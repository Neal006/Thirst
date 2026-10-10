# Thirst

[![CI](https://github.com/Neal006/Thirst/actions/workflows/ci.yml/badge.svg)](https://github.com/Neal006/Thirst/actions/workflows/ci.yml)

Thirst tells you when and how fast to run a GPU job so it takes less water from a stressed city and puts
less CO₂ in the air. It proves the result with a measured "water receipt", and turns receipts into a fair
rating where a 4-GPU college lab can beat a big company's lab.

Environmental Hacks (WeMakeDevs x AWS) · Track 02: Heat and Water · India.

> Status: foundations only. The engine, CLI, backend and web app are built phase by phase from
> [`docs/implementation-plan/`](docs/implementation-plan/README.md).

## Read first

| Doc | What it answers |
|---|---|
| [`Idea.md`](Idea.md) | Why: the problem, the science, the Thirst Score |
| [`prd.md`](prd.md) | What: users, stories, features, metrics |
| [`trd.md`](trd.md) | How: architecture, engine formulas, API, tests |
| [`docs/implementation-plan/`](docs/implementation-plan/README.md) | Step-by-step build plan |
| [`AGENTS.md`](AGENTS.md) | Project memory for people and AI coding tools |

## Develop

Python 3.12, Node 22.12 or newer.

```bash
uv venv --python 3.12 .venv            # or: python -m venv .venv
uv pip install -e ".[dev]" -e ./cli    # or: pip install -e ".[dev]" -e ./cli
make check                             # lint, types, tests, coverage
python scripts/check_skeleton.py       # repo layout sanity check
```

Without `make` (plain Windows), run the commands in the [`Makefile`](Makefile) directly.

## Licence

MIT. See [`LICENSE`](LICENSE). Data sources and their licences are listed in
[`ASSUMPTIONS.md`](ASSUMPTIONS.md).
