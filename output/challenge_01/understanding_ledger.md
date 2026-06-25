# Understanding Ledger

## What I Verified Myself

- Verified the effective savings formula matches the challenge doc: savings over on-demand counterfactual.
- Verified billing period completeness from distinct normalized hourly buckets before selecting the window.
- Verified Spot is treated as account cost in the headline but separated from commitment-derived savings in the instrument decomposition.
- Verified monthly sums reconcile back to the headline totals within a small floating-point tolerance.

## What I Delegated And Trusted

- Trusted DuckDB to scan parquet files and produce the SQL aggregates once the readiness checks passed.
- Trusted matplotlib for direct plot rendering after checking the underlying tables.

## What I'm Unsure Of

- Whether stakeholders would prefer the partial current month to appear as a flagged appendix instead of being excluded from the headline rate.
- Whether some commitments classified as waste should be interpreted differently in edge AWS billing cases outside this dataset.
- Whether commitment ARN-level metadata would materially change the instrument-family inference for some covered rows.
- Challenge 1 does not test alternate windows, so rate stability outside 2025-07 to 2026-05 is not established here.

## Anomaly Review

No material savings anomaly found inside the complete-month window. Dataset artifact noted: Found 13 off-hour `Unused Commitment` rows; analysis uses normalized hourly buckets while preserving raw timestamps.
