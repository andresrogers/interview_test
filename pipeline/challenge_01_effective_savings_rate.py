"""Purpose:
Generate the minimal Challenge 1 effective savings report and artifacts.

Owns:
- Linear Challenge 1 analysis flow.
- Challenge 1 tables, plots, markdown reports, and metrics.json outputs.

Does Not Own:
- Shared readiness rules.
- Later challenge optimization logic.

Main Entry Points:
- main

Key Invariants:
- Effective savings rate is computed as total savings divided by total on-demand cost.
- Only complete billing periods are included in the default analysis window.
- Unused commitment is treated as waste in the report narrative and metrics.

Update This Header When:
- Outputs change.
- Analysis window policy changes.
- Challenge 1 responsibilities change.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from matplotlib.ticker import FuncFormatter

from src.challenge_01 import build_metrics, build_report_texts, choose_analysis_window, collect_outputs
from src.cost_data import connect, load_pricing, load_usage
from src.data_quality import (
    assert_no_fatal_issues,
    billing_period_completeness,
    data_quality_issues,
    ensure_ready_usage_view,
    issue_messages,
)

OUTPUT = Path("output/challenge_01")
TABLES = OUTPUT / "tables"
PLOTS = OUTPUT / "plots"

# Assumptions:
# - Challenge 1 uses complete billing periods only to avoid partial-month distortion.
# - Effective savings compares actual amortized spend against on-demand counterfactual.
# - `Unused Commitment` rows represent waste already paid for and should be called out.


def write_text(path: Path, text: str) -> None:
    path.write_text(text.strip() + "\n", encoding="utf-8")


def _money_k(value: float) -> str:
    return f"${value / 1000:,.1f}k"


def _format_months(frame: pd.DataFrame) -> list[str]:
    return pd.to_datetime(frame["billing_period"] + "-01").dt.strftime("%b-%y").tolist()


def _label_bar(ax, x: float, y: float, value: float, always: bool = False) -> None:
    if not always and abs(value) <= 750:
        return
    va = "bottom" if y >= 0 else "top"
    offset = 3 if y >= 0 else -3
    ax.annotate(_money_k(value), (x, y), textcoords="offset points", xytext=(0, offset), ha="center", va=va, fontsize=8)


def write_tables(periods, outputs) -> None:
    periods.to_csv(TABLES / "billing_period_completeness.csv", index=False)
    outputs["service"].to_csv(TABLES / "effective_savings_by_service.csv", index=False)
    outputs["commitment"].to_csv(TABLES / "effective_savings_by_commitment.csv", index=False)
    outputs["instrument"].to_csv(TABLES / "effective_savings_by_instrument.csv", index=False)
    outputs["monthly"].to_csv(TABLES / "monthly_savings.csv", index=False)
    outputs["monthly_summary"].to_csv(TABLES / "monthly_savings_components.csv", index=False)
    outputs["cost_type"].to_csv(TABLES / "savings_by_cost_type.csv", index=False)


def plot_monthly_rate(outputs) -> None:
    plt.figure(figsize=(8, 4))
    plt.plot(outputs["monthly"]["billing_period"], outputs["monthly"]["effective_savings_rate"], marker="o")
    plt.xticks(rotation=45, ha="right")
    plt.ylabel("effective savings rate")
    plt.title("Monthly effective savings rate")
    plt.tight_layout()
    plt.savefig(PLOTS / "monthly_effective_savings_rate.png")
    plt.close()


def plot_service_savings(outputs) -> None:
    top_services = outputs["service"].head(10).sort_values("savings_dollars")
    plt.figure(figsize=(8, 5))
    plt.barh(top_services["product_code"], top_services["savings_dollars"])
    plt.xlabel("savings dollars")
    plt.title("Savings by service")
    plt.tight_layout()
    plt.savefig(PLOTS / "savings_by_service.png")
    plt.close()


def plot_instrument_decomposition(outputs) -> None:
    instrument_plot = outputs["instrument"].loc[
        (outputs["instrument"]["commitment_realized_savings_dollars"] > 0)
        | (outputs["instrument"]["spot_savings_vs_on_demand_dollars"] > 0)
        | (outputs["instrument"]["waste_dollars"] > 0)
    ].sort_values("net_savings_dollars")
    plt.figure(figsize=(9, 5))
    plt.barh(instrument_plot["instrument_family"], instrument_plot["commitment_realized_savings_dollars"], label="Commitment savings")
    plt.barh(
        instrument_plot["instrument_family"],
        instrument_plot["spot_savings_vs_on_demand_dollars"],
        left=instrument_plot["commitment_realized_savings_dollars"],
        label="Spot savings vs on-demand",
    )
    plt.barh(instrument_plot["instrument_family"], -instrument_plot["waste_dollars"], label="Waste")
    plt.xlabel("dollars")
    plt.title("Savings and waste by instrument")
    plt.legend()
    plt.tight_layout()
    plt.savefig(PLOTS / "instrument_savings_decomposition.png")
    plt.close()


def plot_monthly_components(outputs) -> None:
    monthly = outputs["monthly_summary"]
    plt.figure(figsize=(10, 5))
    plt.bar(monthly["billing_period"], monthly["commitment_savings_dollars"], label="Commitment savings")
    plt.bar(
        monthly["billing_period"],
        monthly["spot_savings_vs_on_demand_dollars"],
        bottom=monthly["commitment_savings_dollars"],
        label="Spot savings vs on-demand",
    )
    plt.bar(monthly["billing_period"], -monthly["waste_dollars"], label="Unused commitment waste")
    plt.plot(monthly["billing_period"], monthly["amortized_cost"], color="black", marker="o", label="Actual cost")
    plt.xticks(rotation=45, ha="right")
    plt.ylabel("dollars")
    plt.title("Monthly savings, waste, and actual cost")
    plt.legend()
    plt.tight_layout()
    plt.savefig(PLOTS / "monthly_savings_components.png")
    plt.close()


def _bridge_totals_text(df: pd.DataFrame) -> str:
    total_on_demand = float(df["on_demand_cost"].sum())
    total_actual = float(df["amortized_cost"].sum())
    total_net_savings = float(df["savings_dollars"].sum())
    total_waste = float(df["waste_dollars"].sum())
    rate = total_net_savings / total_on_demand
    return (
        f"Total on-demand equivalent: {_money_k(total_on_demand)}\n"
        f"Actual amortized cost: {_money_k(total_actual)}\n"
        f"Net savings: {_money_k(total_net_savings)}\n"
        f"Effective savings rate: {rate:.1%}\n"
        f"Unused commitment waste: {_money_k(total_waste)}"
    )


def _bridge_colors() -> dict[str, str]:
    return {
        "baseline": "#d3d3d3",
        "actual": "#1f2937",
        "commitment": "#2e8b57",
        "spot": "#2a9d8f",
        "waste": "#e76f51",
        "other": "#8d99ae",
    }


def _draw_bridge_month(ax, xs, row, width: float, colors: dict[str, str]) -> None:
    baseline = float(row["on_demand_cost"])
    actual = float(row["amortized_cost"])
    level = baseline
    ax.bar(xs[0], baseline, width=width, color=colors["baseline"])
    _label_bar(ax, xs[0], baseline, baseline, always=True)
    components = [
        (-float(row["commitment_savings_dollars"]), colors["commitment"]),
        (-float(row["spot_savings_vs_on_demand_dollars"]), colors["spot"]),
        (float(row["waste_dollars"]), colors["waste"]),
        (-float(row["other_reconciliation"]), colors["other"]),
    ]
    for offset, (delta, color) in enumerate(components, start=1):
        old = level
        level += delta
        ax.bar(xs[offset], abs(level - old), width=width, bottom=min(old, level), color=color)
        _label_bar(ax, xs[offset], max(old, level), abs(delta))
    assert abs(level - actual) < 1e-6
    ax.bar(xs[5], actual, width=width, color=colors["actual"])
    _label_bar(ax, xs[5], actual, actual, always=True)


def _bridge_legend(ax, colors: dict[str, str]) -> None:
    handles = [
        Patch(facecolor=colors["baseline"], label="On-demand equivalent"),
        Patch(facecolor=colors["commitment"], label="Commitment discount"),
        Patch(facecolor=colors["spot"], label="Spot market savings"),
        Patch(facecolor=colors["waste"], label="Unused commitment waste"),
        Patch(facecolor=colors["other"], label="Other / reconciliation"),
        Patch(facecolor=colors["actual"], label="Actual amortized cost"),
    ]
    ax.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, 1.18), ncol=3, frameon=False)


def plot_monthly_cost_bridge(outputs) -> None:
    df = outputs["monthly_summary"].copy().reset_index(drop=True)
    labels = _format_months(df)
    colors = _bridge_colors()
    fig, ax = plt.subplots(figsize=(14, 7.5))
    width = 0.11
    group_gap = 0.82
    group_width = 6 * width + group_gap
    centers = []
    for idx, row in df.iterrows():
        xs = [idx * group_width + step * width for step in range(6)]
        centers.append((xs[0] + xs[-1]) / 2)
        _draw_bridge_month(ax, xs, row, width, colors)
    ax.axhline(0, color="black", linewidth=0.8)
    ax.grid(axis="y", alpha=0.25)
    ax.set_xticks(centers)
    ax.set_xticklabels(labels)
    ax.set_ylabel("$k")
    ax.yaxis.set_major_formatter(FuncFormatter(lambda value, _: f"${value/1000:,.0f}k"))
    fig.suptitle("Monthly Cost Bridge: On-Demand Equivalent to Actual Cost", fontsize=16, fontweight="bold")
    ax.set_title(
        "Commitment discounts reduce cost, Spot savings are separate, and unused hourly commitment is shown as waste.",
        fontsize=10,
        pad=16,
    )
    _bridge_legend(ax, colors)
    ax.text(
        0.985,
        0.98,
        _bridge_totals_text(df),
        transform=ax.transAxes,
        ha="right",
        va="top",
        fontsize=9,
        bbox={"boxstyle": "round,pad=0.4", "facecolor": "white", "edgecolor": "#c7c7c7"},
    )
    fig.text(
        0.5,
        0.01,
        "The bridge starts from the on-demand equivalent, subtracts gross commitment and Spot savings, adds unused commitment waste, and lands on actual amortized cost.",
        ha="center",
        fontsize=10,
    )
    fig.tight_layout(rect=(0, 0.04, 1, 0.92))
    fig.savefig(PLOTS / "monthly_cost_bridge.png", dpi=200)
    plt.close(fig)


def plot_monthly_cost_summary(outputs) -> None:
    df = outputs["monthly_summary"].copy().reset_index(drop=True)
    labels = _format_months(df)
    x = list(range(len(df)))
    fig, ax = plt.subplots(figsize=(14, 7.5))
    width = 0.24
    ax.bar([v - width for v in x], df["on_demand_cost"], width=width, color="#d3d3d3", label="On-demand equivalent")
    ax.bar(x, df["amortized_cost"], width=width, color="#1f2937", label="Actual amortized cost")
    ax.bar([v + width for v in x], df["savings_dollars"], width=width, color="#2e8b57", label="Net savings")
    ax.scatter(x, df["waste_dollars"], color="#e76f51", marker="D", label="Unused commitment waste")
    rate_ax = ax.twinx()
    rate_ax.plot(x, df["effective_savings_rate"], color="#264653", marker="o", label="Effective savings rate")
    for idx, rate in enumerate(df["effective_savings_rate"]):
        if pd.notna(rate):
            rate_ax.annotate(f"{rate:.0%}", (x[idx], rate), textcoords="offset points", xytext=(0, 6), ha="center", fontsize=8)
    ax.grid(axis="y", alpha=0.25)
    ax.axhline(0, color="black", linewidth=0.8)
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_ylabel("$k")
    ax.yaxis.set_major_formatter(FuncFormatter(lambda value, _: f"${value/1000:,.0f}k"))
    rate_ax.set_ylabel("effective savings rate")
    rate_ax.yaxis.set_major_formatter(FuncFormatter(lambda value, _: f"{value:.0%}"))
    fig.suptitle("Commitments reduced cost, but unused hourly commitment reduced the effective savings.", fontsize=16, fontweight="bold")
    ax.set_title("Monthly Savings Decomposition: Commitments, Spot, and Waste", fontsize=10, pad=14)
    handles = [
        Patch(facecolor="#d3d3d3", label="On-demand equivalent"),
        Patch(facecolor="#1f2937", label="Actual amortized cost"),
        Patch(facecolor="#2e8b57", label="Net savings"),
        Line2D([0], [0], color="#e76f51", marker="D", linestyle="None", label="Unused commitment waste"),
        Line2D([0], [0], color="#264653", marker="o", label="Effective savings rate"),
    ]
    ax.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, 1.14), ncol=5, frameon=False)
    fig.tight_layout(rect=(0, 0.02, 1, 0.9))
    fig.savefig(PLOTS / "monthly_cost_summary.png", dpi=200)
    plt.close(fig)


def print_qa_table(outputs, metrics) -> None:
    df = outputs["monthly_summary"]
    headline = metrics["headline"]
    largest_waste = df.loc[df["waste_dollars"].idxmax(), "billing_period"]
    largest_spot = df.loc[df["spot_savings_vs_on_demand_dollars"].idxmax(), "billing_period"]
    largest_commitment = df.loc[df["commitment_savings_dollars"].idxmax(), "billing_period"]
    lines = [
        f"Total on-demand equivalent: {_money_k(float(df['on_demand_cost'].sum()))}",
        f"Total amortized actual cost: {_money_k(float(df['amortized_cost'].sum()))}",
        f"Total net savings: {_money_k(float(df['savings_dollars'].sum()))}",
        f"Total gross commitment discount: {_money_k(headline['commitment_savings_dollars'])}",
        f"Total Spot market savings: {_money_k(headline['spot_savings_vs_on_demand_dollars'])}",
        f"Total unused commitment waste: {_money_k(headline['waste_dollars'])}",
        f"Total other / reconciliation: {_money_k(headline['other_reconciliation_dollars'])}",
        f"Effective savings rate: {headline['effective_savings_rate']:.2%}",
        f"Max monthly savings rate: {df['effective_savings_rate'].max():.2%}",
        f"Min monthly savings rate: {df['effective_savings_rate'].min():.2%}",
        f"Largest waste month: {largest_waste}",
        f"Largest Spot savings month: {largest_spot}",
        f"Largest commitment savings month: {largest_commitment}",
    ]
    for line in lines:
        print(line)


def main() -> None:
    TABLES.mkdir(parents=True, exist_ok=True)
    PLOTS.mkdir(parents=True, exist_ok=True)

    con = connect()
    load_usage(con)
    load_pricing(con)
    ensure_ready_usage_view(con)

    issues = data_quality_issues(con)
    assert_no_fatal_issues(issues)
    validation_warnings = issue_messages(issues, "warning")
    periods = billing_period_completeness(con)
    complete_periods, partial_periods = choose_analysis_window(periods)
    outputs = collect_outputs(con, complete_periods)

    write_tables(periods, outputs)
    plot_monthly_rate(outputs)
    plot_service_savings(outputs)
    plot_instrument_decomposition(outputs)
    plot_monthly_components(outputs)
    plot_monthly_cost_bridge(outputs)
    plot_monthly_cost_summary(outputs)

    metrics = build_metrics(outputs, complete_periods, partial_periods, validation_warnings)
    reports = build_report_texts(metrics, complete_periods, partial_periods, outputs, validation_warnings)
    write_text(OUTPUT / "metrics.json", json.dumps(metrics, indent=2))
    for name, text in reports.items():
        write_text(OUTPUT / name, text)

    print(OUTPUT)
    print("n/a" if metrics["headline"]["effective_savings_rate"] is None else f"{metrics['headline']['effective_savings_rate']:.4f}")
    print_qa_table(outputs, metrics)


if __name__ == "__main__":
    main()
