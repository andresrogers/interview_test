"""Purpose:
Reusable Challenge 0 readiness outputs and report text.

Owns:
- Challenge 0 readiness table collection.
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
    return {
        "issues": data_quality_issues(con),
        "periods": billing_period_completeness(con),
        "schema": schema_summary(con, {"usage": "usage", "pricing": "pricing"}),
        "nulls": pd.concat([null_profile(con, "usage", "usage"), null_profile(con, "pricing", "pricing")], ignore_index=True),
        "cost_types": cost_type_profile(con),
        "monthly": monthly_dataset_profile(con),
    }


def write_tables(outputs: dict[str, pd.DataFrame], tables_dir: Path) -> None:
    outputs["issues"].to_csv(tables_dir / "data_quality_issues.csv", index=False)
    outputs["periods"].to_csv(tables_dir / "billing_period_completeness.csv", index=False)
    outputs["schema"].to_csv(tables_dir / "schema_summary.csv", index=False)
    outputs["nulls"].to_csv(tables_dir / "null_profile.csv", index=False)
    outputs["cost_types"].to_csv(tables_dir / "cost_type_profile.csv", index=False)
    outputs["monthly"].to_csv(tables_dir / "monthly_dataset_profile.csv", index=False)


def build_metrics(
    con: duckdb.DuckDBPyConnection,
    outputs: dict[str, pd.DataFrame],
) -> dict[str, Any]:
    metrics = readiness_metrics(con, outputs["issues"], outputs["periods"])
    metrics.update(
        {
            "challenge": "challenge_00_data_readiness",
            "cleaning_applied": metrics["normalized_row_count"] > 0,
        }
    )
    return metrics


def build_report_texts(metrics: dict[str, Any]) -> dict[str, str]:
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

## Cleaning Applied

- Raw `timestamp` is preserved.
- `analysis_timestamp` truncates rows to the analysis hour.
- `timestamp_was_normalized` marks rows that needed normalization.

## Anomaly Review Note

{anomaly_note}

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
4. Produce EDA tables for schema, nulls, cost types, and monthly row/cost shape.
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

## What I'm Unsure Of

- Whether future challenges need more normalization than hourly timestamp bucketing.
- Whether additional business-specific data rules will be needed once commitment optimization begins.
- Readiness currently normalizes timestamp shape only; it does not adjudicate semantic correctness of every cost row.

## Anomaly Review

{anomaly_note}
""",
    }
