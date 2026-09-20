# AI Usage Log

AI tools were used during this time-boxed exercise for exploration, implementation support, debugging, classification, and review.

I retained responsibility for the analytical choices, interpretation of results, scope decisions, and final conclusions.

## Claude

Claude was used heavily during the initial exploration and implementation phase.

I used it to:

- explore the supplied datasets and stakeholder context
- identify possible data-quality checks
- brainstorm hypotheses worth testing
- help draft and debug Python analysis code
- reason through repeat-contact definitions
- inspect leaderboard fairness
- challenge suspicious or unexpected results
- iterate on the ticket-classification approach

I did not treat its initial suggestions as conclusions.

Several directions explored with AI were later changed or discarded after checking them against the data.

Examples:

- A global tickets-closed leaderboard was rejected because queue throughput differed substantially.
- High throughput from one Billing agent was investigated but not treated as evidence of poor performance after checking repeat outcomes.
- A possible manufacturing-lot anomaly was explored and dropped when the evidence was not strong enough.
- The frontline anecdote about customers repeating themselves was tested rather than assumed to be true.
- An all-LLM classification design was replaced with a rules-first cascade to control cost.

## Gemini API

Gemini 3.1 Flash-Lite was used as part of the ticket issue-classification pipeline.

The model was not called for every ticket.

The pipeline first applies deterministic rules. Gemini is used when:

- the rule-based classifier is uncertain, or
- the customer-message and agent-note signals conflict.

A separate 300-ticket rule-confident control sample was also sent to Gemini as an independent consistency check.

Of 11,875 unique tickets, 3,764 — 31.7% — were identified as hard cases by the deterministic layer.

Model responses are cached in:

```text
cache/llm_labels.jsonl
```

This prevents repeated API calls for tickets that have already been classified.

Customer text is scrubbed before being sent to the external model.

## Prompting approach

The classification prompt defines a constrained issue taxonomy and asks the model to return structured labels rather than unrestricted prose.

The current prompt is stored in:

```text
prompts/v1.txt
```

The implementation also validates returned ticket IDs and labels before accepting model output. Invalid or omitted labels are not silently cached as valid classifications.

I did not recreate earlier prompt versions after the fact when they had not been preserved.

## Classification validation

A human-labelled validation sample was considered during development.

Given the exercise's intended time-box, I chose not to spend additional time manually labelling a large holdout after the classification pipeline was functioning.

Instead, I used a 300-ticket control sample where deterministic rules were already confident and asked Gemini to classify the same tickets independently.

The two methods agreed on 97.7% of labels.

I treat this only as a cross-method agreement check.

It is not ground-truth accuracy because neither method represents a human-labelled reference set.

Before production deployment, my next validation step would be a manually labelled stratified holdout containing both easy and ambiguous tickets.

## ChatGPT

ChatGPT was used during the final review and packaging phase.

I used it to:

- review the completed analysis outputs
- challenge how validation results should be described
- distinguish agreement from accuracy
- review the weekly digest
- review the leaderboard presentation
- build the lightweight Streamlit viewer
- structure the README and decision log
- help prepare the final communication of the analysis

## Where I overruled or changed AI-assisted directions

AI assistance was most useful for generating possible directions quickly, but several suggestions were deliberately not carried into the final result.

### Raw leaderboard

A simple ranking by tickets closed satisfied the request literally but ignored major differences between queues.

I changed the design to within-team Tier 1 rankings and a separate Tier 2 view.

### Agent anomaly

High throughput and thin notes initially made one agent look suspicious.

After checking the agent's repeat-contact outcome against the team, I did not find evidence supporting a quality conclusion and dropped that interpretation.

### Manufacturing-lot analysis

An apparent lot-level anomaly was not sufficiently convincing after considering exposure and the number of comparisons.

I excluded it from the final story.

### Repeat-contact definition

Broader definitions generated larger financial numbers but could combine unrelated customer problems.

I selected the stricter same-customer + product + issue definition for the headline.

### Financial extrapolation

The stated business volume and supplied export volume do not reconcile.

Rather than scaling the result to produce a larger savings estimate, I kept the headline tied to the supplied data and documented the discrepancy.

## Cost-control design

A specific stakeholder concern was avoiding an unpredictable model bill.

The pipeline therefore uses:

1. deterministic rules before the LLM
2. selective LLM routing
3. batched model requests
4. response caching
5. a maximum-call guard
6. reusable generated labels

The measured uncached classification run used approximately:

- 510,427 input tokens
- 117,204 output/thinking tokens

The code records token usage so model cost can be estimated using the provider's current pricing.

Provider pricing is intentionally treated as an external assumption because it can change over time.

## Human responsibility

AI was used as an accelerator rather than as the source of final business conclusions.

The decisions I retained responsibility for included:

- identifying repeat contacts as the main actionable opportunity
- defining the headline repeat-contact metric
- deciding which financial estimate to report
- rejecting unsupported hypotheses
- restructuring the requested leaderboard
- distinguishing correlation from causation
- deciding when additional analysis was no longer worth the time-box
- documenting limitations instead of hiding them