# Challenge 4 Summary

Fixed compute baseline realized savings rate: 30.56%

## Headline

- Baseline anchor month: 2025-08
- Forward backtest window: 2025-09 to 2026-05
- Fixed baseline commitment: $18.77/hour discounted spend
- Baseline realized savings: $70,120.35
- Baseline realized effective savings rate: 30.56%
- Baseline waste: $13,348.36
- Hindsight-optimal fixed commitment: $21.26/hour
- Hindsight-optimal savings over same window: $70,463.22
- Savings gap vs optimum: $342.87

## What This Answers

This backtest freezes the compute baseline roughly nine months before the latest complete month, then applies that same hourly commitment level forward with the same use-it-or-lose-it allocation rules from Challenge 2.

## Interpretation

- Baseline utilization: 89.15%
- Baseline coverage of eligible compute spend: 84.18%
- Optimal utilization over same window: 85.92%
- Optimal coverage over same window: 91.42%

The gap quantifies what a historically safe commitment missed once later usage moved. If the baseline stays highly utilized but still trails the optimum, that means growth created unrealized discounts. If baseline waste appears, that means the historical level became too large for later quiet hours.

## Anomaly Review Note

Material anomaly found: a baseline derived from past usage still produced waste in the forward window. That is a real regime-change signal, not a modeling artifact.

## Assumptions And Risks

- The baseline level is taken from the last available `baseline_max` value in the anchor month and then held fixed from the next complete month onward.
- The backtest scope is Compute Savings Plan-eligible non-Spot usage only.
- The pricing view matches Challenge 2: `compute_savings_plan`, 36 months, `no_upfront`, `savings_plan`.
- Missing pricing or invalid compute rows are quarantined and reported in `metrics.json` warnings.
