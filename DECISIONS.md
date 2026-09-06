# Ground-Truth and Scoring Decisions

This document records judgment calls made in constructing the ground truth
(GT) and scoring the Gap Detector (GD) experiments, so that reviewers can audit
them. All raw inputs and outputs referenced here are included in this package.

## 1. Label and scoring policy

- **PARTIAL counts as a gap.** The microservice GT judge assigns one of
  INFERRED / GAP / PARTIAL per removed requirement (prompt: Fig. 4 of the
  paper). PARTIAL (mechanism present but a material, observable detail is
  wrong) is scored as a true gap: fulfillment is binary, and a test of the
  requirement as stated would fail. GAP-vs-PARTIAL is retained only as a
  diagnostic sub-division.
- **Multiple GD omissions for one requirement count once.** If a GD emits
  several omission items that the match judge maps to the same removed
  requirement, they count as a single detection (one TP or one FP).
- **MATCH and PARTIAL match labels both count as identifying a requirement.**
  [NOTE: PARTIAL used here is not the same PARTIAL used in the first item.]
  The match judge labels each GD omission MATCH / PARTIAL / no-match against
  the removed-requirement list. Both MATCH and PARTIAL are treated as the GD
  having identified the requirement; unmatched omissions are *excluded* items,
  reported separately via the exclusion rate (a conservative upper bound on
  false omissions — see paper §3, Step 5).
- **Aggregation is pooled (micro).** Precision/recall aggregates sum numerators
  and denominators across experiments, weighting each omitted requirement
  equally rather than each experiment equally.

## 2. Fully leaked requirements — EXCLUDED from the evaluation set (delta)

Two of the 73 originally removed requirements were fully leaked: the reduced
spec still contained the complete requirement, so the generator effectively saw
it and the requirement cannot be evaluated as "removed." Excluding them leaves
71 valid removals (37 RESTestBench + 34 microservices):

- **pet-store / petorder R10** (purchase-id uniqueness): the removed sentence
  is restated word-for-word in a kept general-guidelines section of the
  reduced spec ("All resource ids unique") — the requirement leaked in full
  via duplication in another section.
- **public-library / logs R13** (POST /logs): the removal was incompletely
  applied — the reduced spec's own description of the endpoint and its full
  payload remained in place. The leak mechanism differs from R10 (an
  incomplete edit rather than duplication elsewhere), but the effect is
  identical: the full requirement was visible to the generator.

## 3. Partially leaked (implied) requirements — RETAINED in the evaluation set (delta)

Other removed requirements were not restated outright, but remained implied by
kept text of the reduced spec. These are retained in delta, for the following
reasons:

- **Microservices (4 requirements)**: strongly or partially implied by kept
  text (e.g., a date format surviving in another service's section). The
  generator did *not* implement any of them despite the leakage, so all four
  are retained in delta as genuine gaps.
- **RESTestBench (13 requirements)**: each RESTestBench requirement is an
  independent test scenario, so omitting one is unambiguous even when another
  scenario implies similar behavior; all 13 are retained. Of these, 8 were
  implemented by the generator (counted as inferred) and 5 were not.

## 4. Human adjudications of GT verdicts

Four LLM judgements (2 models x 2 passes) were collected per removed
requirement. Three verdicts required author adjudication; the raw judgement
files for all of them are in this package.

- **RealWorld R15 (pagination) -> IMPLEMENTED.** Split verdict (2 x
  NOT_IMPLEMENTED citing newest-first ordering; 2 x IMPLEMENTED). The
  objection adds an ordering constraint the requirement does not state; the
  limit/offset mechanics and articlesCount are correct in the code. Later,
  independent execution of the corresponding unit test passed, confirming the
  adjudication (adjudication preceded test execution).
- **RealWorld R5 (article deletion) -> IMPLEMENTED.** 3-1 split; the lone
  dissent contradicts the requirement text, which itself specifies status 200
  with an empty object. Also subsequently confirmed by unit-test execution.
- **Pet-store R6 (lifespan range handling) -> PARTIAL (a gap).** The four
  judgements were unanimously INFERRED, but code inspection showed the
  positively-phrased statement given to the judges encoded only one of the
  requirement's two behaviors (range extraction) and omitted the other
  (absent-value must be JSON null; the code returns 0). The null-vs-0
  deviation is material, so the verdict was overridden to PARTIAL. This is the
  single case where a unanimous LLM verdict was overridden.

## 5. Unit-test validation of the GT (RESTestBench)

Each RESTestBench requirement has a golden unit test; we executed the tests for
all removed requirements against the generated code (paper Appendix B). Two
kinds of minimal intervention were needed, both documented in the paper:

- **One-token fix to generated TodoApp code**: `response_modegetl` ->
  `response_model`, a syntax typo that prevented the module from importing.
  Import-only; changes no behavior.
- **Setup-only test adaptations**: the JWT token field name in TodoApp tests
  (spec does not fix the name; test and generated code chose differently), and
  the article-response envelope in 5 RealWorld tests (tests read created-article
  fields at the top level; the generated code correctly nests them under
  `article` per the Conduit spec). Assertions were never modified.
- **Deliberately NOT adapted**: TodoApp tests asserting HTTP 201 on todo
  creation (the generated code returns the framework-default 200; the spec is
  silent on the status, but adapting a status assertion could mask a genuine
  deviation), and RealWorld feed/timestamp tests whose failing accesses are at
  or near the requirement's own assertion. These remain unexecuted and are
  reported as such.
- **The single test/GT disagreement (RealWorld R24, ordering)**: the code sorts
  articles by id rather than by creation timestamp; the LLM verdict (gap) is
  correct. The golden test creates articles sequentially with delays, making
  id-order and time-order coincide, so it cannot distinguish the two and
  passes. The disagreement reflects the test under-testing, not a GT error.

## 6. File map for auditing these decisions

| Decision | Evidence in this package |
|---|---|
| GT verdicts (microservices) | `results/inferability-consistency.txt` (3-pass consensus), `results/microservices-ground-truth-recheck-v2/` (per-judgement label + evidence + reasoning) |
| GT verdicts (RESTestBench) | `results/restestbench/<variant>/per-req/gpt-5.4/` (per-requirement verdicts), `results/restestbench/ground-truth-recheck/` (2 models x 2 passes) |
| Consolidated GT incl. exclusions of §2 | `results/ground_truth.json` (rules + per-variant labels) |
| Leakage analysis (§3) | `results/restestbench/<variant>/spec-leakage/` |
| Unit-test validation (§5) | `validate_gt_by_tests.py`, `results/restestbench-gt-validation/` (per-requirement outcomes, adaptations applied, confusion matrices) |
