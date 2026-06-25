# Challenge 2 Methodology

## Window

- Included complete billing periods: 2026-03, 2026-04, 2026-05
- Excluded partial periods: 2026-06
- Excluded older complete periods: 2025-07, 2025-08, 2025-09, 2025-10, 2025-11, 2025-12, 2026-01, 2026-02

## Pricing View

- Instrument: `compute_savings_plan`
- Term: 36 months
- Payment option: `no_upfront`
- Offering class: `savings_plan`

## Steps

1. Load raw parquet inputs into DuckDB and build the shared `usage_ready` view.
2. Keep only the most recent three complete billing periods.
3. Select `AWS#Compute*` rows, exclude Spot, and join one Compute Savings Plan rate per `price_list_key`.
4. Quarantine zero-usage rows, missing pricing matches, and rows where discounted economics are invalid.
5. For each hour, sort valid rows by descending discount percentage and build cumulative discounted-cost breakpoints.
6. Sweep commitment breakpoints exactly and evaluate the best commitment with hourly waste, utilization, and coverage metrics.
7. Save the curve, hourly summary, markdown reports, and presentation-ready plots.

## Validation Notes

- Warnings: Found 13 off-hour `Unused Commitment` rows; analysis uses normalized hourly buckets while preserving raw timestamps., Excluded partial billing periods from optimization: 2026-06, Used only the most recent three complete periods: 2026-03, 2026-04, 2026-05; older complete periods kept out of scope..
- Hours with no eligible Compute usage are still counted; any non-zero commitment in those hours becomes full waste.
- Coverage and utilization are reported separately because they use different denominators.
