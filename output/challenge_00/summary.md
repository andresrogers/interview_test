# Challenge 0 Summary

Dataset ready for analysis: yes

## Headline

- Usage rows profiled: 20,901,528
- Pricing rows profiled: 10,955
- Complete billing periods: 2025-07, 2025-08, 2025-09, 2025-10, 2025-11, 2025-12, 2026-01, 2026-02, 2026-03, 2026-04, 2026-05
- Partial billing periods: 2026-06
- Normalized off-hour rows: 13

## What Was Checked

- Required usage and pricing columns.
- Off-hour timestamps, negative values, and non-finite costs.
- Null profile by column.
- Monthly row and cost profile.
- Monthly on-demand-equivalent load trend, duplicate checks, ratio diagnostics, commitment consistency, and pricing key coverage.

## Cleaning Applied

- Raw `timestamp` is preserved.
- `analysis_timestamp` truncates rows to the analysis hour.
- `timestamp_was_normalized` marks rows that needed normalization.

## Anomaly Review Note

No fatal anomaly found. The notable data artifact was off-hour `Unused Commitment` rows, and 13 rows were normalized into `analysis_timestamp` while preserving `source_timestamp`.

## Additional Diagnostics

- Monthly AWS demand trend from complete months: growing across 2025-07 to 2026-05.
- Last observed month excluded from trend interpretation: yes.
- Exact duplicate rows: 0.
- Duplicate hourly line keys: 108,029.
- Numeric anomaly rows across explicit sanity checks: 0.
- Unexpected `cost_type` values: none.
- Unexpected `commitment_key` prefixes: none.
- Commitment consistency failures: 0.
- Usage rows missing pricing matches: 19,294,842 (81.28%).

## Assumptions And Risks

- Challenge 0 normalizes timestamp artifacts only; it does not rewrite financial values.
- Partial periods are flagged, not backfilled.
- Later challenges should prefer `analysis_timestamp` for hourly completeness logic.
