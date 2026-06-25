"""Purpose:
Run shared data readiness checks and build a normalized analysis view.

Owns:
- Required schema definitions.
- Readiness checks and severity classification.
- Read-only normalization for analysis timestamps.
- Reusable EDA tables used by challenge pipelines.

Does Not Own:
- Challenge-specific metric definitions.
- Plot rendering or markdown file writes.

Main Entry Points:
- ensure_ready_usage_view
- data_quality_issues
- assert_no_fatal_issues
- issue_messages
- billing_period_completeness
- schema_summary
- null_profile
- cost_type_profile
- monthly_dataset_profile
- readiness_metrics

Key Invariants:
- Raw source rows are not mutated.
- Off-hour timestamps on `Unused Commitment` rows are warnings; other off-hour timestamps are fatal.
- Billing completeness uses distinct truncated hourly buckets.

Update This Header When:
- Public entry points change.
- Severity rules change.
- Ready-view columns change.
"""

from __future__ import annotations

from typing import Any

import duckdb
import pandas as pd

REQUIRED_USAGE_COLUMNS = {
    "timestamp",
    "billing_period",
    "product_code",
    "usage_amount",
    "on_demand_cost",
    "amortized_cost",
    "commitment",
    "commitment_key",
    "cost_type",
}

REQUIRED_PRICING_COLUMNS = {
    "price_list_key",
    "instrument_type",
    "term_months",
    "payment_option",
    "rate",
    "offering_class",
}

READY_COLUMNS = {"analysis_timestamp", "source_timestamp", "timestamp_was_normalized"}


def table_columns(con: duckdb.DuckDBPyConnection, table_name: str) -> list[tuple[str, str]]:
    rows = con.execute(f"describe select * from {table_name}").fetchall()
    return [(row[0], row[1]) for row in rows]


def ensure_ready_usage_view(
    con: duckdb.DuckDBPyConnection,
    source_table: str = "usage",
    ready_table: str = "usage_ready",
) -> str:
    column_names = {name for name, _ in table_columns(con, source_table)}
    if READY_COLUMNS.issubset(column_names):
        con.execute(f"create or replace view {ready_table} as select * from {source_table}")
        return ready_table

    con.execute(
        f"""
        create or replace view {ready_table} as
        select
          *,
          timestamp as source_timestamp,
          date_trunc('hour', timestamp) as analysis_timestamp,
          timestamp != date_trunc('hour', timestamp) as timestamp_was_normalized
        from {source_table}
        """
    )
    return ready_table


def _count_rows(con: duckdb.DuckDBPyConnection, stmt: str) -> int:
    row = con.execute(stmt).fetchone()
    if row is None:
        return 0
    return int(row[0])


def _required_column_issues(
    con: duckdb.DuckDBPyConnection,
    table_name: str,
    dataset: str,
    required: set[str],
) -> list[dict[str, Any]]:
    missing = sorted(required - {name for name, _ in table_columns(con, table_name)})
    if not missing:
        return []
    return [
        {
            "severity": "fatal",
            "dataset": dataset,
            "check_name": "required_columns",
            "row_count": len(missing),
            "details": f"Missing required columns: {', '.join(missing)}",
        }
    ]


def _off_hour_timestamp_issues(con: duckdb.DuckDBPyConnection, table_name: str) -> list[dict[str, Any]]:
    rows = con.execute(
        f"""
        select cost_type, count(*) as row_count
        from {table_name}
        where date_trunc('hour', timestamp) != timestamp
        group by 1
        order by 1
        """
    ).fetchall()
    if not rows:
        return []
    if len(rows) == 1 and rows[0][0] == "Unused Commitment":
        return [
            {
                "severity": "warning",
                "dataset": "usage",
                "check_name": "off_hour_timestamps",
                "row_count": rows[0][1],
                "details": (
                    f"Found {rows[0][1]} off-hour `Unused Commitment` rows; "
                    "analysis uses normalized hourly buckets while preserving raw timestamps."
                ),
            }
        ]
    details = ", ".join(f"{cost_type}: {row_count}" for cost_type, row_count in rows)
    total = sum(row_count for _, row_count in rows)
    return [
        {
            "severity": "fatal",
            "dataset": "usage",
            "check_name": "off_hour_timestamps",
            "row_count": total,
            "details": f"Usage timestamps are not aligned to full hours: {details}",
        }
    ]


def _numeric_issues(con: duckdb.DuckDBPyConnection, table_name: str) -> list[dict[str, Any]]:
    checks = [
        ("negative_usage_amount", "usage_amount < 0", "usage_amount has negative rows."),
        ("negative_on_demand_cost", "on_demand_cost < 0", "on_demand_cost has negative rows."),
        ("non_finite_amortized_cost", "not isfinite(amortized_cost)", "amortized_cost has non-finite rows."),
    ]
    issues = []
    for check_name, predicate, details in checks:
        row_count = _count_rows(con, f"select count(*) from {table_name} where {predicate}")
        if row_count:
            issues.append(
                {
                    "severity": "fatal",
                    "dataset": "usage",
                    "check_name": check_name,
                    "row_count": row_count,
                    "details": details,
                }
            )
    return issues


def _pricing_rate_issues(con: duckdb.DuckDBPyConnection, table_name: str) -> list[dict[str, Any]]:
    row_count = _count_rows(con, f"select count(*) from {table_name} where not isfinite(rate) or rate < 0")
    if not row_count:
        return []
    return [
        {
            "severity": "fatal",
            "dataset": "pricing",
            "check_name": "invalid_rate",
            "row_count": row_count,
            "details": "Pricing `rate` has non-finite or negative rows.",
        }
    ]


def data_quality_issues(
    con: duckdb.DuckDBPyConnection,
    usage_table: str = "usage",
    pricing_table: str = "pricing",
) -> pd.DataFrame:
    issues = []
    usage_column_issues = _required_column_issues(con, usage_table, "usage", REQUIRED_USAGE_COLUMNS)
    pricing_column_issues = _required_column_issues(con, pricing_table, "pricing", REQUIRED_PRICING_COLUMNS)
    issues.extend(usage_column_issues)
    issues.extend(pricing_column_issues)
    if not usage_column_issues:
        issues.extend(_off_hour_timestamp_issues(con, usage_table))
        issues.extend(_numeric_issues(con, usage_table))
    if not pricing_column_issues:
        issues.extend(_pricing_rate_issues(con, pricing_table))
    return pd.DataFrame(issues, columns=["severity", "dataset", "check_name", "row_count", "details"])


def assert_no_fatal_issues(issues: pd.DataFrame) -> None:
    if issues.empty:
        return
    fatal = issues.loc[issues["severity"] == "fatal", "details"].tolist()
    if fatal:
        raise ValueError("; ".join(fatal))


def issue_messages(issues: pd.DataFrame, severity: str) -> list[str]:
    if issues.empty:
        return []
    return issues.loc[issues["severity"] == severity, "details"].tolist()


def schema_summary(
    con: duckdb.DuckDBPyConnection,
    table_map: dict[str, str],
) -> pd.DataFrame:
    rows = []
    for dataset, table_name in table_map.items():
        for column_name, data_type in table_columns(con, table_name):
            rows.append({"dataset": dataset, "column_name": column_name, "data_type": data_type})
    return pd.DataFrame(rows)


def null_profile(
    con: duckdb.DuckDBPyConnection,
    table_name: str,
    dataset: str,
) -> pd.DataFrame:
    row_count = _count_rows(con, f"select count(*) from {table_name}")
    rows = []
    for column_name, _ in table_columns(con, table_name):
        null_rows = _count_rows(con, f'select count(*) from {table_name} where "{column_name}" is null')
        rows.append(
            {
                "dataset": dataset,
                "column_name": column_name,
                "null_rows": null_rows,
                "null_share": 0.0 if row_count == 0 else null_rows / row_count,
            }
        )
    return pd.DataFrame(rows)


def billing_period_completeness(
    con: duckdb.DuckDBPyConnection,
    table_name: str = "usage_ready",
    timestamp_column: str = "analysis_timestamp",
) -> pd.DataFrame:
    stmt = f"""
    with periods as (
      select
        billing_period,
        min({timestamp_column}) as min_timestamp,
        max({timestamp_column}) as max_timestamp,
        count(distinct date_trunc('hour', {timestamp_column})) as observed_hours,
        date_diff(
          'hour',
          strptime(billing_period || '-01', '%Y-%m-%d'),
          strptime(billing_period || '-01', '%Y-%m-%d') + interval 1 month
        ) as expected_hours
      from {table_name}
      group by 1
    )
    select
      billing_period,
      min_timestamp,
      max_timestamp,
      observed_hours,
      expected_hours,
      observed_hours = expected_hours as is_complete
    from periods
    order by billing_period
    """
    return con.execute(stmt).df()


def cost_type_profile(con: duckdb.DuckDBPyConnection, table_name: str = "usage_ready") -> pd.DataFrame:
    stmt = f"""
    select
      cost_type,
      count(*) as row_count,
      sum(usage_amount) as usage_amount,
      sum(on_demand_cost) as on_demand_cost,
      sum(amortized_cost) as amortized_cost
    from {table_name}
    group by 1
    order by 1
    """
    return con.execute(stmt).df()


def monthly_dataset_profile(
    con: duckdb.DuckDBPyConnection,
    table_name: str = "usage_ready",
    timestamp_column: str = "analysis_timestamp",
) -> pd.DataFrame:
    stmt = f"""
    select
      billing_period,
      min({timestamp_column}) as min_timestamp,
      max({timestamp_column}) as max_timestamp,
      count(*) as row_count,
      sum(on_demand_cost) as on_demand_cost,
      sum(amortized_cost) as amortized_cost
    from {table_name}
    group by 1
    order by 1
    """
    return con.execute(stmt).df()


def readiness_metrics(
    con: duckdb.DuckDBPyConnection,
    issues: pd.DataFrame,
    periods: pd.DataFrame,
    ready_table: str = "usage_ready",
) -> dict[str, Any]:
    normalized_row_count = _count_rows(
        con,
        f"select count(*) from {ready_table} where coalesce(timestamp_was_normalized, false)",
    )
    warning_messages = issue_messages(issues, "warning")
    fatal_messages = issue_messages(issues, "fatal")
    return {
        "trust_level": "low" if fatal_messages else "medium" if warning_messages else "high",
        "warnings": warning_messages,
        "fatal_issues": fatal_messages,
        "usage_row_count": _count_rows(con, f"select count(*) from {ready_table}"),
        "pricing_row_count": _count_rows(con, "select count(*) from pricing"),
        "normalized_row_count": normalized_row_count,
        "complete_billing_periods": periods.loc[periods["is_complete"], "billing_period"].tolist(),
        "partial_billing_periods": periods.loc[~periods["is_complete"], "billing_period"].tolist(),
    }
