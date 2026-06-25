import pandas as pd

from src.commitments import build_hourly_inputs, evaluate_commitment, optimize_commitment


def _hours(count: int = 1) -> pd.DatetimeIndex:
    return pd.date_range("2025-07-01 00:00:00", periods=count, freq="h")


def test_commitment_covers_highest_discount_first() -> None:
    frame = pd.DataFrame(
        {
            "analysis_timestamp": [pd.Timestamp("2025-07-01 00:00:00")] * 2,
            "discount_pct": [0.2, 0.5],
            "discounted_cost": [8.0, 5.0],
            "gross_savings_if_fully_covered": [2.0, 5.0],
            "on_demand_cost": [10.0, 10.0],
        }
    )

    hourly_inputs = build_hourly_inputs(frame, _hours())
    result = evaluate_commitment(5.0, hourly_inputs)

    assert result["total_savings_dollars"] == 5.0
    assert result["total_covered_on_demand_cost"] == 10.0


def test_commitment_is_sized_in_discounted_dollars_per_hour() -> None:
    frame = pd.DataFrame(
        {
            "analysis_timestamp": [pd.Timestamp("2025-07-01 00:00:00")],
            "discount_pct": [0.5],
            "discounted_cost": [5.0],
            "gross_savings_if_fully_covered": [5.0],
            "on_demand_cost": [10.0],
        }
    )

    hourly_inputs = build_hourly_inputs(frame, _hours())
    result = evaluate_commitment(5.0, hourly_inputs)

    assert result["total_consumed_commitment"] == 5.0
    assert result["total_covered_on_demand_cost"] == 10.0
    assert result["coverage_rate"] == 1.0


def test_unused_commitment_is_paid_waste() -> None:
    frame = pd.DataFrame(
        {
            "analysis_timestamp": [pd.Timestamp("2025-07-01 00:00:00")],
            "discount_pct": [0.5],
            "discounted_cost": [5.0],
            "gross_savings_if_fully_covered": [5.0],
            "on_demand_cost": [10.0],
        }
    )

    hourly_inputs = build_hourly_inputs(frame, _hours())
    result = evaluate_commitment(8.0, hourly_inputs)

    assert result["total_unused_commitment_waste"] == 3.0
    assert result["total_savings_dollars"] == 2.0


def test_hours_with_no_compute_usage_are_full_waste() -> None:
    frame = pd.DataFrame(
        {
            "analysis_timestamp": [pd.Timestamp("2025-07-01 00:00:00")],
            "discount_pct": [0.5],
            "discounted_cost": [5.0],
            "gross_savings_if_fully_covered": [5.0],
            "on_demand_cost": [10.0],
        }
    )

    hourly_inputs = build_hourly_inputs(frame, _hours(2))
    result = evaluate_commitment(5.0, hourly_inputs)

    assert result["total_paid_commitment"] == 10.0
    assert result["total_unused_commitment_waste"] == 5.0
    assert result["total_savings_dollars"] == 0.0


def test_optimizer_returns_zero_when_waste_outweighs_discounts() -> None:
    frame = pd.DataFrame(
        {
            "analysis_timestamp": [pd.Timestamp("2025-07-01 00:00:00")],
            "discount_pct": [0.1],
            "discounted_cost": [9.0],
            "gross_savings_if_fully_covered": [1.0],
            "on_demand_cost": [10.0],
        }
    )

    hourly_inputs = build_hourly_inputs(frame, _hours(2))
    curve, optimum = optimize_commitment(hourly_inputs)

    assert curve.iloc[0]["commitment_per_hour"] == 0.0
    assert optimum["commitment_per_hour"] == 0.0
    assert optimum["total_savings_dollars"] == 0.0
