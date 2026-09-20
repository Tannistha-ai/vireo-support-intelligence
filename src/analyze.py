"""Turns labels into: repeat-contact cost, what drives repeats, a fair leaderboard, a weekly digest.

    python src/analyze.py

Reads outputs/labels.csv (written by labels.py). If it is missing, falls back to RULES-ONLY labels and says so loudly,
so the pipeline can be tested before the LLM run finishes. Numbers from a fallback run are PROVISIONAL.

Repeat contact (policy s10): same customer contacts again about the same issue within 30 days of resolution,
costed at the contact cost of the channel used (policy s4).
"""
import sys, re, json
from pathlib import Path
sys.path.insert(0, "src")
import pandas as pd, numpy as np
from clean import load, COST_PER_CONTACT, BLENDED_COST
from taxonomy import TAXONOMY
import rules
from privacy import build_scrubber

QUARTERS = 6          # Jan 2025 - Jun 2026 = 18 months
REPEAT_LANG = re.compile(r"third time|second time|again|already (?:told|raised|explained|reported|complained|sent)|told (?:your|a|ur) (?:colleague|agent|team)|"
                         r"last (?:time|week|month)|earlier|previous|prior ticket|not fixed|same (?:issue|problem)|raised this|was told|supposedly|did ?n.?t hold|"
                         r"sorted by your team", re.I)
OUT = Path("outputs"); OUT.mkdir(exist_ok=True)

def with_labels(t):
    p = OUT / "labels.csv"
    if p.exists():
        L = pd.read_csv(p)[["ticket_id", "final_label", "final_source"]]
        t = t.merge(L, on="ticket_id", how="left"); t["final_label"] = t.final_label.fillna("other_unclear")
        src = "LLM+rules cascade (outputs/labels.csv)"
    else:
        print("!! outputs/labels.csv not found: using RULES-ONLY labels. Numbers below are PROVISIONAL.\n")
        rules.build_normalizer(list(t.customer_message) + list(t.agent_notes))
        t["final_label"] = [rules.classify(m, n)[0] for m, n in zip(t.customer_message, t.agent_notes)]
        t["final_source"] = "rules"; src = "RULES-ONLY STAND-IN (provisional)"
    t["family"] = t.final_label.map(lambda x: TAXONOMY[x][0])
    return t, src

def find_repeats(t, level):
    key = {"strict": ["customer_id", "product_sku", "final_label"], "family": ["customer_id", "product_sku", "family"],
           "any": ["customer_id", "product_sku"]}[level]
    d = t.sort_values("created_at")
    g = d.groupby(key, dropna=False)
    gap = (d.created_at - g.resolved_at.shift()).dt.total_seconds() / 86400   # NaN when previous ticket has no resolution
    d[f"rep_{level}"] = (gap >= 0) & (gap <= 30)
    d[f"prev_{level}"] = g.ticket_id.shift().where(d[f"rep_{level}"])
    return d.sort_index()

def main():
    t, ag, *_ = load(); t, label_src = with_labels(t)
    res = {"label_source": label_src, "tickets": len(t)}
    for lv in ["strict", "family", "any"]:
        t[[f"rep_{lv}", f"prev_{lv}"]] = find_repeats(t, lv)[[f"rep_{lv}", f"prev_{lv}"]]
    t["cost"] = t.channel.map(COST_PER_CONTACT)
    print(f"LABEL SOURCE: {label_src}\n")
    print("REPEAT CONTACTS (same customer + product, within 30 days of the earlier resolution)")
    for lv, desc in [("strict", "same issue label      (policy definition, headline)"), ("family", "same issue family     (looser)"),
                     ("any", "any issue             (loosest, upper bound)")]:
        n = int(t[f"rep_{lv}"].sum()); rs = float(t.loc[t[f"rep_{lv}"], "cost"].sum())
        res[lv] = {"repeats": n, "share_of_tickets": round(n / len(t), 4), "cost_18m_inr": round(rs), "cost_per_quarter_inr": round(rs / QUARTERS),
                   "per_qtr_at_flat_180": round(n * 180 / QUARTERS), "per_qtr_at_blended_290": round(n * BLENDED_COST / QUARTERS)}
        r = res[lv]; print(f"  {desc}: {n:5d} = {r['share_of_tickets']:.1%} of tickets | Rs {r['cost_per_quarter_inr']:,}/qtr (channel costs) | Rs {r['per_qtr_at_flat_180']:,} at Arjun's 180 | Rs {r['per_qtr_at_blended_290']:,} at 290")

    # ---- what drives repeats: for each resolved ticket A, was it followed by a strict repeat?
    followed = set(t.prev_strict.dropna())
    A = t[t.status.isin(["resolved", "closed"])].copy(); A["followed"] = A.ticket_id.isin(followed)
    def junk(n):
        s = re.sub(r"(~\w+|//\w+|-\s?[A-Z]{2}\b|\[closed\])", "", n).strip(" .-\n")
        return len(s) < 22 and rules.classify("", n)[0] == "other_unclear"
    A["junk_note"] = A.agent_notes.map(junk); A["had_transfer"] = A.transfers > 0
    A["bot_tag_other"] = A.category == "Other"
    base = A.followed.mean(); res["base_followed_rate"] = round(float(base), 4)
    print(f"\nDRIVERS: chance a resolved ticket is followed by a repeat = {base:.1%} overall")
    rows = []
    for col in ["status", "channel", "had_transfer", "junk_note", "bot_tag_other", "priority", "family"]:
        for val, g in A.groupby(col):
            rows.append({"driver": col, "value": val, "tickets": len(g), "repeat_rate": g.followed.mean(), "lift_vs_base": g.followed.mean() / base})
    D = pd.DataFrame(rows); D.to_csv(OUT / "drivers.csv", index=False)
    show = D[(D.tickets >= 150)].sort_values("lift_vs_base", ascending=False)
    print(show.head(8).round(3).to_string(index=False)); print("  ...lowest:"); print(show.tail(3).round(3).to_string(index=False))

    # ---- does the customer's own language ("third time", "already told...") agree with what we detect?
    t["says_repeat"] = t.customer_message.str.contains(REPEAT_LANG)
    any_rep = t.rep_any | t.rep_family | t.rep_strict
    print(f"\nVALIDITY: {t.says_repeat.mean():.1%} of messages contain repeat-language. Of those, {any_rep[t.says_repeat].mean():.1%} have a detected earlier ticket "
          f"(vs {any_rep[~t.says_repeat].mean():.1%} of messages without it).")
    res["says_repeat_share"] = round(float(t.says_repeat.mean()), 4); res["detected_given_says_repeat"] = round(float(any_rep[t.says_repeat].mean()), 4)
    print("  repeat-language by channel:", t.groupby("channel").says_repeat.mean().round(3).to_dict())
    prev_agent = t.set_index("ticket_id").agent_id
    rp = t[t.rep_strict].copy(); rp["prev_agent"] = rp.prev_strict.map(prev_agent)
    print(f"  strict repeats handled by a DIFFERENT agent than the first ticket: {(rp.prev_agent != rp.agent_id).mean():.1%} (n={len(rp)})")

    # ---- leaderboard: Tier 1 only, ranked WITHIN team, plus quality signals (policy s6: Tier 2 not comparable)
    weeks = (t.created_at.max() - t.created_at.min()).days / 7
    R = A.merge(ag[["agent_id", "name", "team", "tier", "site", "shift"]], on="agent_id")
    T1 = R[R.tier == 1].groupby(["agent_id", "name", "team", "site", "shift"]).agg(
        closed=("ticket_id", "count"), repeat_rate=("followed", "mean"), csat=("csat_score", "mean"), csat_n=("csat_score", "count"),
        junk_notes=("junk_note", "mean"), median_handle_hr=("handle_hr", "median")).reset_index()
    T1["closed_per_week"] = T1.closed / weeks
    T1["rank_in_team_by_volume"] = T1.groupby("team").closed_per_week.rank(ascending=False, method="min").astype(int)
    T1["rank_in_team_by_repeats(low=good)"] = T1.groupby("team").repeat_rate.rank(method="min").astype(int)
    T1["team_size"] = T1.groupby("team").agent_id.transform("count")
    T1.sort_values(["team", "rank_in_team_by_volume"]).round(3).to_csv(OUT / "leaderboard_tier1.csv", index=False)
    T2 = R[R.tier == 2].groupby(["agent_id", "name", "team"]).agg(closed=("ticket_id", "count"), median_days_to_resolve=("handle_hr", lambda s: s.median() / 24),
                                                                   repeat_rate=("followed", "mean")).reset_index()
    T2.round(3).to_csv(OUT / "tier2_days_to_resolve.csv", index=False)
    raw_rank = A.groupby("agent_id").size().rank(ascending=False, method="min")
    print(f"\nLEADERBOARD: {weeks:.0f} weeks of data. Raw top 5 by volume are on teams: "
          f"{ag.set_index('agent_id').loc[raw_rank.nsmallest(5).index, 'team'].value_counts().to_dict()}")
    print("  within-team spread of closed/week (Tier 1):"); print(T1.groupby("team").closed_per_week.agg(["min", "median", "max"]).round(2).to_string())
    top = T1.sort_values("closed_per_week", ascending=False).head(4)
    print("  highest-volume Tier 1 agents vs their repeat rate (team median in brackets):")
    for r in top.itertuples():
        print(f"    {r.agent_id} {r.team[:18]:18s} {r.closed_per_week:5.1f}/wk  repeat {r.repeat_rate:.1%} (team {T1[T1.team == r.team].repeat_rate.median():.1%})  junk notes {r.junk_notes:.0%}")

    # ---- weekly digest for the latest complete week
    t["week"] = t.created_at.dt.to_period("W-SUN")
    last = [w for w in sorted(t.week.unique()) if w.end_time.normalize() <= t.created_at.max().normalize() + pd.Timedelta(days=0)]
    wk = last[-1] if last else sorted(t.week.unique())[-2]
    cur = t[t.week == wk]; prev8 = t[t.week.isin([w for w in sorted(t.week.unique()) if w < wk][-8:])]
    c = cur.final_label.value_counts(); p8 = prev8.groupby([prev8.week, "final_label"]).size().unstack(fill_value=0)
    scrub = build_scrubber()
    md = [f"# Weekly complaint digest: week {wk.start_time:%d %b} to {wk.end_time:%d %b %Y}", "",
          f"Labels: {label_src}. **{len(cur)} tickets** this week; {cur.rep_strict.sum()} were repeat contacts "
          f"(Rs {int(cur.loc[cur.rep_strict, 'cost'].sum()):,}); {(cur.final_label == 'other_unclear').mean():.1%} could not be classified.", "",
          "| Rank | Issue | Family | Tickets | vs 8-wk avg | Flag |", "|---|---|---|---|---|---|"]
    for i, (lab, n) in enumerate(c.head(8).items(), 1):
        avg = p8[lab].mean() if lab in p8 else 0; sd = p8[lab].std() if lab in p8 else 0
        flag = "SPIKE" if (n >= 10 and avg > 0 and n > avg + 2 * max(sd, 1)) else ""
        md.append(f"| {i} | {lab} | {TAXONOMY[lab][0]} | {n} | {n - avg:+.1f} | {flag} |")
    md += ["", "Example customer words (names and contact details removed):"]
    for lab in c.head(3).index:
        ex = cur[cur.final_label == lab].customer_message.iloc[0]
        md.append(f"- **{lab}**: \"{scrub(ex).replace(chr(10), ' ')[:140]}\"")
    (OUT / "digest_latest.md").write_text("\n".join(md), encoding="utf-8")
    print("\nDIGEST written: outputs/digest_latest.md (top 3 this week:", ", ".join(c.head(3).index), ")")
    (OUT / "results.json").write_text(json.dumps(res, indent=2)); print("wrote outputs/results.json, drivers.csv, leaderboard_tier1.csv, tier2_days_to_resolve.csv")

if __name__ == "__main__":
    main()