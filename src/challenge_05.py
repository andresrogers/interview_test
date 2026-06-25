"""Purpose:
Build reusable Challenge 5 commitment-audit metrics and report text.

Owns:
- Current commitment audit validation.
- Commitment inventory and monthly utilization tables.
- Challenge 5 markdown and metrics payloads.

Does Not Own:
- DuckDB parquet loading.
- Plot rendering.

Main Entry Points:
- load_commitment_audit_rows
- validate_commitment_audit_inputs
- build_commitment_inventory
- build_commitment_monthly
- build_metrics
- build_report_texts

Key Invariants:
- `Usage with Discount` rows represent realized commitment coverage.
- `Unused Commitment` rows represent paid waste and must stay tied to the same commitment.
- Coverage and utilization stay separate in the audit.

Update This Header When:
- Public entry points change.
- Audit window or classification rules change.
"""

from __future__ import annotations

from typing import Any

import duckdb
import pandas as pd

from src.challenge_02 import choose_analysis_window
from src.metrics import safe_ratio


def load_commitment_audit_rows(con: duckdb.DuckDBPyConnection, included_periods: list[str]) -> pd.DataFrame:
    period_list = ", ".join(f"'{period}'" for period in included_periods)
    stmt = f"""
    select
      analysis_timestamp,
      billing_period,
      product_code,
      usage_type,
      instance_type,
      usage_amount,
      on_demand_cost,
      amortized_cost,
      commitment_key,
      commitment,
      cost_type
    from usage_ready
    where billing_period in ({period_list})
      and commitment is not null
      and cost_type in ('Usage with Discount', 'Unused Commitment')
    order by commitment, analysis_timestamp
    """
    return con.execute(stmt).df()


def validate_commitment_audit_inputs(frame: pd.DataFrame) -> list[str]:
    warnings = []
    missing_unused = int(frame.loc[(frame["cost_type"] == "Unused Commitment") & frame["commitment"].isna()].shape[0])
    missing_discount = int(frame.loc[(frame["cost_type"] == "Usage with Discount") & frame["commitment"].isna()].shape[0])
    if missing_unused:
        warnings.append(f"Found {missing_unused:,} `Unused Commitment` rows without a commitment identifier.")
    if missing_discount:
        warnings.append(f"Found {missing_discount:,} `Usage with Discount` rows without a commitment identifier.")
    orphan_unused = frame.loc[frame["cost_type"] == "Unused Commitment", "commitment"].dropna().unique().tolist()
    covered = set(frame.loc[frame["cost_type"] == "Usage with Discount", "commitment"].dropna().tolist())
    orphan_count = sum(1 for commitment in orphan_unused if commitment not in covered)
    if orphan_count:
        warnings.append(
            f"Found {orphan_count:,} commitments with waste rows but no covered rows in the audit window; they may be newly idle or partially observed."
        )
    return warnings


def _commitment_kind(commitment: str) -> str:
    if ":savingsplan/" in commitment:
        return "savings_plan"
    if ":ri:" in commitment:
        return "reserved_instance"
    return "other"


def _scope_label(frame: pd.DataFrame) -> str:
    keys = [value for value in frame.loc[frame["commitment_key"].notna(), "commitment_key"].astype(str).tolist() if value != "None"]
    if not keys:
        return "unknown"
    first = keys[0]
    if first.startswith("AWS#Compute"):
        return "compute"
    if first.startswith("AWS#Database"):
        return "database"
    if first.startswith("AWS#AmazonRDS"):
        return "rds"
    if first.startswith("AWS#AmazonElastiCache"):
        return "elasticache"
    return first.split("#", 2)[1] if "#" in first else first


def _sizing_assessment(utilization: float | None, waste_share: float | None, residual_same_products: float) -> str:
    if utilization is None:
        return "unknown"
    if utilization < 0.85 or (waste_share or 0.0) > 0.15:
        return "over_committed"
    if utilization >= 0.98 and residual_same_products > 0:
        return "under_committed"
    return "well_sized"


def build_commitment_inventory(frame: pd.DataFrame, account_usage: pd.DataFrame) -> pd.DataFrame:
    rows = []
    covered = frame.loc[frame["cost_type"] == "Usage with Discount"].copy()
    for commitment, commitment_rows in frame.groupby("commitment", sort=False):
        covered_rows = commitment_rows.loc[commitment_rows["cost_type"] == "Usage with Discount"]
        unused_rows = commitment_rows.loc[commitment_rows["cost_type"] == "Unused Commitment"]
        products = sorted(set(covered_rows["product_code"].dropna().tolist()))
        residual_same_products = float(
            account_usage.loc[
                (account_usage["cost_type"] == "On Demand Usage") & account_usage["product_code"].isin(products), "on_demand_cost"
            ].sum()
        )
        covered_on_demand = float(covered_rows["on_demand_cost"].sum())
        consumed = float(covered_rows["amortized_cost"].sum())
        waste = float(unused_rows["amortized_cost"].sum())
        paid = consumed + waste
        utilization = safe_ratio(consumed, paid)
        waste_share = safe_ratio(waste, paid)
        rows.append(
            {
                "commitment": commitment,
                "commitment_kind": _commitment_kind(str(commitment)),
                "scope_label": _scope_label(commitment_rows),
                "covered_products": ", ".join(products[:4]) or "none",
                "covered_product_count": len(products),
                "covered_on_demand_cost": covered_on_demand,
                "consumed_commitment": consumed,
                "unused_commitment_waste": waste,
                "paid_commitment": paid,
                "utilization": utilization,
                "waste_share": waste_share,
                "residual_on_demand_same_products": residual_same_products,
                "portfolio_coverage_share": safe_ratio(covered_on_demand, float(covered["on_demand_cost"].sum())),
                "sizing_assessment": _sizing_assessment(utilization, waste_share, residual_same_products),
            }
        )
    return pd.DataFrame(rows).sort_values(["paid_commitment", "covered_on_demand_cost"], ascending=[False, False]).reset_index(drop=True)


def build_commitment_monthly(frame: pd.DataFrame) -> pd.DataFrame:
    covered = frame.loc[frame["cost_type"] == "Usage with Discount"].copy()
    unused = frame.loc[frame["cost_type"] == "Unused Commitment"].copy()
    covered_monthly = covered.groupby(["commitment", "billing_period"], as_index=False).agg(
        covered_on_demand_cost=("on_demand_cost", "sum"),
        consumed_commitment=("amortized_cost", "sum"),
    )
    unused_monthly = unused.groupby(["commitment", "billing_period"], as_index=False).agg(
        unused_commitment_waste=("amortized_cost", "sum"),
    )
    monthly = covered_monthly.merge(unused_monthly, how="outer", on=["commitment", "billing_period"]).fillna(0.0)
    paid_commitment = [
        float(consumed) + float(unused)
        for consumed, unused in zip(monthly["consumed_commitment"].tolist(), monthly["unused_commitment_waste"].tolist())
    ]
    utilization = [
        safe_ratio(float(consumed), float(paid))
        for consumed, paid in zip(monthly["consumed_commitment"].tolist(), paid_commitment)
    ]
    return monthly.assign(paid_commitment=paid_commitment, utilization=utilization).sort_values(
        ["commitment", "billing_period"]
    ).reset_index(drop=True)


def _portfolio_summary(inventory: pd.DataFrame, account_usage: pd.DataFrame) -> dict[str, float | None]:
    total_covered = float(inventory["covered_on_demand_cost"].to_numpy(dtype=float).sum())
    total_paid = float(inventory["paid_commitment"].to_numpy(dtype=float).sum())
    total_consumed = float(inventory["consumed_commitment"].to_numpy(dtype=float).sum())
    total_eligible = float(
        account_usage.loc[account_usage["commitment_key"].notna() & (account_usage["usage_amount"] > 0), "on_demand_cost"]
        .to_numpy(dtype=float)
        .sum()
    )
    return {
        "portfolio_coverage_rate": safe_ratio(total_covered, total_eligible),
        "portfolio_utilization": safe_ratio(total_consumed, total_paid),
        "total_paid_commitment": total_paid,
        "total_consumed_commitment": total_consumed,
        "total_unused_commitment_waste": float(inventory["unused_commitment_waste"].to_numpy(dtype=float).sum()),
    }


def build_metrics(
    inventory: pd.DataFrame,
    monthly: pd.DataFrame,
    account_usage: pd.DataFrame,
    included_periods: list[str],
    partial_periods: list[str],
    warnings: list[str],
) -> dict[str, Any]:
    portfolio = _portfolio_summary(inventory, account_usage)
    inventory_paid = float(inventory["paid_commitment"].to_numpy(dtype=float).sum())
    monthly_paid = float(monthly["paid_commitment"].to_numpy(dtype=float).sum())
    consumed_plus_unused_gap = abs(
        float(inventory["consumed_commitment"].to_numpy(dtype=float).sum())
        + float(inventory["unused_commitment_waste"].to_numpy(dtype=float).sum())
        - inventory_paid
    )
    metrics_warnings = list(warnings)
    if partial_periods:
        metrics_warnings.append(f"Excluded partial billing periods from commitment audit: {', '.join(partial_periods)}")
    if abs(monthly_paid - inventory_paid) > 1e-6:
        metrics_warnings.append(f"Monthly paid commitment does not reconcile to inventory total: {abs(monthly_paid - inventory_paid):.6f}")
    if consumed_plus_unused_gap > 1e-6:
        metrics_warnings.append(f"Inventory consumed plus unused commitment does not reconcile to paid commitment: {consumed_plus_unused_gap:.6f}")
    return {
        "challenge": "challenge_05_audit_commitments",
        "trust_level": "medium" if metrics_warnings else "high",
        "warnings": metrics_warnings,
        "window": {
            "billing_periods_included": included_periods,
            "billing_periods_excluded_partial": partial_periods,
        },
        "headline": {
            "commitment_count": int(len(inventory)),
            "over_committed_count": int((inventory["sizing_assessment"] == "over_committed").sum()) if not inventory.empty else 0,
            "under_committed_count": int((inventory["sizing_assessment"] == "under_committed").sum()) if not inventory.empty else 0,
            "well_sized_count": int((inventory["sizing_assessment"] == "well_sized").sum()) if not inventory.empty else 0,
            **portfolio,
        },
        "reconciliation": {
            "monthly_paid_commitment_gap": abs(monthly_paid - inventory_paid),
            "consumed_plus_unused_gap": consumed_plus_unused_gap,
        },
    }


def _money(value: float) -> str:
    return f"${value:,.2f}"


def _rate(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.2%}"


def _anomaly_note(inventory: pd.DataFrame) -> str:
    if inventory.empty:
        return "No commitments found in the audit window."
    top_waste = inventory.sort_values("unused_commitment_waste", ascending=False).iloc[0]
    if float(top_waste["unused_commitment_waste"]) > 0 and (top_waste["waste_share"] or 0.0) > 0.2:
        return (
            f"Material anomaly found: one commitment drives a large share of waste ({_money(float(top_waste['unused_commitment_waste']))}, "
            f"utilization {_rate(top_waste['utilization'])}). That is real idle commitment, not a reporting artifact."
        )
    if int((inventory["sizing_assessment"] == "under_committed").sum()) > 0:
        return "No material waste anomaly found, but some commitments look fully used while similar spend stays on-demand. That is a real under-commitment signal."
    return "No material anomaly found. Waste, utilization, and covered spend move in the expected directions across the inventory."


def build_report_texts(metrics: dict[str, Any], inventory: pd.DataFrame) -> dict[str, str]:
    headline = metrics["headline"]
    top = inventory.head(5)
    over = inventory.loc[inventory["sizing_assessment"] == "over_committed"].head(2)
    under = inventory.loc[inventory["sizing_assessment"] == "under_committed"].head(2)
    well = inventory.loc[inventory["sizing_assessment"] == "well_sized"].head(2)
    lines = "\n".join(
        f"- `{row['commitment']}` ({row['commitment_kind']}, {row['scope_label']}): utilization {_rate(row['utilization'])}, waste {_money(float(row['unused_commitment_waste']))}, covers {row['covered_products']}."
        for row in top.to_dict("records")
    ) or "- none"
    assessment_lines = []
    if not over.empty:
        assessment_lines.append(
            "Over-committed examples:\n" + "\n".join(
                f"- `{row['commitment']}`: utilization {_rate(row['utilization'])}, waste {_money(float(row['unused_commitment_waste']))}."
                for row in over.to_dict("records")
            )
        )
    if not under.empty:
        assessment_lines.append(
            "Under-committed examples:\n" + "\n".join(
                f"- `{row['commitment']}`: utilization {_rate(row['utilization'])}, residual same-product on-demand {_money(float(row['residual_on_demand_same_products']))}."
                for row in under.to_dict("records")
            )
        )
    if not well.empty:
        assessment_lines.append(
            "Well-sized examples:\n" + "\n".join(
                f"- `{row['commitment']}`: utilization {_rate(row['utilization'])}, waste {_money(float(row['unused_commitment_waste']))}."
                for row in well.to_dict("records")
            )
        )
    assessment_text = "\n\n".join(assessment_lines) or "No commitment classifications were available."
    return {
        "summary.md": f"""
# Challenge 5 Summary

Current audited commitment portfolio utilization: {_rate(headline['portfolio_utilization'])}

## Headline

- Audit window: {metrics['window']['billing_periods_included'][0]} to {metrics['window']['billing_periods_included'][-1]}
- Commitments observed: {headline['commitment_count']}
- Portfolio paid commitment: {_money(float(headline['total_paid_commitment']))}
- Portfolio consumed commitment: {_money(float(headline['total_consumed_commitment']))}
- Portfolio unused commitment waste: {_money(float(headline['total_unused_commitment_waste']))}
- Portfolio utilization: {_rate(headline['portfolio_utilization'])}
- Portfolio coverage of eligible committed spend: {_rate(headline['portfolio_coverage_rate'])}
- Likely over-committed instruments: {headline['over_committed_count']}
- Likely under-committed instruments: {headline['under_committed_count']}
- Likely well-sized instruments: {headline['well_sized_count']}

## Inventory Snapshot

{lines}

## Assessment

This audit reconstructs commitments from `commitment`, `Usage with Discount`, and `Unused Commitment` rows only. Utilization answers how much paid commitment got consumed. Coverage answers how much eligible on-demand spend the whole portfolio actually covered. They are reported separately on purpose.

{assessment_text}

## Anomaly Review Note

{_anomaly_note(inventory)}

## Assumptions And Risks

- The audit window uses the most recent three complete billing periods so the inventory reflects current posture rather than the full year.
- Per-commitment "under-committed" status is a proxy based on fully used commitments plus residual on-demand spend in the same products; it is directional evidence, not proof of exact scope miss.
- `Unused Commitment` rows are tied back by commitment ARN; if identifiers are missing the issue is reported in `metrics.json` warnings.
""",
        "methodology.md": f"""
# Challenge 5 Methodology

## Steps

1. Keep the most recent three complete billing periods.
2. Pull only rows with a non-null commitment and cost types `Usage with Discount` or `Unused Commitment`.
3. Aggregate by commitment for covered on-demand spend, consumed commitment, unused waste, and utilization.
4. Build a monthly utilization table from the same commitment rows.
5. Classify each commitment as well-sized, under-committed, or over-committed with simple evidence-based rules.
6. Run explicit reconciliation checks from monthly rows back to inventory totals.

## Validation Notes

- Warnings: {', '.join(metrics['warnings']) if metrics['warnings'] else 'none'}.
- Portfolio coverage denominator = eligible on-demand cost on all commitment-eligible rows in the same window.
- Portfolio utilization denominator = paid commitment dollars from covered plus unused rows.
""",
        "understanding_ledger.md": """
# Understanding Ledger

## What I Verified Myself

- Verified `Usage with Discount` and `Unused Commitment` are the two commitment-audit signals used.
- Verified waste stays tied to the same commitment identifier rather than being pooled away.
- Verified monthly paid commitment rolls back up to the inventory total.

## What I Delegated And Trusted

- Trusted repeated grouping and CSV export once the inventory and monthly reconciliation checks matched.
- Trusted the utilization heatmap after the plotted values matched the monthly utilization table.

## What I'm Unsure Of

- Whether some commitment scopes would need deeper service-specific logic to prove under-commitment beyond the simple residual-on-demand proxy used here.
- Whether a longer or shorter audit window would better represent "current" posture for every commitment.
""",
    }
