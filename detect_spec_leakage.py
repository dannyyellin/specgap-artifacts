"""
detect_spec_leakage.py — Spec-Leakage Detection for RESTestBench Variants

When a requirement is removed from a spec to create a reduced spec, the
removed requirement's underlying constraint may still be present in the
reduced spec through other kept requirements.  We call this "spec-leakage":
the generator implements the requirement not from domain knowledge, but
because the reduced spec still communicates the same constraint.

Example: R47 in fastapi-R4R10R13R30R35R47 ("registration rejects 7-char
password") was removed, but R50, R52, and R56 — all kept — say "reject
7-char passwords" in other contexts, making the 8-char minimum constraint
still explicit in the reduced spec.

This script asks an LLM to judge, for each removed requirement, whether
the reduced spec directly implies that constraint through other requirements
— based solely on spec text, without external domain knowledge.

Verdicts
--------
  SPEC_LEAKED  : The reduced spec, through kept requirements, explicitly
                 states the same underlying constraint.  The removal was
                 not a true information gap.
  NOT_LEAKED   : Implementing the removed requirement requires knowledge
                 beyond what the spec says (conventions, best practices).
  UNCERTAIN    : The judge cannot determine with confidence.

Output (per variant, under results/restestbench/{variant}/spec-leakage/{model}/)
--------
  requirement_{N}_result.json   — per-requirement LLM verdict
  summary.json                  — counts and all verdicts

Usage
-----
  python3 detect_spec_leakage.py --variant fastapi-R4R10R13R30R35R47 --model gpt-5.4
  python3 detect_spec_leakage.py --all --model gpt-5.4
  python3 detect_spec_leakage.py --all --model gpt-5.4 --resume
  python3 detect_spec_leakage.py --all --model gpt-5.4 --dry-run
"""

import argparse
import json
import os
import sys
from datetime import datetime

REPO_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, REPO_DIR)

RESTESTBENCH_DIR = os.path.join(REPO_DIR, "RESTestBench")
RESULTS_DIR      = os.path.join(REPO_DIR, "results", "restestbench")

# ---------------------------------------------------------------------------
# Variant → requirement JSON directory (under RESTestBench/data/requirements/)
# ---------------------------------------------------------------------------
VARIANT_CONFIGS = {
    "todoapp-R1R2R4R5R7R8R10R12":          "todoapp",
    "fastapi-R4R10R13R30R35R47":            "fastapi",
    "fastapi-R14R15R16R17R18R46R56":        "fastapi",
    "realworld-R5R6R9R12R19R23R25R27R29":   "nestjs-realworld",
    "realworld-R2R10R13R15R24R26R28":       "nestjs-realworld",
}

# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are a specification analyst. Your task is to determine whether a
specification document directly implies a specific behavioral requirement.

IMPORTANT RULE: Base your judgment ONLY on what is explicitly stated or
directly entailed by the text of the specification provided. Do NOT apply
external software engineering knowledge, security conventions, REST best
practices, or common coding patterns. If inferring the requirement would
require any knowledge beyond what the spec text says, the verdict is
NOT_LEAKED.

Definition of SPEC_LEAKED: the reduced spec, through requirements that were
kept, explicitly states the same underlying constraint in a different context.
A reader of only the spec text — with no prior knowledge — could deduce the
removed requirement directly from what the spec says elsewhere.

Definition of NOT_LEAKED: implementing the removed requirement requires
applying general knowledge that the spec never states (e.g., "passwords
should have a minimum length", "tokens expire", "IDs should be unique")
rather than something the spec itself communicates.

The concrete test: could a reader who knows nothing about software
engineering, but who can read and reason about text, conclude from the
spec that the removed requirement must be satisfied? If yes: SPEC_LEAKED.
If they would need outside knowledge: NOT_LEAKED.

Respond with a JSON object with exactly these three fields:
{
  "verdict": "SPEC_LEAKED" | "NOT_LEAKED" | "UNCERTAIN",
  "spec_evidence": "The specific sentence(s) from the spec that imply the constraint, or null if none",
  "reasoning": "One or two sentences explaining your verdict"
}

Output ONLY valid JSON, no other text.
"""


def _build_user_prompt(req_precise, req_vague, spec_reduced):
    return (
        f"## Reduced Specification\n\n"
        f"{spec_reduced}\n\n"
        f"---\n\n"
        f"## Removed Requirement\n\n"
        f"Summary: {req_vague}\n\n"
        f"Full scenario:\n{req_precise}\n\n"
        f"---\n\n"
        f"Based solely on the reduced specification above (no external knowledge), "
        f"does the spec directly imply the removed requirement's constraint?"
    )


def _load_vague(req_dir, req_id):
    path = os.path.join(RESTESTBENCH_DIR, "data", "requirements",
                        req_dir, f"requirement_{req_id}.json")
    if not os.path.exists(path):
        return "(vague description unavailable)"
    return json.load(open(path)).get("requirement_vague", "(unavailable)")


# ---------------------------------------------------------------------------
# Per-variant runner
# ---------------------------------------------------------------------------

def run_variant(variant, req_dir, model, dry_run=False, resume=False):
    variant_dir = os.path.join(RESULTS_DIR, variant)

    removals_path    = os.path.join(variant_dir, "removals.json")
    spec_reduced_path = os.path.join(variant_dir, "spec_reduced.txt")

    for p in (removals_path, spec_reduced_path):
        if not os.path.exists(p):
            print(f"  ERROR: not found: {p}")
            return None

    removals     = json.load(open(removals_path))
    spec_reduced = open(spec_reduced_path).read()

    output_dir = os.path.join(variant_dir, "spec-leakage", model)
    os.makedirs(output_dir, exist_ok=True)

    if not dry_run:
        import detect_spec_gaps as dsg
        dsg.configure_model(model)

    results = []

    for rem in removals:
        req_id    = rem["id"]
        req_text  = rem["requirement"]
        vague     = _load_vague(req_dir, req_id)
        result_path = os.path.join(output_dir, f"requirement_{req_id}_result.json")

        # -- Resume: load existing result --
        if resume and os.path.exists(result_path):
            saved = json.load(open(result_path))
            results.append(saved)
            verdict = saved.get("verdict", "?")
            print(f"    R{req_id:>3} [{verdict:<12}] {vague[:70]}  [SKIP]")
            continue

        # -- Dry-run --
        if dry_run:
            print(f"    R{req_id:>3} [DRY RUN     ] {vague[:70]}")
            continue

        # -- Live LLM call --
        user_prompt = _build_user_prompt(req_text, vague, spec_reduced)
        raw_text, usage = dsg.call_llm(SYSTEM_PROMPT, user_prompt, temperature=0)

        try:
            parsed = dsg.extract_result_json(raw_text)
        except Exception:
            parsed = None

        if parsed is None:
            rec = {
                "req_id":              req_id,
                "requirement_vague":   vague,
                "requirement_precise": req_text,
                "verdict":             "PARSE_ERROR",
                "spec_evidence":       None,
                "reasoning":           None,
                "parse_error":         True,
                "raw_response":        raw_text,
                "usage":               usage,
            }
            print(f"    R{req_id:>3} [PARSE_ERROR ] {vague[:70]}")
        else:
            verdict = parsed.get("verdict", "UNCERTAIN")
            rec = {
                "req_id":              req_id,
                "requirement_vague":   vague,
                "requirement_precise": req_text,
                "verdict":             verdict,
                "spec_evidence":       parsed.get("spec_evidence"),
                "reasoning":           parsed.get("reasoning"),
                "parse_error":         False,
                "usage":               usage,
            }
            print(f"    R{req_id:>3} [{verdict:<12}] {vague[:70]}")

        results.append(rec)
        with open(result_path, "w") as f:
            json.dump(rec, f, indent=2)

    if dry_run:
        print(f"    → Dry run: would check {len(removals)} requirements")
        return None

    # -- Summary --
    leaked  = [r for r in results if r["verdict"] == "SPEC_LEAKED"]
    not_lk  = [r for r in results if r["verdict"] == "NOT_LEAKED"]
    uncert  = [r for r in results if r["verdict"] == "UNCERTAIN"]
    errors  = [r for r in results if r.get("parse_error")]

    summary = {
        "variant":          variant,
        "model":            model,
        "timestamp":        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "n_removed":        len(removals),
        "n_spec_leaked":    len(leaked),
        "n_not_leaked":     len(not_lk),
        "n_uncertain":      len(uncert),
        "n_parse_errors":   len(errors),
        "spec_leaked_ids":  [r["req_id"] for r in leaked],
        "not_leaked_ids":   [r["req_id"] for r in not_lk],
        "uncertain_ids":    [r["req_id"] for r in uncert],
        "per_requirement":  results,
    }
    with open(os.path.join(output_dir, "summary.json"), "w") as f:
        json.dump(summary, f, indent=2)

    print(f"    → SPEC_LEAKED={len(leaked)}, NOT_LEAKED={len(not_lk)}, "
          f"UNCERTAIN={len(uncert)}, ERRORS={len(errors)}")
    return summary


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Detect spec-leakage in RESTestBench removed requirements"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--variant", choices=list(VARIANT_CONFIGS.keys()),
        help="Run on a single named variant"
    )
    group.add_argument(
        "--all", action="store_true",
        help="Run on all 5 RESTestBench variants"
    )
    parser.add_argument(
        "--model", required=True,
        help="LLM model to use as judge (e.g. gpt-5.4, claude-sonnet-4-6)"
    )
    parser.add_argument(
        "--resume", action="store_true",
        help="Skip requirements whose result file already exists"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print what would run without calling the LLM"
    )
    args = parser.parse_args()

    variants_to_run = (
        list(VARIANT_CONFIGS.items()) if args.all
        else [(args.variant, VARIANT_CONFIGS[args.variant])]
    )

    all_summaries = []
    for variant, req_dir in variants_to_run:
        print(f"\n{'='*60}")
        print(f"Variant:  {variant}")
        print(f"Req dir:  {req_dir}")
        print(f"Model:    {args.model}")
        if args.dry_run:
            print("[DRY RUN]")
        print(f"{'='*60}")
        summary = run_variant(
            variant, req_dir, args.model,
            dry_run=args.dry_run, resume=args.resume,
        )
        if summary:
            all_summaries.append(summary)

    if args.all and all_summaries:
        total_removed = sum(s["n_removed"]     for s in all_summaries)
        total_leaked  = sum(s["n_spec_leaked"] for s in all_summaries)
        total_not     = sum(s["n_not_leaked"]  for s in all_summaries)
        total_unc     = sum(s["n_uncertain"]   for s in all_summaries)
        print(f"\n{'='*60}")
        print("OVERALL SUMMARY")
        print(f"{'='*60}")
        print(f"  Total removed requirements : {total_removed}")
        print(f"  SPEC_LEAKED  : {total_leaked:>3}  "
              f"({100*total_leaked/total_removed:.1f}%)")
        print(f"  NOT_LEAKED   : {total_not:>3}  "
              f"({100*total_not/total_removed:.1f}%)")
        print(f"  UNCERTAIN    : {total_unc:>3}  "
              f"({100*total_unc/total_removed:.1f}%)")
        print()
        for s in all_summaries:
            ids = s["spec_leaked_ids"]
            tag = f"  R{ids}" if ids else "  (none)"
            print(f"  {s['variant']}")
            print(f"    SPEC_LEAKED: {tag}")


if __name__ == "__main__":
    main()
