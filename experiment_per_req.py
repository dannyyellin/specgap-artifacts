"""
Experiment 2A: Per-Requirement Gap Detection on RESTestBench.

For each requirement in the full spec (kept and removed alike), asks the
detector: "is this requirement implemented in the code?"  Requirements
flagged as not implemented become omissions.

Comparing kept vs. removed requirements in the output gives us:
  - om_recall:  removed requirements flagged as not implemented
  - ad_recall:  removed requirements flagged as implemented
                (generator inferred the requirement despite it being absent
                from the reduced spec used for code generation)
  - FP rate:    kept requirements flagged as not implemented
                (generator errors, same as Experiment 4)

Output is written to:
  results/restestbench/{variant}/per-req/{model}/
    requirement_{N}_result.json   — per-requirement LLM response
    detection_result.json         — omissions aggregated in the same format
                                    as the original experiments, so that
                                    match_detections.py and analyze_results.py
                                    work unchanged (method label: "per-req")
    summary.json                  — counts and per-requirement verdicts
    run.log                       — human-readable run record

Usage:
  python3 experiment_per_req.py --service todoapp --model gpt-5.4
  python3 experiment_per_req.py --service fastapi  --round 1 --model gpt-5.4
  python3 experiment_per_req.py --service fastapi  --round 2 --model claude-sonnet-4-6
  python3 experiment_per_req.py --service realworld --round 1 --model gpt-5.4
  python3 experiment_per_req.py --service realworld --round 2 --model gpt-5.4

  # dry-run: print what would be run without calling the LLM
  python3 experiment_per_req.py --service todoapp --model gpt-5.4 --dry-run

  # skip requirements whose result file already exists (resume after interruption)
  python3 experiment_per_req.py --service fastapi --round 1 --model gpt-5.4 --resume
"""

import argparse
import json
import os
import sys
from datetime import datetime

REPO_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, REPO_DIR)

RESTESTBENCH_DIR = os.path.join(REPO_DIR, "RESTestBench")

# ---------------------------------------------------------------------------
# Service configuration
# ---------------------------------------------------------------------------

SERVICE_CONFIGS = {
    'todoapp': {
        'req_dir': 'todoapp',
        'rounds': {
            1: [1, 2, 4, 5, 7, 8, 10, 12],
        },
    },
    'fastapi': {
        'req_dir': 'fastapi',
        'rounds': {
            1: [4, 10, 13, 30, 35, 47],
            2: [14, 15, 16, 17, 18, 46, 56],
        },
    },
    'realworld': {
        'req_dir': 'nestjs-realworld',
        'rounds': {
            1: [5, 6, 9, 12, 19, 23, 25, 27, 29],
            2: [2, 10, 13, 15, 24, 26, 28],
        },
    },
}

# Map service+round to the variant directory name used by other experiments
VARIANT_DIRS = {
    ('todoapp', 1): 'todoapp-R1R2R4R5R7R8R10R12',
    ('fastapi',  1): 'fastapi-R4R10R13R30R35R47',
    ('fastapi',  2): 'fastapi-R14R15R16R17R18R46R56',
    ('realworld', 1): 'realworld-R5R6R9R12R19R23R25R27R29',
    ('realworld', 2): 'realworld-R2R10R13R15R24R26R28',
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_requirements(service):
    req_dir = os.path.join(RESTESTBENCH_DIR, "data", "requirements",
                           SERVICE_CONFIGS[service]['req_dir'])
    reqs = {}
    for fname in sorted(os.listdir(req_dir), key=lambda x: int(x.split('_')[1].split('.')[0])):
        if not fname.endswith('.json'):
            continue
        d = json.load(open(os.path.join(req_dir, fname)))
        reqs[d['id']] = d
    return reqs


def build_system_prompt():
    categories = open(os.path.join(REPO_DIR, "prompts", "categories.txt")).read()
    template = open(os.path.join(REPO_DIR, "prompts", "per_req_check.txt")).read()
    return template.replace("{{CATEGORIES}}", categories)


def build_user_prompt(req, code):
    return (
        f"## Requirement\n\n"
        f"{req['requirement_vague']}\n\n"
        f"Scenario:\n{req['requirement_precise']}\n\n"
        f"## Code\n\n{code}"
    )


def parse_response(text):
    """Parse the LLM JSON response. Returns the parsed dict or None on failure."""
    from detect_spec_gaps import extract_result_json
    try:
        return extract_result_json(text)
    except (json.JSONDecodeError, Exception):
        return None


# ---------------------------------------------------------------------------
# Main experiment
# ---------------------------------------------------------------------------

def run(service, round_num, model, dry_run=False, resume=False):
    cfg = SERVICE_CONFIGS[service]
    removals = set(cfg['rounds'][round_num])
    variant_dir_name = VARIANT_DIRS[(service, round_num)]

    # Locate generated code (produced by the original experiment)
    variant_dir = os.path.join(REPO_DIR, "results", "restestbench", variant_dir_name)
    code_path = os.path.join(variant_dir, "generated_code.py")
    if not os.path.exists(code_path):
        print(f"ERROR: generated code not found: {code_path}")
        sys.exit(1)
    with open(code_path) as f:
        generated_code = f.read()

    reqs = load_requirements(service)
    system_prompt = build_system_prompt()

    output_dir = os.path.join(variant_dir, "per-req", model)
    os.makedirs(output_dir, exist_ok=True)

    print(f"Service:   {service} (round {round_num})")
    print(f"Variant:   {variant_dir_name}")
    print(f"Model:     {model}")
    print(f"Removals:  {sorted(removals)}")
    print(f"Total requirements: {len(reqs)}")
    print(f"Output:    {output_dir}")
    if dry_run:
        print("\n[DRY RUN — no LLM calls will be made]")
    print()

    if not dry_run:
        import detect_spec_gaps
        detect_spec_gaps.configure_model(model)

    total_tokens = 0
    per_req_results = []   # list of dicts, one per requirement

    for req_id in sorted(reqs.keys()):
        req = reqs[req_id]
        result_path = os.path.join(output_dir, f"requirement_{req_id}_result.json")

        if resume and os.path.exists(result_path):
            saved = json.load(open(result_path))
            per_req_results.append(saved)
            omissions = saved.get('omissions', [])
            status = "SKIP (already done)"
            verdict = "NOT_IMPLEMENTED" if omissions else "IMPLEMENTED"
            location = saved.get('implementation', {}) or {}
            loc_str = f"  @ {location.get('location', '')}" if verdict == "IMPLEMENTED" else ""
            print(f"  R{req_id:>3} [{verdict:<15}] {req['requirement_vague'][:70]}{loc_str}  [{status}]")
            continue

        user_prompt = build_user_prompt(req, generated_code)

        if dry_run:
            print(f"  R{req_id:>3} [DRY RUN        ] {req['requirement_vague'][:70]}")
            continue

        raw_text, usage = detect_spec_gaps.call_llm(system_prompt, user_prompt, temperature=0)
        total_tokens += usage.get('total_tokens', 0)

        parsed = parse_response(raw_text)

        if parsed is None:
            rec = {
                'req_id': req_id,
                'requirement_vague': req['requirement_vague'],
                'requirement_precise': req['requirement_precise'],
                'removed': req_id in removals,
                'omissions': None,   # parse error
                'implementation': None,
                'usage': usage,
                'raw_response': raw_text,
                'parse_error': True,
            }
            print(f"  R{req_id:>3} [PARSE ERROR    ] {req['requirement_vague'][:70]}")
        else:
            omissions = parsed.get('omissions', [])
            implementation = parsed.get('implementation', None)
            # Renumber omission IDs to include the requirement number for clarity
            for i, om in enumerate(omissions, 1):
                om['id'] = f"R{req_id}-O{i}"
            verdict = "NOT_IMPLEMENTED" if omissions else "IMPLEMENTED"
            rec = {
                'req_id': req_id,
                'requirement_vague': req['requirement_vague'],
                'requirement_precise': req['requirement_precise'],
                'removed': req_id in removals,
                'omissions': omissions,
                'implementation': implementation,
                'usage': usage,
                'parse_error': False,
            }
            loc_str = f"  @ {implementation.get('location', '')}" if implementation else ""
            print(f"  R{req_id:>3} [{verdict:<15}] {req['requirement_vague'][:70]}"
                  f"{loc_str}{'  [REMOVED]' if req_id in removals else ''}")

        per_req_results.append(rec)
        with open(result_path, 'w') as f:
            json.dump(rec, f, indent=2)

    if dry_run:
        print(f"\nDry run complete. Would have made {len(reqs)} LLM calls.")
        return

    # -----------------------------------------------------------------------
    # Aggregate into detection_result.json (same format as original experiments)
    # -----------------------------------------------------------------------
    all_omissions = []
    for rec in per_req_results:
        if rec.get('parse_error') or rec['omissions'] is None:
            continue
        all_omissions.extend(rec['omissions'])

    detection_result = {
        'result': {
            'omissions': all_omissions,
            'additions': [],   # Phase 1 does not detect additions
        },
        'usage': {'total_tokens': total_tokens},
    }
    with open(os.path.join(output_dir, "detection_result.json"), 'w') as f:
        json.dump(detection_result, f, indent=2)

    # -----------------------------------------------------------------------
    # Summary
    # -----------------------------------------------------------------------
    implemented   = [r for r in per_req_results if not r.get('parse_error') and not r['omissions']]
    not_impl      = [r for r in per_req_results if not r.get('parse_error') and r['omissions']]
    parse_errors  = [r for r in per_req_results if r.get('parse_error')]

    removed_not_impl = [r for r in not_impl if r['removed']]
    removed_impl     = [r for r in implemented if r['removed']]
    kept_not_impl    = [r for r in not_impl if not r['removed']]

    om_recall = len(removed_not_impl) / len(removals) if removals else 0
    ad_recall = len(removed_impl)     / len(removals) if removals else 0
    fp_rate   = len(kept_not_impl)    / (len(reqs) - len(removals)) if (len(reqs) - len(removals)) else 0

    summary = {
        'service': service,
        'round': round_num,
        'variant': variant_dir_name,
        'model': model,
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'total_requirements': len(reqs),
        'removed_requirements': sorted(removals),
        'n_removed': len(removals),
        'n_implemented': len(implemented),
        'n_not_implemented': len(not_impl),
        'n_parse_errors': len(parse_errors),
        'total_omissions_reported': len(all_omissions),
        'total_tokens': total_tokens,
        'removed_not_implemented': [r['req_id'] for r in removed_not_impl],
        'removed_implemented': [r['req_id'] for r in removed_impl],
        'kept_not_implemented': [r['req_id'] for r in kept_not_impl],
        'om_recall': round(om_recall, 4),
        'ad_recall': round(ad_recall, 4),
        'fp_rate_on_kept': round(fp_rate, 4),
    }
    with open(os.path.join(output_dir, "summary.json"), 'w') as f:
        json.dump(summary, f, indent=2)

    # -----------------------------------------------------------------------
    # run.log
    # -----------------------------------------------------------------------
    log_lines = [
        f"Timestamp:  {summary['timestamp']}",
        f"Service:    {service} (round {round_num})",
        f"Variant:    {variant_dir_name}",
        f"Model:      {model}",
        f"Removals:   {sorted(removals)}",
        f"",
        f"Total requirements:      {len(reqs)}",
        f"  Implemented:           {len(implemented)}",
        f"  Not implemented:       {len(not_impl)}",
        f"  Parse errors:          {len(parse_errors)}",
        f"",
        f"Removed requirements ({len(removals)}):  {sorted(removals)}",
        f"  Detected (NOT_IMPLEMENTED):  {[r['req_id'] for r in removed_not_impl]}",
        f"  Missed  (IMPLEMENTED):       {[r['req_id'] for r in removed_impl]}",
        f"",
        f"Kept requirements flagged as NOT_IMPLEMENTED (generator errors):",
        f"  {[r['req_id'] for r in kept_not_impl]}",
        f"",
        f"om_recall        (removed & not implemented / n_removed):  {om_recall:.3f}",
        f"ad_recall        (removed & implemented     / n_removed):  {ad_recall:.3f}",
        f"fp_rate_on_kept  (kept    & not implemented / n_kept   ):  {fp_rate:.3f}",
        f"",
        f"Total omissions reported: {len(all_omissions)}",
        f"Total tokens:             {total_tokens}",
        f"",
        f"--- Per-requirement verdicts ---",
        f"",
    ]
    for rec in per_req_results:
        if rec.get('parse_error'):
            verdict = "PARSE_ERROR"
        elif rec['omissions']:
            verdict = "NOT_IMPLEMENTED"
        else:
            verdict = "IMPLEMENTED"
        tag = " [REMOVED]" if rec['removed'] else ""
        impl = rec.get('implementation') or {}
        loc = f"  @ {impl['location']}" if impl.get('location') and verdict == "IMPLEMENTED" else ""
        log_lines.append(f"  R{rec['req_id']:>3}  {verdict:<15}  {rec['requirement_vague'][:70]}{loc}{tag}")

    with open(os.path.join(output_dir, "run.log"), 'w') as f:
        f.write("\n".join(log_lines) + "\n")

    # -----------------------------------------------------------------------
    # Console summary
    # -----------------------------------------------------------------------
    print()
    print("=" * 60)
    print(f"RESULTS — {service} round {round_num} — {model}")
    print("=" * 60)
    print(f"  om_recall       : {om_recall:.3f}  "
          f"({len(removed_not_impl)}/{len(removals)} removed reqs detected)")
    print(f"  ad_recall       : {ad_recall:.3f}  "
          f"({len(removed_impl)}/{len(removals)} removed reqs inferred by generator)")
    print(f"  fp_rate_on_kept : {fp_rate:.3f}  "
          f"({len(kept_not_impl)}/{len(reqs)-len(removals)} kept reqs flagged)")
    print(f"  total tokens    : {total_tokens}")
    print(f"  output          : {output_dir}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Experiment 2A: per-requirement detection")
    parser.add_argument('--service', required=True,
                        choices=['todoapp', 'fastapi', 'realworld'])
    parser.add_argument('--round', type=int, default=1,
                        help='Removal round (1 or 2; todoapp only has round 1)')
    parser.add_argument('--model', required=True,
                        help='Detector model name (e.g. gpt-5.4, claude-sonnet-4-6)')
    parser.add_argument('--dry-run', action='store_true',
                        help='Print what would run without calling the LLM')
    parser.add_argument('--resume', action='store_true',
                        help='Skip requirements whose result file already exists')
    args = parser.parse_args()

    cfg = SERVICE_CONFIGS.get(args.service)
    if not cfg:
        print(f"Unknown service: {args.service}")
        sys.exit(1)
    if args.round not in cfg['rounds']:
        print(f"Round {args.round} not configured for service '{args.service}'. "
              f"Available: {list(cfg['rounds'].keys())}")
        sys.exit(1)

    run(args.service, args.round, args.model,
        dry_run=args.dry_run, resume=args.resume)


if __name__ == '__main__':
    main()
