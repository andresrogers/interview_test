"""Purpose:
Build reusable window-sensitivity outputs for Challenge 3.

Owns:
- Window-set construction for trailing and anchored views.
- Window-sensitivity metrics and recommendation text.
- Challenge 3 markdown report text.

Does Not Own:
- Hourly commitment allocation mechanics.
- Plot rendering.

Main Entry Points:
- build_window_specs
- monthly_regime_summary
- build_metrics
- build_report_texts

Key Invariants:
- Trailing windows use complete billing periods only.
- Anchored windows reuse the same optimizer as Challenge 2.
- Recommendation stays explicit about regime-change risk.

Update This Header When:
- Public entry points change.
- Recommendation logic changes.
"""

from __future__ import annotations

from typing import Any

import duckdb
import pandas as pd


def build_window_specs(complete_periods: list[str]) -> list[dict[str, Any]]:
    specs = []
    for month_count in (1, 2, 3, 6):
        if len(complete_periods) < month_count:
            continue
        periods = complete_periods[-month_count:]
        label = f"trailing_{month_count:02d}m"
        specs.append(
            {
                "window_label": label,
                "window_type": "trailing",
                "month_count": month_count,
                "billing_periods": periods,
                "start_period": periods[0],
                "end_period": periods[-1],
            }
        )
    if len(complete_periods) >= 3:
        for start in range(len(complete_periods) - 2):
            periods = complete_periods[start : start + 3]
            specs.append(
                {
                    "window_label": f"anchored_{periods[0]}_to_{periods[-1]}",
                    "window_type": "anchored",
                    "month_count": 3,
                    "billing_periods": periods,
                    "start_period": periods[0],
                    "end_period": periods[-1],
                }
            )
    return specs


def monthly_regime_summary(
    con: duckdb.DuckDBPyConnection,
    complete_periods: list[str],
    term_months: int,
    payment_option: str,
    offering_class: str,
) -> pd.DataFrame:
    period_list = ", ".join(f"'{period}'" for period in complete_periods)
    stmt = f"""
    with compute_usage as (
      select
        usage.billing_period,
        sum(usage.on_demand_cost) as eligible_on_demand_cost,
        sum(usage.usage_amount * pricing.rate) as eligible_discounted_cost,
        sum(usage.on_demand_cost - usage.usage_amount * pricing.rate) as gross_savings_if_fully_covered
      from usage_ready as usage
      left join pricing
        on usage.price_list_key = pricing.price_list_key
       and lower(pricing.instrument_type) = 'compute_savings_plan'
       and pricing.term_months = {term_months}
       and lower(pricing.payment_option) = '{payment_option}'
       and lower(pricing.offering_class) = '{offering_class}'
      where usage.billing_period in ({period_list})
        and usage.commitment_key like 'AWS#Compute%'
        and coalesce(usage.cost_type, '') != 'Spot Usage'
        and usage.usage_amount > 0
        and pricing.rate is not null
      group by 1
    )
    select
      billing_period,
      eligible_on_demand_cost,
      eligible_discounted_cost,
      gross_savings_if_fully_covered,
      eligible_discounted_cost - lag(eligible_discounted_cost) over (order by billing_period) as discounted_cost_change,
      eligible_discounted_cost / nullif(lag(eligible_discounted_cost) over (order by billing_period), 0) - 1 as discounted_cost_change_pct
    from compute_usage
    order by billing_period
    """
    return con.execute(stmt).df()


def _as_float(value: float | None) -> float:
    return 0.0 if value is None else float(value)


def _money(value: float) -> str:
    return f"${value:,.2f}"


def _rate(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.2%}"


def _recommended_rule(results: pd.DataFrame) -> dict[str, Any]:
    trailing = results.loc[results["window_type"] == "trailing"].copy()
    trailing_three = trailing.loc[trailing["month_count"] == 3]
    trailing_six = trailing.loc[trailing["month_count"] == 6]
    if trailing_three.empty:
        row = trailing.sort_values("end_period").iloc[-1]
        return {
            "rule": "Use the most recent complete trailing window available.",
            "recommended_window_label": row["window_label"],
            "recommended_commitment_per_hour": float(row["commitment_per_hour"]),
            "reason": "Only one stable trailing window was available, so broader sensitivity could not be compared.",
        }
    row = trailing_three.iloc[0]
    if not trailing_six.empty:
        six = trailing_six.iloc[0]
        gap = abs(float(row["commitment_per_hour"]) - float(six["commitment_per_hour"]))
        baseline = max(float(six["commitment_per_hour"]), 1e-9)
        if gap / baseline > 0.2:
            recommended = min(float(row["commitment_per_hour"]), float(six["commitment_per_hour"]))
            return {
                "rule": "Use recent 3 complete months, then cap the buy at the lower of the trailing 3-month and 6-month optima.",
                "recommended_window_label": row["window_label"],
                "recommended_commitment_per_hour": recommended,
                "reason": "The 3-month and 6-month optima diverge materially, which signals a regime shift. Capping at the lower level keeps recent demand in view while limiting over-commit risk.",
            }
    return {
        "rule": "Use the most recent 3 complete months as the primary sizing window.",
        "recommended_window_label": row["window_label"],
        "recommended_commitment_per_hour": float(row["commitment_per_hour"]),
        "reason": "The recent 3-month result is close enough to broader trailing history that it gives a current signal without obvious instability.",
    }


def build_metrics(
    results: pd.DataFrame,
    regime: pd.DataFrame,
    warnings: list[str],
) -> dict[str, Any]:
    recommendation = _recommended_rule(results)
    spread = float(results["commitment_per_hour"].max() - results["commitment_per_hour"].min()) if not results.empty else 0.0
    change = regime["discounted_cost_change"].dropna() if not regime.empty else pd.Series(dtype=float)
    top_jump = regime.loc[change.abs().idxmax()].to_dict() if not change.empty else {}
    metrics_warnings = list(warnings)
    if spread > 0:
        metrics_warnings.append(f"Window sensitivity spread in optimal commitment is {_money(spread)}/hour across evaluated windows.")
    return {
        "challenge": "challenge_03_window_sensitivity",
        "trust_level": "medium" if metrics_warnings else "high",
        "warnings": metrics_warnings,
        "headline": {
            "recommended_window_rule": recommendation["rule"],
            "recommended_window_label": recommendation["recommended_window_label"],
            "recommended_commitment_per_hour": recommendation["recommended_commitment_per_hour"],
            "window_count": int(len(results)),
            "optimal_commitment_spread_per_hour": spread,
        },
        "regime_change": top_jump,
    }


def _anomaly_note(results: pd.DataFrame, regime: pd.DataFrame) -> str:
    anchored = results.loc[results["window_type"] == "anchored"]
    if len(anchored) >= 2 and anchored["commitment_per_hour"].max() > anchored["commitment_per_hour"].min() * 1.2:
        return (
            "Material anomaly found: anchored 3-month windows produce meaningfully different optima. "
            "That is a real regime-change signal, not chart noise, because the optimizer is unchanged and only the history slice moved. "
            "Recommendation impact: do not buy to the highest hindsight window without checking whether that demand still exists."
        )
    if not regime.empty and regime["discounted_cost_change"].abs().max() > 0:
        jump = regime.loc[regime["discounted_cost_change"].abs().idxmax()]
        return (
            f"Largest monthly shift appears at {jump['billing_period']}, where eligible discounted compute spend moved by {_money(float(jump['discounted_cost_change']))}. "
            "Treat that as a real usage change first and an optimization result second."
        )
    return "No material anomaly found. Window shifts did not show a strong regime break in the evaluated history."


def build_report_texts(metrics: dict[str, Any], results: pd.DataFrame, regime: pd.DataFrame) -> dict[str, str]:
    headline = metrics["headline"]
    recommendation = _recommended_rule(results)
    best = results.sort_values("total_savings_dollars", ascending=False).iloc[0]
    trailing_lines = "\n".join(
        f"- {row.window_label}: {_money(float(row.commitment_per_hour))}/hour, {_money(float(row.total_savings_dollars))} savings, {_rate(float(row.average_utilization))} utilization, {_rate(float(row.coverage_rate))} coverage."
        for row in results.loc[results["window_type"] == "trailing"].itertuples(index=False)
    ) or "- none"
    anchored_lines = "\n".join(
        f"- {row.start_period} to {row.end_period}: {_money(float(row.commitment_per_hour))}/hour, {_money(float(row.total_savings_dollars))} savings."
        for row in results.loc[results["window_type"] == "anchored"].itertuples(index=False)
    ) or "- none"
    top_jump = metrics["regime_change"]
    regime_line = "- No monthly regime jump detected in valid compute spend."
    if top_jump:
        regime_line = (
            f"- Largest month-over-month discounted-spend move: {top_jump['billing_period']} at {_money(float(top_jump['discounted_cost_change']))} "
            f"({_rate(top_jump.get('discounted_cost_change_pct'))})."
        )
    return {
        "summary.md": f"""
# Challenge 3 Summary

Recommended sizing rule: {headline['recommended_window_rule']}

## Headline

- Recommended commitment: {_money(float(headline['recommended_commitment_per_hour']))}/hour discounted spend
- Recommended source window: {headline['recommended_window_label']}
- Best hindsight window in the sweep: {best['window_label']} at {_money(float(best['commitment_per_hour']))}/hour and {_money(float(best['total_savings_dollars']))} savings
- Window count evaluated: {headline['window_count']}
- Spread between lowest and highest optimum: {_money(float(headline['optimal_commitment_spread_per_hour']))}/hour

## Sensitivity Results

### Trailing windows

{trailing_lines}

### Anchored 3-month windows

{anchored_lines}

## Interpretation

{recommendation['reason']}

## Regime Change Review

{regime_line}

## Anomaly Review Note

{_anomaly_note(results, regime)}

## Assumptions And Risks

- All windows reuse the verified Challenge 2 Compute Savings Plan optimizer and pricing view.
- Anchored windows are fixed at 3 months so they are directly comparable to the default Challenge 2 policy.
- This is still hindsight on observed history; a forward buy should be capped by business downside tolerance, not just the highest backtested savings point.
""",
        "methodology.md": f"""
# Challenge 3 Methodology

## Window Set

- Trailing windows: 1, 2, 3, and 6 complete months when available.
- Anchored windows: every 3-complete-month slice across the available history.

## Steps

1. Load the shared compute-eligible non-Spot optimizer input used in Challenge 2.
2. Rebuild hourly candidate arrays for each evaluation window.
3. Re-run the exact breakpoint optimizer for every window.
4. Record optimal commitment, net savings, utilization, coverage, and eligible spend totals.
5. Aggregate monthly compute-eligible discounted spend to show where the history changes regime.
6. Recommend a window rule that favors forward safety when recent and broad windows disagree.

## Validation Notes

- Warnings: {', '.join(metrics['warnings']) if metrics['warnings'] else 'none'}.
- Only complete billing periods are eligible for window construction.
- The anomaly review is embedded in `summary.md`, not split into a separate challenge.
""",
        "understanding_ledger.md": """
# Understanding Ledger

## What I Verified Myself

- Verified Challenge 3 only changes the history window; the hourly optimizer mechanics stay the same as Challenge 2.
- Verified trailing and anchored windows use complete billing periods only.
- Verified the recommendation rule is explicit about regime-change risk instead of blindly picking the biggest hindsight result.

## What I Delegated And Trusted

- Trusted the repeated breakpoint sweeps once the Challenge 2 allocation logic and tests passed.
- Trusted matplotlib rendering and CSV export after checking the headline values in `metrics.json` and `tables/window_sensitivity.csv`.

## What I'm Unsure Of

- Whether the future will look more like the most recent 3 months or the broader 6-month history if the account is mid-migration.
- Whether a different anchored window length would better reflect the business planning cadence.
""",
    }
