# Cloud cost challenges

A set of analysis challenges built on the anonymized hourly cost-and-usage dataset
in `output/`. Work them in roughly the order below — but read the references
first.

## Read these first

- [Data dictionary](../data_dictionary.md) — every column in the dataset and the pricing table.
- [AWS discount cheat sheet](../aws_discount_cheatsheet.md) — the commitment-discount rules these problems turn on.
- [What we value: understanding over output](../understanding_debt.md).
- [The understanding ledger](../understanding_ledger.md) — submit one with your work.
- [`notebooks/demo.ipynb`](../../notebooks/demo.ipynb) — a runnable starter: loads the dataset, does the usage↔pricing join (on-demand vs Savings-Plan-discounted cost), and plots the `baseline_max` level. Run `uv sync`, then open it in Jupyter from that environment.

## This is deliberately bigger than one person can do by hand

The full set is scaled past what anyone could complete unaided in a reasonable
amount of time — you are **expected to use AI heavily**. It is very likely scaled
past what you can complete *and* fully understand. **That tension is the point:**
you will have to trade off **how much you finish** against **how much you
genuinely understand and can defend.**

**Plan to spend up to about 3 hours.** There is **no target completion level — we
are not counting challenges, and we do not expect you to finish the set.** Success
looks like: **a large amount of quality work, for a reasonable investment of time,
that you can defend under scrutiny.** We would far rather see three challenges you
deeply own than eight you can't explain. Use AI to go fast and wide, choose where
to go deep, and be honest in your [understanding ledger](../understanding_ledger.md)
about which is which.

## Suggested order

You don't have to follow this, but it builds naturally — each step leans on the
ones before it:

1. [Effective savings rate](./effective_savings_rate.md) — orient in the data: what is the account saving today?
2. [Optimal commitment level](./optimal_commitment.md) — the core mechanic: size a single Compute Savings Plan.
3. [Sensitivity to the evaluation window](./window_sensitivity.md) — stress-test that optimum.
4. [Realized savings of a past baseline](./baseline_realized_savings.md) — backtest a fixed commitment forward.
5. [Audit the existing commitments](./audit_commitments.md) — read the account's current posture.
6. [Coverage–utilization frontier](./coverage_utilization_frontier.md) — the decision surface FinOps teams balance.
7. [Optimal commitment basket](./commitment_basket.md) — generalize across instruments *(hard)*.
8. [Forecast and commit](./forecast_and_commit.md) — size a forward-looking commitment *(hard)*.

[Explain the anomaly](./explain_the_anomaly.md) is a short, anytime probe — pick it
up whenever something in the data surprises you.

## What to submit

Package your work as a git repository or a zip and send it back through the same
contact who sent you this challenge. Please include:

- **Your analysis** — runnable code and/or notebooks that reproduce your results
  from the dataset and pricing table, plus any figures or short write-ups.
- **An [understanding ledger](../understanding_ledger.md)** — the short record of
  what you genuinely understand versus what you leaned on AI for. Read
  [what we value](../understanding_debt.md) first; this is the part we weigh most.

Whatever format you choose, make it something we can re-run and that you can walk us
through and defend in a follow-up conversation.
