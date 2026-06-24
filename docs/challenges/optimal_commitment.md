# Challenge: Optimal Commitment Level

## Scenario

A team runs a large, variable compute footprint on AWS. They can buy a **Compute
Savings Plan** — an hourly spend commitment that discounts their compute usage in
exchange for committing to a fixed hourly amount for a term. Commit too little and
they leave savings on the table; commit too much and they pay for capacity they
don't use. They've asked you a precise question.

## The question

**Using the most recent three complete months of data, what commitment level
would have produced the maximum total dollars saved?**

Report that optimal commitment level and show the savings it would have achieved.

## How the commitment works (read carefully)

This mechanic is what makes the problem what it is — make sure your model matches
it:

1. **The commitment is sized in _discounted_ dollars per hour** — an amount of
   compute spend *at Savings-Plan (post-discount) rates*, per hour. It is **not**
   sized in on-demand dollars.
2. **Each hour, the commitment is allocated to that hour's eligible usage in order
   of decreasing discount** — the highest-discount usage is covered first, then
   the next, and so on, consuming the commitment's discounted-dollar budget until
   it is exhausted. Usage beyond the commitment that hour is billed at on-demand
   rates.
3. **It is use-it-or-lose-it, per hour.** The full commitment is paid every hour
   regardless of usage. In an hour where eligible usage is smaller than the
   commitment, the unused portion is wasted.
4. **Eligible usage** is everything a Compute Savings Plan covers: **EC2, Fargate,
   and Lambda.** Your dataset provides the Cloud Capital proprietary `commitment_key`
   column and every usage row with a commitment_key prefix of AWS#Compute is
   coverable by a Compute Savings Plan.

So, for a given commitment level, the dollars saved in an hour are the on-demand
cost of the covered usage minus what that usage costs under the commitment —
reduced by any commitment wasted in under-utilized hours. Note that commitment
under-utilization may result in negative savings. Total savings is the sum of this
signed savings over every hour in the window.

## Data & tools

- **`output/candidate_dataset.parquet`** — anonymized hourly cost & usage. Every
  column is described in [`docs/data_dictionary.md`](../data_dictionary.md). Derive
  on-demand unit rates from it (`on_demand_cost / usage_amount`).
- **`output/pricing_options_filtered.parquet`** — the commitment rate
  table, scoped to the instances and regions in the dataset. Use it to find the
  discounted rate — and therefore the discount — for each kind of usage.
- The [`notebooks/demo.ipynb`](../../notebooks/demo.ipynb) starter and your own AI
  agents are yours to use.

## Deliverables

1. **The optimal commitment level and its savings curve.** The single best
   commitment level, and the curve of total dollars saved as a function of
   commitment level — so the shape of the tradeoff, and why your answer is the
   maximum, is visible.
2. **A reproducible analysis.** Runnable code (a notebook is fine) that derives the
   result from the dataset and the pricing table, so we can re-run it.
3. **A short presentation — to the hiring manager and our Head of Product —
   proposing how we would explain, _in the product_, the savings a commitment
   achieved to a non-technical user.** Imagine the customer is a layperson opening
   the app: what is the clearest, most honest way to show them what the commitment
   saved them? This is a product-communication deliverable, grounded in your
   analysis.

## What we're looking for

We care as much about *understanding* as about the number. Be ready to explain and
defend your model: why the discounted-dollar sizing and the decreasing-discount
allocation matter, what assumptions you made (how you treated the partial current
month, eligibility, hours with no usage), and where the answer is sensitive. A
confident, well-communicated result you genuinely understand beats a black-box
number.

This is one instance of what we look for across every challenge here — using agents
to go fast without going into **understanding debt**. See
[Understanding debt](../understanding_debt.md).

---

**Data & references:** [data dictionary](../data_dictionary.md) · [AWS discount cheat sheet](../aws_discount_cheatsheet.md) · dataset `output/candidate_dataset.parquet`, pricing `output/pricing_options_filtered.parquet`.

**With your submission:** an [understanding ledger](../understanding_ledger.md). See the [challenge overview](./README.md) for how the whole set is meant to be approached.
