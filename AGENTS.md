# AGENTS.md — Project Memory (auto-maintained)
Last updated: 2026-10-09 | Sessions logged: 2

## Identity
Thirst: a water and carbon planner, receipt and rating for GPU jobs in India (WeMakeDevs x AWS Environmental Hacks, Track 02).
Users: students and lab heads in college GPU labs, startups on rented GPUs. Built by team hello_world.

## Stack & Commands
- Engine and handlers: Python 3.12, pure-Python engine (no numpy), pytest + hypothesis, ruff, mypy (strict, `src/` only).
- CLI: Python ≥ 3.10, nvidia-ml-py, httpx; `thirst` entry point (stub today).
- Web: Vite + React 19 + TypeScript + Recharts + Vitest, Node 22.12+ (`web/`; lint is oxlint; vitest 5 and jest-dom 7 need Node 22).
- AWS: SAM CLI, `ap-south-1`, profile `thirst`, stack `thirst-dev`; `template.yaml` arrives in step 05.1.
- Setup: `uv venv --python 3.12 .venv && uv pip install --python .venv -e ".[dev]" -e ./cli && npm --prefix web ci`.
- Checks (same as CI): `make check` = `ruff check .` + `mypy` + `pytest -m "not gpu and not aws" --cov` (+ `make cov-engine` once engine tests exist).
  Without make (Windows): run `.venv/Scripts/python.exe -m ruff check .`, `-m mypy`, `-m pytest …`, and `npm --prefix web test -- --run | run lint | run build`.
- Skeleton sanity: `python scripts/check_skeleton.py`.

## Current State & Focus
- Phase 01 (foundations), local part DONE: repo hygiene, skeleton (stubs only), Python and Node tooling, CI workflow, offline forecast data. 29 Python tests and 1 web test green.
- Phase 01 still needs people: AWS account/SAM/Docker/budgets/Bedrock/SSM secret (1.6), CSEP/Ember/Aqueduct data (1.7.b–f), GPU box checks (1.8), team registration and deadline (1.9). CI (python, web, sam, secrets) passed on draft PR #1; the Makefile ran green on ubuntu.
- Next: Phase 02 engine (B), Phase 05 backend (A) and Phase 06 frontend (C) in parallel.
- Code freeze Sun 11 Oct 11:00 IST; submit Sun 14:00 to 16:00 IST. The exact deadline time is still to be checked on the schedule page.

## Architecture
CLI (NVML meter, power cap, pause/resume) → HMAC-signed receipts → API Gateway HTTP API → Lambda `api` (engine) → DynamoDB (weather, sites, plans, receipts).
EventBridge Scheduler (hourly) → Lambda `refresh` → Open-Meteo → weather table.
Browser → Amplify (React) → `/plan`, `/sites`, `/leaderboard`, `/assumptions`; optional Lambda `explain` (Strands + Bedrock, template fallback).
The engine is pure Python with no AWS imports; the solver decides and the AI only explains.

## File Map
- `Idea.md` — why: problem, science, Thirst Score spec v0.2, sources (renamed from `Idea_1.md`, D1)
- `pyproject.toml`, `Makefile`, `.github/workflows/ci.yml` — Python tooling, task runner, CI (python, web, sam, secrets jobs)
- `src/engine/` — pure-Python engine; module stubs today, each filled by its plan step (02.x); `data/sample_forecast.json` = offline weather fallback
- `src/handlers/` — Lambda handlers (stubs; plan 05.x); `cli/thirst/` — CLI package (stubs; plan 04.x) with its own `cli/pyproject.toml`
- `web/` — Vite React TS app (placeholder `App.tsx`, Vitest set up in `vite.config.ts`, `.env.example`)
- `scripts/check_skeleton.py` — asserts the repo layout from plan 1.2; other `scripts/*.py` are stubs
- `prd.md` — what: goals, personas, US1–US12, F1–F14, metrics, video plan
- `trd.md` — how: architecture, engine formulas, CLI, API, data model, tests, schedule
- `docs/implementation-plan/README.md` — plan index: gates, critical path, decisions D1–D26, load balancing, two-person mode, traceability, DoD
- `docs/implementation-plan/01..07-*.md` — step-by-step plan per phase (foundations, engine, Step 0, CLI, backend, frontend, QA and release)
- `docs/implementation-plan/08-reference-contracts.md` — data file schemas, API contract, error codes, DynamoDB items, HMAC vectors

## Conventions
- Units are in names (`_kwh`, `_l`, `_kg`, `_pct`); IST-aware datetimes only; one-hour slots.
- Every user-facing number has a tag (measured, modelled, placeholder, sourced, calibrated) and an Assumptions link.
- Savings are always ranges (low, central, high factor sets), never single numbers.
- Frozen dataclasses and no mutation; new constants go in `factors.json` with source and status.
- TDD: tests first. Engine coverage ≥ 90%, CLI and handlers ≥ 80%.
- Conventional commits, commit every 1 to 2 h, trunk-based with short branches and CI green (D18).

## Dependencies & Gotchas
- Never create: EC2 GPU, SageMaker endpoints, OpenSearch, NAT Gateway, RDS/Aurora, provisioned concurrency (TRD §12).
- Budgets $10/$25/$50, plus a $5 alarm line by Sat 21:00 (D4).
- SAM `CodeUri: src/` does not ship root `data/`; runtime JSON lives in `src/engine/data/` (D6).
- HTTP API may base64-encode the body; verify the HMAC over the decoded raw bytes (D21).
- `sam build --use-container` is needed on Windows for correct arm64 wheels.
- SIGSTOP/killpg are POSIX only; the CLI forces non-pausable on Windows and for distributed launchers (D15).
- A stopped (SIGSTOP) process must get SIGCONT before SIGTERM, or it can't exit.
- DynamoDB needs Decimal, not float; NaN and Inf are rejected.
- The power limit resets on reboot or driver reload; the restore marker is `~/.thirst/restore.json`.
- (Windows dev box of the first session only) no `make`, `sam` or Docker installed: run Makefile commands by hand. `sam build --use-container` needs Docker Desktop everywhere.
- Ruff targets py312 for the repo but `cli/ruff.toml` pins py310 for the CLI (lab machines); mypy checks `src/` only.
- pytest runs with `--import-mode=importlib` and `pythonpath = src, cli, scripts`; tests import `engine`, `handlers`, `thirst`, `check_skeleton` directly.
- `create-vite` ignores `--template` when called through `npm create … -- --template` in PowerShell: use `npx create-vite@latest web --template react-ts --no-interactive`.
- The CI `web` job needs `web/package-lock.json` committed; the `sam` job is a no-op until `template.yaml` exists.
- Repo was renamed `thrist` → `Thirst` on GitHub (D2 done); old URLs redirect. Still private until submission (D3).

## Decisions Log
- 2026-10-09 — Repo created private as `thrist`, renamed on GitHub to `Thirst` (D2 done); make it public at submission — D3
- 2026-10-09 — Web needs Node 22.12+ (CI uses 22) — the lockfile's vitest 5, jest-dom 7 and jsdom 29 require it
- 2026-10-09 — Plan-level decisions D1–D26 recorded in `docs/implementation-plan/README.md` §5 — resolve gaps in the PRD and TRD before build

## Changelog
- 2026-10-09 | Phase 01 foundations (local part) | LICENSE, .gitignore, .editorconfig, .gitattributes, Makefile, pyproject.toml, cli/pyproject.toml, .github/workflows/ci.yml, src/**, cli/**, scripts/check_skeleton.py, web/**, tests/test_smoke.py, README.md, docs/FIXLIST.md | stubs-only skeleton checked by script; Idea_1.md→Idea.md (D1); engine kept free of AWS imports by test
- 2026-10-09 | Detailed implementation plan | AGENTS.md, docs/implementation-plan/* | phase files + contracts; ECC architect/planner review folded in
- 2026-10-09 | Create private repo, add Idea/PRD/TRD | Idea_1.md, prd.md, trd.md | docs-only initial commit

## Archived Summary
(none yet)
