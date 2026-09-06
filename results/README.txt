Results from revised prompts (2026-05-25 onward).

These experiments use the updated prompts with:
- "properties" terminology for code-side findings
- Symmetric output schema: {id, category, description, reasoning} for both additions and omissions
- Single "category" field (no primary/secondary)
- EXTERNAL_INTERACTIONS category (renamed from CROSS_SERVICE)
- categories.txt (replaced ontology.txt)
- "Domain-standard behaviors" removed from omission guidance
- Revised examples (example_task_tracker.txt, example_warehouse.txt)
- updated removed requirements not to use password hashing as this is included in general instructions to code generator.
- added the non-infrastructure requirements to the full spec used for gap detection.

Detection methods compared:
1. Single-agent zero-shot
2. Single-agent one-shot (task tracker example)
3. Single-agent two-shot (both examples)
4. Two one-shots with different examples, results combined

These are the results cited in the paper.
