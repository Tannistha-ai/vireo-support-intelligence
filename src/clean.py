"""Load and clean the Vireo support export. Every fix here is traced to a source doc.

Fixes (see DECISIONS.md):
 1. Duplicates: 653 ticket_ids exist in BOTH helpdesk and legacy_fd (policy s9 re-import).
    Rows are identical except resolved_at (+5.5h) and csat (0 vs blank). Keep the helpdesk row.
 2. Legacy resolved_at is UTC (policy s9); helpdesk/README timestamps are IST. Add 5h30m to
    legacy-only rows. (Sameer: 'I did not touch them.')
 3. Legacy csat_score 0 = no response (README). Set to NaN. Never average zeros.
 4. Money: policy s9 warns legacy uses a 'native unit'. Checked refund/retail-price ratios:
    identical distribution in both systems -> already rupees. NO conversion applied.
"""
import pandas as pd, numpy as np
from pathlib import Path

IST_OFFSET = pd.Timedelta(hours=5, minutes=30)
FRT_TARGET_MIN = {"chat": 15, "voice": 120, "social": 240, "email": 480}   # policy s3
COST_PER_CONTACT = {"chat": 210, "email": 260, "voice": 520, "social": 240} # policy s4
BLENDED_COST, TRANSFER_COST, SLA_CREDIT = 290, 305, 350

def load(data_dir="data"):
    d = Path(data_dir)
    t = pd.read_csv(d/"tickets.csv")
    for c in ["created_at", "first_response_at", "resolved_at"]:
        t[c] = pd.to_datetime(t[c])
    n_raw = len(t)
    # 1. dedupe, prefer helpdesk (sorts before legacy_fd)
    t = t.sort_values(["ticket_id", "source_system"]).drop_duplicates("ticket_id", keep="first").copy()
    # 2. legacy resolved_at is UTC -> IST
    leg = t.source_system == "legacy_fd"
    t.loc[leg, "resolved_at"] = t.loc[leg, "resolved_at"] + IST_OFFSET
    # 3. legacy csat 0 = no response
    t.loc[leg & (t.csat_score == 0), "csat_score"] = np.nan
    # derived
    t["frt_min"] = (t.first_response_at - t.created_at).dt.total_seconds() / 60
    t["breach"] = t.frt_min > t.channel.map(FRT_TARGET_MIN)
    t["handle_hr"] = (t.resolved_at - t.first_response_at).dt.total_seconds() / 3600
    t.attrs["n_raw"] = n_raw
    agents = pd.read_csv(d/"agents.csv")
    orders = pd.read_csv(d/"orders.csv"); customers = pd.read_csv(d/"customers.csv")
    products = pd.read_csv(d/"products.csv")
    return t.reset_index(drop=True), agents, orders, customers, products

if __name__ == "__main__":
    t, a, o, c, p = load()
    print(f"raw {t.attrs['n_raw']} -> clean {len(t)} tickets")
    print("negative handle time:", (t.handle_hr < 0).sum(), "| csat zeros left:", (t.csat_score == 0).sum())
    print("resolved before created:", (t.resolved_at < t.created_at).sum())
