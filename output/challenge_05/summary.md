# Challenge 5 Summary

Current audited commitment portfolio utilization: 97.24%

## Headline

- Audit window: 2026-03 to 2026-05
- Commitments observed: 29
- Portfolio paid commitment: $56,439.64
- Portfolio consumed commitment: $54,882.96
- Portfolio unused commitment waste: $1,556.68
- Portfolio utilization: 97.24%
- Portfolio coverage of eligible committed spend: 29.14%
- Likely over-committed instruments: 2
- Likely under-committed instruments: 27
- Likely well-sized instruments: 0

## Inventory Snapshot

- `arn:aws:savingsplans::417908285034:savingsplan/fa6ce1ab-3d42-0fda-9680-980310866d79` (savings_plan, compute): utilization 100.00%, waste $0.00, covers AmazonEC2, AmazonECS.
- `arn:aws:savingsplans::559750980952:savingsplan/eda5f203-29b6-c471-c841-9ad0b0c71d19` (savings_plan, compute): utilization 100.00%, waste $0.00, covers AmazonEC2, AmazonECS.
- `arn:aws:savingsplans::559750980952:savingsplan/884c727d-42b6-7899-4ee8-ffc9e2c58bdf` (savings_plan, compute): utilization 100.00%, waste $0.00, covers AmazonEC2, AmazonECS.
- `arn:aws:rds:eu-central-1:559750980952:ri:ri-2025-11-12-21-07-48-094` (reserved_instance, rds): utilization 100.00%, waste $0.00, covers AmazonRDS.
- `arn:aws:savingsplans::559750980952:savingsplan/2697b084-02ab-5e6d-2b36-952c2292ddc0` (savings_plan, compute): utilization 100.00%, waste $0.00, covers AmazonEC2, AmazonECS.

## Assessment

This audit reconstructs commitments from `commitment`, `Usage with Discount`, and `Unused Commitment` rows only. Utilization answers how much paid commitment got consumed. Coverage answers how much eligible on-demand spend the whole portfolio actually covered. They are reported separately on purpose.

Over-committed examples:
- `arn:aws:rds:eu-central-1:559750980952:ri:ri-2025-01-13-06-24-24-124`: utilization 5.53%, waste $1,536.67.
- `arn:aws:rds:eu-west-3:527480136527:ri:ri-2024-04-06-12-21-55-317`: utilization 49.78%, waste $19.15.

Under-committed examples:
- `arn:aws:savingsplans::417908285034:savingsplan/fa6ce1ab-3d42-0fda-9680-980310866d79`: utilization 100.00%, residual same-product on-demand $60,577.67.
- `arn:aws:savingsplans::559750980952:savingsplan/eda5f203-29b6-c471-c841-9ad0b0c71d19`: utilization 100.00%, residual same-product on-demand $60,577.67.

## Anomaly Review Note

Material anomaly found: one commitment drives a large share of waste ($1,536.67, utilization 5.53%). That is real idle commitment, not a reporting artifact.

## Assumptions And Risks

- The audit window uses the most recent three complete billing periods so the inventory reflects current posture rather than the full year.
- Per-commitment "under-committed" status is a proxy based on fully used commitments plus residual on-demand spend in the same products; it is directional evidence, not proof of exact scope miss.
- `Unused Commitment` rows are tied back by commitment ARN; if identifiers are missing the issue is reported in `metrics.json` warnings.
