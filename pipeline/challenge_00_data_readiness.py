"""Purpose:
Generate the minimal Challenge 0 data readiness report.

Owns:
- Challenge 0 tables, plots, markdown reports, and metrics.json.

Does Not Own:
- Challenge-specific savings metrics.
- Raw data mutation.

Main Entry Points:
- main

Key Invariants:
- Raw source parquet is never edited.
- Readiness cleaning is explicit, reversible, and documented.
- Off-hour artifacts are normalized into `analysis_timestamp`, not hidden.

Update This Header When:
- Outputs change.
- Readiness rules change.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import matplotlib.pyplot as plt

from src.challenge_00 import build_metrics, build_report_texts, collect_outputs, write_tables
from src.cost_data import RAW_USAGE_PATH, connect, load_pricing, load_usage
from src.data_quality import assert_no_fatal_issues, ensure_ready_usage_view

OUTPUT = Path("output/challenge_00")
TABLES = OUTPUT / "tables"
PLOTS = OUTPUT / "plots"

# Assumptions:
# - Raw parquet files under `output/` are the only source inputs.
# - Readiness normalizes timestamp artifacts for analysis but preserves raw timestamps.
# - Later challenges should rebuild the shared readiness view directly from the documented source parquet files.


def write_text(path: Path, text: str) -> None:
    path.write_text(text.strip() + "\n", encoding="utf-8")


def main() -> None:
    TABLES.mkdir(parents=True, exist_ok=True)
    PLOTS.mkdir(parents=True, exist_ok=True)

    con = connect()
    load_usage(con, path=RAW_USAGE_PATH)
    load_pricing(con)
    ensure_ready_usage_view(con)

    outputs = collect_outputs(con)
    assert_no_fatal_issues(outputs["issues"])
    metrics = build_metrics(con, outputs)
    write_tables(outputs, TABLES)

    plt.figure(figsize=(8, 4))
    plt.plot(outputs["monthly"]["billing_period"], outputs["monthly"]["row_count"], marker="o")
    plt.xticks(rotation=45, ha="right")
    plt.ylabel("row count")
    plt.title("Monthly dataset row count")
    plt.tight_layout()
    plt.savefig(PLOTS / "monthly_row_counts.png")
    plt.close()

    complete_periods = outputs["periods"].loc[outputs["periods"]["is_complete"], "billing_period"]
    monthly_complete = outputs["monthly"].loc[outputs["monthly"]["billing_period"].isin(complete_periods)]

    plt.figure(figsize=(8, 4))
    plt.plot(monthly_complete["billing_period"], monthly_complete["on_demand_cost"], marker="o", label="on_demand_cost")
    plt.plot(monthly_complete["billing_period"], monthly_complete["amortized_cost"], marker="o", label="amortized_cost")
    plt.xticks(rotation=45, ha="right")
    plt.ylabel("cost ($)")
    plt.title("Monthly cost profile")
    plt.legend()
    plt.tight_layout()
    plt.savefig(PLOTS / "monthly_cost_profile.png")
    plt.close()

    trend = outputs["monthly_trend"].loc[outputs["monthly_trend"]["is_complete_month"]]
    plt.figure(figsize=(8, 4))
    plt.plot(trend["month"], trend["total_on_demand_cost"], marker="o")
    plt.xticks(rotation=45, ha="right")
    plt.ylabel("on-demand cost ($)")
    plt.title("Monthly AWS load trend")
    plt.tight_layout()
    plt.savefig(PLOTS / "monthly_aws_load_trend.png")
    plt.close()

    trend_by_service = outputs["monthly_trend_by_service"]
    if not trend_by_service.empty:
        plt.figure(figsize=(9, 4))
        for product_code, frame in trend_by_service.groupby("product_code"):
            plt.plot(frame["month"], frame["total_on_demand_cost"], marker="o", label=product_code)
        plt.xticks(rotation=45, ha="right")
        plt.ylabel("on-demand cost ($)")
        plt.title("Monthly AWS load trend by top services")
        plt.legend()
        plt.tight_layout()
        plt.savefig(PLOTS / "monthly_aws_load_trend_by_service.png")
        plt.close()

    write_text(OUTPUT / "metrics.json", json.dumps(metrics, indent=2))
    for name, text in build_report_texts(metrics).items():
        write_text(OUTPUT / name, text)

    print(OUTPUT)
    print(metrics["trust_level"])


if __name__ == "__main__":
    main()
