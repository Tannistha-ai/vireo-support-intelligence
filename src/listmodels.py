"""Lists the Gemini models YOUR key can actually call. Run:  python src/list_models.py
Pick a 'flash-lite' (cheapest) or 'flash' name from the output and put it in .env as GEMINI_MODEL=..."""
import sys, os
sys.path.insert(0, "src")
import requests
from env import load_env; load_env()
key = os.environ.get("GEMINI_API_KEY", "").strip()
if not key: sys.exit("No GEMINI_API_KEY in .env")
r = requests.get("https://generativelanguage.googleapis.com/v1beta/models?pageSize=200",
                 headers={"x-goog-api-key": key}, timeout=30)
if not r.ok: sys.exit(f"HTTP {r.status_code}: {r.text[:400]}")
rows = [m for m in r.json().get("models", []) if "generateContent" in m.get("supportedGenerationMethods", [])]
print(f"{len(rows)} models support generateContent for your key:\n")
for m in sorted(rows, key=lambda m: m["name"]):
    print(" ", m["name"].replace("models/", ""))
print("\nSuggested: the newest name containing 'flash-lite'. Then set GEMINI_MODEL in .env.")