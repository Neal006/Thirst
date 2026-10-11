# Thirst — Implementation Plan (master index)

> **Status on 11 Oct 2026, 14:00 IST.** Code is live and every phase except 03 is built.
>
> | Phase | Status |
> |---|---|
> | [01](01-foundations.md) Foundations | ✅ done; real data (1.7), GPU box (1.8) and team registration (1.9) open |
> | [02](02-engine.md) Engine | ✅ done (317 tests, 99% coverage); placeholder data until 1.7 |
> | [03](03-step0-notebook.md) Step 0 notebook | ⬜ not done |
> | [04](04-cli-hardware.md) CLI | ✅ software done and reviewed, `thirst` 0.3.1 on PyPI; hardware checks open |
> | [05](05-backend-aws.md) Backend + AWS | ✅ deployed, smoke + bench green; Bedrock blocked for the account |
> | [06](06-frontend.md) Frontend | ✅ done, including Playwright e2e + axe; 6.3.j, 6.8 and 6.10 open |
> | [07](07-integration-qa-release.md) QA + release | ⚠️ docs done; the people items are in [`../SUBMISSION.md`](../SUBMISSION.md) |
>
> Gates:
> - M1 ✅ · M2 ✅ · M5 ✅
> - M3 ⚠️ receipts work, no real overnight GPU receipt yet
> - M4 ⚠️ the plan → run → receipt → board loop works with `--modelled`, not yet measured on a GPU
> - M6 ✅ code freeze held for features; fixes and docs went in after it
> - M7 ⬜ submission
>
> Decisions taken after this plan: D27–D39 in [`../../AGENTS.md`](../../AGENTS.md). Live status: [`../TODO.md`](../TODO.md).

Version 1.0 · 9 Oct 2026 · Built from `Idea.md` (then `Idea_1.md`, renamed in D1) (why), `prd.md` (what) and `trd.md` (how).
Code freeze **Sun 11 Oct 11:00 IST** · Submit **Sun 11 Oct 14:00 to 16:00 IST**.

This plan turns the three documents into tasks you can execute in order. Every task has an ID,
an owner, a time box, sub-steps, an output, a "done when" check and a command or action that
verifies it. If the plan and the TRD disagree, the TRD wins **unless** the disagreement is listed in
[Resolved inconsistencies](#5-resolved-inconsistencies-and-plan-level-decisions), which records a decision on purpose.

---

## 1. How to read this plan

| Item | Meaning |
|---|---|
| **Phase** | A workstream that ships one part of the product (`01` to `07`) |
| **Step** `X.Y` | One task that one person can finish in 15 to 90 minutes |
| **Sub-step** `X.Y.z` | One concrete action (a file, a function, a command, a test) |
| **Owner** | **A** Backend/AWS · **B** Engine/CLI/Hardware · **C** Frontend + Data/Story (TRD §15) |
| **Priority** | **P0** demo depends on it · **P1** only if all P0 is green by Fri 22:00 · **P2** after the hackathon |
| **Time box** | When to stop and escalate. Overrunning by 50% means ask for help or cut scope (PRD §5.4) |
| **Done when** | An objective check. If you can't run the check, the step is not done |
| **TDD** | Engine, CLI and handler steps list their tests **before** the implementation sub-steps. Write them first, watch them fail, then implement |

**Default "Done when"**: a step without its own line is done when its tests
(`pytest tests/<area>/test_<module>.py`, or `npm test -- --run <Component>` for web) are green in CI,
module coverage meets the DoD target, the PR is merged, and web steps also render correctly at 360 px in `npm run dev`.

### Load balancing (after the ECC planner review)

These moves apply in **both** team sizes. They take about 4 h off B's Friday critical path:

| Work | Moved from → to | When |
|---|---|---|
| Writing `factors.json` and `gpus.json` content (02.2.a, 02.2.b) | B → **C** (TRD §15 already gives factors to C) | Fri 10:30 to 11:30 |
| `score.py` (02.8) | B → **A** (A's 05.7 needs it anyway) | Fri 15:00 to 17:00 |
| 4.4.d restore marker, 4.6 tests 8 and 10, `doctor` checks beyond NVML/cap/API, `thirst sync` | B Fri → **B Sat 09:00 to 12:00** | Sat |
| Hand-written `tests/fixtures/plan_response.json` stub (05.1.c′) | new, **A** | Fri by 10:45 |

### Two-person mode (likely: PRD §11 lists two members)

| Person | Owns | Cuts in this mode |
|---|---|---|
| **P1 = A + C-frontend** | Phase 05, Phase 06, 02.8 score | 6.4.c DOM tag scan, 6.10.e Lighthouse, 6.11 live runs (mocks only), 5.11.c alarm, 6.3.j |
| **P2 = B + C-data** | Phases 02 and 04, `factors.json`, `cities.json`, Phase 03 | Step 0 runs as the TEMP cell only, with "Midday wins" as the default headline unless the TEMP result says otherwise; the 4.5 sweep runs once |

---

## 2. Phase files

| # | File | Owner | Window (IST) | Ships |
|---|---|---|---|---|
| 01 | [01-foundations.md](01-foundations.md) | All | Fri 09:00 to 10:30 | Repo, tooling, CI, AWS account, Bedrock access request, data-source checks, GPU box readiness |
| 02 | [02-engine.md](02-engine.md) | B | Fri 09:30 to 18:00 | `src/engine/*`: units, factors, wet-bulb, cooling, grid, footprint, planner, score, with full tests |
| 03 | [03-step0-notebook.md](03-step0-notebook.md) | C | Fri 09:30 to 13:00 | India trade-off finding, headline decision, `docs/india_finding.png` |
| 04 | [04-cli-hardware.md](04-cli-hardware.md) | B | Fri 13:00 to 22:00 | `thirst` CLI: register, plan, run, sweep, doctor, sync; NVML meter; power cap; pause/resume; signed receipts; overnight run |
| 05 | [05-backend-aws.md](05-backend-aws.md) | A | Fri 09:30 to Sat 12:00 | SAM template, DynamoDB, `api` / `refresh` / `explain` Lambdas, HMAC, seed data, budgets, deploy |
| 06 | [06-frontend.md](06-frontend.md) | C | Fri 13:00 to Sat 17:00 | React app: Plan, Receipt, Leaderboard, Site, Assumptions; charts; slider; Amplify deploy |
| 07 | [07-integration-qa-release.md](07-integration-qa-release.md) | All | Sat 09:00 to Sun 16:00 | E2E, clean-machine test, security pass, docs, video, blog, submission, post-hackathon roadmap |
| 08 | [08-reference-contracts.md](08-reference-contracts.md) | All (read) | n/a | JSON file schemas, API contract with validation rules, error codes, env vars, DynamoDB item shapes, test vectors |

---

## 3. Milestones and gates

A gate is a checkpoint where the team stops and checks in for 5 minutes. If a gate fails, apply the
listed fallback straight away. Don't push the gate back.

| Gate | When | Pass condition | Fallback if it fails |
|---|---|---|---|
| **G0 Ready** | Fri 10:30 | Repo skeleton pushed, CI green, `sam deploy` works for a hello stub, Bedrock access requested, GPU box shows `nvidia-smi`, Open-Meteo curl works | Missing AWS: develop locally against `sam local start-api`. Missing GPU: `--modelled` path, find a lab machine for the one real run |
| **M1a Headline** | Fri 13:00 | Step 0 headline chosen (from the TEMP cell if the engine isn't merged yet; re-checked against engine code by Sat 12:00, 3.7.e) | Ship the "Midday wins" headline |
| **M1b Engine** | Fri 15:30 | `pytest tests/engine` green; median of 20 `planner.plan()` runs for the default example < 200 ms on the CI runner | Keep planner without the fragmentation limit (3b.4) and add it Sat |
| **M2 API live** | Fri 18:00 | `POST /plan` on Lambda returns a valid response (50 requests after 1 warm-up, p95 < 2000 ms, saved to `docs/bench_plan.txt`); power-cap sweep JSON committed; Playwright `plan.spec.ts` passes against the Amplify URL | Web uses the mock fixtures; sweep keeps PLACEHOLDER values, labelled |
| **M3 Scope lock** | Fri 22:00 (job start **by 22:30 at the latest**) | `thirst run` passes the 4.6.h manual check on the GPU box; **overnight job started**. `/receipts` may land by Sat 09:00, because the receipt waits in the outbox and `thirst sync` posts it | Start the overnight job with `--now`, not pausable, so you still get one measured receipt |
| **M4 Loop closed** | Sat 12:00 | Overnight receipt is on the board and the site page; Capture shown; leaderboard has seeded simulated sites | Re-run a 1-hour job with the plan forced to start immediately |
| **M5 Clean machine** | Sat 21:00 | Fresh clone, then install, register, plan, run `--modelled`, and see the board, in under 15 min with only README instructions | Fix the README and installer before anything else |
| **M6 Code freeze** | Sun 11:00 | Main is green, deployed, tagged `v0.3.0` | Revert the last risky merge; ship the tag before it |
| **M7 Submitted** | Sun 16:00 | Submission checklist (07 §7.10) all ticked | n/a |

---

## 4. Critical path and dependencies

```
                    ┌─────────────── 01 Foundations (all, Fri 09:00-10:30) ───────────────┐
                    │                                                                       │
     B: 02.1 units ─► 02.2 factors ─► 02.3 wetbulb ─► 02.4 cooling ─► 02.5 grid ─► 02.6 footprint ─► 02.7 planner ─► 02.8 score
                          │                                  ▲            │                   │                │
     C: 03 Step 0 ────────┘ (factors.json, cities.json) ─────┘            │                   │                │
                                                                          ▼                   ▼                ▼
     A: 05.1 SAM skeleton ─► 05.2 tables ─► 05.3 store ─► 05.4 refresh ─► 05.5 /plan ─► 05.6 /sites ─► 05.7 /receipts ─► 05.8 board/assumptions ─► 05.10 seed
                                                                          │                                   ▲
     B:                                                    04.1 CLI skeleton ─► 04.3 meter ─► 04.4 powercap ─► 04.5 sweep ─► 04.6 runner ─► 04.7 receipt post ─► 04.9 OVERNIGHT RUN (Fri 22:00)
                                                                          │
     C:                                           06.1 scaffold + mock API ─► 06.3 Plan page ─► 06.5 Receipt ─► 06.6 Leaderboard/Site ─► 06.7 Assumptions ─► 06.9 Amplify
```

**Critical path** (any slip here moves the demo): `02.1 → 02.7 planner → 05.5 /plan on Lambda → 04.6 runner → 05.7 /receipts → 04.9 overnight run → 07.2 overnight verification`.

**Things that unblock other people early:**

1. **05.1.c′**: A hand-writes `tests/fixtures/plan_response.json` from the 08 §3.1 example by **Fri 10:45**. **02.7.k** overwrites it with real engine output (about 15:30). C builds the whole Plan page against the fixture, without waiting for Lambda or the engine.
2. **08 §6** HMAC test vectors are committed by Fri 13:00. A (server) and B (CLI) both test against the same vectors.
3. **05.1** deploys a stub `/plan` returning the fixture by Fri 11:00. The live URL exists early and CORS problems show up early.

---

## 5. Resolved inconsistencies and plan-level decisions

These are gaps or conflicts in the source documents. The plan picks one answer and records it here.
Each one is also copied into the `AGENTS.md` Decisions Log.

| ID | Issue found | Decision | Why |
|---|---|---|---|
| D1 | The docs refer to `Idea.md`, but the file is `Idea_1.md` | Rename it to `Idea.md` in 01.1.b | Cross-references must resolve |
| D2 | The GitHub repo is `thrist`; the product is **Thirst** | Rename the repo to `thirst` in 01.1.a (`gh repo rename thirst`); GitHub redirects the old URL | Judges will see the URL; a typo looks careless |
| D3 | TRD §17 needs a **public** repo with an MIT licence; the repo is private | Stay private while building; run a secret scan, then flip to public in 07.10.c | No leaked secrets, and the rule is still met |
| D4 | Spend target: PRD says under $5 by Saturday night, TRD says under $15 for the weekend | Both apply: **$5 by Sat 21:00 is the alarm line**, $15 is the hard cap | They don't conflict; one is a checkpoint |
| D5 | The agent snippet imports `engine.factors`, but TRD §3 lists no `factors.py` | Add `src/engine/factors.py` (loader, factor sets, `table()`) | The agent and `/assumptions` need it |
| D6 | Runtime JSON lives in root `data/`, but SAM `CodeUri: src/` won't package it | Runtime files (`cities.json`, `grid_shares.json`, `powercap_sweep.json`, `sample_forecast.json`) live in `src/engine/data/`. Root `data/` keeps raw downloads and notebook outputs | Lambda must see the files; one copy only |
| D7 | Slot 0 is `floor(submit_ts)` but Base "starts the moment the job was submitted" | Slot 0 has **capacity** `f0 = 1 − minutes_past_hour/60`. Base starts at `submit_ts` and uses `f0` of slot 0. Other slots have capacity 1 | Honest Base, and still one-hour slots |
| D8 | Fragmentation rule (TRD 5.8 step 3b.4) could drop below `work_hours`, or create new gaps forever | After filling the shortest gap, drop the most expensive **block-edge** slots **only while** remaining work ≥ `work_hours`, then re-trim. At most 48 iterations, then fall back to non-pausable | The deadline and work guarantees always hold, and the loop always ends |
| D9 | "Flexible jobs" is not defined | **Flexible** = `1 − J_best ≥ 0.03` (has room to shift). Flexible share = flexible energy / total energy | Matches the "no room to shift" rule; can't be gamed by labelling |
| D10 | Site score with no flexible receipts yet | Score shows **"Not rated yet: needs 1 flexible receipt"**, not 0; part C is still shown | A new lab must not show as worst on the board |
| D11 | The slider switches on the client between 11 plans, but `pareto[]` in TRD §7 only has points | Each `pareto[]` item carries the full plan (schedule, finish, savings ranges, series overlay) | The slider is client-only (TRD §11) |
| D12 | `job_id` must be unique, but the receipts key is `site_id + end_ts#job_id` | Guard item `PK=site_id, SK=job#<job_id>` written in the same `TransactWriteItems` with `attribute_not_exists` | A plain put can't enforce uniqueness across sort keys |
| D13 | The `explain` daily counter needs storage, and TRD says four tables | Counter item in the `plans` table: `PK=quota#YYYY-MM-DD`, atomic `ADD`, TTL 2 days | Stays at four tables |
| D14 | Strands and its deps (pydantic-core is native) would bloat the `api` Lambda | `StrandsLayer` (built from `layers/strands/requirements.txt`) attached only to `ExplainFn` | Smaller `api` cold start, no native build in `api` |
| D15 | SIGSTOP/`killpg` don't exist on Windows | On Windows, and for distributed launchers (`torchrun`, `accelerate launch`, `deepspeed`, `mpirun`, `WORLD_SIZE>1`), the CLI forces non-pausable and says so | Same rule as TRD 6.3, extended |
| D16 | Engine numeric stack | **Pure Python, no numpy** in `src/engine` (48 slots × 3 levels is tiny); the notebook may use pandas | Small Lambda zip, no native wheels |
| D17 | Web language | **TypeScript** (Vite `react-ts` template) | API contract types catch slider and series bugs at build time |
| D18 | Git flow for 3 people in 2.5 days | Trunk-based: short branches `a/…`, `b/…`, `c/…`, PR into `main` with CI green, squash merge, **commit every 1 to 2 h** (TRD §3) | Fast, and history stays clean |
| D19 | The CLI needs `gpus.json` **and** τ/ε/u factors for `--modelled` without network | The CLI bundles copies of `gpus.json`, `factors.json` and `powercap_sweep.json` (if present) in `cli/thirst/data/`; a test asserts each is byte-identical to its `src/engine/data/` source | No drift, works offline |
| D20 | Who records the submit time for anti-cheat | Only the server's `/plan` sets `submit_ts`. The CLI never sends its own submit time. Offline plans (P1 `--offline`) post receipts with `method=unverified` and `plan_id: null` (the only case where a null plan is accepted). They are stored, never scored | TRD §7.4 "Base uses server submit time" |
| D23 | The CLI's `/plan` needs a site's city and cooling | `city`/`cooling` are required **unless** `site_id` is given, in which case they default from the site. The CLI **always** sends `site_id`. A receipt needs `plan.site_id == site_id`; there is no "claim the plan later" path | Unblocks the CLI loop; closes the ownership gap |
| D24 | A receipt page needs the full Base/Best/Actual breakdown | New `GET /receipts/{site_id}/{job_id}` returns the 08 §3.4 response shape | The CLI-printed URL must render |
| D25 | `CUDA_VISIBLE_DEVICES` indices ≠ NVML indices | The runner sets `CUDA_DEVICE_ORDER=PCI_BUS_ID` for the child (unless the user already set it) and maps GPUs by UUID | The meter reads the GPUs the job actually uses |
| D26 | Private sites (`public: false`) | Left off the board; `GET /sites/{id}` returns only name, division and score (no receipts or footprint) | `public` must mean something |
| D21 | HTTP API payload v2 can base64-encode the body | The signature is verified over the **decoded raw bytes** (`isBase64Encoded`) before JSON parsing | Otherwise valid receipts fail verification |
| D22 | `job_id` source | The CLI generates `j_` + 12 random base32 chars (uuid4-derived) at `thirst run` start | Unique without a server round-trip |

---

## 6. Traceability: user story → feature → tasks → tests

| Story | Feature | Tasks | Tests that prove it |
|---|---|---|---|
| US1 plan in < 3 s | F1, F5 | 02.7, 05.5, 06.2, 06.3, 06.4 | `test_planner_*`, `scripts/bench_plan.py` p95 < 2 s, Playwright `plan.spec.ts` |
| US2 slider < 1 s | F3, F4 | 02.7.h (Pareto), 06.3.e, 06.3.f | `Slider.test.tsx` (no network call on change), Playwright timing |
| US3 one-command run | F7 | 04.2, 04.3, 04.4, 04.6 | `test_runner_state_machine`, `test_powercap_restore_on_sigint`, GPU-box manual check 04.6.n |
| US4 receipt | F8 | 02.8, 04.7, 05.7, 06.5 | `test_score_*`, `test_receipt_signature`, `test_receipt_plausibility`, E2E 07.1 |
| US5 site page | F10 | 02.8.f, 05.8, 06.6 | `test_site_score_*`, `SitePage.test.tsx` |
| US6 board | F9 | 02.8.g, 05.8, 05.10, 06.6 | `test_leaderboard_*`, Playwright `board.spec.ts` |
| US7 assumptions | F6 | 02.2, 05.8.d, 06.7, 07.5.b | `test_factors_schema`, `test_assumptions_md_in_sync` |
| US8 sentence → form (P1) | F12 | 05.9, 06.3.j | `test_explain_template_fallback`, `test_explain_quota` |
| US9 India finding (P1) | F13 | 03.*, 06.8 | Notebook runs top to bottom; PNG exists |
| US10 to US12 (P2) | — | 07.11 roadmap | — |

---

## 7. Global Definition of Done

A step is **done** only when all of these hold:

1. The "done when" check passes and its output has been seen (not assumed).
2. Tests were written first and pass in CI. Engine coverage ≥ 90%, CLI and handlers ≥ 80% (`pytest --cov`).
3. No secrets in code or logs; no `print`/`console.log` left in code (the CLI's user-facing output is fine).
4. Every number shown to a user carries a tag (`measured` / `modelled` / `placeholder` / `sourced` / `calibrated`) and an Assumptions link (G5).
5. Any new constant lives in `factors.json` with source and status; nothing is hard-coded in UI or handlers.
6. The PR passes review: `ecc:code-reviewer`, plus `ecc:python-reviewer` or `ecc:typescript-reviewer`/`ecc:react-reviewer`, plus `ecc:security-reviewer` for anything touching `/receipts`, `/sites`, signing, tokens, or `explain`. CRITICAL and HIGH findings are fixed.
7. `AGENTS.md` Changelog has one line for the change.

---

## 8. Engineering workflow (ECC pipeline, scaled to a hackathon)

| Stage | What to do | Tooling |
|---|---|---|
| Plan | This document. For any new feature or change of approach, update the phase file first | `ecc:planner` / `ecc:architect` |
| Test first | Write the failing test from the step's **Tests first** list | `pytest`, `hypothesis`, `vitest`, Playwright · `ecc:tdd-guide` |
| Implement | Smallest code that passes; immutable data (frozen dataclasses, new dicts) | — |
| Review | Self-review the diff, then run the review agents (DoD #6) | `ecc:code-reviewer`, language reviewer, `ecc:security-reviewer` |
| Verify | `make check` (lint, type check, tests, coverage) and CI green | `ecc:verification-loop` before merge, `ecc:quality-gate` at M5 and M6 |
| Commit | Conventional commits (`feat:`, `fix:`, `test:`, `docs:`, `chore:`), every 1 to 2 h | — |

---

## 9. Daily stand-ups (5 minutes, at the gates)

Each person answers three questions: what's green since the last gate, what's blocked, and
what gets cut if we're late. Keep a running **fix list** in `docs/FIXLIST.md`. From Sat 21:00 it is
the only thing anyone works on (TRD §15).
