"""
Match detected omissions and additions to removed requirements using an LLM judge.

For each detection_result.json, calls the LLM matcher to determine which detected
omissions and additions correspond to removed requirements. Results are saved as
omissions_match_{model}.json and additions_match_{model}.json alongside the detection result.

Usage:
  python match_detections.py [--model MODEL] [--force] [--app APP] [--variant VARIANT]
  python match_detections.py --summary-only

Recommended judge models: gpt-5.4, claude-sonnet-4-6

Output:
  - {result_dir}/omissions_match_{model}.json  (per detection result, per judge model)
  - {result_dir}/additions_match_{model}.json
  - results/match_summary.csv
"""

import os
import sys
import json
import re
import csv
import argparse

REPO_DIR = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIR = os.path.join(REPO_DIR, "results")
SPECS_DIR = os.path.join(REPO_DIR, "specs")
PROMPTS_DIR = os.path.join(REPO_DIR, "prompts")

sys.path.insert(0, REPO_DIR)
from detect_spec_gaps import configure_model, call_llm, extract_result_json

MICROSERVICES_APPS = {"nutrition", "public-library", "pet-store"}
JUDGE_MODELS = ["gpt-5.4", "claude-sonnet-4-6"]
MATCHER_MODEL = JUDGE_MODELS[0]


# ---------------------------------------------------------------------------
# Filename helpers
# ---------------------------------------------------------------------------

def model_to_slug(model):
    return model.replace("/", "-")


def match_filepath(result_dir, base, model):
    return os.path.join(result_dir, f"{base}_{model_to_slug(model)}.json")


# ---------------------------------------------------------------------------
# Prompt loading
# ---------------------------------------------------------------------------

def load_prompt(filename):
    with open(os.path.join(PROMPTS_DIR, filename)) as f:
        content = f.read()
    parts = re.split(r'##\s*USER PROMPT', content, maxsplit=1)
    system = re.sub(r'##\s*SYSTEM PROMPT\s*', '', parts[0]).strip()
    user = parts[1].strip() if len(parts) > 1 else ''
    return system, user


# ---------------------------------------------------------------------------
# Ground truth formatting
# ---------------------------------------------------------------------------

def format_requirements_restestbench(variant_dir):
    path = os.path.join(variant_dir, "removals.json")
    if not os.path.exists(path):
        return None
    with open(path) as f:
        removals = json.load(f)
    return "\n\n".join(f"R{r['id']}: {r['requirement']}" for r in removals)


def format_requirements_microservices(app, variant):
    path = os.path.join(SPECS_DIR, app, f"{variant}-removals.txt")
    if not os.path.exists(path):
        return None
    lines = []
    with open(path) as f:
        for line in f:
            m = re.match(r'^#\s+(R\d+):\s+(.+)', line)
            if m:
                lines.append(f"{m.group(1)}: {m.group(2)}")
    return "\n".join(lines) if lines else None


def n_removed_restestbench(variant_dir):
    path = os.path.join(variant_dir, "removals.json")
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return len(json.load(f))


def n_removed_microservices(app, variant):
    path = os.path.join(SPECS_DIR, app, f"{variant}-removals.txt")
    if not os.path.exists(path):
        return None
    with open(path) as f:
        for line in f:
            m = re.search(r'# MODIFIED SPEC: (\d+) elements removed', line)
            if m:
                return int(m.group(1))
    return None


# ---------------------------------------------------------------------------
# Detection formatting
# ---------------------------------------------------------------------------

def format_detections(items):
    parts = []
    for item in items:
        text = f"{item['id']}: {item.get('description', '')}"
        if item.get('reasoning'):
            text += f"\n  Reasoning: {item['reasoning']}"
        parts.append(text)
    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# LLM matching
# ---------------------------------------------------------------------------

def run_match(system_prompt, user_template, requirements_text, detections_text, detections_key):
    user_prompt = (user_template
                   .replace("{removed_requirements}", requirements_text)
                   .replace(f"{{{detections_key}}}", detections_text))
    response_text, usage = call_llm(system_prompt, user_prompt)
    try:
        result = extract_result_json(response_text)
    except json.JSONDecodeError:
        preview = response_text[:200].replace("\n", " ") if response_text else "<empty>"
        raise ValueError(f"LLM returned non-JSON response: {preview}")
    return result, usage


# ---------------------------------------------------------------------------
# Entry collection
# ---------------------------------------------------------------------------

def collect_entries():
    entries = []

    rb_dir = os.path.join(RESULTS_DIR, "restestbench")
    if os.path.isdir(rb_dir):
        for variant in sorted(os.listdir(rb_dir)):
            variant_dir = os.path.join(rb_dir, variant)
            if not os.path.isdir(variant_dir):
                continue
            for model in sorted(os.listdir(variant_dir)):
                model_dir = os.path.join(variant_dir, model)
                if not os.path.isdir(model_dir):
                    continue
                for method in sorted(os.listdir(model_dir)):
                    result_path = os.path.join(model_dir, method, "detection_result.json")
                    if os.path.exists(result_path):
                        entries.append({
                            "type": "restestbench",
                            "app": variant.split("-")[0],
                            "variant": variant,
                            "variant_dir": variant_dir,
                            "model": model,
                            "method": method,
                            "result_path": result_path,
                            "result_dir": os.path.join(model_dir, method),
                        })

    for app in sorted(MICROSERVICES_APPS):
        app_dir = os.path.join(RESULTS_DIR, app)
        if not os.path.isdir(app_dir):
            continue
        for variant in sorted(os.listdir(app_dir)):
            variant_dir = os.path.join(app_dir, variant)
            if not os.path.isdir(variant_dir):
                continue
            for model in sorted(os.listdir(variant_dir)):
                model_dir = os.path.join(variant_dir, model)
                if not os.path.isdir(model_dir):
                    continue
                for method in sorted(os.listdir(model_dir)):
                    result_path = os.path.join(model_dir, method, "detection_result.json")
                    if os.path.exists(result_path):
                        entries.append({
                            "type": "microservices",
                            "app": app,
                            "variant": variant,
                            "variant_dir": variant_dir,
                            "model": model,
                            "method": method,
                            "result_path": result_path,
                            "result_dir": os.path.join(model_dir, method),
                        })

    return entries


# ---------------------------------------------------------------------------
# Matching run
# ---------------------------------------------------------------------------

def run_matching(entries, args, omissions_system, omissions_user, additions_system, additions_user):
    skipped = 0

    for entry in entries:
        omissions_path = match_filepath(entry["result_dir"], "omissions_match", args.model)
        additions_path = match_filepath(entry["result_dir"], "additions_match", args.model)

        both_exist = os.path.exists(omissions_path) and os.path.exists(additions_path)
        if not args.force and both_exist:
            skipped += 1
            continue

        with open(entry["result_path"]) as f:
            data = json.load(f)
        result = data.get("result", {})
        omissions = result.get("omissions", [])
        additions = result.get("additions", [])

        if entry["type"] == "restestbench":
            req_text = format_requirements_restestbench(entry["variant_dir"])
        else:
            req_text = format_requirements_microservices(entry["app"], entry["variant"])

        if req_text is None:
            print(f"  SKIP (no requirements found): {entry['variant']}/{entry['model']}/{entry['method']}")
            continue

        label = f"{entry['variant']}/{entry['model']}/{entry['method']}"

        # Omissions
        if not args.force and os.path.exists(omissions_path):
            pass
        elif omissions:
            print(f"  Matching omissions: {label} ({len(omissions)} omissions)...")
            try:
                match_result, usage = run_match(
                    omissions_system, omissions_user,
                    req_text, format_detections(omissions), "detected_omissions"
                )
                matches = match_result.get("matches", [])
                n_match = sum(1 for m in matches if m["label"] == "MATCH")
                n_partial = sum(1 for m in matches if m["label"] == "PARTIAL")
                n_none = sum(1 for m in matches if m["label"] == "NONE")
                print(f"    -> MATCH={n_match} PARTIAL={n_partial} NONE={n_none}")
                with open(omissions_path, "w") as f:
                    json.dump({"matcher_model": args.model, "result": match_result, "usage": usage}, f, indent=2)
            except (ValueError, Exception) as e:
                print(f"    WARNING: skipping omissions for {label} — {e}")
        else:
            with open(omissions_path, "w") as f:
                json.dump({"matcher_model": args.model, "result": {"matches": []}, "usage": {}}, f, indent=2)

        # Additions
        if not args.force and os.path.exists(additions_path):
            pass
        elif additions:
            print(f"  Matching additions:  {label} ({len(additions)} additions)...")
            try:
                match_result, usage = run_match(
                    additions_system, additions_user,
                    req_text, format_detections(additions), "detected_additions"
                )
                matches = match_result.get("matches", [])
                n_match = sum(1 for m in matches if m["label"] == "MATCH")
                n_partial = sum(1 for m in matches if m["label"] == "PARTIAL")
                n_none = sum(1 for m in matches if m["label"] == "NONE")
                print(f"    -> MATCH={n_match} PARTIAL={n_partial} NONE={n_none}")
                with open(additions_path, "w") as f:
                    json.dump({"matcher_model": args.model, "result": match_result, "usage": usage}, f, indent=2)
            except (ValueError, Exception) as e:
                print(f"    WARNING: skipping additions for {label} — {e}")
        else:
            with open(additions_path, "w") as f:
                json.dump({"matcher_model": args.model, "result": {"matches": []}, "usage": {}}, f, indent=2)

    if skipped:
        print(f"Skipped {skipped} already-matched results (use --force to re-run).")


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

def load_match_counts(match_path):
    if not os.path.exists(match_path):
        return None
    with open(match_path) as f:
        data = json.load(f)
    matches = data.get("result", {}).get("matches", [])
    n_match = sum(1 for m in matches if m["label"] == "MATCH")
    n_partial = sum(1 for m in matches if m["label"] == "PARTIAL")
    n_none = sum(1 for m in matches if m["label"] == "NONE")
    reqs_matched = len({m["requirement_id"] for m in matches
                        if m["label"] in ("MATCH", "PARTIAL") and m.get("requirement_id")})
    return {"match": n_match, "partial": n_partial, "none": n_none, "reqs_matched": reqs_matched}


def find_judge_slugs(result_dir):
    """Return sorted list of judge model slugs with existing match files in result_dir."""
    slugs = set()
    for fname in os.listdir(result_dir):
        if fname.startswith("omissions_match_") and fname.endswith(".json"):
            slugs.add(fname[len("omissions_match_"):-len(".json")])
    return sorted(slugs)


def collect_summary_rows(entries):
    rows = []
    for entry in entries:
        if entry["type"] == "restestbench":
            n_rem = n_removed_restestbench(entry["variant_dir"])
        else:
            n_rem = n_removed_microservices(entry["app"], entry["variant"])

        with open(entry["result_path"]) as f:
            data = json.load(f)
        result = data.get("result", {})
        n_omissions = len(result.get("omissions", []))
        n_additions = len(result.get("additions", []))

        for judge_slug in find_judge_slugs(entry["result_dir"]):
            om = load_match_counts(os.path.join(entry["result_dir"], f"omissions_match_{judge_slug}.json"))
            ad = load_match_counts(os.path.join(entry["result_dir"], f"additions_match_{judge_slug}.json"))

            rows.append({
                "judge_model": judge_slug,
                "experiment_type": entry["type"],
                "app": entry["app"],
                "variant": entry["variant"],
                "detector_model": entry["model"],
                "method": entry["method"],
                "n_removed": n_rem,
                "n_omissions": n_omissions,
                "n_additions": n_additions,
                "omissions_match": om["match"] if om else None,
                "omissions_partial": om["partial"] if om else None,
                "omissions_none": om["none"] if om else None,
                "reqs_found_via_omissions": om["reqs_matched"] if om else None,
                "additions_match": ad["match"] if ad else None,
                "additions_partial": ad["partial"] if ad else None,
                "additions_none": ad["none"] if ad else None,
                "reqs_found_via_additions": ad["reqs_matched"] if ad else None,
            })
    return rows


def safe_mean(values):
    vals = [v for v in values if v is not None]
    return sum(vals) / len(vals) if vals else None


def print_summary(rows):
    W = {"variant": 38, "model": 20, "method": 18}
    header = (f"{'variant':<{W['variant']}} {'detector':<{W['model']}} {'method':<{W['method']}} "
              f"{'n_rem':>6} {'om_M':>5} {'om_P':>5} {'om_N':>5} {'req_om':>6} "
              f"{'ad_M':>5} {'ad_P':>5} {'ad_N':>5} {'req_ad':>6}")
    sep = "-" * len(header)

    def fmt(v): return str(v) if v is not None else "?"
    def fmtf(v): return f"{v:.2f}" if v is not None else "?"

    for judge_slug in sorted(set(r["judge_model"] for r in rows)):
        judge_rows = [r for r in rows if r["judge_model"] == judge_slug]

        print(f"\n{'#' * len(header)}")
        print(f"  JUDGE MODEL: {judge_slug}")
        print(f"{'#' * len(header)}")

        current_exp = None
        for row in judge_rows:
            if row["experiment_type"] != current_exp:
                current_exp = row["experiment_type"]
                print(f"\n{'=' * len(header)}")
                print(f"  {current_exp.upper()}")
                print(f"{'=' * len(header)}")
                print(header)
                print(sep)

            print(f"{row['variant']:<{W['variant']}} {row['detector_model']:<{W['model']}} "
                  f"{row['method']:<{W['method']}} "
                  f"{fmt(row['n_removed']):>6} "
                  f"{fmt(row['omissions_match']):>5} {fmt(row['omissions_partial']):>5} {fmt(row['omissions_none']):>5} "
                  f"{fmt(row['reqs_found_via_omissions']):>6} "
                  f"{fmt(row['additions_match']):>5} {fmt(row['additions_partial']):>5} {fmt(row['additions_none']):>5} "
                  f"{fmt(row['reqs_found_via_additions']):>6}")

        print(f"\n\n=== AGGREGATE BY DETECTOR MODEL (judge={judge_slug}) ===")
        print(f"{'model':<22} {'n':>5} {'om_recall':>10} {'om_precision':>13} {'ad_recall':>10}")
        print("-" * 64)
        for model in sorted(set(r["detector_model"] for r in judge_rows)):
            subset = [r for r in judge_rows if r["detector_model"] == model]
            recalls, precisions, ad_recalls = [], [], []
            for r in subset:
                if r["n_removed"] and r["reqs_found_via_omissions"] is not None:
                    recalls.append(r["reqs_found_via_omissions"] / r["n_removed"])
                if r["n_omissions"] and r["omissions_match"] is not None:
                    precisions.append(r["omissions_match"] / r["n_omissions"])
                if r["n_removed"] and r["reqs_found_via_additions"] is not None:
                    ad_recalls.append(r["reqs_found_via_additions"] / r["n_removed"])
            print(f"{model:<22} {len(subset):>5} "
                  f"{fmtf(safe_mean(recalls)):>10} "
                  f"{fmtf(safe_mean(precisions)):>13} "
                  f"{fmtf(safe_mean(ad_recalls)):>10}")

        print(f"\n=== AGGREGATE BY METHOD (judge={judge_slug}) ===")
        print(f"{'method':<20} {'n':>5} {'om_recall':>10} {'om_precision':>13} {'ad_recall':>10}")
        print("-" * 62)
        for method in sorted(set(r["method"] for r in judge_rows)):
            subset = [r for r in judge_rows if r["method"] == method]
            recalls, precisions, ad_recalls = [], [], []
            for r in subset:
                if r["n_removed"] and r["reqs_found_via_omissions"] is not None:
                    recalls.append(r["reqs_found_via_omissions"] / r["n_removed"])
                if r["n_omissions"] and r["omissions_match"] is not None:
                    precisions.append(r["omissions_match"] / r["n_omissions"])
                if r["n_removed"] and r["reqs_found_via_additions"] is not None:
                    ad_recalls.append(r["reqs_found_via_additions"] / r["n_removed"])
            print(f"{method:<20} {len(subset):>5} "
                  f"{fmtf(safe_mean(recalls)):>10} "
                  f"{fmtf(safe_mean(precisions)):>13} "
                  f"{fmtf(safe_mean(ad_recalls)):>10}")


def write_csv(rows):
    out_path = os.path.join(RESULTS_DIR, "match_summary.csv")
    fields = [
        "judge_model", "experiment_type", "app", "variant", "detector_model", "method",
        "n_removed", "n_omissions", "n_additions",
        "omissions_match", "omissions_partial", "omissions_none", "reqs_found_via_omissions",
        "additions_match", "additions_partial", "additions_none", "reqs_found_via_additions",
    ]
    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    print(f"\nCSV written to {out_path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default=MATCHER_MODEL,
                        help=f"LLM judge model (default: {MATCHER_MODEL}). "
                             f"Recommended: {', '.join(JUDGE_MODELS)}")
    parser.add_argument("--force", action="store_true", help="Re-run even if match files exist")
    parser.add_argument("--app", help="Filter to a specific app")
    parser.add_argument("--variant", help="Filter to a specific variant")
    parser.add_argument("--summary-only", action="store_true",
                        help="Skip matching, just print summary from existing match files")
    args = parser.parse_args()

    entries = collect_entries()
    if args.app:
        entries = [e for e in entries if e["app"] == args.app]
    if args.variant:
        entries = [e for e in entries if e["variant"] == args.variant]

    print(f"Found {len(entries)} detection results.")

    if not args.summary_only:
        configure_model(args.model)
        omissions_system, omissions_user = load_prompt("match_omissions_to_requirements.txt")
        additions_system, additions_user = load_prompt("match_additions_to_requirements.txt")
        run_matching(entries, args, omissions_system, omissions_user, additions_system, additions_user)

    rows = collect_summary_rows(entries)
    matched_rows = [r for r in rows if r["omissions_match"] is not None]
    if matched_rows:
        print_summary(matched_rows)
        write_csv(matched_rows)
    else:
        print("No match results found yet. Run without --summary-only to generate them.")


if __name__ == "__main__":
    main()
