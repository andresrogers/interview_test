# Challenge: Explain the anomaly

> Short. A pure comprehension probe — pick it up whenever the data surprises you.

## Scenario

Real cost data is full of features that look like errors but aren't — and the
occasional one that is. Telling them apart is a core skill.

## The question

**Find a feature in this dataset that looks surprising, and explain it from first
principles.** For example: the sharp change in monthly spend partway through the
window; the dollars sitting in `Unused Commitment`; the way the most recent month
behaves differently from the rest. Pick one (or your own), and account for it
using the data.

## How it works (and where it gets subtle)

- The test is whether you can produce an explanation *the data supports* —
  distinguishing a genuine **signal** (a real change in usage or commitments) from
  an **artifact** (a partial period, an accounting line, a modeling boundary).
- An agent will happily generate a plausible-sounding story for any chart. The
  bar here is an explanation you've actually checked against the rows, and can
  defend.

## Deliverables

1. **The feature**, and your explanation of it, grounded in the data.
2. **Signal vs artifact** — which it is, and how you can tell.
3. **So what** — whether it changes how you'd act, briefly.

---

**Data & references:** [data dictionary](../data_dictionary.md) · [AWS discount cheat sheet](../aws_discount_cheatsheet.md) · dataset `output/candidate_dataset.parquet`, pricing `output/pricing_options_filtered.parquet`.

**With your submission:** an [understanding ledger](../understanding_ledger.md). See [what we value](../understanding_debt.md) and the [challenge overview](./README.md).
