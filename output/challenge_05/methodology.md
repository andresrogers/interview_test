# Challenge 5 Methodology

## Steps

1. Keep the most recent three complete billing periods.
2. Pull only rows with a non-null commitment and cost types `Usage with Discount` or `Unused Commitment`.
3. Aggregate by commitment for covered on-demand spend, consumed commitment, unused waste, and utilization.
4. Build a monthly utilization table from the same commitment rows.
5. Classify each commitment as well-sized, under-committed, or over-committed with simple evidence-based rules.
6. Run explicit reconciliation checks from monthly rows back to inventory totals.

## Validation Notes

- Warnings: Found 13 off-hour `Unused Commitment` rows; analysis uses normalized hourly buckets while preserving raw timestamps., Excluded partial billing periods from commitment audit: 2026-06.
- Portfolio coverage denominator = eligible on-demand cost on all commitment-eligible rows in the same window.
- Portfolio utilization denominator = paid commitment dollars from covered plus unused rows.
