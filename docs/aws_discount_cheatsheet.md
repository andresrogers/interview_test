# AWS Commitment Discount Cheat Sheet

A quick reference to the subtler rules of how AWS commitment discounts apply to
usage. These rules are easy to state and easy to get subtly wrong — they decide
*which* usage a commitment covers and *in what order*, which is exactly what
determines the savings a commitment produces.

## The instruments (broad → specific)

| Instrument | Scope it covers | Flexibility | Discount |
|---|---|---|---|
| **On-Demand** | n/a — full published rate | total | none |
| **Spot** | spare capacity, interruptible | n/a | deep, but its own rate (see rule 2) |
| **Compute Savings Plan** | all EC2 (any region/family/size/OS/tenancy), Fargate, Lambda | highest | lowest of the commitments |
| **Database Savings Plan** | newer database families (any region/size), **including serverless databases that no RI can cover** | high (within database) | low (broad SP) |
| **EC2 Instance Savings Plan** | one instance **family** in one **region** (any size/OS/tenancy within it) | medium | higher than Compute SP |
| **Reserved Instance (RI)** | one specific config: service + region + instance type/family + platform + tenancy | lowest | highest | 

Savings Plans are sold as an **hourly dollar commitment** (committed spend at the
plan's discounted rates) for a 1- or 3-year term. RIs commit to a specific
configuration for a term. RIs exist for many services (EC2, RDS, ElastiCache,
OpenSearch, Redshift, …) **but cannot cover serverless databases**; Savings Plans
cover compute (EC2/Fargate/Lambda), **database** (newer families, including
serverless), and SageMaker.

In this dataset the `commitment_key` prefix records what can cover a row:
`AWS#Compute` marks Compute-Savings-Plan-coverable usage, and `AWS#Database` marks
Database-Savings-Plan-coverable usage (serverless-database rows are covered here
and nowhere else).

## How discounts get applied — the rules that bite

1. **Hourly, most-discounted usage first.** A Savings Plan is applied **each
   hour**, to the eligible usage with the **highest discount percentage first**,
   then the next, and so on until the hour's committed amount is exhausted. It is
   **use-it-or-lose-it per hour** — committed dollars not consumed in an hour are
   wasted (no rollover), and usage beyond the commitment that hour bills at
   on-demand rates.

2. **Spot is never discounted below the spot rate.** No Savings Plan or RI
   applies to Spot usage — Spot is already its own (variable) rate, and
   commitments leave it untouched.

3. **Most specific instrument first.** When more than one instrument could cover
   the same usage, the **most specific one is applied first** — a Reserved
   Instance or an EC2 Instance Savings Plan before a (broader) Compute Savings
   Plan, and an RDS Reserved Instance before a (broader) Database Savings Plan.
   The broad commitment only sees what's left after the specific ones have taken
   their share. Serverless database usage has no RI at all, so only the Database
   Savings Plan can cover it.

4. **Tie-break by commitment size.** If two instruments of the **same
   specificity** could apply to the same usage, the **larger commitment is
   applied first.**

## Sizing, terms, and what you pay

- A Savings Plan is sized in **discounted dollars per hour** — committed spend at
  *plan* rates, **not** on-demand dollars. A commitment of \$X/hr therefore covers
  *more* than \$X of on-demand spend, because the covered usage's on-demand value
  exceeds its discounted value.
- **Term:** 1-year vs 3-year — a longer term earns a larger discount.
- **Payment option:** no-upfront / partial-upfront / all-upfront — more upfront
  earns a larger discount.
- You pay the **commitment regardless of usage**; the discount is on the usage it
  covers. Unused commitment is pure waste.

## Modeling gotchas

- **Coverage ≠ utilization.** Coverage is the share of eligible spend you've
  committed to; utilization is the share of your commitment that actually gets
  used. A commitment can be 100% utilized but cover little, or cover a lot but
  sit half-used.
- **Per-hour waste from variability.** Because the commitment is use-it-or-lose-it
  hourly, variable usage wastes commitment in low hours. Sizing is a balance:
  more commitment covers more high-discount usage but risks more idle waste.
- **Effective savings rate** = amortized cost (what you actually pay, including
  amortized upfront and *including* unused-commitment waste) vs the on-demand
  equivalent. Leaving waste out flatters the number.
- **Commitments are forward-looking.** Sizing on historical usage assumes the
  future resembles the past; a usage regime change (growth, migration, shutdown)
  can turn a once-optimal commitment into over- or under-commitment.
