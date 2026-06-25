"""Purpose:
Small reusable savings, coverage, and utilization calculations.

Owns:
- Headline effective savings formula.
- Savings columns added to aggregated DataFrames.
- Shared coverage and utilization ratios.

Does Not Own:
- Challenge-specific grouping choices.
- Plotting or markdown output.

Main Entry Points:
- effective_savings_metrics
- add_effective_savings_columns
- coverage_rate
- utilization_rate

Key Invariants:
- Savings dollars are `on_demand_cost - amortized_cost`.
- Effective savings rate uses total on-demand cost as the denominator.
- Zero denominators yield `None` instead of a fabricated rate.

Update This Header When:
- Public entry points change.
- Metric definitions change.
"""

from __future__ import annotations

from typing import Any

import pandas as pd


def safe_ratio(numerator: float, denominator: float) -> float | None:
    if denominator <= 0:
        return None
    return numerator / denominator


def coverage_rate(covered_on_demand_cost: float, eligible_on_demand_cost: float) -> float | None:
    return safe_ratio(covered_on_demand_cost, eligible_on_demand_cost)


def utilization_rate(consumed_commitment: float, paid_commitment: float) -> float | None:
    return safe_ratio(consumed_commitment, paid_commitment)


def effective_savings_metrics(frame: pd.DataFrame) -> dict[str, Any]:
    on_demand_cost = sum(float(value) for value in frame["on_demand_cost"].tolist())
    amortized_cost = sum(float(value) for value in frame["amortized_cost"].tolist())
    savings_dollars = on_demand_cost - amortized_cost
    return {
        "on_demand_cost": on_demand_cost,
        "amortized_cost": amortized_cost,
        "savings_dollars": savings_dollars,
        "effective_savings_rate": safe_ratio(savings_dollars, on_demand_cost),
    }


def add_effective_savings_columns(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    result["savings_dollars"] = result["on_demand_cost"] - result["amortized_cost"]
    result["effective_savings_rate"] = [
        safe_ratio(float(savings), float(on_demand))
        for savings, on_demand in zip(result["savings_dollars"].tolist(), result["on_demand_cost"].tolist())
    ]
    return result
