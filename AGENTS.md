# AGENTS.md — Project Memory (auto-maintained)
Last updated: 2026-10-09 | Sessions logged: 3

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
- Phase 02 (engine) DONE and reviewed (ECC code + Python reviewers, all CRITICAL/HIGH fixed): units, errors, wetbulb, factors, cooling, grid, forecast, footprint, planner, score, explain + `scripts/gen_fixtures.py`; engine coverage 99%, 317 tests, fixtures in `tests/fixtures/*_response.json` (a test fails when they go stale: run `make fixtures`).
- Engine data is still PLACEHOLDER where plan 1.7 is open: `cities.json` stress categories, `grid_shares.json` national mix, `powercap_sweep.json` (empty, so tau/eps use the placeholders and every plan tags `tau: placeholder`).
- Next: Phase 05 backend (A) and Phase 06 frontend (C) can start from the fixtures; Phase 04 CLI needs the GPU box.
- Code freeze Sun 11 Oct 11:00 IST; submit Sun 14:00 to 16:00 IST. The exact deadline time is still to be checked on the schedule page.

## Architecture
CLI (NVML meter, power cap, pause/resume) → HMAC-signed receipts → API Gateway HTTP API → Lambda `api` (engine) → DynamoDB (weather, sites, plans, receipts).
EventBridge Scheduler (hourly) → Lambda `refresh` → Open-Meteo → weather table.
Browser → Amplify (React) → `/plan`, `/sites`, `/leaderboard`, `/assumptions`; optional Lambda `explain` (Strands + Bedrock, template fallback).
The engine is pure Python with no AWS imports; the solver decides and the AI only explains.

## File Map
- `Idea.md` — why: problem, science, Thirst Score spec v0.2, sources (renamed from `Idea_1.md`, D1)
- `pyproject.toml`, `Makefile`, `.github/workflows/ci.yml` — Python tooling, task runner, CI (python, web, sam, secrets jobs)
- `src/engine/units.py` — IST (fixed +05:30), `floor_hour`, `slot_starts`, `slot0_capacity`, `deadline_slots`; `errors.py` — `EngineError(code, message)`; `wetbulb.py` — `stull_tw`, `stull_tw_checked`
- `src/engine/factors.py` — `load_factors()` (cached) → `Factors` (`central/low/high()`, `gpu_params`, `stress_weight`, `table`), `load_gpus`, `load_cities`, `get_city`; `cooling.py` — `Cooling`, `pue`, `wue`, `cop`; `grid.py` — `load_grid`, `hourly_shares`, `ci`, `ewif`, `calibrate_coal_ef`
- `src/engine/forecast.py` — `WeatherRow`, `ForecastSnapshot` (to/from_json), `build_snapshot`, `intensities`, `load_sample_rows`; `footprint.py` — `footprint`, `coefficients`, `Totals`
- `src/engine/planner.py` — `PlanRequest`, `plan(req, snap, fx)`, `plan_from_rows`; returns base/best/pareto(11)/chosen/series/ranges (08 §3.1 plus `best`, `j_best`, `points`, per-entry `gpu_kwh`, `savings_central`)
- `src/engine/score.py` — `receipt_footprints`, `capture`, `site_score`, `badge`, `division`, `site_page_view`, `leaderboard_rows`; `explain.py` — `explain_template`
- `src/engine/data/` — `factors.json` (57 factors, status per row), `gpus.json` (13), `cities.json` (6), `grid_shares.json`, `powercap_sweep.json`, `sample_forecast.json` (96 h × 6 cities, matched by hour of day)
- `tests/weather_helpers.py` — synthetic weather and `request()` builder shared by engine tests; `scripts/gen_fixtures.py` — writes the three API fixtures
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
- pytest runs with `--import-mode=importlib` and `pythonpath = src, cli, scripts, tests`; tests import `engine`, `handlers`, `thirst`, `check_skeleton`, `gen_fixtures`, `weather_helpers` directly. Test modules cannot import each other: share helpers in `tests/weather_helpers.py`.
- IST is a fixed `timezone(+05:30)`, not `ZoneInfo` (Windows has no tzdata). Naive datetimes raise `ValueError`.
- `ef_coal` in `factors.json` is stored as 0.0 and calibrated at load time from the annual mix so the year matches CEA 0.727 (`status: calibrated`, ±15%). Factors with `footprint_effect: decreasing` (COP) swap low and high in the low/high sets.
- Model quirks (by design, from TRD): energy per unit of work is `eps_l`, so with the placeholder sweep 70% always has the lowest cost and plans pick it unless the deadline forces more; most of the ~20% saving is the cap, time shifting adds a few points. `sigma_grid = sigma_site` in v0. Grid Option B scales solar by radiation relative to the window mean, so uniformly cloudy days look the same as clear ones; Option A (`hod_profile`) sees absolute cloudiness.
- Planner perf: non-pausable candidates are built once per request; `plan()` ≈ 50 ms (100 ms under coverage). The 500-example deadline property test takes ~45 s with coverage.
- Engine input rules (review fixes): every bad input raises `EngineError` (`invalid_field`, `slot_out_of_range`, `implausible_energy`), never a bare `ValueError`/`KeyError`. `PlanRequest`: strict types, finite numbers, aware datetimes, alpha on the 0.1 grid. Receipts: 1–72 slots, hour ≤ 48+72 slots from submit, ≤ GPUs × max power × 1.1 kWh per hour, ≥ 1 Wh run energy in total. `WeatherRow` rejects NaN and implausible values. Cached objects (`load_cities`, grid, sweep, factor sets) are read-only. `factor_version` hashes factors, grid, sweep, gpus and cities files; scored receipts carry `factor_version_mismatch`.
- Known limit: the pausable plan only uses each slot's cheapest level, so a tight deadline that needs a faster level falls back to the non-pausable plan (note `pause_no_room`). Work above 47 h can exceed the 48-slot window when submitted mid-hour (`invalid_field` says how much fits).
- Private sites (D26): `site_page_view` returns no receipts or monthly footprint for `public: false`; the leaderboard omits them.
- GateGuard asks for facts on the first write/edit of each file: state callers, API, schema and the user's instruction in text, then repeat the call.
- `create-vite` ignores `--template` when called through `npm create … -- --template` in PowerShell: use `npx create-vite@latest web --template react-ts --no-interactive`.
- The CI `web` job needs `web/package-lock.json` committed; the `sam` job is a no-op until `template.yaml` exists.
- Repo was renamed `thrist` → `Thirst` on GitHub (D2 done); old URLs redirect. Still private until submission (D3).

## Decisions Log
- 2026-10-09 — Repo created private as `thrist`, renamed on GitHub to `Thirst` (D2 done); make it public at submission — D3
- 2026-10-09 — Web needs Node 22.12+ (CI uses 22) — the lockfile's vitest 5, jest-dom 7 and jsdom 29 require it
- 2026-10-09 — Plan-level decisions D1–D26 recorded in `docs/implementation-plan/README.md` §5 — resolve gaps in the PRD and TRD before build
- 2026-10-09 — D27: "Best" for scoring is a separate J-optimal solve (weights 0.45/0.35/0.20, same pausable setting), returned as `best` with `j_best`; it does not depend on the user's alpha — TRD 5.9 never says which plan Best is
- 2026-10-09 — D28: pausable plan falls back to the best non-pausable plan (note `gap_limit_fallback`) when the cheapest levels cannot finish in time, and the schedule keeps only the last run slot partial
- 2026-10-09 — D29: `monthly_absolute` and leaderboard footprints are scalars (central set); `kwh` means GPU kWh from receipts, `facility_kwh` is the modelled facility figure

## Changelog
- 2026-10-09 | Phase 02 engine | src/engine/*.py, src/engine/data/*.json, scripts/gen_fixtures.py, scripts/check_skeleton.py, tests/engine/*, tests/weather_helpers.py, tests/fixtures/*, pyproject.toml | tests first; Best = J-optimal solve (D27); placeholder data flagged in factors.json
- 2026-10-09 | Phase 01 foundations (local part) | LICENSE, .gitignore, .editorconfig, .gitattributes, Makefile, pyproject.toml, cli/pyproject.toml, .github/workflows/ci.yml, src/**, cli/**, scripts/check_skeleton.py, web/**, tests/test_smoke.py, README.md, docs/FIXLIST.md | stubs-only skeleton checked by script; Idea_1.md→Idea.md (D1); engine kept free of AWS imports by test
- 2026-10-09 | Detailed implementation plan | AGENTS.md, docs/implementation-plan/* | phase files + contracts; ECC architect/planner review folded in
- 2026-10-09 | Create private repo, add Idea/PRD/TRD | Idea_1.md, prd.md, trd.md | docs-only initial commit

## Archived Summary
(none yet)
