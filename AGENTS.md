# AGENTS.md — Project Memory (auto-maintained)
Last updated: 2026-10-11 | Sessions logged: 6

## Identity
Thirst: a water and carbon planner, receipt and rating for GPU jobs in India (WeMakeDevs x AWS Environmental Hacks, Track 02).
Users: students and lab heads in college GPU labs, startups on rented GPUs. Built by team hello_world.

## Stack & Commands
- Engine and handlers: Python 3.12, pure-Python engine (no numpy), pytest + hypothesis, ruff, mypy (strict, `src/` only).
- CLI: Python ≥ 3.10, nvidia-ml-py, httpx; `thirst` on PyPI (0.3.1), released by tag `cli-vX.Y.Z` (Trusted Publishing).
- Web: Vite + React 19 + TypeScript + Recharts + Vitest, Node 22.12+ (`web/`; lint is oxlint; vitest 5 and jest-dom 7 need Node 22).
- AWS: SAM CLI, `ap-south-1`, profile `thirst` (`aws login --profile thirst`), stack `thirst-dev`, LIVE. Deploys run from GitHub (`deploy.yml`, OIDC role `thirst-github-deploy`) after CI on `main`; by hand: `python scripts/build_layer.py && sam build && sam deploy --profile thirst`, then `python scripts/deploy_web.py --app-id dzxkrtlc7xqfx --api-url <ApiUrl> --profile thirst`.
- Ops scripts: `python scripts/seed.py --profile thirst --stage dev [--wipe-simulated | --delete-site ID]`; `bash scripts/smoke.sh "$API"`; `python scripts/bench_plan.py "$API"`.
- Setup: `uv venv --python 3.12 .venv && uv pip install --python .venv -e ".[dev]" -e ./cli && npm --prefix web ci`.
- Checks (same as CI): `make check` = `ruff check .` + `mypy` + `pytest -m "not gpu and not aws" --cov` (+ `make cov-engine` once engine tests exist).
  Without make (Windows): run `.venv/Scripts/python.exe -m ruff check .`, `-m mypy`, `-m pytest …`, and `npm --prefix web test -- --run | run lint | run build`.
- Skeleton sanity: `python scripts/check_skeleton.py`. Generated files: `make fixtures` (API fixtures) and `make assumptions` (`ASSUMPTIONS.md`); tests fail when either is stale.
- Web e2e: `npm --prefix web run e2e` (Playwright vs the live site, read-only).

## Current State & Focus
- 2026-10-11 ~14:00 IST: **LIVE and submission-ready on the code side.** Web https://main.dzxkrtlc7xqfx.amplifyapp.com, API https://l6y3i40hh4.execute-api.ap-south-1.amazonaws.com, `pip install thirst` 0.3.1. CI, Deploy and Publish CLI workflows green. PRs #1–#13 merged; work on short branches + PRs; the owner merges (auto mode blocks `gh pr merge`).
- Phases: 01 foundations DONE (except 1.7 real data, 1.8 GPU box, 1.9 people); 02 engine DONE (317 tests, 99%); 04 CLI DONE in software and reviewed (PR #7 fixed H4/M1, SIGHUP, SIGCONT-after-error, loud restore failure), hardware checks NOT done; 05 backend DONE and deployed (smoke + bench green, p95 383 ms); 06 frontend DONE incl. Playwright e2e + axe (PR #9) and code-splitting (PR #6); 07 release: writeup, checklist, test guide, video script written (`docs/`), people items open.
- Biggest honesty gap: 18 of 57 factors are placeholders, worst is the power-cap sweep (`powercap_sweep.json` empty → every plan picks 70%, all 11 Pareto points identical; on the UX branch the planner hides the slider and says why). Needs `thirst sweep` on a desktop NVIDIA GPU (laptops block power limits).
- Bedrock is blocked account-wide ("Operation not allowed", NOT_AUTHORIZED); `BedrockModelId` is empty and `/explain` serves the template. Needs an AWS Support case.
- Open work is tracked in `docs/TODO.md` (open items only, done items in its §7), `docs/FIXLIST.md` (problems found while testing, metrics evidence), `docs/SUBMISSION.md` (submission checklist) and issue #5. The 7 CLI walkthrough issues (TODO 4.1.a–g) and most 4.2 review leftovers are fixed on `feat/web-ui-accessibility` and ship with CLI 0.3.2.
- Submit Sun 11 Oct 14:00–16:00 IST: team registration, video (`docs/VIDEO_SCRIPT.md`), blog, repo public (D3), Cost Explorer screenshot, delete the PyPI token pasted in chat. The full-history gitleaks scan is done (no leaks, `docs/gitleaks_full_history.txt`). After submitting, leave the stack and data running.

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
- `src/engine/data/` — `factors.json` (57 factors, status per row), `gpus.json` (42, each sourced), `cities.json` (6), `grid_shares.json`, `powercap_sweep.json`, `sample_forecast.json` (96 h × 6 cities, matched by hour of day)
- `tests/weather_helpers.py` — synthetic weather and `request()` builder shared by engine tests; `scripts/gen_fixtures.py` — writes the three API fixtures
- `src/handlers/api.py` — Powertools `APIGatewayHttpResolver`, all routes except `/explain`; receipt order: headers → size → signature → site → JSON → validate → plan checks → plausibility → score → transaction write; `reset_caches()`
- `src/handlers/http.py` — `new_app(logger)` (JSON error handlers), `json_response`, `read_body`, `parse_json`, `new_id`; `errors.py` — `ApiError`, `from_engine`; `security.py` — `site_token`, `verify_signature`, `load_secret`
- `src/handlers/validation.py` — `plan_request`, `site_request`, `receipt_request` + id regexes; `store.py` — `TABLE_SPECS`, `Tables`, `WeatherRepo/SiteRepo/PlanRepo/ReceiptRepo`, `to_ddb/from_ddb`
- `src/handlers/refresh.py` — hourly Open-Meteo → weather table; `cache.py` — `TtlCache`; `assumptions.py` — `/assumptions` body; `explain.py` — `/explain`, `AgentContext`, `strands_tools`
- `template.yaml` — SAM stack (4 tables, HttpApi, Api/Refresh/Explain functions, alarm); `tests/handlers/test_template.py` cross-checks it against `store.TABLE_SPECS`
- `scripts/seed.py` — 8 `s_sim…` sites (D1×5, D2×2, D3×1) + real lab; `smoke.sh`, `bench_plan.py`; `tests/api_helpers.py` + `tests/handlers/conftest.py` — moto fixtures, signed-call client
- `cli/thirst/` — CLI package with its own `cli/pyproject.toml`: `commands.py`/`jobrun.py`/`jobsetup.py` (commands), `client.py`+`outbox.py` (signed HTTP, retries), `meter.py`+`nvml.py`+`modelled.py` (energy), `powercap.py` (cap + `~/.thirst/restore.json`), `process.py`+`runner.py`+`schedule.py` (pause/resume), `receipt.py`, `sweep.py`, `data/gpus.json` (byte copy of the engine file, tested)
- CLI gotchas: `register` saves the token to `config.toml` (0600) and never prints it; `thirst run` refuses to start (exit 5) if a restore marker is left over unless `--no-cap`/`--modelled`; `doctor --restore` resets caps; exit 2 = command not found; `THIRST_HOME` moves the config/receipts folder (use it for throwaway tests); defaults are the live API and site (`cli/thirst/config.py`); the receipt is saved and queued before the POST (PR #7); tests use `tests/cli/thirst_fakes.py` + `thirst_rig.py`.
- `web/src/` — `api/` (client, guards, types, mocks), `lib/` (format, tags, deadline, jobForm, planView), `hooks/` (usePlan, useLoad, ...), `components/`, `pages/`, `routes.tsx`, `test/honesty.ts` (no-bare-number DOM scan); `amplify.yml` at repo root; `.env.example`
- Web routes: `/` is the home page (live forecast via the sample job in `lib/landing.ts`, one shared /plan request per city+cooling in `useCityForecast`), the planner is `/plan` (`?city=` prefills; a full share link `?city&gpu&n&hours&deadline&pause&cooling` fills the form and plans at once, `lib/jobForm.ts` `valuesFromQuery`), `/cities` compares the sample job in six cities. Theme is light only, Monsoon palette (teal `#126e6b`, amber `#f0b43c`): Archivo + IBM Plex Mono from Google Fonts, tokens in `index.css` (old names `--cobalt`/`--signal` alias the new colours; the refresh rules sit at the end of `index.css`, `theme.css`, `pages.css` and `landing.css`).
- Planner extras (phase 09): `lib/planViews.ts` (pure: hour cells, cleanest window, why-this-time, run command, `.ics`, share query) feeds `PlanViews` (Timetable/Hourly/Calendar/Chart tabs) and `PlanActions`; `lib/recentPlans.ts` keeps the last 5 jobs in localStorage (try/catch, optional); the trade-off slider is hidden with a note while all 11 Pareto entries are the same plan, and the e2e slider tests skip then.
- Web gotchas: production builds throw if `VITE_USE_MOCKS=true` or `VITE_API_URL` is not https; the slider picks `pareto[round(alpha*10)]` on the client; in mock mode the 11 Pareto entries are identical (placeholder sweep), tests use `src/test/planFixture.ts`; test files must type-check (no `node:` imports under `src`, fetch mocks take `RequestInfo | URL`); GateGuard still applies to web edits.
- `scripts/check_skeleton.py` — asserts the repo layout from plan 1.2; `gen_assumptions.py` — renders `ASSUMPTIONS.md` from `handlers.assumptions.build` (`--check` for staleness); `build_layer.py` — Strands layer from manylinux aarch64 wheels (no Docker); `deploy_web.py` — Amplify zip deploy; `local_api.py` — real handlers on moto + live weather
- `.github/workflows/` — `ci.yml` (python, web, sam validate --lint, gitleaks), `deploy.yml` (OIDC → SAM + Amplify after CI on main), `publish-cli.yml` (tag `cli-v*` → PyPI Trusted Publishing)
- `SPEC.md` — score rules as implemented; `ASSUMPTIONS.md` — generated factor table; `docs/` — `WRITEUP.md`, `SUBMISSION.md`, `TODO.md`, `FIXLIST.md`, `USER_TEST_GUIDE.md`, `VIDEO_SCRIPT.md`, `bench_plan.txt`, `readme/` (README images); `web/README.md`, `cli/README.md` (also the PyPI page)
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
- Budget `thirst-monthly` $50 (credits excluded), emails at 10/20/50/100% + forecast to the owner; spend 1–11 Oct: $0.00. ~$160 credits left (D4, D37).
- SAM `CodeUri: src/` does not ship root `data/`; runtime JSON lives in `src/engine/data/` (D6).
- HTTP API may base64-encode the body; verify the HMAC over the decoded raw bytes (D21).
- The Strands layer is built WITHOUT Docker: `python scripts/build_layer.py` installs manylinux aarch64 wheels into `layers/strands/python` (gitignored); `template.yaml` packages that folder as-is (no BuildMethod).
- SIGSTOP/killpg are POSIX only; the CLI forces non-pausable on Windows and for distributed launchers (D15).
- A stopped (SIGSTOP) process must get SIGCONT before SIGTERM, or it can't exit.
- DynamoDB needs Decimal, not float; NaN and Inf are rejected.
- The power limit resets on reboot or driver reload; the restore marker is `~/.thirst/restore.json`.
- Windows dev box: no `make` (run Makefile commands by hand); Git Bash mangles args starting with `/` (set `MSYS_NO_PATHCONV=1` for AWS CLI); boto3 needs `botocore[crt]` to read `aws login` credentials.
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
- Open gaps: leaderboard still costs one Query per public site per cache miss (capped by the site limit; a precomputed per-division item is the real fix); Bedrock model access blocked for the account. (`sam validate --lint` runs in CI; IAM verified by the live deploy.)
- Test clock: never move a test `Clock` backwards between a receipt and a board read, or later receipts look like they are in the future and are not counted.
- Seed behaviour profiles: capture clusters at 0 or 1 because the placeholder power-cap sweep always makes 70% optimal (plan 1.7 data will spread it).
- Sandbox: the shell refuses compound commands that cannot be verified to stay in the worktree; run plain separate commands.
- Private sites (D26): `site_page_view` returns no receipts or monthly footprint for `public: false`; the leaderboard omits them.
- GateGuard asks for facts on the first write/edit of each file: state callers, API, schema and the user's instruction in text, then repeat the call.
- `create-vite` ignores `--template` when called through `npm create … -- --template` in PowerShell: use `npx create-vite@latest web --template react-ts --no-interactive`.
- The CI `web` job needs `web/package-lock.json` committed. Deploy has no `environment:` block on purpose: it would change the OIDC `sub` claim and the role would refuse it.
- Repo was renamed `thrist` → `Thirst` on GitHub (D2 done); old URLs redirect. Still private until submission (D3). Test labs created on the live site are removed with `scripts/seed.py --delete-site <id>`.
- CLI release: bump `cli/pyproject.toml` + `cli/thirst/__init__.py`, merge, then `git tag cli-vX.Y.Z && git push origin cli-vX.Y.Z`; `.github/workflows/publish-cli.yml` checks the tag matches and publishes via PyPI Trusted Publishing (publisher: Neal006/Thirst, workflow publish-cli.yml, no environment). PyPI's JSON API can lag a few minutes; the simple index updates first.
- e2e: `npm --prefix web run e2e` hits the live site by default (read-only guard: only GET and POST /plan). For a local build use `vite preview --port 5173` (5173 is the only local origin in `AllowedOrigins`) and `E2E_BASE_URL=http://localhost:5173`.
- Contrast tokens are WCAG AA on white, paper and sunk backgrounds (axe checks them in e2e); keep new text colours ≥ 4.5:1 and links ≥ 24 px tall.
- The git-workflow `pr-status.sh` script fails on Windows (`jq: Argument list too long`); use `gh pr checks <n>`. Auto mode may block `gh pr merge` and IAM changes: hand those to the user.

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
- 2026-10-11 — D37: limits raised for judging (team decision: nothing may block judges): 1000 new sites/day, 2000 receipts/site/day, 3000 explain calls/day, API throttle 200 rps burst 400; the $50 AWS budget alerts (credits excluded) are the cost guard instead
- 2026-10-11 — D38: the deploy role trusts both OIDC subject forms (`repo:Neal006/Thirst:ref:refs/heads/main` and the immutable `repo:Neal006@176215022/Thirst@1411286480:ref:refs/heads/main`) — the repo uses GitHub's immutable subject claim, so the old form alone failed with "Not authorized to perform sts:AssumeRoleWithWebIdentity"
- 2026-10-11 — D39: pages other than home load through react-router `lazy` (main chunk 810 → 249 kB); route tests wait up to 5 s for the planner chunk
- 2026-10-10 — D33: `/explain` accepts an agent answer only if every number in it appears in the plan facts and it uses no spelled-out big number or "percent"; otherwise the template is returned (`note: agent_rejected`)

## Changelog
- 2026-10-11 | TODO sweep on `feat/web-ui-accessibility` + restore PR #14 docs lost in the branch merge | cli/thirst/{__init__,receipt,planning,commands,jobrun,powercap,process,sweep}.py, cli/pyproject.toml, tests/cli/*, .github/workflows/{ci,deploy,publish-cli}.yml, docs/{TODO,FIXLIST,SUBMISSION,USER_TEST_GUIDE,VIDEO_SCRIPT,gitleaks_full_history}.*, README.md, cli/README.md, web/README.md, AGENTS.md, docs/implementation-plan/{04,06,07,09}*, docs/pr/* | 4.1.g "modelled at 70% (plan level)". 4.2: `/plan` reply checked (`planning.checked_plan`), full `nvidia-smi`/`sudo` paths (`powercap.absolute_argv`), sweep sets `CUDA_DEVICE_ORDER`, tee survives log errors. 2.2 sweep runs combine by median (`sweep.combine_runs`, `history`). Actions on Node 24. Deploy gets an `e2e` job. Full-history gitleaks clean. CLI version 0.3.2 (tag `cli-v0.3.2` still to push). TODO.md now lists open items only
- 2026-10-11 | Phase 09 UX overhaul + merge review + TODO 4.1/5.x | web/src/{components/{PlanViews,PlanActions,PlanResults,ResultCard,JobForm,Layout},pages/{CitiesPage,PlanPage,Leaderboard,Site,Receipt,Assumptions,Landing}Page,lib/{planViews,recentPlans,jobForm}}.ts*, web/src/*.css, web/e2e/*, cli/thirst/{commands,jobrun,jobsetup,receipt,config}.py, docs/{USER_TEST_GUIDE,VIDEO_SCRIPT,TODO,WRITEUP}.md, docs/implementation-plan/09-ux-overhaul.md, docs/pr/*, docs/readme/* | Monsoon theme; tag chips kept ≥ 4.5:1 after axe failed the first softer version; "Assumptions" name and team slogan kept because e2e, video and README use them; CLI: doctor `[warn]` on laptops, full Assumptions URL, dry-run exact times, `--modelled` uses the detected GPU, Wh/mL/g for short jobs, no 404 link for private sites (`config.toml` keeps `public`)
- 2026-10-11 | Refresh every doc; generate ASSUMPTIONS.md; write SPEC.md; real web/README | ASSUMPTIONS.md, SPEC.md, scripts/gen_assumptions.py, tests/test_gen_assumptions.py, README.md, cli/README.md, web/README.md, docs/*, docs/implementation-plan/*, prd.md, trd.md, Idea.md, AGENTS.md | owner ran USER_TEST_GUIDE end to end (78.57 Gold for one public modelled receipt, see SPEC §4); test labs deleted
- 2026-10-11 | `thirst` 0.3.1 on PyPI via Trusted Publishing | .github/workflows/publish-cli.yml, cli/pyproject.toml, cli/thirst/__init__.py | tag `cli-v0.3.1`; includes #7 CLI fixes and #8 GPUs (RTX 3050 Laptop detected)
- 2026-10-11 | Finish Neal's salvaged issue-5 branches, writeup, branch cleanup | web/src/routes.tsx, web/src/api/defaultClient.ts, web/src/components/ui/Spinner.tsx, web/src/index.css, web/src/components/landing/PowerCap.tsx, web/e2e/*, cli/thirst/{jobrun,outbox,runner,process}.py, src/engine/data/gpus.json, docs/{WRITEUP,SUBMISSION}.md, README.md | first e2e run vs live: 61/79, axe contrast/dl/target-size fixed → 77 pass + 2 skip (placeholder Pareto); receipts saved before POST; OIDC trust fixed (D38)
- 2026-10-11 | First AWS deploy + CD + PyPI | template.yaml, samconfig.toml, scripts/{build_layer,deploy_web}.py, .github/workflows/deploy.yml, cli/thirst/config.py, .gitleaks.toml | stack thirst-dev (ap-south-1), API https://l6y3i40hh4.execute-api.ap-south-1.amazonaws.com, web https://main.dzxkrtlc7xqfx.amplifyapp.com (Amplify app dzxkrtlc7xqfx, manual zip deploys), Strands layer built without Docker from manylinux aarch64 wheels, GitHub deploys via OIDC role thirst-github-deploy (main only), `thirst` 0.3.0 on PyPI with the live API as default; Bedrock blocked for the account until first console use, so BedrockModelId is empty (template explanations)
- 2026-10-10 | Game theme on inner pages, readability fixes, user README, PyPI prep | web/src/pages/{Leaderboard,Site,Receipt,Assumptions,Plan}*, web/src/{theme,pages}.css, web/src/lib/badges.ts, README.md, docs/readme/*, cli/README.md, cli/pyproject.toml | badge thresholds come from /assumptions; chip hover was white-on-white; `thirst` is free on PyPI but not published (needs a default API URL after deploy)
- 2026-10-10 | Home page and light theme: water clock, beakers, power-cap switch, pipeline + sample receipt, board preview; planner moved to /plan with quick-fill presets and ?city= prefill | web/src/pages/LandingPage.tsx, web/src/components/landing/*, web/src/lib/landing.ts, web/src/index.css, web/src/pages/landing.css | every landing number comes from /plan or /assumptions and wears a tag; the receipt picture is in <code> and stamped Sample
- 2026-10-10 | Local API runner and receipt tag fix | scripts/local_api.py, cli/thirst/receipt.py | runs the real Lambda handlers on moto + live Open-Meteo, no AWS needed; --modelled receipts no longer say "measured"
- 2026-10-10 | Phase 05 ops: seed, smoke, bench, e2e flow tests | scripts/seed.py, scripts/smoke.sh, scripts/bench_plan.py, tests/handlers/test_seed.py, test_ops_scripts.py, test_flow.py | seed never touches non-simulated data; scripts tested against a local stub API
- 2026-10-10 | Phase 05 handlers: refresh, cache, routes, explain, SAM template | src/handlers/*, template.yaml, layers/strands/requirements.txt, src/engine/planner.py (force_now), tests/handlers/*, tests/fixtures/*.json | signature before JSON; template cross-checked with store.TABLE_SPECS; strands-agents pinned 1.59.0
- 2026-10-09 | Phase 05 foundations: errors, security, validation, store | src/handlers/{errors,security,validation,store}.py, scripts/gen_hmac_vectors.py, tests/vectors/hmac.json | HMAC vectors match plan 08 §6
- 2026-10-09 | Phase 02 engine | src/engine/*.py, src/engine/data/*.json, scripts/gen_fixtures.py, scripts/check_skeleton.py, tests/engine/*, tests/weather_helpers.py, tests/fixtures/*, pyproject.toml | tests first; Best = J-optimal solve (D27); placeholder data flagged in factors.json
- 2026-10-09 | Phase 01 foundations (local part) | LICENSE, .gitignore, .editorconfig, .gitattributes, Makefile, pyproject.toml, cli/pyproject.toml, .github/workflows/ci.yml, src/**, cli/**, scripts/check_skeleton.py, web/**, tests/test_smoke.py, README.md, docs/FIXLIST.md | stubs-only skeleton checked by script; Idea_1.md→Idea.md (D1); engine kept free of AWS imports by test
- 2026-10-09 | Detailed implementation plan | AGENTS.md, docs/implementation-plan/* | phase files + contracts; ECC architect/planner review folded in
- 2026-10-09 | Create private repo, add Idea/PRD/TRD | Idea_1.md, prd.md, trd.md | docs-only initial commit

## Archived Summary
- 2026-10-09/10 (sessions 1–4): plan written (D1–D26), Phase 01/02/04/05/06 built offline with TDD, reviewed, handed over on draft PR #1 (`worktree-impl-plan`). The handoff list (AWS account, SSM secret, deploy, Amplify env + SPA rewrite, smoke/bench, seed, real data, GPU box, Playwright, React-review leftovers, mock-chunk gating, amplify.yml comment) is now done except real data, GPU box, Bedrock and the people items.
- 2026-10-10/11 (session 5): landing page + light theme (#2), inner-page game theme + user README (#3), first AWS deploy + CD + PyPI 0.3.0 (#4), Neal's salvaged issue-5 branches finished (#6 web, #7 CLI, #8 GPUs, #9 e2e), OIDC immutable-subject fix (D38), docs (#10, #11, #13), PyPI 0.3.1 via Trusted Publishing (#12).
