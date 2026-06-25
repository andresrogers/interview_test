# Understanding Ledger

## What I Verified Myself

- Verified `Usage with Discount` and `Unused Commitment` are the two commitment-audit signals used.
- Verified waste stays tied to the same commitment identifier rather than being pooled away.
- Verified monthly paid commitment rolls back up to the inventory total.

## What I Delegated And Trusted

- Trusted repeated grouping and CSV export once the inventory and monthly reconciliation checks matched.
- Trusted the utilization heatmap after the plotted values matched the monthly utilization table.

## What I'm Unsure Of

- Whether some commitment scopes would need deeper service-specific logic to prove under-commitment beyond the simple residual-on-demand proxy used here.
- Whether a longer or shorter audit window would better represent "current" posture for every commitment.
