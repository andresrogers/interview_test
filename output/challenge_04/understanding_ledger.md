# Understanding Ledger

## What I Verified Myself

- Verified the baseline commitment stays fixed after the anchor month.
- Verified the forward backtest reuses the same hourly commitment mechanics as Challenge 2.
- Verified realized savings and waste reconcile from hourly rows into monthly totals.

## What I Delegated And Trusted

- Trusted repeated hourly evaluation once the fixed-baseline and optimal scenarios matched their reconciliation checks.
- Trusted plot rendering after the chart annotations matched the exported CSV tables.

## What I'm Unsure Of

- Whether the challenge wanted the anchor taken exactly nine months prior or approximately nine months prior; this implementation uses the nearest complete anchor month.
- Whether a different baseline extraction point inside the anchor month would materially change the result.
