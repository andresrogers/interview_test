"""Purpose:
Build reusable frontier outputs for Challenge 6.

Owns:
- Current compute posture rollup from Challenge 5 inventory.
- Frontier recommendation logic.
- Challenge 6 markdown report text.

Does Not Own:
- Hourly commitment allocation mechanics.
- Plot rendering.

Main Entry Points:
- current_commitment_posture_from_inventory
- build_metrics
- build_report_texts

Key Invariants:
- Coverage uses eligible on-demand cost as the denominator.
- Utilization uses paid commitment as the denominator.
- Current posture comes from the exported Challenge 5 inventory, not a parallel estimate.

Update This Header When:
- Public entry points change.
- Current posture definition changes.
"""

from __future__ import annotations

from typing import Any, cast

import pandas as pd


def _series_sum(frame: pd.DataFrame, column: str) -> float:
    return float(cast(float, frame[column].sum()))


def current_commitment_posture_from_inventory(
    inventory: pd.DataFrame,
    eligible_on_demand_cost: float,
    analysis_hour_count: int,
) -> dict[str, float | None]:
    compute = inventory.loc[inventory["scope_label"] == "compute"].copy()
    covered_on_demand = _series_sum(compute, "covered_on_demand_cost")
    consumed_commitment = _series_sum(compute, "consumed_commitment")
    paid_commitment = _series_sum(compute, "paid_commitment")
    waste = _series_sum(compute, "unused_commitment_waste")
    net_savings = covered_on_demand - paid_commitment
    return {
        "commitment_per_hour": paid_commitment / analysis_hour_count if analysis_hour_count else None,
        "coverage_rate": None if eligible_on_demand_cost <= 0 else covered_on_demand / eligible_on_demand_cost,
        "average_utilization": None if paid_commitment <= 0 else consumed_commitment / paid_commitment,
        "total_savings_dollars": net_savings,
        "total_paid_commitment": paid_commitment,
        "total_consumed_commitment": consumed_commitment,
        "total_unused_commitment_waste": waste,
    }


def _as_float(value: float | None) -> float:
    return 0.0 if value is None else float(value)


def _money(value: float) -> str:
    return f"${value:,.2f}"


def _rate(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.2%}"


def _row_float(row: pd.Series, key: str) -> float:
    return float(cast(Any, row[key]))


def _recommended_point(frontier: pd.DataFrame) -> pd.Series:
    max_savings = float(cast(float, frontier["total_savings_dollars"].max()))
    efficient = frontier.loc[frontier["total_savings_dollars"] >= max_savings * 0.95].copy()
    return efficient.sort_values(["average_utilization", "total_savings_dollars"], ascending=[False, False]).iloc[0]


def build_metrics(
    frontier: pd.DataFrame,
    current_posture: dict[str, float | None],
    warnings: list[str],
    exact_breakpoint_count: int,
    plotted_point_count: int,
) -> dict[str, Any]:
    optimum = frontier.sort_values("total_savings_dollars", ascending=False).iloc[0]
    recommended = _recommended_point(frontier)
    metrics_warnings = list(warnings)
    if current_posture["commitment_per_hour"] is None:
        metrics_warnings.append("Current compute commitment posture could not be derived from Challenge 5 inventory.")
    if plotted_point_count < exact_breakpoint_count:
        metrics_warnings.append(
            f"Frontier output was thinned from {exact_breakpoint_count:,} exact breakpoints to {plotted_point_count:,} plotted points to keep runtime and charts usable."
        )
    return {
        "challenge": "challenge_06_coverage_utilization_frontier",
        "trust_level": "medium" if metrics_warnings else "high",
        "warnings": metrics_warnings,
        "frontier": {
            "exact_breakpoint_count": exact_breakpoint_count,
            "plotted_point_count": plotted_point_count,
            "thinned_for_output": plotted_point_count < exact_breakpoint_count,
        },
        "headline": {
            "optimal_commitment_per_hour": _row_float(optimum, "commitment_per_hour"),
            "optimal_total_savings_dollars": _row_float(optimum, "total_savings_dollars"),
            "recommended_commitment_per_hour": _row_float(recommended, "commitment_per_hour"),
            "recommended_total_savings_dollars": _row_float(recommended, "total_savings_dollars"),
            "recommended_coverage_rate": _row_float(recommended, "coverage_rate"),
            "recommended_average_utilization": _row_float(recommended, "average_utilization"),
        },
        "current_posture": current_posture,
    }


def _anomaly_note(frontier: pd.DataFrame, current_posture: dict[str, float | None]) -> str:
    max_util = float(cast(float, frontier["average_utilization"].max()))
    recommended = _recommended_point(frontier)
    if (
        current_posture["commitment_per_hour"]
        and _as_float(current_posture["average_utilization"]) > _row_float(recommended, "average_utilization")
        and _as_float(current_posture["coverage_rate"]) < _row_float(recommended, "coverage_rate")
    ):
        return (
            "Material anomaly found: today's posture is more utilized than the recommended point but covers less spend. "
            "That is the real FinOps tradeoff the frontier is meant to expose, not a metric bug."
        )
    if max_util == 1.0:
        return "No material anomaly found. The left edge of the frontier is fully utilized because any tiny commitment gets consumed before variability creates waste."
    return "No material anomaly found. Coverage, utilization, and savings move in the expected opposing directions across the frontier."


def build_report_texts(metrics: dict[str, Any], frontier: pd.DataFrame) -> dict[str, str]:
    headline = metrics["headline"]
    current = metrics["current_posture"]
    frontier_info = metrics["frontier"]
    return {
        "summary.md": f"""
# Challenge 6 Summary

Recommended operating point: {_money(float(headline['recommended_commitment_per_hour']))}/hour discounted spend

## Frontier Answer

- Max-savings point: {_money(float(headline['optimal_commitment_per_hour']))}/hour with {_money(float(headline['optimal_total_savings_dollars']))} net savings
- Recommended operating point: {_money(float(headline['recommended_commitment_per_hour']))}/hour with {_money(float(headline['recommended_total_savings_dollars']))} net savings
- Recommended coverage: {_rate(headline['recommended_coverage_rate'])}
- Recommended utilization: {_rate(headline['recommended_average_utilization'])}
- Frontier points exported: {frontier_info['plotted_point_count']:,}
- Exact breakpoint count behind the curve: {frontier_info['exact_breakpoint_count']:,}

## Where The Account Sits Today

- Current compute commitment from Challenge 5 inventory: {_money(_as_float(current['commitment_per_hour']))}/hour
- Current coverage: {_rate(current['coverage_rate'])}
- Current utilization: {_rate(current['average_utilization'])}
- Current net savings on compute commitments: {_money(_as_float(current['total_savings_dollars']))}

## Recommended Operating Point

The max-savings point and the max-utilization point are not the same. I recommend the highest-utilization point that still keeps at least 95% of the frontier's best savings. That preserves most of the upside while reducing the downside from idle commitment in quiet hours.

## Anomaly Review Note

{_anomaly_note(frontier, current)}

## Assumptions And Risks

- The frontier uses the same 3 complete billing-period window and pricing view as Challenge 2.
- The current posture is read from `output/challenge_05/tables/commitment_inventory.csv` and filtered to compute-scope commitments.
- The exported frontier can be sampled below the exact breakpoint count when the exact curve is too large to plot cleanly.
- A business with higher downside tolerance may choose the absolute savings peak instead of the recommended operating point.
""",
        "methodology.md": f"""
# Challenge 6 Methodology

## Steps

1. Reuse the Challenge 2 compute optimizer input for the most recent 3 complete billing periods.
2. Take the exact breakpoint commitments from the savings curve.
3. Thin the exported frontier only when the exact breakpoint count is too large for practical plotting.
4. Evaluate coverage, utilization, waste, and net savings at each exported commitment level.
5. Read today's posture from the exported Challenge 5 commitment inventory and keep only compute-scope commitments.
6. Recommend the highest-utilization point that retains at least 95% of peak savings.

## Validation Notes

- Warnings: {', '.join(metrics['warnings']) if metrics['warnings'] else 'none'}.
- Coverage denominator = eligible compute on-demand cost.
- Utilization denominator = paid commitment dollars.
""",
        "understanding_ledger.md": """
# Understanding Ledger

## What I Verified Myself

- Verified frontier points reuse the same hourly allocation rules as Challenge 2.
- Verified coverage and utilization use different denominators.
- Verified the recommended point is not just the raw savings maximum.
- Verified current posture now comes from Challenge 5 inventory instead of a duplicate estimate.

## What I Delegated And Trusted

- Trusted repeated frontier evaluation after metric definitions were tested directly.
- Trusted plot rendering once the highlighted operating points matched the `frontier.csv` table.

## What I'm Unsure Of

- Whether Challenge 5's compute-only inventory slice is the exact scope the business wants to compare against the Compute Savings Plan frontier.
- Whether the business would prefer 95% of max savings or a stricter utilization floor.
""",
    }
