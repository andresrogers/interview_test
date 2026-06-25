# Challenge 3 Methodology

## Window Set

- Trailing windows: 1, 2, 3, and 6 complete months when available.
- Anchored windows: every 3-complete-month slice across the available history.

## Steps

1. Load the shared compute-eligible non-Spot optimizer input used in Challenge 2.
2. Rebuild hourly candidate arrays for each evaluation window.
3. Re-run the exact breakpoint optimizer for every window.
4. Record optimal commitment, net savings, utilization, coverage, and eligible spend totals.
5. Aggregate monthly compute-eligible discounted spend to show where the history changes regime.
6. Recommend a window rule that favors forward safety when recent and broad windows disagree.

## Validation Notes

- Warnings: Found 13 off-hour `Unused Commitment` rows; analysis uses normalized hourly buckets while preserving raw timestamps., Window sensitivity spread in optimal commitment is $11.71/hour across evaluated windows..
- Only complete billing periods are eligible for window construction.
- The anomaly review is embedded in `summary.md`, not split into a separate challenge.
