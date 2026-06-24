# Working in this repository (for agents)

This repository is a set of **cloud-cost analysis challenges** for candidates. If
you are an agent helping someone work through it, orient yourself here.

**Start with [`README.md`](README.md)** — it covers environment setup (`uv`), where
the dataset lives (`output/`), and links to everything below. Run code through the
environment with `uv run …`.

Key references:

- [`docs/challenges/README.md`](docs/challenges/README.md) — the challenges, a suggested order, and how the set is meant to be approached.
- [`docs/data_dictionary.md`](docs/data_dictionary.md) — every column in the dataset and the pricing table.
- [`docs/aws_discount_cheatsheet.md`](docs/aws_discount_cheatsheet.md) — the AWS commitment-discount rules the problems turn on.
- [`docs/understanding_debt.md`](docs/understanding_debt.md) and [`docs/understanding_ledger.md`](docs/understanding_ledger.md) — what the work is evaluated on. Read these.
- [`notebooks/demo.ipynb`](notebooks/demo.ipynb) — a runnable starter (loads the data, joins usage to pricing, plots).
