"""Purpose:
Load documented parquet inputs into DuckDB views.

Owns:
- Input path constants for usage and pricing parquet files.
- Lightweight DuckDB view registration for pipeline scripts.

Does Not Own:
- Data-quality checks.
- Challenge-specific aggregations or report writing.

Main Entry Points:
- connect
- load_usage
- load_pricing

Key Invariants:
- Raw usage data stays immutable.

Update This Header When:
- Public entry points change.
- Path ownership changes.
"""

from __future__ import annotations

from pathlib import Path

import duckdb

RAW_USAGE_PATH = Path("output/candidate_dataset.parquet")
PRICING_PATH = Path("output/pricing_options_filtered.parquet")


def connect() -> duckdb.DuckDBPyConnection:
    return duckdb.connect()


def _parquet_path_sql(path: Path) -> str:
    return str(path).replace("'", "''")


def load_usage(
    con: duckdb.DuckDBPyConnection,
    path: Path | None = None,
    view_name: str = "usage",
) -> str:
    target = path or RAW_USAGE_PATH
    con.execute(
        f"create or replace view {view_name} as select * from read_parquet('{_parquet_path_sql(target)}')"
    )
    return view_name


def load_pricing(
    con: duckdb.DuckDBPyConnection,
    path: Path = PRICING_PATH,
    view_name: str = "pricing",
) -> str:
    con.execute(
        f"create or replace view {view_name} as select * from read_parquet('{_parquet_path_sql(path)}')"
    )
    return view_name
