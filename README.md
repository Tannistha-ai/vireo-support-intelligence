# Vireo Audio — Support Intelligence Prototype

A time-boxed AI-assisted prototype that turns Vireo Audio's historical support-ticket export into a weekly complaint digest and an agent leaderboard.

The goal was not to build a full support platform, but to make the existing ticket data useful for recurring CX decisions.

## Business goal

The supplied data shows that **10.4% of tickets are strict repeat contacts**, representing approximately **₹52.4k per quarter in channel-specific contact cost**.

I would use the prototype to target a reduction in strict repeat contacts from **10.4% to 8.0%**.

At the supplied dataset's volume, that is approximately a **23% reduction in repeat contacts** and about **₹12k per quarter in avoided contact cost** if the target is achieved.

The 8.0% figure is a proposed pilot target, not a causal prediction from the historical data. Savings should be measured against a pre-intervention baseline before being attributed to the intervention.

---

## What the prototype produces

The project generates two primary deliverables:

### 1. Weekly complaint digest

- ticket volume
- top complaint types
- change versus an 8-week baseline
- complaint spike detection
- repeat-contact volume and estimated cost
- sanitized examples of customer language

### 2. Agent leaderboard

- tickets closed
- closed tickets per week
- repeat-contact rate
- Tier 1 agents compared within their own team
- Tier 2 shown separately using resolution time

A lightweight Streamlit interface displays these outputs for review.

---

## Project structure

```text
vireo-support-intelligence/
│
├── app.py
├── requirements.txt
├── README.md
├── DECISIONS.md
├── AI_LOG.md
│
├── data/                       # supplied assessment data; not committed
│   ├── tickets.csv
│   ├── agents.csv
│   ├── orders.csv
│   ├── customers.csv
│   └── products.csv
│
├── src/
│   ├── clean.py
│   ├── rules.py
│   ├── taxonomy.py
│   ├── labels.py
│   ├── providers.py
│   ├── privacy.py
│   └── analyze.py
│
├── prompts/
│   └── v1.txt
│
├── cache/                      # generated locally; not committed
│   └── llm_labels.jsonl
│
└── outputs/
    ├── labels.csv              # generated locally; not committed
    ├── digest_latest.md
    ├── drivers.csv
    ├── leaderboard_tier1.csv
    ├── tier2_days_to_resolve.csv
    └── results.json
```

---

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/Tannistha-ai/vireo-support-intelligence.git
cd vireo-support-intelligence
```

### 2. Create a virtual environment

```bash
python -m venv .venv
```

On Windows:

```bash
.venv\Scripts\activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

### 3. Add the supplied assessment data

The original assessment data is **not committed to this public repository**.

Create a `data/` directory and place the supplied files inside it:

```text
data/
├── agents.csv
├── customers.csv
├── orders.csv
├── products.csv
└── tickets.csv
```

The supplied `support-policy.pdf`, `email-thread.txt`, and `README.txt` were used as business and data context but are not redistributed in this public repository.

### 4. Configure Gemini

Copy the example environment file:

```bash
copy .env.example .env
```

Add your Gemini API key to `.env`.

API credentials are not included in the repository.

---
## Smoke test

Before making any paid model calls, verify the installation and privacy-scrubbing path with the mock provider:

```bash
python src/smoke_test.py

## Running the analysis

From the project root, run the classification pipeline:

```bash
python src/labels.py
```

This writes ticket-level classifications to:

```text
outputs/labels.csv
```

Model responses are cached in:

```text
cache/llm_labels.jsonl
```

so already processed tickets do not need to be sent to the model again.

Then run:

```bash
python src/analyze.py
```

This generates the weekly digest, repeat-contact analysis and leaderboard outputs.

Finally, start the viewer:

```bash
streamlit run app.py
```

The Streamlit application reads the generated outputs; it does not make live Gemini calls.

---

## Data quality findings

Before analyzing support performance, I checked whether the supplied export could be trusted as-is.

### Migration duplicates

The raw ticket file contains **12,528 rows but 11,875 unique tickets**.

The migration history indicates that part of the legacy Freshdesk data was re-imported into the new helpdesk.

Duplicate migration records are removed before calculating ticket volume, repeat contacts or agent metrics.

### Legacy timestamps

2,263 legacy records initially produced impossible negative resolution durations.

The affected records showed a consistent **5 hour 30 minute offset**, consistent with a UTC/IST mismatch.

The legacy resolution timestamps are corrected before duration calculations.

### Legacy CSAT

Legacy records use a CSAT value of `0` when the customer did not respond.

These values are treated as missing rather than as genuine zero ratings.

---

## Issue classification

The intake-bot category is not treated as ground truth. A significant number of tickets are assigned broad categories such as `Other`, while the customer message often contains a more specific issue.

The prototype therefore uses a cost-controlled cascade:

```text
Customer message + agent notes
             |
             v
    Deterministic rules
             |
             v
     Clear classification?
        /           \
      Yes       No / conflict
       |             |
       v             v
   Rule label      Gemini
        \           /
         \         /
          Final label
```

The LLM is therefore not called for every ticket.

Of the 11,875 unique tickets, **3,764 (31.7%)** were identified as ambiguous or conflicting by the rules layer.

An additional 300 rule-confident tickets were sent to Gemini as a control sample during validation.

Responses are cached to avoid paying for the same classification again during reruns.

Customer text is scrubbed before being sent to the external model.

---

## Classification validation

On a **300-ticket control sample** where the deterministic rules were already confident, Gemini independently agreed with the rule label on **97.7%** of tickets.

This is **cross-method agreement, not ground-truth accuracy**.

The observed disagreement rate on this control was **2.3%**.

This check is also intentionally easier than the ambiguous population routed to the LLM, so it should not be interpreted as evidence of 97.7% production accuracy.

A manually labelled, stratified holdout — particularly containing ambiguous tickets — would be required before treating the classifier as production-ready.

---

## Main business finding: repeat contacts

A strict repeat contact is defined as:

> Another ticket from the same customer, for the same product and classified issue, within 30 days of the earlier ticket's resolution.

Using this definition:

- **1,238 strict repeat contacts**
- **10.4% of supplied tickets**
- approximately **₹52.4k per quarter** in channel-specific contact cost represented by those repeat contacts

The financial figure describes the contact-cost opportunity represented in the supplied export. It is **not guaranteed savings**.

The issue families with the highest observed repeat rates include:

- Audio Quality — 15.2%
- Charging & Battery — 13.9%
- Connectivity — 13.4%

Additionally, **75.9% of strict repeat contacts were handled by a different agent from the preceding ticket**.

This is treated as an operational signal, not evidence that agent handoffs caused the repeat contact.

---

## Leaderboard methodology

A raw company-wide ranking by tickets closed would mix agents working in queues with substantially different workloads.

For example, median Tier 1 throughput ranges from approximately:

```text
Chat Frontline:  2.4 closed tickets/week
Logistics:       5.1 closed tickets/week
```

A global leaderboard would therefore partly rank the queue rather than the agent.

The requested leaderboard is retained, but:

- Tier 1 agents are ranked by tickets closed **within their team**
- repeat-contact rate is shown as context
- Tier 2 Escalations & Warranty is kept separate
- Tier 2 is shown using resolution time because those cases take longer by design

The leaderboard should not be interpreted as an overall agent-quality score.

---

## Weekly digest

For the latest complete week in the supplied data, **22–28 June 2026**, the prototype identified:

- 199 tickets
- 19 strict repeat contacts
- approximately ₹4,920 in repeat-contact cost
- 0 unclassified tickets

The highest-volume issues were:

1. Not delivered
2. Refund delay
3. Pairing failure

The digest also compares each issue with its previous 8-week average and flags unusual increases.

The generated digest is available at:

```text
outputs/digest_latest.md
```

and is also presented through the Streamlit interface.

---

## Cost controls

The LLM stage was deliberately designed so model spend does not scale blindly with every support ticket.

Cost controls include:

- deterministic classification before LLM use
- LLM calls only for ambiguous/conflicting cases
- batched requests
- response caching
- a maximum-call guard
- reusable generated labels

The measured uncached classification run consumed approximately:

- **510,427 input tokens**
- **117,204 output/thinking tokens**

Provider pricing is external to the repository and may change. Current Gemini pricing should therefore be checked when calculating production operating cost.

---

## Limitations

### Export volume

The supplied dataset averages materially fewer tickets per week than the approximately 650/week stated in the business context.

For that reason, financial figures in this analysis describe the supplied export and are **not silently scaled to the stated operating volume**.

This discrepancy should be reconciled before forecasting production savings.

### Classifier evaluation

The 97.7% result measures agreement between two classification methods on a rule-confident control sample rather than human-labelled accuracy.

### Causality

The analysis identifies associations and operational signals. For example, a repeat contact being handled by another agent does not establish that the handoff caused the repeat.

### Prototype scope

This is a time-boxed analytical prototype rather than a production support system.

Production deployment would require stronger human-labelled validation, monitoring, access controls and integration with the live support workflow.

---

## Additional documentation

`DECISIONS.md` records analytical choices, assumptions and discarded directions.

`AI_LOG.md` documents how AI tools were used, what was changed, and what was deliberately rejected during the exercise.