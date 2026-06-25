# Challenge 1 Summary

Headline effective savings rate: 11.52%

## Headline

- Analysis window: 2025-07 to 2026-05
- On-demand equivalent: $963,836.65
- Amortized actual cost: $852,808.22
- Savings dollars: $111,028.43
- Commitment discount: $105,826.33
- Spot market savings: $6,873.12
- Unused commitment waste: $7,001.90
- Other / reconciliation: $5,330.88

## What The Metric Means

Effective savings rate is defined as `(sum(on_demand_cost) - sum(amortized_cost)) / sum(on_demand_cost)` over complete billing periods only.

The monthly bridge starts from the on-demand equivalent, subtracts commitment discount and Spot market savings, adds unused commitment waste, applies other / reconciliation, and lands on actual amortized cost.

Spot is included in the account's actual cost because it is real spend, but Spot market savings are shown separately from commitment discount.

Unused commitment waste can coexist with Spot in the same month because commitments do not apply to Spot, and waste can happen in different workloads or lower-usage hours while Spot spend happens elsewhere.

## Main Drivers

### Commitment discount by instrument

- Compute Savings Plan: $87,211.17 realized commitment savings.
- Reserved Instance: $18,615.16 realized commitment savings.

### Spot cost treatment

- Spot (non-commitment cost): $6,873.12 lower than on-demand, included in account cost but shown separately from commitment savings.

### Waste by instrument

- Reserved Instance: $7,001.90 unused commitment cost.

### Savings by service

- AmazonEC2: $56,859.35 net savings.
- AmazonECS: $39,248.51 net savings.
- AmazonRDS: $10,449.46 net savings.

## Key Takeaways

- The denominator includes all in-scope on-demand spend for the chosen window.
- Spot is included as account cost, but Spot market savings are separated from commitment discount so the bridge stays honest.
- Unused commitment waste is shown as a cost increase instead of being folded into net savings.
- Service, commitment, and instrument decompositions are written to `tables/` for drill-down and later presentation use.

## Anomaly Review Note

No material savings anomaly found inside the complete-month window. Dataset artifact noted: Found 13 off-hour `Unused Commitment` rows; analysis uses normalized hourly buckets while preserving raw timestamps.

## Assumptions And Risks

- Incomplete billing periods are excluded rather than scaled up.
- This challenge reports current realized savings only; it does not estimate a better future commitment level.
- `Unused Commitment` is treated as paid waste based on the dataset's `cost_type` semantics.
