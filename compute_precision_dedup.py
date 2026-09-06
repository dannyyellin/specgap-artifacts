"""
Compute requirement-level (deduplicated) precision across all 256 detection
runs (4 detector models x 4 methods x 16 variants) and both judges
(gpt-5.4, claude-sonnet-4-6).

Background: under the paper's set semantics (2026-07-08 decision: requirements
are single-location by definition, so omissions/additions are plain sets and
duplicate detections of the same requirement are counted once), Precision is:

  Precision(O) = |Delta_minus ∩ O| / |delta ∩ O|

with both counts over DISTINCT requirements:
  numerator   = distinct true-gap requirements (Delta_minus) matched by at
                least one omission item
  denominator = distinct removed requirements (delta, true-gap or inferred)
                matched by at least one omission item

This differs from compute_precision_tracked.py, which counts omission ITEMS
in both numerator and denominator. Both views are retained per the standing
dual-reporting convention; this script produces the requirement-level view
that matches the paper's formal definition.

Recall under set semantics is unchanged from compute_recall_tracked.py
(it already counts distinct requirement IDs); this script recomputes it
anyway and cross-checks equality against results/recall_tracked.csv.

Same inputs and ground truth as the sibling scripts -- no LLM calls:
  - results/.../omissions_match_{judge}.json (existing judge match files)
  - results/inferability-consistency.txt (microservices GAP/INF/PAR consensus)
  - results/restestbench/{variant}/per-req/gpt-5.4/summary.json (RESTestBench)
R13 correction applied: public-library/logs-R12R13's R13 is excluded from
delta entirely (invalid removal); omission items the judge matched to R13
are excluded from both numerator and denominator (counted in n_invalid).

strict/broad variants as in the sibling scripts:
  strict: only MATCH-label items count.
  broad:  MATCH and PARTIAL-label items count.

Per-run precision is undefined when the denominator |delta ∩ O| is 0 (the
run matched no removed requirements at all); such runs are excluded from
per-run averages. Aggregate tables report POOLED precision (summed
numerators / summed denominators across runs), which sidesteps the
undefined-run issue; the count of undefined runs is reported alongside.

Usage:
  python compute_precision_dedup.py

Output:
  results/precision_dedup.csv -- per-run breakdown (judge x detector x
                                  method x variant), strict/broad columns.
  Aggregate tables printed to stdout (by detector model, by method, overall,
  per judge), plus a cross-check that recall matches recall_tracked.csv.
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
from compute_recall_tracked import (
    microservices_delta_and_true_gaps,
    restestbench_delta_and_true_gaps,
)

RESULTS_DIR = md.RESULTS_DIR


def classify_run(entry, judge, delta, true_gaps):
    match_path = md.match_filepath(entry["result_dir"], "omissions_match", judge)
    if not os.path.exists(match_path):
        return None
    with open(match_path) as f:
        data = json.load(f)
    matches = data.get("result", {}).get("matches", [])

    found_delta = {"strict": set(), "broad": set()}
    found_gaps = {"strict": set(), "broad": set()}
    n_invalid = 0

    for m in matches:
        label = m.get("label")
        req_id = m.get("requirement_id")
        if label == "NONE" or not req_id:
            continue
        if req_id not in delta:
            n_invalid += 1  # e.g. logs R13 after the invalid-removal correction
            continue
        found_delta["broad"].add(req_id)
        if req_id in true_gaps:
            found_gaps["broad"].add(req_id)
        if label == "MATCH":
            found_delta["strict"].add(req_id)
            if req_id in true_gaps:
                found_gaps["strict"].add(req_id)

    def prec(mode):
        d = len(found_delta[mode])
        return len(found_gaps[mode]) / d if d else None

    def rec(mode):
        return len(found_gaps[mode]) / len(true_gaps) if true_gaps else None

    return {
        "n_omission_items": len(matches),
        "n_delta": len(delta),
        "n_true_gaps": len(true_gaps),
        "n_invalid": n_invalid,
        "found_delta_strict": len(found_delta["strict"]),
        "found_gaps_strict": len(found_gaps["strict"]),
        "precision_dedup_strict": prec("strict"),
        "recall_dedup_strict": rec("strict"),
        "found_delta_broad": len(found_delta["broad"]),
        "found_gaps_broad": len(found_gaps["broad"]),
        "precision_dedup_broad": prec("broad"),
        "recall_dedup_broad": rec("broad"),
    }


def print_aggregate(rows, group_key, label):
    print(f"\n=== precision_dedup BY {label} (pooled) ===")
    print(f"{label:<22} {'n':>4} {'gaps_s':>7} {'delta_s':>8} {'prec_s':>7} {'undef_s':>8} "
          f"{'gaps_b':>7} {'delta_b':>8} {'prec_b':>7} {'undef_b':>8}")
    print("-" * 92)
    groups = defaultdict(list)
    for r in rows:
        groups[group_key(r)].append(r)
    for key in sorted(groups):
        subset = groups[key]
        gs = sum(r["found_gaps_strict"] for r in subset)
        ds = sum(r["found_delta_strict"] for r in subset)
        gb = sum(r["found_gaps_broad"] for r in subset)
        db = sum(r["found_delta_broad"] for r in subset)
        us = sum(1 for r in subset if r["found_delta_strict"] == 0)
        ub = sum(1 for r in subset if r["found_delta_broad"] == 0)

        def f(n, d):
            return f"{n/d:.3f}" if d else "?"

        print(f"{key:<22} {len(subset):>4} {gs:>7} {ds:>8} {f(gs,ds):>7} {us:>8} "
              f"{gb:>7} {db:>8} {f(gb,db):>7} {ub:>8}")


def cross_check_recall(csv_rows):
    """Verify recall counts match results/recall_tracked.csv exactly."""
    path = os.path.join(RESULTS_DIR, "recall_tracked.csv")
    if not os.path.exists(path):
        print("\nWARNING: recall_tracked.csv not found; skipping cross-check.")
        return
    with open(path) as f:
        prior = {(r["judge_model"], r["variant"], r["detector_model"], r["method"]):
                 (int(r["found_strict"]), int(r["found_broad"]), int(r["n_true_gaps"]))
                 for r in csv.DictReader(f)}
    mismatches = 0
    for r in csv_rows:
        key = (r["judge_model"], r["variant"], r["detector_model"], r["method"])
        expected = prior.get(key)
        actual = (r["found_gaps_strict"], r["found_gaps_broad"], r["n_true_gaps"])
        if expected != actual:
            mismatches += 1
            print(f"  RECALL MISMATCH {key}: recall_tracked={expected} here={actual}")
    if mismatches == 0:
        print(f"\nCross-check PASSED: recall counts identical to recall_tracked.csv "
              f"for all {len(csv_rows)} (run x judge) rows.")
    else:
        print(f"\nCross-check FAILED: {mismatches} mismatching rows (see above).")


def main():
    micro_gt = load_microservices_ground_truth()
    rb_gt = load_restestbench_ground_truth()

    entries = [e for e in md.collect_entries() if e["model"] != "per-req"]
    print(f"Found {len(entries)} detection runs (excluding per-req).")
    if len(entries) != 256:
        print(f"WARNING: expected 256 runs, found {len(entries)}.")

    variant_sets = {}
    for entry in entries:
        key = (entry["type"], entry["variant"])
        if key in variant_sets:
            continue
        if entry["type"] == "microservices":
            variant_sets[key] = microservices_delta_and_true_gaps(micro_gt, entry["variant"])
        else:
            variant_sets[key] = restestbench_delta_and_true_gaps(rb_gt, entry["variant"])

    judges = ["gpt-5.4", "claude-sonnet-4-6"]
    csv_rows = []

    for judge in judges:
        rows_for_judge = []
        for entry in entries:
            delta, true_gaps = variant_sets[(entry["type"], entry["variant"])]
            result = classify_run(entry, judge, delta, true_gaps)
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

        print(f"\n{'#' * 92}")
        print(f"  JUDGE MODEL: {judge}  ({len(rows_for_judge)} runs)")
        print(f"{'#' * 92}")
        print_aggregate(rows_for_judge, lambda r: r["detector_model"], "detector_model")
        print_aggregate(rows_for_judge, lambda r: r["method"], "method")
        print_aggregate(rows_for_judge, lambda r: "OVERALL", "OVERALL")

    cross_check_recall(csv_rows)

    out_path = os.path.join(RESULTS_DIR, "precision_dedup.csv")
    fields = ["judge_model", "experiment_type", "app", "variant", "detector_model", "method",
              "n_omission_items", "n_delta", "n_true_gaps", "n_invalid",
              "found_delta_strict", "found_gaps_strict",
              "precision_dedup_strict", "recall_dedup_strict",
              "found_delta_broad", "found_gaps_broad",
              "precision_dedup_broad", "recall_dedup_broad"]
    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in csv_rows:
            out_row = dict(row)
            for k in ("precision_dedup_strict", "recall_dedup_strict",
                      "precision_dedup_broad", "recall_dedup_broad"):
                if out_row[k] is None:
                    out_row[k] = ""
            writer.writerow(out_row)
    print(f"\nPer-run CSV written to {out_path}")


if __name__ == "__main__":
    main()
