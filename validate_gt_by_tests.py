"""
Validate RESTestBench ground-truth labels by ACTUAL TEST EXECUTION
==================================================================

Purpose
-------
The paper's ground truth for each removed requirement (IMPLEMENTED / inferred vs.
NOT_IMPLEMENTED / true gap) comes from an LLM-as-a-judge (the per-req evaluation,
results/restestbench/{variant}/per-req/gpt-5.4/summary.json). A reviewer's #1
concern is circularity: LLMs act as generator, ground-truth judge, and match
judge. This script provides an INDEPENDENT, non-LLM check of the ground truth for
RESTestBench, where each requirement has a hand-written golden test.

For every removed requirement in every RESTestBench variant we:
  1. Load the GPT-5.4-generated code (results/restestbench/{variant}/generated_code.py)
     into an in-memory SQLite database via FastAPI's TestClient (no network, no
     external DB; the same harness Experiment 4 used).
  2. Run that requirement's golden test (RESTestBench/data/tests/{service}/test_{N}.py)
     against the loaded app, redirecting the test's `requests` calls
     (http://localhost:8000/...) to the in-process TestClient via a shim.
  3. Interpret the outcome:
        golden test PASS  -> behavior present  -> should be IMPLEMENTED (inferred)
        golden test FAIL  -> behavior absent/wrong -> should be NOT_IMPLEMENTED (gap)
        golden test ERROR -> test could not execute in-process (e.g. it needs an
                             external service such as Mailcatcher) -> SKIP,
                             reported separately, excluded from agreement stats.
  4. Compare the test verdict with the LLM (per-req) verdict.

Agreement between the two INDEPENDENT sources (executable tests vs. LLM judge)
is the evidence that de-risks the circularity threat. Disagreements are listed
individually for author adjudication.

Isolation
---------
Each variant runs in its own subprocess (--variant worker mode) because the five
generated apps are different FastAPI/SQLModel applications that reuse table names;
loading two of them in one interpreter collides on the global SQLModel metadata.
Within a variant, the in-memory DB is dropped and recreated (and startup handlers
re-fired) before each requirement's test, so tests do not leak state into one
another.

Usage
-----
  python validate_gt_by_tests.py                 # orchestrate all 5 variants, print report
  python validate_gt_by_tests.py --variant fastapi-R4R10R13R30R35R47   # one variant (worker)

Output
------
  results/restestbench-gt-validation/{variant}.json   # per-variant raw results
  results/restestbench-gt-validation/summary.json     # aggregate + confusion matrix
  Human-readable report printed to stdout by the orchestrator.

NOTE: This script makes NO LLM calls. It only executes existing golden tests
against already-generated code and compares to already-computed LLM verdicts.
"""

import argparse
import importlib.util
import json
import os
import subprocess
import sys
import types

REPO = os.path.dirname(os.path.abspath(__file__))
RB_DIR = os.path.join(REPO, "results", "restestbench")
GOLDEN_DIR = os.path.join(REPO, "RESTestBench", "data", "tests")
OUT_DIR = os.path.join(REPO, "results", "restestbench-gt-validation")

# app prefix in the variant name  ->  golden-test service directory name
SERVICE_DIR = {"todoapp": "todoapp", "fastapi": "fastapi", "realworld": "nestjs-realworld"}

# ---------------------------------------------------------------------------
# GOLDEN-TEST SETUP ADAPTATIONS (2026-08-19)
# ---------------------------------------------------------------------------
# Some LLM-generated golden tests fail in their SETUP scaffolding (before the
# removed-requirement assertion is reached) because they assume a surface
# contract — a response field NAME or ENVELOPE shape — that the GPT-5.4-generated
# code chose differently, AND that the spec does not mandate. We adapt ONLY those
# spec-agnostic setup accesses so the test can reach the requirement it is meant
# to check. We never touch the requirement's own assertion. Each adaptation is a
# single exact string replacement, applied to a fresh copy of the golden-test
# source at load time (the vendored golden test on disk is not modified), and is
# guarded by an exact-occurrence-count check so a stale/renamed target fails
# loudly instead of silently doing nothing.
#
# ADAPTATIONS[(service, req_id)] = [(old_string, new_string, expected_count, reason), ...]
ADAPTATIONS = {
    # ---- todoapp: login response field name -----------------------------------
    # Golden test reads login_response.json()["accessToken"]; the generated code
    # returns {"access_token": ..., "token_type": "bearer"} (standard OAuth2).
    # The spec only says "receive a JWT access token" and does NOT name the field.
    **{("todoapp", rid): [(
        'login_response.json()["accessToken"]',
        'login_response.json()["access_token"]',
        1,
        "token field name: spec-agnostic; code uses snake_case access_token",
    )] for rid in (1, 2, 4, 5, 7, 8, 10, 12)},

    # ---- realworld: article-creation response envelope ------------------------
    # Golden tests read the created article's slug at the TOP level, but the
    # generated app correctly returns the Conduit envelope {"article": {...}}.
    # Fixing the access to the spec-correct nesting lets setup proceed. (These
    # touch only the create-article SETUP step, never a feed/list assertion.)
    ("nestjs-realworld", 5): [(
        'created_article["slug"]', 'created_article["article"]["slug"]', 1,
        "article envelope: code returns spec-correct {'article':{...}}",
    )],
    ("nestjs-realworld", 19): [(
        'created_article["slug"]', 'created_article["article"]["slug"]', 1,
        "article envelope: code returns spec-correct {'article':{...}}",
    )],
    ("nestjs-realworld", 26): [(
        'article_response.json()["slug"]', 'article_response.json()["article"]["slug"]', 1,
        "article envelope: code returns spec-correct {'article':{...}}",
    )],
    ("nestjs-realworld", 28): [
        ('article_response.json()["slug"]', 'article_response.json()["article"]["slug"]', 1,
         "article envelope (1st create): spec-correct {'article':{...}}"),
        ('article_response2.json()["slug"]', 'article_response2.json()["article"]["slug"]', 1,
         "article envelope (2nd create): spec-correct {'article':{...}}"),
    ],
    ("nestjs-realworld", 29): [(
        'article_response.json()["slug"]', 'article_response.json()["article"]["slug"]', 1,
        "article envelope: spec-correct {'article':{...}}; a['slug'] on list "
        "elements (later lines) is left unchanged and correct",
    )],
}

# Requirements whose golden test, even after the adaptations above, cannot reach
# its removed-requirement assertion because of a SEPARATE setup mismatch that we
# deliberately do NOT adapt. When the golden test FAILs, these are reported
# UNDETERMINED (with this reason), never counted as NOT_IMPLEMENTED.
#   todoapp R1,R5,R8,R10,R12: their setup creates a todo and asserts HTTP 201.
#   The todoapp SPEC does NOT specify a success status for POST /todos (it is
#   silent). RESTestBench's reference implementation returns 201
#   (TypedResults.Created, Todo.Api/Todos/TodoApi.cs), so the golden test asserts
#   201 to match the reference. The generated code returns FastAPI's default 200
#   (no explicit status_code). This is therefore a REFERENCE-CONTRACT mismatch on
#   a status code the spec leaves open — NOT a spec/kept-requirement violation by
#   the generated code. We do not adapt it (adapting a status assertion would edge
#   toward masking behavior), so these reqs stay undetermined.
SETUP_BLOCKED = {
    ("todoapp", 1): "setup asserts POST /todos == 201 (reference contract; spec is silent on create status); generated code returns FastAPI-default 200 — not adapted",
    ("todoapp", 5): "setup asserts POST /todos == 201 (reference contract; spec is silent on create status); generated code returns FastAPI-default 200 — not adapted",
    ("todoapp", 8): "setup asserts POST /todos == 201 (reference contract; spec is silent on create status); generated code returns FastAPI-default 200 — not adapted",
    ("todoapp", 10): "setup asserts POST /todos == 201 (reference contract; spec is silent on create status); generated code returns FastAPI-default 200 — not adapted",
    ("todoapp", 12): "setup asserts POST /todos == 201 (reference contract; spec is silent on create status); generated code returns FastAPI-default 200 — not adapted",
}


def apply_adaptations(src, service, req_id):
    """Return (adapted_src, applied_list). Raises if a target is not present the
    expected number of times (so a silent no-op can never happen)."""
    applied = []
    for old, new, expected_count, reason in ADAPTATIONS.get((service, req_id), []):
        found = src.count(old)
        if found != expected_count:
            raise AssertionError(
                f"Adaptation guard failed for {service} R{req_id}: expected "
                f"{expected_count} occurrence(s) of {old!r}, found {found}. "
                f"Golden test may have changed; refusing to run silently."
            )
        src = src.replace(old, new)
        applied.append({"old": old, "new": new, "reason": reason})
    return src, applied


VARIANTS = [
    "todoapp-R1R2R4R5R7R8R10R12",
    "fastapi-R4R10R13R30R35R47",
    "fastapi-R14R15R16R17R18R46R56",
    "realworld-R2R10R13R15R24R26R28",
    "realworld-R5R6R9R12R19R23R25R27R29",
]


# ---------------------------------------------------------------------------
# Worker: run all golden tests for one variant against its generated app
# ---------------------------------------------------------------------------

def _load_app(code_path, module_name):
    """Load generated_code.py, swap in an in-memory SQLite engine, create tables."""
    from sqlalchemy.pool import StaticPool
    from sqlmodel import SQLModel, create_engine
    from fastapi.testclient import TestClient

    if module_name in sys.modules:
        del sys.modules[module_name]
    spec = importlib.util.spec_from_file_location(module_name, code_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)

    mem_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    mod.engine = mem_engine
    SQLModel.metadata.create_all(mem_engine)
    client = TestClient(mod.app, raise_server_exceptions=False)
    return mod, client, mem_engine


def _reset_db(mod, engine):
    """Drop + recreate all tables and re-fire startup handlers (reseed superuser)."""
    from sqlmodel import SQLModel
    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)
    app = mod.app
    for handler in getattr(getattr(app, "router", app), "on_startup", []):
        try:
            handler()
        except Exception:
            pass  # a failed seed is surfaced by the test outcome itself


class _ShimResp:
    def __init__(self, r):
        self._r = r
        self.status_code = r.status_code
        self.text = r.text
        self.content = r.content
        self.headers = r.headers

    def json(self):
        return self._r.json()


def _make_requests_shim(client, base="http://localhost:8000"):
    """A stand-in `requests` module that routes HTTP verbs to the TestClient."""
    shim = types.ModuleType("requests")

    def strip(url):
        return url[len(base):] if url.startswith(base) else url

    for method in ["get", "post", "put", "delete", "patch", "head", "options"]:
        def make(m):
            def call(url, **kw):
                return _ShimResp(getattr(client, m)(strip(url), **kw))
            return call
        setattr(shim, method, make(method))

    class RequestException(Exception):
        pass
    shim.RequestException = RequestException
    shim.exceptions = types.SimpleNamespace(RequestException=RequestException)
    return shim


def _run_golden_test(client, test_path, service, req_id):
    """Execute a golden test file against the client. Return (status, detail, applied).

    status: PASS  (all test_* functions passed)
            FAIL  (>=1 assertion failed, none errored)
            ERROR (>=1 raised a non-assertion exception and none failed)
    applied: list of setup adaptations applied to the golden-test source (may be empty)
    """
    shim = _make_requests_shim(client)
    saved = sys.modules.get("requests")
    sys.modules["requests"] = shim
    try:
        src = open(test_path).read()
        src, applied = apply_adaptations(src, service, req_id)
        ns = {"__name__": "golden_test"}
        exec(compile(src, test_path, "exec"), ns)
        fns = [k for k, v in ns.items() if k.startswith("test_") and callable(v)]
        if not fns:
            return "ERROR", "no test_* function found in golden file", applied
        statuses = []
        for fn in fns:
            try:
                ns[fn]()
                statuses.append(("PASS", ""))
            except AssertionError as e:
                statuses.append(("FAIL", f"{fn}: {str(e)[:200]}"))
            except Exception as e:
                statuses.append(("ERROR", f"{fn}: {type(e).__name__}: {str(e)[:200]}"))
        if any(s == "FAIL" for s, _ in statuses):
            return "FAIL", " | ".join(d for s, d in statuses if s == "FAIL"), applied
        if any(s == "ERROR" for s, _ in statuses):
            return "ERROR", " | ".join(d for s, d in statuses if s == "ERROR"), applied
        return "PASS", "", applied
    finally:
        if saved is not None:
            sys.modules["requests"] = saved
        else:
            sys.modules.pop("requests", None)


def run_variant(variant):
    """Run all removed-requirement golden tests for one variant. Return result dict."""
    app = variant.split("-")[0]
    service = SERVICE_DIR[app]
    code_path = os.path.join(RB_DIR, variant, "generated_code.py")
    removals = json.load(open(os.path.join(RB_DIR, variant, "removals.json")))
    perreq = json.load(open(os.path.join(RB_DIR, variant, "per-req", "gpt-5.4", "summary.json")))
    llm_impl = set(perreq["removed_implemented"])          # LLM verdict IMPLEMENTED
    llm_gap = set(perreq["removed_not_implemented"])       # LLM verdict NOT_IMPLEMENTED

    mod, client, engine = _load_app(code_path, f"gen_{variant.replace('-', '_')}")

    rows = []
    for rem in removals:
        rid = rem["id"]
        test_path = os.path.join(GOLDEN_DIR, service, f"test_{rid}.py")
        _reset_db(mod, engine)
        status, detail, applied = _run_golden_test(client, test_path, service, rid)

        # test verdict: PASS -> implemented; FAIL -> gap; ERROR -> undetermined.
        # Exception: a requirement listed in SETUP_BLOCKED that FAILs did not
        # reach its own assertion (it failed on an unadapted setup mismatch);
        # such a FAIL is reported UNDETERMINED, never NOT_IMPLEMENTED.
        blocked_reason = SETUP_BLOCKED.get((service, rid))
        if status == "PASS":
            test_verdict = "IMPLEMENTED"
        elif status == "FAIL" and blocked_reason is None:
            test_verdict = "NOT_IMPLEMENTED"
        else:  # ERROR, or FAIL on a known setup blocker
            test_verdict = "UNDETERMINED"

        if rid in llm_impl:
            llm_verdict = "IMPLEMENTED"
        elif rid in llm_gap:
            llm_verdict = "NOT_IMPLEMENTED"
        else:
            llm_verdict = "UNKNOWN"

        agree = (test_verdict == llm_verdict) if test_verdict != "UNDETERMINED" else None
        rows.append({
            "req_id": rid,
            "test_status": status,
            "test_verdict": test_verdict,
            "llm_verdict": llm_verdict,
            "agree": agree,
            "detail": detail,
            "adaptations": applied,
            "setup_blocked_reason": blocked_reason,
        })

    return {"variant": variant, "service": service, "results": rows}


# ---------------------------------------------------------------------------
# Orchestrator: spawn one worker subprocess per variant, aggregate
# ---------------------------------------------------------------------------

def orchestrate():
    os.makedirs(OUT_DIR, exist_ok=True)
    all_results = []
    for variant in VARIANTS:
        print(f"\n{'='*66}\nVariant: {variant}\n{'='*66}")
        cmd = [sys.executable, os.path.abspath(__file__), "--variant", variant]
        proc = subprocess.run(cmd, capture_output=True, text=True, cwd=REPO)
        if proc.returncode != 0:
            print(f"  WORKER FAILED (exit {proc.returncode})")
            print(proc.stderr[-1500:])
            continue
        out_path = os.path.join(OUT_DIR, f"{variant}.json")
        data = json.load(open(out_path))
        all_results.append(data)
        for r in data["results"]:
            mark = {"PASS": "PASS", "FAIL": "FAIL", "ERROR": "ERR "}[r["test_status"]]
            flag = "" if r["agree"] is None else ("  AGREE" if r["agree"] else "  <<< DISAGREE")
            adapt = "  [adapted]" if r.get("adaptations") else ""
            print(f"  R{r['req_id']:<3} test={mark}  test_verdict={r['test_verdict']:<15} "
                  f"llm={r['llm_verdict']:<15}{flag}{adapt}")

    _report(all_results)


def _report(all_results):
    # Confusion matrix over comparable (non-UNDETERMINED) requirements
    tp_impl = tn_gap = 0
    disagreements = []
    undetermined = []
    n_compared = 0
    # matrix[llm][test]
    matrix = {"IMPLEMENTED": {"IMPLEMENTED": 0, "NOT_IMPLEMENTED": 0},
              "NOT_IMPLEMENTED": {"IMPLEMENTED": 0, "NOT_IMPLEMENTED": 0}}

    for data in all_results:
        for r in data["results"]:
            if r["test_verdict"] == "UNDETERMINED" or r["llm_verdict"] == "UNKNOWN":
                undetermined.append((data["variant"], r))
                continue
            n_compared += 1
            matrix[r["llm_verdict"]][r["test_verdict"]] += 1
            if not r["agree"]:
                disagreements.append((data["variant"], r))

    agree_count = matrix["IMPLEMENTED"]["IMPLEMENTED"] + matrix["NOT_IMPLEMENTED"]["NOT_IMPLEMENTED"]

    print("\n\n" + "=" * 66)
    print("SUMMARY: golden-test execution vs. LLM (per-req) ground truth")
    print("=" * 66)
    print(f"\nRequirements compared (both verdicts available): {n_compared}")
    print(f"Undetermined (test could not execute in-process): {len(undetermined)}")
    print(f"\nConfusion matrix (rows = LLM verdict, cols = golden-test verdict):")
    print(f"{'':>22}{'test:IMPL':>14}{'test:GAP':>14}")
    print(f"{'LLM:IMPLEMENTED':>22}{matrix['IMPLEMENTED']['IMPLEMENTED']:>14}"
          f"{matrix['IMPLEMENTED']['NOT_IMPLEMENTED']:>14}")
    print(f"{'LLM:NOT_IMPLEMENTED':>22}{matrix['NOT_IMPLEMENTED']['IMPLEMENTED']:>14}"
          f"{matrix['NOT_IMPLEMENTED']['NOT_IMPLEMENTED']:>14}")
    if n_compared:
        print(f"\nAgreement: {agree_count}/{n_compared} = {agree_count/n_compared:.3f}")

    if disagreements:
        print(f"\nDISAGREEMENTS ({len(disagreements)}) — for author adjudication:")
        for variant, r in disagreements:
            print(f"  {variant}  R{r['req_id']}: "
                  f"LLM={r['llm_verdict']} but test={r['test_status']}({r['test_verdict']})")
            if r["detail"]:
                print(f"      {r['detail'][:200]}")

    if undetermined:
        print(f"\nUNDETERMINED ({len(undetermined)}) — golden test could not reach its assertion:")
        for variant, r in undetermined:
            reason = r.get("setup_blocked_reason") or r["detail"]
            print(f"  {variant}  R{r['req_id']}: {r['test_status']} — {reason[:170]}")

    summary = {
        "n_compared": n_compared,
        "agreement": (agree_count / n_compared) if n_compared else None,
        "agree_count": agree_count,
        "confusion_matrix": matrix,
        "n_disagreements": len(disagreements),
        "disagreements": [{"variant": v, **r} for v, r in disagreements],
        "n_undetermined": len(undetermined),
        "undetermined": [{"variant": v, **r} for v, r in undetermined],
    }
    with open(os.path.join(OUT_DIR, "summary.json"), "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\nWrote {os.path.join(OUT_DIR, 'summary.json')}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", help="Run one variant in worker mode (internal).")
    args = ap.parse_args()
    if args.variant:
        os.makedirs(OUT_DIR, exist_ok=True)
        data = run_variant(args.variant)
        with open(os.path.join(OUT_DIR, f"{args.variant}.json"), "w") as f:
            json.dump(data, f, indent=2)
    else:
        orchestrate()


if __name__ == "__main__":
    main()
