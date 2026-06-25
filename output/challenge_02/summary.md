# Challenge 2 Summary

Optimal Compute Savings Plan commitment: $23.14/hour

## Headline

- Analysis window: 2026-03 to 2026-05
- Pricing view: 3-year no-upfront compute_savings_plan / savings_plan
- Optimal commitment: $23.14/hour discounted spend
- Total savings at optimum: $38,581.82
- Effective savings rate on eligible compute spend: 40.46%
- Average utilization at optimum: 99.41%
- Coverage of eligible compute on-demand spend: 94.05%
- Unused commitment waste at optimum: $299.89

## What This Answers

This challenge sizes one fixed Compute Savings Plan in discounted dollars per hour. The optimizer allocates the commitment every hour to eligible non-Spot `AWS#Compute*` usage in highest-discount-first order, then charges on-demand for the uncovered remainder.

## Main Drivers

- AmazonEC2: $54,434.49 eligible on-demand, $24,216.23 max gross savings if fully covered.
- AmazonECS: $37,616.82 eligible on-demand, $15,878.35 max gross savings if fully covered.
- AWSLambda: $3,299.45 eligible on-demand, $309.79 max gross savings if fully covered.

## Product Communication Note

- Customer headline card: "This plan would have saved $38,581.82 over 2026-03 to 2026-05."
- Support card 1: "Recommended commitment = $23.14/hour" with the savings-curve plot and the optimum point called out.
- Support card 2: "Why not higher?" show unused commitment waste of $299.89 and note that quiet hours can waste unused commitment.
- Plain-language explainer: "AWS applies the plan each hour to the compute usage where it saves the most first, then any leftover usage stays on-demand."

## Why This Is The Maximum

The curve peaks where almost all of the commitment is consumed (utilization 99.41%) while waste stays small at $299.89. To the left, the account leaves discount on the table. To the right, extra commitment mostly adds waste instead of new savings.

## Anomaly Review Note

No material allocation anomaly found after validation. Main artifact reviewed: Found 13 off-hour `Unused Commitment` rows; analysis uses normalized hourly buckets while preserving raw timestamps.

## Assumptions And Risks

- The result uses the most recent three complete months only; older history may imply a different sizing target.
- Spot is excluded because Savings Plans do not discount Spot.
- Missing or invalid pricing matches are quarantined and reported in `metrics.json` warnings.
- The recommendation is hindsight-optimal on history, not a forward guarantee.
