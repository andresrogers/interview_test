"""Purpose:
Build Challenge 0 duplicate diagnostics.

Owns:
- Exact full-row duplicate counts and samples.
- Duplicate hourly line-key counts and samples.

Does Not Own:
- Other Challenge 0 diagnostics.

Main Entry Points:
- duplicate_check_outputs

Key Invariants:
- Key-based duplicate checks use only columns present in the dataset.
- Outputs are report-only.

Update This Header When:
- Public entry points change.
- Duplicate key rules change.
"""

from __future__ import annotations

import duckdb
import pandas as pd

KEY_CANDIDATES = [
    "analysis_timestamp",
    "billing_period",
    "product_code",
    "usage_type",
    "operation",
    "region",
    "account_id",
    "resource_id",
    "resource",
    "price_list_key",
    "commitment_key",
    "cost_type",
]


def _quote(name: str) -> str:
    return f'"{name}"'


def _count_rows(con: duckdb.DuckDBPyConnection, stmt: str) -> int:
    row = con.execute(stmt).fetchone()
    return 0 if row is None else int(row[0])


def _table_columns(con: duckdb.DuckDBPyConnection, table_name: str) -> list[str]:
    return con.execute(f"describe select * from {table_name}").df()["column_name"].tolist()


def _group_duplicates(con: duckdb.DuckDBPyConnection, table_name: str, columns: list[str]) -> tuple[int, pd.DataFrame]:
    select_list = ", ".join(_quote(column) for column in columns)
    duplicate_count = _count_rows(
        con,
        f"""
        with duplicate_groups as (
          select {select_list}, count(*) as duplicate_instances
          from {table_name}
          group by {select_list}
          having count(*) > 1
        )
        select coalesce(sum(duplicate_instances - 1), 0)
        from duplicate_groups
        """,
    )
    sample = con.execute(
        f"""
        with duplicate_groups as (
          select {select_list}, count(*) as duplicate_instances
          from {table_name}
          group by {select_list}
          having count(*) > 1
        )
        select *
        from duplicate_groups
        order by duplicate_instances desc
        limit 20
        """
    ).df()
    return duplicate_count, sample


def _duplicate_key_rows(con: duckdb.DuckDBPyConnection, table_name: str, key_columns: list[str]) -> pd.DataFrame:
    if not key_columns:
        return pd.DataFrame(columns=["duplicate_instances"])
    key_list = ", ".join(_quote(column) for column in key_columns)
    return con.execute(
        f"""
        with duplicate_keys as (
          select {key_list}, count(*) as duplicate_instances
          from {table_name}
          group by {key_list}
          having count(*) > 1
        )
        select sample.*, duplicate_keys.duplicate_instances
        from {table_name} as sample
        join duplicate_keys using ({key_list})
        order by duplicate_keys.duplicate_instances desc
        limit 20
        """
    ).df()


def duplicate_check_outputs(con: duckdb.DuckDBPyConnection, table_name: str = "usage_ready") -> dict[str, pd.DataFrame]:
    columns = _table_columns(con, table_name)
    row_count = max(_count_rows(con, f"select count(*) from {table_name}"), 1)
    exact_duplicate_count, exact_duplicates = _group_duplicates(con, table_name, columns)
    key_columns = [column for column in KEY_CANDIDATES if column in columns]
    duplicate_key_count = 0
    duplicate_key_rows = pd.DataFrame(columns=key_columns + ["duplicate_instances"])
    if key_columns:
        duplicate_key_count, _ = _group_duplicates(con, table_name, key_columns)
        duplicate_key_rows = _duplicate_key_rows(con, table_name, key_columns)
    summary = pd.DataFrame(
        [
            {
                "check_name": "exact_full_row_duplicates",
                "duplicate_count": exact_duplicate_count,
                "duplicate_share": exact_duplicate_count / row_count,
                "key_columns_used": "all columns",
            },
            {
                "check_name": "duplicate_hourly_line_keys",
                "duplicate_count": duplicate_key_count,
                "duplicate_share": duplicate_key_count / row_count,
                "key_columns_used": ", ".join(key_columns),
            },
        ]
    )
    return {
        "duplicate_summary": summary,
        "exact_duplicate_rows": exact_duplicates,
        "duplicate_hourly_line_keys": duplicate_key_rows,
    }
