# Challenge: Forecast and commit

> Hard. The most forward-looking — and the most judgment-dependent — challenge.

## Scenario

Every real commitment decision is a bet on the *future*, not a fit to the past.
You're asked to size a commitment for the months ahead.

## The question

**Build a usage forecast and recommend a forward commitment** for the account's
compute that maximizes expected savings while managing the risk of
over-committing — for, say, the next three months.

## How it works (and where it gets subtle)

- You'll need a **forecast** of compute usage, and the data has a **trend / regime
  change** you have to take a position on (does it continue, plateau, reverse?).
- The risk is **asymmetric**: a commitment is paid whether or not you use it, and
  you can't take it back. Under-committing leaves savings on the table;
  over-committing burns cash with no recourse. The right recommendation reflects
  that asymmetry, not just an expected-value point estimate.
- Forecasting is where an agent will most confidently produce something that looks
  authoritative and isn't. Owning the method, its uncertainty, and the downside is
  the whole test.

## Deliverables

1. **A forecast** — with method and an honest statement of uncertainty.
2. **A recommended forward commitment** — the level, and the expected savings *and*
   downside if usage comes in low.
3. **Reproducible analysis.**

---

**Data & references:** [data dictionary](../data_dictionary.md) · [AWS discount cheat sheet](../aws_discount_cheatsheet.md) · dataset `output/candidate_dataset.parquet`, pricing `output/pricing_options_filtered.parquet`.

**With your submission:** an [understanding ledger](../understanding_ledger.md). See [what we value](../understanding_debt.md) and the [challenge overview](./README.md).
