# Challenge 00 doubts

## 1) How many `account_id` values are in `output/candidate_dataset.parquet`?

Confirmed from the parquet directly:

- **42 distinct `account_id` values**
- **20,901,528 total rows**

Interpretation:

- This is **not one AWS account**.
- It is **one organization / one customer environment with many linked AWS accounts**.
- This matches the data dictionary, which says: *“The dataset spans multiple linked AWS accounts under a single organization.”*

## 2) What did “normalization” of the 13 off-hour `Unused Commitment` rows actually do?

Short answer:

- It **only normalized the timestamp used for analysis**.
- It **did not change any cost, usage, or financial amount numerically**.
- There was **no prorating**, **no rescaling**, and **no 20-minutes-vs-40-minutes adjustment**.

### What the code actually does

`ensure_ready_usage_view()` in `src/data_quality.py` creates a derived view called `usage_ready`.

If the ready columns are not already present, it runs this logic:

```sql
create or replace view usage_ready as
select
  *,
  timestamp as source_timestamp,
  date_trunc('hour', timestamp) as analysis_timestamp,
  timestamp != date_trunc('hour', timestamp) as timestamp_was_normalized
from usage
```

Meaning:

- `source_timestamp`: preserves the raw source timestamp exactly.
- `analysis_timestamp`: truncates to the hour bucket for hourly analysis.
- `timestamp_was_normalized`: marks whether that truncation changed the timestamp.

Important:

- `on_demand_cost` unchanged
- `amortized_cost` unchanged
- `usage_amount` unchanged
- `commitment` unchanged
- source parquet unchanged

So “normalized” here means **hour-bucket normalization of the timestamp only**.

## 3) Evidence from the actual 13 rows

Direct checks on the parquet show:

- **all 13 rows** are `cost_type = 'Unused Commitment'`
- **all 13 rows** have `on_demand_cost = 0`
- **all 13 rows** have a non-null `commitment`
- **all 13 rows** have `baseline_covered = null`
- **all 13 rows** have `baseline_max = null`
- minutes are irregular: `2, 4, 13, 18, 41, 54`

Aggregate of those 13 rows:

- total `usage_amount` = **31,819.798611**
- total `on_demand_cost` = **0.0**
- total `amortized_cost` = **134.295188**

They land in these normalized hours:

- `2025-08-21 12:00:00` → 1 row
- `2025-11-11 18:00:00` → 1 row
- `2025-12-08 14:00:00` → 1 row
- `2025-12-09 12:00:00` → 3 rows
- `2025-12-16 09:00:00` → 6 rows
- `2026-01-05 09:00:00` → 1 row

Also important: those hours already contain many other rows. Example:

- `2025-12-16 09:00:00` has **2,896 total rows**, of which **6** are off-hour rows.

So the normalization did **not invent a new hour**. It only placed a few stray accounting rows into the existing hourly bucket where the rest of the dataset already lives.

## 4) Did we assume those rows represented only part of an hour?

No.

We did **not** assume:

- “timestamp at `12:41:57` means only 18 minutes belong in that hour”
- “unused commitment should be multiplied by `18/60` or `40/60`”
- “usage_amount` is a minute fraction that should be rescaled”

We specifically **did not do that** because the docs do not support that interpretation.

### Why prorating would have been unjustified

1. **The docs define the dataset grain as hourly already.**  
   Data dictionary: *“one row per hour per usage line.”*

2. **These are `Unused Commitment` accounting rows, not normal metered usage rows.**  
   The docs say `Unused Commitment` means committed capacity that went unused. That is a waste / billing line, not evidence of “20 minutes of real runtime”.

3. **`on_demand_cost` is zero on all 13 rows.**  
   That makes them clearly different from normal usage rows. They are not uncovered usage being billed for a partial interval.

4. **The minute offsets are irregular and do not form a coherent partial-hour rule.**  
   The rows appear at minutes 2, 4, 13, 18, 41, and 54. That looks like timestamp artifact / accounting emission timing, not a reliable duration measure.

5. **`usage_amount` is not safe evidence of duration here.**  
   For these rows, `usage_amount` is large and service-specific, while `on_demand_cost = 0`. For `Unused Commitment`, that quantity is not documented as “fraction of an hour to prorate”.

Because of all that, any numerical normalization would have been a **new business assumption**, not a defensible cleanup.

## 5) Why the chosen fix was reasonable

The chosen fix was:

- preserve raw source data
- add an analysis-only hour bucket
- keep a flag showing which rows needed that bucket normalization

This is the safest move because later challenges depend on **hourly completeness**:

- Challenge 2 optimizer allocates commitment **hour by hour**
- Challenge 3 compares windows of hourly commitment behavior
- Challenge 4 backtests hourly waste and coverage
- Challenge 5 audits commitment waste rows
- Challenge 6 builds a frontier from hourly commitment outcomes

If these 13 rows were left off-hour, then:

- hourly grouping would be inconsistent
- billing-period completeness by distinct hours could be distorted
- commitment waste lines could miss the hour bucket used by the rest of the analysis

So the fix is best described as:

> “Make the timestamps consistent with the documented hourly grain, without changing the economics.”

## 6) Compare solution vs what the docs said to do

### What the docs said

From the repo docs/data dictionary:

- data grain is hourly
- partial billing periods may exist
- `Unused Commitment` is a distinct cost type meaning paid waste
- agents should be explicit about assumptions

### What the solution assumed

The implemented Challenge 00 solution assumed:

1. The dataset is intended to be analyzed at **hourly grain**.
2. These 13 rows violate that shape only in timestamp formatting / emission timing.
3. Since they are `Unused Commitment` rows, they should remain as waste evidence but be placed into the correct hour bucket for analysis.
4. No financial rewrite should happen unless the docs explicitly justify one.

### Was that aligned with the docs?

Yes — mostly well aligned.

Why aligned:

- respects documented hourly grain
- preserves raw source data
- keeps waste rows visible
- avoids undocumented numeric assumptions

What was an implementation choice rather than an explicit doc instruction:

- The docs did **not explicitly say** “truncate off-hour waste rows to the hour”.
- That was a local engineering choice to reconcile actual data shape with the documented hourly grain.

I think it was the correct choice because it is:

- minimal
- reversible
- auditable
- financially conservative

## 7) Bottom line

- We were dealing with **42 account_id values**.
- “Normalization” of the 13 rows meant **timestamp normalization only**.
- It **did not** numerically alter `usage_amount`, `amortized_cost`, or `on_demand_cost`.
- It **did not** prorate rows by minute fraction.
- That choice is consistent with the docs: preserve economics, respect hourly grain, and treat `Unused Commitment` as waste evidence rather than as partial metered usage.

## 8) What exactly did Challenge 00 test, and was it enough?

Short answer:

- It was **not totally naive**.
- But it was also **not exhaustive**.
- It checked a small set of high-value structural/data-integrity conditions, then assumed the rest of the data was usable.

### What Challenge 00 explicitly tested

From `src/data_quality.py` and `src/challenge_00.py`, Challenge 00 checked:

1. **Required columns exist**
   - Usage table required: `timestamp`, `billing_period`, `product_code`, `usage_amount`, `on_demand_cost`, `amortized_cost`, `commitment`, `commitment_key`, `cost_type`
   - Pricing table required: `price_list_key`, `instrument_type`, `term_months`, `payment_option`, `rate`, `offering_class`

2. **Timestamp alignment to hourly grain**
   - Off-hour timestamps are checked.
   - If off-hour rows are only `Unused Commitment`, they are treated as a **warning**.
   - Any other off-hour cost types would have been a **fatal error**.

3. **Basic numeric sanity checks on usage**
   - `usage_amount < 0` → fatal
   - `on_demand_cost < 0` → fatal
   - non-finite `amortized_cost` → fatal

4. **Basic numeric sanity on pricing**
   - pricing `rate` non-finite or negative → fatal

5. **Null profile by column**
   - It computed null counts / null shares for every column in usage and pricing.
   - This was exported for inspection, but nulls were **not automatically treated as fatal** unless they caused one of the explicit checks above to fail.

6. **Billing period completeness**
   - It checked observed distinct hourly buckets vs expected hours in each month.
   - This is how it identified complete months vs partial `2026-06`.

7. **Basic EDA summary tables**
   - schema summary
   - null profile
   - cost type profile
   - monthly row counts and monthly cost totals

### What Challenge 00 did **not** test

This is the important part.

Challenge 00 did **not** explicitly test:

1. **Duplicate rows**
   - There is no duplicate check in `src/data_quality.py`.

2. **Duplicate hourly line keys / broken grain**
   - It did not explicitly verify that the same hourly usage line appears only once.

3. **Upper-bound outliers / unusually large values**
   - No z-score, percentile, Tukey/IQR, MAD, or threshold-based outlier detection.
   - No service-specific range checks like “is this usage_amount impossibly large for this instance type?”

4. **Cross-column financial reconciliation**
   - It did not verify relationships like:
     - `amortized_cost <= on_demand_cost` for covered rows
     - `usage_amount == 0` implications
     - cost/usage consistency by service family
     - whether all `Usage with Discount` rows have valid commitment linkage

5. **Categorical-domain validation**
   - It did not verify allowed sets of `cost_type`, `product_code`, `commitment_key` prefixes, etc.

6. **Business-semantic anomaly checks**
   - It did not test whether RDS / ElastiCache / EC2 rows follow deeper AWS-specific accounting expectations.

So yes: Challenge 00 was a **minimal readiness gate**, not a deep audit.

## 9) Are there duplicates in the data?

Challenge 00 did not check this, so I checked it separately from the parquet.

### Result

- **Exact duplicate rows: 0**
- **Repeated hourly line-key groups: 0**

The hourly line-key check grouped by:

- `timestamp`
- `billing_period`
- `product_code`
- `usage_type`
- `instance_type`
- `price_list_key`
- `commitment_key`
- `account_id`
- `commitment`
- `cost_type`

Interpretation:

- I found **no evidence of raw duplicated rows**.
- I also found **no evidence that the same hourly usage line was duplicated across multiple rows** for that key definition.

This is reassuring, but note:

- this was **my extra check**, not part of the original Challenge 00 implementation.

## 10) Did Challenge 00 handle outliers or out-of-range values well?

Only in a **very narrow sense**.

What it handled:

- negative `usage_amount`
- negative `on_demand_cost`
- non-finite `amortized_cost`
- non-finite / negative pricing `rate`

What it did **not** handle:

- suspiciously large but still positive values
- service-specific implausible values
- abnormal spikes relative to history
- weird but finite ratios like extreme cost-per-unit

So if by “outliers” you mean statistical or domain outliers, the answer is:

- **No, Challenge 00 did not really do that.**

It mainly enforced:

> “The file has the expected columns, no obviously impossible sign/NaN issues, and monthly/hourly structure is usable.”

## 11) Was the overall assumption “data is fine” too naive?

I would describe it this way:

- **Not naive for a first-stage structural gate**
- **Too light if you wanted a full production-grade data certification**

Why it was reasonable for this repo:

- the later challenges themselves perform additional validation where needed
- Challenge 02, for example, quarantines rows with missing pricing or invalid economics
- the repo is interview-scale, so the author likely chose the smallest readiness gate that prevents obvious downstream breakage

Why it may still feel insufficient:

- it did not prove absence of semantic anomalies
- it did not prove every service family obeys perfect business rules
- it did not give explicit duplicate assurance until I checked it separately
- it did not report statistical outlier analysis

## 12) What would I have wanted Challenge 00 to report to make us more at ease?

If I were strengthening Challenge 00, I would add these checks explicitly:

1. **Duplicate checks**
   - exact row duplicates
   - duplicate hourly line keys

2. **More numeric sanity checks**
   - non-finite `usage_amount`
   - non-finite `on_demand_cost`
   - zero `usage_amount` with non-zero costs
   - negative `amortized_cost` if not expected by accounting semantics

3. **Basic ratio checks**
   - extreme `on_demand_cost / usage_amount`
   - extreme `amortized_cost / usage_amount`

4. **Categorical validation**
   - unexpected `cost_type` values
   - unexpected `commitment_key` prefixes

5. **Commitment consistency checks**
   - `Usage with Discount` should usually have non-null `commitment`
   - `Unused Commitment` should have non-null `commitment`

6. **Simple outlier summaries**
   - top 20 rows by `usage_amount`
   - top 20 rows by `on_demand_cost`
   - top 20 rows by `amortized_cost`
   - monthly spike flags

7. **Cross-table quality checks**
   - share of usage rows missing matching `price_list_key` entries in pricing

## 13) Final comfort level after re-checking

After combining the original Challenge 00 checks with the extra duplicate/off-hour inspection I ran here, my view is:

- **Structural quality looks good enough for the rest of the repo's work**
- **No duplicate evidence found**
- **The only explicit timestamp artifact is narrow and well understood**
- **The readiness gate is still minimal, not exhaustive**

So the right interpretation is:

> Challenge 00 did enough to justify continuing the analysis, but not enough to claim the dataset was exhaustively certified in every possible way.

## 14) In Challenge 2, how was the 1-D optimization searched? Was it a grid over hourly commitment prices?

No grid search was used.

It was treated as an **exact 1-D piecewise-linear optimization** problem.

### What the code does

In `src/commitments.py`, `optimize_commitment()` builds the savings curve from **exact breakpoints**.

For each hour, after sorting eligible rows by **highest discount first**, it computes the cumulative discounted spend for that hour:

- first covered row breakpoint
- second covered row breakpoint
- third covered row breakpoint
- etc.

Those cumulative discounted-spend values are the points where the slope of total savings can change, because that is where an extra dollar/hour of commitment starts covering a new segment of usage.

So the candidate set was:

- `0`
- plus **every distinct cumulative discounted-cost breakpoint** across all hours

Then the algorithm walks those breakpoints in sorted order, updates the current slope, and keeps the best point it sees.

### So how granular was the search?

Granularity was **not** something like:

- `$1/hour steps`
- `$0.10/hour steps`
- or a sampled hourly price grid

Instead, granularity was exactly the set of **data-defined breakpoints** implied by the hourly usage rows.

That means the search was effectively **continuous for this model**, because between two adjacent breakpoints the objective is linear, so no interior point can beat the endpoints unless the slope is flat. For this reason, breakpoint search is the exact method here.

Bottom line:

- **not a grid search**
- **not approximate by price step size**
- **exact breakpoint sweep over the piecewise-linear savings curve**

## 15) In Challenge 4, was the backtest anchored on one month or many? Why that one?

It used **one fixed anchor month**, not many.

### What the docs asked for

The challenge prompt says:

> “Take the baseline commitment level for compute as of about nine months before the latest complete month, hold it fixed, and simulate it forward to now...”

That wording is singular, so the repo did **not** interpret this as “try many anchor months and average them.”

### What the implementation chose

`choose_baseline_backtest_window()` in `src/challenge_04.py` selects:

- the **latest complete month** as the end reference
- the **single complete month roughly nine months before that** as `anchor_period`
- the **next nine complete months** as the forward backtest window

So yes: **one anchor month only**.

### Why that specific one?

Partly **doc-driven**, partly an **implementation choice**.

Doc-driven part:

- the prompt explicitly asks for a baseline “as of about nine months before the latest complete month”

Implementation-choice part:

- we operationalized “about nine months before” as the **nearest complete billing month at that offset**
- and then took the **last available `baseline_max` value inside that anchor month** as the fixed baseline commitment

So:

- **using one anchor month** came from the prompt
- **using the nearest complete month and the last `baseline_max` inside it** was our implementation choice

It was a reasonable choice because the whole point of Challenge 4 is a **single historical decision, frozen, then backtested forward**. Using many anchors would have turned it into a sensitivity study instead, which is a different question.

## 16) In Challenge 5, why these classification heuristics? Why those cutoffs? What does `under_committed` mean in practice?

Short answer:

- this was **our heuristic**, not a threshold rule mandated by the docs
- the rule was meant to be an **interpretable audit label**, not a theorem
- the numbers (`0.85`, `0.15`, `0.98`) are **judgment cutoffs** chosen to separate clearly bad / clearly tight / middle cases

The code is:

```text
if utilization < 0.85 or waste_share > 0.15:
    over_committed
elif utilization >= 0.98 and residual_same_products > 0:
    under_committed
else:
    well_sized
```

### Meaning of each input

For one commitment:

- `utilization = consumed_commitment / paid_commitment`
  - how much of what you paid for actually got used
- `waste_share = unused_commitment_waste / paid_commitment`
  - how much of what you paid for turned into explicit idle waste
- `residual_same_products`
  - on-demand spend that remained on the table in the **same product family** that this commitment was already covering

Example:

- if a Compute Savings Plan covers EC2 rows very heavily, but there is still EC2 spend buying on-demand in the same window, that residual is evidence that the commitment may have been **too small** rather than too big

### Why `over_committed` means what it means

`over_committed` means: **you bought more commitment than the observed workload could consistently consume**.

That is why the rule flags either:

- `utilization < 0.85` → too much of the paid commitment sat idle overall
- `waste_share > 0.15` → too much of paid commitment became explicit unused-commitment waste

These are two views of the same problem: low use and high waste.

Why those numbers?

- `85%` says “this is not just tiny friction; this is materially underused”
- `15%` waste says “waste is large enough to call out, not just normal noise”

They are practical cutoffs, not AWS-official thresholds.

### What `under_committed` means in practice

`under_committed` does **not** mean the instrument wasted too little.

It means:

> “This commitment was basically fully used, and there was still more similar spend left uncovered on-demand.”

That is why the rule requires both:

- `utilization >= 0.98`
  - the commitment is effectively saturated
- `residual_same_products > 0`
  - there is still same-family on-demand spend that looks like extra coverage opportunity

In plain English:

- the commitment is **full all the time or almost full**
- but the account is still buying more of the same thing on demand
- so the likely problem is **too little commitment**, not too much

### Why `well_sized` is the middle bucket

`well_sized` means neither extreme signal was strong enough:

- not obviously loose / wasteful
- not obviously maxed out while similar spend leaks on-demand

So it is the “nothing clearly wrong from these simple signals” bucket.

### Important limitation

This is a **coarse heuristic classification**, not a full causal sizing model.

Its job was to produce readable audit labels from the data available in Challenge 5. A more rigorous version would calibrate thresholds, separate instrument types more carefully, and test sensitivity of the labels to those cutoffs.

Bottom line:

- `over_committed` = paid for more than the workload usually consumed
- `under_committed` = commitment stayed full, but similar spend still leaked to on-demand
- `well_sized` = neither problem is clearly visible from these summary signals
