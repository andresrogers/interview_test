"""Purpose:
Generate the minimal Challenge 5 commitment-audit report and artifacts.

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


def plot_utilization_heatmap(monthly: pd.DataFrame, inventory: pd.DataFrame) -> None:
    top_commitments = inventory.head(12)["commitment"].tolist()
    pivot = monthly.loc[monthly["commitment"].isin(top_commitments)].pivot(
        index="commitment", columns="billing_period", values="utilization"
    )
    if pivot.empty:
        return
    fig, ax = plt.subplots(figsize=(9, max(3, 0.5 * len(pivot))))
    image = ax.imshow(pivot.fillna(0.0).to_numpy(), aspect="auto", cmap="YlGnBu", vmin=0.0, vmax=1.0)
    ax.set_xticks(range(len(pivot.columns)))
    ax.set_xticklabels(pivot.columns, rotation=45, ha="right")
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels([value[-12:] for value in pivot.index])
    ax.set_title("Challenge 5 commitment utilization heatmap")
    fig.colorbar(image, ax=ax, label="utilization")
    plt.tight_layout()
    plt.savefig(PLOTS / "commitment_utilization_heatmap.png")
    plt.close()


def plot_waste_by_commitment(inventory: pd.DataFrame) -> None:
    top = inventory.head(12).sort_values("unused_commitment_waste")
    plt.figure(figsize=(9, 5))
    plt.barh([value[-12:] for value in top["commitment"]], top["unused_commitment_waste"], color="#e76f51")
    plt.xlabel("unused commitment waste ($)")
    plt.title("Challenge 5 waste by commitment")
    plt.tight_layout()
    plt.savefig(PLOTS / "waste_by_commitment.png")
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

    write_text(OUTPUT / "metrics.json", json.dumps(metrics, indent=2))
    for name, text in build_report_texts(metrics, inventory).items():
        write_text(OUTPUT / name, text)

    print(OUTPUT)
    headline = metrics["headline"]
    print(f"portfolio utilization: {headline['portfolio_utilization']:.2%}" if headline["portfolio_utilization"] is not None else OUTPUT)


if __name__ == "__main__":
    main()
