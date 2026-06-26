"""Purpose:
Generate the Challenge 5 commitment-audit report and artifacts.

Owns:
- Linear Challenge 5 analysis flow.
- Challenge 5 tables, plots, markdown reports, and metrics.json outputs.

Does Not Own:
- Shared readiness rules.
- Shared commitment metrics beyond this audit.

Main Entry Points:
- main

Key Invariants:
- The audit uses commitment-attributed rows only.
- `Unused Commitment` stays tied to the same commitment identifier.
- Coverage and utilization stay separate in the outputs.

Update This Header When:
- Outputs change.
- Audit window policy changes.
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
from matplotlib.colors import PowerNorm
from matplotlib.ticker import PercentFormatter

from src.challenge_02 import choose_analysis_window
from src.challenge_05 import (
    build_commitment_inventory,
    build_commitment_monthly,
    build_metrics,
    build_report_texts,
    load_commitment_audit_rows,
    validate_commitment_audit_inputs,
)
from src.cost_data import connect, load_pricing, load_usage
from src.data_quality import (
    assert_no_fatal_issues,
    billing_period_completeness,
    data_quality_issues,
    ensure_ready_usage_view,
    issue_messages,
)

OUTPUT = Path("output/challenge_05")
TABLES = OUTPUT / "tables"
PLOTS = OUTPUT / "plots"

# Assumptions:
# - The audit uses the most recent three complete billing periods as the current posture window.
# - Commitment inventory is reconstructed from `commitment`, `Usage with Discount`, and `Unused Commitment` rows only.
# - Per-commitment under-sizing is a proxy based on high utilization plus same-product on-demand residuals.


def write_text(path: Path, text: str) -> None:
    path.write_text(text.strip() + "\n", encoding="utf-8")


def write_tables(periods, inventory, monthly, audit_rows) -> None:
    periods.to_csv(TABLES / "billing_period_completeness.csv", index=False)
    audit_rows.to_csv(TABLES / "commitment_audit_rows.csv", index=False)
    inventory.to_csv(TABLES / "commitment_inventory.csv", index=False)
    monthly.to_csv(TABLES / "commitment_monthly_utilization.csv", index=False)


def _commitment_label(row: dict) -> str:
    scope = str(row.get("scope_label", "unknown")).replace("_", " ").title()
    commitment = str(row["commitment"])
    return f"{scope} • …{commitment[-8:]}"


def _commitment_labels(frame: pd.DataFrame) -> dict[str, str]:
    return {str(row["commitment"]): _commitment_label(row) for row in frame.to_dict("records")}


def _review_priority(inventory: pd.DataFrame) -> pd.DataFrame:
    return inventory.sort_values(
        ["unused_commitment_waste", "utilization", "paid_commitment"],
        ascending=[False, True, False],
        na_position="last",
    )


def plot_utilization_heatmap(monthly: pd.DataFrame, inventory: pd.DataFrame) -> None:
    selected = _review_priority(inventory).head(12)
    top_commitments = selected["commitment"].tolist()
    pivot = monthly.loc[monthly["commitment"].isin(top_commitments)].pivot(
        index="commitment", columns="billing_period", values="utilization"
    )
    if pivot.empty:
        return
    plot_data = pivot.reindex(top_commitments).fillna(0.0)
    labels = _commitment_labels(selected)
    fig, ax = plt.subplots(figsize=(10, max(4, 0.65 * len(plot_data))))
    image = ax.imshow(
        plot_data.to_numpy(),
        aspect="auto",
        cmap="viridis",
        norm=PowerNorm(gamma=0.7, vmin=0.0, vmax=1.0),
    )
    ax.set_xticks(range(len(pivot.columns)))
    ax.set_xticklabels(pivot.columns, rotation=45, ha="right")
    ax.set_yticks(range(len(plot_data.index)))
    ax.set_yticklabels([labels[value] for value in plot_data.index])
    ax.set_xlabel("Billing period")
    ax.set_ylabel("12 commitments most worth reviewing")
    ax.set_title("Review-priority commitments: monthly utilization")
    for row_index, values in enumerate(plot_data.to_numpy()):
        for col_index, value in enumerate(values):
            text_color = "white" if value >= 0.6 else "#1f2933"
            ax.text(col_index, row_index, f"{value:.0%}", ha="center", va="center", color=text_color, fontsize=8)
    colorbar = fig.colorbar(image, ax=ax)
    colorbar.set_label("Monthly utilization rate")
    plt.tight_layout()
    plt.savefig(PLOTS / "commitment_utilization_heatmap.png")
    plt.close()


def plot_waste_by_commitment(inventory: pd.DataFrame) -> None:
    top = inventory.sort_values("unused_commitment_waste", ascending=False).head(12)
    if top.empty:
        return
    labels = _commitment_labels(top)
    top = top.sort_values("unused_commitment_waste")
    fig, ax = plt.subplots(figsize=(10, max(4, 0.55 * len(top))))
    values = top["unused_commitment_waste"].tolist()
    bars = ax.barh(
        [labels[str(value)] for value in top["commitment"]],
        values,
        color="#e76f51",
        edgecolor="#b5523a",
    )
    ax.set_xlabel("Unused commitment spend ($)")
    ax.set_ylabel("12 highest unused-spend commitments")
    ax.set_title("Where unused commitment spend is concentrated")
    ax.grid(axis="x", color="#d9e2ec", linewidth=0.8)
    ax.set_axisbelow(True)
    for bar, value in zip(bars, values):
        ax.text(value, bar.get_y() + bar.get_height() / 2, f"  ${value:,.0f}", va="center", ha="left", fontsize=8)
    plt.tight_layout()
    plt.savefig(PLOTS / "waste_by_commitment.png")
    plt.close()


def plot_coverage_utilization_bubble(inventory: pd.DataFrame) -> None:
    if inventory.empty:
        return
    frame = inventory.copy()
    max_paid = float(frame["paid_commitment"].to_numpy(dtype=float).max()) or 1.0
    waste_max = float(frame["waste_share"].to_numpy(dtype=float).max())
    sizes = 80 + 900 * frame["paid_commitment"].to_numpy(dtype=float) / max_paid
    fig, ax = plt.subplots(figsize=(9, 5.5))
    scatter = ax.scatter(
        frame["portfolio_coverage_share"],
        frame["utilization"],
        s=sizes,
        c=frame["waste_share"],
        cmap="OrRd",
        vmin=0.0,
        vmax=max(0.25, waste_max),
        alpha=0.8,
        edgecolors="#25364a",
        linewidths=0.6,
    )
    labels = _commitment_labels(frame)
    for row in frame.sort_values("unused_commitment_waste", ascending=False).head(5).to_dict("records"):
        ax.annotate(labels[str(row["commitment"])], (row["portfolio_coverage_share"], row["utilization"]), fontsize=7)
    ax.axhline(0.85, color="#d1495b", linestyle="--", linewidth=1, label="Review below 85% utilization")
    ax.set_xlabel("Share of covered eligible spend")
    ax.set_ylabel("Utilization")
    ax.set_title("Coverage vs. utilization by commitment")
    ax.xaxis.set_major_formatter(PercentFormatter(1.0))
    ax.yaxis.set_major_formatter(PercentFormatter(1.0))
    ax.grid(color="#d9e2ec", linewidth=0.8)
    ax.set_axisbelow(True)
    ax.legend(loc="lower right")
    colorbar = fig.colorbar(scatter, ax=ax, label="Waste share of paid commitment")
    colorbar.ax.yaxis.set_major_formatter(PercentFormatter(1.0))
    plt.tight_layout()
    plt.savefig(PLOTS / "coverage_utilization_bubble.png")
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
    included_periods, partial_periods, _ = choose_analysis_window(periods)
    account_usage = con.execute(
        f"""
        select *
        from usage_ready
        where billing_period in ({", ".join(f"'{period}'" for period in included_periods)})
        """
    ).df()
    audit_rows = load_commitment_audit_rows(con, included_periods)
    warnings = validate_commitment_audit_inputs(audit_rows)
    warnings.extend(issue_messages(issues, "warning"))
    inventory = build_commitment_inventory(audit_rows, account_usage)
    monthly = build_commitment_monthly(audit_rows)
    metrics = build_metrics(inventory, monthly, account_usage, included_periods, partial_periods, warnings)

    write_tables(periods, inventory, monthly, audit_rows)
    plot_utilization_heatmap(monthly, inventory)
    plot_waste_by_commitment(inventory)
    plot_coverage_utilization_bubble(inventory)

    write_text(OUTPUT / "metrics.json", json.dumps(metrics, indent=2))
    for name, text in build_report_texts(metrics, inventory).items():
        write_text(OUTPUT / name, text)

    print(OUTPUT)
    headline = metrics["headline"]
    print(f"portfolio utilization: {headline['portfolio_utilization']:.2%}" if headline["portfolio_utilization"] is not None else OUTPUT)


if __name__ == "__main__":
    main()
