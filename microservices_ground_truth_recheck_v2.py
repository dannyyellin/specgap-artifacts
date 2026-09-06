"""
Microservices ground-truth recheck, VERSION 2 — positively-phrased
requirements (eliminates the polarity-inversion artifact of v1).

Differences from microservices_ground_truth_recheck.py (v1, 2026-07-13):
  1. INPUT: requirements come from specs/removed-requirements-positive.json —
     author-reviewed positive statements ("User passwords are encrypted with
     bcrypt...") — instead of the removal-note headlines ("Removed password
     encryption (bcrypt)") that v1 fed the checkers. v1's phrasing caused a
     confirmed polarity-inversion artifact (checkers verifying the removal
     instead of the requirement; see results-analysis.txt, "GROUND-TRUTH
     RECHECK: MICROSERVICES", 2026-07-13).
  2. PROMPT: prompts/microservice_ground_truth_check_v2.txt — identical
     INFERRED/GAP/PARTIAL definitions and decision guide, but describes the
     input as a positive requirement statement and adds an explicit
     anti-inversion instruction ("classify the requirement AS STATED ...
     never whether the requirement is absent").
  3. OUTPUT DIR: results/microservices-ground-truth-recheck-v2/ (v1's raw
     records are left untouched for comparison).

Everything else matches v1 exactly: same 36 requirements, same generated
code files (generated/{app}/{variant}/gpt-5.4/{service}.py), same 2 models
(gpt-5.4, claude-sonnet-4-6) x 2 passes = 144 calls, temperature=0, same
classification comparison against the original 3-pass consensus
(results/inferability-consistency.txt).

The numbers this produces are pure LLM verdicts — no manual corrections or
post-hoc reinterpretation are applied by this script.

Safety checks before any LLM call:
  - The JSON must cover exactly the same (variant, req_id) pairs as the
    consensus table (36 requirements) — aborts otherwise.
  - --dry-run prints every requirement statement that would be sent,
    without calling any LLM.

Usage:
  python3 microservices_ground_truth_recheck_v2.py --dry-run   # review first
  python3 microservices_ground_truth_recheck_v2.py [--resume]

Output:
  results/microservices-ground-truth-recheck-v2/{variant}/R{id}_{model}_pass{k}.json
  results/microservices-ground-truth-recheck-v2/recheck_summary.json
"""

import argparse
import json
import os
import sys
from datetime import datetime

REPO_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, REPO_DIR)

from compute_precision_tracked import load_microservices_ground_truth
from microservices_ground_truth_recheck import ALL_VARIANTS, parse_verdict

MODELS = ["gpt-5.4", "claude-sonnet-4-6"]
PASSES = [1, 2]

RECHECK_DIR = os.path.join(REPO_DIR, "results", "microservices-ground-truth-recheck-v2")
POSITIVE_REQS_FILE = os.path.join(REPO_DIR, "specs", "removed-requirements-positive.json")
PROMPT_FILE = os.path.join(REPO_DIR, "prompts", "microservice_ground_truth_check_v2.txt")


def load_positive_requirements():
    with open(POSITIVE_REQS_FILE) as f:
        data = json.load(f)
    data.pop("_comment", None)
    return data


def validate_coverage(positive, consensus):
    """Abort (before any LLM call) unless the positive-statements file is
    consistent with the AUTHORITATIVE removal source and with the scoring
    key-space.

    PRIMARY check — against specs/{app}/{variant}-removals.txt (the source
    of record for what was removed), via the same headline parser v1 used:
      (a) exact (variant, req_id) set match, and
      (b) each entry's source_headline matches the removals-file headline
          VERBATIM — so every positive statement is mechanically tied to
          the exact removal text it was derived from. (Whether the positive
          REWRITE faithfully restates that headline is the author-review
          step; a mechanical check cannot judge that.)

    SECONDARY check — the (variant, req_id) keys also exist in the
    consensus table (inferability-consistency.txt). Only the KEYS are read;
    the 3-pass verdicts/consensus labels are never read here and are never
    sent to the LLM — they are used only after the run, to print the
    agreement comparison. This check just guarantees that post-run
    comparison will find every requirement."""
    from microservices_ground_truth_recheck import load_removal_headlines

    errors = []

    # --- primary: specs/*-removals.txt ---
    spec_pairs = {}
    for app, variant, service in ALL_VARIANTS:
        for rid, headline in load_removal_headlines(app, variant).items():
            spec_pairs[(variant, rid)] = headline
    positive_pairs = {(variant, rid): entry
                      for variant, reqs in positive.items()
                      for rid, entry in reqs.items()}

    for pair in sorted(set(spec_pairs) - set(positive_pairs)):
        errors.append(f"missing from positive file (per removals.txt): {pair}")
    for pair in sorted(set(positive_pairs) - set(spec_pairs)):
        errors.append(f"not in any removals.txt: {pair}")
    for pair in sorted(set(spec_pairs) & set(positive_pairs)):
        if positive_pairs[pair]["source_headline"] != spec_pairs[pair]:
            errors.append(
                f"source_headline mismatch for {pair}:\n"
                f"    removals.txt: {spec_pairs[pair]}\n"
                f"    positive file: {positive_pairs[pair]['source_headline']}")

    # --- secondary: consensus key-space (keys only; verdicts unread) ---
    consensus_pairs = set()
    for app, variant, service in ALL_VARIANTS:
        short = variant.split("-", 1)[0]
        for (sn, rid) in consensus:
            if sn == short:
                consensus_pairs.add((variant, rid))
    for pair in sorted(set(positive_pairs) - consensus_pairs):
        errors.append(f"key absent from consensus table (post-run "
                      f"comparison would fail): {pair}")

    if errors:
        for e in errors:
            print(f"COVERAGE ERROR: {e}")
        sys.exit(1)
    print(f"Coverage check PASSED: {len(positive_pairs)} requirements; "
          f"exact match with specs/*-removals.txt (IDs and verbatim "
          f"headlines) and with the scoring key-space.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    import detect_spec_gaps

    system_prompt = open(PROMPT_FILE).read()
    consensus = load_microservices_ground_truth()
    positive = load_positive_requirements()
    validate_coverage(positive, consensus)

    all_records = []
    total_tokens = 0

    for app, variant, service in ALL_VARIANTS:
        reqs = positive[variant]
        code_path = os.path.join(REPO_DIR, "generated", app, variant, "gpt-5.4",
                                 f"{service}.py")
        with open(code_path) as f:
            code = f.read()
        out_dir = os.path.join(RECHECK_DIR, variant)
        os.makedirs(out_dir, exist_ok=True)

        print(f"\n=== {app}/{variant} ({service}.py, {len(reqs)} removed reqs) ===")

        for req_id, entry in reqs.items():
            statement = entry["requirement"]
            user_prompt = (f"## Requirement (removed from the specification "
                           f"before code generation)\n\n{req_id}: {statement}\n\n"
                           f"## Service code ({service}.py)\n\n{code}")
            if args.dry_run:
                print(f"  {req_id:>4}: {statement}")
                continue

            for model in MODELS:
                for pass_num in PASSES:
                    fname = f"{req_id}_{model}_pass{pass_num}.json"
                    result_path = os.path.join(out_dir, fname)
                    if args.resume and os.path.exists(result_path):
                        rec = json.load(open(result_path))
                        all_records.append(rec)
                        print(f"  {req_id:>4} {model:<20} pass{pass_num} "
                              f"[{rec['label']:<8}] (cached)")
                        continue

                    detect_spec_gaps.configure_model(model)
                    raw_text, usage = detect_spec_gaps.call_llm(
                        system_prompt, user_prompt, temperature=0)
                    total_tokens += usage.get("total_tokens", 0)

                    parsed = parse_verdict(raw_text)
                    rec = {
                        "app": app, "variant": variant, "service": service,
                        "req_id": req_id, "requirement": statement,
                        "source_headline": entry["source_headline"],
                        "model": model, "pass": pass_num,
                        "label": parsed["label"] if parsed else "PARSE_ERROR",
                        "evidence": (parsed or {}).get("evidence"),
                        "reasoning": (parsed or {}).get("reasoning"),
                        "usage": usage,
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    }
                    if parsed is None:
                        rec["raw_response"] = raw_text
                    with open(result_path, "w") as f:
                        json.dump(rec, f, indent=2)
                    all_records.append(rec)
                    print(f"  {req_id:>4} {model:<20} pass{pass_num} [{rec['label']:<8}]")

    if args.dry_run:
        print("\n[DRY RUN complete — no LLM calls made]")
        return

    # ---------------- comparison vs 3-pass consensus ----------------
    print(f"\n{'=' * 100}")
    print("COMPARISON vs ORIGINAL 3-PASS CONSENSUS (inferability-consistency.txt)")
    print(f"{'=' * 100}")
    header = (f"{'variant':<24} {'req':>5} {'consensus':<10} "
              f"{'gpt54_p1':<9} {'gpt54_p2':<9} {'sonnet_p1':<10} {'sonnet_p2':<10} {'agree':<6}")
    print(header)
    print("-" * len(header))

    by_req = {}
    for rec in all_records:
        by_req.setdefault((rec["variant"], rec["req_id"]), {})[
            (rec["model"], rec["pass"])] = rec["label"]

    label_map = {"INFERRED": "INF", "GAP": "GAP", "PARTIAL": "PAR", "PARSE_ERROR": "ERR"}

    summary = {"records": [], "disagreements": []}
    n_unanimous = n_match = 0
    for app, variant, service in ALL_VARIANTS:
        short = variant.split("-", 1)[0]
        for (v, req_id), verdicts in sorted(by_req.items()):
            if v != variant:
                continue
            orig = consensus.get((short, req_id), "?")
            labels = [verdicts.get(("gpt-5.4", 1)), verdicts.get(("gpt-5.4", 2)),
                      verdicts.get(("claude-sonnet-4-6", 1)),
                      verdicts.get(("claude-sonnet-4-6", 2))]
            shorts = [label_map.get(l, "?") for l in labels]
            unanimous = len(set(shorts)) == 1
            matches = unanimous and shorts[0] == orig
            n_unanimous += unanimous
            n_match += matches
            row = {"variant": variant, "req_id": req_id, "consensus": orig,
                   "gpt-5.4_pass1": shorts[0], "gpt-5.4_pass2": shorts[1],
                   "sonnet_pass1": shorts[2], "sonnet_pass2": shorts[3],
                   "unanimous": unanimous, "matches_consensus": matches}
            summary["records"].append(row)
            if not matches:
                summary["disagreements"].append(row)
            flag = "OK" if matches else ("SPLIT" if not unanimous else "FLIP")
            print(f"{variant:<24} {req_id:>5} {orig:<10} "
                  f"{shorts[0]:<9} {shorts[1]:<9} {shorts[2]:<10} {shorts[3]:<10} {flag:<6}")

    n = len(summary["records"])
    print(f"\nRequirements checked: {n}")
    print(f"Unanimous across all 4 verdicts:          {n_unanimous}/{n}")
    print(f"Unanimous AND matching 3-pass consensus:  {n_match}/{n}")
    print(f"Total tokens this run: {total_tokens}")

    summary["stats"] = {"n_requirements": n, "n_unanimous": n_unanimous,
                        "n_match_consensus": n_match, "total_tokens": total_tokens,
                        "models": MODELS, "passes": PASSES,
                        "prompt": "prompts/microservice_ground_truth_check_v2.txt",
                        "requirements_file": "specs/removed-requirements-positive.json"}
    out = os.path.join(RECHECK_DIR, "recheck_summary.json")
    with open(out, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\nSummary written to {out}")


if __name__ == "__main__":
    main()
