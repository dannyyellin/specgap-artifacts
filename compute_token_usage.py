"""
Compute token usage per prompting method across all 256 Gap Detector runs.

Reproduces Table 6 of the paper ("Average tokens per gap-detector run by
prompting method") and the per-dataset breakdown.

Input:  the "usage" block ({prompt_tokens, completion_tokens, total_tokens})
        recorded in every detection run's output file at
            results/{app}/{variant}/{gd_model}/{method}/detection_result.json
        Each prompting method covers 64 runs: 4 GD models x 16 reduced specs
        (44 microservices + 20 RESTestBench).

Output: aggregate tables printed to stdout, and
        results/token_usage_by_method.csv (one row per dataset x method).

No LLM calls; reads existing result files only.
"""

import csv
import glob
import json
import os

REPO_DIR = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIR = os.path.join(REPO_DIR, "results")

MICRO_APPS = {"nutrition", "public-library", "pet-store"}
METHODS = ["zeroshot", "oneshot-tracker", "oneshot-warehouse", "twoshot"]


def collect():
    """Return agg[(dataset, method)] = [n_runs, sum_prompt, sum_completion, sum_total]."""
    agg = {}
    pattern = os.path.join(RESULTS_DIR, "**", "detection_result.json")
    for path in glob.glob(pattern, recursive=True):
        rel = os.path.relpath(path, RESULTS_DIR)
        parts = rel.split(os.sep)  # {app}/{variant}/{gd_model}/{method}/detection_result.json
        if len(parts) != 5:
            continue  # skips per-req and any non-run layout
        app, method = parts[0], parts[3]
        if method not in METHODS:
            continue
        dataset = ("microservices" if app in MICRO_APPS
                   else "restestbench" if app == "restestbench"
                   else None)
        if dataset is None:
            continue
        try:
            usage = json.load(open(path)).get("usage") or {}
        except (json.JSONDecodeError, OSError):
            continue
        p = usage.get("prompt_tokens", 0)
        c = usage.get("completion_tokens", 0)
        t = usage.get("total_tokens", 0)
        if not t:
            continue
        for key in [(dataset, method), ("BOTH", method)]:
            n = agg.setdefault(key, [0, 0, 0, 0])
            n[0] += 1
            n[1] += p
            n[2] += c
            n[3] += t
    return agg


def report(agg):
    csv_rows = []
    for dataset in ["microservices", "restestbench", "BOTH"]:
        print(f"\n=== {dataset}: average tokens per GD run, by prompting method ===")
        print(f"{'method':<20}{'runs':>5}{'prompt':>10}{'compl.':>9}{'total':>9}{'x vs 0-shot':>13}")
        base_total = None
        for method in METHODS:
            if (dataset, method) not in agg:
                continue
            n, p, c, t = agg[(dataset, method)]
            avg_p, avg_c, avg_t = p / n, c / n, t / n
            if method == "zeroshot":
                base_total = avg_t
            ratio = f"{avg_t / base_total:.2f}" if base_total else "-"
            print(f"{method:<20}{n:>5}{avg_p:>10.0f}{avg_c:>9.0f}{avg_t:>9.0f}{ratio:>13}")
            csv_rows.append({
                "dataset": dataset, "method": method, "n_runs": n,
                "avg_prompt_tokens": round(avg_p), "avg_completion_tokens": round(avg_c),
                "avg_total_tokens": round(avg_t),
                "ratio_vs_zeroshot": round(avg_t / base_total, 2) if base_total else "",
                "sum_total_tokens": t,
            })

    out_path = os.path.join(RESULTS_DIR, "token_usage_by_method.csv")
    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(csv_rows[0].keys()))
        writer.writeheader()
        writer.writerows(csv_rows)
    print(f"\nCSV written to {out_path}")


if __name__ == "__main__":
    agg = collect()
    n_total = sum(v[0] for k, v in agg.items() if k[0] != "BOTH")
    print(f"Collected usage from {n_total} detection runs (expected 256).")
    report(agg)
