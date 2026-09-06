"""
Compute precision_tracked across all 256 detection runs (4 detector models x
4 methods x 16 variants) and both judges (gpt-5.4, claude-sonnet-4-6).

Background: precision_tracked = TP / (TP + FP_tracked), where an omission
item only enters the calculation if the LLM judge matched it to one of the
36/37 tracked removed requirements (i.e. it has a requirement_id). Items with
no requirement_id (match label NONE, "FP_extra") are excluded entirely, not
counted as either TP or FP. Among the tracked items:
  TP         = matched requirement is a genuine gap (the code does NOT
               actually implement it)
  FP_tracked = matched requirement was implemented anyway despite its
               removal (the code HAS it; the detector is wrong to flag it)

This reuses match_detections.py's existing collect_entries() and the
omissions_match_{judge}.json files already on disk -- no new LLM calls, no
new experiments. Ground truth for "was this removed requirement actually
implemented in the generated code" comes from two existing sources (both
based on reading the actual generated code, not prose prediction):
  - Microservices (11 variants, 36 requirements):
      results/inferability-consistency.txt  (3-pass consensus: GAP/INF/PAR)
  - RESTestBench (5 variants, 37 requirements):
      results/restestbench/{variant}/per-req/gpt-5.4/summary.json
      (removed_not_implemented / removed_implemented lists)

Two variants are computed and reported side by side (2026-07-01 decision:
report both rather than pick one -- a sanity check against the manual
gpt-5.4/zeroshot/microservices baseline in precision-analysis.txt found the
two diverge by ~10pp, so neither is reported alone):
  strict (MATCH-only): only full MATCH-label items count as "tracked."
  broad  (MATCH+PARTIAL): MATCH and PARTIAL-label items both count as
    "tracked" (PARTIAL matches still carry a requirement_id).

Usage:
  python compute_precision_tracked.py

Output:
  results/precision_tracked.csv  -- per-run breakdown (judge x detector x
                                     method x variant), both variants as
                                     separate column groups
  Aggregate tables printed to stdout: by detector model, by method, overall,
  each reporting precision_tracked_strict, precision_tracked_broad, AND the
  exclusion rate side by side (required companion figure -- see
  results-analysis.txt).
"""

import os
import re
import csv
import json
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import match_detections as md

RESULTS_DIR = md.RESULTS_DIR
INFERABILITY_CONSISTENCY_FILE = os.path.join(RESULTS_DIR, "inferability-consistency.txt")


# ---------------------------------------------------------------------------
# Ground truth: microservices (inferability-consistency.txt consensus table)
# ---------------------------------------------------------------------------

def load_microservices_ground_truth():
    """Return dict[(short_name, req_id)] -> 'GAP' | 'INF' | 'PAR'."""
    with open(INFERABILITY_CONSISTENCY_FILE) as f:
        text = f.read()

    # Table rows look like:
    #   borrows     R1           | GAP    | GAP    | GAP    | GAP    Y
    #   dishes      R4b          | INF    | INF    | INF    | INF    Y
    row_re = re.compile(
        r'^(?P<short>[A-Za-z]+)\s+(?P<req>R\d+[a-z]?)\s*\|'
        r'\s*\S+\s*\|\s*\S+\s*\|\s*\S+\s*\|\s*(?P<consensus>GAP|INF|PAR)\b',
        re.MULTILINE,
    )
    ground_truth = {}
    for m in row_re.finditer(text):
        ground_truth[(m.group("short"), m.group("req"))] = m.group("consensus")

    if len(ground_truth) != 36:
        raise ValueError(
            f"Expected 36 microservice ground-truth rows, parsed {len(ground_truth)}. "
            f"inferability-consistency.txt format may have changed."
        )
    return ground_truth


# Microservice requirements excluded from delta entirely — omission items
# matched to these are excluded from both TP and FP_tracked (treated as
# "unknown"), same as the exclusion applied in compute_recall_tracked.py.
# petorder R10: full spec leak (approved 2026-07-17; see compute_recall_tracked.py).
# logs R13: invalid removal (R13 has consensus INF in the source file, so
#   without explicit exclusion it would be counted as FP_tracked — here we
#   exclude it entirely to mirror the recall treatment).
_MICRO_EXCLUDED = {("logs", "R13"), ("petorder", "R10")}


def lookup_microservices(ground_truth, variant, req_id):
    short_name = variant.split("-", 1)[0]
    if (short_name, req_id) in _MICRO_EXCLUDED:
        return None  # excluded from delta; treated as "unknown" (neither TP nor FP)
    return ground_truth.get((short_name, req_id))


# ---------------------------------------------------------------------------
# Ground truth: RESTestBench (per-req summary.json, code-based verdicts)
# ---------------------------------------------------------------------------

def load_restestbench_ground_truth():
    """Return dict[variant] -> {'not_implemented': set[str], 'implemented': set[str]}."""
    rb_dir = os.path.join(RESULTS_DIR, "restestbench")
    ground_truth = {}
    for variant in sorted(os.listdir(rb_dir)):
        summary_path = os.path.join(rb_dir, variant, "per-req", "gpt-5.4", "summary.json")
        if not os.path.exists(summary_path):
            continue
        with open(summary_path) as f:
            summary = json.load(f)
        ground_truth[variant] = {
            "not_implemented": {f"R{n}" for n in summary["removed_not_implemented"]},
            "implemented": {f"R{n}" for n in summary["removed_implemented"]},
        }
    if len(ground_truth) != 5:
        raise ValueError(
            f"Expected 5 RESTestBench per-req summaries, found {len(ground_truth)}."
        )
    return ground_truth


def lookup_restestbench(ground_truth, variant, req_id):
    variant_gt = ground_truth.get(variant)
    if variant_gt is None:
        return None
    if req_id in variant_gt["not_implemented"]:
        return "GAP"
    if req_id in variant_gt["implemented"]:
        return "INF"
    return None


# ---------------------------------------------------------------------------
# Per-run classification
# ---------------------------------------------------------------------------

def _bump(counts, verdict):
    if verdict == "INF":
        counts["fp_tracked"] += 1
    elif verdict in ("GAP", "PAR"):
        counts["tp"] += 1
    else:
        counts["unknown"] += 1


def classify_run(entry, judge, micro_gt, rb_gt):
    """Return dict with strict/broad tp+fp_tracked+unknown, excluded, n_omissions."""
    match_path = md.match_filepath(entry["result_dir"], "omissions_match", judge)
    if not os.path.exists(match_path):
        return None
    with open(match_path) as f:
        data = json.load(f)
    matches = data.get("result", {}).get("matches", [])

    strict = {"tp": 0, "fp_tracked": 0, "unknown": 0}
    broad = {"tp": 0, "fp_tracked": 0, "unknown": 0}
    excluded = 0

    for m in matches:
        label = m.get("label")
        req_id = m.get("requirement_id")
        if label == "NONE" or not req_id:
            excluded += 1
            continue

        if entry["type"] == "microservices":
            verdict = lookup_microservices(micro_gt, entry["variant"], req_id)
        else:
            verdict = lookup_restestbench(rb_gt, entry["variant"], req_id)

        # broad: MATCH and PARTIAL both count as tracked
        _bump(broad, verdict)
        # strict: only full MATCH counts as tracked; PARTIAL is excluded
        if label == "MATCH":
            _bump(strict, verdict)
        else:
            excluded += 0  # PARTIAL-under-strict is reported via strict_excluded below

    # strict's excluded count includes PARTIAL items (which broad treats as tracked)
    n_partial = sum(1 for m in matches if m.get("label") == "PARTIAL" and m.get("requirement_id"))
    strict_excluded = excluded + n_partial

    return {
        "n_omissions": len(matches),
        "excluded_broad": excluded,
        "excluded_strict": strict_excluded,
        "tp_strict": strict["tp"], "fp_tracked_strict": strict["fp_tracked"], "unknown_strict": strict["unknown"],
        "tp_broad": broad["tp"], "fp_tracked_broad": broad["fp_tracked"], "unknown_broad": broad["unknown"],
    }


# ---------------------------------------------------------------------------
# Aggregation + reporting
# ---------------------------------------------------------------------------

def safe_div(a, b):
    return a / b if b else None


def print_aggregate(rows, group_key, label):
    print(f"\n=== precision_tracked BY {label} ===")
    print(f"{label:<22} {'n':>4} "
          f"{'prec_strict':>12} {'excl_strict':>12} "
          f"{'prec_broad':>12} {'excl_broad':>12}")
    print("-" * 78)
    groups = defaultdict(list)
    for r in rows:
        groups[group_key(r)].append(r)
    for key in sorted(groups):
        subset = groups[key]
        n_om = sum(r["n_omissions"] for r in subset)

        tp_s = sum(r["tp_strict"] for r in subset)
        fpt_s = sum(r["fp_tracked_strict"] for r in subset)
        excl_s = sum(r["excluded_strict"] for r in subset)
        prec_s = safe_div(tp_s, tp_s + fpt_s)
        excl_rate_s = safe_div(excl_s, n_om)

        tp_b = sum(r["tp_broad"] for r in subset)
        fpt_b = sum(r["fp_tracked_broad"] for r in subset)
        excl_b = sum(r["excluded_broad"] for r in subset)
        prec_b = safe_div(tp_b, tp_b + fpt_b)
        excl_rate_b = safe_div(excl_b, n_om)

        def f(x):
            return f"{x:.3f}" if x is not None else "?"

        print(f"{key:<22} {len(subset):>4} "
              f"{f(prec_s):>12} {f(excl_rate_s):>12} "
              f"{f(prec_b):>12} {f(excl_rate_b):>12}")


def main():
    micro_gt = load_microservices_ground_truth()
    rb_gt = load_restestbench_ground_truth()

    entries = [e for e in md.collect_entries() if e["model"] != "per-req"]
    print(f"Found {len(entries)} detection runs (excluding per-req).")
    if len(entries) != 256:
        print(f"WARNING: expected 256 runs, found {len(entries)}.")

    judges = ["gpt-5.4", "claude-sonnet-4-6"]
    csv_rows = []
    unknown_total = 0

    for judge in judges:
        rows_for_judge = []
        for entry in entries:
            result = classify_run(entry, judge, micro_gt, rb_gt)
            if result is None:
                continue
            row = {
                "judge_model": judge,
                "experiment_type": entry["type"],
                "app": entry["app"],
                "variant": entry["variant"],
                "detector_model": entry["model"],
                "method": entry["method"],
                **result,
            }
            row["precision_tracked_strict"] = safe_div(row["tp_strict"], row["tp_strict"] + row["fp_tracked_strict"])
            row["exclusion_rate_strict"] = safe_div(row["excluded_strict"], row["n_omissions"])
            row["precision_tracked_broad"] = safe_div(row["tp_broad"], row["tp_broad"] + row["fp_tracked_broad"])
            row["exclusion_rate_broad"] = safe_div(row["excluded_broad"], row["n_omissions"])
            rows_for_judge.append(row)
            csv_rows.append(row)
            unknown_total += result["unknown_strict"] + result["unknown_broad"]

        print(f"\n{'#' * 78}")
        print(f"  JUDGE MODEL: {judge}  ({len(rows_for_judge)} runs)")
        print(f"{'#' * 78}")
        print_aggregate(rows_for_judge, lambda r: r["detector_model"], "detector_model")
        print_aggregate(rows_for_judge, lambda r: r["method"], "method")
        print_aggregate(rows_for_judge, lambda r: "OVERALL", "OVERALL")

    if unknown_total:
        print(f"\nWARNING: {unknown_total} matched items had no ground-truth verdict "
              f"(requirement_id not found in the ground-truth source for that variant). "
              f"These were excluded from TP/FP_tracked like FP_extra -- check the "
              f"detection_id / requirement_id values for typos or off-by-one issues.")

    out_path = os.path.join(RESULTS_DIR, "precision_tracked.csv")
    fields = ["judge_model", "experiment_type", "app", "variant", "detector_model", "method",
              "n_omissions",
              "tp_strict", "fp_tracked_strict", "excluded_strict", "unknown_strict",
              "precision_tracked_strict", "exclusion_rate_strict",
              "tp_broad", "fp_tracked_broad", "excluded_broad", "unknown_broad",
              "precision_tracked_broad", "exclusion_rate_broad"]
    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(csv_rows)
    print(f"\nPer-run CSV written to {out_path}")


if __name__ == "__main__":
    main()
