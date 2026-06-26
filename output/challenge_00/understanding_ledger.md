# Understanding Ledger

## What I Verified Myself

- Verified the source schema against the documented required columns used by early challenges.
- Verified the off-hour timestamp artifact is isolated to `Unused Commitment` rows before treating it as a warning.
- Verified readiness stays in the shared analysis view instead of mutating the source file.

## What I Delegated And Trusted

- Trusted DuckDB to scan parquet files, build the readiness view, and generate the grouped EDA tables after checks passed.
- Trusted matplotlib for the row and cost profile plots after checking the underlying monthly tables.
- Trusted simple ranked diagnostics and month-over-month deltas for duplicate, ratio, and spike summaries rather than imposing statistical outlier thresholds.

## What I'm Unsure Of

- Whether future challenges need more normalization than hourly timestamp bucketing.
- Whether additional business-specific data rules will be needed once commitment optimization begins.
- Readiness currently normalizes timestamp shape only; it does not adjudicate semantic correctness of every cost row.
- Ranked ratio and spike outputs are diagnostics only; they do not prove invalid billing on their own.

## Anomaly Review

No fatal anomaly found. The notable data artifact was off-hour `Unused Commitment` rows, and 13 rows were normalized into `analysis_timestamp` while preserving `source_timestamp`.
