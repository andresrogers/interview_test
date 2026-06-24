# Cloud Cost Challenges

A set of analysis challenges over a real (anonymized) AWS hourly cost-and-usage
dataset. You're expected to use AI agents heavily — see
[what we value](docs/understanding_debt.md) and the
[challenge overview](docs/challenges/README.md).

## The presentation matters as much as the analysis

Solving a challenge is only half the work. **Plan to spend roughly half your time
turning what you found into a clear visual narrative** — the figures and the story
that explain what you learned in the problem you solved and why it matters.

Your audience is our **Head of Product** — not a fellow engineer. Pitch your
findings at a level they can follow *without* the SQL or the modeling details, so
they can make one call: **do your discoveries warrant building into the product?**
Lead with the insight, show it with a visual, and make the "so what" unmistakable.
A sharp result you can't communicate to a non-technical decision-maker is not yet a
finding — the visuals and the narrative are where the work pays off.

## Quickstart

This project uses [`uv`](https://docs.astral.sh/uv/). From the repo root:

```sh
# 1. Install uv (skip if you already have it)
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. Build an isolated environment with all dependencies
uv sync

# 3. Launch Jupyter and open the starter notebook
uv run jupyter lab notebooks/demo.ipynb
```

`uv sync` creates a `.venv` with DuckDB, pandas, matplotlib, and JupyterLab
(pinned in `uv.lock`); `uv run …` executes a command inside it. To run a script
or a one-off, use `uv run python your_script.py`.

> **Setting up with an agent?** Paste the three commands above and ask it to get
> JupyterLab running and confirm `notebooks/demo.ipynb` executes top to bottom.

## The data

The dataset is **not distributed with this repository** — it is provided
separately. Place the files in the `output/` directory (where the notebooks and
queries expect them):

- `output/candidate_dataset.parquet` — hourly cost & usage
- `output/pricing_options_filtered.parquet` — commitment pricing

**Don't have the data?** Email **engineering@cloudcapital.co** to request a
pre-signed download link (valid for one week).

## Where to go

| | |
|---|---|
| [docs/challenges/](docs/challenges/README.md) | The challenges, a suggested order, and how the set is meant to be approached. |
| [docs/data_dictionary.md](docs/data_dictionary.md) | Every column in the dataset and the pricing table. |
| [docs/aws_discount_cheatsheet.md](docs/aws_discount_cheatsheet.md) | The AWS commitment-discount rules the problems turn on. |
| [docs/understanding_debt.md](docs/understanding_debt.md) | What we value — read this before you start. |
| [docs/understanding_ledger.md](docs/understanding_ledger.md) | The short ledger to submit with your work. |
| [notebooks/demo.ipynb](notebooks/demo.ipynb) | A runnable starter: loads the data, joins usage to pricing, and plots. |
