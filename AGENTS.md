# AGENTS.md — Project Memory (auto-maintained)
Last updated: 2026-10-09 | Sessions logged: 2

## Identity
Thirst: a water and carbon planner, receipt and rating for GPU jobs in India (WeMakeDevs x AWS Environmental Hacks, Track 02).
Users: students and lab heads in college GPU labs, startups on rented GPUs. Built by team hello_world.

## Stack & Commands
Planned (no code yet). See `docs/implementation-plan/01-foundations.md` §1.3 to §1.5.
- Engine and handlers: Python 3.12, pure-Python engine (no numpy), pytest + hypothesis, ruff, mypy.
- CLI: Python ≥ 3.10, nvidia-ml-py, httpx; `pip install -e ./cli` → `thirst …`.
- Web: Vite + React + TypeScript + Recharts, Node 20; `cd web && npm ci && npm run dev`.
- AWS: SAM CLI, `ap-south-1`, profile `thirst`, stack `thirst-dev`; `sam build --use-container && sam deploy`.
- Task runner (planned): `make check | test | fixtures | assumptions | build | deploy | smoke`.

## Current State & Focus
- Docs only: `Idea_1.md`, `prd.md`, `trd.md`, and the implementation plan in `docs/implementation-plan/`.
- Next: Phase 01 Foundations (Fri 9 Oct 09:00 IST), then the engine (B), backend (A) and frontend (C) in parallel.
- Code freeze Sun 11 Oct 11:00 IST; submit Sun 14:00 to 16:00 IST. The exact deadline time is still to be checked on the schedule page.

## Architecture
CLI (NVML meter, power cap, pause/resume) → HMAC-signed receipts → API Gateway HTTP API → Lambda `api` (engine) → DynamoDB (weather, sites, plans, receipts).
EventBridge Scheduler (hourly) → Lambda `refresh` → Open-Meteo → weather table.
Browser → Amplify (React) → `/plan`, `/sites`, `/leaderboard`, `/assumptions`; optional Lambda `explain` (Strands + Bedrock, template fallback).
The engine is pure Python with no AWS imports; the solver decides and the AI only explains.

## File Map
- `Idea_1.md` — why: problem, science, Thirst Score spec v0.2, sources (to be renamed to `Idea.md`, D1)
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

## Decisions Log
- 2026-10-09 — Repo created private as `thrist`; rename to `thirst` and make it public at submission — D2, D3
- 2026-10-09 — Plan-level decisions D1–D26 recorded in `docs/implementation-plan/README.md` §5 — resolve gaps in the PRD and TRD before build

## Changelog
- 2026-10-09 | Detailed implementation plan | AGENTS.md, docs/implementation-plan/* | phase files + contracts; ECC architect/planner review folded in
- 2026-10-09 | Create private repo, add Idea/PRD/TRD | Idea_1.md, prd.md, trd.md | docs-only initial commit

## Archived Summary
(none yet)
