"""
Spec-Reduction Experiment on RESTestBench TodoApp service.

TodoApp is a simple CRUD todo list with JWT authentication and per-user
isolation. The reference implementation is ASP.NET Core (C#), but we
generate Python/FastAPI for consistency with other experiments.

Removals are balanced across difficulty:
  Easy (highly inferrable):    R4 (GET 404), R7 (DELETE 404)
  Moderate:                    R2 (title validation), R10 (ID mismatch on PUT)
  Hard (feature cluster):      R1, R5, R8, R12 (per-user todo isolation)
"""

import os
import json
import sys
from datetime import datetime

REPO_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, REPO_DIR)

RESTESTBENCH_DIR = os.path.join(REPO_DIR, "RESTestBench")

# ========================= CONFIGURATION =========================

DETECTOR_MODEL = 'claude-sonnet-4-6'  # change to run a different detector
SERVICE = "todoapp"

REMOVALS = [1, 2, 4, 5, 7, 8, 10, 12]

METHODS = ['zeroshot', 'oneshot-tracker', 'oneshot-warehouse', 'twoshot']

removal_label = "R" + "R".join(str(r) for r in REMOVALS)
BASE_OUTPUT_DIR = os.path.join(REPO_DIR, "results", "restestbench",
                               f"todoapp-{removal_label}")

CODEGEN_REQUIREMENTS = """## Implementation Requirements
- Uses JWT tokens for authentication (PyJWT library)
- Uses bcrypt for password hashing (passlib library)
"""

# ========================= BUILD SPECIFICATIONS =========================

def load_all_requirements():
    """Load all 14 requirements, return dict keyed by id."""
    req_dir = os.path.join(RESTESTBENCH_DIR, "data", "requirements", SERVICE)
    reqs = {}
    for f in sorted(os.listdir(req_dir), key=lambda x: int(x.split('_')[1].split('.')[0])):
        d = json.load(open(os.path.join(req_dir, f)))
        reqs[d['id']] = d
    return reqs


def build_spec(reqs, exclude_ids=None):
    """Build a specification document from requirements."""
    if exclude_ids is None:
        exclude_ids = set()

    areas = {
        'Todo Operations': [],
        'User Authentication': [],
    }

    for rid, req in sorted(reqs.items()):
        if rid in exclude_ids:
            continue
        text = req['requirement_precise']
        mutant_files = set(m['file'] for m in req['mutants'])

        if any('Users' in f for f in mutant_files):
            areas['User Authentication'].append((rid, text))
        else:
            areas['Todo Operations'].append((rid, text))

    lines = []
    lines.append("SPECIFICATION: Todo List Application")
    lines.append("=" * 60)
    lines.append("")
    lines.append("This application provides a REST API for managing personal todo")
    lines.append("lists. Users register and login to receive JWT access tokens.")
    lines.append("Each user manages their own set of todos via CRUD endpoints.")
    lines.append("")
    lines.append("Endpoints:")
    lines.append("  POST /users/register — register a new user")
    lines.append("  POST /users/login — login and receive access token")
    lines.append("  GET /todos — list todos")
    lines.append("  GET /todos/{id} — get a specific todo")
    lines.append("  POST /todos — create a new todo")
    lines.append("  PUT /todos/{id} — update a todo")
    lines.append("  DELETE /todos/{id} — delete a todo")
    lines.append("")

    for area, area_reqs in areas.items():
        if not area_reqs:
            continue
        lines.append(f"## {area}")
        lines.append("")
        for rid, text in area_reqs:
            lines.append(f"- {text}")
            lines.append("")

    return "\n".join(lines)


# ========================= CODE GENERATION =========================

def generate_code(spec_text):
    """Use LLM to generate a FastAPI implementation from the specification."""
    from detect_spec_gaps import call_llm

    system_prompt = """You are an expert Python developer. Generate a complete FastAPI application
that implements the specification provided.

Requirements:
- Use FastAPI with SQLModel for the ORM
- Use JWT tokens for authentication (PyJWT library)
- Use bcrypt for password hashing (passlib library)
- Use SQLite as the database backend
- All code in a SINGLE Python file
- Include all models, routes, dependencies, and startup logic

Output ONLY the Python code, no explanations or markdown fences."""

    user_prompt = f"""Implement the following specification as a complete FastAPI application:

{spec_text}"""

    response_text, usage = call_llm(system_prompt, user_prompt, temperature=0)

    code = response_text.strip()
    if code.startswith("```"):
        code = code.split("\n", 1)[1]
    if code.endswith("```"):
        code = code[:-3].rstrip()

    return code, usage


# ========================= PROMPT ASSEMBLY =========================

def build_system_prompt(method):
    """Build the system prompt for a given detection method."""
    categories = open(os.path.join(REPO_DIR, "prompts", "categories.txt")).read()

    if method == 'zeroshot':
        prompt = open(os.path.join(REPO_DIR, "prompts", "agent_single_zeroshot.txt")).read()
        return prompt.replace("{{CATEGORIES}}", categories)

    elif method == 'oneshot-tracker':
        prompt = open(os.path.join(REPO_DIR, "prompts", "agent_single_oneshot.txt")).read()
        example = open(os.path.join(REPO_DIR, "prompts", "example_task_tracker.txt")).read()
        return prompt.replace("{{CATEGORIES}}", categories).replace("{{EXAMPLE}}", example)

    elif method == 'oneshot-warehouse':
        prompt = open(os.path.join(REPO_DIR, "prompts", "agent_single_oneshot.txt")).read()
        example = open(os.path.join(REPO_DIR, "prompts", "example_warehouse.txt")).read()
        return prompt.replace("{{CATEGORIES}}", categories).replace("{{EXAMPLE}}", example)

    elif method == 'twoshot':
        prompt = open(os.path.join(REPO_DIR, "prompts", "agent_single_twoshot.txt")).read()
        example1 = open(os.path.join(REPO_DIR, "prompts", "example_task_tracker.txt")).read()
        example2 = open(os.path.join(REPO_DIR, "prompts", "example_warehouse.txt")).read()
        return (prompt.replace("{{CATEGORIES}}", categories)
                .replace("{{EXAMPLE_1}}", example1)
                .replace("{{EXAMPLE_2}}", example2))

    else:
        raise ValueError(f"Unknown method: {method}")


# ========================= GAP DETECTION =========================

def run_detector(full_spec, generated_code, method):
    """Run the gap detector with the given method."""
    from detect_spec_gaps import call_llm

    system_prompt = build_system_prompt(method)

    user_prompt = f"""=== SPECIFICATION ===

{full_spec}

{CODEGEN_REQUIREMENTS}

=== CODE (todoapp) ===

{generated_code}

=== SERVICE TO ANALYZE ===
todoapp"""

    from detect_spec_gaps import extract_result_json
    response_text, usage = call_llm(system_prompt, user_prompt, temperature=0)

    try:
        result = extract_result_json(response_text)
    except json.JSONDecodeError as e:
        print(f"  JSON parse error: {e}")
        result = None

    return result, usage, system_prompt, user_prompt, response_text


# ========================= MAIN EXPERIMENT =========================

def run():
    import detect_spec_gaps
    detect_spec_gaps.configure_model(DETECTOR_MODEL)

    reqs = load_all_requirements()
    removal_set = set(REMOVALS)

    full_spec = build_spec(reqs)
    reduced_spec = build_spec(reqs, exclude_ids=removal_set)

    os.makedirs(BASE_OUTPUT_DIR, exist_ok=True)
    with open(os.path.join(BASE_OUTPUT_DIR, "spec_full.txt"), 'w') as f:
        f.write(full_spec)
    with open(os.path.join(BASE_OUTPUT_DIR, "spec_reduced.txt"), 'w') as f:
        f.write(reduced_spec)

    removals_doc = []
    for rid in REMOVALS:
        req = reqs[rid]
        removals_doc.append({
            'id': rid,
            'requirement': req['requirement_precise'],
            'mutant_files': list(set(m['file'] for m in req['mutants'])),
        })
    with open(os.path.join(BASE_OUTPUT_DIR, "removals.json"), 'w') as f:
        json.dump(removals_doc, f, indent=2)

    print(f"Full spec: {len(full_spec)} chars, Reduced spec: {len(reduced_spec)} chars")
    print(f"Removed requirements: {REMOVALS}")

    # Step 1: Generate code from reduced spec (shared across methods)
    code_path = os.path.join(BASE_OUTPUT_DIR, "generated_code.py")
    meta_path = os.path.join(BASE_OUTPUT_DIR, "codegen_meta.json")
    if os.path.exists(code_path):
        print(f"\nStep 1: Loading existing generated code from {code_path}")
        with open(code_path) as f:
            generated_code = f.read()
        gen_usage = None
    else:
        print("\nStep 1: Generating code from reduced spec...")
        generated_code, gen_usage = generate_code(reduced_spec)
        print(f"  Generated {len(generated_code)} chars, {gen_usage['total_tokens']} tokens")
        with open(code_path, 'w') as f:
            f.write(generated_code)
        with open(meta_path, 'w') as f:
            json.dump({
                'model': DETECTOR_MODEL,
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'usage': gen_usage,
            }, f, indent=2)

    # Step 2: Run each detection method
    for method in METHODS:
        method_dir = os.path.join(BASE_OUTPUT_DIR, DETECTOR_MODEL, method)
        os.makedirs(method_dir, exist_ok=True)

        print(f"\n{'=' * 60}")
        print(f"Step 2: Running detector [{method}] with {DETECTOR_MODEL}...")
        print(f"{'=' * 60}")

        result, detect_usage, sys_prompt, usr_prompt, raw_response = run_detector(
            full_spec, generated_code, method)

        with open(os.path.join(method_dir, "prompt.txt"), 'w') as f:
            f.write("=== SYSTEM PROMPT ===\n\n")
            f.write(sys_prompt)
            f.write("\n\n=== USER PROMPT ===\n\n")
            f.write(usr_prompt)

        if result is None:
            with open(os.path.join(method_dir, "raw_response.txt"), 'w') as f:
                f.write(raw_response)
            with open(os.path.join(method_dir, "run.log"), 'w') as f:
                f.write(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Detector:  {DETECTOR_MODEL}\n")
                f.write(f"Service:   {SERVICE}  Removals: {REMOVALS}\n")
                f.write(f"Method:    {method}\n\n")
                f.write(f"PARSE ERROR — raw response saved to raw_response.txt\n")
                f.write(f"Tokens: {detect_usage['total_tokens']}\n")
            print(f"  PARSE ERROR — raw_response.txt saved; detection_result.json NOT written")
            continue

        print(f"  Tokens: {detect_usage['total_tokens']}")
        print(f"  Additions: {len(result.get('additions', []))}")
        print(f"  Omissions: {len(result.get('omissions', []))}")

        with open(os.path.join(method_dir, "detection_result.json"), 'w') as f:
            json.dump({'result': result, 'usage': detect_usage}, f, indent=2)

        log_lines = [
            f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"Detector:  {DETECTOR_MODEL}",
            f"Service:   {SERVICE}  Removals: {REMOVALS}",
            f"Method:    {method}",
            f"",
            f"Tokens: prompt={detect_usage['prompt_tokens']}, "
            f"completion={detect_usage['completion_tokens']}, total={detect_usage['total_tokens']}",
            f"Additions: {len(result.get('additions', []))}",
            f"Omissions: {len(result.get('omissions', []))}",
            f"",
        ]
        for a in result.get('additions', []):
            log_lines.append(f"  A {a['id']}: {a['description']}")
        if result.get('additions'):
            log_lines.append("")
        for o in result.get('omissions', []):
            log_lines.append(f"  O {o['id']}: {o['description']}")
        with open(os.path.join(method_dir, "run.log"), 'w') as f:
            f.write("\n".join(log_lines) + "\n")

        print(f"\n  Additions:")
        for a in result.get('additions', []):
            print(f"    {a['id']}: {a['description'][:100]}")

        print(f"\n  Omissions:")
        for o in result.get('omissions', []):
            print(f"    {o['id']}: {o['description'][:100]}")

        summary = {
            'method': method,
            'removals': REMOVALS,
            'detector_model': DETECTOR_MODEL,
            'gen_usage': gen_usage,
            'detect_usage': detect_usage,
            'n_additions': len(result.get('additions', [])),
            'n_omissions': len(result.get('omissions', [])),
        }
        with open(os.path.join(method_dir, "summary.json"), 'w') as f:
            json.dump(summary, f, indent=2)

    print(f"\nAll results saved to {BASE_OUTPUT_DIR}")


if __name__ == "__main__":
    run()
