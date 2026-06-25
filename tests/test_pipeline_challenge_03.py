import json
from pathlib import Path

import pandas as pd

import pipeline.challenge_03_window_sensitivity as challenge_03


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
    for month, cost in zip(range(1, 7), [10.0, 10.0, 10.0, 18.0, 18.0, 18.0], strict=False):
        for ts in pd.date_range(f"2025-{month:02d}-01 00:00:00", f"2025-{month:02d}-28 23:00:00", freq="h"):
            rows.append(
                {
                    "timestamp": ts,
                    "billing_period": ts.strftime("%Y-%m"),
                    "product_code": "AmazonEC2",
                    "usage_type": "BoxUsage:m5.large",
                    "instance_type": "m5.large",
                    "usage_amount": 1.0,
                    "on_demand_cost": cost,
                    "amortized_cost": cost,
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
            "timestamp": pd.Timestamp("2025-07-01 00:00:00"),
            "billing_period": "2025-07",
            "product_code": "AmazonEC2",
            "usage_type": "BoxUsage:m5.large",
            "instance_type": "m5.large",
            "usage_amount": 1.0,
            "on_demand_cost": 18.0,
            "amortized_cost": 18.0,
            "price_list_key": "k1",
            "commitment_key": "AWS#Compute#EC2",
            "account_id": "a1",
            "commitment": None,
            "cost_type": "On Demand Usage",
            "baseline_covered": None,
            "baseline_max": None,
        }
    )
    return pd.DataFrame(rows)


def test_challenge_03_pipeline_writes_expected_outputs(tmp_path: Path, monkeypatch) -> None:
    usage_path = tmp_path / "usage.parquet"
    pricing_path = tmp_path / "pricing.parquet"
    output = tmp_path / "challenge_03"
    write_parquet(usage_path, usage_frame())
    write_parquet(pricing_path, pricing_frame())
    _patch_pipeline(monkeypatch, challenge_03, usage_path, pricing_path, output)

    challenge_03.main()

    assert (output / "summary.md").exists()
    assert (output / "methodology.md").exists()
    assert (output / "understanding_ledger.md").exists()
    assert (output / "metrics.json").exists()
    assert (output / "tables" / "window_sensitivity.csv").exists()
    assert (output / "plots" / "optimal_level_by_window.png").exists()
    assert (output / "plots" / "savings_by_window.png").exists()
    assert (output / "plots" / "eligible_spend_regime_change.png").exists()

    metrics = json.loads((output / "metrics.json").read_text(encoding="utf-8"))
    assert "trust_level" in metrics
    assert "warnings" in metrics
    assert "headline" in metrics
    summary = (output / "summary.md").read_text(encoding="utf-8")
    assert "Recommended sizing rule" in summary
    assert "Anchored 3-month windows" in summary
