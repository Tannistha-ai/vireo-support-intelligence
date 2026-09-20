"""Swappable LLM backends with built-in cost tracking.

  mock    - no network, deterministic; tests the plumbing only (NOT real labels)
  ollama  - local model at http://localhost:11434. Rs 0 per ticket, no key, data never leaves the machine.
  gemini  - Google AI Studio REST API. Tiny per-ticket cost; text is sent to Google (scrub first).

Every provider counts tokens so a run can print its own bill (`usage_report`).
UNTESTED against live Gemini/Ollama as of writing - only `mock` was run. Expect small fixes.
Prices are USD per 1M tokens (input, output). Gemini figure is a third-party July 2026 quote:
VERIFY at ai.google.dev/pricing before quoting it to a client.
"""
import os, time, json, requests, threading

PRICE_PER_M = {
    "gemini-2.5-flash-lite": (0.10, 0.40),
    "gemini-3.1-flash-lite": (0.25, 1.50),
}
# third-party July 2026 quote; verify
# For any other model set GEMINI_PRICE_IN_USD / GEMINI_PRICE_OUT_USD (USD per 1M tokens) from ai.google.dev/pricing
USD_TO_INR = 88   # assumption for planning only; update to the current rate

class Provider:
    name = "base"; model = "n/a"
    def __init__(self):
        self.tokens_in = 0; self.tokens_out = 0; self.calls = 0
        self.lock = threading.Lock()
    def _complete(self, system, user): raise NotImplementedError
    def complete_json(self, system: str, user: str) -> str:
        with self.lock: self.calls += 1
        return self._complete(system, user)
    def usage_report(self) -> dict:
        pin, pout = PRICE_PER_M.get(self.model, (None, None))
        if pin is None and os.environ.get("GEMINI_PRICE_IN_USD"):
            pin = float(os.environ["GEMINI_PRICE_IN_USD"]); pout = float(os.environ.get("GEMINI_PRICE_OUT_USD", 0))
        price_known = pin is not None or self.name != "gemini"
        pin, pout = (pin or 0.0), (pout or 0.0)
        usd = self.tokens_in / 1e6 * pin + self.tokens_out / 1e6 * pout
        return {"provider": self.name, "model": self.model, "calls": self.calls,
                "tokens_in": self.tokens_in, "tokens_out": self.tokens_out,
                "cost_usd": round(usd, 4), "cost_inr": round(usd * USD_TO_INR, 2),
                "price_known": price_known}

class Mock(Provider):
    name = "mock"
    def _complete(self, system, user):
        self.tokens_in += (len(system) + len(user)) // 4; self.tokens_out += 12
        return json.dumps({"issue": "unknown", "confidence": 0.0})

class Ollama(Provider):
    name = "ollama"
    def __init__(self):
        super().__init__()
        self.model = os.environ.get("OLLAMA_MODEL", "llama3.2")
    def _complete(self, system, user):
        try:
            r = requests.post("http://localhost:11434/api/chat", timeout=300, json={
                "model": self.model, "stream": False, "format": "json",
                "options": {"temperature": 0},
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]})
        except requests.ConnectionError:
            raise SystemExit("Cannot reach Ollama. Is the Ollama app running? (then: ollama pull " + self.model + ")")
        r.raise_for_status(); j = r.json()
        self.tokens_in += j.get("prompt_eval_count", 0); self.tokens_out += j.get("eval_count", 0)
        return j["message"]["content"]

class Gemini(Provider):
    name = "gemini"
    def __init__(self):
        super().__init__()
        self.key = os.environ["GEMINI_API_KEY"]
        self.model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash-lite")
    def _complete(self, system, user):
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
        body = {"systemInstruction": {"parts": [{"text": system}]},
                "contents": [{"role": "user", "parts": [{"text": user}]}],
                "generationConfig": {"temperature": 0, "responseMimeType": "application/json"}}
        for attempt in range(5):
            try:
                r = requests.post(url, json=body, headers={"x-goog-api-key": self.key}, timeout=60)
            except (requests.ConnectionError, requests.Timeout):   # network dropped: back off and retry
                time.sleep(2 ** attempt * 3); continue
            if r.status_code in (429, 500, 502, 503, 504):        # rate limit / Google-side hiccup
                time.sleep(2 ** attempt * 5); continue
            if not r.ok:
                raise RuntimeError(f"Gemini HTTP {r.status_code} for model '{self.model}': {r.text[:400]}")
            j = r.json()
            u = j.get("usageMetadata", {})
            self.tokens_in += u.get("promptTokenCount", 0); self.tokens_out += u.get("candidatesTokenCount", 0) + u.get("thoughtsTokenCount", 0)  # thinking tokens are billed as output
            return j["candidates"][0]["content"]["parts"][0]["text"]
        raise RuntimeError("Gemini unreachable or rate-limited after 5 retries")

def get_provider(name=None) -> Provider:
    name = name or os.environ.get("LLM_PROVIDER", "mock")
    return {"mock": Mock, "ollama": Ollama, "gemini": Gemini}[name]()