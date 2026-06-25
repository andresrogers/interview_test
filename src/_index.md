# src Index

## Purpose
Shared helpers for loading parquet data, preparing a readiness-safe analysis view, computing reusable metrics, and running minimal commitment optimization.

## Owns
- Parquet path constants and DuckDB view setup.
- Shared data readiness checks, EDA tables, and normalized analysis timestamps.
- Minimal effective savings helpers and challenge-specific reusable computations.

## Does Not Own
- Challenge-specific plot rendering in pipeline scripts.
- Generic framework code.

## Files
| File | Purpose | Main entry points |
|---|---|---|
| `cost_data.py` | Load documented parquet files into DuckDB views. | `connect`, `load_usage`, `load_pricing` |
| `data_quality.py` | Shared readiness checks, EDA tables, and ready usage view creation. | `ensure_ready_usage_view`, `data_quality_issues`, `assert_no_fatal_issues`, `billing_period_completeness`, `readiness_metrics` |
| `metrics.py` | Minimal effective savings plus coverage/utilization helpers. | `effective_savings_metrics`, `add_effective_savings_columns`, `coverage_rate`, `utilization_rate` |
| `commitments.py` | Hourly commitment allocation and optimization helpers. | `build_hourly_inputs`, `evaluate_commitment`, `optimize_commitment`, `hourly_summary` |
| `challenge_00.py` | Reusable Challenge 0 readiness collection and report text. | `collect_outputs`, `build_metrics`, `write_tables`, `build_report_texts` |
| `challenge_01.py` | Reusable Challenge 1 aggregations and report text. | `choose_analysis_window`, `collect_outputs`, `build_metrics`, `build_report_texts` |
| `challenge_02.py` | Reusable Challenge 2 windowing, validation, metrics, and report text. | `choose_analysis_window`, `validate_optimizer_inputs`, `build_metrics`, `build_report_texts` |

## Dependency Rules
Allowed:
- `duckdb`, `pandas`, stdlib.

Forbidden:
- Generic report frameworks.
- Cross-challenge business logic hidden in vague helpers.

## Common Change Paths
- To change readiness rules, edit `data_quality.py` and update `tests/test_data_quality.py`.
- To change Challenge 0 readiness narrative or outputs, edit `challenge_00.py` and `pipeline/challenge_00_data_readiness.py`.
- To change effective savings or commitment metric definitions, edit `metrics.py` and update `tests/test_metrics.py`.
- To change Challenge 1 decomposition or narrative, edit `challenge_01.py` and `pipeline/challenge_01_effective_savings_rate.py`.
- To change Challenge 2 allocation mechanics, edit `commitments.py` and update `tests/test_commitments.py`.
- To change Challenge 2 narrative or outputs, edit `challenge_02.py` and `pipeline/challenge_02_optimal_commitment.py`.

## Test Command
```bash
uv run pytest tests/test_data_quality.py tests/test_metrics.py tests/test_commitments.py tests/test_pipeline_smoke.py
```
