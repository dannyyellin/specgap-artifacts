"""
Ground-truth recheck for RESTestBench: re-run the per-requirement
implemented/not-implemented check on the 37 REMOVED requirements only,
with 2 models x 2 passes each (gpt-5.4, claude-sonnet-4-6).

Motivation (2026-07-12 discussion): the RESTestBench precision/recall ground
truth (Delta_minus vs I) came from a SINGLE gpt-5.4 pass of
experiment_per_req.py. Three weaknesses: (1) no repeat-consistency estimate
(microservices ground truth has 3 passes / 89% unanimity; RESTestBench has
none); (2) only the 14 IMPLEMENTED verdicts were manually verified — the 23
NOT_IMPLEMENTED verdicts (recall's denominator) were never independently
checked; (3) circularity — gpt-5.4 generated the code, built the ground
truth, and is an evaluated detector.

Protocol: identical to experiment_per_req.py (same system prompt =
prompts/per_req_check.txt with {{CATEGORIES}} from prompts/categories.txt;
same user prompt = requirement_vague + requirement_precise scenario + full
generated code; same classification rule: NOT_IMPLEMENTED iff the returned
omissions list is non-empty; temperature=0). Only the scope differs:
removed requirements only (37 across 5 variants), and 4 verdicts per
requirement (2 models x 2 passes) instead of 1.

Usage:
  python3 ground_truth_recheck.py [--resume] [--dry-run]

Output:
  results/restestbench/ground-truth-recheck/{variant}/R{id}_{model}_pass{k}.json
      (raw per-call record, same fields as experiment_per_req.py records)
  results/restestbench/ground-truth-recheck/recheck_summary.json
      (all verdicts + agreement analysis vs. the original ground truth)
  Comparison table printed to stdout.
"""

import argparse
import json
import os
import sys
from datetime import datetime

REPO_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, REPO_DIR)

from experiment_per_req import (
    SERVICE_CONFIGS, VARIANT_DIRS, load_requirements,
    build_system_prompt, build_user_prompt, parse_response,
)

MODELS = ["gpt-5.4", "claude-sonnet-4-6"]
PASSES = [1, 2]

RECHECK_DIR = os.path.join(REPO_DIR, "results", "restestbench", "ground-truth-recheck")


def original_ground_truth(variant_dir_name):
    path = os.path.join(REPO_DIR, "results", "restestbench", variant_dir_name,
                        "per-req", "gpt-5.4", "summary.json")
    with open(path) as f:
        s = json.load(f)
    gt = {}
    for n in s["removed_not_implemented"]:
        gt[n] = "NOT_IMPLEMENTED"
    for n in s["removed_implemented"]:
        gt[n] = "IMPLEMENTED"
    return gt


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--resume", action="store_true",
                        help="skip calls whose result file already exists")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    import detect_spec_gaps

    all_records = []
    total_tokens = 0

    for (service, round_num), variant_dir_name in VARIANT_DIRS.items():
        cfg = SERVICE_CONFIGS[service]
        removals = sorted(cfg["rounds"][round_num])
        variant_dir = os.path.join(REPO_DIR, "results", "restestbench", variant_dir_name)
        code_path = os.path.join(variant_dir, "generated_code.py")
        with open(code_path) as f:
            generated_code = f.read()
        reqs = load_requirements(service)
        system_prompt = build_system_prompt()
        out_dir = os.path.join(RECHECK_DIR, variant_dir_name)
        os.makedirs(out_dir, exist_ok=True)

        print(f"\n=== {variant_dir_name}  ({len(removals)} removed reqs) ===")

        for req_id in removals:
            req = reqs[req_id]
            for model in MODELS:
                for pass_num in PASSES:
                    fname = f"R{req_id}_{model}_pass{pass_num}.json"
                    result_path = os.path.join(out_dir, fname)

                    if args.resume and os.path.exists(result_path):
                        rec = json.load(open(result_path))
                        all_records.append(rec)
                        print(f"  R{req_id:>3} {model:<20} pass{pass_num} "
                              f"[{rec['verdict']:<15}] (cached)")
                        continue
                    if args.dry_run:
                        print(f"  R{req_id:>3} {model:<20} pass{pass_num} [DRY RUN]")
                        continue

                    detect_spec_gaps.configure_model(model)
                    user_prompt = build_user_prompt(req, generated_code)
                    raw_text, usage = detect_spec_gaps.call_llm(
                        system_prompt, user_prompt, temperature=0)
                    total_tokens += usage.get("total_tokens", 0)

                    parsed = parse_response(raw_text)
                    if parsed is None:
                        verdict = "PARSE_ERROR"
                        omissions = None
                    else:
                        omissions = parsed.get("omissions", [])
                        verdict = "NOT_IMPLEMENTED" if omissions else "IMPLEMENTED"

                    rec = {
                        "variant": variant_dir_name,
                        "req_id": req_id,
                        "model": model,
                        "pass": pass_num,
                        "verdict": verdict,
                        "requirement_vague": req["requirement_vague"],
                        "omissions": omissions,
                        "implementation": (parsed or {}).get("implementation"),
                        "usage": usage,
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    }
                    if parsed is None:
                        rec["raw_response"] = raw_text
                    with open(result_path, "w") as f:
                        json.dump(rec, f, indent=2)
                    all_records.append(rec)
                    print(f"  R{req_id:>3} {model:<20} pass{pass_num} [{verdict:<15}]")

    if args.dry_run:
        print("\n[DRY RUN complete — no LLM calls made]")
        return

    # ---------------- agreement analysis ----------------
    print(f"\n{'=' * 96}")
    print("COMPARISON vs ORIGINAL GROUND TRUTH (single gpt-5.4 pass)")
    print(f"{'=' * 96}")
    header = (f"{'variant':<34} {'req':>4} {'orig':<8} "
              f"{'gpt54_p1':<9} {'gpt54_p2':<9} {'sonnet_p1':<10} {'sonnet_p2':<10} {'agree':<6}")
    print(header)
    print("-" * len(header))

    by_req = {}
    for rec in all_records:
        by_req.setdefault((rec["variant"], rec["req_id"]), {})[
            (rec["model"], rec["pass"])] = rec["verdict"]

    def short(v):
        return {"NOT_IMPLEMENTED": "NOT_IMPL", "IMPLEMENTED": "IMPL",
                "PARSE_ERROR": "ERR"}.get(v, "?")

    summary = {"records": [], "disagreements": []}
    n_unanimous = n_match_orig = 0
    for (variant, req_id), verdicts in sorted(by_req.items()):
        orig = original_ground_truth(variant).get(req_id, "?")
        v = [verdicts.get(("gpt-5.4", 1)), verdicts.get(("gpt-5.4", 2)),
             verdicts.get(("claude-sonnet-4-6", 1)), verdicts.get(("claude-sonnet-4-6", 2))]
        unanimous = len(set(v)) == 1
        agrees_orig = unanimous and v[0] == orig
        if unanimous:
            n_unanimous += 1
        if agrees_orig:
            n_match_orig += 1
        row = {"variant": variant, "req_id": req_id, "original": orig,
               "gpt-5.4_pass1": v[0], "gpt-5.4_pass2": v[1],
               "sonnet_pass1": v[2], "sonnet_pass2": v[3],
               "unanimous": unanimous, "matches_original": agrees_orig}
        summary["records"].append(row)
        if not agrees_orig:
            summary["disagreements"].append(row)
        flag = "OK" if agrees_orig else ("SPLIT" if not unanimous else "FLIP")
        print(f"{variant:<34} R{req_id:>3} {short(orig):<8} "
              f"{short(v[0]):<9} {short(v[1]):<9} {short(v[2]):<10} {short(v[3]):<10} {flag:<6}")

    n = len(by_req)
    print(f"\nRequirements checked: {n}")
    print(f"Unanimous across all 4 verdicts:        {n_unanimous}/{n}")
    print(f"Unanimous AND matching original truth:  {n_match_orig}/{n}")
    print(f"Total tokens this run: {total_tokens}")

    summary["stats"] = {"n_requirements": n, "n_unanimous": n_unanimous,
                        "n_match_original": n_match_orig,
                        "total_tokens": total_tokens,
                        "models": MODELS, "passes": PASSES}
    out = os.path.join(RECHECK_DIR, "recheck_summary.json")
    with open(out, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\nSummary written to {out}")


if __name__ == "__main__":
    main()
