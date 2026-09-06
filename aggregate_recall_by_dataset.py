"""
Per-dataset (microservices vs. RESTestBench) aggregate recall tables for
the paper's results section — sibling of aggregate_precision_by_dataset.py.

Reads the existing per-run recall CSV — no LLM calls, no new experiments,
pure re-aggregation:
  - results/recall_tracked.csv  (requirement-level adjusted recall; matches
    the paper's Equation (2): found true-gap requirements / |Delta_minus|,
    with the R13 correction applied)

For each judge x dataset, prints OVERALL, by-detector-model, and by-method
tables with recall (strict / broad) under BOTH aggregation conventions:
  micro (pooled):  summed found / summed n_true_gaps across runs
  macro:           mean of per-run ratios (no undefined runs exist --
                   Delta_minus is non-empty for all 16 variants)
Both are shown because the aggregation-convention decision (TODO.md) is
still open; the earlier recall_tracked aggregate tables were macro-only.

Usage:
  python aggregate_recall_by_dataset.py

Output:
  results/recall_by_dataset.csv  (one row per judge x dataset x group)
  Tables printed to stdout.
"""

import os
import csv
from collections import defaultdict

REPO_DIR = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIR = os.path.join(REPO_DIR, "results")

DATASETS = ["microservices", "restestbench"]
JUDGES = ["gpt-5.4", "claude-sonnet-4-6"]


def fmt(x):
    return f"{x:.3f}" if x is not None else "  n/a"


def safe_div(a, b):
    return a / b if b else None


def aggregate(rows, group_label, group_value):
    fs = sum(int(r["found_strict"]) for r in rows)
    fb = sum(int(r["found_broad"]) for r in rows)
    tg = sum(int(r["n_true_gaps"]) for r in rows)
    macro_s = [float(r["recall_strict"]) for r in rows if r["recall_strict"] != ""]
    macro_b = [float(r["recall_broad"]) for r in rows if r["recall_broad"] != ""]
    return {
        "group_type": group_label, "group_value": group_value, "n_runs": len(rows),
        "recall_strict_micro": safe_div(fs, tg),
        "recall_broad_micro": safe_div(fb, tg),
        "recall_strict_macro": safe_div(sum(macro_s), len(macro_s)),
        "recall_broad_macro": safe_div(sum(macro_b), len(macro_b)),
    }


def main():
    with open(os.path.join(RESULTS_DIR, "recall_tracked.csv")) as f:
        rows = list(csv.DictReader(f))

    csv_rows = []
    header = (f"{'group':<22} {'n':>4} {'rec_s_micro':>11} {'rec_s_macro':>11} "
              f"{'rec_b_micro':>11} {'rec_b_macro':>11}")

    for judge in JUDGES:
        for dataset in DATASETS:
            subset = [r for r in rows
                      if r["judge_model"] == judge and r["experiment_type"] == dataset]
            print(f"\n{'=' * 78}")
            print(f"  JUDGE: {judge}    DATASET: {dataset}    ({len(subset)} runs)")
            print(f"{'=' * 78}")

            groups = [("OVERALL", lambda r: "OVERALL"),
                      ("detector_model", lambda r: r["detector_model"]),
                      ("method", lambda r: r["method"])]
            for label, keyfn in groups:
                print(f"\n--- by {label} ---")
                print(header)
                print("-" * len(header))
                buckets = defaultdict(list)
                for r in subset:
                    buckets[keyfn(r)].append(r)
                for gv in sorted(buckets):
                    agg = aggregate(buckets[gv], label, gv)
                    agg["judge_model"] = judge
                    agg["experiment_type"] = dataset
                    csv_rows.append(agg)
                    print(f"{gv:<22} {agg['n_runs']:>4} "
                          f"{fmt(agg['recall_strict_micro']):>11} {fmt(agg['recall_strict_macro']):>11} "
                          f"{fmt(agg['recall_broad_micro']):>11} {fmt(agg['recall_broad_macro']):>11}")

    out_path = os.path.join(RESULTS_DIR, "recall_by_dataset.csv")
    fields = ["judge_model", "experiment_type", "group_type", "group_value", "n_runs",
              "recall_strict_micro", "recall_strict_macro",
              "recall_broad_micro", "recall_broad_macro"]
    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in csv_rows:
            writer.writerow({k: ("" if row[k] is None else row[k]) for k in fields})
    print(f"\nCSV written to {out_path}")


if __name__ == "__main__":
    main()
