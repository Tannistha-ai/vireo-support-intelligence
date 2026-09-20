"""Label tickets with an issue from the 27-label taxonomy.  Cascade, cheapest step first:
   1. free rules (rules.py) label everything;
   2. the LLM re-labels only the HARD tickets (rules unsure, or message-rule vs note-rule disagree)
      plus a small random CONTROL sample of easy tickets, so we can measure how often rules are wrong.
Spend is capped (--max-calls), results are cached on disk (re-running never pays twice), text is scrubbed first.

  python src/labels.py --dry-run                 # how many tickets/calls, no spend
  python src/labels.py --max-tickets 60          # small trial run
  python src/labels.py --max-calls 400           # full run
"""
import sys, json, time, argparse, random
from pathlib import Path
sys.path.insert(0, "src")
import pandas as pd
from env import load_env; load_env()
from clean import load
import rules
from taxonomy import TAXONOMY, LABELS
from privacy import build_scrubber
from providers import get_provider

PROMPT_VERSION = "v1"
BATCH = 12

def build_system_prompt(version=PROMPT_VERSION):
    text = Path(f"prompts/{version}.txt").read_text(encoding="utf-8")
    lab = "\n".join(f"- {k}: {v[1]}" for k, v in TAXONOMY.items())
    return text.replace("{LABELS}", lab)

def rule_pass(t):
    rules.build_normalizer(list(t.customer_message) + list(t.agent_notes))
    t["rule_msg"] = [rules.classify(m, "")[0] for m in t.customer_message]
    t["rule_note"] = [rules.classify("", n)[0] for n in t.agent_notes]
    t["rule_label"] = [rules.classify(m, n)[0] for m, n in zip(t.customer_message, t.agent_notes)]
    unsure = t.rule_msg == "other_unclear"
    conflict = (t.rule_msg != "other_unclear") & (t.rule_note != "other_unclear") & (t.rule_msg != t.rule_note)
    t["hard"] = unsure | conflict
    return t

def _norm_id(x):
    return str(x).strip().strip("[]").strip().strip("'\"")

def _conf(x):
    try: return float(x)
    except (TypeError, ValueError): return {"high": 0.9, "medium": 0.6, "low": 0.3}.get(str(x).strip().lower(), 0.0)

def parse_batch(raw, ids):
    """Return ({id: (label, confidence)}, n_not_labeled).
    FIX 2/3: only VALID entries are returned. A wrong id format, invalid label or omitted ticket is NOT stored as
    other_unclear (that silently poisoned the cache forever); it stays uncached and is retried on the next run."""
    raw = raw.strip()
    if raw.startswith("```"): raw = raw.strip("`").removeprefix("json").strip()
    out, valid = {}, set(ids)
    try:
        j = json.loads(raw)
        items = j["labels"] if isinstance(j, dict) else j
        for it in items:
            tid, lab = _norm_id(it.get("id")), it.get("label")
            if tid in valid and lab in TAXONOMY: out[tid] = (lab, _conf(it.get("confidence", 0)))
    except Exception:
        return {}, len(ids)
    return out, len(ids) - len(out)

def llm_label(df, prov, scrub, cache_path, max_calls, version=PROMPT_VERSION):
    system = build_system_prompt(version)
    cache = {}
    if cache_path.exists():
        for line in cache_path.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            if r["prompt"] == version and r["model"] == prov.model: cache[r["ticket_id"]] = r
    todo = df[~df.ticket_id.isin(cache)]
    print(f"cached: {len(cache)} | to label: {len(todo)}")
    calls = bad_total = 0
    cache_path.parent.mkdir(parents=True, exist_ok=True)      # FIX 1: cache/ may not exist
    with cache_path.open("a", encoding="utf-8") as f:
        for i in range(0, len(todo), BATCH):
            if calls >= max_calls: print(f"!! spend cap reached ({max_calls} calls). Re-run to continue."); break
            chunk = todo.iloc[i:i + BATCH]
            body = "\n\n".join(f"[{r.ticket_id}] customer: {scrub(r.customer_message)[:600]!r}\n"
                               f"      agent note: {scrub(r.agent_notes)[:300]!r}" for r in chunk.itertuples())
            for attempt in range(2):
                out, bad = parse_batch(prov.complete_json(system, "TICKETS:\n" + body), list(chunk.ticket_id))
                calls += 1
                if out: break
            bad_total += bad
            for tid, (lab, conf) in out.items():
                rec = {"ticket_id": tid, "label": lab, "confidence": conf, "prompt": version, "model": prov.model}
                cache[tid] = rec; f.write(json.dumps(rec) + "\n")
            f.flush()
            if calls % 10 == 0: print(f"  {calls} calls, {len(cache)} labeled")
    print(f"calls this run: {calls} | invalid/missing labels: {bad_total}")
    return cache

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true"); ap.add_argument("--max-calls", type=int, default=400)
    ap.add_argument("--max-tickets", type=int, default=None); ap.add_argument("--control", type=int, default=300)
    ap.add_argument("--prompt", default=PROMPT_VERSION)
    a = ap.parse_args()
    t, *_ = load(); t = rule_pass(t)
    hard = t[t.hard]; easy = t[~t.hard].sample(min(a.control, (~t.hard).sum()), random_state=1)
    send = pd.concat([hard, easy]).assign(is_control=lambda d: ~d.hard)
    if a.max_tickets: send = send.sample(min(a.max_tickets, len(send)), random_state=2)
    calls_needed = -(-len(send) // BATCH)
    print(f"tickets: {len(t)} | hard: {len(hard)} ({len(hard)/len(t):.1%}) | control sample: {len(easy)} | to send: {len(send)} | ~calls: {calls_needed}")
    if a.dry_run: return
    prov = get_provider(); scrub = build_scrubber(); t0 = time.time()
    cache = llm_label(send, prov, scrub, Path("cache/llm_labels.jsonl"), a.max_calls, a.prompt)
    missing = set(send.ticket_id) - set(cache)
    if missing: print(f"NOTE: {len(missing)} tickets were sent but not labeled (invalid/omitted/cap). Re-run to retry them.")
    t["llm_label"] = t.ticket_id.map(lambda i: cache[i]["label"] if i in cache else None)
    t["llm_conf"] = t.ticket_id.map(lambda i: cache[i]["confidence"] if i in cache else None)
    t["final_label"] = t.llm_label.fillna(t.rule_label)
    t["final_source"] = t.llm_label.map(lambda x: "rules" if x is None or pd.isna(x) else "llm")
    t["family"] = t.final_label.map(lambda x: TAXONOMY[x][0])
    Path("outputs").mkdir(exist_ok=True)
    t[["ticket_id", "rule_label", "llm_label", "llm_conf", "final_label", "final_source", "family", "hard"]].to_csv("outputs/labels.csv", index=False)
    ctrl = t[t.ticket_id.isin(easy.ticket_id) & t.llm_label.notna()]
    if len(ctrl): print(f"\nCONTROL: on {len(ctrl)} tickets rules were confident about, LLM agrees with rules {(ctrl.llm_label == ctrl.rule_label).mean():.1%}")
    print("USAGE:", prov.usage_report(), f"| {time.time()-t0:.0f}s"); print("wrote outputs/labels.csv")

if __name__ == "__main__":
    main()