import os, sys
sys.path.insert(0, ".")
os.chdir(r"C:\Users\NANDINI DAGGU\CapStone\competitive-intelligence-crew")
from dotenv import load_dotenv; load_dotenv()
KEY = os.getenv("OPENROUTER_API_KEY")

# crewai memory analyze module - let us find what model string it would use
import inspect
from crewai.memory import unified_memory
src = inspect.getsource(unified_memory)
# Find lines that create LLM or reference model
for i, line in enumerate(src.splitlines(), 1):
    if "LLM" in line or "model_name" in line or "self.llm" in line:
        print(f"{i}: {line.rstrip()}")
