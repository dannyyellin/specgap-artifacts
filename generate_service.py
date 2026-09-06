import os
import sys
import re
from openai import AzureOpenAI

MODEL = 'gpt-4.1-mini'
AZURE_OPENAI_API_KEY = os.getenv('GPT41_API_KEY')
AZURE_OPENAI_ENDPOINT = os.getenv('GPT41_URL_AZURE')
API_VERSION = '2025-04-01-preview'
MAX_TOKENS = 5000
TEMP = 0

REPO_DIR = os.path.dirname(os.path.abspath(__file__)) + "/"

JOBS = [
    # Public Library
    {'app': 'public-library', 'variant': 'borrows-R1R2R3', 'service': 'borrows',
     'app_desc': 'a public library application'},
    {'app': 'public-library', 'variant': 'cardholders-R4R5R6R7', 'service': 'cardholders',
     'app_desc': 'a public library application'},
    {'app': 'public-library', 'variant': 'books-R8R9R10R11', 'service': 'books',
     'app_desc': 'a public library application'},
    {'app': 'public-library', 'variant': 'logs-R12R13', 'service': 'logs',
     'app_desc': 'a public library application'},
    # Nutrition
    {'app': 'nutrition', 'variant': 'auth-R1R2R3', 'service': 'authentication',
     'app_desc': 'a restaurant nutrition application'},
    {'app': 'nutrition', 'variant': 'dishes-R4R5R6', 'service': 'dishes',
     'app_desc': 'a restaurant nutrition application'},
    {'app': 'nutrition', 'variant': 'profiles-R7R8R9', 'service': 'profile',
     'app_desc': 'a restaurant nutrition application'},
    {'app': 'nutrition', 'variant': 'ratings-R10R11R12', 'service': 'ratings',
     'app_desc': 'a restaurant nutrition application'},
    # Pet Store
    {'app': 'pet-store', 'variant': 'registry-R1R2R3', 'service': 'registry',
     'app_desc': 'a pet store application'},
    {'app': 'pet-store', 'variant': 'petstore-R4R5R6R7', 'service': 'pet-store',
     'app_desc': 'a pet store application'},
    {'app': 'pet-store', 'variant': 'petorder-R8R9R10', 'service': 'pet-order',
     'app_desc': 'a pet store application'},
]

client = AzureOpenAI(
    api_key=AZURE_OPENAI_API_KEY,
    api_version=API_VERSION,
    azure_endpoint=AZURE_OPENAI_ENDPOINT,
)


def strip_code_fences(text):
    match = re.search(r'```python\s*\n(.*?)```', text, re.DOTALL)
    if match:
        return match.group(1)
    return text


def generate_one(job):
    app = job['app']
    variant = job['variant']
    service = job['service']
    app_desc = job['app_desc']

    spec_file = REPO_DIR + f"specs/{app}/{variant}.txt"
    out_dir = REPO_DIR + f"generated/{app}/{variant}/{MODEL}/"
    out_file = out_dir + f"{service}.py"

    if os.path.exists(out_file):
        print(f"  SKIP (already exists): {out_file}")
        return

    with open(spec_file) as f:
        spec_content = f.read()

    service_prompt = (
        f"Below is (I) a description of the microservices for {app_desc} "
        f"and (II) code generation guidelines.\n"
        f"Generate code for the {service} microservice following the guidelines. "
        f"The code you generate should be complete and executable."
    )

    system_msg = "You are an expert in generating Python microservices using REST APIs"
    user_msg = service_prompt + "\n\n" + spec_content

    print(f"  Calling {MODEL}...")
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg},
        ],
        temperature=TEMP,
        max_tokens=MAX_TOKENS,
        n=1,
    )

    usage = response.usage
    print(f"  Tokens: prompt={usage.prompt_tokens}, completion={usage.completion_tokens}, total={usage.total_tokens}")

    code = strip_code_fences(response.choices[0].message.content)

    os.makedirs(out_dir, exist_ok=True)
    with open(out_file, 'w') as f:
        f.write(code)
    print(f"  Saved: {out_file}")


if __name__ == '__main__':
    if len(sys.argv) > 1:
        filter_app = sys.argv[1]
        jobs = [j for j in JOBS if j['app'] == filter_app]
        if not jobs:
            print(f"No jobs for app '{filter_app}'. Options: public-library, nutrition, pet-store")
            sys.exit(1)
    else:
        jobs = JOBS

    print(f"Generating {len(jobs)} services using {MODEL}")
    for i, job in enumerate(jobs, 1):
        print(f"\n[{i}/{len(jobs)}] {job['app']}/{job['variant']} -> {job['service']}")
        generate_one(job)

    print("\nDone.")
