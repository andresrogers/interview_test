from pathlib import Path

import duckdb
import pandas as pd
import pytest

from src.cost_data import load_pricing, load_usage
from src.challenge_02 import choose_analysis_window, validate_optimizer_inputs
from src.data_quality import (
    billing_period_completeness,
    data_quality_issues,
    ensure_ready_usage_view,
    issue_messages,
)


def write_parquet(path: Path, frame: pd.DataFrame) -> None:
    frame.to_parquet(path, index=False)


def usage_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "timestamp": pd.to_datetime(["2025-07-01 00:00:00", "2025-07-01 01:00:00"]),
            "billing_period": ["2025-07", "2025-07"],
            "product_code": ["AmazonEC2", "AmazonEC2"],
            "usage_amount": [1.0, 2.0],
            "on_demand_cost": [10.0, 20.0],
            "amortized_cost": [8.0, 18.0],
            "price_list_key": ["k1", "k1"],
            "commitment": [None, None],
            "commitment_key": ["AWS#Compute", "AWS#Compute"],
            "cost_type": ["On Demand Usage", "On Demand Usage"],
        }
    )


def pricing_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "price_list_key": ["k1"],
            "instrument_type": ["compute_savings_plan"],
            "term_months": [36],
            "payment_option": ["No Upfront"],
            "rate": [0.1],
            "offering_class": ["standard"],
        }
    )


def load_frames(tmp_path: Path, usage: pd.DataFrame, pricing: pd.DataFrame) -> duckdb.DuckDBPyConnection:
    usage_path = tmp_path / "usage.parquet"
    pricing_path = tmp_path / "pricing.parquet"
    write_parquet(usage_path, usage)
    write_parquet(pricing_path, pricing)
    con = duckdb.connect()
    load_usage(con, usage_path)
    load_pricing(con, pricing_path)
    return con


def test_data_quality_issues_accept_hourly_non_negative_data(tmp_path: Path) -> None:
    con = load_frames(tmp_path, usage_frame(), pricing_frame())

    issues = data_quality_issues(con)

    assert issues.empty


def test_data_quality_warns_for_off_hour_unused_commitment(tmp_path: Path) -> None:
    frame = usage_frame()
    frame.loc[1, "timestamp"] = pd.Timestamp("2025-07-01 01:30:00")
    frame.loc[1, "cost_type"] = "Unused Commitment"
    con = load_frames(tmp_path, frame, pricing_frame())

    issues = data_quality_issues(con)

    assert issue_messages(issues, "warning") == [
        "Found 1 off-hour `Unused Commitment` rows; analysis uses normalized hourly buckets while preserving raw timestamps."
    ]


def test_data_quality_rejects_non_hourly_non_unused_row(tmp_path: Path) -> None:
    frame = usage_frame()
    frame.loc[1, "timestamp"] = pd.Timestamp("2025-07-01 01:30:00")
    con = load_frames(tmp_path, frame, pricing_frame())

    issues = data_quality_issues(con)

    assert "Usage timestamps are not aligned to full hours" in issue_messages(issues, "fatal")[0]


def test_data_quality_rejects_missing_pricing_columns(tmp_path: Path) -> None:
    con = load_frames(tmp_path, usage_frame(), pricing_frame().drop(columns=["offering_class"]))

    issues = data_quality_issues(con)

    assert issue_messages(issues, "fatal") == ["Missing required columns: offering_class"]


def test_ready_usage_view_adds_normalized_columns(tmp_path: Path) -> None:
    frame = usage_frame()
    frame.loc[1, "timestamp"] = pd.Timestamp("2025-07-01 01:30:00")
    frame.loc[1, "cost_type"] = "Unused Commitment"
    con = load_frames(tmp_path, frame, pricing_frame())

    ensure_ready_usage_view(con)
    normalized = con.execute(
        "select analysis_timestamp, timestamp_was_normalized from usage_ready order by analysis_timestamp desc limit 1"
    ).fetchone()

    assert normalized is not None
    assert normalized[0] == pd.Timestamp("2025-07-01 01:00:00")
    assert normalized[1] is True


def test_billing_period_completeness_uses_normalized_hourly_buckets(tmp_path: Path) -> None:
    frame = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(["2025-07-01 00:00:00", "2025-07-01 01:30:00", "2025-08-01 00:00:00"]),
            "billing_period": ["2025-07", "2025-07", "2025-08"],
            "product_code": ["AmazonEC2"] * 3,
            "usage_amount": [1.0, 2.0, 3.0],
            "on_demand_cost": [10.0, 20.0, 30.0],
            "amortized_cost": [8.0, 18.0, 28.0],
            "price_list_key": ["k1"] * 3,
            "commitment": [None] * 3,
            "commitment_key": ["AWS#Compute"] * 3,
            "cost_type": ["On Demand Usage", "Unused Commitment", "On Demand Usage"],
        }
    )
    con = load_frames(tmp_path, frame, pricing_frame())

    ensure_ready_usage_view(con)
    periods = billing_period_completeness(con)

    assert not periods.loc[periods["billing_period"] == "2025-07", "is_complete"].item()
    assert not periods.loc[periods["billing_period"] == "2025-08", "is_complete"].item()


def test_challenge_02_window_uses_most_recent_three_complete_months() -> None:
    periods = pd.DataFrame(
        {
            "billing_period": ["2025-01", "2025-02", "2025-03", "2025-04", "2025-05"],
            "is_complete": [True, True, True, False, True],
        }
    )

    included, partial, excluded = choose_analysis_window(periods)

    assert included == ["2025-02", "2025-03", "2025-05"]
    assert partial == ["2025-04"]
    assert excluded == ["2025-01"]


def test_challenge_02_validation_reports_invalid_optimizer_rows() -> None:
    joined = pd.DataFrame(
        {
            "usage_amount": [1.0, 0.0],
            "discounted_rate": [0.5, None],
            "on_demand_rate": [1.0, None],
            "discounted_cost": [0.5, None],
            "gross_savings_if_fully_covered": [0.5, None],
            "cost_type": ["On Demand Usage", "Unused Commitment"],
        }
    )

    warnings, quarantined = validate_optimizer_inputs(joined, joined.iloc[[0]].copy(), duplicate_price_keys=2)

    assert len(quarantined) == 1
    assert "duplicate price_list_key" in warnings[0]
    assert "Quarantined 1 compute rows" in warnings[1]
