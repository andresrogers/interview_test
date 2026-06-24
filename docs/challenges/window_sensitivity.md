# Challenge: Sensitivity to the evaluation window

> Builds on [Optimal commitment level](./optimal_commitment.md).

## Scenario

The "optimal commitment" you'd recommend depends entirely on *which slice of
history* you optimize over. A commitment is a forward-looking, multi-year
decision — so how much should the recommendation move as you change the window
you learned it from?

## The question

**Show how the optimal commitment level (and the savings it would have produced)
changes as you slide the evaluation window** — e.g. trailing 1, 2, 3, 6 months,
and windows anchored at different start points. Then recommend a window, or a
decision rule, that you'd actually trust for a forward commitment, and say why.

## How it works (and where it gets subtle)

- Re-run the optimal-commitment computation over many windows — easy to generate,
  easy to misread.
- The data has a **usage regime change**; the optimum will jump when a window
  straddles it. The interesting question isn't *that* it jumps but *what that
  implies* for committing going forward.
- The core idea to wrestle with: **"optimal over observed history" ≠ "optimal
  going forward."** A window that perfectly fits the past can be the wrong basis
  for a commitment you'll live with for a year or three.

## Deliverables

1. **Sensitivity results** — the optimal level and realized savings as a function
   of window, visualized so the pattern is legible.
2. **Interpretation** — why it moves where it does, and what that says about
   commitment risk.
3. **A recommended window / decision rule**, with rationale.
4. **Reproducible analysis.**

---

**Data & references:** [data dictionary](../data_dictionary.md) · [AWS discount cheat sheet](../aws_discount_cheatsheet.md) · dataset `output/candidate_dataset.parquet`, pricing `output/pricing_options_filtered.parquet`.

**With your submission:** an [understanding ledger](../understanding_ledger.md). See [what we value](../understanding_debt.md) and the [challenge overview](./README.md).
