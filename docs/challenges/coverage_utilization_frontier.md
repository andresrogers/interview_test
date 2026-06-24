# Challenge: Coverage–utilization frontier

## Scenario

FinOps teams steer commitments by two numbers that pull against each other:
**coverage** (how much of your eligible spend is committed) and **utilization**
(how much of your commitment actually gets used). Push coverage up and
utilization tends to fall; the savings live in the trade-off between them.

## The question

**Map the coverage–utilization–savings surface for this account's compute as the
commitment level varies, locate where the account sits today, and recommend an
operating point** with a rationale.

## How it works (and where it gets subtle)

- For each candidate commitment level, compute the resulting **coverage**,
  **utilization**, and **net savings** over the window (same per-hour,
  decreasing-discount, use-it-or-lose-it mechanics as the optimal-commitment
  problem).
- Coverage and utilization are **not** the same metric and don't move together —
  reporting only one (or blending them into a single number) hides the decision.
- "Maximize savings" and "maximize utilization" point at *different* commitment
  levels. Knowing which one the business should target, and why, is the judgment
  being tested.

## Deliverables

1. **The frontier** — coverage vs utilization vs savings as commitment varies,
   visualized.
2. **Where the account's current commitments land** on it.
3. **A recommended operating point** and the reasoning for it.
4. **Reproducible analysis.**

---

**Data & references:** [data dictionary](../data_dictionary.md) · [AWS discount cheat sheet](../aws_discount_cheatsheet.md) · dataset `output/candidate_dataset.parquet`, pricing `output/pricing_options_filtered.parquet`.

**With your submission:** an [understanding ledger](../understanding_ledger.md). See [what we value](../understanding_debt.md) and the [challenge overview](./README.md).
