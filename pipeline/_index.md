# pipeline Index

## Purpose
Linear challenge scripts that load parquet data, call shared `src/` helpers, and write challenge outputs.

## Owns
- Per-challenge orchestration.
- Challenge-specific SQL blocks, plots, and output directories.

## Does Not Own
- Shared allocation mechanics.
- Generic pipeline frameworks.

## Files
| File | Purpose | Main entry points |
|---|---|---|
| `challenge_00_data_readiness.py` | Readiness checks and profiling outputs. | `main` |
| `challenge_01_effective_savings_rate.py` | Current realized savings decomposition. | `main` |
| `challenge_02_optimal_commitment.py` | Optimal Compute Savings Plan sizing over three complete months. | `main` |

## Dependency Rules
Allowed:
- `duckdb`, `pandas`, `matplotlib`, local `src` helpers.

Forbidden:
- Hidden orchestration layers.
- Challenge logic copied out of `src/` when shared code already exists.

## Common Change Paths
- To change challenge outputs, edit the specific `challenge_nn_*.py` script and matching `src/challenge_nn.py` helper.
- To change commitment mechanics, edit `src/commitments.py` and update `tests/test_commitments.py`.

## Test Command
```bash
uv run pytest tests/test_commitments.py tests/test_metrics.py tests/test_pipeline_smoke.py
```
