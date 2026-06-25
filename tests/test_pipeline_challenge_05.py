import json
from pathlib import Path

import pandas as pd

import pipeline.challenge_05_audit_commitments as challenge_05


def write_parquet(path: Path, frame: pd.DataFrame) -> None:
    frame.to_parquet(path, index=False)


def pricing_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "price_list_key": ["k1", "k2"],
            "instrument_type": ["compute_savings_plan", "compute_savings_plan"],
            "term_months": [36, 36],
            "payment_option": ["no_upfront", "no_upfront"],
            "rate": [0.1, 0.1],
            "unit": ["Hrs", "Hrs"],
            "currency": ["USD", "USD"],
            "offering_class": ["savings_plan", "savings_plan"],
        }
    )


def _patch_pipeline(monkeypatch, module, usage_path: Path, pricing_path: Path, output: Path) -> None:
    monkeypatch.setattr(module, "OUTPUT", output)
    monkeypatch.setattr(module, "TABLES", output / "tables")
    monkeypatch.setattr(module, "PLOTS", output / "plots")

    def load_usage(con, path=usage_path, view_name="usage"):
        escaped = str(path).replace("'", "''")
        con.execute(f"create or replace view {view_name} as select * from read_parquet('{escaped}')")
        return view_name

    def load_pricing(con, path=pricing_path, view_name="pricing"):
        escaped = str(path).replace("'", "''")
        con.execute(f"create or replace view {view_name} as select * from read_parquet('{escaped}')")
        return view_name

    monkeypatch.setattr(module, "load_usage", load_usage)
    monkeypatch.setattr(module, "load_pricing", load_pricing)


def usage_frame() -> pd.DataFrame:
    rows = []
    commitments = ["arn:aws:savingsplans::123:savingsplan/a", "arn:aws:rds:eu-central-1:123:ri:ri-a"]
    for ts in pd.date_range("2025-01-01 00:00:00", "2025-03-31 23:00:00", freq="h"):
        base = {
            "timestamp": ts,
            "billing_period": ts.strftime("%Y-%m"),
            "account_id": "a1",
            "baseline_covered": None,
            "baseline_max": None,
        }
        rows.extend(
            [
                {
                    **base,
                    "product_code": "AmazonEC2",
                    "usage_type": "BoxUsage:m5.large",
                    "instance_type": "m5.large",
                    "usage_amount": 1.0,
                    "on_demand_cost": 10.0,
                    "amortized_cost": 6.0,
                    "price_list_key": "k1",
                    "commitment_key": "AWS#Compute",
                    "commitment": commitments[0],
                    "cost_type": "Usage with Discount",
                },
                {
                    **base,
                    "product_code": "AmazonRDS",
                    "usage_type": "RDS:db.r6g.large",
                    "instance_type": "db.r6g.large",
                    "usage_amount": 1.0,
                    "on_demand_cost": 8.0,
                    "amortized_cost": 5.0,
                    "price_list_key": "k2",
                    "commitment_key": "AWS#AmazonRDS-Database Instance#eu-central-1#r6g",
                    "commitment": commitments[1],
                    "cost_type": "Usage with Discount",
                },
                {
                    **base,
                    "product_code": "AmazonEC2",
                    "usage_type": "BoxUsage:m5.large",
                    "instance_type": "m5.large",
                    "usage_amount": 1.0,
                    "on_demand_cost": 3.0,
                    "amortized_cost": 3.0,
                    "price_list_key": "k1",
                    "commitment_key": "AWS#Compute",
                    "commitment": None,
                    "cost_type": "On Demand Usage",
                },
            ]
        )
    for period in ["2025-01", "2025-02", "2025-03"]:
        rows.append(
            {
                "timestamp": pd.Timestamp(f"{period}-01 00:30:00"),
                "billing_period": period,
                "product_code": "ComputeSavingsPlans",
                "usage_type": "Unused",
                "instance_type": None,
                "usage_amount": 0.0,
                "on_demand_cost": 0.0,
                "amortized_cost": 1.0,
                "price_list_key": "k1",
                "commitment_key": None,
                "account_id": "a1",
                "commitment": commitments[0],
                "cost_type": "Unused Commitment",
                "baseline_covered": None,
                "baseline_max": None,
            }
        )
    return pd.DataFrame(rows)


def test_challenge_05_pipeline_writes_expected_outputs(tmp_path: Path, monkeypatch) -> None:
    usage_path = tmp_path / "usage.parquet"
    pricing_path = tmp_path / "pricing.parquet"
    output = tmp_path / "challenge_05"
    write_parquet(usage_path, usage_frame())
    write_parquet(pricing_path, pricing_frame())
    _patch_pipeline(monkeypatch, challenge_05, usage_path, pricing_path, output)

    challenge_05.main()

    assert (output / "summary.md").exists()
    assert (output / "methodology.md").exists()
    assert (output / "understanding_ledger.md").exists()
    assert (output / "metrics.json").exists()
    assert (output / "tables" / "commitment_inventory.csv").exists()
    assert (output / "tables" / "commitment_monthly_utilization.csv").exists()
    assert (output / "plots" / "commitment_utilization_heatmap.png").exists()
    assert (output / "plots" / "waste_by_commitment.png").exists()

    metrics = json.loads((output / "metrics.json").read_text(encoding="utf-8"))
    assert "trust_level" in metrics
    assert "warnings" in metrics
    assert "headline" in metrics
    assert "reconciliation" in metrics
    summary = (output / "summary.md").read_text(encoding="utf-8")
    assert "Inventory Snapshot" in summary
    assert "Anomaly Review Note" in summary
