# Understanding Ledger

## What I Verified Myself

- Verified the challenge window is the most recent three complete billing periods.
- Verified the optimizer sizes commitment in discounted dollars per hour, not on-demand dollars.
- Verified allocation order is highest discount first and unused hourly commitment becomes waste.
- Verified coverage and utilization are separate metrics with different denominators.

## What I Delegated And Trusted

- Trusted DuckDB to filter the parquet files and join the pinned pricing view after checking for duplicate price keys.
- Trusted the breakpoint sweep to enumerate the exact candidate kinks in the piecewise-linear savings curve.
- Trusted matplotlib for chart rendering after checking the underlying tables and optimum row.

## What I'm Unsure Of

- Whether the last three complete months are representative of future compute demand.
- Whether any quarantined rows would materially change the answer if their pricing metadata were repaired upstream.
- Whether stakeholders would prefer a slightly lower commitment with less downside-hour volatility than the hindsight maximum.

## Anomaly Review

No material allocation anomaly found after validation. Main artifact reviewed: Found 13 off-hour `Unused Commitment` rows; analysis uses normalized hourly buckets while preserving raw timestamps.
