import os, sys
sys.path.insert(0, ".")
os.chdir(r"C:\Users\NANDINI DAGGU\CapStone\competitive-intelligence-crew")
from dotenv import load_dotenv
load_dotenv()

KEY = os.getenv("OPENROUTER_API_KEY")
BASE = "https://openrouter.ai/api/v1"

from crewai.llm import LLM

tests = [
    # (description, model_string, api_key, base_url)
    ("openrouter/ prefix + key+url",  "openrouter/google/gemma-4-31b-it:free", KEY, BASE),
    ("openrouter/ prefix, no extras", "openrouter/google/gemma-4-31b-it:free", None, None),
    ("no prefix + key+url",           "google/gemma-4-31b-it:free",            KEY, BASE),
    ("openrouter/ llama + key+url",   "openrouter/meta-llama/llama-3.3-70b-instruct:free", KEY, BASE),
    ("no prefix llama + key+url",     "meta-llama/llama-3.3-70b-instruct:free", KEY, BASE),
]

for desc, model, key, base_url in tests:
    kwargs = {}
    if key:      kwargs["api_key"]  = key
    if base_url: kwargs["base_url"] = base_url
    try:
        llm = LLM(model=model, **kwargs)
        result = llm.call("Say exactly: WORKING")
        print(f"  OK   {desc}: '{str(result)[:40]}'")
    except Exception as e:
        msg = str(e)[:100]
        print(f"  FAIL {desc}: {msg}")
