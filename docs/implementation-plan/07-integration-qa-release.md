# Phase 07 — Integration, QA, docs, demo, submission

> **Status on 11 Oct 2026.**
>
> Done:
> - The integration loop works live (`--modelled`).
> - Writeup [`../WRITEUP.md`](../WRITEUP.md), checklist [`../SUBMISSION.md`](../SUBMISSION.md), test guide [`../USER_TEST_GUIDE.md`](../USER_TEST_GUIDE.md), video script [`../VIDEO_SCRIPT.md`](../VIDEO_SCRIPT.md).
> - The README covers the AI tools and credits.
> - Bench and cost evidence are recorded in [`../FIXLIST.md`](../FIXLIST.md).
>
> Open (people):
> - Video, blog and team registration.
> - Repo public, full-history gitleaks, Cost Explorer screenshot.
> - Submit, then keep the stack running.
>
> Release: the CLI is tagged `cli-v0.3.1`; the whole-project tag (7.7.e) is not yet pushed.

Owner: **all** · Window: **Sat 09:00 to Sun 16:00** · Gates: **M4, M5, M6, M7**
Source: TRD §14 (tests), §15 (schedule), §16 (fallbacks), §17 (submission), PRD §8 (metrics), §10 (video), §12 (releases).

[← Index](README.md)

---

## 7.1 Contract and integration tests (Fri evening to Sat morning, P0)

- **7.1.a Engine → API → web contract.** `make fixtures` regenerates `tests/fixtures/*.json` from the engine. CI fails if (1) the committed fixtures differ from freshly generated ones (`git diff --exit-code tests/fixtures`), or (2) the web type guards reject a fixture (06.1.b).
- **7.1.b CLI ↔ server signing.** Both `tests/cli/test_client.py` and `tests/handlers/test_security.py` load `tests/vectors/hmac.json` (08 §6). A signing change on one side fails the other side's tests.
- **7.1.c Handler integration** (`tests/handlers/test_flow.py`, moto): register a site → plan with `site_id` → build a receipt with the engine's modelled meter → sign → post → `GET /sites/{id}` shows the receipt and the score → `GET /leaderboard` shows the site. One test, the whole loop, no AWS.
- **7.1.d Live E2E** (`scripts/e2e_live.sh`, marked `aws`): the same flow against the deployed API with a throwaway site `"CI Probe"`, deleted afterwards by `seed.py --delete-site <id>` (5.10.e). **Never** use `--wipe-simulated` here; it would delete the seeded demo sites. The receipt must appear on the board **within 1 minute** (PRD §6.2.7, TRD §14).

---

## 7.2 Overnight receipt verification (Sat 09:00, P0, gate M4)

- **7.2.a** On the GPU box: `tmux attach -t thirst`. Read the final receipt output. If it says "queued", run `thirst sync`.
- **7.2.b** Check `nvidia-smi -q -d POWER`: the current limit equals the original. If not, the restore failed: run `thirst doctor --restore` and **file a P0 bug**.
- **7.2.c** Open the site page on the live URL. Check that the receipt is listed, Capture is shown (or "no room"), the energy tag is **measured**, and the score shows the Provisional tag.
- **7.2.d** Archive the evidence: `docs/overnight_receipt.txt` (terminal output), screenshots of the plan line, the receipt and the site page into `docs/media/`, and the `~/.thirst/logs/<job_id>.log` tail.
- **7.2.e** If anything is missing, apply the M4 fallback straight away: a 1-hour job, forced to start now, recorded on video.

---

## 7.3 Test matrix (TRD §14, all must be green by M5)

| TRD test | Where | Owner | Status check |
|---|---|---|---|
| Stull 20 °C / 50% → 13.7 ± 0.1 | `tests/engine/test_wetbulb.py` | B | CI |
| COP clip in [1.5, 6] for T in [0, 50] | `tests/engine/test_cooling.py` | B | CI |
| Grid shares sum to 1; yearly CI = 0.727 ± 0.005 | `tests/engine/test_grid.py` | B | CI |
| Flat intensities: Best = Base, no room | `tests/engine/test_planner.py` | B | CI |
| Deadline property, 500 random inputs | `tests/engine/test_planner.py` | B | CI (`--hypothesis-seed` printed) |
| Idle cost: a 10 h gap costs more | `tests/engine/test_planner.py` | B | CI |
| Capture in [0, 1] | `tests/engine/test_score.py` | B | CI |
| Base energy = measured run energy at 100% | `tests/engine/test_score.py` | B | CI |
| Receipt plausibility rejects energy above the GPU limit | `tests/handlers/test_api_receipts.py` | A | CI |
| Signature rejects a changed body and an old timestamp | `tests/handlers/test_api_receipts.py` | A | CI |
| Power cap restore after Ctrl-C | `tests/cli/test_powercap.py` (fake) + 4.6.h manual on GPU | B | CI + manual log |
| End to end: receipt on the board within 1 minute | `scripts/e2e_live.sh` | A | manual Sat |
| Phone: all pages usable at 360 px | `web/e2e/mobile.spec.ts` | C | CI (mocks) + live |
| Cost under $5 by Saturday night | Cost Explorer screenshot | A | manual Sat 21:00 |

Coverage targets (DoD #2): engine ≥ 90%, CLI ≥ 80%, handlers ≥ 80%, web components ≥ 70% (UI is covered more by E2E).

---

## 7.4 Edge cases and failure-mode checklist (Sat 12:00 to 17:00, P0)

Walk through each row and record the result in `docs/FIXLIST.md` (pass / fixed / accepted with a note).

| # | Scenario | Expected behaviour | Where handled |
|---|---|---|---|
| 1 | Deadline too soon for the work | 422 with the earliest feasible finish; the form shows it in plain words | 02.7 test 4, 05.5 |
| 2 | Deadline beyond 48 h | Planned within 48 h, note shown | 02.1.c |
| 3 | Submitted at hh:59 | Slot 0 capacity ≈ 0.02, plan still valid | D7, 02.1 |
| 4 | Open-Meteo down for 3 hours | `/plan` uses the last rows plus the sample, with a "cached forecast" banner | 05.4, 05.5 test 4 |
| 5 | DynamoDB throttled or error | 503 `try_again`, logged, no stack trace | 05.5.e |
| 6 | Bedrock not approved or slow | Template explanation, `source: template` | 05.9 |
| 7 | No NVIDIA GPU | `--modelled`, receipt tagged Modelled, no C points | 04.3.e |
| 8 | Power limit refused | Uncapped, `cap_applied: false` shown on the receipt | 04.4 test 3 |
| 9 | Laptop GPU blocks `-pl` | Clock-lock fallback | 04.4 test 4 |
| 10 | `torchrun` job with `--pausable` | Forced non-pausable, message printed | 04.6 test 7 |
| 11 | Ctrl-C while paused | SIGCONT → SIGTERM → restore → receipt `interrupted` | 04.6 test 3 |
| 12 | `kill -9` of the CLI | Next `thirst doctor --restore` restores from the marker | 04.4.d |
| 13 | Machine reboot mid-job | Limits reset by the driver; the receipt is lost (documented limitation); the marker is cleaned up on the next run | Known limitation in README |
| 14 | Network down at the end of the job | Receipt in the outbox, `thirst sync` later | 04.2 test 4 |
| 15 | Clock skew > 10 minutes | 401 `stale_timestamp`; `doctor` warns earlier | 04.8.c, 05.7 |
| 16 | Duplicate receipt post | 409; `sync` treats it as done | 05.7 test 5, 04.2 test 5 |
| 17 | Faked huge energy | 422 `implausible_energy` | 05.7 test 3 |
| 18 | Someone else's `plan_id` | 403 | 05.7 test 4 |
| 19 | Site name with HTML or script | Stored as text, rendered escaped by React | 05.6, React default |
| 20 | Body > 8 KB on `/plan` or > 64 KB on `/receipts` | 413 | 05.5, 05.7 |
| 21 | A burst of 100 requests per second | API Gateway 429; the UI shows "Busy, try again" | 5.1.a throttling |
| 22 | New site, no receipts | "Not rated yet" (not 0, not last) | D10 |
| 23 | Plan TTL expired before the receipt (job > 14 days) | 404 `plan_not_found`; documented, not expected in v0 | 05.7 test 4 |
| 24 | Browser time zone not IST | The form still sends IST | 06.2.d |

---

## 7.5 Docs (Sat 17:00 to 21:00, P0)

- **7.5.a `README.md`**, sections in this order (TRD §17):
  1. one-line pitch and the live URL;
  2. the problem (3 lines, with "person-days");
  3. the Step 0 finding (PNG);
  4. **quick start**: CLI install (`pip install ./cli`), `thirst register`, `thirst run --modelled -- python -c "…"`, and the web URL;
  5. architecture diagram (TRD §2) and the AWS services list (Lambda, API Gateway HTTP API, DynamoDB, EventBridge Scheduler, Amplify Hosting, Bedrock, Strands Agents SDK, SAM CLI, SSM Parameter Store, CloudWatch);
  6. how to deploy (`make deploy`);
  7. measured vs modelled, and known limitations (Idea §11);
  8. **AI coding tools used** (required);
  9. credits and licences: Open-Meteo, CSEP, Ember, CEA, WRI Aqueduct, Recharts, nvidia-ml-py, Strands, Powertools;
  10. MIT licence.
- **7.5.b `ASSUMPTIONS.md`** is generated: `scripts/gen_assumptions.py` renders `engine.factors.table()` to Markdown (`make assumptions`). CI test `test_assumptions_md_in_sync` fails if the committed file differs.
- **7.5.c `SPEC.md`**: Thirst Score spec v0.2 (Idea §7, TRD 5.9) with the J formula, Capture, the no-room rule, the fairness rule, site score parts, badges, divisions, anti-cheating, stress weights, and a "how to change a weight" section.
- **7.5.d `AGENTS.md`**: current state, file map, gotchas found during the build, and the changelog brought up to date.
- **7.5.e** Run `ecc:doc-updater` over the README and `docs/` to check the commands still work and the links resolve.

---

## 7.6 Clean-machine test (Sat 17:00 to 18:00, P0, gate M5)

Done by the person who **didn't** write the CLI, on a machine that has never had the repo (a spare laptop, or a fresh `python:3.12` container plus a browser):

1. `git clone https://github.com/Neal006/thirst && cd thirst` (start a timer).
2. Follow **only** the README quick start. Write down every place you have to guess.
3. `pip install ./cli` → `thirst doctor` (expect ✗ on the GPU items, ✓ on the API).
4. `thirst register --name "Clean Machine Test (simulated)" --city Pune --cooling room_ac --gpus 1`.
5. `thirst run --modelled --hours 0.1 --deadline "<now + 1 h>" --now -- python -c "import time; time.sleep(60)"`.
6. Open the live URL on a phone → Leaderboard → find the site → see the receipt.
7. Stop the timer. **Must be under 15 minutes** (PRD §8.1). Every guess from step 2 becomes a README fix.
8. Clean up: `python scripts/seed.py --delete-site <site_id>` (5.10.e). Record the timer result in `docs/FIXLIST.md`.

---

## 7.7 Quality gate and code freeze (Sat 21:00 to Sun 11:00)

- **7.7.a Sat 21:00 to 23:00: fix list only, no new features** (TRD §15). Each fix is a PR with a test.
- **7.7.b** Run the `ecc:quality-gate` skill and `ecc:verification-loop` on `main`: lint, types, tests, coverage, `sam validate --lint`, web build, Lighthouse, secret scan.
- **7.7.c** Final `ecc:security-reviewer` pass over the whole diff since `engine-m1`.
- **7.7.d Sun 08:00:** check the schedule page for the exact deadline (PRD §11). Move everything earlier if needed.
- **7.7.e Sun 11:00 code freeze (M6):** `git tag v0.3.0 && git push --tags`. Final deploy from the tag; `scripts/smoke.sh` green; live URL checked signed-out on a phone. After the freeze, only docs and video changes go in.

---

## 7.8 Demo video (Sun 11:00 to 14:00, P0, under 3:00)

Storyboard from PRD §10. Collect the assets **before** recording:

| Time | Shot | Asset ready by | Voice line |
|---|---|---|---|
| 0:00 to 0:20 | Credited footage of a water tanker queue or dry reservoir, then the GPU lab | Sat (C finds openly licensed footage, credits it) | "Every GPU hour uses water twice: at the building and at a coal plant. In Chennai, that water is scarce." |
| 0:20 to 0:40 | `docs/india_finding.png` | Fri 13:00 | The Step 0 headline in one sentence |
| 0:40 to 1:30 | Live URL in the address bar → form → Plan → move the slider | Sat 17:00 | "Not just when, but how fast. Our measured sweep: 85% power costs X% speed and saves Y% energy." (X, Y from `powercap_sweep.json`) |
| 1:30 to 2:00 | Terminal: the real overnight receipt | Sat 09:00 (7.2.d) | "Energy measured from the GPU. Water modelled from it, and labelled." |
| 2:00 to 2:25 | Leaderboard D1 → site page | Sat | "We score the choice, not the climate, so a 4-GPU lab can beat a giant's lab." |
| 2:25 to 2:50 | Architecture slide → AWS console: Lambda, DynamoDB, Amplify, EventBridge schedule → Strands code | Sat evening | Name **every** AWS service out loud |
| 2:50 to 3:00 | Assumptions page | Sat | "Every modelled number is labelled. The spec is open. Labs first." |

- **7.8.a** Record the screen at 1080p with OBS. Voice is recorded separately, then edited (DaVinci Resolve or Clipchamp). Add captions (judges may watch muted).
- **7.8.b** Hard limit: **under 3:00**, checked in the exported file's metadata.
- **7.8.c** Upload to YouTube as **unlisted**. Open it in a private window, signed out, to check it plays (TRD §17).
- **7.8.d** Never show tokens, the `config.toml` contents, the AWS account id, or billing pages with personal details. Blur them if needed.

---

## 7.9 Writeup and Builder Center blog (Sun 11:00 to 14:00, P0)

- **7.9.a** Writeup structure (TRD §17): problem → what we built → where AWS fits (each service and why) → measured vs modelled and limits → **AI tools used** → links (repo, live URL, video).
- **7.9.b** Blog: a 900 to 1,200 word version with the India finding chart, the sweep numbers, one real receipt, and the honest limits. Publish it and link it from the README and the submission.
- **7.9.c** Every number in the writeup and the blog is a range or a labelled measurement, matching the app (Idea §12, "no exact litre savings").

---

## 7.10 Submission checklist (Sun 14:00 to 16:00, P0, gate M7)

- [ ] **7.10.a** Every team member is registered and on the team (PRD §11).
- [ ] **7.10.b** Secret scan of the whole history: `gitleaks detect --source . --log-opts="--all"` is clean. Check `samconfig.toml` and notebooks too.
- [ ] **7.10.c** Flip the repo to **public** (D3): `gh repo edit Neal006/thirst --visibility public --accept-visibility-change-consequences`. The MIT `LICENSE` is present. Commits are only from 8 Oct onwards.
- [ ] **7.10.d** The README has the AI coding tools used, and credits and licences.
- [ ] **7.10.e** The live URL works signed-out and on a phone.
- [ ] **7.10.f** The video is under 3:00, unlisted, opens signed-out, and has AWS on screen and named out loud.
- [ ] **7.10.g** The writeup has all sections; the blog is published and linked.
- [ ] **7.10.h** Billing checked; the screenshot is saved.
- [ ] **7.10.i** Submit, then re-open the submission page to confirm it saved.
- [ ] **7.10.k** PRD §8.1 metrics, each with evidence: `docs/bench_plan.txt` p95 < 2000 ms · `powercap_sweep.json` measured for the box's GPU · ≥ 1 receipt with method `nvml_*` on the board · the 7.6 timer < 15 min recorded in FIXLIST · a Cost Explorer screenshot dated Sat showing < $5 · the video length < 3:00.
- [ ] **7.10.j** Post-submit: leave the stack running for judging. **Don't** wipe data. Keep the budgets alerts on.

---

## 7.11 After the hackathon (roadmap, P2, from PRD §12)

| Release | When | Work items (each becomes its own plan file) |
|---|---|---|
| **v0.4** | +2 weeks | Fit WUE vs wet-bulb to Li et al. (replace `wue_a/b` placeholders); CSEP or Ember hourly mix **per grid region** and σ_grid per region's coal basins (TRD 5.5); transmission loss factor from CEA; checkpoint-based pause for distributed jobs; lifecycle carbon toggle; sensitivity chart (low/high sets); share card PNG (US10); spatial comparison (US11) |
| **v0.5** | +6 weeks | Slurm plugin (`SPANK` or a `sbatch` wrapper); company page (multi-site org); materialised leaderboard (DynamoDB stream → board table); first 10 college labs onboarded; wall-meter mode (US12) |
| **v1.0** | +3 months | "Thirst Verified" spot audits; BRSR Core export; spec v1 published for comment; part B (facility efficiency) from metered PUE/WUE; proper accounts instead of site tokens; key rotation for the server secret |

Operational follow-ups (move to `AGENTS.md` Current State after the hackathon):

- Rotate the server secret, and support a secret version prefix in the token (`v1.`) so rotation doesn't break existing sites.
- Move from scan-on-read to a materialised board before 100 sites.
- Re-check every factor marked **verify** and every `placeholder`.
- Watch the Amplify and Bedrock costs monthly; keep the budgets.
