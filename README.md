# specgap-artifacts

Replication package for a paper (under double-anonymous review) on detecting
gaps between natural-language specifications and LLM-generated code, and on
which omitted requirements code-generating LLMs infer on their own.

The package contains all specifications, prompts, generated code, raw
experiment outputs, ground-truth artifacts, and scoring scripts needed to
verify every number in the paper. Reproducing the paper's tables from the
included raw outputs requires **no LLM calls** (stdlib Python only); re-running
the experiments end-to-end requires LLM API access (see "Re-running from
scratch").

**External dependency (RESTestBench).** This package does **not** redistribute
the RESTestBench benchmark. Scripts that build the RESTestBench specifications
or execute its golden unit tests read from a local `RESTestBench/` checkout.
To run those scripts, clone the upstream benchmark into the package root:

```bash
git clone https://github.com/casablancahotelsoftware/RESTestBench.git
git -C RESTestBench checkout 4decc1e36ea3dd41b64ce3e3ac6a85bc72df36ae
```

This provides `RESTestBench/data/requirements/` (used by the RESTestBench
detection, per-requirement, and spec-leakage scripts) and
`RESTestBench/data/tests/` (used by the unit-test ground-truth validation,
Appendix B). Reproducing the paper's tables from the **included** outputs (the
"no LLM calls" path below) does not require this checkout; only re-running the
RESTestBench experiments and the Appendix B validation do.

## Layout

| Path | Contents |
|---|---|
| `specs/` | Full + reduced microservice specs, per-variant removal notes, positively-phrased removed requirements |
| `prompts/` | All prompts: Gap Detector (zero/one/two-shot + examples + categories), match judge, ground-truth judges |
| `generated/` | GPT-5.4-generated microservice code per reduced spec (the code all experiments analyze) |
| `results/<app>/<variant>/<gd_model>/<method>/` | The 256 detection runs: `detection_result.json` (GD output + token usage) and `omissions_match_{gpt-5.4,claude-sonnet-4-6}.json` (both match judges) |
| `results/restestbench/<variant>/` | RESTestBench variant inputs (`spec_full.txt`, `spec_reduced.txt`, `removals.json`, `generated_code.py`), per-requirement ground truth (`per-req/`), spec-leakage analysis (`spec-leakage/`) |
| `results/inferability-consistency.txt` | Microservices ground truth: 3-pass consensus (GAP / INFERRED / PARTIAL per removed requirement) |
| `results/microservices-ground-truth-recheck-v2/` | Microservices GT judgements, 2 models x 2 passes, with per-judgement evidence and reasoning |
| `results/restestbench/ground-truth-recheck/` | RESTestBench GT judgements, 2 models x 2 passes |
| `results/ground_truth.json` | Consolidated canonical ground truth (labels, exclusion rules, totals) |
| `results/restestbench-gt-validation/` | Unit-test execution validation of the ground truth (paper Appendix B) |
| `results/*.csv` | Scoring outputs behind the paper's tables |
| `RESTestBench/` | **not included** — clone separately (see "External dependency" above); required only to re-run the RESTestBench experiments / Appendix B validation |
| `DECISIONS.md` | Record of every ground-truth / scoring judgment call, with pointers to auditing evidence |

## Paper table / figure traceability

| Paper item | Produced by | From |
|---|---|---|
| Table 1 (LLM-as-a-Judge GT) | `microservices_ground_truth_recheck_v2.py`, `ground_truth_recheck.py`, `experiment_per_req.py` | raw judgements in `results/microservices-ground-truth-recheck-v2/`, `results/restestbench/ground-truth-recheck/`, `results/restestbench/*/per-req/` |
| Table 2 (precision + exclusion rate) | `compute_precision_dedup.py`, `compute_precision_tracked.py`, `aggregate_precision_by_dataset.py` | the 256 runs + ground truth → `results/precision_dedup.csv`, `precision_tracked.csv`, `precision_by_dataset.csv` |
| Table 3 (recall) | `compute_recall_tracked.py`, `aggregate_recall_by_dataset.py` | → `results/recall_tracked.csv`, `recall_by_dataset.csv` |
| Table 4 (inferred reqs) | ground truth counts | `results/ground_truth.json` (totals) |
| Table 5 (per prompt method) | `aggregate_precision_by_dataset.py`, `aggregate_recall_by_dataset.py` | `results/precision_by_dataset.csv`, `recall_by_dataset.csv` (`group_type=method`) |
| Table 6 (token usage) | `compute_token_usage.py` | `usage` blocks of the 256 `detection_result.json` → `results/token_usage_by_method.csv` |
| Tables 7–9 / Appendix B (GT validation by unit tests) | `validate_gt_by_tests.py` | golden tests in `RESTestBench/data/tests/` (clone; see above) + `generated_code.py` → `results/restestbench-gt-validation/` (included outputs) |
| Leaked reqs discussion | `detect_spec_leakage.py` | `results/restestbench/*/spec-leakage/` |
| Figs. 4, 5 (prompts) | — | `prompts/microservice_ground_truth_check_v2.txt`, `prompts/agent_single_zeroshot.txt` |
| Fig. 3 (example GD output + match) | — | `results/restestbench/fastapi-R4R10R13R30R35R47/claude-sonnet-4-6/oneshot-tracker/` |

## Reproducing the paper's numbers (no LLM calls)

The scoring layer only re-processes files already in this package:

```bash
python3 compute_precision_dedup.py        # Table 2 precision
python3 compute_recall_tracked.py         # Table 3 recall
python3 compute_precision_tracked.py      # Table 2 exclusion rates
python3 aggregate_precision_by_dataset.py # per-dataset/per-method breakdowns
python3 aggregate_recall_by_dataset.py
python3 compute_token_usage.py            # Table 6
python3 build_ground_truth.py             # regenerates results/ground_truth.json
```

`validate_gt_by_tests.py` (Appendix B) also makes no LLM calls, but it executes
the RESTestBench golden tests, so it requires the `RESTestBench/` checkout above
plus `fastapi`+`sqlmodel` (see `requirements.txt`). Its per-requirement outcomes
are also provided pre-computed in `results/restestbench-gt-validation/`.

## Re-running from scratch (LLM calls required)

Pipeline order: `generate_service.py` (code generation) →
`experiment_microservices.py` / `experiment_restestbench_*.py` (the 256 GD
runs) → `match_detections.py` (match judges) → scoring scripts above. Ground
truth: `experiment_per_req.py` (RESTestBench), `microservices_ground_truth_recheck_v2.py`
and `ground_truth_recheck.py` (2 models x 2 passes each).

Model endpoints in `detect_spec_gaps.py` (`MODEL_CONFIGS`) are placeholders
(`YOUR-AZURE-...`); supply your own deployment endpoints and API keys via the
environment variables named there. Models used in the paper: GPT-5.4,
Claude-Sonnet-4.6, GPT-4.1-mini, DeepSeek-V3-0324; temperature 0.

## Notes

- `detect_spec_gaps.py` contains, below `extract_result_json`, a legacy
  multi-agent pipeline that is **not** used by any reported experiment; the
  experiments import only the model-config/LLM-call plumbing at the top.
- `RESTestBench/` is **not** redistributed here; clone it from the upstream
  benchmark as described under "External dependency" above (the paper cites
  RESTestBench as the source). The requirement *text* that our results
  necessarily reference (e.g. in `results/restestbench/<variant>/spec_*.txt`,
  `removals.json`, and per-requirement verdicts) is retained only where needed
  to interpret the reported outputs. The three authored microservice
  applications' reference implementations are not part of this package (they
  are not used by any experiment; ground truth derives from LLM judges and the
  RESTestBench tests).
- `DECISIONS.md` documents every ground-truth exclusion and human adjudication,
  with a file map for auditing each one.
