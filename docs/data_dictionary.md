# Data Dictionary

This describes the data shipped with the challenges: an anonymized hourly cost &
usage dataset and a Savings-Plan pricing reference. The data is **anonymized real
data** — identifiers are obfuscated, but the shapes, distributions, and
relationships are genuine. The dataset spans multiple linked AWS accounts under a
single organization, and the most recent `billing_period` may be **partial** —
check before treating it as a complete month.

---

## `output/candidate_dataset.parquet` — hourly cost & usage

**Grain:** one row per hour per usage line. A "usage line" is a distinct
combination of the dimension columns below; the measures are summed within that
combination for the hour.

| Column | Type | Definition |
|---|---|---|
| `timestamp` | timestamp | Start of the hour (UTC) in which the usage was metered. The dataset's grain is hourly. |
| `billing_period` | string | The AWS monthly billing period the row belongs to, `YYYY-MM`. |
| `product_code` | string | AWS service code that emitted the usage (e.g. `AmazonEC2`, `AmazonECS` for Fargate, `AWSLambda`, `AmazonRDS`). |
| `usage_type` | string | AWS usage-type string for the metered dimension, region-prefixed (e.g. `EUC1-Fargate-vCPU-Hours:perCPU`, `BoxUsage:m5.xlarge`). The prefix (`EUC1`, `USE1`, …) encodes the AWS region. |
| `instance_type` | string (nullable) | Instance/resource type for instance-based usage (e.g. `m5.xlarge`, `r7g.xlarge.search`). Null for usage with no instance dimension (data transfer, requests, etc.). |
| `usage_amount` | double | Quantity of usage in the native unit implied by `usage_type` (vCPU-hours, instance-hours, GB-hours, requests, …). |
| `on_demand_cost` | double | Cost of this usage at public AWS **on-demand** rates — what it would cost with no commitment or discount. The on-demand unit rate is `on_demand_cost / usage_amount`. |
| `amortized_cost` | double | Cost actually attributed to this usage given the account's **existing** commitments/discounts (e.g. Savings Plan / RI amortization spread across covered usage). Differs from `on_demand_cost` wherever an existing commitment applied.
| `price_list_key` | string | The join key into the pricing reference (`pricing_options_filtered`). Its internal structure isn't important; what matters is that it is precise enough to identify the **exact grain at which AWS publishes its price list**, so each usage line maps to the correct published rate. |
| `commitment_key` | string | A **hierarchical** key describing the commitment scope of this usage. If a commitment instrument's scope is a **prefix** of this key, the spend on this row is covered by that instrument — e.g. a Compute Savings Plan (scope `AWS#Compute`) covers any row whose `commitment_key` starts with `AWS#Compute`, and a Database Savings Plan (scope `AWS#Database`) covers any row starting with `AWS#Database` — including serverless databases, which Reserved Instances cannot cover. `None` when the usage is not commitment-eligible. |
| `account_id` | string | The AWS account that incurred the usage. **Anonymized**: a stable, non-reversible 12-digit hash — consistent across rows, but not the real account id. |
| `commitment` | string (nullable) | The commitment (Savings Plan or Reserved Instance) that covered this usage, as an ARN; null/`None` when the usage was on-demand. **Anonymized**: the account segment and commitment id are hashed consistently, so you can tell which usage shared a commitment without seeing the real ARN. |
| `cost_type` | string | How this usage was billed: `On Demand Usage` (uncovered, on-demand rates), `Usage with Discount` (covered by an existing commitment — pairs with a non-null `commitment`), `Unused Commitment` (committed capacity that went unused), and similar. Distinguishes plain usage from discounted usage and gives the `commitment` column its meaning.
| `baseline_covered` | double (nullable) | The portion of this row's **on-demand cost** that a *baseline-level* commitment would cover. Baselines are computed per **collapsed commitment key** (defined below) as an hourly time series, then spread back across that scope's usage **each hour in order of decreasing discount**. A non-zero value is the dollars of this row's on-demand cost that fall under the baseline commitment; null where no baseline applies (not commitment-eligible). |
| `baseline_max` | double (nullable) | **A level, not a per-row metric.** The baseline commitment level applied to this row's collapsed-commitment scope: the "max-ish" commitment at which that instrument would be (just) fully consumed *given the usage observed up to that point* — it reflects history, not a forward guarantee. It is identical for every row sharing the same scope and hour — read it, don't sum it. For a compute row it is the full baseline commitment level for that compute scope. |

### Collapsed commitment key

The scope a baseline is computed at, derived from `commitment_key`. A broad
Savings Plan covers an entire top-level prefix, so any `commitment_key` beginning
`AWS#Compute`, `AWS#Database`, or `AWS#Sagemaker` collapses to **just that prefix**
(one of those three values) — there is one such broad SP per prefix. Spend not
covered by a broad SP instead collapses to the finer scope at which a **Reserved
Instance** would cover it.

So the collapsed commitment key is **single-valued** across each broad-SP scope
(all `AWS#Compute` spend shares one key, etc.) and otherwise carries the
cardinality of the covering RI's scope. Baselines (`baseline_covered` /
`baseline_max`) are computed once per collapsed commitment key.

---

## `output/pricing_options_filtered.parquet` — commitment pricing reference

The Savings-Plan / Reserved-Instance rate table, filtered to the instances and
regions that appear in the dataset (a small slice of the full catalog). Use it to
find the **discounted** rate for a kind of usage; the **discount** for any usage
line is `1 − (discounted_rate / on_demand_rate)`, where the on-demand rate comes
from the usage dataset.

**Join:** the usage dataset's `price_list_key` matches this table's
`price_list_key`.

| Column | Type | Definition |
|---|---|---|
| `price_list_key` | string | The price-list key the rate applies to, at AWS's published price-list grain. Joins name-for-name to the usage dataset's `price_list_key`. |
| `instrument_type` | string | The commitment instrument: `compute_savings_plan`, `ec2_savings_plan`, `ec2_reserved_instance`, `rds_reserved_instance`, … |
| `offering_class` | string | `savings_plan`, or `standard` / `convertible` for Reserved Instances. |
| `term_months` | int | Commitment term — `12` or `36`. |
| `payment_option` | string | `no_upfront`, `partial_upfront`, or `all_upfront`. |
| `rate` | double | The committed (discounted) rate for one `unit` of usage under this instrument / term / payment. |
| `unit` | string | Unit the `rate` is expressed in (e.g. `Hrs`). |
| `currency` | string | Currency of `rate` (e.g. `USD`). |

---

## Deriving rates and discounts

- **On-demand unit rate** (from the usage dataset): `on_demand_cost / usage_amount` for a given `usage_type`.
- **Discounted unit rate** (from the pricing reference): the `rate` on the row whose `price_list_key` equals the usage line's `price_list_key` (then choose the instrument / term / payment you're evaluating).
- **Discount** for a usage line: `1 − (discounted_rate / on_demand_rate)`.

The pricing table has **several rows per `price_list_key`** — one per
`instrument_type` × `term_months` × `payment_option` × `offering_class` — so a
join must pin those dimensions to land on a single rate (e.g. a 3-year
`compute_savings_plan`), or it will fan out.

**Not every instrument exists for every `price_list_key`.** The table only carries
rows for instruments that can actually cover that usage — so a serverless-database
key has `database_savings_plan` rows but no Reserved-Instance rows. A missing
instrument means it **does not apply** to that usage, not that data is absent.

A runnable worked example of this join — plotting on-demand vs Savings-Plan-
discounted cost, and on-demand vs the `baseline_max` level — is in
[`notebooks/demo.ipynb`](../notebooks/demo.ipynb).
