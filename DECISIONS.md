# Decision Log

This log records the main analytical and product decisions made during the time-boxed Vireo Audio support-ticket exercise, including approaches I considered but did not use.

## 1. Validate the data before analyzing performance

I did not treat the supplied ticket export as analysis-ready.

The raw file contained 12,528 rows but only 11,875 unique tickets. The migration notes also mentioned that part of the Freshdesk history had been re-imported into the newer helpdesk.

**Decision:** deduplicate migrated ticket records before calculating volumes, repeat contacts, costs, or agent performance.

**Why:** otherwise the migration itself would inflate the business metrics.

---

## 2. Correct the legacy timestamp inconsistency

2,263 legacy tickets initially had a resolution timestamp earlier than their creation timestamp.

The affected records showed a consistent 5 hour 30 minute difference.

**Decision:** correct the affected legacy resolution timestamps by +05:30 before calculating resolution durations.

**Why:** the pattern is consistent with a UTC/IST mismatch, and leaving it unchanged would produce impossible negative handling times.

---

## 3. Treat legacy CSAT zero as missing

The supplied documentation states that the legacy system used `0` when a customer did not answer the CSAT survey.

**Decision:** treat these values as missing rather than genuine zero ratings.

**Why:** otherwise agents handling more legacy tickets would appear to have artificially poor CSAT.

---

## 4. Do not use the intake-bot category as ground truth

The existing category field was useful as a reference but not sufficiently specific for the analysis. Many tickets were classified as `Other`, while the customer message or agent notes contained a more specific issue.

**Decision:** create a normalized issue taxonomy from the ticket text.

---

## 5. Use rules first and the LLM selectively

One option was to send every ticket to Gemini.

I rejected this.

**Decision:** use deterministic rules for straightforward cases and send only ambiguous or conflicting tickets to Gemini.

Of 11,875 unique tickets, 3,764 — 31.7% — were identified as hard cases.

A separate 300-ticket rule-confident control sample was also sent to Gemini for a consistency check.

**Why:** this reduces unnecessary model calls, makes the pipeline easier to inspect, and directly addresses the concern about an unpredictable per-ticket model bill.

Responses are cached so rerunning the pipeline does not repeatedly pay to classify the same ticket.

---

## 6. Use a conservative repeat-contact definition

I tested multiple definitions of a repeat contact.

The loosest definition — another ticket from the same customer and product — produced a much larger number, but could combine unrelated problems.

**Decision:** use the following strict definition for the headline result:

> Same customer + same product + same classified issue within 30 days of the earlier ticket's resolution.

This produces:

- 1,238 repeat contacts
- 10.4% of supplied tickets
- approximately ₹52.4k per quarter in channel-specific contact cost

Looser definitions are retained as sensitivity checks rather than used as the headline.

---

## 7. Treat repeat-contact cost as an opportunity pool, not guaranteed savings

Removing every repeat contact is unrealistic.

**Decision:** describe ₹52.4k/quarter as the contact cost represented by strict repeats in the supplied export, rather than claiming the company would automatically save ₹52.4k.

---

## 8. Test the frontline anecdote rather than assume it is true

Operations reported customers saying variations of “I already told your colleague this.”

I looked for repeat-language in customer messages and compared it with detected prior contacts.

12.8% of messages contained repeat-language. Among those messages, 52.4% had a detected earlier ticket, compared with 23.8% among messages without repeat-language.

Among strict repeat contacts, 75.9% were handled by a different agent from the earlier ticket.

**Decision:** treat this as supporting evidence of a context-continuity problem, not proof that agent handoffs cause repeat contacts.

---

## 9. Do not use a company-wide raw leaderboard

The initial request was for a leaderboard by tickets closed.

However, throughput differs substantially between queues. For example, median Tier 1 throughput was approximately 2.4 closed tickets/week for Chat Frontline and 5.1 for Logistics.

The operating policy also indicates that Tier 2 should not be compared with Tier 1 on ticket volume.

**Decision:** keep the requested leaderboard, but rank Tier 1 agents within their own teams.

Tier 2 Escalations & Warranty is shown separately using resolution time.

**Why:** a global volume ranking would partly measure queue assignment rather than individual performance.

---

## 10. Do not turn unusual throughput into an accusation

One Billing agent, A3033, had substantially higher throughput than the rest of the team and relatively thin documentation.

That initially looked worth investigating.

However, the agent's repeat-contact rate was not worse than the Billing team median.

**Decision:** do not characterize the agent as a quality problem based on throughput or note length alone.

This was a useful example of an initial hypothesis that the outcome data did not support.

---

## 11. Do not force a manufacturing-lot finding

I also explored whether particular product lots showed unusually high support incidence.

After accounting for the number of comparisons and exposure differences, the apparent anomaly was not strong enough to use as a headline finding.

**Decision:** drop this direction rather than force a more dramatic story from weak evidence.

---

## 12. Be precise about classifier validation

A manual human-labelled validation set was considered but was not completed within the intended time-box.

Instead, Gemini independently classified a 300-ticket sample where the deterministic rules were already confident.

Agreement was 97.7%.

**Decision:** report this as cross-method agreement, not model accuracy.

A manually labelled stratified holdout, particularly containing difficult tickets, would be the next validation step before production use.

---

## 13. Do not silently extrapolate the financial impact

The supplied ticket export averages materially fewer tickets per week than the approximately 650/week described in the business context.

**Decision:** calculate the headline financial impact from the supplied data rather than multiplying it to match the stated operating volume.

The discrepancy should be reconciled before making a production savings forecast.

---

## 14. Keep the interface deliberately small

The request was for a weekly digest and leaderboard, not a new support platform.

**Decision:** build a lightweight Streamlit viewer with two primary views:

- Weekly Digest
- Agent Leaderboard

The underlying analysis remains in reproducible CSV, JSON and Markdown outputs.

**Why:** the interface demonstrates how the analysis could be consumed without expanding the prototype beyond the requested scope.