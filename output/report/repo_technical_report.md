# Repo Technical Report

## 1. Technical framing

This repo is **not an ML repo** in the usual sense. There are no learned models, no `scikit-learn`, no neural nets, and no forecasting model implemented yet. The implemented work is a **deterministic analytics + optimization pipeline** built mostly with:

- **DuckDB**: scan parquet, join pricing, run SQL aggregations.
- **pandas**: post-SQL shaping, groupby tables, metrics payloads.
- **NumPy**: vectorized hourly commitment allocation math.
- **matplotlib**: charts only.
- **stdlib (`json`, `pathlib`, `sys`)**: orchestration and file writes.

The architecture is intentionally simple:

- `pipeline/challenge_nn_*.py` = thin orchestration scripts.
- `src/*.py` = reusable logic per challenge.
- `src/commitments.py` = the core optimizer.
- `src/metrics.py` = reusable formulas.
- `src/data_quality.py` = readiness and normalization.
- `src/cost_data.py` = parquet → DuckDB views.

## 2. End-to-end execution pattern

Almost every challenge follows this order:

1. `connect()` to DuckDB.
2. `load_usage()` and `load_pricing()` from parquet.
3. `data_quality_issues()` and `assert_no_fatal_issues()`.
4. `ensure_ready_usage_view()` to create `usage_ready` with normalized `analysis_timestamp`.
5. Select the billing window.
6. Run challenge-specific SQL / pandas / optimization logic.
7. Write CSV tables, plots, `summary.md`, `methodology.md`, `metrics.json`.

Quick pseudocode:

```text
con = connect()
load_usage(con)
load_pricing(con)
issues = data_quality_issues(con)
assert_no_fatal_issues(issues)
ensure_ready_usage_view(con)
periods = billing_period_completeness(con)

challenge_specific_analysis(...)
write_tables(...)
write_reports(...)
plot(...)
```

## 3. Shared formulas and algorithms

### 3.1 Readiness normalization

Implemented in `src/data_quality.py`.

Main technical rule:

```text
analysis_timestamp = date_trunc('hour', timestamp)
timestamp_was_normalized = timestamp != date_trunc('hour', timestamp)
```

This is a **read-only derived view**, not source mutation.

### 3.2 Basic cost formulas

Implemented in `src/metrics.py` and `src/challenge_02.py`.

```text
on_demand_rate = on_demand_cost / usage_amount
discounted_cost = usage_amount * discounted_rate
gross_savings_if_fully_covered = on_demand_cost - discounted_cost
savings_dollars = on_demand_cost - amortized_cost
effective_savings_rate = savings_dollars / on_demand_cost
coverage_rate = covered_on_demand_cost / eligible_on_demand_cost
utilization_rate = consumed_commitment / paid_commitment
```

`safe_ratio()` returns `None` for zero/negative denominators instead of inventing a number.

### 3.3 Exact hourly commitment allocator

Core file: `src/commitments.py`.

This is the most important technical component in the repo.

#### Step A: build hourly inputs

`build_hourly_inputs()` groups by `analysis_timestamp`, then sorts rows inside each hour by:

1. `discount_pct` descending
2. `discounted_cost` descending

Then it precomputes cumulative arrays:

- `cumulative_discounted_costs`
- `cumulative_gross_savings`
- `cumulative_on_demand_costs`
- `segment_slopes = gross_savings / discounted_cost`

Interpretation: each hour becomes a **piecewise-linear savings curve**.

#### Step B: evaluate one commitment point

`_covered_components()` and `evaluate_commitment()` compute the result for a fixed commitment `C`.

For each hour:

```text
covered_discounted_cost = min(C, total_discounted_cost_hour)
waste_hour = C - covered_discounted_cost
```

Full rows are covered first via `searchsorted` on cumulative discounted cost. If the commitment cuts through a partial row, the code prorates that row linearly:

```text
fraction = remainder / discounted_cost_of_boundary_row
covered_gross_savings += fraction * row_gross_savings
covered_on_demand_cost += fraction * row_on_demand_cost
```

Then across all hours:

```text
total_savings = total_gross_savings - total_waste
```

This is a deterministic simulator, not a stochastic model.

#### Step C: exact optimizer, not brute force

`optimize_commitment()` does **exact breakpoint sweep**.

Key idea:

- Each hour contributes breakpoints at cumulative discounted spend levels.
- Between breakpoints, total savings is linear.
- Therefore the global optimum must occur at a breakpoint.

Algorithm:

```text
for each hour:
    slopes = [segment_slope_1, ..., segment_slope_k, -1]
    add slope-change events at each cumulative_discounted_cost breakpoint

sort all breakpoints globally
walk left-to-right:
    total_savings += current_slope * delta_commitment
    update best point if savings improves
    apply slope-change event
```

Why this matters: it is much better than naive grid search. It is effectively an **exact piecewise-linear optimization** over all candidate commitment levels.

## 4. Challenge-by-challenge technical logic

### Challenge 0 — Data readiness

Files:

- `pipeline/challenge_00_data_readiness.py`
- `src/challenge_00.py`
- `src/data_quality.py`

Technical approach:

- DuckDB schema inspection: required columns in usage/pricing.
- SQL checks for off-hour timestamps, negative values, non-finite costs.
- SQL completeness check:

```text
observed_hours = count(distinct date_trunc('hour', analysis_timestamp))
expected_hours = hours_in_calendar_month
is_complete = observed_hours == expected_hours
```

- pandas only assembles exported tables and metrics.

Pseudocode:

```text
outputs = {
  issues,
  billing_period_completeness,
  schema_summary,
  null_profile,
  cost_type_profile,
  monthly_dataset_profile,
}
metrics = readiness_metrics(outputs)
```

Why this method: later optimization is hourly, so timestamp integrity is a hard prerequisite.

### Challenge 1 — Effective savings rate

Files:

- `pipeline/challenge_01_effective_savings_rate.py`
- `src/challenge_01.py`
- `src/metrics.py`

Technical approach:

- SQL aggregation in DuckDB across complete months only.
- Reusable helper `_aggregate_frame()` groups by different dimensions:
  - service
  - commitment
  - cost type
  - instrument family
  - billing period
- pandas adds derived columns with `add_effective_savings_columns()`.

Important rule-based classification:

```text
if cost_type == 'Spot Usage' -> Spot (non-commitment cost)
elif commitment_key like 'AWS#Compute%' -> Compute Savings Plan
elif commitment_key like 'AWS#Database%' -> Database Savings Plan
elif commitment is not null -> Reserved Instance
...
```

Then the monthly bridge decomposes savings into:

- commitment realized savings
- Spot savings vs on-demand
- unused commitment waste
- reconciliation residual

Pseudocode:

```text
service = aggregate(by=product_code)
commitment = aggregate(by=commitment, commitment_key, cost_type)
instrument_detail = aggregate(by=instrument_family, cost_type)
monthly_detail = aggregate(by=billing_period, instrument_family, cost_type)

instrument = summarize_commitment_vs_spot_vs_waste(instrument_detail)
monthly_summary = summarize_monthly_bridge(monthly_detail)
headline = effective_savings_metrics(monthly)
```

Why this method: this challenge is descriptive, not predictive. Grouped SQL + accounting decomposition is the right tool.

### Challenge 2 — Optimal commitment level

Files:

- `pipeline/challenge_02_optimal_commitment.py`
- `src/challenge_02.py`
- `src/commitments.py`

Technical approach:

1. `choose_analysis_window()` selects the latest 3 complete months.
2. `load_optimizer_input()` performs the critical SQL join from usage to pricing.
3. `valid_optimizer_rows()` filters to valid economics.
4. `build_hourly_inputs()` converts rows to hourly piecewise-linear inputs.
5. `optimize_commitment()` solves the exact optimum.
6. `hourly_summary()` creates per-hour diagnostics.

Critical SQL-derived features:

```text
discounted_rate = pricing.rate
on_demand_rate = on_demand_cost / usage_amount
discounted_cost = usage_amount * pricing.rate
gross_savings_if_fully_covered = on_demand_cost - usage_amount * pricing.rate
discount_pct = 1 - pricing.rate / (on_demand_cost / usage_amount)
```

Validation logic quarantines rows when:

- `usage_amount <= 0`
- missing pricing
- invalid rates
- discounted cost < 0
- gross savings < 0
- discounted rate > on-demand rate

Pseudocode:

```text
joined = load_optimizer_input(...)
eligible = valid_optimizer_rows(joined)
hourly_inputs = build_hourly_inputs(eligible, analysis_hours)
curve, optimum = optimize_commitment(hourly_inputs)
hourly = hourly_summary(optimum.commitment_per_hour, hourly_inputs)
```

Why this method: the business question is a 1-D exact optimization problem, so piecewise-linear breakpoint search is fast and mathematically precise.

### Challenge 3 — Window sensitivity

Files:

- `pipeline/challenge_03_window_sensitivity.py`
- `src/challenge_03.py`
- reuses `src/challenge_02.py` + `src/commitments.py`

Technical approach:

- `build_window_specs()` creates two families of windows:
  - trailing: 1m, 2m, 3m, 6m
  - anchored: every 3-month slice in history
- `window_result_rows()` reruns the **same optimizer** on every window.
- `monthly_regime_summary()` computes month-level compute spend shifts.

This is essentially a **stability / sensitivity analysis** over the optimizer.

Recommendation logic in `_recommended_rule()`:

- default: recent 3-month window
- if 3m vs 6m optima diverge by >20%, cap recommendation at the lower level

Pseudocode:

```text
specs = build_window_specs(complete_periods)
for spec in specs:
    joined = load_optimizer_input(spec.periods)
    eligible = valid_optimizer_rows(joined)
    hourly_inputs = build_hourly_inputs(eligible, analysis_hours(spec.periods))
    optimum = optimize_commitment(hourly_inputs)
    collect(optimum)

regime = monthly_regime_summary(...)
recommendation = rule_based_window_selection(results, regime)
```

Why this method: no new optimizer is needed. The question is robustness of the existing optimizer under different historical slices.

### Challenge 4 — Baseline realized savings backtest

Files:

- `pipeline/challenge_04_baseline_realized_savings.py`
- `src/challenge_04.py`
- reuses `src/challenge_02.py` + `src/commitments.py`

Technical approach:

- `choose_baseline_backtest_window()` chooses an anchor month about 9 months back.
- `extract_baseline_commitment()` reads the final available `baseline_max` in that anchor month.
- That baseline becomes a fixed decision variable.
- The code then evaluates:
  1. fixed baseline commitment
  2. hindsight-optimal fixed commitment on the same forward window

Monthly backtest features are built by `monthly_backtest()`:

```text
paid_commitment = consumed_commitment + unused_commitment_waste
effective_savings_rate = net_savings / eligible_on_demand_cost
coverage_rate = covered_on_demand_cost / eligible_on_demand_cost
utilization = consumed_commitment / paid_commitment
```

Pseudocode:

```text
anchor_period, forward_periods = choose_baseline_backtest_window(periods)
baseline_commitment = extract_baseline_commitment(anchor_period)
joined = load_optimizer_input(forward_periods)
eligible = valid_optimizer_rows(joined)
hourly_inputs = build_hourly_inputs(eligible, analysis_hours(forward_periods))

baseline = evaluate_commitment(baseline_commitment, hourly_inputs)
curve, optimum = optimize_commitment(hourly_inputs)
compare(baseline, optimum)
```

Why this method: this is a **historical policy backtest**, not a new optimization problem.

### Challenge 5 — Audit current commitments

Files:

- `pipeline/challenge_05_audit_commitments.py`
- `src/challenge_05.py`

Technical approach:

- Pull only rows with non-null `commitment` and cost types in:
  - `Usage with Discount`
  - `Unused Commitment`
- Build per-commitment inventory.
- Build monthly per-commitment utilization table.
- Apply a **rule-based classifier**, not ML.

Per-commitment features:

```text
covered_on_demand = sum(on_demand_cost for discounted rows)
consumed = sum(amortized_cost for discounted rows)
waste = sum(amortized_cost for unused rows)
paid = consumed + waste
utilization = consumed / paid
waste_share = waste / paid
residual_same_products = remaining on-demand spend in same products
```

Classification heuristic:

```text
if utilization < 0.85 or waste_share > 0.15:
    over_committed
elif utilization >= 0.98 and residual_same_products > 0:
    under_committed
else:
    well_sized
```

Pseudocode:

```text
audit_rows = load_commitment_audit_rows(window)
inventory = build_commitment_inventory(audit_rows, account_usage)
monthly = build_commitment_monthly(audit_rows)
portfolio = aggregate_inventory(inventory)
```

**Why this method**: *the task is portfolio reconstruction and diagnostics. A transparent heuristic is preferable to a learned model.*

### Challenge 6 — Coverage/utilization frontier

Files:

- `pipeline/challenge_06_coverage_utilization_frontier.py`
- `src/challenge_06.py`
- reuses `src/commitments.py` and Challenge 2 input logic

Technical approach:

- Reuse Challenge 2 optimizer inputs and curve.
- `frontier_candidates()` samples exact breakpoints if the curve is too dense for plotting.
- `commitment_frontier()` evaluates many candidate commitments with the same exact simulator.
- `current_commitment_posture_from_inventory()` imports current compute posture from Challenge 5 CSV.

Recommendation algorithm:

```text
max_savings = frontier.total_savings_dollars.max()
efficient = rows where savings >= 0.95 * max_savings
recommended = argmax over efficient rows of
    (average_utilization, total_savings_dollars)
```

So this is not a formal Pareto solver, but a **simple efficient-frontier heuristic**:

- keep at least 95% of best savings
- among those, choose the highest-utilization point

Pseudocode:

```text
curve = optimize_commitment(hourly_inputs).curve
candidates = frontier_candidates(curve)
frontier = commitment_frontier(candidates, hourly_inputs)
current = current_commitment_posture_from_inventory(challenge_05_inventory)
metrics = build_metrics(frontier, current, ...)
```

Why this method: the business decision is multi-objective. The code exposes the tradeoff without introducing a complex optimizer.

## 5. What technical work is still missing

Per docs, two harder tasks are still unimplemented in `output/`:

- **Commitment basket**: a multi-instrument allocation problem with precedence and no double-counting.
- **Forecast and commit**: the first place where a real time-series / predictive model would likely appear.

So today the repo is best described as:

> a DuckDB + pandas + NumPy analytical system with an exact piecewise-linear commitment optimizer and several downstream scenario / policy analyses.

Notable technical conclusion: the strongest algorithm in the current codebase is `src/commitments.py::optimize_commitment()`. Everything from Challenges 2, 3, 4, and 6 is built by reusing that exact optimizer under different windows, policies, or decision rules.
