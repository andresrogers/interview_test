# Challenge 3 Summary

Recommended sizing rule: Use the most recent 3 complete months as the primary sizing window.

## Headline

- Recommended commitment: $23.14/hour discounted spend
- Recommended source window: trailing_03m
- Best hindsight window in the sweep: trailing_06m at $22.75/hour and $70,024.34 savings
- Window count evaluated: 13
- Spread between lowest and highest optimum: $11.71/hour

## Sensitivity Results

### Trailing windows

- trailing_01m: $22.76/hour, $12,743.55 savings, 99.55% utilization, 95.07% coverage.
- trailing_02m: $22.99/hour, $25,356.84 savings, 99.44% utilization, 94.42% coverage.
- trailing_03m: $23.14/hour, $38,581.82 savings, 99.41% utilization, 94.05% coverage.
- trailing_06m: $22.75/hour, $70,024.34 savings, 96.71% utilization, 93.82% coverage.

### Anchored 3-month windows

- 2025-07 to 2025-09: $11.48/hour, $18,110.94 savings.
- 2025-08 to 2025-10: $11.68/hour, $18,336.42 savings.
- 2025-09 to 2025-11: $11.95/hour, $18,491.24 savings.
- 2025-10 to 2025-12: $12.46/hour, $19,751.04 savings.
- 2025-11 to 2026-01: $16.13/hour, $22,596.80 savings.
- 2025-12 to 2026-02: $22.25/hour, $31,663.01 savings.
- 2026-01 to 2026-03: $22.89/hour, $37,173.08 savings.
- 2026-02 to 2026-04: $23.19/hour, $37,412.58 savings.
- 2026-03 to 2026-05: $23.14/hour, $38,581.82 savings.

## Interpretation

The recent 3-month result is close enough to broader trailing history that it gives a current signal without obvious instability.

## Regime Change Review

- Largest month-over-month discounted-spend move: 2025-12 at $4,912.26 (50.10%).

## Anomaly Review Note

Material anomaly found: anchored 3-month windows produce meaningfully different optima. That is a real regime-change signal, not chart noise, because the optimizer is unchanged and only the history slice moved. Recommendation impact: do not buy to the highest hindsight window without checking whether that demand still exists.

## Assumptions And Risks

- All windows reuse the verified Challenge 2 Compute Savings Plan optimizer and pricing view.
- Anchored windows are fixed at 3 months so they are directly comparable to the default Challenge 2 policy.
- This is still hindsight on observed history; a forward buy should be capped by business downside tolerance, not just the highest backtested savings point.
