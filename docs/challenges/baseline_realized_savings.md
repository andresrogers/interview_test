# Challenge: Realized savings of a past baseline commitment

## Scenario

Suppose that some months back you had committed at the **baseline level** for the
account's compute as it stood then — the "max-ish" level expected to be fully
consumed *given the usage observed up to that point* — and then simply lived with
that fixed commitment. How did that decision actually play out?

## The question

**Take the baseline commitment level for compute as of about nine months before
the latest complete month, hold it fixed, and simulate it forward to now against
the account's actual usage. What effective savings rate did it realize over that
period?** Then compare it to what an optimal-in-hindsight fixed commitment would
have realized over the same period.

## How it works (and where it gets subtle)

- The **baseline is the fully-consumed level for the history it was fit to** —
  sized so that, over the window it was computed on, the commitment would have been
  (just) fully used. That makes it low-waste *in hindsight, on that data*. It is
  **not** inherently safe going forward: a baseline can only ever be established
  from observed history, so if future usage falls below it, even a baseline-level
  commitment wastes. "Safe given the past" is not "safe for the future" — which is
  exactly what this backtest exposes.
- A commitment is **fixed once made.** You don't get to resize it each hour — you
  apply the *same* level forward, hour by hour, with the usual decreasing-discount,
  use-it-or-lose-it allocation.
- Because usage **grew** over the period, a baseline set nine months ago stays
  fully utilized but **leaves later savings unrealized** — so expect a gap between
  what the baseline realized and what an aggressive, hindsight-optimal commitment
  would have. Quantifying and explaining that gap is the point.

## Deliverables

1. **The realized effective savings rate** of the baseline commitment over the
   period, with the realized-vs-wasted breakdown.
2. **The gap** versus a hindsight-optimal fixed commitment, and an explanation of
   what drives it.
3. **Reproducible analysis.**

---

**Data & references:** [data dictionary](../data_dictionary.md) · [AWS discount cheat sheet](../aws_discount_cheatsheet.md) · dataset `output/candidate_dataset.parquet`, pricing `output/pricing_options_filtered.parquet`.

**With your submission:** an [understanding ledger](../understanding_ledger.md). See [what we value](../understanding_debt.md) and the [challenge overview](./README.md).
