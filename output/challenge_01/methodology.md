# Challenge 1 Methodology

## Window

- Included complete billing periods: 2025-07, 2025-08, 2025-09, 2025-10, 2025-11, 2025-12, 2026-01, 2026-02, 2026-03, 2026-04, 2026-05
- Excluded partial billing periods: 2026-06

## Steps

1. Load the raw usage dataset and pricing reference directly from the documented parquet files.
2. Build the shared `usage_ready` analysis view with normalized hourly buckets.
3. Review shared readiness warnings and stop only on fatal issues.
4. Aggregate `on_demand_cost` and `amortized_cost` by month, service, commitment, instrument family, and cost type.
5. Compute the monthly bridge components: commitment discount, Spot market savings, unused commitment waste, and other / reconciliation.
6. Save tables, plots, and report markdown.

## Notes

- The savings-by-commitment table keeps `cost_type` so `Unused Commitment` stays visible as waste evidence.
- Instrument families are inferred from commitment scope: `AWS#Compute*`, `AWS#Database*`, and `AWS#Sagemaker*` map to Savings Plan families; other covered commitments are treated as Reserved Instances.
- Spot rows are included in actual cost but called out separately as Spot market savings, not commitment discount.
- Validation warnings: Found 13 off-hour `Unused Commitment` rows; analysis uses normalized hourly buckets while preserving raw timestamps..
