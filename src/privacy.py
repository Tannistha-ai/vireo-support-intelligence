"""Strip personal data BEFORE any text leaves the machine.
Free API tiers may use submitted content to improve the provider's products, and the
policy (s1) applies to any vendor handling support data. Local (ollama) needs this less.
"""
import re, pandas as pd
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
_PHONE = re.compile(r"(?<!\d)(?:\+?91[\s-]?)?[6-9]\d{9}(?!\d)")

def build_scrubber(customers_csv="data/customers.csv", agents_csv="data/agents.csv"):
    names = set(pd.read_csv(customers_csv).name.dropna()) | set(pd.read_csv(agents_csv).name.dropna())
    pat = re.compile("|".join(re.escape(n) for n in sorted(names, key=len, reverse=True)), re.I)
    def scrub(text: str) -> str:
        text = _EMAIL.sub("[EMAIL]", text); text = _PHONE.sub("[PHONE]", text)
        return pat.sub("[NAME]", text)
    return scrub
