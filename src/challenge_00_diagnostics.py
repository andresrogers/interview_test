"""Purpose:
Build Challenge 0 trend and diagnostic tables.

Owns:
- Monthly AWS load trend summaries.
- Duplicate, ratio, categorical, commitment, and pricing diagnostics.

Does Not Own:
- Shared readiness severity rules.
- Plot rendering or markdown file writes.

Main Entry Points:
- monthly_aws_load_trend
- monthly_aws_load_by_service
- numeric_sanity_summary
- cost_usage_ratio_outputs
- categorical_validation_summary
- commitment_consistency_outputs
- monthly_spike_flags
- pricing_key_coverage_outputs
- trend_metrics

Key Invariants:
- Diagnostics are report-only.
- Last incomplete observed month is excluded from trend interpretation only.

Update This Header When:
- Public entry points change.
- Diagnostic scope changes.
"""

from __future__ import annotations

from typing import Any

import duckdb
import pandas as pd

from src.challenge_00_duplicates import duplicate_check_outputs
from src.data_quality import billing_period_completeness, cost_type_profile

EXPECTED_COST_TYPES = {
    "On Demand Usage",
    "Spot Usage",
    "Unused Commitment",
    "Usage with Discount",
}

EXPECTED_COMMITMENT_PREFIXES = {
    "AWS#Compute",
    "AWS#Compute-EC2",
    "AWS#Database",
    "AWS#Database-OpenSearch",
    "AWS#Sagemaker",
    "AWS#AmazonRDS-Database Instance",
    "AWS#AmazonElastiCache-Cache Instance",
    "AWS#AmazonES-Amazon OpenSearch Service Instance",
    "None",
}

RANKING_COLUMNS = [
    "analysis_timestamp",
    "billing_period",
    "product_code",
    "usage_type",
    "instance_type",
    "account_id",
    "price_list_key",
    "commitment",
    "commitment_key",
    "cost_type",
    "usage_amount",
    "on_demand_cost",
    "amortized_cost",
]


def _quote(name: str) -> str:
    return f'"{name}"'


def _table_columns(con: duckdb.DuckDBPyConnection, table_name: str) -> list[str]:
    return con.execute(f"describe select * from {table_name}").df()["column_name"].tolist()


def _count_rows(con: duckdb.DuckDBPyConnection, stmt: str) -> int:
    row = con.execute(stmt).fetchone()
    return 0 if row is None else int(row[0])


def _existing_columns(con: duckdb.DuckDBPyConnection, table_name: str, candidates: list[str]) -> list[str]:
    columns = set(_table_columns(con, table_name))
    return [column for column in candidates if column in columns]


def _value_present_sql(column_name: str) -> str:
    column = _quote(column_name)
    return f"{column} is not null and trim(cast({column} as varchar)) not in ('', 'None')"


def _sample_rows(con: duckdb.DuckDBPyConnection, table_name: str, order_by: str, limit: int = 20) -> pd.DataFrame:
    columns = _existing_columns(con, table_name, RANKING_COLUMNS)
    select_list = ", ".join(_quote(column) for column in columns)
    return con.execute(f"select {select_list} from {table_name} order by {order_by} limit {limit}").df()


def _included_trend_months(trend: pd.DataFrame) -> list[str]:
    if len(trend) and not bool(trend.iloc[-1]["is_complete_month"]):
        return trend.iloc[:-1]["month"].tolist()
    return trend["month"].tolist()


def _commitment_prefix_expr() -> str:
    return """
      case
        when commitment_key is null or trim(cast(commitment_key as varchar)) in ('', 'None') then 'None'
        when commitment_key like 'AWS#Compute%' then 'AWS#Compute'
        when commitment_key like 'AWS#Database%' then 'AWS#Database'
        when commitment_key like 'AWS#Sagemaker%' then 'AWS#Sagemaker'
        else split_part(commitment_key, '#', 1) || '#' || split_part(commitment_key, '#', 2)
      end
    """


def monthly_aws_load_trend(
    con: duckdb.DuckDBPyConnection,
    table_name: str = "usage_ready",
    timestamp_column: str = "analysis_timestamp",
) -> pd.DataFrame:
    periods = billing_period_completeness(con, table_name, timestamp_column)[["billing_period", "is_complete"]].copy()
    periods.columns = ["month", "is_complete_month"]
    monthly = con.execute(
        f"""
        select
          billing_period as month,
          count(*) as usage_rows,
          sum(usage_amount) as total_usage_amount,
          sum(on_demand_cost) as total_on_demand_cost,
          sum(amortized_cost) as total_amortized_cost
        from {table_name}
        group by 1
        order by 1
        """
    ).df()
    monthly = monthly.merge(periods, on="month", how="left")
    monthly["mom_on_demand_cost_delta"] = monthly["total_on_demand_cost"].diff()
    monthly["mom_on_demand_cost_pct"] = monthly["total_on_demand_cost"].pct_change()
    return monthly.loc[
        :,
        [
            "month",
            "is_complete_month",
            "usage_rows",
            "total_usage_amount",
            "total_on_demand_cost",
            "total_amortized_cost",
            "mom_on_demand_cost_delta",
            "mom_on_demand_cost_pct",
        ],
    ].copy()


def monthly_aws_load_by_service(con: duckdb.DuckDBPyConnection, table_name: str = "usage_ready") -> pd.DataFrame:
    months = _included_trend_months(monthly_aws_load_trend(con, table_name))
    if not months:
        return pd.DataFrame(columns=["month", "product_code", "total_on_demand_cost"])
    month_list = ", ".join(f"'{month}'" for month in months)
    top_services = con.execute(
        f"""
        select product_code
        from {table_name}
        where billing_period in ({month_list})
        group by 1
        order by sum(on_demand_cost) desc, product_code
        limit 5
        """
    ).df()["product_code"].tolist()
    if not top_services:
        return pd.DataFrame(columns=["month", "product_code", "total_on_demand_cost"])
    service_list = ", ".join(f"'{service.replace("'", "''")}'" for service in top_services)
    return con.execute(
        f"""
        select
          billing_period as month,
          product_code,
          sum(on_demand_cost) as total_on_demand_cost
        from {table_name}
        where billing_period in ({month_list})
          and product_code in ({service_list})
        group by 1, 2
        order by 1, 3 desc, 2
        """
    ).df()


def numeric_sanity_summary(con: duckdb.DuckDBPyConnection, table_name: str = "usage_ready") -> pd.DataFrame:
    row_count = max(_count_rows(con, f"select count(*) from {table_name}"), 1)
    checks = [
        ("non_finite_usage_amount", "not isfinite(usage_amount)"),
        ("non_finite_on_demand_cost", "not isfinite(on_demand_cost)"),
        ("non_finite_amortized_cost", "not isfinite(amortized_cost)"),
        (
            "zero_usage_with_nonzero_cost",
            "coalesce(usage_amount, 0) = 0 and (coalesce(on_demand_cost, 0) != 0 or coalesce(amortized_cost, 0) != 0)",
        ),
        ("negative_usage_amount", "usage_amount < 0"),
        ("negative_on_demand_cost", "on_demand_cost < 0"),
        ("negative_amortized_cost", "amortized_cost < 0"),
    ]
    return pd.DataFrame(
        [
            {
                "check_name": check_name,
                "failing_rows": _count_rows(con, f"select count(*) from {table_name} where {predicate}"),
                "failing_share": _count_rows(con, f"select count(*) from {table_name} where {predicate}") / row_count,
            }
            for check_name, predicate in checks
        ]
    )


def cost_usage_ratio_outputs(con: duckdb.DuckDBPyConnection, table_name: str = "usage_ready") -> dict[str, pd.DataFrame]:
    ratio_summary = con.execute(
        f"""
        with eligible as (
          select *, on_demand_cost / usage_amount as on_demand_cost_per_usage, amortized_cost / usage_amount as amortized_cost_per_usage
          from {table_name}
          where usage_amount > 0
        )
        select * from (
          select
            'on_demand_cost_per_usage' as ratio_name,
            count(*) as eligible_rows,
            count(*) filter (where not isfinite(on_demand_cost_per_usage)) as non_finite_ratio_rows,
            max(on_demand_cost_per_usage) as max_ratio,
            avg(on_demand_cost_per_usage) as avg_ratio
          from eligible
          union all
          select
            'amortized_cost_per_usage' as ratio_name,
            count(*) as eligible_rows,
            count(*) filter (where not isfinite(amortized_cost_per_usage)) as non_finite_ratio_rows,
            max(amortized_cost_per_usage) as max_ratio,
            avg(amortized_cost_per_usage) as avg_ratio
          from eligible
        ) order by ratio_name
        """
    ).df()
    return {
        "cost_usage_ratio_summary": ratio_summary,
        "top_on_demand_cost_per_usage_rows": con.execute(
            f"""
            select *, on_demand_cost / usage_amount as on_demand_cost_per_usage
            from {table_name}
            where usage_amount > 0
            order by on_demand_cost_per_usage desc, on_demand_cost desc
            limit 20
            """
        ).df(),
        "top_amortized_cost_per_usage_rows": con.execute(
            f"""
            select *, amortized_cost / usage_amount as amortized_cost_per_usage
            from {table_name}
            where usage_amount > 0
            order by amortized_cost_per_usage desc, amortized_cost desc
            limit 20
            """
        ).df(),
    }


def categorical_validation_summary(con: duckdb.DuckDBPyConnection, table_name: str = "usage_ready") -> pd.DataFrame:
    cost_types = cost_type_profile(con, table_name)[["cost_type", "row_count"]].copy()
    cost_types.columns = ["value", "row_count"]
    cost_types["category"] = "cost_type"
    cost_types["is_expected"] = [value in EXPECTED_COST_TYPES for value in cost_types["value"].tolist()]
    prefixes = con.execute(
        f"""
        select {_commitment_prefix_expr()} as value, count(*) as row_count
        from {table_name}
        group by 1
        order by row_count desc, value
        """
    ).df()
    prefixes["category"] = "commitment_key_prefix"
    prefixes["is_expected"] = [value in EXPECTED_COMMITMENT_PREFIXES for value in prefixes["value"].tolist()]
    columns = ["category", "value", "row_count", "is_expected"]
    return pd.concat([cost_types.loc[:, columns], prefixes.loc[:, columns]], ignore_index=True)


def commitment_consistency_outputs(con: duckdb.DuckDBPyConnection, table_name: str = "usage_ready") -> dict[str, pd.DataFrame]:
    linkage_field = "commitment" if "commitment" in _table_columns(con, table_name) else "commitment_key"
    row_count = max(_count_rows(con, f"select count(*) from {table_name}"), 1)
    checks = [
        ("usage_with_discount_missing_linkage", f"cost_type = 'Usage with Discount' and not ({_value_present_sql(linkage_field)})"),
        ("unused_commitment_missing_linkage", f"cost_type = 'Unused Commitment' and not ({_value_present_sql(linkage_field)})"),
        ("covered_rows_amortized_gt_on_demand", "cost_type = 'Usage with Discount' and amortized_cost > on_demand_cost"),
    ]
    summary_rows: list[dict[str, Any]] = []
    failure_frames: list[pd.DataFrame] = []
    for check_name, predicate in checks:
        failing_rows = _count_rows(con, f"select count(*) from {table_name} where {predicate}")
        summary_rows.append(
            {
                "check_name": check_name,
                "failing_rows": failing_rows,
                "failing_share": failing_rows / row_count,
                "linkage_field_used": linkage_field,
            }
        )
        frame = con.execute(
            f"""
            select *, '{check_name}' as failure_type
            from {table_name}
            where {predicate}
            limit 20
            """
        ).df()
        if not frame.empty:
            failure_frames.append(frame)
    failures = pd.concat(failure_frames, ignore_index=True) if failure_frames else pd.DataFrame(columns=["failure_type"])
    return {
        "commitment_consistency_summary": pd.DataFrame(summary_rows),
        "commitment_consistency_failures": failures,
    }


def top_usage_rows(con: duckdb.DuckDBPyConnection, table_name: str = "usage_ready") -> dict[str, pd.DataFrame]:
    return {
        "top_usage_amount_rows": _sample_rows(con, table_name, "usage_amount desc, on_demand_cost desc"),
        "top_on_demand_cost_rows": _sample_rows(con, table_name, "on_demand_cost desc, usage_amount desc"),
        "top_amortized_cost_rows": _sample_rows(con, table_name, "amortized_cost desc, on_demand_cost desc"),
    }


def monthly_spike_flags(con: duckdb.DuckDBPyConnection, table_name: str = "usage_ready") -> pd.DataFrame:
    trend = monthly_aws_load_trend(con, table_name)
    months = _included_trend_months(trend)
    if not months:
        return pd.DataFrame(columns=["month", "total_on_demand_cost", "mom_on_demand_cost_delta", "mom_on_demand_cost_pct", "spike_flag"])
    flags = trend.loc[trend["month"].isin(months) & trend["mom_on_demand_cost_delta"].notna(), ["month", "total_on_demand_cost", "mom_on_demand_cost_delta", "mom_on_demand_cost_pct"]].copy()
    flags["spike_flag"] = ["increase" if value > 0 else "decrease" if value < 0 else "flat" for value in flags["mom_on_demand_cost_delta"].tolist()]
    return flags.sort_values(["mom_on_demand_cost_pct", "mom_on_demand_cost_delta"], ascending=[False, False])


def pricing_key_coverage_outputs(
    con: duckdb.DuckDBPyConnection,
    usage_table: str = "usage_ready",
    pricing_table: str = "pricing",
) -> dict[str, pd.DataFrame]:
    summary = con.execute(
        f"""
        with joined as (
          select usage.*, pricing.price_list_key is not null as has_pricing_match
          from {usage_table} as usage
          left join {pricing_table} as pricing
            on usage.price_list_key = pricing.price_list_key
        )
        select
          'overall' as grouping,
          cast(null as varchar) as product_code,
          count(*) as usage_rows,
          count(*) filter (where not has_pricing_match) as missing_pricing_rows,
          count(*) filter (where not has_pricing_match) * 1.0 / count(*) as missing_pricing_share
        from joined
        union all
        select
          'product_code' as grouping,
          product_code,
          count(*) as usage_rows,
          count(*) filter (where not has_pricing_match) as missing_pricing_rows,
          count(*) filter (where not has_pricing_match) * 1.0 / count(*) as missing_pricing_share
        from joined
        group by product_code
        order by grouping, missing_pricing_rows desc, product_code
        """
    ).df()
    missing_rows = con.execute(
        f"""
        select usage.*
        from {usage_table} as usage
        left join {pricing_table} as pricing
          on usage.price_list_key = pricing.price_list_key
        where pricing.price_list_key is null
        order by billing_period, product_code, price_list_key
        limit 20
        """
    ).df()
    return {
        "pricing_key_coverage_summary": summary,
        "missing_price_list_key_rows": missing_rows,
    }


def trend_metrics(monthly: pd.DataFrame) -> dict[str, Any]:
    included_months = _included_trend_months(monthly)
    direction = "insufficient_history"
    if len(included_months) >= 2:
        included = monthly.loc[monthly["month"].isin(included_months), :].reset_index(drop=True)
        delta = float(included.iloc[-1]["total_on_demand_cost"] - included.iloc[0]["total_on_demand_cost"])
        direction = "growing" if delta > 0 else "shrinking" if delta < 0 else "stable"
    return {
        "trend_direction": direction,
        "trend_months": included_months,
        "excluded_last_incomplete_month": len(monthly) != len(included_months),
    }


def metric_value(frame: pd.DataFrame, row_label: str, column_name: str) -> Any:
    rows = frame.loc[frame["check_name"] == row_label, column_name].tolist()
    return rows[0] if rows else 0


def sum_column(frame: pd.DataFrame, column_name: str) -> float:
    return float(sum(frame[column_name].tolist()))
