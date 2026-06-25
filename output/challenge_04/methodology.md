# Challenge 4 Methodology

## Steps

1. Keep complete billing periods only.
2. Pick the compute baseline anchor month about nine months before the latest complete month.
3. Read the last available compute `baseline_max` in that anchor month and treat it as the fixed commitment level.
4. Reuse the Challenge 2 compute pricing join and hourly allocation logic on the forward window only.
5. Evaluate the fixed baseline and the hindsight-optimal fixed commitment over the same forward window.
6. Write monthly tables, hourly tables, plots, and reconciliation checks.

## Validation Notes

- Reconciliation checks live in `metrics.json` for baseline and optimal scenarios.
- Coverage denominator = eligible compute on-demand cost.
- Utilization denominator = paid commitment dollars.
- Warnings: Found 13 off-hour `Unused Commitment` rows; analysis uses normalized hourly buckets while preserving raw timestamps., Excluded partial billing periods from backtest: 2026-06.
