"""Tiny .env loader so we need no extra dependency."""
import os
from pathlib import Path
def load_env(path=".env"):
    p = Path(path)
    if not p.exists(): return
    for line in p.read_text().splitlines():
        line = line.split("#")[0].strip()
        if "=" in line:
            k, v = line.split("=", 1); os.environ.setdefault(k.strip(), v.strip())
