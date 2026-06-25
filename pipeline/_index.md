# pipeline Index

## Purpose
Simple per-challenge scripts that load data, run one analysis, and write presentation-ready outputs under `output/challenge_nn/`.

## Owns
- Linear orchestration for each challenge.
- Challenge-local tables, plots, and markdown files.

## Does Not Own
- Shared pricing joins, metrics, or allocation logic.
- Generic framework code.

## Files
| File | Purpose | Main entry points |
|---|---|---|
| `challenge_00_data_readiness.py` | Readiness checks and dataset overview. | `main` |
| `challenge_01_effective_savings_rate.py` | Actual realized savings and waste baseline. | `main` |
| `challenge_02_optimal_commitment.py` | Hindsight-optimal fixed compute commitment. | `main` |
| `challenge_03_window_sensitivity.py` | Window stress-test for Challenge 2. | `main` |
| `challenge_04_baseline_realized_savings.py` | Fixed historical baseline backtest vs hindsight optimum. | `main` |
| `challenge_05_audit_commitments.py` | Existing commitment inventory and utilization audit. | `main` |
| `challenge_06_coverage_utilization_frontier.py` | Coverage/utilization/savings frontier. | `main` |

## Dependency Rules
Allowed:
- `duckdb`, `pandas`, `matplotlib`, stdlib.
- Shared helpers from `src/`.

Forbidden:
- Shared business logic implemented directly in pipeline scripts.
- Hidden write paths outside each challenge output directory.

## Common Change Paths
- To change challenge-specific narrative or plots, edit the matching pipeline script and its `src/challenge_nn.py` helper.
- To change shared metrics or allocation, edit `src/` first and keep pipeline scripts as thin orchestrators.

## Test Command
```bash
uv run pytest tests/test_pipeline_smoke.py
```
