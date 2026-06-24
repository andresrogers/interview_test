# Challenge: Audit the existing commitments

## Scenario

Before recommending anything new, you need to understand the account's *current*
commitment posture — what it already holds, and how well those commitments are
working.

## The question

**From the data alone, reconstruct the commitments this account currently holds,
and assess each one:** what it covers, how well it's utilized, how much is wasted,
and whether it looks well-sized.

## How it works (and where it gets subtle)

- The signal is spread across `commitment` (the ARN that covered each row),
  `cost_type` (`Usage with Discount` = a commitment paid off; `Unused Commitment`
  = committed dollars that bought nothing), and the usage they attach to.
- **Coverage and utilization are different things** (see the cheat sheet). A
  commitment can cover a large share of spend while sitting half-used, or be fully
  used while covering very little. An audit has to report both, not collapse them.
- `Unused Commitment` is the waste line — tying it back to the right commitment is
  where the read gets fiddly, and where an agent tends to conflate things.

## Deliverables

1. **An inventory** of the existing commitments, each with what it covers, its
   utilization, and its waste over the window.
2. **An assessment** — which look well-sized, which are under- or over-committed,
   and the evidence.
3. **Reproducible analysis.**

---

**Data & references:** [data dictionary](../data_dictionary.md) · [AWS discount cheat sheet](../aws_discount_cheatsheet.md) · dataset `output/candidate_dataset.parquet`, pricing `output/pricing_options_filtered.parquet`.

**With your submission:** an [understanding ledger](../understanding_ledger.md). See [what we value](../understanding_debt.md) and the [challenge overview](./README.md).
