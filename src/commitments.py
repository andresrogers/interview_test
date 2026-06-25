"""Purpose:
Build and evaluate minimal hourly commitment-allocation models.

Owns:
- Hourly Compute Savings Plan allocation inputs.
- Commitment breakpoint sweep and point evaluation.
- Coverage and utilization metrics for a fixed hourly commitment.

Does Not Own:
- DuckDB pricing joins.
- Challenge-specific report text or plotting.

Main Entry Points:
- build_hourly_inputs
- evaluate_commitment
- optimize_commitment
- hourly_summary

Key Invariants:
- Commitment is sized in discounted dollars per hour.
- Coverage is allocated highest discount first within each hour.
- Unused commitment is paid waste.

Update This Header When:
- Public entry points change.
- Allocation semantics change.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from src.metrics import safe_ratio


def build_hourly_inputs(eligible_usage: pd.DataFrame, analysis_hours: pd.DatetimeIndex) -> list[dict[str, Any]]:
    hourly_inputs = []
    grouped = {
        hour: frame.sort_values(["discount_pct", "discounted_cost"], ascending=[False, False]).reset_index(drop=True)
        for hour, frame in eligible_usage.groupby("analysis_timestamp", sort=False)
    }
    for hour in analysis_hours:
        rows = grouped.get(hour)
        if rows is None or rows.empty:
            hourly_inputs.append(
                {
                    "analysis_timestamp": hour,
                    "discounted_costs": np.array([], dtype=float),
                    "gross_savings": np.array([], dtype=float),
                    "on_demand_costs": np.array([], dtype=float),
                    "cumulative_discounted_costs": np.array([], dtype=float),
                    "cumulative_gross_savings": np.array([], dtype=float),
                    "cumulative_on_demand_costs": np.array([], dtype=float),
                    "segment_slopes": np.array([], dtype=float),
                    "total_discounted_cost": 0.0,
                    "total_on_demand_cost": 0.0,
                }
            )
            continue
        discounted_costs = rows["discounted_cost"].to_numpy(dtype=float)
        gross_savings = rows["gross_savings_if_fully_covered"].to_numpy(dtype=float)
        on_demand_costs = rows["on_demand_cost"].to_numpy(dtype=float)
        hourly_inputs.append(
            {
                "analysis_timestamp": hour,
                "discounted_costs": discounted_costs,
                "gross_savings": gross_savings,
                "on_demand_costs": on_demand_costs,
                "cumulative_discounted_costs": discounted_costs.cumsum(),
                "cumulative_gross_savings": gross_savings.cumsum(),
                "cumulative_on_demand_costs": on_demand_costs.cumsum(),
                "segment_slopes": np.divide(
                    gross_savings,
                    discounted_costs,
                    out=np.zeros_like(gross_savings),
                    where=discounted_costs > 0,
                ),
                "total_discounted_cost": float(discounted_costs.sum()),
                "total_on_demand_cost": float(on_demand_costs.sum()),
            }
        )
    return hourly_inputs


def _covered_components(hour: dict[str, Any], commitment_per_hour: float) -> tuple[float, float, float]:
    covered_discounted_cost = min(commitment_per_hour, hour["total_discounted_cost"])
    if covered_discounted_cost <= 0 or hour["discounted_costs"].size == 0:
        return 0.0, 0.0, 0.0
    cumulative = hour["cumulative_discounted_costs"]
    full_rows = int(np.searchsorted(cumulative, covered_discounted_cost, side="right"))
    covered_gross_savings = 0.0
    covered_on_demand_cost = 0.0
    if full_rows:
        covered_gross_savings = float(hour["cumulative_gross_savings"][full_rows - 1])
        covered_on_demand_cost = float(hour["cumulative_on_demand_costs"][full_rows - 1])
    if full_rows < hour["discounted_costs"].size:
        already_covered = 0.0 if full_rows == 0 else float(cumulative[full_rows - 1])
        remainder = covered_discounted_cost - already_covered
        if remainder > 0:
            fraction = remainder / float(hour["discounted_costs"][full_rows])
            covered_gross_savings += fraction * float(hour["gross_savings"][full_rows])
            covered_on_demand_cost += fraction * float(hour["on_demand_costs"][full_rows])
    return covered_discounted_cost, covered_gross_savings, covered_on_demand_cost


def evaluate_commitment(commitment_per_hour: float, hourly_inputs: list[dict[str, Any]]) -> dict[str, float | None]:
    paid_commitment = commitment_per_hour * len(hourly_inputs)
    total_eligible_on_demand_cost = 0.0
    total_consumed_commitment = 0.0
    total_waste = 0.0
    total_gross_savings = 0.0
    total_covered_on_demand_cost = 0.0
    for hour in hourly_inputs:
        total_eligible_on_demand_cost += hour["total_on_demand_cost"]
        covered_discounted_cost, covered_gross_savings, covered_on_demand_cost = _covered_components(
            hour, commitment_per_hour
        )
        total_consumed_commitment += covered_discounted_cost
        total_gross_savings += covered_gross_savings
        total_covered_on_demand_cost += covered_on_demand_cost
        total_waste += commitment_per_hour - covered_discounted_cost
    total_savings = total_gross_savings - total_waste
    return {
        "commitment_per_hour": commitment_per_hour,
        "total_savings_dollars": total_savings,
        "total_unused_commitment_waste": total_waste,
        "total_consumed_commitment": total_consumed_commitment,
        "total_paid_commitment": paid_commitment,
        "total_eligible_on_demand_cost": total_eligible_on_demand_cost,
        "total_covered_on_demand_cost": total_covered_on_demand_cost,
        "effective_savings_rate": safe_ratio(total_savings, total_eligible_on_demand_cost),
        "coverage_rate": safe_ratio(total_covered_on_demand_cost, total_eligible_on_demand_cost),
        "average_utilization": safe_ratio(total_consumed_commitment, paid_commitment),
    }


def optimize_commitment(hourly_inputs: list[dict[str, Any]]) -> tuple[pd.DataFrame, dict[str, float | None]]:
    events: dict[float, float] = {}
    current_slope = 0.0
    for hour in hourly_inputs:
        if hour["segment_slopes"].size == 0:
            current_slope -= 1.0
            continue
        slopes = np.append(hour["segment_slopes"], -1.0)
        current_slope += float(slopes[0])
        for breakpoint, old_slope, new_slope in zip(hour["cumulative_discounted_costs"], slopes[:-1], slopes[1:]):
            key = float(breakpoint)
            events[key] = events.get(key, 0.0) + float(new_slope - old_slope)
    curve_rows = [{"commitment_per_hour": 0.0, "total_savings_dollars": 0.0}]
    best_commitment = 0.0
    best_savings = 0.0
    prior_commitment = 0.0
    total_savings = 0.0
    for commitment in sorted(events):
        total_savings += current_slope * (commitment - prior_commitment)
        curve_rows.append({"commitment_per_hour": commitment, "total_savings_dollars": total_savings})
        if total_savings > best_savings + 1e-9:
            best_commitment = commitment
            best_savings = total_savings
        current_slope += events[commitment]
        prior_commitment = commitment
    curve = pd.DataFrame(curve_rows)
    optimum = evaluate_commitment(best_commitment, hourly_inputs)
    return curve, optimum


def hourly_summary(commitment_per_hour: float, hourly_inputs: list[dict[str, Any]]) -> pd.DataFrame:
    rows = []
    for hour in hourly_inputs:
        covered_discounted_cost, covered_gross_savings, covered_on_demand_cost = _covered_components(
            hour, commitment_per_hour
        )
        waste = commitment_per_hour - covered_discounted_cost
        rows.append(
            {
                "analysis_timestamp": hour["analysis_timestamp"],
                "eligible_on_demand_cost": hour["total_on_demand_cost"],
                "eligible_discounted_cost": hour["total_discounted_cost"],
                "covered_on_demand_cost": covered_on_demand_cost,
                "consumed_commitment": covered_discounted_cost,
                "unused_commitment_waste": waste,
                "gross_savings": covered_gross_savings,
                "net_savings": covered_gross_savings - waste,
                "utilization": safe_ratio(covered_discounted_cost, commitment_per_hour),
                "coverage_rate": safe_ratio(covered_on_demand_cost, hour["total_on_demand_cost"]),
            }
        )
    return pd.DataFrame(rows)
