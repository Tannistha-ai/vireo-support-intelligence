"""Run this FIRST. It proves your key works and that only scrubbed text leaves your machine.
    python src/smoke_test.py
"""
import sys, json, os
sys.path.insert(0, "src")
import pandas as pd
from env import load_env; load_env()
from providers import get_provider
from privacy import build_scrubber

if os.environ.get("LLM_PROVIDER", "mock") == "gemini":
    _k = os.environ.get("GEMINI_API_KEY", "").strip()
    # Do not guess the key format (Google may change it); only catch empty or placeholder values.
    if len(_k) < 20 or "paste" in _k.lower():
        sys.exit("No GEMINI_API_KEY found in .env. Copy .env.example to .env and paste your key (no quotes, no spaces).")

SYSTEM = 'You label customer-support tickets. Reply with JSON only: {"issue": "<3-6 word plain-English issue>"}'
scrub = build_scrubber()
t = pd.read_csv("data/tickets.csv").sample(3, random_state=7)
prov = get_provider()
print(f"provider: {prov.name}\n")
for _, r in t.iterrows():
    msg, note = scrub(r.customer_message), scrub(r.agent_notes)
    print("SENT   :", msg.replace("\n", " | ")[:110])
    out = prov.complete_json(SYSTEM, f"Customer message: {msg}\nAgent note: {note}")
    print("GOT    :", json.loads(out), "\n")
print("USAGE  :", prov.usage_report())
print("OK - if you can read the SENT lines and see no real names, you are safe to continue.")
