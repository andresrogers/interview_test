import pandas as pd

from src.metrics import add_effective_savings_columns, coverage_rate, effective_savings_metrics, utilization_rate


def test_effective_savings_metrics_uses_on_demand_denominator() -> None:
    frame = pd.DataFrame(
        {
            "on_demand_cost": [100.0, 50.0],
            "amortized_cost": [80.0, 60.0],
        }
    )

    metrics = effective_savings_metrics(frame)

    assert metrics["savings_dollars"] == 10.0
    assert metrics["effective_savings_rate"] == 10.0 / 150.0


def test_effective_savings_allows_negative_result() -> None:
    frame = pd.DataFrame(
        {
            "on_demand_cost": [40.0],
            "amortized_cost": [55.0],
        }
    )

    metrics = effective_savings_metrics(frame)

    assert metrics["savings_dollars"] == -15.0
    assert metrics["effective_savings_rate"] == -15.0 / 40.0


def test_monthly_grouping_preserves_totals() -> None:
    frame = pd.DataFrame(
        {
            "billing_period": ["2025-07", "2025-07", "2025-08"],
            "on_demand_cost": [100.0, 50.0, 25.0],
            "amortized_cost": [70.0, 40.0, 30.0],
        }
    )

    grouped = frame.groupby("billing_period", as_index=False)[["on_demand_cost", "amortized_cost"]].sum()
    monthly = add_effective_savings_columns(pd.DataFrame(grouped))
    total = effective_savings_metrics(frame)

    assert monthly["savings_dollars"].sum() == total["savings_dollars"]
    assert monthly["on_demand_cost"].sum() == total["on_demand_cost"]


def test_coverage_and_utilization_use_different_denominators() -> None:
    assert coverage_rate(60.0, 100.0) == 0.6
    assert utilization_rate(60.0, 80.0) == 0.75
