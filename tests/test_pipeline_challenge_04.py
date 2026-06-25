import json
from pathlib import Path

import pandas as pd

import pipeline.challenge_04_baseline_realized_savings as challenge_04


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
    for ts in pd.date_range("2025-07-01 00:00:00", "2026-05-31 23:00:00", freq="h"):
        month = ts.strftime("%Y-%m")
        usage_amount = 1.0 if ts < pd.Timestamp("2026-01-01 00:00:00") else 2.0
        rows.append(
            {
                "timestamp": ts,
                "billing_period": month,
                "product_code": "AmazonEC2",
                "usage_type": "BoxUsage:m5.large",
                "instance_type": "m5.large",
                "usage_amount": usage_amount,
                "on_demand_cost": 10.0 * usage_amount,
                "amortized_cost": 10.0 * usage_amount,
                "price_list_key": "k1",
                "commitment_key": "AWS#Compute",
                "account_id": "a1",
                "commitment": None,
                "cost_type": "On Demand Usage",
                "baseline_covered": None,
                "baseline_max": 0.1,
            }
        )
    rows.append(
        {
            "timestamp": pd.Timestamp("2026-06-01 00:00:00"),
            "billing_period": "2026-06",
            "product_code": "AmazonEC2",
            "usage_type": "BoxUsage:m5.large",
            "instance_type": "m5.large",
            "usage_amount": 2.0,
            "on_demand_cost": 20.0,
            "amortized_cost": 20.0,
            "price_list_key": "k1",
            "commitment_key": "AWS#Compute",
            "account_id": "a1",
            "commitment": None,
            "cost_type": "On Demand Usage",
            "baseline_covered": None,
            "baseline_max": None,
        }
    )
    return pd.DataFrame(rows)


def test_challenge_04_pipeline_writes_expected_outputs(tmp_path: Path, monkeypatch) -> None:
    usage_path = tmp_path / "usage.parquet"
    pricing_path = tmp_path / "pricing.parquet"
    output = tmp_path / "challenge_04"
    write_parquet(usage_path, usage_frame())
    write_parquet(pricing_path, pricing_frame())
    _patch_pipeline(monkeypatch, challenge_04, usage_path, pricing_path, output)

    challenge_04.main()

    assert (output / "summary.md").exists()
    assert (output / "methodology.md").exists()
    assert (output / "understanding_ledger.md").exists()
    assert (output / "metrics.json").exists()
    assert (output / "tables" / "baseline_backtest_monthly.csv").exists()
    assert (output / "tables" / "baseline_vs_optimal.csv").exists()
    assert (output / "plots" / "baseline_vs_hourly_eligible_spend.png").exists()
    assert (output / "plots" / "baseline_gap_decomposition.png").exists()

    metrics = json.loads((output / "metrics.json").read_text(encoding="utf-8"))
    assert "trust_level" in metrics
    assert "warnings" in metrics
    assert "headline" in metrics
    assert "reconciliation" in metrics
    summary = (output / "summary.md").read_text(encoding="utf-8")
    assert "Fixed compute baseline realized savings rate" in summary
    assert "Anomaly Review Note" in summary
