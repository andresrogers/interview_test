# Challenge: Effective savings rate

## Scenario

Leadership wants a single, honest answer to "how much are we actually saving?"
— the account holds commitments today, and they want to know what those are
worth versus paying everything at on-demand rates.

## The question

**What effective savings rate is this account realizing — and where does it come
from?** Compute the rate, then decompose it (by service, by instrument, and over
time).

## How it works (and where it gets subtle)

The headline number is simple — roughly `1 − (Σ amortized_cost / Σ on_demand_cost)`
— but the *meaning* depends on choices you have to make and defend:

- Do you include **`Unused Commitment`** (committed dollars that bought nothing)?
  Leaving waste out flatters the rate; including it tells the truer story.
- What about **Spot**? It's discounted, but not by a commitment — including it
  conflates two different kinds of savings.
- Is the denominator **all spend**, or only **commitment-eligible** spend?

There isn't one right answer — there's a *defensible* one. The point is to know
which rate you computed and why it's the meaningful one.

## Deliverables

1. **The effective savings rate**, with a precise definition you can defend.
2. **A decomposition** — by service, by instrument/commitment, and over the window
   — that shows where the savings (and any waste) come from.
3. **Reproducible analysis** that derives it from the dataset.

---

**Data & references:** [data dictionary](../data_dictionary.md) · [AWS discount cheat sheet](../aws_discount_cheatsheet.md) · dataset `output/candidate_dataset.parquet`, pricing `output/pricing_options_filtered.parquet`.

**With your submission:** an [understanding ledger](../understanding_ledger.md). See [what we value](../understanding_debt.md) and the [challenge overview](./README.md).
