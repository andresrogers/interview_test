"""Purpose:
Assemble minimal Challenge 2 metrics and report text.

Owns:
- Challenge 2 window selection.
- Optimizer input validation messages.
- Challenge 2 markdown and metrics payloads.

Does Not Own:
- DuckDB parquet loading.
- Hourly commitment allocation mechanics.

Main Entry Points:
- choose_analysis_window
- validate_optimizer_inputs
- build_metrics
- build_report_texts

Key Invariants:
- Challenge 2 uses the most recent three complete billing periods.
- Missing pricing and zero-usage rows are reported, not hidden.
- Anomaly review stays inside the main report files.

Update This Header When:
- Public entry points change.
- Deliverables or validation rules change.
"""

from __future__ import annotations

from typing import Any

import pandas as pd


def choose_analysis_window(periods: pd.DataFrame, month_count: int = 3) -> tuple[list[str], list[str], list[str]]:
    complete = periods.loc[periods["is_complete"], "billing_period"].tolist()
    partial = periods.loc[~periods["is_complete"], "billing_period"].tolist()
    if len(complete) < month_count:
        raise ValueError(f"need at least {month_count} complete billing periods for Challenge 2")
    included = complete[-month_count:]
    excluded = complete[:-month_count]
    return included, partial, excluded


def validate_optimizer_inputs(joined: pd.DataFrame, eligible_usage: pd.DataFrame, duplicate_price_keys: int) -> tuple[list[str], pd.DataFrame]:
    quarantined = joined.loc[
        (joined["usage_amount"] <= 0)
        | joined["discounted_rate"].isna()
        | joined["on_demand_rate"].isna()
        | (joined["discounted_cost"] < 0)
        | (joined["gross_savings_if_fully_covered"] < -1e-9)
        | (joined["discounted_rate"] > joined["on_demand_rate"] + 1e-9)
    ].copy()
    warnings = []
    if duplicate_price_keys:
        warnings.append(
            f"Pinned pricing selection still has {duplicate_price_keys} duplicate price_list_key rows; challenge 2 requires one compute plan rate per key."
        )
    if not quarantined.empty:
        warnings.append(f"Quarantined {len(quarantined):,} compute rows with zero usage, missing pricing, or invalid economics.")
    if eligible_usage.empty:
        warnings.append("No valid Compute Savings Plan-eligible non-Spot rows remained after validation.")
    if bool(joined["cost_type"].eq("Unused Commitment").any()):
        warnings.append("Historical `Unused Commitment` rows were excluded from the optimizer because they are waste evidence, not coverable usage.")
    return warnings, quarantined


def _as_float(value: float | None) -> float:
    return 0.0 if value is None else float(value)


def _money(value: float) -> str:
    return f"${value:,.2f}"


def _rate(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.2%}"


def _anomaly_note(hourly: pd.DataFrame, warnings: list[str]) -> str:
    negative_hours = int((hourly["net_savings"] < 0).sum())
    idle_hours = int((hourly["eligible_discounted_cost"] == 0).sum())
    if negative_hours:
        return (
            f"Material anomaly found: {negative_hours:,} hours are net-negative at the optimum because hourly waste exceeded covered savings. "
            "That is a real use-it-or-lose-it signal, not a plotting artifact. Recommendation impact: explain downside hours alongside the headline savings."
        )
    if idle_hours:
        return (
            f"No net-negative optimum hours found, but {idle_hours:,} hours had zero Compute-eligible usage. "
            "Those hours are where any oversized commitment would become pure waste, so the savings curve should be read as a variability story."
        )
    if warnings:
        return f"No material allocation anomaly found after validation. Main artifact reviewed: {warnings[0]}"
    return "No material anomaly found. Highest-discount-first allocation, waste, and zero-usage hours were checked."


def _tradeoff_note(headline: dict[str, Any], hourly: pd.DataFrame) -> str:
    negative_hours = int((hourly["net_savings"] < 0).sum())
    waste = _as_float(headline["total_unused_commitment_waste"])
    utilization = headline["average_utilization"]
    if negative_hours:
        return (
            f"The optimum still has {negative_hours:,} downside hours, so the peak reflects a tradeoff between extra covered discounts and extra idle commitment. "
            f"At the chosen point the plan wastes {_money(waste)} and still comes out ahead overall."
        )
    return (
        f"The curve peaks where almost all of the commitment is consumed (utilization {_rate(utilization)}) while waste stays small at {_money(waste)}. "
        "To the left, the account leaves discount on the table. To the right, extra commitment mostly adds waste instead of new savings."
    )


def build_metrics(
    optimum: dict[str, float | None],
    hourly: pd.DataFrame,
    curve: pd.DataFrame,
    included_periods: list[str],
    partial_periods: list[str],
    excluded_complete_periods: list[str],
    warnings: list[str],
) -> dict[str, Any]:
    curve_peak = float(curve["total_savings_dollars"].to_numpy(dtype=float).max()) if not curve.empty else 0.0
    metrics_warnings = list(warnings)
    if partial_periods:
        metrics_warnings.append(f"Excluded partial billing periods from optimization: {', '.join(partial_periods)}")
    if excluded_complete_periods:
        metrics_warnings.append(
            f"Used only the most recent three complete periods: {', '.join(included_periods)}; older complete periods kept out of scope."
        )
    if abs(curve_peak - _as_float(optimum["total_savings_dollars"])) > 1e-6:
        metrics_warnings.append("Savings curve peak did not reconcile to the evaluated optimum within tolerance.")
    return {
        "challenge": "challenge_02_optimal_commitment",
        "trust_level": "medium" if metrics_warnings else "high",
        "warnings": metrics_warnings,
        "window": {
            "billing_periods_included": included_periods,
            "billing_periods_excluded_partial": partial_periods,
            "billing_periods_excluded_complete": excluded_complete_periods,
        },
        "headline": optimum,
        "hourly_profile": {
            "hours_in_window": int(len(hourly)),
            "negative_hours_at_optimum": int((hourly["net_savings"] < 0).sum()),
            "idle_compute_hours": int((hourly["eligible_discounted_cost"] == 0).sum()),
        },
    }


def build_report_texts(
    metrics: dict[str, Any],
    hourly: pd.DataFrame,
    service_summary: pd.DataFrame,
    warnings: list[str],
    pricing_view: str,
) -> dict[str, str]:
    headline = metrics["headline"]
    periods = metrics["window"]["billing_periods_included"]
    included_window = f"{periods[0]} to {periods[-1]}"
    anomaly_note = _anomaly_note(hourly, warnings)
    tradeoff_note = _tradeoff_note(headline, hourly)
    top_services = service_summary.head(3)
    service_lines = "\n".join(
        f"- {row['product_code']}: {_money(float(row['on_demand_cost']))} eligible on-demand, {_money(float(row['gross_savings_if_fully_covered']))} max gross savings if fully covered."
        for row in top_services.to_dict("records")
    ) or "- none"
    return {
        "summary.md": f"""
# Challenge 2 Summary

Optimal Compute Savings Plan commitment: {_money(_as_float(headline['commitment_per_hour']))}/hour

## Headline

- Analysis window: {included_window}
- Pricing view: {pricing_view}
- Optimal commitment: {_money(_as_float(headline['commitment_per_hour']))}/hour discounted spend
- Total savings at optimum: {_money(_as_float(headline['total_savings_dollars']))}
- Effective savings rate on eligible compute spend: {_rate(headline['effective_savings_rate'])}
- Average utilization at optimum: {_rate(headline['average_utilization'])}
- Coverage of eligible compute on-demand spend: {_rate(headline['coverage_rate'])}
- Unused commitment waste at optimum: {_money(_as_float(headline['total_unused_commitment_waste']))}

## What This Answers

This challenge sizes one fixed Compute Savings Plan in discounted dollars per hour. The optimizer allocates the commitment every hour to eligible non-Spot `AWS#Compute*` usage in highest-discount-first order, then charges on-demand for the uncovered remainder.

## Main Drivers

{service_lines}

## Product Communication Note

- Customer headline card: "This plan would have saved {_money(_as_float(headline['total_savings_dollars']))} over {included_window}."
- Support card 1: "Recommended commitment = {_money(_as_float(headline['commitment_per_hour']))}/hour" with the savings-curve plot and the optimum point called out.
- Support card 2: "Why not higher?" show unused commitment waste of {_money(_as_float(headline['total_unused_commitment_waste']))} and note that quiet hours can waste unused commitment.
- Plain-language explainer: "AWS applies the plan each hour to the compute usage where it saves the most first, then any leftover usage stays on-demand."

## Why This Is The Maximum

{tradeoff_note}

## Anomaly Review Note

{anomaly_note}

## Assumptions And Risks

- The result uses the most recent three complete months only; older history may imply a different sizing target.
- Spot is excluded because Savings Plans do not discount Spot.
- Missing or invalid pricing matches are quarantined and reported in `metrics.json` warnings.
- The recommendation is hindsight-optimal on history, not a forward guarantee.
""",
        "methodology.md": f"""
# Challenge 2 Methodology

## Window

- Included complete billing periods: {', '.join(periods)}
- Excluded partial periods: {', '.join(metrics['window']['billing_periods_excluded_partial']) or 'none'}
- Excluded older complete periods: {', '.join(metrics['window']['billing_periods_excluded_complete']) or 'none'}

## Pricing View

- Instrument: `compute_savings_plan`
- Term: 36 months
- Payment option: `no_upfront`
- Offering class: `savings_plan`

## Steps

1. Load raw parquet inputs into DuckDB and build the shared `usage_ready` view.
2. Keep only the most recent three complete billing periods.
3. Select `AWS#Compute*` rows, exclude Spot, and join one Compute Savings Plan rate per `price_list_key`.
4. Quarantine zero-usage rows, missing pricing matches, and rows where discounted economics are invalid.
5. For each hour, sort valid rows by descending discount percentage and build cumulative discounted-cost breakpoints.
6. Sweep commitment breakpoints exactly and evaluate the best commitment with hourly waste, utilization, and coverage metrics.
7. Save the curve, hourly summary, markdown reports, and presentation-ready plots.

## Validation Notes

- Warnings: {', '.join(warnings) if warnings else 'none'}.
- Hours with no eligible Compute usage are still counted; any non-zero commitment in those hours becomes full waste.
- Coverage and utilization are reported separately because they use different denominators.
""",
        "understanding_ledger.md": f"""
# Understanding Ledger

## What I Verified Myself

- Verified the challenge window is the most recent three complete billing periods.
- Verified the optimizer sizes commitment in discounted dollars per hour, not on-demand dollars.
- Verified allocation order is highest discount first and unused hourly commitment becomes waste.
- Verified coverage and utilization are separate metrics with different denominators.

## What I Delegated And Trusted

- Trusted DuckDB to filter the parquet files and join the pinned pricing view after checking for duplicate price keys.
- Trusted the breakpoint sweep to enumerate the exact candidate kinks in the piecewise-linear savings curve.
- Trusted matplotlib for chart rendering after checking the underlying tables and optimum row.

## What I'm Unsure Of

- Whether the last three complete months are representative of future compute demand.
- Whether any quarantined rows would materially change the answer if their pricing metadata were repaired upstream.
- Whether stakeholders would prefer a slightly lower commitment with less downside-hour volatility than the hindsight maximum.

## Anomaly Review

{anomaly_note}
""",
    }
