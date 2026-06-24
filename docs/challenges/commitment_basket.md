# Challenge: Optimal commitment basket

> Hard, and deliberately larger than one sitting. This is the place to be most
> conscious of the breadth-vs-understanding trade-off.

## Scenario

A single Compute Savings Plan is the blunt instrument. A real recommendation is a
**portfolio**: Compute Savings Plans, EC2 Instance Savings Plans, and Reserved
Instances, each at its own scope, term, and payment option — chosen so they stack
without stepping on each other.

## The question

**Design the basket of commitments that maximizes savings on this account's
compute over the observed data.** For each instrument in the basket, specify what
it covers, its size/level, term (1 vs 3 yr), and payment option — and the total
savings the basket produces versus the single-Compute-SP answer.

## How it works (and where it gets subtle)

The [cheat sheet](../aws_discount_cheatsheet.md) rules are load-bearing here:

- **Application order matters.** The most specific instrument applies first
  (RI → EC2 Instance SP → Compute SP). If you size each instrument as if it had
  the usage to itself, you'll **double-cover** and overstate savings. The broad
  Compute SP should only see what the specific instruments leave behind.
- **Scope cardinality.** An RI commits to one narrow configuration; an EC2
  Instance SP to a family+region; a Compute SP to everything. More specific =
  higher discount, less flexible.
- **Per-hour, use-it-or-lose-it, discounted-dollar sizing** still applies to every
  SP in the basket, and the highest-discount usage is consumed first.

The search space is large. You will not hand-tune this — but the correctness of
the *interaction* between instruments is exactly the part an agent will get subtly
wrong, and the part you must understand.

## Deliverables

1. **The recommended basket** — each instrument with scope, level/quantity, term,
   payment option — and the total projected savings vs the single-Compute-SP baseline.
2. **The interaction argument** — how the instruments stack, and a convincing
   demonstration that you did **not** double-cover usage.
3. **Reproducible analysis.**

---

**Data & references:** [data dictionary](../data_dictionary.md) · [AWS discount cheat sheet](../aws_discount_cheatsheet.md) · dataset `output/candidate_dataset.parquet`, pricing `output/pricing_options_filtered.parquet`.

**With your submission:** an [understanding ledger](../understanding_ledger.md). See [what we value](../understanding_debt.md) and the [challenge overview](./README.md).
