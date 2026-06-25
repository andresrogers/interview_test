"""Purpose:
Generate reusable Challenge 1 aggregations, metrics, and report text.

Owns:
- Challenge 1 decomposition tables.
- Challenge 1 metric assembly.
- Challenge 1 markdown report text.

Does Not Own:
- Shared data readiness checks.
- Plot rendering.

Main Entry Points:
- choose_analysis_window
- collect_outputs
- build_metrics
- build_report_texts

Key Invariants:
- Challenge 1 uses complete billing periods for its headline metric.
- Savings dollars are `on_demand_cost - amortized_cost`.
- Spot is included in headline cost but separated from commitment savings in the instrument view.
- `Unused Commitment` remains visible as waste evidence.

Update This Header When:
- Public entry points change.
- Challenge 1 deliverables change.
"""

from __future__ import annotations

from typing import Any

import duckdb
import pandas as pd

from src.metrics import add_effective_savings_columns, effective_savings_metrics


def _money(value: float) -> str:
    return f"${value:,.2f}"


def _rate_text(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.2%}"


def _instrument_family_expr() -> str:
    return """
    case
      when cost_type = 'Spot Usage' then 'Spot (non-commitment cost)'
      when cost_type = 'On Demand Usage' then 'On Demand / No Commitment'
      when commitment_key like 'AWS#Compute%' then 'Compute Savings Plan'
      when commitment_key like 'AWS#Database%' then 'Database Savings Plan'
      when commitment_key like 'AWS#Sagemaker%' then 'SageMaker Savings Plan'
      when commitment is not null then 'Reserved Instance'
      when commitment_key is null then 'Not Commitment-Eligible'
      else 'Commitment-Eligible Uncovered'
    end as instrument_family
    """


def _aggregate_frame(
    con: duckdb.DuckDBPyConnection,
    table_name: str,
    complete_periods: list[str],
    dimensions: list[str],
) -> pd.DataFrame:
    period_list = ", ".join(f"'{period}'" for period in complete_periods)
    group_by = ", ".join(str(index) for index in range(1, len(dimensions) + 1))
    select_dimensions = ",\n      ".join(dimensions)
    stmt = f"""
    select
      {select_dimensions},
      sum(on_demand_cost) as on_demand_cost,
      sum(amortized_cost) as amortized_cost
    from {table_name}
    where billing_period in ({period_list})
    group by {group_by}
    order by {group_by}
    """
    return add_effective_savings_columns(con.execute(stmt).df())


def _instrument_summary(detail: pd.DataFrame) -> pd.DataFrame:
    frame = detail.copy()
    discounted_mask = (frame["cost_type"] == "Usage with Discount") & (
        frame["instrument_family"] != "Spot (non-commitment cost)"
    )
    frame["commitment_realized_savings_dollars"] = frame["savings_dollars"].where(discounted_mask, 0.0)
    frame["spot_savings_vs_on_demand_dollars"] = frame["savings_dollars"].where(frame["cost_type"] == "Spot Usage", 0.0)
    frame["waste_dollars"] = frame["amortized_cost"].where(frame["cost_type"] == "Unused Commitment", 0.0)
    summary = frame.groupby("instrument_family", as_index=False)[
        [
            "on_demand_cost",
            "amortized_cost",
            "commitment_realized_savings_dollars",
            "spot_savings_vs_on_demand_dollars",
            "waste_dollars",
        ]
    ].sum()
    summary["net_savings_dollars"] = summary["on_demand_cost"] - summary["amortized_cost"]
    summary["net_effective_savings_rate"] = summary["net_savings_dollars"] / summary["on_demand_cost"]
    summary.loc[summary["on_demand_cost"] <= 0, "net_effective_savings_rate"] = None
    return summary.sort_values("net_savings_dollars", ascending=False)


def _top_lines(frame: pd.DataFrame, label: str, value: str, template: str, count: int = 3) -> str:
    top = frame.loc[frame[value] > 0, [label, value]].sort_values(value, ascending=False).head(count)
    if top.empty:
        return "- none"
    return "\n".join(
        template.format(name=getattr(row, label), value=_money(getattr(row, value))) for row in top.itertuples(index=False)
    )


def _driver_lines(outputs: dict[str, pd.DataFrame]) -> dict[str, str]:
    return {
        "instrument_savings": _top_lines(
            outputs["instrument"],
            "instrument_family",
            "commitment_realized_savings_dollars",
            "- {name}: {value} realized commitment savings.",
        ),
        "spot": _top_lines(
            outputs["instrument"],
            "instrument_family",
            "spot_savings_vs_on_demand_dollars",
            "- {name}: {value} lower than on-demand, included in account cost but shown separately from commitment savings.",
            count=1,
        ),
        "waste": _top_lines(
            outputs["instrument"],
            "instrument_family",
            "waste_dollars",
            "- {name}: {value} unused commitment cost.",
        ),
        "service": _top_lines(
            outputs["service"],
            "product_code",
            "savings_dollars",
            "- {name}: {value} net savings.",
        ),
    }


def _monthly_summary(detail: pd.DataFrame) -> pd.DataFrame:
    frame = detail.copy()
    discounted_mask = (frame["cost_type"] == "Usage with Discount") & (
        frame["instrument_family"] != "Spot (non-commitment cost)"
    )
    frame["commitment_savings_dollars"] = frame["savings_dollars"].where(discounted_mask, 0.0)
    frame["spot_savings_vs_on_demand_dollars"] = frame["savings_dollars"].where(frame["cost_type"] == "Spot Usage", 0.0)
    frame["waste_dollars"] = frame["amortized_cost"].where(frame["cost_type"] == "Unused Commitment", 0.0)
    monthly = frame.groupby("billing_period", as_index=False)[
        [
            "on_demand_cost",
            "amortized_cost",
            "savings_dollars",
            "commitment_savings_dollars",
            "spot_savings_vs_on_demand_dollars",
            "waste_dollars",
        ]
    ].sum()
    monthly["other_reconciliation"] = (
        monthly["savings_dollars"]
        - monthly["commitment_savings_dollars"]
        - monthly["spot_savings_vs_on_demand_dollars"]
        + monthly["waste_dollars"]
    )
    monthly["effective_savings_rate"] = monthly["savings_dollars"] / monthly["on_demand_cost"]
    monthly.loc[monthly["on_demand_cost"] <= 0, "effective_savings_rate"] = None
    return monthly.sort_values("billing_period")


def choose_analysis_window(periods: pd.DataFrame) -> tuple[list[str], list[str]]:
    complete = periods.loc[periods["is_complete"], "billing_period"].tolist()
    partial = periods.loc[~periods["is_complete"], "billing_period"].tolist()
    if not complete:
        raise ValueError("no complete billing periods available for Challenge 1")
    return complete, partial


def collect_outputs(
    con: duckdb.DuckDBPyConnection,
    complete_periods: list[str],
    table_name: str = "usage_ready",
) -> dict[str, pd.DataFrame]:
    service = _aggregate_frame(con, table_name, complete_periods, ["product_code"])
    commitment = _aggregate_frame(
        con,
        table_name,
        complete_periods,
        ["coalesce(commitment, 'No Commitment') as commitment", "commitment_key", "cost_type"],
    )
    monthly = _aggregate_frame(con, table_name, complete_periods, ["billing_period"])
    cost_type = _aggregate_frame(con, table_name, complete_periods, ["cost_type"])
    instrument_detail = _aggregate_frame(con, table_name, complete_periods, [_instrument_family_expr(), "cost_type"])
    monthly_detail = _aggregate_frame(con, table_name, complete_periods, ["billing_period", _instrument_family_expr(), "cost_type"])
    return {
        "service": service.sort_values("savings_dollars", ascending=False),
        "commitment": commitment.sort_values("savings_dollars", ascending=False),
        "monthly": monthly,
        "cost_type": cost_type,
        "instrument": _instrument_summary(instrument_detail),
        "instrument_detail": instrument_detail.sort_values("savings_dollars", ascending=False),
        "monthly_summary": _monthly_summary(monthly_detail),
    }


def _anomaly_note(partial_periods: list[str], monthly: pd.DataFrame, warnings: list[str]) -> str:
    negative_months = monthly.loc[monthly["savings_dollars"] < 0, "billing_period"].tolist()
    if negative_months:
        months = ", ".join(negative_months)
        return (
            "Material anomaly found: one or more complete months show negative savings "
            f"({months}). That is a data-backed signal that waste or unfavorable discounting "
            "outweighed realized discounts in those months. Recommendation impact: inspect the "
            "affected commitment rows before treating the headline rate as stable."
        )
    if warnings:
        return f"No material savings anomaly found inside the complete-month window. Dataset artifact noted: {warnings[0]}"
    if partial_periods:
        months = ", ".join(partial_periods)
        return (
            "No material savings anomaly found inside the complete-month window. The only clear "
            f"artifact was partial billing period data ({months}), which was excluded from the "
            "headline rate so the summary is not biased by an incomplete month."
        )
    return "No material anomaly found. Negative savings and partial-period artifacts were checked and not observed."


def build_metrics(
    outputs: dict[str, pd.DataFrame],
    complete_periods: list[str],
    partial_periods: list[str],
    validation_warnings: list[str],
) -> dict[str, Any]:
    monthly = outputs["monthly"]
    headline = effective_savings_metrics(monthly)
    waste_row = outputs["cost_type"].loc[outputs["cost_type"]["cost_type"] == "Unused Commitment"]
    spot_row = outputs["instrument"].loc[outputs["instrument"]["instrument_family"] == "Spot (non-commitment cost)"]
    waste_dollars = 0.0 if waste_row.empty else float(waste_row["amortized_cost"].iloc[0])
    spot_savings_vs_on_demand_dollars = (
        0.0 if spot_row.empty else float(spot_row["spot_savings_vs_on_demand_dollars"].iloc[0])
    )
    commitment_savings_dollars = float(outputs["instrument"]["commitment_realized_savings_dollars"].sum())
    other_reconciliation_dollars = float(outputs["monthly_summary"]["other_reconciliation"].sum())
    reconciliation_gap = abs(monthly["savings_dollars"].sum() - headline["savings_dollars"])
    warnings = list(validation_warnings)
    if partial_periods:
        warnings.append(f"Excluded partial billing periods from headline metric: {', '.join(partial_periods)}")
    if headline["effective_savings_rate"] is None:
        warnings.append("Headline effective savings rate has a zero or negative on-demand denominator.")
    if (monthly["savings_dollars"] < 0).any():
        warnings.append("At least one complete billing period has negative savings.")
    if reconciliation_gap > 1e-6:
        warnings.append(f"Monthly savings do not reconcile exactly to headline savings: {reconciliation_gap:.6f}")
    return {
        "challenge": "challenge_01_effective_savings_rate",
        "trust_level": "medium" if warnings else "high",
        "warnings": warnings,
        "window": {
            "billing_periods_included": complete_periods,
            "billing_periods_excluded": partial_periods,
        },
        "headline": {
            **headline,
            "commitment_savings_dollars": commitment_savings_dollars,
            "spot_savings_vs_on_demand_dollars": spot_savings_vs_on_demand_dollars,
            "waste_dollars": waste_dollars,
            "other_reconciliation_dollars": other_reconciliation_dollars,
        },
        "reconciliation": {
            "monthly_savings_minus_headline_savings": float(
                monthly["savings_dollars"].sum() - headline["savings_dollars"]
            )
        },
    }


def _summary_text(
    headline: dict[str, Any],
    included_window: str,
    anomaly_note: str,
    drivers: dict[str, str],
) -> str:
    return f"""
# Challenge 1 Summary

Headline effective savings rate: {_rate_text(headline['effective_savings_rate'])}

## Headline

- Analysis window: {included_window}
- On-demand equivalent: {_money(headline['on_demand_cost'])}
- Amortized actual cost: {_money(headline['amortized_cost'])}
- Savings dollars: {_money(headline['savings_dollars'])}
- Commitment discount: {_money(headline['commitment_savings_dollars'])}
- Spot market savings: {_money(headline['spot_savings_vs_on_demand_dollars'])}
- Unused commitment waste: {_money(headline['waste_dollars'])}
- Other / reconciliation: {_money(headline['other_reconciliation_dollars'])}

## What The Metric Means

Effective savings rate is defined as `(sum(on_demand_cost) - sum(amortized_cost)) / sum(on_demand_cost)` over complete billing periods only.

The monthly bridge starts from the on-demand equivalent, subtracts commitment discount and Spot market savings, adds unused commitment waste, applies other / reconciliation, and lands on actual amortized cost.

Spot is included in the account's actual cost because it is real spend, but Spot market savings are shown separately from commitment discount.

Unused commitment waste can coexist with Spot in the same month because commitments do not apply to Spot, and waste can happen in different workloads or lower-usage hours while Spot spend happens elsewhere.

## Main Drivers

### Commitment discount by instrument

{drivers['instrument_savings']}

### Spot cost treatment

{drivers['spot']}

### Waste by instrument

{drivers['waste']}

### Savings by service

{drivers['service']}

## Key Takeaways

- The denominator includes all in-scope on-demand spend for the chosen window.
- Spot is included as account cost, but Spot market savings are separated from commitment discount so the bridge stays honest.
- Unused commitment waste is shown as a cost increase instead of being folded into net savings.
- Service, commitment, and instrument decompositions are written to `tables/` for drill-down and later presentation use.

## Anomaly Review Note

{anomaly_note}

## Assumptions And Risks

- Incomplete billing periods are excluded rather than scaled up.
- This challenge reports current realized savings only; it does not estimate a better future commitment level.
- `Unused Commitment` is treated as paid waste based on the dataset's `cost_type` semantics.
"""


def _methodology_text(complete_periods: list[str], partial_periods: list[str], validation_warnings: list[str]) -> str:
    return f"""
# Challenge 1 Methodology

## Window

- Included complete billing periods: {', '.join(complete_periods)}
- Excluded partial billing periods: {', '.join(partial_periods) if partial_periods else 'none'}

## Steps

1. Load the raw usage dataset and pricing reference directly from the documented parquet files.
2. Build the shared `usage_ready` analysis view with normalized hourly buckets.
3. Review shared readiness warnings and stop only on fatal issues.
4. Aggregate `on_demand_cost` and `amortized_cost` by month, service, commitment, instrument family, and cost type.
5. Compute the monthly bridge components: commitment discount, Spot market savings, unused commitment waste, and other / reconciliation.
6. Save tables, plots, and report markdown.

## Notes

- The savings-by-commitment table keeps `cost_type` so `Unused Commitment` stays visible as waste evidence.
- Instrument families are inferred from commitment scope: `AWS#Compute*`, `AWS#Database*`, and `AWS#Sagemaker*` map to Savings Plan families; other covered commitments are treated as Reserved Instances.
- Spot rows are included in actual cost but called out separately as Spot market savings, not commitment discount.
- Validation warnings: {', '.join(validation_warnings) if validation_warnings else 'none'}.
"""


def _ledger_text(included_window: str, anomaly_note: str) -> str:
    return f"""
# Understanding Ledger

## What I Verified Myself

- Verified the effective savings formula matches the challenge doc: savings over on-demand counterfactual.
- Verified billing period completeness from distinct normalized hourly buckets before selecting the window.
- Verified Spot is treated as account cost in the headline but separated from commitment-derived savings in the instrument decomposition.
- Verified monthly sums reconcile back to the headline totals within a small floating-point tolerance.

## What I Delegated And Trusted

- Trusted DuckDB to scan parquet files and produce the SQL aggregates once the readiness checks passed.
- Trusted matplotlib for direct plot rendering after checking the underlying tables.

## What I'm Unsure Of

- Whether stakeholders would prefer the partial current month to appear as a flagged appendix instead of being excluded from the headline rate.
- Whether some commitments classified as waste should be interpreted differently in edge AWS billing cases outside this dataset.
- Whether commitment ARN-level metadata would materially change the instrument-family inference for some covered rows.
- Challenge 1 does not test alternate windows, so rate stability outside {included_window} is not established here.

## Anomaly Review

{anomaly_note}
"""


def build_report_texts(
    metrics: dict[str, Any],
    complete_periods: list[str],
    partial_periods: list[str],
    outputs: dict[str, pd.DataFrame],
    validation_warnings: list[str],
) -> dict[str, str]:
    headline = metrics["headline"]
    included_window = f"{complete_periods[0]} to {complete_periods[-1]}"
    anomaly_note = _anomaly_note(partial_periods, outputs["monthly"], validation_warnings)
    drivers = _driver_lines(outputs)
    return {
        "summary.md": _summary_text(headline, included_window, anomaly_note, drivers),
        "methodology.md": _methodology_text(complete_periods, partial_periods, validation_warnings),
        "understanding_ledger.md": _ledger_text(included_window, anomaly_note),
    }
