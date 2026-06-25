"""Purpose:
Generate the minimal Challenge 4 baseline-backtest report and artifacts.

Owns:
- Linear Challenge 4 analysis flow.
- Challenge 4 tables, plots, markdown reports, and metrics.json outputs.

Does Not Own:
- Shared readiness rules.
- Shared hourly commitment allocation logic.

Main Entry Points:
- main

Key Invariants:
- The compute baseline commitment is fixed after the anchor month.
- Baseline and hindsight-optimal scenarios use the same forward window.
- Reconciliation checks are written to metrics.json.

Update This Header When:
- Outputs change.
- Anchor policy changes.
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

from src.challenge_02 import analysis_hours, duplicate_price_keys, load_optimizer_input, valid_optimizer_rows, validate_optimizer_inputs
from src.challenge_04 import (
    build_metrics,
    build_report_texts,
    choose_baseline_backtest_window,
    extract_baseline_commitment,
    monthly_backtest,
    scenario_row,
)
from src.commitments import build_hourly_inputs, evaluate_commitment, hourly_summary, optimize_commitment
from src.cost_data import connect, load_pricing, load_usage
from src.data_quality import (
    assert_no_fatal_issues,
    billing_period_completeness,
    data_quality_issues,
    ensure_ready_usage_view,
    issue_messages,
)

OUTPUT = Path("output/challenge_04")
TABLES = OUTPUT / "tables"
PLOTS = OUTPUT / "plots"

TERM_MONTHS = 36
PAYMENT_OPTION = "no_upfront"
OFFERING_CLASS = "savings_plan"

# Assumptions:
# - The anchor month is the nearest complete month roughly nine months before the latest complete month.
# - The fixed baseline level is the final compute `baseline_max` observed in that anchor month.
# - The backtest scope is Compute Savings Plan-eligible non-Spot usage only.


def write_text(path: Path, text: str) -> None:
    path.write_text(text.strip() + "\n", encoding="utf-8")


def write_tables(periods, tables: dict[str, pd.DataFrame]) -> None:
    periods.to_csv(TABLES / "billing_period_completeness.csv", index=False)
    for name, frame in tables.items():
        frame.to_csv(TABLES / name, index=False)


def plot_hourly_spend(hourly: pd.DataFrame, baseline_commitment: float, optimal_commitment: float) -> None:
    plt.figure(figsize=(10, 4.5))
    plt.plot(hourly["analysis_timestamp"], hourly["eligible_discounted_cost"], color="#1f77b4", label="Eligible discounted spend")
    plt.axhline(baseline_commitment, color="#d62728", linestyle="--", label="Fixed baseline")
    plt.axhline(optimal_commitment, color="#2ca02c", linestyle=":", label="Hindsight optimum")
    plt.xticks(rotation=45, ha="right")
    plt.ylabel("$/hour")
    plt.title("Challenge 4 baseline vs hourly eligible discounted spend")
    plt.legend()
    plt.tight_layout()
    plt.savefig(PLOTS / "baseline_vs_hourly_eligible_spend.png")
    plt.close()


def plot_gap_decomposition(baseline_monthly: pd.DataFrame, optimum_monthly: pd.DataFrame) -> None:
    merged = baseline_monthly.merge(optimum_monthly, on="billing_period", suffixes=("_baseline", "_optimal"))
    gross_gap = merged["gross_savings_optimal"] - merged["gross_savings_baseline"]
    waste_gap = merged["unused_commitment_waste_baseline"] - merged["unused_commitment_waste_optimal"]
    plt.figure(figsize=(9, 4.5))
    plt.bar(merged["billing_period"], gross_gap, label="Extra gross savings at optimum")
    plt.bar(merged["billing_period"], waste_gap, bottom=gross_gap, label="Waste avoided vs baseline")
    plt.xticks(rotation=45, ha="right")
    plt.ylabel("dollars")
    plt.title("Challenge 4 monthly gap decomposition")
    plt.legend()
    plt.tight_layout()
    plt.savefig(PLOTS / "baseline_gap_decomposition.png")
    plt.close()


def main() -> None:
    TABLES.mkdir(parents=True, exist_ok=True)
    PLOTS.mkdir(parents=True, exist_ok=True)

    con = connect()
    load_usage(con)
    load_pricing(con)

    issues = data_quality_issues(con)
    assert_no_fatal_issues(issues)
    ensure_ready_usage_view(con)
    periods = billing_period_completeness(con)
    anchor_period, forward_periods, partial_periods = choose_baseline_backtest_window(periods)
    baseline_commitment, anchor_timestamp = extract_baseline_commitment(con, anchor_period)

    joined = load_optimizer_input(con, forward_periods, TERM_MONTHS, PAYMENT_OPTION, OFFERING_CLASS)
    eligible_usage = valid_optimizer_rows(joined)
    warnings, quarantined = validate_optimizer_inputs(
        joined,
        eligible_usage,
        duplicate_price_keys(con, TERM_MONTHS, PAYMENT_OPTION, OFFERING_CLASS),
    )
    warnings.extend(issue_messages(issues, "warning"))

    hours = analysis_hours(forward_periods)
    hourly_inputs = build_hourly_inputs(eligible_usage, hours)
    baseline = evaluate_commitment(baseline_commitment, hourly_inputs)
    curve, optimum = optimize_commitment(hourly_inputs)
    baseline_hourly = hourly_summary(baseline_commitment, hourly_inputs)
    optimum_hourly = hourly_summary(float(optimum["commitment_per_hour"] or 0.0), hourly_inputs)
    baseline_monthly = monthly_backtest(baseline_hourly)
    optimum_monthly = monthly_backtest(optimum_hourly)
    baseline["total_gross_savings_dollars"] = float(baseline_hourly["gross_savings"].to_numpy(dtype=float).sum())
    optimum["total_gross_savings_dollars"] = float(optimum_hourly["gross_savings"].to_numpy(dtype=float).sum())
    scenario_table = pd.DataFrame([scenario_row("baseline", baseline), scenario_row("optimal", optimum)])
    metrics = build_metrics(
        {
            "anchor_period": anchor_period,
            "anchor_timestamp": anchor_timestamp,
            "forward_periods": forward_periods,
            "partial_periods": partial_periods,
            "baseline": baseline,
            "optimal": optimum,
            "baseline_hourly": baseline_hourly,
            "baseline_monthly": baseline_monthly,
            "optimal_hourly": optimum_hourly,
            "optimal_monthly": optimum_monthly,
            "warnings": warnings,
        }
    )
    write_tables(
        periods,
        {
            "compute_backtest_input.csv": eligible_usage,
            "compute_backtest_quarantine.csv": quarantined,
            "hourly_baseline_backtest.csv": baseline_hourly,
            "baseline_backtest_monthly.csv": baseline_monthly,
            "hourly_optimal_backtest.csv": optimum_hourly,
            "optimal_backtest_monthly.csv": optimum_monthly,
            "baseline_vs_optimal.csv": scenario_table,
        },
    )
    plot_hourly_spend(optimum_hourly, baseline_commitment, float(optimum["commitment_per_hour"] or 0.0))
    plot_gap_decomposition(baseline_monthly, optimum_monthly)

    write_text(OUTPUT / "metrics.json", json.dumps(metrics, indent=2))
    for name, text in build_report_texts(metrics).items():
        write_text(OUTPUT / name, text)

    print(OUTPUT)
    print(f"baseline realized savings rate: {baseline['effective_savings_rate']:.2%}" if baseline["effective_savings_rate"] is not None else OUTPUT)


if __name__ == "__main__":
    main()
