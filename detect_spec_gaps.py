# Detect spec gaps: given a partial specification and generated code, identify
# behaviors in the code that are not specified.
#
# Pipeline (sequential function calls):
#   1. Spec Analyzer  - extract specified behaviors using shared classification
#   2. Code Analyzer  - extract implemented behaviors using shared classification
#   3. Gap Detector   - identify code behaviors with no spec equivalent
#   4. Verifier       - (optional) re-check each gap against the spec
#   5. Assessor       - classify each gap: inferrable? correct?
#
# Configuration:
#   MODEL, SPEC_FILE, CODE_FILE, SERVICE_NAME, VERIFY_GAPS, OUTPUT_DIR

import os
import json
import sys
from datetime import datetime
import openai


# ========================= MODEL CONFIGURATION =========================

MODEL_CONFIGS = {
    'gpt-4.1-mini': { #confirmed
        'provider': 'azure_openai',
        'api': 'chat_completions',
        'endpoint_env': 'GPT41_URL_AZURE',
        'api_key_env': 'GPT41_API_KEY',
        'api_version': '2025-04-01-preview',
        'max_tokens': 8000,
        'supports_temperature': True,
    },
    'gpt-4o-mini': {
        'provider': 'azure_openai',
        'api': 'chat_completions',
        'endpoint_env': 'AZURE_OPENAI_ENDPOINT_4omini',
        'api_key_env': 'GPT41_API_KEY',
        'api_version': '2024-08-01-preview',
        'max_tokens': 8000,
        'supports_temperature': True,
    },
    'gpt-5.1-codex': {
        'provider': 'azure_openai',
        'api': 'responses',
        'endpoint_env': 'AZURE_OPENAI_ENDPOINT_51codex',
        'api_key_env': 'CODEX_API_KEY',
        'api_version': '2025-05-01-preview',
        'max_tokens': 16000,
        'supports_temperature': True,
    },
    'claude-sonnet-4-6': {
        'provider': 'anthropic_azure',
        'base_url': 'https://YOUR-AZURE-ANTHROPIC-ENDPOINT/anthropic',
        'api_key_env': 'GPT_EAST_US_KEY',
        'model_id': 'claude-sonnet-4-6',
        'max_tokens': 8000,
        'supports_temperature': True,
    },
    'gpt-5.4': {
        'provider': 'openai_compatible',
        'api': 'chat_completions',
        'base_url': 'https://YOUR-AZURE-OPENAI-ENDPOINT/openai/v1',
        'api_key_env': 'GPT41_API_KEY',
        'deployment_name': 'gpt-5.4',
        'max_tokens': 16000,
        'supports_temperature': True,
    },
    'gpt-4o': {
        'provider': 'azure_openai',
        'api': 'chat_completions',
        'endpoint_env': 'AZURE_GPT4O_ENDPOINT',
        'api_key_env': 'AZURE_GPT4O_API_KEY',
        'api_version': '2024-12-01-preview',
        'max_tokens': 8000,
        'supports_temperature': True,
    },
    'DeepSeek-V3-0324': {
        'provider': 'openai_compatible',
        'api': 'chat_completions',
        'base_url': 'https://YOUR-AZURE-OPENAI-ENDPOINT/openai/v1',
        'api_key_env': 'GPT41_API_KEY',
        'deployment_name': 'DeepSeek-V3-0324',
        'max_tokens': 8000,
        'supports_temperature': True,
    },
    'DeepSeek-V4-Flash': {
        'provider': 'azure_inference',
        'endpoint_env': 'AZURE_DEEPSEEK_ENDPOINT',
        'api_key_env': 'AZURE_DEEPSEEK_API_KEY',
        'deployment_name': 'DeepSeek-V4-Flash',
        'max_tokens': 8000,
        'supports_temperature': True,
    },
    'DeepSeek-V4-Pro': {
        'provider': 'azure_inference',
        'endpoint_env': 'AZURE_DEEPSEEK_ENDPOINT',
        'api_key_env': 'AZURE_DEEPSEEK_API_KEY',
        'deployment_name': 'DeepSeek-V4-Pro',
        'max_tokens': 8000,
        'supports_temperature': True,
    },
}

# ========================= EXPERIMENT SETTINGS =========================

MODEL = 'gpt-5.4'  # this can be changed by call to configure_model
SERVICE_NAME = 'ratings'
VERIFY_GAPS = True

REPO_DIR = os.path.dirname(os.path.abspath(__file__)) + "/"
APP_NAME = 'nutrition'
SPEC_VARIANT = 'ratings-R10R11R12'
GEN_MODEL = 'gpt-4.1-mini'

SPEC_FILE = REPO_DIR + f"specs/{APP_NAME}/{SPEC_VARIANT}.txt"
CODE_FILE = REPO_DIR + f"generated/{APP_NAME}/{SPEC_VARIANT}/{GEN_MODEL}/{SERVICE_NAME}.py"
OUTPUT_DIR = REPO_DIR + f"results/{APP_NAME}/{SPEC_VARIANT}/"

# ========================= SHARED ONTOLOGY =========================

ONTOLOGY = """Categories (use exactly these names):

1. ENDPOINTS: Route definitions, HTTP methods supported, URL patterns.
2. REQUEST_VALIDATION: Required fields, type checking, media type validation,
   missing/invalid parameter handling.
3. RESPONSE_FORMAT: Returned JSON fields, status codes for success and error cases,
   response structure.
4. BUSINESS_LOGIC: Domain rules, guards, constraints, conditional behavior,
   access control decisions, state transitions.
5. COMPUTED_VALUES: Derived or calculated fields, formulas, date arithmetic,
   aggregations (e.g., totalPrice = unitPrice * quantity).
6. CROSS_SERVICE: Outbound HTTP calls to other microservices, data fetched from
   or sent to other services, notifications.
7. DATA_PERSISTENCE: What is stored in the database, field mappings between
   request/response and stored documents, ID generation.

Each item should be tagged with:
- primary_category: one of the above
- secondary_category: one of the above, or null if none applies"""

# ========================= LLM CLIENT SETUP =========================

config = MODEL_CONFIGS[MODEL]

if config['provider'] == 'azure_openai':
    from openai import AzureOpenAI
    api_key = os.getenv(config['api_key_env'])
    endpoint = os.getenv(config['endpoint_env'])
    if not api_key or not endpoint:
        print(f"Missing env vars: {config['api_key_env']} and/or {config['endpoint_env']}")
        sys.exit(1)
    client = AzureOpenAI(
        api_key=api_key,
        api_version=config['api_version'],
        azure_endpoint=endpoint,
    )
elif config['provider'] == 'openai_compatible':
    from openai import OpenAI
    api_key = os.getenv(config['api_key_env'])
    if not api_key:
        print(f"Missing env var: {config['api_key_env']}")
        sys.exit(1)
    _oc_kwargs = {'base_url': config['base_url'], 'api_key': api_key}
    if 'api_version' in config:
        _oc_kwargs['default_query'] = {'api-version': config['api_version']}
    client = OpenAI(**_oc_kwargs)
elif config['provider'] == 'anthropic_azure':
    api_key = os.getenv(config['api_key_env'])
    if not api_key:
        print(f"Missing env var: {config['api_key_env']}")
        sys.exit(1)
    client = None  # uses requests directly in call_llm
elif config['provider'] == 'azure_inference':
    from azure.ai.inference import ChatCompletionsClient
    from azure.core.credentials import AzureKeyCredential
    api_key = os.getenv(config['api_key_env'])
    endpoint = os.getenv(config['endpoint_env'])
    if not api_key or not endpoint:
        print(f"Missing env vars: {config['api_key_env']} and/or {config['endpoint_env']}")
        sys.exit(1)
    client = ChatCompletionsClient(endpoint=endpoint, credential=AzureKeyCredential(api_key))


def configure_model(model_name):
    """Switch the active model and client without reimporting the module."""
    global MODEL, config, client
    if model_name not in MODEL_CONFIGS:
        raise ValueError(f"Unknown model: {model_name}. Available: {list(MODEL_CONFIGS.keys())}")
    MODEL = model_name
    config = MODEL_CONFIGS[MODEL]

    if config['provider'] == 'azure_openai':
        from openai import AzureOpenAI
        api_key = os.getenv(config['api_key_env'])
        endpoint = os.getenv(config['endpoint_env'])
        if not api_key or not endpoint:
            raise EnvironmentError(f"Missing env vars: {config['api_key_env']} and/or {config['endpoint_env']}")
        client = AzureOpenAI(api_key=api_key, api_version=config['api_version'], azure_endpoint=endpoint)
    elif config['provider'] == 'openai_compatible':
        from openai import OpenAI
        api_key = os.getenv(config['api_key_env'])
        if not api_key:
            raise EnvironmentError(f"Missing env var: {config['api_key_env']}")
        _oc_kwargs = {'base_url': config['base_url'], 'api_key': api_key}
        if 'api_version' in config:
            _oc_kwargs['default_query'] = {'api-version': config['api_version']}
        client = OpenAI(**_oc_kwargs)
    elif config['provider'] == 'anthropic_azure':
        api_key = os.getenv(config['api_key_env'])
        if not api_key:
            raise EnvironmentError(f"Missing env var: {config['api_key_env']}")
        client = None  # uses requests directly in call_llm
    elif config['provider'] == 'azure_inference':
        from azure.ai.inference import ChatCompletionsClient
        from azure.core.credentials import AzureKeyCredential
        api_key = os.getenv(config['api_key_env'])
        endpoint = os.getenv(config['endpoint_env'])
        if not api_key or not endpoint:
            raise EnvironmentError(f"Missing env vars: {config['api_key_env']} and/or {config['endpoint_env']}")
        client = ChatCompletionsClient(endpoint=endpoint, credential=AzureKeyCredential(api_key))
    else:
        raise ValueError(f"Unknown provider: {config['provider']}")
    print(f"Configured model: {MODEL} ({config['provider']})")


def call_llm(system_prompt, user_prompt, temperature=0):
    """Unified LLM call. Returns (response_text, usage_dict)."""

    if config['provider'] == 'azure_openai' and config['api'] == 'chat_completions':
        kwargs = {
            'model': MODEL,
            'messages': [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            'max_tokens': config['max_tokens'],
            'n': 1,
        }
        if config['supports_temperature']:
            kwargs['temperature'] = temperature
        response = client.chat.completions.create(**kwargs)
        usage = {
            'total_tokens': response.usage.total_tokens,
            'prompt_tokens': response.usage.prompt_tokens,
            'completion_tokens': response.usage.completion_tokens,
        }
        return response.choices[0].message.content, usage

    elif config['provider'] == 'openai_compatible' and config['api'] == 'chat_completions':
        model_name = config.get('deployment_name', MODEL)
        max_tokens_key = config.get('max_tokens_param', 'max_completion_tokens')
        kwargs = {
            'model': model_name,
            'messages': [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            'extra_body': {max_tokens_key: config['max_tokens']},
        }
        if config.get('supports_temperature'):
            kwargs['temperature'] = temperature
        response = client.chat.completions.create(**kwargs)
        usage = {
            'total_tokens': response.usage.total_tokens,
            'prompt_tokens': response.usage.prompt_tokens,
            'completion_tokens': response.usage.completion_tokens,
        }
        return response.choices[0].message.content, usage

    elif config['provider'] == 'azure_openai' and config['api'] == 'responses':
        # Azure OpenAI Responses API (gpt-5.1-codex, gpt-5.2-codex)
        kwargs = {
            'model': MODEL,
            'input': [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        if config['supports_temperature']:
            kwargs['temperature'] = temperature
        if config['max_tokens']:
            kwargs['max_output_tokens'] = config['max_tokens']
        response = client.responses.create(**kwargs)
        usage = {
            'total_tokens': getattr(response.usage, 'total_tokens', 0),
            'prompt_tokens': getattr(response.usage, 'input_tokens', 0),
            'completion_tokens': getattr(response.usage, 'output_tokens', 0),
        }
        return response.output_text, usage

    elif config['provider'] == 'anthropic_azure':
        import requests as _requests
        api_key = os.getenv(config['api_key_env'])
        url = config['base_url'].rstrip('/') + '/v1/messages'
        body = {
            'model': config['model_id'],
            'max_tokens': config['max_tokens'],
            'system': system_prompt,
            'messages': [{'role': 'user', 'content': user_prompt}],
        }
        if config.get('supports_temperature'):
            body['temperature'] = temperature
        resp = _requests.post(url, json=body, headers={
            'x-api-key': api_key,
            'anthropic-version': '2023-06-01',
            'content-type': 'application/json',
        })
        resp.raise_for_status()
        data = resp.json()
        usage = {
            'total_tokens': data['usage']['input_tokens'] + data['usage']['output_tokens'],
            'prompt_tokens': data['usage']['input_tokens'],
            'completion_tokens': data['usage']['output_tokens'],
        }
        return data['content'][0]['text'], usage

    elif config['provider'] == 'azure_inference':
        from azure.ai.inference.models import SystemMessage, UserMessage
        model_name = config.get('deployment_name', MODEL)
        kwargs = {
            'model': model_name,
            'messages': [
                SystemMessage(content=system_prompt),
                UserMessage(content=user_prompt),
            ],
            'max_tokens': config['max_tokens'],
        }
        if config.get('supports_temperature'):
            kwargs['temperature'] = temperature
        response = client.complete(**kwargs)
        usage = {
            'total_tokens': response.usage.total_tokens,
            'prompt_tokens': response.usage.prompt_tokens,
            'completion_tokens': response.usage.completion_tokens,
        }
        return response.choices[0].message.content, usage

    else:
        raise ValueError(f"Unsupported provider/api: {config['provider']}/{config['api']}")


# ========================= AGENT PROMPTS =========================

SPEC_ANALYZER_SYSTEM = f"""You are an expert at analyzing microservice specifications.

You will receive the specification for a multi-service application and the name of
one service to analyze.

Your task is to extract every individual requirement for that service from the
specification. A "requirement" is any specific demand the specification makes —
an endpoint it defines, a validation it expects, a status code it prescribes,
a computation it describes, a cross-service call it mandates, or a data model
field it declares.

{ONTOLOGY}

Output a JSON array of requirement objects. Each object has:
- "id": a short identifier like "S1", "S2", ...
- "description": concise description of the requirement
- "primary_category": one of the category names above
- "secondary_category": one of the category names above, or null
- "spec_excerpt": the relevant phrase or sentence from the specification

Be thorough: split compound specification statements into separate requirements.
For example, "POST /items requires fields name, price, and category" contains at
least two requirements (the endpoint definition and the required fields).

Output ONLY valid JSON, no other text."""

CODE_ANALYZER_SYSTEM = f"""You are an expert at analyzing Python microservice implementations.

You will receive the code for one microservice.

Your task is to extract every individual behavior implemented in the code.
A "behavior" is any observable action the code performs — an endpoint it handles,
a validation it enforces, a status code it returns, a computation it performs,
a cross-service call it makes, or a field it stores.

{ONTOLOGY}

Output a JSON array of behavior objects. Each object has:
- "id": a short identifier like "C1", "C2", ...
- "description": concise description of the behavior
- "primary_category": one of the category names above
- "secondary_category": one of the category names above, or null
- "code_reference": the relevant function/line or brief code snippet

Be thorough: split compound behaviors into separate items. For example, if a
single function validates input, calls an external service, computes a value,
and stores a result, each of those is a separate behavior. Do not bundle
multiple distinct actions into one item.

Output ONLY valid JSON, no other text."""

CODE_BEHAVIOR_VERIFIER_SYSTEM = """You are an expert at reviewing code analysis for completeness.

You will receive:
1. The code for a microservice
2. A list of behaviors that were previously extracted from this code

Your task: verify that the behavior list is COMPLETE. Read through the code
carefully and identify any behaviors that are implemented in the code but
MISSING from the list.

A "behavior" is any observable action the code performs:
- Endpoints it handles and HTTP methods it supports
- Validations it enforces (required fields, type checks, format checks,
  range checks, media type checks)
- Status codes it returns and under what conditions
- Computations it performs (formulas, date arithmetic, aggregations)
- Cross-service calls it makes (outbound HTTP requests to other services)
- Data it stores, including specific field mappings and ID generation
- Business rules it enforces (guards, constraints, conditional logic)
- Startup/initialization logic (seeding data, creating indexes)
- Security-related behavior (password hashing, anti-enumeration patterns,
  authentication checks)

Pay special attention to behaviors that are easy to overlook:
- Behaviors bundled inside larger functions (e.g., a function that validates
  input AND calls an external service AND stores a result contains at least
  three separate behaviors)
- Specific status codes returned for specific error conditions
- WHERE data comes from (e.g., user_id extracted from a token vs. from the
  request body)
- Startup or initialization code that runs before request handling begins
- Security design decisions (e.g., returning the same error for "not found"
  and "wrong password" to prevent enumeration)
- Query parameter handling and filtering logic

Output a JSON object with:
- "missing_behaviors": array of {"id": "M1", "description": "...", "primary_category": "...", "code_reference": "..."} for behaviors found in the code but absent from the list
- "bundled_behaviors": array of {"existing_id": "C3", "should_split": "...", "reason": "..."} for list items that bundle multiple distinct behaviors and should be split

If the list is complete, output: {"missing_behaviors": [], "bundled_behaviors": []}

Output ONLY valid JSON, no other text."""

GAP_DETECTOR_SYSTEM = """You are an expert at comparing microservice specifications with implementations.

You will receive two lists:
1. SPEC_REQUIREMENTS: requirements extracted from the specification
2. CODE_BEHAVIORS: behaviors extracted from the code

Your task: for each CODE BEHAVIOR, determine if there is a corresponding SPEC
REQUIREMENT that EXPLICITLY REQUIRES it. If a code behavior has no spec
requirement that explicitly requires it, it is a "gap" — the code does something
the specification never asked for.

IMPORTANT — be STRICT about what counts as a match:
- A match requires the specification to explicitly state or directly require
  the behavior.
- A vague spec requirement does NOT match a specific code behavior. For example,
  "return appropriate status codes" does NOT cover "return 401 when the user
  is not found." The specification must explicitly state the specific condition
  and the specific behavior for it to count as a match.
- The specification not contradicting a behavior is NOT enough. The specification
  must positively require it. For example, if the specification says "store user
  records" and the code encrypts passwords before storing, encryption is a gap —
  the specification permits it but does not ask for it.
- If the code adds a constraint, validation, cross-service call, or computation
  that the specification does not explicitly require, it IS a gap — even if it
  seems like good practice.
- Minor implementation details (variable naming, error message text, code
  structure) are NOT gaps.

Output a JSON object with:
- "matched": array of {"code_id": "C1", "spec_id": "S3", "explanation": "..."} for matched pairs
- "gaps": array of {"code_id": "C5", "description": "...", "primary_category": "...", "secondary_category": "..." or null, "reasoning": "why no spec requirement covers this behavior"} for unmatched code behaviors

Output ONLY valid JSON, no other text."""

VERIFIER_SYSTEM = """You are a careful specification analyst performing a verification pass.

You will receive the original specification and a list of suspected gaps — code
behaviors that were identified as having no matching spec requirement.

For each suspected gap, re-read the specification very carefully and determine
if the behavior really IS absent from the specification. Consider:
- Could it be required using different terminology?
- Could it be implied by another requirement?
- Could it be a consequence of a stated requirement?
- Is it part of the general guidelines that apply to all services?

For each gap, output your verdict:
- "confirmed": true if the behavior is genuinely not required by the specification
- "confirmed": false if you found a spec requirement that does cover it (explain where)

Output a JSON array of objects:
- "code_id": the code behavior id
- "confirmed": true or false
- "explanation": why you confirmed or rejected this gap

Output ONLY valid JSON, no other text."""

ASSESSOR_SYSTEM = """You are an expert at classifying gaps between specifications and generated code.

You will receive a list of confirmed gaps — code behaviors that have no matching
requirement in the specification.

For each confirmed gap, assess:

1. INFERRABILITY: Could a developer (or LLM) reasonably infer this behavior
   even though the specification does not require it?
   - "highly_inferrable": standard practice, common convention, or strongly implied
     by domain knowledge
   - "partially_inferrable": hints exist in other parts of the specification or
     related services
   - "not_inferrable": arbitrary design decision with no basis in the specification

2. CORRECTNESS: Assuming a full, unmodified specification exists, would this
   behavior be correct?
   - "likely_correct": aligns with standard practices for this domain
   - "uncertain": could go either way
   - "likely_incorrect": unusual or problematic choice

3. IMPACT: What is the functional impact?
   - "high": affects core business logic or data correctness
   - "medium": affects behavior but not core functionality
   - "low": cosmetic or minor implementation detail

Output a JSON array of objects:
- "code_id": the code behavior id
- "description": brief description
- "primary_category": category from the ontology
- "inferrability": one of the three levels above
- "correctness": one of the three levels above
- "impact": one of the three levels above
- "reasoning": brief explanation of your assessment

Output ONLY valid JSON, no other text."""

OMISSION_DETECTOR_SYSTEM = f"""You are an expert at identifying missing behaviors in microservice implementations.

You will receive:
1. The full specification for a multi-service application
2. The code for one specific service
3. The name of the service to analyze

Your task: identify behaviors that are MISSING from the code but that a correct
implementation would likely need. Compare the specification directly against the
code — do not rely on any intermediate summaries.

{ONTOLOGY}

Sources of expected-but-missing behavior:
a) EXPLICIT REQUIREMENTS: A requirement is stated clearly in the specification
   but the code simply does not implement it. This includes requirements that
   appear in unexpected locations — in another service's section, in general
   guidelines, or in preamble text that applies to all services. Read the
   entire specification, not just the section for this service.
b) CROSS-SERVICE HINTS: Other services' descriptions may reference interactions
   with this service (e.g., "service A notifies service B" implies B should
   receive notifications, or A should send them).
c) DATA MODEL IMPLICATIONS: Fields defined in the specification that are never
   computed, populated, or used in the code (e.g., a total_price field that
   exists in the data model but is never calculated).
d) DOMAIN KNOWLEDGE: Standard practices for this type of application that a
   developer would typically implement (e.g., in a reservation system,
   preventing double-booking of the same resource).
e) SPEC IMPLICATIONS: Requirements that are implied by the combination of
   multiple specification statements, even if no single statement directly
   requires them.

IMPORTANT:
- Only flag behaviors that have a reasonable basis — either from the specification,
  from cross-service hints, or from strong domain conventions.
- Do NOT flag the absence of features that are purely speculative.
- Focus on FUNCTIONAL omissions: missing business logic, missing computations,
  missing cross-service calls, missing input validations, missing or incorrect
  error status codes, and missing constraints. Do not flag code quality issues
  like naming or structure.

Output a JSON array of omission objects. Each object has:
- "id": a short identifier like "O1", "O2", ...
- "description": what behavior is missing from the code
- "primary_category": one of the category names above
- "secondary_category": one of the category names above, or null
- "source": one of "explicit_requirement", "cross_service_hint",
  "data_model_implication", "domain_knowledge", or "spec_implication"
- "evidence": the specific specification text, field name, or domain convention
  that suggests this behavior should exist

Output ONLY valid JSON, no other text."""

OMISSION_VERIFIER_SYSTEM = """You are a careful analyst verifying suspected omissions in microservice code.

You will receive the code and a list of suspected omissions — behaviors that
the code is expected to implement but appears to be missing.

For each suspected omission, examine the code carefully and determine:
1. Is this behavior truly absent from the code? (It might be implemented
   differently than expected, or under a different function name.)
2. Is the evidence for expecting this behavior strong enough? (Is it really
   required by the specification or domain, or is it speculative?)

For each omission, output your verdict:
- "confirmed": true if the behavior is genuinely missing AND there is reasonable
  evidence it should be there
- "confirmed": false if the behavior exists in some form, or the evidence is too weak

Output a JSON array of objects:
- "omission_id": the omission id
- "confirmed": true or false
- "explanation": why you confirmed or rejected this omission

Output ONLY valid JSON, no other text."""

OMISSION_ASSESSOR_SYSTEM = """You are an expert at classifying missing behaviors in generated microservice code.

You will receive a list of confirmed omissions — behaviors the code should
implement but doesn't.

For each confirmed omission, assess:

1. INFERRABILITY: How strong is the signal that this behavior should exist?
   - "highly_inferrable": explicitly stated in the specification for this or
     another service, or a field exists in the data model that clearly needs
     computation
   - "partially_inferrable": hinted at by domain knowledge or indirect
     specification references
   - "not_inferrable": only a domain expert would know this should exist;
     no specification signal at all

2. IMPACT: What is the functional impact of this omission?
   - "high": core business logic missing, data correctness affected, or
     cross-service contract broken
   - "medium": secondary functionality missing
   - "low": minor convenience feature missing

Output a JSON array of objects:
- "omission_id": the omission id
- "description": brief description of the missing behavior
- "primary_category": category from the ontology
- "source": the evidence source
- "inferrability": one of the three levels above
- "impact": one of the three levels above
- "reasoning": brief explanation of your assessment

Output ONLY valid JSON, no other text."""

# ========================= PIPELINE FUNCTIONS =========================

def extract_json(text):
    """Extract JSON from LLM response, handling markdown code blocks."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        start = 1
        end = len(lines) - 1
        if lines[0].startswith("```json"):
            start = 1
        for i in range(len(lines) - 1, 0, -1):
            if lines[i].strip() == "```":
                end = i
                break
        text = "\n".join(lines[start:end])
    return json.loads(text)


def extract_result_json(text):
    """Parse JSON from a detector response with fallback strategies.

    Handles: markdown code fences (including multiple blocks — tries last first),
    preamble/postamble text, bracket-boundary extraction.
    Raises JSONDecodeError if all strategies fail.
    """
    text = text.strip()

    # Extract all fenced code blocks and try them last-to-first (model may
    # self-correct by appending a revised block after an initial draft).
    import re
    fence_blocks = re.findall(r'```[^\n]*\n(.*?)```', text, re.DOTALL)
    for block in reversed(fence_blocks):
        block = block.strip()
        try:
            return json.loads(block)
        except json.JSONDecodeError:
            pass

    # Try the raw text directly (no fences)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Fallback: find outermost { } or [ ] (handles preamble/postamble text)
    for open_ch, close_ch in [('{', '}'), ('[', ']')]:
        start = text.find(open_ch)
        end = text.rfind(close_ch)
        if start != -1 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                pass
    raise json.JSONDecodeError("No valid JSON found in response", text, 0)


def run_agent(agent_name, system_prompt, user_prompt):
    """Run a single agent, return parsed JSON and usage."""
    print(f"\n{'='*60}")
    print(f"Running {agent_name}...")
    print(f"{'='*60}")

    response_text, usage = call_llm(system_prompt, user_prompt)

    print(f"  Tokens: prompt={usage['prompt_tokens']}, "
          f"completion={usage['completion_tokens']}, "
          f"total={usage['total_tokens']}")

    try:
        parsed = extract_json(response_text)
    except json.JSONDecodeError as e:
        print(f"  WARNING: Failed to parse JSON from {agent_name}: {e}")
        err_file = f"{OUTPUT_DIR}_parse_error_{agent_name.replace(' ', '_')}.txt"
        os.makedirs(os.path.dirname(err_file), exist_ok=True)
        with open(err_file, "w") as f:
            f.write(response_text)
        print(f"  Raw response saved to: {err_file}")
        parsed = None

    return parsed, response_text, usage


def agent_spec_analyzer(spec_text, service_name):
    user_prompt = (
        f"Analyze the following specification and extract ALL requirements "
        f"for the **{service_name}** service. Include requirements from the "
        f"service-specific section AND from general guidelines that apply to all services.\n\n"
        f"SPECIFICATION:\n{spec_text}"
    )
    return run_agent("Spec Analyzer", SPEC_ANALYZER_SYSTEM, user_prompt)


def agent_code_analyzer(code_text, service_name):
    user_prompt = (
        f"Analyze the following Python implementation of the **{service_name}** "
        f"microservice and extract ALL implemented behaviors.\n\n"
        f"CODE:\n{code_text}"
    )
    return run_agent("Code Analyzer", CODE_ANALYZER_SYSTEM, user_prompt)


def agent_code_behavior_verifier(code_text, code_behaviors_json):
    user_prompt = (
        f"Review the following code and behavior list for completeness. "
        f"Identify any behaviors in the code that are MISSING from the list.\n\n"
        f"CODE:\n{code_text}\n\n"
        f"EXTRACTED BEHAVIORS:\n{json.dumps(code_behaviors_json, indent=2)}"
    )
    return run_agent("Code Behavior Verifier", CODE_BEHAVIOR_VERIFIER_SYSTEM, user_prompt)


def agent_gap_detector(spec_behaviors_json, code_behaviors_json):
    user_prompt = (
        f"Compare these two lists and identify gaps.\n\n"
        f"SPEC_REQUIREMENTS:\n{json.dumps(spec_behaviors_json, indent=2)}\n\n"
        f"CODE_BEHAVIORS:\n{json.dumps(code_behaviors_json, indent=2)}"
    )
    return run_agent("Gap Detector", GAP_DETECTOR_SYSTEM, user_prompt)


def agent_verifier(spec_text, gaps_json):
    user_prompt = (
        f"Verify each of the following suspected spec gaps against the specification.\n\n"
        f"SPECIFICATION:\n{spec_text}\n\n"
        f"SUSPECTED GAPS:\n{json.dumps(gaps_json, indent=2)}"
    )
    return run_agent("Verifier", VERIFIER_SYSTEM, user_prompt)


def agent_assessor(confirmed_gaps_json):
    user_prompt = (
        f"Assess each of the following confirmed spec gaps.\n\n"
        f"CONFIRMED GAPS:\n{json.dumps(confirmed_gaps_json, indent=2)}"
    )
    return run_agent("Assessor", ASSESSOR_SYSTEM, user_prompt)


def agent_omission_detector(spec_text, code_text, service_name):
    user_prompt = (
        f"Examine the following specification and code for the **{service_name}** "
        f"microservice. Identify behaviors that are MISSING from the code but that "
        f"a correct implementation would likely need.\n\n"
        f"Pay special attention to:\n"
        f"- Other services' descriptions that reference {service_name}\n"
        f"- Fields in the data model that are defined but never computed\n"
        f"- Domain-standard behaviors for this type of application\n\n"
        f"FULL SPECIFICATION (all services):\n{spec_text}\n\n"
        f"CODE ({service_name} service):\n{code_text}"
    )
    return run_agent("Omission Detector", OMISSION_DETECTOR_SYSTEM, user_prompt)


def agent_omission_verifier(code_text, omissions_json):
    user_prompt = (
        f"Verify each suspected omission against the actual code.\n\n"
        f"CODE:\n{code_text}\n\n"
        f"SUSPECTED OMISSIONS:\n{json.dumps(omissions_json, indent=2)}"
    )
    return run_agent("Omission Verifier", OMISSION_VERIFIER_SYSTEM, user_prompt)


def agent_omission_assessor(confirmed_omissions_json):
    user_prompt = (
        f"Assess each of the following confirmed omissions.\n\n"
        f"CONFIRMED OMISSIONS:\n{json.dumps(confirmed_omissions_json, indent=2)}"
    )
    return run_agent("Omission Assessor", OMISSION_ASSESSOR_SYSTEM, user_prompt)


# ========================= MAIN PIPELINE =========================

def run_pipeline():
    # Load inputs
    with open(SPEC_FILE) as f:
        spec_text = f.read()
    with open(CODE_FILE) as f:
        code_text = f.read()

    # Create output directory: results/{app}/{spec-variant}/{detect-model}/
    d = datetime.now()
    run_dir = f"{OUTPUT_DIR}{MODEL}/"
    os.makedirs(run_dir, exist_ok=True)

    all_usage = []

    # Write run metadata
    with open(run_dir + "meta_data.txt", "w") as f:
        f.write(f"Timestamp: {d.strftime('%d-%m-%Y %H:%M:%S')}\n")
        f.write(f"Detect model: {MODEL}\n")
        f.write(f"Gen model: {GEN_MODEL}\n")
        f.write(f"Provider: {config['provider']}/{config['api']}\n")
        f.write(f"Service: {SERVICE_NAME}\n")
        f.write(f"Spec file: {SPEC_FILE}\n")
        f.write(f"Code file: {CODE_FILE}\n")
        f.write(f"Verify gaps: {VERIFY_GAPS}\n\n")

    # --- Agent 1: Spec Analyzer ---
    spec_behaviors, spec_raw, spec_usage = agent_spec_analyzer(spec_text, SERVICE_NAME)
    all_usage.append(("Spec Analyzer", spec_usage))
    with open(run_dir + "1_spec_behaviors.json", "w") as f:
        json.dump(spec_behaviors, f, indent=2)

    if spec_behaviors is None:
        print("ERROR: Spec Analyzer failed to produce valid JSON. Aborting.")
        return

    print(f"  Found {len(spec_behaviors)} spec behaviors.")

    # --- Agent 2: Code Analyzer ---
    code_behaviors, code_raw, code_usage = agent_code_analyzer(code_text, SERVICE_NAME)
    all_usage.append(("Code Analyzer", code_usage))
    with open(run_dir + "2_code_behaviors.json", "w") as f:
        json.dump(code_behaviors, f, indent=2)

    if code_behaviors is None:
        print("ERROR: Code Analyzer failed to produce valid JSON. Aborting.")
        return

    print(f"  Found {len(code_behaviors)} code behaviors.")

    # --- Agent 2b: Code Behavior Verifier ---
    verifier_result, verifier_raw, verifier_usage = agent_code_behavior_verifier(
        code_text, code_behaviors)
    all_usage.append(("Code Behavior Verifier", verifier_usage))
    with open(run_dir + "2b_code_behavior_verification.json", "w") as f:
        json.dump(verifier_result, f, indent=2)

    if verifier_result is not None:
        missing = verifier_result.get("missing_behaviors", [])
        bundled = verifier_result.get("bundled_behaviors", [])
        if missing:
            max_id = max(int(b["id"][1:]) for b in code_behaviors)
            for m in missing:
                max_id += 1
                code_behaviors.append({
                    "id": f"C{max_id}",
                    "description": m["description"],
                    "primary_category": m.get("primary_category", ""),
                    "secondary_category": None,
                    "code_reference": m.get("code_reference", ""),
                })
            print(f"  Verifier found {len(missing)} missing behaviors (added to list).")
        if bundled:
            print(f"  Verifier flagged {len(bundled)} bundled behaviors for splitting.")
        if not missing and not bundled:
            print(f"  Verifier confirmed behavior list is complete.")
    else:
        print("  WARNING: Code Behavior Verifier failed to parse. Proceeding with original list.")

    # --- Agent 3: Gap Detector ---
    gap_result, gap_raw, gap_usage = agent_gap_detector(spec_behaviors, code_behaviors)
    all_usage.append(("Gap Detector", gap_usage))
    with open(run_dir + "3_gap_detection.json", "w") as f:
        json.dump(gap_result, f, indent=2)

    if gap_result is None:
        print("ERROR: Gap Detector failed to produce valid JSON. Aborting.")
        return

    gaps = gap_result.get("gaps", [])
    matched = gap_result.get("matched", [])
    print(f"  Matched: {len(matched)} behaviors.  Gaps found: {len(gaps)}")

    # --- Agents 4-5: Verify and assess additions (only if gaps found) ---
    verify_result = None
    assessment = None
    verified_gaps = gaps

    if len(gaps) > 0:
        # --- Agent 4: Verifier (optional) ---
        if VERIFY_GAPS:
            verify_result, verify_raw, verify_usage = agent_verifier(spec_text, gaps)
            all_usage.append(("Verifier", verify_usage))
            with open(run_dir + "4_verification.json", "w") as f:
                json.dump(verify_result, f, indent=2)

            if verify_result is None:
                print("WARNING: Verifier failed to parse. Proceeding with all gaps.")
            else:
                confirmed_ids = {v["code_id"] for v in verify_result if v.get("confirmed", True)}
                rejected = [v for v in verify_result if not v.get("confirmed", True)]
                verified_gaps = [g for g in gaps if g["code_id"] in confirmed_ids]
                print(f"  Verified: {len(verified_gaps)} confirmed, {len(rejected)} rejected.")
                if rejected:
                    for r in rejected:
                        print(f"    Rejected {r['code_id']}: {r.get('explanation', '')[:80]}")
        else:
            print("  Skipping verification step (VERIFY_GAPS=False).")

        # --- Agent 5: Assessor ---
        if len(verified_gaps) > 0:
            assessment, assess_raw, assess_usage = agent_assessor(verified_gaps)
            all_usage.append(("Assessor", assess_usage))
            with open(run_dir + "5_assessment.json", "w") as f:
                json.dump(assessment, f, indent=2)

            if assessment:
                print(f"\n{'='*60}")
                print("ADDITION ASSESSMENT RESULTS")
                print(f"{'='*60}")
                for a in assessment:
                    print(f"  [{a.get('code_id')}] {a.get('description', '')[:60]}")
                    print(f"    Category: {a.get('primary_category')}")
                    print(f"    Inferrability: {a.get('inferrability')}")
                    print(f"    Correctness: {a.get('correctness')}")
                    print(f"    Impact: {a.get('impact')}")
                    print()
    else:
        print("\nNo unspecified additions detected.")

    # --- Agent 6: Omission Detector ---
    omissions, omission_raw, omission_usage = agent_omission_detector(
        spec_text, code_text, SERVICE_NAME)
    all_usage.append(("Omission Detector", omission_usage))
    with open(run_dir + "6_omissions.json", "w") as f:
        json.dump(omissions, f, indent=2)

    if omissions is None:
        print("WARNING: Omission Detector failed to produce valid JSON.")
        omissions = []

    print(f"  Found {len(omissions)} suspected omissions.")

    # --- Agent 7: Omission Verifier ---
    verified_omissions = omissions
    if VERIFY_GAPS and len(omissions) > 0:
        om_verify_result, om_verify_raw, om_verify_usage = agent_omission_verifier(
            code_text, omissions)
        all_usage.append(("Omission Verifier", om_verify_usage))
        with open(run_dir + "7_omission_verification.json", "w") as f:
            json.dump(om_verify_result, f, indent=2)

        if om_verify_result is None:
            print("WARNING: Omission Verifier failed to parse. Proceeding with all omissions.")
        else:
            confirmed_ids = {v["omission_id"] for v in om_verify_result if v.get("confirmed", True)}
            rejected = [v for v in om_verify_result if not v.get("confirmed", True)]
            verified_omissions = [o for o in omissions if o["id"] in confirmed_ids]
            print(f"  Verified: {len(verified_omissions)} confirmed, {len(rejected)} rejected.")
            if rejected:
                for r in rejected:
                    print(f"    Rejected {r['omission_id']}: {r.get('explanation', '')[:80]}")

    # --- Agent 8: Omission Assessor ---
    omission_assessment = None
    if len(verified_omissions) > 0:
        omission_assessment, om_assess_raw, om_assess_usage = agent_omission_assessor(
            verified_omissions)
        all_usage.append(("Omission Assessor", om_assess_usage))
        with open(run_dir + "8_omission_assessment.json", "w") as f:
            json.dump(omission_assessment, f, indent=2)

        if omission_assessment:
            print(f"\n{'='*60}")
            print("OMISSION ASSESSMENT RESULTS")
            print(f"{'='*60}")
            for a in omission_assessment:
                print(f"  [{a.get('omission_id')}] {a.get('description', '')[:60]}")
                print(f"    Category: {a.get('primary_category')}")
                print(f"    Source: {a.get('source')}")
                print(f"    Inferrability: {a.get('inferrability')}")
                print(f"    Impact: {a.get('impact')}")
                print()
    else:
        print("\nNo confirmed omissions.")

    write_summary(run_dir, all_usage, spec_behaviors, code_behaviors, gap_result,
                  verify_result if VERIFY_GAPS else None, assessment,
                  omission_assessment)


def write_summary(run_dir, all_usage, spec_behaviors, code_behaviors, gap_result,
                  verify_result, assessment, omission_assessment=None):
    """Write a human-readable summary file."""
    with open(run_dir + "summary.txt", "w") as f:
        f.write(f"Spec Gap Detection Summary\n")
        f.write(f"{'='*60}\n")
        f.write(f"Model: {MODEL}\n")
        f.write(f"Service: {SERVICE_NAME}\n")
        f.write(f"Spec: {SPEC_FILE}\n")
        f.write(f"Code: {CODE_FILE}\n\n")

        f.write(f"Spec behaviors found: {len(spec_behaviors) if spec_behaviors else 0}\n")
        f.write(f"Code behaviors found: {len(code_behaviors) if code_behaviors else 0}\n")

        gaps = gap_result.get("gaps", []) if gap_result else []
        matched = gap_result.get("matched", []) if gap_result else []
        f.write(f"Matched behaviors: {len(matched)}\n")
        f.write(f"Initial gaps detected: {len(gaps)}\n")

        if verify_result:
            confirmed = sum(1 for v in verify_result if v.get("confirmed", True))
            f.write(f"Gaps after verification: {confirmed}\n")

        f.write(f"\n{'='*60}\n")
        f.write("TOKEN USAGE\n")
        f.write(f"{'='*60}\n")
        total_tokens = 0
        for agent_name, usage in all_usage:
            f.write(f"  {agent_name}: prompt={usage['prompt_tokens']}, "
                    f"completion={usage['completion_tokens']}, "
                    f"total={usage['total_tokens']}\n")
            total_tokens += usage['total_tokens']
        f.write(f"  TOTAL: {total_tokens}\n")

        if assessment:
            f.write(f"\n{'='*60}\n")
            f.write("DETECTED UNSPECIFIED ADDITIONS\n")
            f.write(f"{'='*60}\n\n")
            for a in assessment:
                f.write(f"[{a.get('code_id')}] {a.get('description', '')}\n")
                f.write(f"  Category:      {a.get('primary_category')}\n")
                f.write(f"  Inferrability: {a.get('inferrability')}\n")
                f.write(f"  Correctness:   {a.get('correctness')}\n")
                f.write(f"  Impact:        {a.get('impact')}\n")
                f.write(f"  Reasoning:     {a.get('reasoning', '')}\n\n")

        if omission_assessment:
            f.write(f"\n{'='*60}\n")
            f.write("DETECTED OMISSIONS\n")
            f.write(f"{'='*60}\n\n")
            for a in omission_assessment:
                f.write(f"[{a.get('omission_id')}] {a.get('description', '')}\n")
                f.write(f"  Category:      {a.get('primary_category')}\n")
                f.write(f"  Source:        {a.get('source')}\n")
                f.write(f"  Inferrability: {a.get('inferrability')}\n")
                f.write(f"  Impact:        {a.get('impact')}\n")
                f.write(f"  Reasoning:     {a.get('reasoning', '')}\n\n")

    print(f"\nAll results saved to: {run_dir}")


if __name__ == "__main__":
    if len(sys.argv) >= 4:
        APP_NAME = sys.argv[1]
        SPEC_VARIANT = sys.argv[2]
        SERVICE_NAME = sys.argv[3]
        GEN_MODEL = sys.argv[4] if len(sys.argv) > 4 else GEN_MODEL
        SPEC_FILE = REPO_DIR + f"specs/{APP_NAME}/{SPEC_VARIANT}.txt"
        CODE_FILE = REPO_DIR + f"generated/{APP_NAME}/{SPEC_VARIANT}/{GEN_MODEL}/{SERVICE_NAME}.py"
        OUTPUT_DIR = REPO_DIR + f"results/{APP_NAME}/{SPEC_VARIANT}/"
        print(f"CLI override: app={APP_NAME}, variant={SPEC_VARIANT}, service={SERVICE_NAME}")
    run_pipeline()
