# Understanding Ledger

## What I Verified Myself

- Verified Challenge 3 only changes the history window; the hourly optimizer mechanics stay the same as Challenge 2.
- Verified trailing and anchored windows use complete billing periods only.
- Verified the recommendation rule is explicit about regime-change risk instead of blindly picking the biggest hindsight result.

## What I Delegated And Trusted

- Trusted the repeated breakpoint sweeps once the Challenge 2 allocation logic and tests passed.
- Trusted matplotlib rendering and CSV export after checking the headline values in `metrics.json` and `tables/window_sensitivity.csv`.

## What I'm Unsure Of

- Whether the future will look more like the most recent 3 months or the broader 6-month history if the account is mid-migration.
- Whether a different anchored window length would better reflect the business planning cadence.
