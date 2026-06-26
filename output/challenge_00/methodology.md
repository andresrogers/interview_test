# Challenge 0 Methodology

## Steps

1. Load raw usage and pricing parquet files into DuckDB.
2. Build `usage_ready`, a derived view that preserves raw timestamps and adds normalized hourly buckets.
3. Run schema, timestamp, and numeric readiness checks.
4. Produce EDA tables for schema, nulls, cost types, duplicate keys, ratios, pricing coverage, and monthly row/cost shape.
5. Reuse the shared `usage_ready` view directly in later challenge scripts.

## Cleaning Rule

- If a row lands off exact hour boundaries, keep the original `timestamp` and set `analysis_timestamp = date_trunc('hour', timestamp)`.
- In the current dataset this only appears on `Unused Commitment` rows, so it is reported as a warning rather than a fatal blocker.
