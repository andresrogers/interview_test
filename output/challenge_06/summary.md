# Challenge 6 Summary

Recommended operating point: $21.51/hour discounted spend

## Frontier Answer

- Max-savings point: $23.12/hour with $38,581.66 net savings
- Recommended operating point: $21.51/hour with $37,156.94 net savings
- Recommended coverage: 88.77%
- Recommended utilization: 100.00%
- Frontier points exported: 251
- Exact breakpoint count behind the curve: 263,290

## Where The Account Sits Today

- Current compute commitment from Challenge 5 inventory: $19.46/hour
- Current coverage: 79.98%
- Current utilization: 100.00%
- Current net savings on compute commitments: $33,304.23

## Recommended Operating Point

The max-savings point and the max-utilization point are not the same. I recommend the highest-utilization point that still keeps at least 95% of the frontier's best savings. That preserves most of the upside while reducing the downside from idle commitment in quiet hours.

## Anomaly Review Note

No material anomaly found. Coverage, utilization, and savings move in the expected opposing directions across the frontier.

## Assumptions And Risks

- The frontier uses the same 3 complete billing-period window and pricing view as Challenge 2.
- The current posture is read from `output/challenge_05/tables/commitment_inventory.csv` and filtered to compute-scope commitments.
- The exported frontier can be sampled below the exact breakpoint count when the exact curve is too large to plot cleanly.
- A business with higher downside tolerance may choose the absolute savings peak instead of the recommended operating point.
