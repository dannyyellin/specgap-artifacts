"""
Compute adjusted recall (Recall(O) per the paper's formal definition) across
all 256 detection runs (4 detector models x 4 methods x 16 variants) and
both judges (gpt-5.4, claude-sonnet-4-6).

Background: Recall(O) = (O|delta ∩ Delta_minus) / Delta_minus, where
Delta_minus = delta - Delta_plus_2 is the TRUE GAP set for a variant --
removed requirements the generator did NOT implement anyway. This excludes
generator-inferred removed requirements (Delta_plus_2) from the denominator,
so the detector is not penalized for "missing" something that was never
actually absent from the code.

For each run, Recall = (number of distinct Delta_minus requirement IDs with
at least one matching omission item) / |Delta_minus|.

This is the sibling computation to compute_precision_tracked.py and reuses
its ground-truth-loading functions verbatim -- no new LLM calls, no new
experiments, just reprocessing the existing omissions_match_{judge}.json
files against the same ground truth sources:
  - Microservices (11 variants): results/inferability-consistency.txt
    (3-pass consensus GAP/INF/PAR), MINUS the R13 correction (see below).
  - RESTestBench (5 variants): results/restestbench/{variant}/per-req/
    gpt-5.4/summary.json (removed_not_implemented / removed_implemented).

R13 CORRECTION: public-library/logs-R12R13's R13 was determined to be an
invalid removal (the reduced spec still explicitly described POST /logs
with its full payload -- see results-analysis.txt, "CORRECTION: R13 INVALID
REMOVAL"). R13 is therefore excluded entirely from delta/Delta_minus for
this variant; only R12 counts. This mirrors the fix already applied in
match_summary_updated.csv (n_removed=1 for this variant).

Two variants (strict/broad) are computed, matching compute_precision_tracked.py:
  strict: only full MATCH-label items count as "found."
  broad:  MATCH and PARTIAL-label items both count as "found."

Per-variant Delta_minus can be empty (all removed reqs for that variant were
inferred). Per the 2026-07-07 discussion, Recall is left UNDEFINED (not 0,
not 1) for such variants, and they are excluded from averages -- consistent
with how fastapi-R1's empty CleanGaps set was already handled ("n/a") in the
earlier clean-recall analysis.

Usage:
  python compute_recall_tracked.py

Output:
  results/recall_tracked.csv  -- per-run breakdown (judge x detector x
                                  method x variant), strict/broad as
                                  separate column groups. recall_strict /
                                  recall_broad are blank (empty string) for
                                  the undefined (Delta_minus empty) case.
  Aggregate tables printed to stdout: by detector model, by method, overall,
  each reporting recall_strict, recall_broad, and n_undefined (count of
  variants excluded from that average due to an empty Delta_minus).
"""

import os
import csv
import json
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import match_detections as md
from compute_precision_tracked import (
    load_microservices_ground_truth,
    load_restestbench_ground_truth,
)

RESULTS_DIR = md.RESULTS_DIR

# Requirements excluded from delta entirely (invalid removals or full spec leaks).
# R13 (public-library/logs-R12R13): invalid removal — reduced spec still
#   described POST /logs with full payload (2026-06-30).
# R10 (pet-store/petorder-R8R9R10): full spec leak — reduced spec's general
#   guideline "All resource ids must be unique and cannot be reused" subsumes
#   the removed sentence; approved for exclusion 2026-07-17.
R13_EXCLUDED = {("logs", "R13"), ("petorder", "R10")}


# ---------------------------------------------------------------------------
# Per-variant delta / true-gap (Delta_minus) sets
# ---------------------------------------------------------------------------

def microservices_delta_and_true_gaps(micro_gt, variant):
    """Return (delta_set, true_gap_set) of requirement_id strings for a
    microservice variant, using inferability-consistency.txt, with exclusions
    applied (R13 and petorder R10)."""
    short_name = variant.split("-", 1)[0]
    delta = set()
    true_gaps = set()
    for (sn, req_id), consensus in micro_gt.items():
        if sn != short_name:
            continue
        if (sn, req_id) in R13_EXCLUDED:
            continue
        delta.add(req_id)
        if consensus in ("GAP", "PAR"):
            true_gaps.add(req_id)
    return delta, true_gaps


def restestbench_delta_and_true_gaps(rb_gt, variant):
    """Return (delta_set, true_gap_set) of requirement_id strings for a
    RESTestBench variant, using per-req/gpt-5.4/summary.json."""
    variant_gt = rb_gt.get(variant)
    if variant_gt is None:
        return set(), set()
    delta = variant_gt["not_implemented"] | variant_gt["implemented"]
    true_gaps = set(variant_gt["not_implemented"])
    return delta, true_gaps


# ---------------------------------------------------------------------------
# Per-run recall
# ---------------------------------------------------------------------------

def compute_recall(entry, judge, micro_gt, rb_gt, true_gaps):
    """Return dict with recall_strict, recall_broad (or None if
    Delta_minus is empty), plus n_true_gaps and n_omissions."""
    match_path = md.match_filepath(entry["result_dir"], "omissions_match", judge)
    if not os.path.exists(match_path):
        return None
    with open(match_path) as f:
        data = json.load(f)
    matches = data.get("result", {}).get("matches", [])

    found_strict = set()
    found_broad = set()
    for m in matches:
        label = m.get("label")
        req_id = m.get("requirement_id")
        if label == "NONE" or not req_id:
            continue
        if req_id in true_gaps:
            found_broad.add(req_id)
            if label == "MATCH":
                found_strict.add(req_id)

    n_true_gaps = len(true_gaps)
    recall_strict = len(found_strict) / n_true_gaps if n_true_gaps else None
    recall_broad = len(found_broad) / n_true_gaps if n_true_gaps else None

    return {
        "n_omissions": len(matches),
        "n_true_gaps": n_true_gaps,
        "found_strict": len(found_strict),
        "found_broad": len(found_broad),
        "recall_strict": recall_strict,
        "recall_broad": recall_broad,
    }


# ---------------------------------------------------------------------------
# Aggregation + reporting
# ---------------------------------------------------------------------------

def print_aggregate(rows, group_key, label):
    print(f"\n=== recall_tracked BY {label} ===")
    print(f"{label:<22} {'n':>4} {'n_def':>6} {'recall_strict':>14} "
          f"{'n_def':>6} {'recall_broad':>13}")
    print("-" * 78)
    groups = defaultdict(list)
    for r in rows:
        groups[group_key(r)].append(r)
    for key in sorted(groups):
        subset = groups[key]
        strict_vals = [r["recall_strict"] for r in subset if r["recall_strict"] is not None]
        broad_vals = [r["recall_broad"] for r in subset if r["recall_broad"] is not None]
        s_mean = sum(strict_vals) / len(strict_vals) if strict_vals else None
        b_mean = sum(broad_vals) / len(broad_vals) if broad_vals else None

        def f(x):
            return f"{x:.3f}" if x is not None else "?"

        print(f"{key:<22} {len(subset):>4} {len(strict_vals):>6} {f(s_mean):>14} "
              f"{len(broad_vals):>6} {f(b_mean):>13}")


def main():
    micro_gt = load_microservices_ground_truth()
    rb_gt = load_restestbench_ground_truth()

    entries = [e for e in md.collect_entries() if e["model"] != "per-req"]
    print(f"Found {len(entries)} detection runs (excluding per-req).")
    if len(entries) != 256:
        print(f"WARNING: expected 256 runs, found {len(entries)}.")

    # Precompute delta/true_gaps per variant once
    variant_true_gaps = {}
    for entry in entries:
        key = (entry["type"], entry["variant"])
        if key in variant_true_gaps:
            continue
        if entry["type"] == "microservices":
            delta, true_gaps = microservices_delta_and_true_gaps(micro_gt, entry["variant"])
        else:
            delta, true_gaps = restestbench_delta_and_true_gaps(rb_gt, entry["variant"])
        variant_true_gaps[key] = (delta, true_gaps)

    print("\nPer-variant Delta_minus (true gap) sizes:")
    for (etype, variant), (delta, true_gaps) in sorted(variant_true_gaps.items()):
        flag = "  <-- Delta_minus EMPTY (recall undefined)" if not true_gaps else ""
        print(f"  {etype:<14} {variant:<38} delta={len(delta):<3} "
              f"true_gaps={len(true_gaps):<3}{flag}")

    judges = ["gpt-5.4", "claude-sonnet-4-6"]
    csv_rows = []

    for judge in judges:
        rows_for_judge = []
        for entry in entries:
            _, true_gaps = variant_true_gaps[(entry["type"], entry["variant"])]
            result = compute_recall(entry, judge, micro_gt, rb_gt, true_gaps)
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
            rows_for_judge.append(row)
            csv_rows.append(row)

        print(f"\n{'#' * 78}")
        print(f"  JUDGE MODEL: {judge}  ({len(rows_for_judge)} runs)")
        print(f"{'#' * 78}")
        print_aggregate(rows_for_judge, lambda r: r["detector_model"], "detector_model")
        print_aggregate(rows_for_judge, lambda r: r["method"], "method")
        print_aggregate(rows_for_judge, lambda r: "OVERALL", "OVERALL")

    out_path = os.path.join(RESULTS_DIR, "recall_tracked.csv")
    fields = ["judge_model", "experiment_type", "app", "variant", "detector_model", "method",
              "n_omissions", "n_true_gaps", "found_strict", "found_broad",
              "recall_strict", "recall_broad"]
    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in csv_rows:
            out_row = dict(row)
            if out_row["recall_strict"] is None:
                out_row["recall_strict"] = ""
            if out_row["recall_broad"] is None:
                out_row["recall_broad"] = ""
            writer.writerow(out_row)
    print(f"\nPer-run CSV written to {out_path}")


if __name__ == "__main__":
    main()
