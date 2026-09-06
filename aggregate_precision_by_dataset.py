"""
Per-dataset (microservices vs. RESTestBench) aggregate precision tables for
the paper's results section.

Reads the two existing per-run precision CSVs — no LLM calls, no new
experiments, pure re-aggregation:
  - results/precision_dedup.csv    (requirement-level, matches the paper's
                                     Equation (1); primary figure)
  - results/precision_tracked.csv  (item-level, auxiliary; sole source of
                                     the exclusion-rate companion figure)

For each judge x dataset, prints OVERALL, by-detector-model, and by-method
tables with:
  prec_req_s / prec_req_b   requirement-level precision (strict / broad), POOLED
  prec_itm_s / prec_itm_b   item-level precision (strict / broad), POOLED
  excl_s / excl_b           item exclusion rate (strict / broad), POOLED
Pooled (micro) = summed numerators / summed denominators across runs.

A final comparison table reports OVERALL requirement-level precision under
both aggregation conventions (micro/pooled vs. macro/mean-of-defined-runs)
per judge x dataset, to inform the open macro-vs-micro decision (TODO.md).

Usage:
  python aggregate_precision_by_dataset.py

Output:
  results/precision_by_dataset.csv  (one row per judge x dataset x group)
  Tables printed to stdout.
"""

import os
import csv
from collections import defaultdict

REPO_DIR = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIR = os.path.join(REPO_DIR, "results")

DATASETS = ["microservices", "restestbench"]
JUDGES = ["gpt-5.4", "claude-sonnet-4-6"]


def load(name):
    with open(os.path.join(RESULTS_DIR, name)) as f:
        return list(csv.DictReader(f))


def key(r):
    return (r["judge_model"], r["experiment_type"], r["variant"],
            r["detector_model"], r["method"])


def fmt(x):
    return f"{x:.3f}" if x is not None else "  n/a"


def safe_div(a, b):
    return a / b if b else None


def aggregate(dedup_rows, tracked_by_key, group_label, group_value):
    """Pooled metrics for one group of dedup rows (tracked rows joined by key)."""
    gs = ds = gb = db = 0
    tp_s = fpt_s = tp_b = fpt_b = excl_s = excl_b = n_items = 0
    macro_s, macro_b = [], []
    for r in dedup_rows:
        gs += int(r["found_gaps_strict"]); ds += int(r["found_delta_strict"])
        gb += int(r["found_gaps_broad"]); db += int(r["found_delta_broad"])
        if r["precision_dedup_strict"] != "":
            macro_s.append(float(r["precision_dedup_strict"]))
        if r["precision_dedup_broad"] != "":
            macro_b.append(float(r["precision_dedup_broad"]))
        t = tracked_by_key[key(r)]
        tp_s += int(t["tp_strict"]); fpt_s += int(t["fp_tracked_strict"])
        tp_b += int(t["tp_broad"]); fpt_b += int(t["fp_tracked_broad"])
        excl_s += int(t["excluded_strict"]); excl_b += int(t["excluded_broad"])
        n_items += int(t["n_omissions"])
    return {
        "group_type": group_label, "group_value": group_value, "n_runs": len(dedup_rows),
        "prec_req_strict": safe_div(gs, ds), "prec_req_broad": safe_div(gb, db),
        "prec_req_strict_macro": safe_div(sum(macro_s), len(macro_s)),
        "prec_req_broad_macro": safe_div(sum(macro_b), len(macro_b)),
        "prec_item_strict": safe_div(tp_s, tp_s + fpt_s),
        "prec_item_broad": safe_div(tp_b, tp_b + fpt_b),
        "excl_rate_strict": safe_div(excl_s, n_items),
        "excl_rate_broad": safe_div(excl_b, n_items),
    }


def main():
    dedup = load("precision_dedup.csv")
    tracked = load("precision_tracked.csv")
    tracked_by_key = {key(r): r for r in tracked}
    assert all(key(r) in tracked_by_key for r in dedup), "CSV row mismatch"

    csv_rows = []
    header = (f"{'group':<22} {'n':>4} {'prec_req_s':>10} {'prec_req_b':>10} "
              f"{'prec_itm_s':>10} {'prec_itm_b':>10} {'excl_s':>7} {'excl_b':>7}")

    for judge in JUDGES:
        for dataset in DATASETS:
            subset = [r for r in dedup
                      if r["judge_model"] == judge and r["experiment_type"] == dataset]
            print(f"\n{'=' * 88}")
            print(f"  JUDGE: {judge}    DATASET: {dataset}    ({len(subset)} runs)")
            print(f"{'=' * 88}")

            groups = [("OVERALL", lambda r: "OVERALL"),
                      ("detector_model", lambda r: r["detector_model"]),
                      ("method", lambda r: r["method"])]
            for label, keyfn in groups:
                print(f"\n--- by {label} (pooled) ---")
                print(header)
                print("-" * len(header))
                buckets = defaultdict(list)
                for r in subset:
                    buckets[keyfn(r)].append(r)
                for gv in sorted(buckets):
                    agg = aggregate(buckets[gv], tracked_by_key, label, gv)
                    agg["judge_model"] = judge
                    agg["experiment_type"] = dataset
                    csv_rows.append(agg)
                    print(f"{gv:<22} {agg['n_runs']:>4} "
                          f"{fmt(agg['prec_req_strict']):>10} {fmt(agg['prec_req_broad']):>10} "
                          f"{fmt(agg['prec_item_strict']):>10} {fmt(agg['prec_item_broad']):>10} "
                          f"{fmt(agg['excl_rate_strict']):>7} {fmt(agg['excl_rate_broad']):>7}")

    print(f"\n{'=' * 88}")
    print("  MICRO (pooled) vs MACRO (mean of defined per-run ratios) — "
          "requirement-level, OVERALL")
    print(f"{'=' * 88}")
    print(f"{'judge':<20} {'dataset':<15} {'micro_s':>8} {'macro_s':>8} "
          f"{'micro_b':>8} {'macro_b':>8}")
    print("-" * 72)
    for row in csv_rows:
        if row["group_type"] == "OVERALL":
            print(f"{row['judge_model']:<20} {row['experiment_type']:<15} "
                  f"{fmt(row['prec_req_strict']):>8} {fmt(row['prec_req_strict_macro']):>8} "
                  f"{fmt(row['prec_req_broad']):>8} {fmt(row['prec_req_broad_macro']):>8}")

    out_path = os.path.join(RESULTS_DIR, "precision_by_dataset.csv")
    fields = ["judge_model", "experiment_type", "group_type", "group_value", "n_runs",
              "prec_req_strict", "prec_req_broad",
              "prec_req_strict_macro", "prec_req_broad_macro",
              "prec_item_strict", "prec_item_broad",
              "excl_rate_strict", "excl_rate_broad"]
    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in csv_rows:
            writer.writerow({k: ("" if row[k] is None else row[k]) for k in fields})
    print(f"\nCSV written to {out_path}")


if __name__ == "__main__":
    main()
