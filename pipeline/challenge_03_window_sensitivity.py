"""Purpose:
Generate the minimal Challenge 3 window-sensitivity report and artifacts.

Owns:
- Linear Challenge 3 analysis flow.
- Window-sensitivity tables, plots, markdown reports, and metrics.json outputs.

Does Not Own:
- Shared readiness rules.
- Shared hourly commitment allocation logic.

Main Entry Points:
- main

Key Invariants:
- Windows use complete billing periods only.
- Every window reuses the same Compute Savings Plan optimizer as Challenge 2.
- Anomaly review stays inside the main report files.

Update This Header When:
- Outputs change.
- Window policy changes.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import matplotlib.pyplot as plt
import pandas as pd

from src.challenge_02 import (
    analysis_hours,
    duplicate_price_keys,
    load_optimizer_input,
    valid_optimizer_rows,
    validate_optimizer_inputs,
)
from src.challenge_03 import build_metrics, build_report_texts, build_window_specs, monthly_regime_summary
from src.commitments import build_hourly_inputs, optimize_commitment
from src.cost_data import connect, load_pricing, load_usage
from src.data_quality import (
    assert_no_fatal_issues,
    billing_period_completeness,
    data_quality_issues,
    ensure_ready_usage_view,
    issue_messages,
)

OUTPUT = Path("output/challenge_03")
TABLES = OUTPUT / "tables"
PLOTS = OUTPUT / "plots"

TERM_MONTHS = 36
PAYMENT_OPTION = "no_upfront"
OFFERING_CLASS = "savings_plan"

# Assumptions:
# - Challenge 3 reuses the verified Challenge 2 compute optimizer unchanged.
# - Trailing windows use complete billing periods only.
# - Anchored sensitivity uses 3-month windows because that is the default sizing horizon.


def write_text(path: Path, text: str) -> None:
    path.write_text(text.strip() + "\n", encoding="utf-8")


def _window_colors(values: pd.Series, palette: dict[str, str]) -> list[str]:
    return [palette.get(str(value), "#7f7f7f") for value in values.tolist()]


def window_result_rows(con, specs: list[dict[str, Any]], duplicate_keys: int) -> tuple[pd.DataFrame, list[str]]:
    rows = []
    warnings = []
    for spec in specs:
        periods = cast(list[str], spec["billing_periods"])
        joined = load_optimizer_input(con, periods, TERM_MONTHS, PAYMENT_OPTION, OFFERING_CLASS)
        eligible = valid_optimizer_rows(joined)
        window_warnings, _ = validate_optimizer_inputs(joined, eligible, duplicate_keys)
        hours = analysis_hours(periods)
        hourly_inputs = build_hourly_inputs(eligible, hours)
        _, optimum = optimize_commitment(hourly_inputs)
        rows.append(
            {
                **{key: spec[key] for key in ["window_label", "window_type", "month_count", "start_period", "end_period"]},
                "billing_periods": ", ".join(periods),
                **optimum,
            }
        )
        warnings.extend(f"{spec['window_label']}: {message}" for message in window_warnings)
    return pd.DataFrame(rows), warnings


def write_tables(periods: pd.DataFrame, results: pd.DataFrame, regime: pd.DataFrame) -> None:
    periods.to_csv(TABLES / "billing_period_completeness.csv", index=False)
    results.to_csv(TABLES / "window_sensitivity.csv", index=False)
    regime.to_csv(TABLES / "monthly_compute_regime_change.csv", index=False)


def plot_optimal_levels(results: pd.DataFrame) -> None:
    plot = results.copy()
    colors = _window_colors(cast(pd.Series, plot["window_type"]), {"trailing": "#1f77b4", "anchored": "#ff7f0e"})
    plt.figure(figsize=(10, 4.5))
    plt.bar(plot["window_label"], plot["commitment_per_hour"], color=colors)
    plt.xticks(rotation=45, ha="right")
    plt.ylabel("commitment ($/hour, discounted)")
    plt.title("Optimal commitment by evaluation window")
    plt.tight_layout()
    plt.savefig(PLOTS / "optimal_level_by_window.png")
    plt.close()


def plot_savings(results: pd.DataFrame) -> None:
    plot = results.copy()
    colors = _window_colors(cast(pd.Series, plot["window_type"]), {"trailing": "#2ca02c", "anchored": "#9467bd"})
    plt.figure(figsize=(10, 4.5))
    plt.bar(plot["window_label"], plot["total_savings_dollars"], color=colors)
    plt.xticks(rotation=45, ha="right")
    plt.ylabel("net savings ($)")
    plt.title("Savings at the optimal commitment for each window")
    plt.tight_layout()
    plt.savefig(PLOTS / "savings_by_window.png")
    plt.close()


def plot_regime_change(regime: pd.DataFrame) -> None:
    plt.figure(figsize=(8.5, 4.5))
    plt.plot(regime["billing_period"], regime["eligible_discounted_cost"], marker="o")
    change = regime["discounted_cost_change"].dropna() if not regime.empty else pd.Series(dtype=float)
    if not change.empty:
        jump = regime.loc[change.abs().idxmax()]
        plt.axvline(jump["billing_period"], color="#d62728", linestyle="--", alpha=0.6)
        plt.annotate(
            "largest monthly move",
            (jump["billing_period"], jump["eligible_discounted_cost"]),
            textcoords="offset points",
            xytext=(10, 10),
            fontsize=9,
        )
    plt.ylabel("eligible discounted compute spend ($)")
    plt.title("Monthly compute spend used for regime-change review")
    plt.tight_layout()
    plt.savefig(PLOTS / "eligible_spend_regime_change.png")
    plt.close()


def write_reports(metrics: dict[str, object], results: pd.DataFrame, regime: pd.DataFrame) -> None:
    write_text(OUTPUT / "metrics.json", json.dumps(metrics, indent=2))
    for name, text in build_report_texts(metrics, results, regime).items():
        write_text(OUTPUT / name, text)


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
    complete_periods = periods.loc[periods["is_complete"], "billing_period"].tolist()
    specs = build_window_specs(complete_periods)
    results, validation_warnings = window_result_rows(
        con,
        specs,
        duplicate_price_keys(con, TERM_MONTHS, PAYMENT_OPTION, OFFERING_CLASS),
    )
    validation_warnings.extend(issue_messages(issues, "warning"))
    regime = monthly_regime_summary(con, complete_periods, TERM_MONTHS, PAYMENT_OPTION, OFFERING_CLASS)
    metrics = build_metrics(results, regime, validation_warnings)

    write_tables(periods, results, regime)
    write_reports(metrics, results, regime)
    plot_optimal_levels(results)
    plot_savings(results)
    plot_regime_change(regime)

    print(OUTPUT)
    print(f"recommended_commitment_per_hour={metrics['headline']['recommended_commitment_per_hour']:.6f}")


if __name__ == "__main__":
    main()
