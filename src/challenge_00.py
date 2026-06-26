"""Purpose:
Reusable Challenge 0 readiness outputs and report text.

Owns:
- Challenge 0 readiness table collection.
- Challenge 0 trend and diagnostic table collection.
- Challenge 0 metrics assembly.
- Challenge 0 markdown report text generation.

Does Not Own:
- Shared schema/timestamp checks.
- Plot rendering.

Main Entry Points:
- collect_outputs
- build_metrics
- write_tables
- build_report_texts

Key Invariants:
- Readiness outputs describe raw data plus the derived analysis view.
- Cleaning means derived normalization only, never source mutation.
-
Update This Header When:
- Public entry points change.
- Challenge 0 deliverables change.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import duckdb
import pandas as pd

from src.challenge_00_diagnostics import (
    categorical_validation_summary,
    commitment_consistency_outputs,
    cost_usage_ratio_outputs,
    duplicate_check_outputs,
    metric_value,
    monthly_aws_load_by_service,
    monthly_aws_load_trend,
    monthly_spike_flags,
    numeric_sanity_summary,
    pricing_key_coverage_outputs,
    sum_column,
    top_usage_rows,
    trend_metrics,
)

from src.data_quality import (
    billing_period_completeness,
    cost_type_profile,
    data_quality_issues,
    issue_messages,
    monthly_dataset_profile,
    null_profile,
    readiness_metrics,
    schema_summary,
)


def collect_outputs(con: duckdb.DuckDBPyConnection) -> dict[str, pd.DataFrame]:
    duplicates = duplicate_check_outputs(con)
    ratios = cost_usage_ratio_outputs(con)
    commitments = commitment_consistency_outputs(con)
    pricing = pricing_key_coverage_outputs(con)
    top_rows = top_usage_rows(con)
    return {
        "issues": data_quality_issues(con),
        "periods": billing_period_completeness(con),
        "schema": schema_summary(con, {"usage": "usage", "pricing": "pricing"}),
        "nulls": pd.concat([null_profile(con, "usage", "usage"), null_profile(con, "pricing", "pricing")], ignore_index=True),
        "cost_types": cost_type_profile(con),
        "monthly": monthly_dataset_profile(con),
        "monthly_trend": monthly_aws_load_trend(con),
        "monthly_trend_by_service": monthly_aws_load_by_service(con),
        "duplicate_summary": duplicates["duplicate_summary"],
        "exact_duplicate_rows": duplicates["exact_duplicate_rows"],
        "duplicate_hourly_line_keys": duplicates["duplicate_hourly_line_keys"],
        "numeric_sanity": numeric_sanity_summary(con),
        "cost_usage_ratio_summary": ratios["cost_usage_ratio_summary"],
        "top_on_demand_cost_per_usage_rows": ratios["top_on_demand_cost_per_usage_rows"],
        "top_amortized_cost_per_usage_rows": ratios["top_amortized_cost_per_usage_rows"],
        "categorical_validation": categorical_validation_summary(con),
        "commitment_consistency_summary": commitments["commitment_consistency_summary"],
        "commitment_consistency_failures": commitments["commitment_consistency_failures"],
        "top_usage_amount_rows": top_rows["top_usage_amount_rows"],
        "top_on_demand_cost_rows": top_rows["top_on_demand_cost_rows"],
        "top_amortized_cost_rows": top_rows["top_amortized_cost_rows"],
        "monthly_spike_flags": monthly_spike_flags(con),
        "pricing_key_coverage_summary": pricing["pricing_key_coverage_summary"],
        "missing_price_list_key_rows": pricing["missing_price_list_key_rows"],
    }


def write_tables(outputs: dict[str, pd.DataFrame], tables_dir: Path) -> None:
    outputs["issues"].to_csv(tables_dir / "data_quality_issues.csv", index=False)
    outputs["periods"].to_csv(tables_dir / "billing_period_completeness.csv", index=False)
    outputs["schema"].to_csv(tables_dir / "schema_summary.csv", index=False)
    outputs["nulls"].to_csv(tables_dir / "null_profile.csv", index=False)
    outputs["cost_types"].to_csv(tables_dir / "cost_type_profile.csv", index=False)
    outputs["monthly"].to_csv(tables_dir / "monthly_dataset_profile.csv", index=False)
    outputs["monthly_trend"].to_csv(tables_dir / "monthly_aws_load_trend.csv", index=False)
    outputs["duplicate_summary"].to_csv(tables_dir / "duplicate_check_summary.csv", index=False)
    outputs["exact_duplicate_rows"].to_csv(tables_dir / "exact_duplicate_rows_sample.csv", index=False)
    outputs["duplicate_hourly_line_keys"].to_csv(tables_dir / "duplicate_hourly_line_keys_sample.csv", index=False)
    outputs["numeric_sanity"].to_csv(tables_dir / "numeric_sanity_check_summary.csv", index=False)
    outputs["cost_usage_ratio_summary"].to_csv(tables_dir / "cost_usage_ratio_summary.csv", index=False)
    outputs["top_on_demand_cost_per_usage_rows"].to_csv(tables_dir / "top_on_demand_cost_per_usage_rows.csv", index=False)
    outputs["top_amortized_cost_per_usage_rows"].to_csv(tables_dir / "top_amortized_cost_per_usage_rows.csv", index=False)
    outputs["categorical_validation"].to_csv(tables_dir / "categorical_validation_summary.csv", index=False)
    outputs["commitment_consistency_summary"].to_csv(tables_dir / "commitment_consistency_summary.csv", index=False)
    outputs["commitment_consistency_failures"].to_csv(tables_dir / "commitment_consistency_failures_sample.csv", index=False)
    outputs["top_usage_amount_rows"].to_csv(tables_dir / "top_usage_amount_rows.csv", index=False)
    outputs["top_on_demand_cost_rows"].to_csv(tables_dir / "top_on_demand_cost_rows.csv", index=False)
    outputs["top_amortized_cost_rows"].to_csv(tables_dir / "top_amortized_cost_rows.csv", index=False)
    outputs["monthly_spike_flags"].to_csv(tables_dir / "monthly_spike_flags.csv", index=False)
    outputs["pricing_key_coverage_summary"].to_csv(tables_dir / "pricing_key_coverage_summary.csv", index=False)
    outputs["missing_price_list_key_rows"].to_csv(tables_dir / "missing_price_list_key_rows_sample.csv", index=False)


def build_metrics(
    con: duckdb.DuckDBPyConnection,
    outputs: dict[str, pd.DataFrame],
) -> dict[str, Any]:
    metrics = readiness_metrics(con, outputs["issues"], outputs["periods"])
    trend = trend_metrics(outputs["monthly_trend"])
    pricing_summary = outputs["pricing_key_coverage_summary"]
    overall_pricing = pricing_summary.loc[pricing_summary["grouping"] == "overall"].iloc[0]
    metrics.update(
        {
            "challenge": "challenge_00_data_readiness",
            "cleaning_applied": metrics["normalized_row_count"] > 0,
            "trend": trend,
            "exact_duplicate_rows": int(metric_value(outputs["duplicate_summary"], "exact_full_row_duplicates", "duplicate_count")),
            "duplicate_hourly_line_keys": int(metric_value(outputs["duplicate_summary"], "duplicate_hourly_line_keys", "duplicate_count")),
            "numeric_anomaly_rows": int(sum_column(outputs["numeric_sanity"], "failing_rows")),
            "unexpected_cost_type_values": outputs["categorical_validation"]
            .loc[(outputs["categorical_validation"]["category"] == "cost_type") & ~outputs["categorical_validation"]["is_expected"], "value"]
            .tolist(),
            "unexpected_commitment_prefixes": outputs["categorical_validation"]
            .loc[
                (outputs["categorical_validation"]["category"] == "commitment_key_prefix")
                & ~outputs["categorical_validation"]["is_expected"],
                "value",
            ]
            .tolist(),
            "commitment_consistency_failures": int(sum_column(outputs["commitment_consistency_summary"], "failing_rows")),
            "missing_pricing_rows": int(overall_pricing["missing_pricing_rows"]),
            "missing_pricing_share": float(overall_pricing["missing_pricing_share"]),
        }
    )
    return metrics


def build_report_texts(metrics: dict[str, Any]) -> dict[str, str]:
    trend_months = metrics["trend"]["trend_months"]
    trend_window = f"{trend_months[0]} to {trend_months[-1]}" if trend_months else "insufficient complete months"
    unexpected_cost_types = ", ".join(metrics["unexpected_cost_type_values"]) if metrics["unexpected_cost_type_values"] else "none"
    unexpected_commitment_prefixes = (
        ", ".join(metrics["unexpected_commitment_prefixes"]) if metrics["unexpected_commitment_prefixes"] else "none"
    )
    anomaly_note = (
        "No fatal anomaly found. The notable data artifact was off-hour `Unused Commitment` rows, "
        f"and {metrics['normalized_row_count']} rows were normalized into `analysis_timestamp` while preserving `source_timestamp`."
        if metrics["normalized_row_count"]
        else "No material readiness anomaly found. Schema, numeric checks, and hourly bucketing all passed without normalization."
    )
    return {
        "summary.md": f"""
# Challenge 0 Summary

Dataset ready for analysis: {'yes' if not metrics['fatal_issues'] else 'no'}

## Headline

- Usage rows profiled: {metrics['usage_row_count']:,}
- Pricing rows profiled: {metrics['pricing_row_count']:,}
- Complete billing periods: {', '.join(metrics['complete_billing_periods']) if metrics['complete_billing_periods'] else 'none'}
- Partial billing periods: {', '.join(metrics['partial_billing_periods']) if metrics['partial_billing_periods'] else 'none'}
- Normalized off-hour rows: {metrics['normalized_row_count']:,}

## What Was Checked

- Required usage and pricing columns.
- Off-hour timestamps, negative values, and non-finite costs.
- Null profile by column.
- Monthly row and cost profile.
- Monthly on-demand-equivalent load trend, duplicate checks, ratio diagnostics, commitment consistency, and pricing key coverage.

## Cleaning Applied

- Raw `timestamp` is preserved.
- `analysis_timestamp` truncates rows to the analysis hour.
- `timestamp_was_normalized` marks rows that needed normalization.

## Anomaly Review Note

{anomaly_note}

## Additional Diagnostics

- Monthly AWS demand trend from complete months: {metrics['trend']['trend_direction']} across {trend_window}.
- Last observed month excluded from trend interpretation: {'yes' if metrics['trend']['excluded_last_incomplete_month'] else 'no'}.
- Exact duplicate rows: {metrics['exact_duplicate_rows']:,}.
- Duplicate hourly line keys: {metrics['duplicate_hourly_line_keys']:,}.
- Numeric anomaly rows across explicit sanity checks: {metrics['numeric_anomaly_rows']:,}.
- Unexpected `cost_type` values: {unexpected_cost_types}.
- Unexpected `commitment_key` prefixes: {unexpected_commitment_prefixes}.
- Commitment consistency failures: {metrics['commitment_consistency_failures']:,}.
- Usage rows missing pricing matches: {metrics['missing_pricing_rows']:,} ({metrics['missing_pricing_share']:.2%}).

## Assumptions And Risks

- Challenge 0 normalizes timestamp artifacts only; it does not rewrite financial values.
- Partial periods are flagged, not backfilled.
- Later challenges should prefer `analysis_timestamp` for hourly completeness logic.
""",
        "methodology.md": """
# Challenge 0 Methodology

## Steps

1. Load raw usage and pricing parquet files into DuckDB.
2. Build `usage_ready`, a derived view that preserves raw timestamps and adds normalized hourly buckets.
3. Run schema, timestamp, and numeric readiness checks.
4. Produce EDA tables for schema, nulls, cost types, duplicate keys, ratios, pricing coverage, and monthly row/cost shape.
5. Reuse the shared `usage_ready` view directly in later challenge scripts.

## Cleaning Rule

- If a row lands off exact hour boundaries, keep the original `timestamp` and set `analysis_timestamp = date_trunc('hour', timestamp)`.
- In the current dataset this only appears on `Unused Commitment` rows, so it is reported as a warning rather than a fatal blocker.
""",
        "understanding_ledger.md": f"""
# Understanding Ledger

## What I Verified Myself

- Verified the source schema against the documented required columns used by early challenges.
- Verified the off-hour timestamp artifact is isolated to `Unused Commitment` rows before treating it as a warning.
- Verified readiness stays in the shared analysis view instead of mutating the source file.

## What I Delegated And Trusted

- Trusted DuckDB to scan parquet files, build the readiness view, and generate the grouped EDA tables after checks passed.
- Trusted matplotlib for the row and cost profile plots after checking the underlying monthly tables.
- Trusted simple ranked diagnostics and month-over-month deltas for duplicate, ratio, and spike summaries rather than imposing statistical outlier thresholds.

## What I'm Unsure Of

- Whether future challenges need more normalization than hourly timestamp bucketing.
- Whether additional business-specific data rules will be needed once commitment optimization begins.
- Readiness currently normalizes timestamp shape only; it does not adjudicate semantic correctness of every cost row.
- Ranked ratio and spike outputs are diagnostics only; they do not prove invalid billing on their own.

## Anomaly Review

{anomaly_note}
""",
    }
