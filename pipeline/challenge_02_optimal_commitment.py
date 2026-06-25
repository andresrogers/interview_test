"""Purpose:
Generate the minimal Challenge 2 optimal Compute Savings Plan report and artifacts.

Owns:
- Linear Challenge 2 analysis flow.
- Challenge 2 tables, plots, markdown reports, and metrics.json outputs.

Does Not Own:
- Shared readiness rules.
- Shared hourly commitment allocation logic.

Main Entry Points:
- main

Key Invariants:
- The window is the most recent three complete billing periods.
- Only non-Spot `AWS#Compute*` usage is eligible for the optimizer.
- Commitment is allocated by discounted dollars per hour, highest discount first.

Update This Header When:
- Outputs change.
- Pricing view or window policy changes.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import duckdb
import matplotlib.pyplot as plt
import pandas as pd

from src.challenge_02 import (
    analysis_hours,
    build_metrics,
    build_report_texts,
    choose_analysis_window,
    duplicate_price_keys,
    load_optimizer_input,
    service_summary_frame,
    valid_optimizer_rows,
    validate_optimizer_inputs,
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

OUTPUT = Path("output/challenge_02")
TABLES = OUTPUT / "tables"
PLOTS = OUTPUT / "plots"

TERM_MONTHS = 36
PAYMENT_OPTION = "no_upfront"
OFFERING_CLASS = "savings_plan"

# Assumptions:
# - Challenge 2 uses the most recent three complete billing periods only.
# - Compute Savings Plan sizing is evaluated in discounted dollars per hour.
# - Spot rows and historical `Unused Commitment` rows are excluded from the hypothetical optimizer.


def write_text(path: Path, text: str) -> None:
    path.write_text(text.strip() + "\n", encoding="utf-8")


def _headline_float(optimum: dict[str, float | None], key: str) -> float:
    value = optimum.get(key)
    return 0.0 if value is None else float(value)


def write_tables(periods, joined, quarantined, service_summary, curve, hourly) -> None:
    periods.to_csv(TABLES / "billing_period_completeness.csv", index=False)
    joined.to_csv(TABLES / "compute_optimizer_input.csv", index=False)
    quarantined.to_csv(TABLES / "compute_optimizer_quarantine.csv", index=False)
    service_summary.to_csv(TABLES / "compute_service_summary.csv", index=False)
    curve.to_csv(TABLES / "savings_curve.csv", index=False)
    hourly.to_csv(TABLES / "hourly_commitment_summary.csv", index=False)


def commitment_options_frame(hourly_inputs, optimum: dict[str, float | None]) -> pd.DataFrame:
    optimum_commitment = _headline_float(optimum, "commitment_per_hour")
    candidates = [0.0, optimum_commitment * 0.5, optimum_commitment, optimum_commitment * 1.1]
    rows = []
    seen = set()
    for candidate in candidates:
        rounded = round(candidate, 6)
        if rounded in seen:
            continue
        seen.add(rounded)
        rows.append(evaluate_commitment(candidate, hourly_inputs))
    return pd.DataFrame(rows)


def write_reports(metrics, hourly, service_summary) -> None:
    write_text(OUTPUT / "metrics.json", json.dumps(metrics, indent=2))
    pricing_view = "3-year no-upfront compute_savings_plan / savings_plan"
    for name, text in build_report_texts(metrics, hourly, service_summary, metrics["warnings"], pricing_view).items():
        write_text(OUTPUT / name, text)


def plot_savings_curve(curve: pd.DataFrame, optimum: dict[str, float | None]) -> None:
    commitment = _headline_float(optimum, "commitment_per_hour")
    savings = _headline_float(optimum, "total_savings_dollars")
    plt.figure(figsize=(8, 4.5))
    plt.plot(curve["commitment_per_hour"], curve["total_savings_dollars"], color="#1f77b4")
    plt.scatter([commitment], [savings], color="#d62728", zorder=3)
    plt.axvline(commitment, color="#d62728", linestyle="--", alpha=0.6)
    plt.xlabel("commitment ($/hour, discounted)")
    plt.ylabel("total savings ($)")
    plt.title("Challenge 2 savings curve")
    plt.annotate(
        f"optimum\n${commitment:,.2f}/hr\n${savings:,.0f} savings",
        (commitment, savings),
        textcoords="offset points",
        xytext=(10, -25),
        fontsize=9,
        bbox={"boxstyle": "round,pad=0.3", "facecolor": "white", "edgecolor": "#c7c7c7"},
    )
    plt.tight_layout()
    plt.savefig(PLOTS / "savings_curve.png")
    plt.close()


def plot_hourly_profile(hourly: pd.DataFrame, optimum: dict[str, float | None]) -> None:
    plt.figure(figsize=(10, 4.5))
    plt.plot(hourly["analysis_timestamp"], hourly["eligible_discounted_cost"], label="Eligible discounted spend")
    plt.axhline(_headline_float(optimum, "commitment_per_hour"), color="#d62728", linestyle="--", label="Optimal commitment")
    plt.xticks(rotation=45, ha="right")
    plt.ylabel("$/hour")
    plt.title("Hourly eligible discounted spend vs optimal commitment")
    plt.legend()
    plt.tight_layout()
    plt.savefig(PLOTS / "hourly_commitment_profile.png")
    plt.close()


def plot_service_savings(service_summary: pd.DataFrame) -> None:
    top = service_summary.head(8).sort_values("gross_savings_if_fully_covered")
    plt.figure(figsize=(8, 4.5))
    plt.barh(top["product_code"], top["gross_savings_if_fully_covered"], color="#2ca02c")
    plt.xlabel("gross savings if fully covered ($)")
    plt.title("Compute services with the most gross upside")
    plt.tight_layout()
    plt.savefig(PLOTS / "service_gross_savings.png")
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
    included_periods, partial_periods, excluded_complete_periods = choose_analysis_window(periods)

    joined = load_optimizer_input(con, included_periods, TERM_MONTHS, PAYMENT_OPTION, OFFERING_CLASS)
    eligible_usage = valid_optimizer_rows(joined)
    validation_warnings, quarantined = validate_optimizer_inputs(
        joined,
        eligible_usage,
        duplicate_price_keys(con, TERM_MONTHS, PAYMENT_OPTION, OFFERING_CLASS),
    )
    validation_warnings.extend(issue_messages(issues, "warning"))

    hourly_inputs = build_hourly_inputs(eligible_usage, analysis_hours(included_periods))
    curve, optimum = optimize_commitment(hourly_inputs)
    hourly = hourly_summary(_headline_float(optimum, "commitment_per_hour"), hourly_inputs)
    service_summary = service_summary_frame(eligible_usage)
    options = commitment_options_frame(hourly_inputs, optimum)
    metrics = build_metrics(
        optimum,
        hourly,
        curve,
        included_periods,
        partial_periods,
        excluded_complete_periods,
        validation_warnings,
    )
    write_tables(periods, eligible_usage, quarantined, service_summary, curve, hourly)
    options.to_csv(TABLES / "commitment_options.csv", index=False)
    plot_savings_curve(curve, optimum)
    plot_hourly_profile(hourly, optimum)
    plot_service_savings(service_summary)
    write_reports(metrics, hourly, service_summary)

    print(OUTPUT)
    print(f"optimal commitment: ${_headline_float(optimum, 'commitment_per_hour'):,.2f}/hour")


if __name__ == "__main__":
    main()
