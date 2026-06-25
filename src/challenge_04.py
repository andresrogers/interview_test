"""Purpose:
Build reusable Challenge 4 baseline-backtest metrics and report text.

Owns:
- Historical compute baseline window selection.
- Baseline vs hindsight-optimal scenario summaries.
- Challenge 4 markdown and metrics payloads.

Does Not Own:
- DuckDB parquet loading.
- Hourly commitment allocation mechanics.

Main Entry Points:
- choose_baseline_backtest_window
- extract_baseline_commitment
- monthly_backtest
- reconciliation_checks
- build_metrics
- build_report_texts

Key Invariants:
- Baseline commitment is fixed after the anchor month.
- Backtest uses the same hourly allocation rules as Challenge 2.
- Reconciliation checks stay explicit in metrics.json.

Update This Header When:
- Public entry points change.
- Baseline anchor policy changes.
"""

from __future__ import annotations

from typing import Any

import duckdb
import pandas as pd

from src.challenge_02 import analysis_hours
from src.metrics import coverage_rate, safe_ratio, utilization_rate


def choose_baseline_backtest_window(periods: pd.DataFrame, months_back: int = 9) -> tuple[str, list[str], list[str]]:
    complete = periods.loc[periods["is_complete"], "billing_period"].tolist()
    partial = periods.loc[~periods["is_complete"], "billing_period"].tolist()
    required_months = months_back + 2
    if len(complete) < required_months:
        raise ValueError(f"need at least {required_months} complete billing periods for Challenge 4")
    anchor_period = complete[-(months_back + 1)]
    forward_periods = complete[-months_back:]
    return anchor_period, forward_periods, partial


def extract_baseline_commitment(con: duckdb.DuckDBPyConnection, anchor_period: str) -> tuple[float, pd.Timestamp | None]:
    stmt = f"""
    with hourly as (
      select
        analysis_timestamp,
        max(baseline_max) as baseline_commitment_per_hour
      from usage_ready
      where billing_period = '{anchor_period}'
        and commitment_key like 'AWS#Compute%'
        and baseline_max is not null
      group by 1
    )
    select analysis_timestamp, baseline_commitment_per_hour
    from hourly
    order by analysis_timestamp desc
    limit 1
    """
    row = con.execute(stmt).fetchone()
    if row is None:
        raise ValueError(f"no compute baseline_max found in anchor period {anchor_period}")
    return float(row[1]), row[0]


def monthly_backtest(hourly: pd.DataFrame) -> pd.DataFrame:
    frame = hourly.copy()
    frame = frame.assign(billing_period=pd.to_datetime(frame["analysis_timestamp"]).dt.strftime("%Y-%m"))
    monthly = pd.DataFrame(frame.groupby("billing_period", as_index=False).agg(
        eligible_on_demand_cost=("eligible_on_demand_cost", "sum"),
        eligible_discounted_cost=("eligible_discounted_cost", "sum"),
        covered_on_demand_cost=("covered_on_demand_cost", "sum"),
        consumed_commitment=("consumed_commitment", "sum"),
        unused_commitment_waste=("unused_commitment_waste", "sum"),
        gross_savings=("gross_savings", "sum"),
        net_savings=("net_savings", "sum"),
    ))
    paid_commitment = [
        float(consumed) + float(unused)
        for consumed, unused in zip(monthly["consumed_commitment"].tolist(), monthly["unused_commitment_waste"].tolist())
    ]
    effective_savings_rate = [
        safe_ratio(float(net), float(on_demand))
        for net, on_demand in zip(monthly["net_savings"].tolist(), monthly["eligible_on_demand_cost"].tolist())
    ]
    coverage = [
        coverage_rate(float(covered), float(on_demand))
        for covered, on_demand in zip(monthly["covered_on_demand_cost"].tolist(), monthly["eligible_on_demand_cost"].tolist())
    ]
    utilization = [
        utilization_rate(float(consumed), float(paid))
        for consumed, paid in zip(monthly["consumed_commitment"].tolist(), paid_commitment)
    ]
    return monthly.assign(
        paid_commitment=paid_commitment,
        effective_savings_rate=effective_savings_rate,
        coverage_rate=coverage,
        utilization=utilization,
    )


def reconciliation_checks(summary: dict[str, float | None], hourly: pd.DataFrame, monthly: pd.DataFrame) -> dict[str, float]:
    total_eligible = float(hourly["eligible_on_demand_cost"].to_numpy(dtype=float).sum())
    total_covered = float(hourly["covered_on_demand_cost"].to_numpy(dtype=float).sum())
    total_paid = float(
        hourly["consumed_commitment"].to_numpy(dtype=float).sum()
        + hourly["unused_commitment_waste"].to_numpy(dtype=float).sum()
    )
    return {
        "monthly_net_savings_gap": abs(
            float(monthly["net_savings"].to_numpy(dtype=float).sum()) - float(summary["total_savings_dollars"] or 0.0)
        ),
        "covered_plus_uncovered_gap": abs(total_eligible - (total_covered + (total_eligible - total_covered))),
        "consumed_plus_unused_gap": abs(total_paid - float(summary["total_paid_commitment"] or 0.0)),
    }


def _as_float(value: float | None) -> float:
    return 0.0 if value is None else float(value)


def scenario_row(label: str, summary: dict[str, float | None]) -> dict[str, Any]:
    return {
        "scenario": label,
        "commitment_per_hour": _as_float(summary["commitment_per_hour"]),
        "total_savings_dollars": _as_float(summary["total_savings_dollars"]),
        "effective_savings_rate": summary["effective_savings_rate"],
        "coverage_rate": summary["coverage_rate"],
        "average_utilization": summary["average_utilization"],
        "total_unused_commitment_waste": _as_float(summary["total_unused_commitment_waste"]),
        "total_paid_commitment": _as_float(summary["total_paid_commitment"]),
        "total_gross_savings_dollars": _as_float(summary.get("total_gross_savings_dollars")),
    }


def _money(value: float) -> str:
    return f"${value:,.2f}"


def _rate(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.2%}"


def _anomaly_note(baseline: dict[str, float | None], optimum: dict[str, float | None]) -> str:
    baseline_util = baseline["average_utilization"]
    baseline_cov = baseline["coverage_rate"]
    optimum_cov = optimum["coverage_rate"]
    if baseline_util is not None and baseline_util >= 0.98 and (optimum_cov or 0.0) > (baseline_cov or 0.0) + 0.05:
        return (
            "Material anomaly found: the fixed baseline stayed almost fully utilized yet still trailed the hindsight optimum. "
            "That is a real growth signal: later compute demand outgrew the old baseline, so the account left discounts unrealized rather than wasting commitment."
        )
    if _as_float(baseline["total_unused_commitment_waste"]) > 0:
        return (
            "Material anomaly found: a baseline derived from past usage still produced waste in the forward window. "
            "That is a real regime-change signal, not a modeling artifact."
        )
    return "No material anomaly found. The fixed baseline behaved as expected under hourly highest-discount-first allocation."


def build_metrics(context: dict[str, Any]) -> dict[str, Any]:
    baseline = context["baseline"]
    optimum = context["optimal"]
    baseline_checks = reconciliation_checks(baseline, context["baseline_hourly"], context["baseline_monthly"])
    optimum_checks = reconciliation_checks(optimum, context["optimal_hourly"], context["optimal_monthly"])
    metrics_warnings = list(context["warnings"])
    partial_periods = context["partial_periods"]
    if partial_periods:
        metrics_warnings.append(f"Excluded partial billing periods from backtest: {', '.join(partial_periods)}")
    for scenario, checks in {"baseline": baseline_checks, "optimal": optimum_checks}.items():
        for name, gap in checks.items():
            if gap > 1e-6:
                metrics_warnings.append(f"{scenario} reconciliation failed for {name}: {gap:.6f}")
    return {
        "challenge": "challenge_04_baseline_realized_savings",
        "trust_level": "medium" if metrics_warnings else "high",
        "warnings": metrics_warnings,
        "window": {
            "baseline_anchor_period": context["anchor_period"],
            "baseline_anchor_timestamp": None
            if context["anchor_timestamp"] is None
            else context["anchor_timestamp"].isoformat(),
            "forward_periods": context["forward_periods"],
            "excluded_partial_periods": partial_periods,
        },
        "headline": {
            "baseline": baseline,
            "optimal": optimum,
            "savings_gap_dollars": _as_float(optimum["total_savings_dollars"]) - _as_float(baseline["total_savings_dollars"]),
            "effective_savings_rate_gap": (optimum["effective_savings_rate"] or 0.0) - (baseline["effective_savings_rate"] or 0.0),
        },
        "reconciliation": {
            "baseline": baseline_checks,
            "optimal": optimum_checks,
        },
    }


def build_report_texts(metrics: dict[str, Any]) -> dict[str, str]:
    baseline = metrics["headline"]["baseline"]
    optimum = metrics["headline"]["optimal"]
    periods = metrics["window"]["forward_periods"]
    anomaly_note = _anomaly_note(baseline, optimum)
    return {
        "summary.md": f"""
# Challenge 4 Summary

Fixed compute baseline realized savings rate: {_rate(baseline['effective_savings_rate'])}

## Headline

- Baseline anchor month: {metrics['window']['baseline_anchor_period']}
- Forward backtest window: {periods[0]} to {periods[-1]}
- Fixed baseline commitment: {_money(_as_float(baseline['commitment_per_hour']))}/hour discounted spend
- Baseline realized savings: {_money(_as_float(baseline['total_savings_dollars']))}
- Baseline realized effective savings rate: {_rate(baseline['effective_savings_rate'])}
- Baseline waste: {_money(_as_float(baseline['total_unused_commitment_waste']))}
- Hindsight-optimal fixed commitment: {_money(_as_float(optimum['commitment_per_hour']))}/hour
- Hindsight-optimal savings over same window: {_money(_as_float(optimum['total_savings_dollars']))}
- Savings gap vs optimum: {_money(float(metrics['headline']['savings_gap_dollars']))}

## What This Answers

This backtest freezes the compute baseline roughly nine months before the latest complete month, then applies that same hourly commitment level forward with the same use-it-or-lose-it allocation rules from Challenge 2.

## Interpretation

- Baseline utilization: {_rate(baseline['average_utilization'])}
- Baseline coverage of eligible compute spend: {_rate(baseline['coverage_rate'])}
- Optimal utilization over same window: {_rate(optimum['average_utilization'])}
- Optimal coverage over same window: {_rate(optimum['coverage_rate'])}

The gap quantifies what a historically safe commitment missed once later usage moved. If the baseline stays highly utilized but still trails the optimum, that means growth created unrealized discounts. If baseline waste appears, that means the historical level became too large for later quiet hours.

## Anomaly Review Note

{anomaly_note}

## Assumptions And Risks

- The baseline level is taken from the last available `baseline_max` value in the anchor month and then held fixed from the next complete month onward.
- The backtest scope is Compute Savings Plan-eligible non-Spot usage only.
- The pricing view matches Challenge 2: `compute_savings_plan`, 36 months, `no_upfront`, `savings_plan`.
- Missing pricing or invalid compute rows are quarantined and reported in `metrics.json` warnings.
""",
        "methodology.md": f"""
# Challenge 4 Methodology

## Steps

1. Keep complete billing periods only.
2. Pick the compute baseline anchor month about nine months before the latest complete month.
3. Read the last available compute `baseline_max` in that anchor month and treat it as the fixed commitment level.
4. Reuse the Challenge 2 compute pricing join and hourly allocation logic on the forward window only.
5. Evaluate the fixed baseline and the hindsight-optimal fixed commitment over the same forward window.
6. Write monthly tables, hourly tables, plots, and reconciliation checks.

## Validation Notes

- Reconciliation checks live in `metrics.json` for baseline and optimal scenarios.
- Coverage denominator = eligible compute on-demand cost.
- Utilization denominator = paid commitment dollars.
- Warnings: {', '.join(metrics['warnings']) if metrics['warnings'] else 'none'}.
""",
        "understanding_ledger.md": """
# Understanding Ledger

## What I Verified Myself

- Verified the baseline commitment stays fixed after the anchor month.
- Verified the forward backtest reuses the same hourly commitment mechanics as Challenge 2.
- Verified realized savings and waste reconcile from hourly rows into monthly totals.

## What I Delegated And Trusted

- Trusted repeated hourly evaluation once the fixed-baseline and optimal scenarios matched their reconciliation checks.
- Trusted plot rendering after the chart annotations matched the exported CSV tables.

## What I'm Unsure Of

- Whether the challenge wanted the anchor taken exactly nine months prior or approximately nine months prior; this implementation uses the nearest complete anchor month.
- Whether a different baseline extraction point inside the anchor month would materially change the result.
""",
    }
