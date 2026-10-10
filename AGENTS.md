# AGENTS.md — Project Memory (auto-maintained)
Last updated: 2026-10-10 | Sessions logged: 4

## Identity
Thirst: a water and carbon planner, receipt and rating for GPU jobs in India (WeMakeDevs x AWS Environmental Hacks, Track 02).
Users: students and lab heads in college GPU labs, startups on rented GPUs. Built by team hello_world.

## Stack & Commands
- Engine and handlers: Python 3.12, pure-Python engine (no numpy), pytest + hypothesis, ruff, mypy (strict, `src/` only).
- CLI: Python ≥ 3.10, nvidia-ml-py, httpx; `thirst` entry point (stub today).
- Web: Vite + React 19 + TypeScript + Recharts + Vitest, Node 22.12+ (`web/`; lint is oxlint; vitest 5 and jest-dom 7 need Node 22).
- AWS: SAM CLI, `ap-south-1`, profile `thirst`, stack `thirst-dev`; `template.yaml` is written (not yet deployed or `sam validate`d: no SAM CLI here).
- Ops scripts: `python scripts/seed.py --profile thirst --stage dev [--wipe-simulated | --delete-site ID]`; `bash scripts/smoke.sh "$API"`; `python scripts/bench_plan.py "$API"`.
- Setup: `uv venv --python 3.12 .venv && uv pip install --python .venv -e ".[dev]" -e ./cli && npm --prefix web ci`.
- Checks (same as CI): `make check` = `ruff check .` + `mypy` + `pytest -m "not gpu and not aws" --cov` (+ `make cov-engine` once engine tests exist).
  Without make (Windows): run `.venv/Scripts/python.exe -m ruff check .`, `-m mypy`, `-m pytest …`, and `npm --prefix web test -- --run | run lint | run build`.
- Skeleton sanity: `python scripts/check_skeleton.py`.

## Current State & Focus
- Phase 01 (foundations), local part DONE: repo hygiene, skeleton (stubs only), Python and Node tooling, CI workflow, offline forecast data. 29 Python tests and 1 web test green.
- Phase 01 still needs people: AWS account/SAM/Docker/budgets/Bedrock/SSM secret (1.6), CSEP/Ember/Aqueduct data (1.7.b–f), GPU box checks (1.8), team registration and deadline (1.9). CI (python, web, sam, secrets) passed on draft PR #1; the Makefile ran green on ubuntu.
- Phase 02 (engine) DONE and reviewed (ECC code + Python reviewers, all CRITICAL/HIGH fixed): units, errors, wetbulb, factors, cooling, grid, forecast, footprint, planner, score, explain + `scripts/gen_fixtures.py`; engine coverage 99%, 317 tests, fixtures in `tests/fixtures/*_response.json` (a test fails when they go stale: run `make fixtures`).
- Engine data is still PLACEHOLDER where plan 1.7 is open: `cities.json` stress categories, `grid_shares.json` national mix, `powercap_sweep.json` (empty, so tau/eps use the placeholders and every plan tags `tau: placeholder`).
- Phase 05 (backend code) DONE offline: errors, security (HMAC), validation, store (moto), refresh, cache, API routes (/plan /sites /receipts /leaderboard /assumptions), `/explain` (template first, optional Strands agent), `template.yaml`, seed/smoke/bench scripts; ~520 handler tests incl. `test_flow.py` end to end on moto. NOT done (needs AWS account): deploy, SSM secret, `sam build --use-container`, smoke and bench against a real URL, Bedrock model access.
- Phase 06 (frontend) P0 pages DONE offline: router/layout, JobForm (IST deadline), Plan page (chart, slider with no request, Pareto, result card), Receipt, Leaderboard, Site, Assumptions, mock mode (`VITE_USE_MOCKS=true`, dev only), honesty scan test, `amplify.yml`. ~340 vitest tests. Reviewed (security: no CRITICAL/HIGH, fixed; React review: 1 HIGH + MEDIUMs, a fix pass was in progress at handoff, see HANDOFF). NOT done: 6.3.j AI sentence box, 6.8 India finding, 6.11 Playwright, 6.10 phone/Lighthouse pass, real-browser look at layout and dark mode (CSS never rendered by a human yet).
- Phase 04 (CLI) software parts: built by a subagent against a fake NVML in `cli/thirst/` + `tests/cli/`; see HANDOFF for what was finished. Hardware parts (real NVML, power-cap sweep, tau/eps measurement) need the GPU box.
- HANDOFF (2026-10-10, work passed to another developer): branch `worktree-impl-plan`, draft PR #1. First run the gates: `.venv/Scripts/python.exe -m ruff check .`, `-m mypy`, `-m pytest -m "not gpu and not aws" --cov`, `python scripts/check_skeleton.py`, `npm --prefix web test -- --run`, `npm --prefix web run lint`, `npm --prefix web run build`. Then, in order: (1) read the last commit messages for anything marked unfinished; (2) human-only items: AWS account/profile `thirst`, SSM server secret, Docker + `sam build --use-container` + `sam validate --lint` + deploy, Bedrock access, set Amplify env (`VITE_API_URL` https, `VITE_USE_MOCKS=false`, `AMPLIFY_MONOREPO_APP_ROOT=web`), Amplify SPA rewrite rule + add Amplify domain to `AllowedOrigins`, run `scripts/smoke.sh` and `scripts/bench_plan.py` against the live URL, run `scripts/seed.py`; (3) real data for plan 1.7 (CSEP, Ember, Aqueduct, power-cap sweep) so placeholder tags go away; (4) GPU box checks (plan 1.8, phase 04 hardware, phase 03 notebook); (5) Phase 07 QA/release and Playwright e2e; (6) team registration, make the repo public at submission (D3). Code freeze Sun 11 Oct 11:00 IST. (7) Open React-review items (all fixed: phone form reset HIGH, deeper guards + error boundary, error summary + focus, route focus, clock-skew slack, window days, Pareto alpha order check): NOT done are a deferred-promise `useLoad` stale-key test, `usePlan` abort on unmount, the vacuous AlphaSlider "not a number" test, a genuinely malformed-rows leaderboard test, restoring `scrollIntoView` in `AssumptionsPage.test.tsx`, ParetoChart accessibility (still `role="img"`, dots mouse-only), coincident Pareto dots pick the last alpha, `useLoad` should keep `load` in a ref, negative-capture wording, page titles with the site name, Spinner announce, RecentReceipts example deadline + per-row link labels, `client.ts` pre-aborted signal, gate the mock import with `import.meta.env.DEV` (the prod build still emits a 73 kB unused `mockFetch` chunk), and the `amplify.yml` comment about a custom API domain and the SPA rewrite rule.
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
- `src/handlers/api.py` — Powertools `APIGatewayHttpResolver`, all routes except `/explain`; receipt order: headers → size → signature → site → JSON → validate → plan checks → plausibility → score → transaction write; `reset_caches()`
- `src/handlers/http.py` — `new_app(logger)` (JSON error handlers), `json_response`, `read_body`, `parse_json`, `new_id`; `errors.py` — `ApiError`, `from_engine`; `security.py` — `site_token`, `verify_signature`, `load_secret`
- `src/handlers/validation.py` — `plan_request`, `site_request`, `receipt_request` + id regexes; `store.py` — `TABLE_SPECS`, `Tables`, `WeatherRepo/SiteRepo/PlanRepo/ReceiptRepo`, `to_ddb/from_ddb`
- `src/handlers/refresh.py` — hourly Open-Meteo → weather table; `cache.py` — `TtlCache`; `assumptions.py` — `/assumptions` body; `explain.py` — `/explain`, `AgentContext`, `strands_tools`
- `template.yaml` — SAM stack (4 tables, HttpApi, Api/Refresh/Explain functions, alarm); `tests/handlers/test_template.py` cross-checks it against `store.TABLE_SPECS`
- `scripts/seed.py` — 8 `s_sim…` sites (D1×5, D2×2, D3×1) + real lab; `smoke.sh`, `bench_plan.py`; `tests/api_helpers.py` + `tests/handlers/conftest.py` — moto fixtures, signed-call client
- `cli/thirst/` — CLI package (stubs; plan 04.x) with its own `cli/pyproject.toml`
- `web/src/` — `api/` (client, guards, types, mocks), `lib/` (format, tags, deadline, jobForm, planView), `hooks/` (usePlan, useLoad, ...), `components/`, `pages/`, `routes.tsx`, `test/honesty.ts` (no-bare-number DOM scan); `amplify.yml` at repo root; `.env.example`
- Web gotchas: production builds throw if `VITE_USE_MOCKS=true` or `VITE_API_URL` is not https; the slider picks `pareto[round(alpha*10)]` on the client; in mock mode the 11 Pareto entries are identical (placeholder sweep), tests use `src/test/planFixture.ts`; test files must type-check (no `node:` imports under `src`, fetch mocks take `RequestInfo | URL`); GateGuard still applies to web edits.
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
- Handlers (Phase 05): verify the HMAC over the raw bytes before parsing JSON; an unknown site and a bad signature are both 401 (no enumeration), a validly signed request for a missing site is 404. `end_ts` more than 10 min in the future is refused. Unverified receipts are stored `scored: false` and never counted.
- Site ids are `s_` + 10 chars of `[a-z2-7]` (base32 alphabet has no 0, 1, 8, 9), plan ids `p_` + 10, job ids `j_` + 12; the plan's `s_sim000001` example is invalid, seeded ids are `s_simaaaaaaa…h` (D30).
- DynamoDB: floats are stored as `Decimal(repr(x))`; NaN/Inf refused; the receipt sort key is `<IST end_ts>#<job_id>` and `job#<job_id>` is the duplicate guard item; the `plans` table also holds `quota#YYYY-MM-DD` counters.
- Powertools: register exception handlers by call (`app.exception_handler(X)(fn)`), the decorator is untyped under strict mypy. Test modules cannot import each other; shared test helpers live in `tests/api_helpers.py`.
- Validation must never leak a 503: `_number` skips `isfinite` for ints (`10**400` overflows it), `_aware` catches `OverflowError` (year 1 or 9999), `parse_json` catches `RecursionError`, receipt times are cut to whole seconds (the sort key regex has no fraction).
- Open gaps (need AWS or later work): `sam validate --lint` never run; leaderboard still costs one Query per public site per cache miss (capped by the site limit; a precomputed per-division item is the real fix); IAM actions are unverified by moto; Bedrock model access untested.
- Test clock: never move a test `Clock` backwards between a receipt and a board read, or later receipts look like they are in the future and are not counted.
- Seed behaviour profiles: capture clusters at 0 or 1 because the placeholder power-cap sweep always makes 70% optimal (plan 1.7 data will spread it).
- Sandbox: the shell refuses compound commands that cannot be verified to stay in the worktree; run plain separate commands.
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

- 2026-10-10 — D30: seeded demo site ids are `s_sim` + 7 letters (the plan's `s_sim000001` fails the id regex) — ids must match one validator everywhere
- 2026-10-10 — D31: `PlanRequest.force_now` lives in the engine (not the handler) so `chosen`, `series` and savings stay consistent for `thirst run --now`
- 2026-10-10 — D32: simulated receipts follow behaviour profiles always_now / follows_plan / water_first / co2_first / mixed (plan 5.10.b named caps-only and follows-70%, which the engine cannot express without new plan kinds)
- 2026-10-10 — D34: abuse limits because POST /sites is open: 100 new sites per IST day, 200 receipts per site per day, leaderboard capped at 100 rows, receipts older than 30 days refused, anonymous plans kept 2 h (site plans 14 d); counters live in the `plans` table as `quota#<scope>#<day>`
- 2026-10-10 — D35: the real lab is found by the `seed_owner = real_lab` attribute, never by name; `simulated` and `seed_owner` cannot be set through the API
- 2026-10-10 — D36: ApiFn gets least-privilege DynamoDB actions (no delete, weather read-only); alarms cover Lambda Errors, API Gateway 5xx (the handler answers 503 itself, so Errors stays 0) and RefreshFailed
- 2026-10-10 — D33: `/explain` accepts an agent answer only if every number in it appears in the plan facts and it uses no spelled-out big number or "percent"; otherwise the template is returned (`note: agent_rejected`)

## Changelog
- 2026-10-10 | Phase 05 ops: seed, smoke, bench, e2e flow tests | scripts/seed.py, scripts/smoke.sh, scripts/bench_plan.py, tests/handlers/test_seed.py, test_ops_scripts.py, test_flow.py | seed never touches non-simulated data; scripts tested against a local stub API
- 2026-10-10 | Phase 05 handlers: refresh, cache, routes, explain, SAM template | src/handlers/*, template.yaml, layers/strands/requirements.txt, src/engine/planner.py (force_now), tests/handlers/*, tests/fixtures/*.json | signature before JSON; template cross-checked with store.TABLE_SPECS; strands-agents pinned 1.59.0
- 2026-10-09 | Phase 05 foundations: errors, security, validation, store | src/handlers/{errors,security,validation,store}.py, scripts/gen_hmac_vectors.py, tests/vectors/hmac.json | HMAC vectors match plan 08 §6
- 2026-10-09 | Phase 02 engine | src/engine/*.py, src/engine/data/*.json, scripts/gen_fixtures.py, scripts/check_skeleton.py, tests/engine/*, tests/weather_helpers.py, tests/fixtures/*, pyproject.toml | tests first; Best = J-optimal solve (D27); placeholder data flagged in factors.json
- 2026-10-09 | Phase 01 foundations (local part) | LICENSE, .gitignore, .editorconfig, .gitattributes, Makefile, pyproject.toml, cli/pyproject.toml, .github/workflows/ci.yml, src/**, cli/**, scripts/check_skeleton.py, web/**, tests/test_smoke.py, README.md, docs/FIXLIST.md | stubs-only skeleton checked by script; Idea_1.md→Idea.md (D1); engine kept free of AWS imports by test
- 2026-10-09 | Detailed implementation plan | AGENTS.md, docs/implementation-plan/* | phase files + contracts; ECC architect/planner review folded in
- 2026-10-09 | Create private repo, add Idea/PRD/TRD | Idea_1.md, prd.md, trd.md | docs-only initial commit

## Archived Summary
(none yet)
