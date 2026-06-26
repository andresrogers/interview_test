import json
from pathlib import Path

import pandas as pd

import pipeline.challenge_00_data_readiness as challenge_00


def write_parquet(path: Path, frame: pd.DataFrame) -> None:
    frame.to_parquet(path, index=False)


def usage_frame() -> pd.DataFrame:
    full_month = pd.date_range("2025-07-01 00:00:00", periods=24 * 31, freq="h")
    partial_month = [pd.Timestamp("2025-08-01 00:00:00")]
    timestamps = list(full_month[:-1]) + [pd.Timestamp("2025-07-31 23:30:00")] + partial_month
    cost_types = ["Usage with Discount"] * (len(full_month) - 2) + ["Spot Usage", "Unused Commitment", "On Demand Usage"]
    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "billing_period": ["2025-07"] * len(full_month) + ["2025-08"],
            "product_code": ["AmazonEC2"] * (len(full_month) + 1),
            "usage_type": ["BoxUsage:m5.large"] * (len(full_month) + 1),
            "instance_type": ["m5.large"] * (len(full_month) + 1),
            "usage_amount": [1.0] * (len(full_month) + 1),
            "on_demand_cost": [10.0] * len(full_month) + [10.0],
            "amortized_cost": [8.0] * (len(full_month) - 2) + [6.0, 0.0, 12.0],
            "price_list_key": ["k1"] * (len(full_month) + 1),
            "commitment_key": ["AWS#Compute"] * (len(full_month) + 1),
            "account_id": ["a1"] * (len(full_month) + 1),
            "commitment": ["c1"] * len(full_month) + [None],
            "cost_type": cost_types,
            "baseline_covered": [None] * (len(full_month) + 1),
            "baseline_max": [None] * (len(full_month) + 1),
        }
    )


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
        escaped = str(usage_path).replace("'", "''")
        con.execute(f"create or replace view {view_name} as select * from read_parquet('{escaped}')")
        return view_name

    def load_pricing(con, path=pricing_path, view_name="pricing"):
        escaped = str(pricing_path).replace("'", "''")
        con.execute(f"create or replace view {view_name} as select * from read_parquet('{escaped}')")
        return view_name

    monkeypatch.setattr(module, "load_usage", load_usage)
    monkeypatch.setattr(module, "load_pricing", load_pricing)


def test_challenge_00_pipeline_writes_expected_outputs(tmp_path: Path, monkeypatch) -> None:
    usage_path = tmp_path / "usage.parquet"
    pricing_path = tmp_path / "pricing.parquet"
    output = tmp_path / "challenge_00"
    write_parquet(usage_path, usage_frame())
    write_parquet(pricing_path, pricing_frame())
    _patch_pipeline(monkeypatch, challenge_00, usage_path, pricing_path, output)

    captured_plots: dict[str, list[list[str]]] = {}
    current_plot_lines: list[list[str]] = []
    original_plot = challenge_00.plt.plot
    original_savefig = challenge_00.plt.savefig

    def capture_plot(x, *args, **kwargs):
        current_plot_lines.append([str(value) for value in list(x)])
        return original_plot(x, *args, **kwargs)

    def capture_savefig(path, *args, **kwargs):
        captured_plots[Path(path).name] = list(current_plot_lines)
        current_plot_lines.clear()
        return original_savefig(path, *args, **kwargs)

    monkeypatch.setattr(challenge_00.plt, "plot", capture_plot)
    monkeypatch.setattr(challenge_00.plt, "savefig", capture_savefig)

    challenge_00.main()

    assert (output / "summary.md").exists()
    assert (output / "methodology.md").exists()
    assert (output / "understanding_ledger.md").exists()
    assert (output / "metrics.json").exists()
    assert (output / "tables" / "data_quality_issues.csv").exists()
    assert (output / "tables" / "monthly_aws_load_trend.csv").exists()
    assert (output / "tables" / "duplicate_check_summary.csv").exists()
    assert (output / "tables" / "numeric_sanity_check_summary.csv").exists()
    assert (output / "tables" / "pricing_key_coverage_summary.csv").exists()
    assert (output / "plots" / "monthly_row_counts.png").exists()
    assert (output / "plots" / "monthly_aws_load_trend.png").exists()
    assert (output / "plots" / "monthly_aws_load_trend_by_service.png").exists()

    metrics = json.loads((output / "metrics.json").read_text(encoding="utf-8"))
    assert metrics["cleaning_applied"] is True
    assert "trust_level" in metrics
    assert "warnings" in metrics
    assert metrics["trend"]["excluded_last_incomplete_month"] is True

    trend = pd.read_csv(output / "tables" / "monthly_aws_load_trend.csv")
    assert trend.loc[trend["month"] == "2025-08", "is_complete_month"].item() == False
    assert captured_plots["monthly_cost_profile.png"] == [["2025-07"], ["2025-07"]]
    assert captured_plots["monthly_aws_load_trend.png"] == [["2025-07"]]

    summary = (output / "summary.md").read_text(encoding="utf-8")
    assert "Last observed month excluded from trend interpretation" in summary
