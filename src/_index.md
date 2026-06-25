# src Index

## Purpose
Shared helpers for loading parquet data, preparing a readiness-safe analysis view, and computing small reusable challenge metrics.

## Owns
- Parquet path constants and DuckDB view setup.
- Shared data readiness checks, EDA tables, and normalized analysis timestamps.
- Minimal effective savings helpers and challenge-specific reusable computations.

## Does Not Own
- Challenge-specific plot rendering in pipeline scripts.
- Generic framework code.
- Commitment optimization logic for later challenges.

## Files
| File | Purpose | Main entry points |
|---|---|---|
| `cost_data.py` | Load documented parquet files into DuckDB views. | `connect`, `load_usage`, `load_pricing` |
| `data_quality.py` | Shared readiness checks, EDA tables, and ready usage view creation. | `ensure_ready_usage_view`, `data_quality_issues`, `assert_no_fatal_issues`, `billing_period_completeness`, `readiness_metrics` |
| `metrics.py` | Minimal effective savings computations. | `effective_savings_metrics`, `add_effective_savings_columns` |
| `challenge_00.py` | Reusable Challenge 0 readiness collection and report text. | `collect_outputs`, `build_metrics`, `write_tables`, `build_report_texts` |
| `challenge_01.py` | Reusable Challenge 1 aggregations and report text. | `choose_analysis_window`, `collect_outputs`, `build_metrics`, `build_report_texts` |

## Dependency Rules
Allowed:
- `duckdb`, `pandas`, stdlib.

Forbidden:
- Generic report frameworks.
- Cross-challenge business logic hidden in vague helpers.

## Common Change Paths
- To change readiness rules, edit `data_quality.py` and update `tests/test_data_quality.py`.
- To change Challenge 0 readiness narrative or outputs, edit `challenge_00.py` and `pipeline/challenge_00_data_readiness.py`.
- To change effective savings definitions, edit `metrics.py` and update `tests/test_metrics.py`.
- To change Challenge 1 decomposition or narrative, edit `challenge_01.py` and `pipeline/challenge_01_effective_savings_rate.py`.

## Test Command
```bash
uv run pytest tests/test_data_quality.py tests/test_metrics.py tests/test_pipeline_smoke.py
```
