import streamlit as st
import pandas as pd
import json
import re
from pathlib import Path


# --------------------------------------------------
# Page configuration
# --------------------------------------------------

st.set_page_config(
    page_title="Vireo Support Pulse",
    page_icon="🎧",
    layout="wide"
)

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "outputs"


# --------------------------------------------------
# Load generated analysis outputs
# --------------------------------------------------

@st.cache_data
def load_data():
    with open(OUTPUT_DIR / "results.json", "r", encoding="utf-8") as f:
        results = json.load(f)

    leaderboard = pd.read_csv(OUTPUT_DIR / "leaderboard_tier1.csv")
    tier2 = pd.read_csv(OUTPUT_DIR / "tier2_days_to_resolve.csv")
    drivers = pd.read_csv(OUTPUT_DIR / "drivers.csv")

    digest_text = (OUTPUT_DIR / "digest_latest.md").read_text(encoding="utf-8")

    return results, leaderboard, tier2, drivers, digest_text


results, leaderboard, tier2, drivers, digest_text = load_data()


# --------------------------------------------------
# Helpers
# --------------------------------------------------

def pretty_label(value):
    return str(value).replace("_", " ").title()


def extract_digest_table(markdown_text):
    """
    Extract the markdown issue table from digest_latest.md.
    """
    rows = []

    for line in markdown_text.splitlines():
        line = line.strip()

        if not line.startswith("|"):
            continue

        cells = [cell.strip() for cell in line.strip("|").split("|")]

        if len(cells) != 6:
            continue

        if cells[0] in {"Rank", "---"}:
            continue

        try:
            rank = int(cells[0])
            tickets = int(cells[3])
        except ValueError:
            continue

        rows.append({
            "Rank": rank,
            "Issue": pretty_label(cells[1]),
            "Family": cells[2],
            "Tickets": tickets,
            "vs 8-wk avg": cells[4],
            "Flag": cells[5]
        })

    return pd.DataFrame(rows)


def extract_examples(markdown_text):
    """
    Extract sanitized example customer messages already generated
    in digest_latest.md.
    """
    examples = []

    pattern = r'- \*\*(.*?)\*\*: "(.*?)"'

    for issue, message in re.findall(pattern, markdown_text):
        examples.append((pretty_label(issue), message))

    return examples


digest_df = extract_digest_table(digest_text)
examples = extract_examples(digest_text)


# --------------------------------------------------
# Header
# --------------------------------------------------

st.title("🎧 Vireo Support Pulse")

st.caption("Support intelligence • 18 months of ticket data")

st.markdown(
    "A lightweight weekly view of complaint trends and agent operations."
)


# --------------------------------------------------
# Main navigation
# --------------------------------------------------

digest_tab, leaderboard_tab = st.tabs(
    ["📊 Weekly Digest", "🏆 Agent Leaderboard"]
)


# ==================================================
# WEEKLY DIGEST
# ==================================================

with digest_tab:

    st.header("Weekly complaint digest")

    st.caption("22–28 June 2026")

    # Weekly headline metrics
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            "Tickets this week",
            "199"
        )

    with col2:
        st.metric(
            "Repeat contacts",
            "19"
        )
        st.caption("9.5% of weekly tickets")

    with col3:
        st.metric(
            "Repeat-contact cost",
            "₹4,920"
        )
        st.caption("Channel-specific estimate")

    with col4:
        st.metric(
            "Unclassified",
            "0"
        )
        st.caption("0.0% of weekly tickets")

    st.divider()

    # ----------------------------------------------
    # Complaint table
    # ----------------------------------------------

    st.subheader("Top complaints this week")

    st.caption(
        "Highest-volume issues compared with their previous 8-week average."
    )

    if not digest_df.empty:

        st.dataframe(
            digest_df,
            hide_index=True,
            use_container_width=True,
            column_config={
                "Rank": st.column_config.NumberColumn(
                    "Rank",
                    format="%d"
                ),
                "Tickets": st.column_config.NumberColumn(
                    "Tickets",
                    format="%d"
                )
            }
        )

    else:
        st.warning("Weekly complaint table could not be read from the digest.")

    st.divider()

    # ----------------------------------------------
    # Customer examples
    # ----------------------------------------------

    st.subheader("Customer voice")

    st.caption(
        "Sanitized examples from this week's leading complaint types."
    )

    if examples:

        example_cols = st.columns(min(len(examples), 3))

        for index, (issue, message) in enumerate(examples[:3]):

            with example_cols[index]:
                st.markdown(f"**{issue}**")
                st.write(f'“{message}”')

    st.divider()

    # ----------------------------------------------
    # Supporting repeat analysis
    # ----------------------------------------------

    with st.expander(
        "Why are customers contacting support again?",
        expanded=False
    ):

        st.markdown(
            """
            **Historical strict repeat-contact rate: 10.4%**

            A strict repeat is another ticket from the same customer,
            for the same product and classified issue, within 30 days
            of the earlier ticket's resolution.
            """
        )

        family_drivers = drivers[
            drivers["driver"] == "family"
        ].copy()

        if not family_drivers.empty:

            family_drivers = family_drivers.sort_values(
                "repeat_rate",
                ascending=False
            ).head(7)

            family_drivers["repeat_rate"] = (
                family_drivers["repeat_rate"] * 100
            ).round(1)

            family_drivers["lift_vs_base"] = (
                family_drivers["lift_vs_base"]
            ).round(2)

            family_display = family_drivers[
                [
                    "value",
                    "tickets",
                    "repeat_rate",
                    "lift_vs_base"
                ]
            ].rename(
                columns={
                    "value": "Issue family",
                    "tickets": "Tickets",
                    "repeat_rate": "Repeat rate (%)",
                    "lift_vs_base": "Lift vs baseline"
                }
            )

            st.dataframe(
                family_display,
                hide_index=True,
                use_container_width=True
            )

        st.markdown(
            "**75.9%** of strict repeat contacts were handled by "
            "a different agent from the earlier ticket."
        )

        st.caption(
            "This is an operational signal, not evidence that agent "
            "handoffs caused the repeat contact."
        )


# ==================================================
# AGENT LEADERBOARD
# ==================================================

with leaderboard_tab:

    st.header("Tier 1 agent leaderboard")

    st.caption(
        "Tickets closed, compared within team rather than across "
        "queues with different workloads."
    )

    teams = sorted(leaderboard["team"].dropna().unique())

    selected_team = st.selectbox(
        "Select team",
        teams
    )

    team_df = leaderboard[
        leaderboard["team"] == selected_team
    ].copy()

    team_df = team_df.sort_values(
        "rank_in_team_by_volume"
    )

    team_df["repeat_rate"] = (
        team_df["repeat_rate"] * 100
    ).round(1)

    team_df["closed_per_week"] = (
        team_df["closed_per_week"]
    ).round(1)

    team_df["csat"] = team_df["csat"].round(2)

    leaderboard_display = team_df[
        [
            "rank_in_team_by_volume",
            "name",
            "site",
            "shift",
            "closed",
            "closed_per_week",
            "repeat_rate"
        ]
    ].rename(
        columns={
            "rank_in_team_by_volume": "Rank",
            "name": "Agent",
            "site": "Site",
            "shift": "Shift",
            "closed": "Tickets closed",
            "closed_per_week": "Closed / week",
            "repeat_rate": "Repeat rate (%)"
        }
    )

    st.dataframe(
        leaderboard_display,
        hide_index=True,
        use_container_width=True
    )

    st.info(
        "Leaderboard position is based on tickets closed within the "
        "selected Tier 1 team. It should not be interpreted as an "
        "overall agent-quality score."
    )

    st.divider()

    # ----------------------------------------------
    # Tier 2
    # ----------------------------------------------

    st.subheader("Tier 2: Escalations & Warranty")

    st.caption(
        "Tier 2 cases take longer by design, so they are shown "
        "separately using resolution time rather than included in "
        "the Tier 1 volume leaderboard."
    )

    tier2_display = tier2.copy()

    tier2_display["median_days_to_resolve"] = (
        tier2_display["median_days_to_resolve"]
    ).round(1)

    tier2_display["repeat_rate"] = (
        tier2_display["repeat_rate"] * 100
    ).round(1)

    tier2_display = tier2_display[
        [
            "name",
            "closed",
            "median_days_to_resolve",
            "repeat_rate"
        ]
    ].rename(
        columns={
            "name": "Agent",
            "closed": "Tickets closed",
            "median_days_to_resolve": "Median days to resolve",
            "repeat_rate": "Repeat rate (%)"
        }
    )

    st.dataframe(
        tier2_display,
        hide_index=True,
        use_container_width=True
    )


# --------------------------------------------------
# Footer
# --------------------------------------------------

st.divider()

st.caption(
    "Prototype generated from the supplied Vireo Audio support export. "
    "Issue classification uses a deterministic rules + Gemini cascade."
)