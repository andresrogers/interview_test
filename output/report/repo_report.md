# Cloud Cost Challenge Report

## 1. What this repo is about

This repository is a compact FinOps case study over real-but-anonymized AWS cost data. The core problem is **cloud commitment sizing**: deciding how much infrastructure spend should be covered by Savings Plans or Reserved Instances instead of paying pure on-demand rates.

Why this matters:

- Commit too little: savings are left on the table.
- Commit too much: AWS still charges the commitment, so unused hours become waste.
- Commit to the wrong scope: the commitment may be fully used but still cover too little of the bill.

The practical goal across the challenges is to understand one organization’s AWS usage well enough to answer four business questions:

1. How much is the account saving today?
2. What single compute commitment would have been best on recent history?
3. How stable is that answer across time?
4. What does the current commitment portfolio look like, and what operating point should be recommended?

Repo intent also matters: this is an interview exercise designed to test **understanding**, not just output. The docs explicitly warn against “understanding debt”: using AI to produce answers you cannot explain or defend later.

## 2. Data and pricing context

### Data scope

- Source data: `output/candidate_dataset.parquet`
- Pricing reference: `output/pricing_options_filtered.parquet`
- Usage grain: **one row per hour per usage line**
- Period covered: complete months `2025-07` through `2026-05`, plus partial `2026-06`
- Size profiled in Challenge 0: **20,901,528 usage rows** and **10,955 pricing rows**

This is **not multiple customers**. It is one anonymized AWS organization with **multiple linked AWS accounts** under it. `account_id` identifies the internal AWS account that incurred usage.

### How AWS pricing works here

- **On-Demand**: pay full published rate, no commitment.
- **Spot**: cheaper market-based rate, already discounted, and **not covered** by commitments.
- **Savings Plans / Reserved Instances**: commit to spend/scope in exchange for discounts.

Important modeling rules from the repo docs:

- Savings Plans are sized in **discounted dollars per hour**, not on-demand dollars.
- Allocation happens **hour by hour**.
- Eligible usage is covered in **highest-discount-first** order.
- Commitments are **use-it-or-lose-it each hour**; unused commitment becomes waste.
- More specific instruments apply before broader ones.
- **Coverage** and **utilization** are different metrics and must stay separate.

### Usage dataset columns

| Column | Meaning |
|---|---|
| `timestamp` | UTC start of usage hour. |
| `billing_period` | AWS month, `YYYY-MM`. |
| `product_code` | AWS service, e.g. EC2, ECS/Fargate, Lambda, RDS. |
| `usage_type` | Metered usage dimension; also encodes region prefix. |
| `instance_type` | Resource type when applicable; null for non-instance usage. |
| `usage_amount` | Quantity in native unit: instance-hours, vCPU-hours, GB-hours, requests, etc. |
| `on_demand_cost` | What the row would cost at public on-demand rates. |
| `amortized_cost` | Actual attributed cost after existing commitments/discounts. |
| `price_list_key` | Exact join key into the pricing reference table. |
| `commitment_key` | Hierarchical eligibility scope used to determine what commitment types can cover the row. |
| `account_id` | Anonymized linked AWS account id inside the organization. |
| `commitment` | Anonymized ARN of the Savings Plan or RI that covered the row, if any. |
| `cost_type` | Billing treatment, e.g. `On Demand Usage`, `Usage with Discount`, `Unused Commitment`. |
| `baseline_covered` | Portion of on-demand cost a baseline-sized commitment would cover on that row. |
| `baseline_max` | Historical “safe-ish” baseline commitment level for that collapsed scope; read as a level, not something to sum. |

### Pricing table columns

| Column | Meaning |
|---|---|
| `price_list_key` | Joins to usage at AWS published price-list grain. |
| `instrument_type` | Commitment type, e.g. compute SP, EC2 SP, EC2 RI, RDS RI. |
| `offering_class` | Savings plan / standard RI / convertible RI. |
| `term_months` | Commitment term, usually 12 or 36 months. |
| `payment_option` | No upfront / partial upfront / all upfront. |
| `rate` | Discounted committed rate per usage unit. |
| `unit` | Pricing unit, e.g. hours. |
| `currency` | Pricing currency. |

Main join logic: compute on-demand rate from usage (`on_demand_cost / usage_amount`), join pricing by `price_list_key`, then compare that on-demand rate against the selected commitment rate.

## 3. Main assumptions used in the work

- Use **complete billing periods only** for headline metrics and optimization; partial `2026-06` is excluded.
- Normalize 13 off-hour `Unused Commitment` rows into hourly `analysis_timestamp` buckets, while preserving raw timestamps.
- Treat Spot separately from commitment savings because commitments do not discount Spot.
- For the compute-sizing work, use **Compute Savings Plan**, **3-year**, **no upfront**, **savings_plan** pricing.
- Optimize only over **Compute Savings Plan-eligible, non-Spot** usage for the compute challenges.
- Treat missing or invalid pricing matches as quarantined rows, not silent fills.
- Keep **coverage**, **utilization**, **waste**, and **net savings** separate.

## 4. What each completed challenge did and what it found

### Challenge 0 — Data readiness

Purpose: prove the dataset is safe to analyze before drawing conclusions.

What was done:
- Loaded usage and pricing into DuckDB.
- Built `usage_ready` with normalized hourly analysis buckets.
- Checked schema, nulls, timestamps, negative/non-finite values, and monthly shape.

Result:
- Dataset judged ready.
- Only notable artifact: **13 off-hour `Unused Commitment` rows**.
- Complete months: `2025-07` to `2026-05`; partial month: `2026-06`.

Takeaway: the main data risk is timing normalization on waste rows, not missing economics.

### Challenge 1 — Effective savings rate

Purpose: measure how much the organization actually saved versus pure on-demand pricing.

What was done:
- Aggregated complete months only.
- Compared total on-demand equivalent vs amortized actual cost.
- Broke the bridge into commitment discount, Spot savings, unused commitment waste, and reconciliation.

Result:
- **Effective savings rate: 11.52%**
- On-demand equivalent: **$963,836.65**
- Actual amortized cost: **$852,808.22**
- Net savings: **$111,028.43**
- Unused commitment waste: **$7,001.90**

Takeaway: the account is saving materially, mostly via commitments, but some savings are offset by real idle commitment waste.

### Challenge 2 — Optimal compute commitment

Purpose: find the single fixed Compute Savings Plan commitment that would have maximized savings over the latest 3 complete months.

What was done:
- Filtered to non-Spot `AWS#Compute*` usage.
- Joined one compute SP rate per `price_list_key`.
- For each hour, sorted usage by discount percentage and allocated commitment highest-discount-first.
- Evaluated exact commitment breakpoints to find the true optimum.

Result:
- **Optimal commitment: $23.14/hour**
- **Savings at optimum: $38,581.82**
- Effective savings rate on eligible compute spend: **40.46%**
- Utilization: **99.41%**
- Coverage: **94.05%**
- Waste at optimum: **$299.89**

Takeaway: recent compute usage supports a fairly high commitment with almost no idle waste; the main savings opportunity is on EC2 and ECS.

### Challenge 3 — Window sensitivity

Purpose: test whether the “optimal” commitment depends heavily on which historical window is chosen.

What was done:
- Re-ran the exact optimizer across trailing windows and anchored 3-month windows.
- Compared commitment levels, savings, utilization, and coverage across windows.
- Reviewed monthly discounted-spend changes to detect regime shifts.

Result:
- Recommended rule: **use the most recent 3 complete months**.
- Recommended commitment from that rule: **$23.14/hour**.
- Spread between lowest and highest 3-month optimum: **$11.71/hour**.
- Largest regime shift: **2025-12**, with discounted compute spend up **50.10%** month over month.

Takeaway: commitment sizing is highly window-sensitive because workload levels changed materially; older windows understate today’s compute level.

### Challenge 4 — Baseline backtest

Purpose: test how a historically “safe” baseline commitment would have performed if bought earlier and held fixed.

What was done:
- Picked compute baseline from anchor month **2025-08**.
- Froze that `baseline_max` level.
- Simulated it forward from `2025-09` to `2026-05` using the same hourly allocation logic as Challenge 2.
- Compared it with the hindsight-optimal fixed commitment for the same forward window.

Result:
- Fixed baseline commitment: **$18.77/hour**
- Realized savings: **$70,120.35**
- Realized savings rate: **30.56%**
- Waste: **$13,348.36**
- Hindsight-optimal fixed commitment: **$21.26/hour**
- Gap vs optimum: only **$342.87**

Takeaway: the old baseline was surprisingly close to hindsight optimum on total savings, but still produced material waste. That means “safe on history” did not stay safe hour by hour once usage regime changed.

### Challenge 5 — Audit current commitments

Purpose: reconstruct what commitments the organization already holds and assess whether they are well-sized.

What was done:
- Used only rows with non-null `commitment` plus `Usage with Discount` / `Unused Commitment` cost types.
- Aggregated by commitment ARN to compute paid commitment, consumed commitment, waste, utilization, and coverage evidence.
- Classified commitments as under-, over-, or well-sized using simple evidence rules.

Result:
- **29 commitments observed**
- Portfolio utilization: **97.24%**
- Portfolio coverage of eligible commitment spend: **29.14%**
- Waste: **$1,556.68** over the 3-month audit window
- **2 likely over-committed**, **27 likely under-committed**, **0 clearly well-sized**
- One RDS RI is the main problem: **5.53% utilization** and **$1,536.67** waste

Takeaway: the current portfolio is mostly fully used, which sounds good, but overall coverage is low. The organization appears **capacity-constrained on commitments**, with one clearly bad RI exception creating most of the waste.

### Challenge 6 — Coverage/utilization frontier

Purpose: map the trade-off between more coverage and more idle risk, then recommend an operating point.

What was done:
- Reused the Challenge 2 optimizer over the same 3-month compute window.
- Evaluated coverage, utilization, waste, and net savings at many exact commitment breakpoints.
- Read today’s compute posture from Challenge 5 inventory.
- Recommended the highest-utilization point that still retains at least 95% of peak savings.

Result:
- Max-savings point: **$23.12/hour**, **$38,581.66** savings
- Recommended operating point: **$21.51/hour**, **$37,156.94** savings
- Recommended coverage: **88.77%**
- Recommended utilization: **100.00%**
- Current compute posture: **$19.46/hour**, **79.98%** coverage, **100.00%** utilization, **$33,304.23** savings

Takeaway: current compute commitments look conservative. Moving from about **$19.46/hour** to **$21.51/hour** captures most of the available upside while preserving a no-idle posture.

## 5. Overall conclusions

1. **The organization is already saving money, but not near its full compute opportunity.** Current all-in realized savings are meaningful, yet the compute portfolio appears under-covered.
2. **Recent compute demand is materially higher than older windows suggest.** This is why recent 3-month optimization produces much higher commitments than older anchored windows.
3. **A single historical baseline is not automatically safe.** Even a baseline chosen from past usage can waste materially when future hourly usage softens or shifts.
4. **The current posture is conservative, not reckless.** Portfolio utilization is very high, but coverage is low. That usually means the business is leaving discounts on the table rather than overbuying broadly.
5. **The practical recommendation from the completed work is modest expansion, not an aggressive jump.** A compute operating point around **$21.5/hour** looks like the best balance between upside and downside on recent history.

## 6. What is not yet covered

The challenge docs also define two harder next steps that are **not yet implemented in `output/`**:

- **Optimal commitment basket**: mix multiple instruments without double-covering usage.
- **Forecast and commit**: size commitments forward under uncertainty, not just on hindsight history.

So this repo currently delivers a strong understanding of **today’s savings, recent optimal compute sizing, sensitivity to history choice, current portfolio posture, and the recommended compute operating point** — but not yet a full forward-looking multi-instrument buying strategy.
