import json
from pathlib import Path

import pandas as pd

import pipeline.challenge_06_coverage_utilization_frontier as challenge_06


def test_frontier_candidates_thin_to_251_points() -> None:
    curve = pd.DataFrame(
        {"commitment_per_hour": [float(value) for value in range(300)]}
    )

    candidates = challenge_06.frontier_candidates(curve)

    assert len(candidates) == 251
    assert candidates[0] == 0.0
    assert candidates[-1] == 299.0


def write_parquet(path: Path, frame: pd.DataFrame) -> None:
    frame.to_parquet(path, index=False)


def pricing_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "price_list_key": ["k1"],
            "instrument_type": ["compute_savings_plan"],
            "term_months": [36],
            "payment_option": ["no_upfront"],
            "rate": [0.1],
            "unit": ["Hrs"],
            "currency": ["USD"],
            "offering_class": ["savings_plan"],
        }
    )


def _patch_pipeline(
    monkeypatch, module, usage_path: Path, pricing_path: Path, output: Path
) -> None:
    monkeypatch.setattr(module, "OUTPUT", output)
    monkeypatch.setattr(module, "TABLES", output / "tables")
    monkeypatch.setattr(module, "PLOTS", output / "plots")

    def load_usage(con, path=usage_path, view_name="usage"):
        escaped = str(path).replace("'", "''")
        con.execute(
            f"create or replace view {view_name} as select * from read_parquet('{escaped}')"
        )
        return view_name

    def load_pricing(con, path=pricing_path, view_name="pricing"):
        escaped = str(path).replace("'", "''")
        con.execute(
            f"create or replace view {view_name} as select * from read_parquet('{escaped}')"
        )
        return view_name

    monkeypatch.setattr(module, "load_usage", load_usage)
    monkeypatch.setattr(module, "load_pricing", load_pricing)


def usage_frame() -> pd.DataFrame:
    timestamps = list(
        pd.date_range("2025-01-01 00:00:00", "2025-03-31 23:00:00", freq="h")
    )
    rows = []
    for ts in timestamps:
        billing_period = ts.strftime("%Y-%m")
        rows.append(
            {
                "timestamp": ts,
                "billing_period": billing_period,
                "product_code": "AmazonEC2",
                "usage_type": "BoxUsage:m5.large",
                "instance_type": "m5.large",
                "usage_amount": 1.0,
                "on_demand_cost": 10.0,
                "amortized_cost": 10.0,
                "price_list_key": "k1",
                "commitment_key": "AWS#Compute#EC2",
                "account_id": "a1",
                "commitment": None,
                "cost_type": "On Demand Usage",
                "baseline_covered": None,
                "baseline_max": None,
            }
        )
    rows.append(
        {
            "timestamp": pd.Timestamp("2025-02-01 00:00:00"),
            "billing_period": "2025-02",
            "product_code": "AmazonEC2",
            "usage_type": "SpotUsage:m5.large",
            "instance_type": "m5.large",
            "usage_amount": 1.0,
            "on_demand_cost": 4.0,
            "amortized_cost": 4.0,
            "price_list_key": "k1",
            "commitment_key": "AWS#Compute#EC2",
            "account_id": "a1",
            "commitment": None,
            "cost_type": "Spot Usage",
            "baseline_covered": None,
            "baseline_max": None,
        }
    )
    rows.append(
        {
            "timestamp": pd.Timestamp("2025-03-10 12:00:00"),
            "billing_period": "2025-03",
            "product_code": "AmazonEC2",
            "usage_type": "BoxUsage:m5.large",
            "instance_type": "m5.large",
            "usage_amount": 0.0,
            "on_demand_cost": 0.0,
            "amortized_cost": 1.0,
            "price_list_key": "k1",
            "commitment_key": "AWS#Compute#EC2",
            "account_id": "a1",
            "commitment": "c1",
            "cost_type": "Unused Commitment",
            "baseline_covered": None,
            "baseline_max": None,
        }
    )
    return pd.DataFrame(rows)


def inventory_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "commitment": ["c1", "c2"],
            "scope_label": ["compute", "rds"],
            "covered_on_demand_cost": [10.0, 5.0],
            "consumed_commitment": [8.0, 5.0],
            "unused_commitment_waste": [2.0, 0.0],
            "paid_commitment": [10.0, 5.0],
        }
    )


def test_challenge_06_pipeline_writes_expected_outputs(
    tmp_path: Path, monkeypatch
) -> None:
    usage_path = tmp_path / "usage.parquet"
    pricing_path = tmp_path / "pricing.parquet"
    output = tmp_path / "challenge_06"
    inventory_path = tmp_path / "commitment_inventory.csv"
    write_parquet(usage_path, usage_frame())
    write_parquet(pricing_path, pricing_frame())
    inventory_frame().to_csv(inventory_path, index=False)
    _patch_pipeline(monkeypatch, challenge_06, usage_path, pricing_path, output)
    monkeypatch.setattr(challenge_06, "CHALLENGE_05_INVENTORY", inventory_path)

    challenge_06.main()

    assert (output / "summary.md").exists()
    assert (output / "methodology.md").exists()
    assert (output / "understanding_ledger.md").exists()
    assert (output / "metrics.json").exists()
    assert (output / "tables" / "frontier.csv").exists()
    assert (output / "plots" / "coverage_utilization_frontier.png").exists()
    assert (output / "plots" / "savings_coverage_utilization_bubble.png").exists()

    metrics = json.loads((output / "metrics.json").read_text(encoding="utf-8"))
    assert "trust_level" in metrics
    assert "warnings" in metrics
    assert "headline" in metrics
    assert "frontier" in metrics
    assert metrics["headline"]["recommended_commitment_per_hour"] >= 0
    summary = (output / "summary.md").read_text(encoding="utf-8")
    assert "Frontier Answer" in summary
    assert "Where The Account Sits Today" in summary
    assert "Recommended Operating Point" in summary
