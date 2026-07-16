import os, sys, re, pathlib
os.chdir(r"C:\Users\NANDINI DAGGU\CapStone\competitive-intelligence-crew")

PATTERNS = [
    r"MODEL_NAME", r"MODEL_PRIMARY", r"MODEL_FALLBACK", r"MODEL_LAST_RESORT",
    r"model_primary", r"model_fallback", r"model_name", r"model_cascade",
    r"openrouter/", r"gemma", r"llama", r"qwen", r"mistral", r"deepseek",
    r"gemini", r"nemotron", r"hermes",
    r'llm\s*=', r'self\.model\s*=', r'model\s*=\s*["\']',
]
COMBINED = re.compile("|".join(PATTERNS), re.IGNORECASE)

SKIP = {"venv", "__pycache__", ".git", ".github", "node_modules"}
EXTS = {".py", ".yaml", ".yml", ".env", ".toml", ".txt", ".cfg", ".ini"}

results = []
for f in pathlib.Path(".").rglob("*"):
    if f.is_dir(): continue
    if any(s in f.parts for s in SKIP): continue
    if f.suffix not in EXTS: continue
    if any(x in f.name for x in ["_audit", "_verify", "_test", "_probe", "_find"]): continue
    try:
        lines = f.read_text(encoding="utf-8", errors="replace").splitlines()
    except: continue
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("#"): continue
        if COMBINED.search(stripped):
            results.append((str(f), i, stripped[:100]))

results.sort(key=lambda x: x[0])
current_file = None
for path, lno, line in results:
    if path != current_file:
        print(f"\n--- {path} ---")
        current_file = path
    print(f"  {lno:4}: {line}")

print(f"\nTotal: {len(results)} matches in {len(set(r[0] for r in results))} files")
