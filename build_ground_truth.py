"""
Materialize the canonical ground truth for Gap Detector precision/recall
into a single file: results/ground_truth.json.

Motivation (2026-07-12 discussion): the operative ground truth was implicit
in two differently-formatted sources plus three code-level adjustments —
fragile to cite and easy to misread. This script consolidates it into one
explicit, per-requirement JSON, and VERIFIES byte-for-byte equivalence with
what the scoring scripts actually compute (via the same loader functions
they import), so the file is guaranteed to describe the numbers in
precision_dedup.csv / recall_tracked.csv.

Sources (unchanged, still authoritative for regeneration):
  - Microservices: results/inferability-consistency.txt (3-pass consensus
    GAP/INF/PAR over the gpt-5.4-generated code; 2026-05-27)
  - RESTestBench: results/restestbench/{variant}/per-req/gpt-5.4/summary.json
    (single-pass per-req verdicts; experiment_per_req.py; 2026-06-22/23)
  - Validation overlay: results/restestbench/ground-truth-recheck/
    recheck_summary.json (2 models x 2 passes, 2026-07-12) — embedded as
    per-requirement recheck status, NOT yet used to change classifications.

Rules applied (made explicit here instead of living in code):
  1. R13 (public-library/logs-R12R13) is EXCLUDED from delta entirely —
     invalid removal (reduced spec still described the behavior).
  2. Microservice consensus PAR counts as a TRUE GAP (in Delta_minus) —
     the conservative-against-the-detector choice. Known sensitivity:
     petorder R10 and petstore R6 were judged "present in code (with
     qualification)" by the 2026-06-25 manual pass.
  3. RESTestBench: NOT_IMPLEMENTED -> true gap; IMPLEMENTED -> inferred.
     Disputed by the 2026-07-12 recheck (pending adjudication, TODO.md):
     realworld R15 (cross-model split) and realworld R5 (recheck majority
     says IMPLEMENTED).

Usage:
  python3 build_ground_truth.py

Output:
  results/ground_truth.json
"""

import json
import os
import sys
from datetime import datetime

REPO_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, REPO_DIR)
RESULTS_DIR = os.path.join(REPO_DIR, "results")

from compute_precision_tracked import (
    load_microservices_ground_truth,
    load_restestbench_ground_truth,
)
from compute_recall_tracked import (
    microservices_delta_and_true_gaps,
    restestbench_delta_and_true_gaps,
    R13_EXCLUDED,
)

MICRO_VARIANTS = {
    "nutrition": ["auth-R1R2R3", "dishes-R4R5R6", "profiles-R7R8R9", "ratings-R10R11R12"],
    "public-library": ["borrows-R1R2R3", "cardholders-R4R5R6R7", "books-R8R9R10R11", "logs-R12R13"],
    "pet-store": ["registry-R1R2R3", "petstore-R4R5R6R7", "petorder-R8R9R10"],
}

# 2/3-majority (non-unanimous) consensus cases per inferability-consistency.txt
MICRO_DISPUTED = {("cardholders", "R4"), ("auth", "R2"), ("dishes", "R6"), ("petstore", "R6")}

# PAR items the 2026-06-25 manual pass judged "present in code (with qualification)"
# Note: petorder R10 was removed from this dict — it is now excluded from delta
# entirely (full spec leak, approved 2026-07-17); see R13_EXCLUDED in
# compute_recall_tracked.py (which build_ground_truth.py imports).
MANUAL_PRESENT_NOTES = {
    ("petstore", "R6"): "2026-06-25 manual pass judged present (regex extracts first integer from ranges)",
}

RB_VARIANT_APPS = {
    "todoapp-R1R2R4R5R7R8R10R12": "todoapp",
    "fastapi-R4R10R13R30R35R47": "fastapi",
    "fastapi-R14R15R16R17R18R46R56": "fastapi",
    "realworld-R5R6R9R12R19R23R25R27R29": "nestjs-realworld",
    "realworld-R2R10R13R15R24R26R28": "nestjs-realworld",
}


def main():
    micro_gt = load_microservices_ground_truth()
    rb_gt = load_restestbench_ground_truth()

    recheck_path = os.path.join(RESULTS_DIR, "restestbench", "ground-truth-recheck",
                                "recheck_summary.json")
    recheck = {}
    if os.path.exists(recheck_path):
        with open(recheck_path) as f:
            for row in json.load(f)["records"]:
                recheck[(row["variant"], f"R{row['req_id']}")] = row

    out = {
        "generated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "script": "build_ground_truth.py",
        "sources": {
            "microservices": "results/inferability-consistency.txt (3-pass consensus, 2026-05-27)",
            "restestbench": "results/restestbench/{variant}/per-req/gpt-5.4/summary.json "
                            "(experiment_per_req.py, 2026-06-22/23)",
            "validation_overlay": "results/restestbench/ground-truth-recheck/recheck_summary.json "
                                  "(2 models x 2 passes, 2026-07-12; informational only)",
        },
        "rules": [
            "logs R13 (public-library/logs-R12R13) excluded from delta: invalid removal (2026-06-30)",
            "petorder R10 (pet-store/petorder-R8R9R10) excluded from delta: full spec leak — "
            "general guideline 'All resource ids unique' subsumes removed sentence (approved 2026-07-17)",
            "Microservice consensus PAR counts as true gap (conservative against detector)",
            "RESTestBench NOT_IMPLEMENTED -> true gap; IMPLEMENTED -> inferred; "
            "realworld-R2 R15 and realworld-R1 R5 reclassified IMPLEMENTED (author adjudication 2026-07-17)",
        ],
        "label_definitions": {
            "INFERRED": "Fully implemented in substance: the generated code contains "
                        "behavior satisfying the requirement; a test exercising the "
                        "required behavior would PASS. Behavior-preserving differences "
                        "(naming, equivalent mechanisms) do not block this label.",
            "GAP": "Not implemented: no code addresses the requirement; a test would "
                   "fail because the required behavior is ABSENT entirely (not merely "
                   "wrong in a detail).",
            "PARTIAL": "Partially implemented: the mechanism/endpoint/logic for the "
                       "requirement is present but deviates in a material observable "
                       "detail (wrong constant, format, status code; missing sub-case; "
                       "wrong scope); a test would fail ON THE DETAIL though the "
                       "machinery exists.",
            "NOT_IMPLEMENTED": "RESTestBench per-req verdict: the requirement's test "
                               "scenario is not satisfied by the code (binary protocol; "
                               "no PARTIAL label exists on this side).",
            "IMPLEMENTED": "RESTestBench per-req verdict: the requirement's test "
                           "scenario is satisfied by the code.",
            "classification_true_gap": "GAP or PARTIAL (microservices) / "
                                       "NOT_IMPLEMENTED (RESTestBench) -> in Delta_minus",
            "classification_inferred": "INFERRED (microservices) / IMPLEMENTED "
                                       "(RESTestBench) -> in I",
        },
        "requirement_text_pointers": {
            "microservices": "specs/{app}/{variant}-removals.txt",
            "restestbench": "RESTestBench/data/requirements/{service}/req_{id}.json",
        },
        "variants": {},
    }

    tg_total = inf_total = 0

    for app, variants in MICRO_VARIANTS.items():
        for variant in variants:
            delta, true_gaps = microservices_delta_and_true_gaps(micro_gt, variant)
            short = variant.split("-", 1)[0]
            reqs = {}
            for (sn, rid), label in sorted(micro_gt.items()):
                if sn != short:
                    continue
                if (sn, rid) in R13_EXCLUDED:
                    reqs[rid] = {"classification": "excluded", "source_label": label,
                                 "note": "invalid removal (R13 correction, 2026-06-30)"}
                    continue
                cls = "true_gap" if label in ("GAP", "PAR") else "inferred"
                rec = {"classification": cls, "source_label": label,
                       "consensus_unanimous": (sn, rid) not in MICRO_DISPUTED}
                if (sn, rid) in MANUAL_PRESENT_NOTES:
                    rec["note"] = MANUAL_PRESENT_NOTES[(sn, rid)]
                reqs[rid] = rec
            out["variants"][variant] = {
                "dataset": "microservices", "app": app,
                "delta": sorted(delta), "true_gaps": sorted(true_gaps),
                "inferred": sorted(delta - true_gaps),
                "requirements": reqs,
            }
            tg_total += len(true_gaps)
            inf_total += len(delta - true_gaps)

    for variant, app in RB_VARIANT_APPS.items():
        delta, true_gaps = restestbench_delta_and_true_gaps(rb_gt, variant)
        reqs = {}
        for rid in sorted(delta, key=lambda x: int(x[1:])):
            cls = "true_gap" if rid in true_gaps else "inferred"
            rec = {"classification": cls,
                   "source_label": "NOT_IMPLEMENTED" if cls == "true_gap" else "IMPLEMENTED"}
            rc = recheck.get((variant, rid))
            if rc:
                rec["recheck_2026_07_12"] = {
                    "unanimous": rc["unanimous"],
                    "confirms_original": rc["matches_original"],
                }
                if not rc["matches_original"]:
                    rec["note"] = "DISPUTED by 4-verdict recheck; pending adjudication (TODO.md)"
            reqs[rid] = rec
        out["variants"][variant] = {
            "dataset": "restestbench", "app": app,
            "delta": sorted(delta, key=lambda x: int(x[1:])),
            "true_gaps": sorted(true_gaps, key=lambda x: int(x[1:])),
            "inferred": sorted(delta - true_gaps, key=lambda x: int(x[1:])),
            "requirements": reqs,
        }
        tg_total += len(true_gaps)
        inf_total += len(delta - true_gaps)

    out["totals"] = {
        "variants": len(out["variants"]),
        "valid_removals": tg_total + inf_total,
        "true_gaps": tg_total,
        "inferred": inf_total,
        "excluded": 1,
    }

    # ------- verification: exact match with what the scoring scripts compute -------
    mismatches = 0
    for variant, v in out["variants"].items():
        if v["dataset"] == "microservices":
            delta, tg = microservices_delta_and_true_gaps(micro_gt, variant)
        else:
            delta, tg = restestbench_delta_and_true_gaps(rb_gt, variant)
        if sorted(delta) != sorted(v["delta"]) or sorted(tg) != sorted(v["true_gaps"]):
            mismatches += 1
            print(f"MISMATCH: {variant}")
    if mismatches:
        print(f"VERIFICATION FAILED: {mismatches} variants differ from scoring-script loaders.")
        sys.exit(1)

    out_path = os.path.join(RESULTS_DIR, "ground_truth.json")
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2)

    print(f"Verification PASSED: delta/true_gaps identical to scoring-script loaders "
          f"for all {len(out['variants'])} variants.")
    print(f"Totals: {out['totals']}")
    print(f"Written to {out_path}")


if __name__ == "__main__":
    main()
