# Challenge 6 Methodology

## Steps

1. Reuse the Challenge 2 compute optimizer input for the most recent 3 complete billing periods.
2. Take the exact breakpoint commitments from the savings curve.
3. Thin the exported frontier only when the exact breakpoint count is too large for practical plotting.
4. Evaluate coverage, utilization, waste, and net savings at each exported commitment level.
5. Read today's posture from the exported Challenge 5 commitment inventory and keep only compute-scope commitments.
6. Recommend the highest-utilization point that retains at least 95% of peak savings.

## Validation Notes

- Warnings: Found 13 off-hour `Unused Commitment` rows; analysis uses normalized hourly buckets while preserving raw timestamps., Frontier output was thinned from 263,290 exact breakpoints to 251 plotted points to keep runtime and charts usable..
- Coverage denominator = eligible compute on-demand cost.
- Utilization denominator = paid commitment dollars.
