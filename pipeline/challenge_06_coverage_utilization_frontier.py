"""Purpose:
Generate the minimal Challenge 6 frontier report and artifacts.

Owns:
- Linear Challenge 6 analysis flow.
- Frontier tables, plots, markdown reports, and metrics.json outputs.

Does Not Own:
- Shared readiness rules.
- Shared hourly commitment allocation logic.

Main Entry Points:
- main

Key Invariants:
- The frontier reuses the Challenge 2 three-complete-month window.
- Coverage and utilization stay separate metrics.
- Anomaly review stays inside the main report files.

Update This Header When:
- Outputs change.
- Window or recommendation policy changes.
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
from matplotlib.ticker import PercentFormatter

from src.challenge_02 import (
    analysis_hours,
    choose_analysis_window,
    duplicate_price_keys,
    load_optimizer_input,
    valid_optimizer_rows,
    validate_optimizer_inputs,
)
from src.challenge_06 import (
    build_metrics,
    build_report_texts,
    current_commitment_posture_from_inventory,
)
from src.commitments import (
    build_hourly_inputs,
    commitment_frontier,
    optimize_commitment,
)
from src.cost_data import connect, load_pricing, load_usage
from src.data_quality import (
    assert_no_fatal_issues,
    billing_period_completeness,
    data_quality_issues,
    ensure_ready_usage_view,
    issue_messages,
)

OUTPUT = Path("output/challenge_06")
TABLES = OUTPUT / "tables"
PLOTS = OUTPUT / "plots"

TERM_MONTHS = 36
PAYMENT_OPTION = "no_upfront"
OFFERING_CLASS = "savings_plan"

# Assumptions:
# - Challenge 6 uses the same 3 complete billing-period window as Challenge 2.
# - The frontier uses exact breakpoint commitments from the verified optimizer.
# - Current posture comes from the exported Challenge 5 commitment inventory.

CHALLENGE_05_INVENTORY = Path("output/challenge_05/tables/commitment_inventory.csv")


def write_text(path: Path, text: str) -> None:
    path.write_text(text.strip() + "\n", encoding="utf-8")


def write_tables(periods, frontier) -> None:
    periods.to_csv(TABLES / "billing_period_completeness.csv", index=False)
    frontier.to_csv(TABLES / "frontier.csv", index=False)


def frontier_candidates(curve, max_points: int = 251) -> list[float]:
    commitments = curve["commitment_per_hour"].tolist()
    if len(commitments) <= max_points:
        return commitments
    last_index = len(commitments) - 1
    sampled_positions = [
        round(step * last_index / (max_points - 1)) for step in range(max_points)
    ]
    sampled = []
    seen = set()
    for position in sampled_positions:
        commitment = float(commitments[position])
        key = round(commitment, 9)
        if key in seen:
            continue
        seen.add(key)
        sampled.append(commitment)
    if sampled[-1] != commitments[-1]:
        sampled.append(float(commitments[-1]))
    return sampled


def load_challenge_05_inventory(path: Path = CHALLENGE_05_INVENTORY) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Challenge 6 needs Challenge 5 inventory at {path}")
    return pd.read_csv(path)


def plot_frontier(frontier, metrics) -> None:
    current = metrics["current_posture"]
    headline = metrics["headline"]
    recommended = frontier.loc[
        frontier["commitment_per_hour"] == headline["recommended_commitment_per_hour"]
    ].iloc[0]
    plt.figure(figsize=(8, 5))
    plt.plot(
        frontier["coverage_rate"], frontier["average_utilization"], color="#1f77b4"
    )
    plt.scatter(
        [recommended["coverage_rate"]],
        [recommended["average_utilization"]],
        color="#d62728",
        label="Recommended",
    )
    if (
        current["coverage_rate"] is not None
        and current["average_utilization"] is not None
    ):
        plt.scatter(
            [current["coverage_rate"]],
            [current["average_utilization"]],
            color="#2ca02c",
            label="Current",
        )
    plt.xlabel("coverage rate")
    plt.ylabel("average utilization")
    plt.title("Coverage-utilization frontier")
    plt.legend()
    plt.tight_layout()
    plt.savefig(PLOTS / "coverage_utilization_frontier.png")
    plt.close()


def plot_bubble(frontier, metrics) -> None:
    current = metrics["current_posture"]
    plot_df = frontier.dropna(
        subset=[
            "coverage_rate",
            "average_utilization",
            "commitment_per_hour",
            "total_savings_dollars",
        ]
    ).sort_values("commitment_per_hour")
    if plot_df.empty:
        return

    max_savings = float(plot_df["total_savings_dollars"].clip(lower=0).max())
    sizes = plot_df["total_savings_dollars"].clip(lower=0)
    if max_savings > 0:
        sizes = 40 + 260 * sizes / max_savings
    else:
        sizes = pd.Series(60.0, index=plot_df.index)

    fig, ax = plt.subplots(figsize=(8.5, 5))
    ax.plot(
        plot_df["coverage_rate"],
        plot_df["average_utilization"],
        color="#25364a",
        linewidth=1.2,
        alpha=0.5,
        label="Frontier path",
    )
    scatter = ax.scatter(
        plot_df["coverage_rate"],
        plot_df["average_utilization"],
        s=sizes,
        c=plot_df["commitment_per_hour"],
        cmap="viridis",
        alpha=0.8,
        edgecolors="#25364a",
        linewidths=0.4,
        label="Candidate commitments",
    )
    best = plot_df.loc[plot_df["total_savings_dollars"].idxmax()]
    ax.scatter(
        [best["coverage_rate"]],
        [best["average_utilization"]],
        s=180,
        marker="*",
        color="#ff7f0e",
        edgecolors="#25364a",
        linewidths=0.8,
        label="Max savings",
        zorder=5,
    )
    if (
        current["coverage_rate"] is not None
        and current["average_utilization"] is not None
    ):
        ax.scatter(
            [current["coverage_rate"]],
            [current["average_utilization"]],
            s=140,
            marker="X",
            color="#d62728",
            edgecolors="#25364a",
            linewidths=0.8,
            label="Current posture",
            zorder=6,
        )
    ax.set_xlabel("Coverage rate")
    ax.set_ylabel("Average utilization")
    ax.set_title("Commitment frontier: coverage vs utilization")
    ax.xaxis.set_major_formatter(PercentFormatter(1.0))
    ax.yaxis.set_major_formatter(PercentFormatter(1.0))
    ax.grid(color="#d9e2ec", linewidth=0.8)
    ax.set_axisbelow(True)
    ax.legend(loc="lower right")
    colorbar = fig.colorbar(scatter, ax=ax)
    colorbar.set_label("commitment ($/hour)")
    plt.tight_layout()
    plt.savefig(PLOTS / "savings_coverage_utilization_bubble.png")
    plt.close()


def write_reports(metrics, frontier) -> None:
    write_text(OUTPUT / "metrics.json", json.dumps(metrics, indent=2))
    for name, text in build_report_texts(metrics, frontier).items():
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
    included_periods, _, _ = choose_analysis_window(periods)

    joined = load_optimizer_input(
        con, included_periods, TERM_MONTHS, PAYMENT_OPTION, OFFERING_CLASS
    )
    eligible_usage = valid_optimizer_rows(joined)
    validation_warnings, _ = validate_optimizer_inputs(
        joined,
        eligible_usage,
        duplicate_price_keys(con, TERM_MONTHS, PAYMENT_OPTION, OFFERING_CLASS),
    )
    validation_warnings.extend(issue_messages(issues, "warning"))
    hours = analysis_hours(included_periods)
    hourly_inputs = build_hourly_inputs(eligible_usage, hours)
    curve, _ = optimize_commitment(hourly_inputs)
    exact_breakpoint_count = len(curve)
    candidates = frontier_candidates(curve)
    frontier = commitment_frontier(candidates, hourly_inputs)
    inventory = load_challenge_05_inventory()
    current = current_commitment_posture_from_inventory(
        inventory,
        float(eligible_usage["on_demand_cost"].to_numpy(dtype=float).sum()),
        len(hours),
    )
    metrics = build_metrics(
        frontier, current, validation_warnings, exact_breakpoint_count, len(frontier)
    )

    write_tables(periods, frontier)
    write_reports(metrics, frontier)
    plot_frontier(frontier, metrics)
    plot_bubble(frontier, metrics)

    print(OUTPUT)
    print(
        f"recommended_commitment_per_hour={metrics['headline']['recommended_commitment_per_hour']:.6f}"
    )


if __name__ == "__main__":
    main()
