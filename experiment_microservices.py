"""
Spec-Reduction Experiment on custom microservice apps.

Covers three applications, each with multiple services:
  public-library: borrows, cardholders, books, logs
  nutrition:      authentication, dishes, profile, ratings
  pet-store:      registry, pet-store, pet-order

For each variant, requirements were removed from the full spec to create
a reduced spec ({variant}.txt). Code is generated from the reduced spec
with gpt-5.4 and stored under generated/{app}/{variant}/gpt-5.4/.
The detector then runs on (full.txt, generated code) with each of the
four detection methods, writing results to results/{app}/{variant}/{method}/.

Set APPS and METHODS below to control which experiments to run.
"""

import os
import json
import sys
from datetime import datetime

REPO_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, REPO_DIR)

# ========================= CONFIGURATION =========================

DETECTOR_MODEL = 'claude-sonnet-4-6'  # change to run a different detector
GEN_MODEL_DIR  = 'gpt-5.4'  # which generated code to use

# Each entry: (app, variant, service_name)
# service_name matches the .py filename under generated/{app}/{variant}/{model}/
ALL_VARIANTS = [
    ('public-library', 'borrows-R1R2R3',       'borrows'),
    ('public-library', 'cardholders-R4R5R6R7',  'cardholders'),
    ('public-library', 'books-R8R9R10R11',      'books'),
    ('public-library', 'logs-R12R13',            'logs'),
    ('nutrition',      'auth-R1R2R3',            'authentication'),
    ('nutrition',      'dishes-R4R5R6',          'dishes'),
    ('nutrition',      'profiles-R7R8R9',        'profile'),
    ('nutrition',      'ratings-R10R11R12',      'ratings'),
    ('pet-store',      'registry-R1R2R3',        'registry'),
    ('pet-store',      'petstore-R4R5R6R7',      'pet-store'),
    ('pet-store',      'petorder-R8R9R10',       'pet-order'),
]

METHODS = ['zeroshot', 'oneshot-tracker', 'oneshot-warehouse', 'twoshot']

# Filter to a subset of apps if desired, e.g. ['nutrition']
# Set to None to run all apps.
APPS = None

# ========================= CODE GENERATION =========================

def generate_code(reduced_spec, service):
    """Use LLM to generate a Flask microservice from the reduced spec."""
    from detect_spec_gaps import call_llm

    system_prompt = """You are an expert Python developer. Generate a complete Flask microservice
that implements the specification provided for the named service.

Requirements:
- Use Flask as the web framework
- Use PyMongo (flask_pymongo) for MongoDB storage
- Use the requests library for any cross-service HTTP calls
- MongoDB URI format: mongodb://mongo:27017/{service}db (replace {service} with the service name)
- All code in a SINGLE Python file
- Include all routes, models, and startup logic
- Use the deployment URLs from the specification for inter-service calls

Output ONLY the Python code, no explanations or markdown fences."""

    user_prompt = f"""Generate the {service} microservice implementing the following specification:

{reduced_spec}"""

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

def run_detector(full_spec, code_text, service, method):
    """Run the gap detector with the given method."""
    from detect_spec_gaps import call_llm

    system_prompt = build_system_prompt(method)

    user_prompt = f"""=== SPECIFICATION ===

{full_spec}

=== CODE ({service}) ===

{code_text}

=== SERVICE TO ANALYZE ===
{service}"""

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

    variants = [
        (app, variant, service)
        for app, variant, service in ALL_VARIANTS
        if APPS is None or app in APPS
    ]

    print(f"Detector model : {DETECTOR_MODEL}")
    print(f"Generated code : {GEN_MODEL_DIR}")
    print(f"Running {len(variants)} service variants × {len(METHODS)} methods "
          f"= {len(variants) * len(METHODS)} detector calls\n")

    for app, variant, service in variants:
        reduced_spec_path = os.path.join(REPO_DIR, "specs", app, f"{variant}.txt")
        full_spec_path    = os.path.join(REPO_DIR, "specs", app, "full.txt")
        code_path         = os.path.join(REPO_DIR, "generated", app, variant,
                                         GEN_MODEL_DIR, f"{service}.py")

        if not os.path.exists(reduced_spec_path):
            print(f"MISSING reduced spec: {reduced_spec_path}")
            continue
        if not os.path.exists(full_spec_path):
            print(f"MISSING full spec: {full_spec_path}")
            continue

        reduced_spec = open(reduced_spec_path).read()
        full_spec    = open(full_spec_path).read()

        print(f"\n{'=' * 60}")
        print(f"{app} / {variant} / {service}")
        print(f"{'=' * 60}")

        # Step 1: Generate code from reduced spec (cached)
        if os.path.exists(code_path):
            print(f"  Step 1: Loading existing {GEN_MODEL_DIR} code")
            code_text = open(code_path).read()
            gen_usage = None
        else:
            print(f"  Step 1: Generating code with {GEN_MODEL_DIR}...")
            code_text, gen_usage = generate_code(reduced_spec, service)
            print(f"    Generated {len(code_text)} chars, "
                  f"{gen_usage['total_tokens']} tokens")
            os.makedirs(os.path.dirname(code_path), exist_ok=True)
            with open(code_path, 'w') as f:
                f.write(code_text)

        # Step 2: Run each detection method against the full spec
        base_out = os.path.join(REPO_DIR, "results", app, variant, DETECTOR_MODEL)
        os.makedirs(base_out, exist_ok=True)

        for method in METHODS:
            method_dir = os.path.join(base_out, method)
            os.makedirs(method_dir, exist_ok=True)

            result_path = os.path.join(method_dir, "detection_result.json")
            if os.path.exists(result_path):
                print(f"  [{method}] already exists, skipping")
                continue

            print(f"  [{method}] running...")
            result, usage, sys_prompt, usr_prompt, raw_response = run_detector(
                full_spec, code_text, service, method)

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
                    f.write(f"App/Variant/Service: {app}/{variant}/{service}\n")
                    f.write(f"Method:    {method}\n\n")
                    f.write(f"PARSE ERROR — raw response saved to raw_response.txt\n")
                    f.write(f"Tokens: {usage['total_tokens']}\n")
                print(f"  [{method}] PARSE ERROR — raw_response.txt saved; will retry on next run")
                continue  # don't write detection_result.json — allows retry

            print(f"    Tokens: {usage['total_tokens']}  "
                  f"Additions: {len(result.get('additions', []))}  "
                  f"Omissions: {len(result.get('omissions', []))}")
            for a in result.get('additions', []):
                print(f"      A: {a['id']}: {a['description'][:80]}")
            for o in result.get('omissions', []):
                print(f"      O: {o['id']}: {o['description'][:80]}")

            with open(result_path, 'w') as f:
                json.dump({'result': result, 'usage': usage}, f, indent=2)

            log_lines = [
                f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                f"Detector:  {DETECTOR_MODEL}",
                f"App/Variant/Service: {app}/{variant}/{service}",
                f"Method:    {method}",
                f"",
                f"Tokens: prompt={usage['prompt_tokens']}, "
                f"completion={usage['completion_tokens']}, total={usage['total_tokens']}",
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

            summary = {
                'app': app,
                'variant': variant,
                'service': service,
                'method': method,
                'detector_model': DETECTOR_MODEL,
                'gen_model': GEN_MODEL_DIR,
                'gen_usage': gen_usage,
                'n_additions': len(result.get('additions', [])),
                'n_omissions': len(result.get('omissions', [])),
                'usage': usage,
            }
            with open(os.path.join(method_dir, "summary.json"), 'w') as f:
                json.dump(summary, f, indent=2)

    print(f"\nDone. Results saved under results/{{app}}/{{variant}}/{DETECTOR_MODEL}/{{method}}/")


if __name__ == "__main__":
    run()
