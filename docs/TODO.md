# Thirst: what is left to do

Status on **2026-10-11, 15:30 IST**:
- The site and API are live on AWS. CI, Deploy and Publish CLI workflows are green.
- PRs #1–#14 are merged, and `thirst` 0.3.1 is on PyPI.
- The `feat/web-ui-accessibility` branch finishes every code and docs task that needed no person, hardware or AWS access (see §7). Its PR description is [`pr/ux-overhaul.md`](pr/ux-overhaul.md).
- Submission window: **Sun 11 Oct 14:00–16:00 IST**.

**This list only holds work that is still open.** Each item says who can do it and why it is still open. Everything already done is in §7.

Priority:
- **P0**: needed to submit.
- **P1**: makes the demo honest and strong.
- **P2**: after the hackathon.

Related docs:
- [`SUBMISSION.md`](SUBMISSION.md): the checklist with evidence
- [`WRITEUP.md`](WRITEUP.md): the submission text
- [`USER_TEST_GUIDE.md`](USER_TEST_GUIDE.md): end-to-end test as a normal user
- [`VIDEO_SCRIPT.md`](VIDEO_SCRIPT.md): the 3-minute video
- [`FIXLIST.md`](FIXLIST.md): problems found while testing, and the metrics evidence
- issue #5: the running tracker

---

## 1. Submission today (P0, people only)

These need a team member's own accounts or a decision only the team can take.

| # | Task | Who | Time | Done when |
|---|---|---|---|---|
| 1.2 | Every team member registered and on the team on the hackathon site | each member | 5 min | team page lists everyone |
| 1.3 | Record the video from [`VIDEO_SCRIPT.md`](VIDEO_SCRIPT.md) (< 3:00, captions, AWS named out loud). Record on the site version the script describes (see its top note) | 1 person | 90 min | exported file shows < 3:00 |
| 1.4 | Upload to YouTube as **unlisted**, then open it in a private window, signed out | same | 10 min | it plays signed out |
| 1.5 | Write and publish the Builder Center blog (900–1,200 words, from `WRITEUP.md`) | 1 person | 60 min | public URL |
| 1.6 | Put the video and blog links in `docs/WRITEUP.md` (top table), `docs/SUBMISSION.md` and the README | anyone | 5 min | links work |
| 1.7 | Delete the PyPI token that was pasted in chat (pypi.org → Account settings → API tokens) | PyPI owner | 2 min | token gone |
| 1.9 | Cost Explorer screenshot (1–11 Oct, $0.00 so far). Hide the account id. | AWS owner | 3 min | PNG saved |
| 1.10 | Make the repo public: `gh repo edit Neal006/Thirst --visibility public --accept-visibility-change-consequences` | repo owner | 1 min | repo opens signed out |
| 1.11 | Fill in and submit the form (links in `SUBMISSION.md`), then re-open it | team lead | 10 min | the submission page shows the saved entry |
| 1.12 | After submitting, leave everything running: don't delete the stack, don't wipe data, keep the budget alerts | everyone | — | site still up during judging |
| 1.13 | Decide when to merge `feat/web-ui-accessibility`. Merging deploys the new look. If the video was recorded on the old site, merge after recording, or re-record the shots that show it | team lead | 5 min | PR merged, Deploy and its new `e2e` job green |
| 1.14 | Formal clean-machine timer (plan 7.6): a second person, a machine that never had the repo, the **live** API, a phone for the last step. A local rehearsal took 70 s (FIXLIST) but does not replace this | 1 person | 15 min | time recorded in `FIXLIST.md` |

---

## 2. Real data: the biggest honesty gap (P1)

These need a desktop NVIDIA GPU or someone to pull and check public datasets. They change live numbers, so they also need a fixtures refresh (`make fixtures`) and a deploy.

Today **18 of 57 factors are placeholders**. The worst is the power-cap curve: every plan picks 70%, all 11 trade-off points are identical (the planner hides the slider and says why), and the "18–21% less" ranges come mostly from placeholder numbers.

| # | Task | Who | Needs | Done when |
|---|---|---|---|---|
| 2.1 | **Power-cap sweep** on a desktop NVIDIA GPU: `pip install "thirst[sweep]"` then `thirst sweep --out src/engine/data/powercap_sweep.json`. Run it twice: the second run is now combined with the first (median per level, plan 4.5.d) | GPU owner | Linux + desktop RTX/A-series, root for power limits, ~30 min per run | `powercap_sweep.json` has measured rows, the `tau`/`eps` tags say `measured`, plans stop always picking 70%, and the slider appears |
| 2.3 | One **real overnight receipt** with method `nvml_*` from a public real lab (plan 4.9) | GPU owner | 2.1 machine | the leaderboard shows a non-simulated site with a measured receipt |
| 2.4 | Real national grid mix by hour from the CSEP tracker → `grid_shares.json` (plan 1.7.b) | data person | 1–2 h | `grid_shares.json` status `sourced` |
| 2.5 | City water-stress categories from WRI Aqueduct → `cities.json` (plan 1.7.d) | data person | 1 h | status `sourced` |
| 2.6 | Other placeholders on `/assumptions` (idle power = 10% of max, etc.): source or measure each | data person | — | placeholder count goes down |
| 2.7 | Phase 03 "India finding" notebook: does midday solar beat cool nights? Export `docs/india_finding.png`. Needs 2.4 first, or it would only restate placeholder data | data person | 2–3 h | chart in repo, used in the video and blog |

After any data change: run `make fixtures` (or `python scripts/gen_fixtures.py`) and commit the fixtures. CI fails if they are stale.

Notes for 2.1:
- Laptop GPUs usually block power-limit changes. Our RTX 3050 Laptop reports `power.limit [N/A]`.
- The 31 GPU rows (PR #8) only give each GPU's maximum power. They do not replace the sweep.

---

## 3. AWS (P1)

These need the AWS account owner, or change the live data path while judges are using it.

| # | Task | Who | Done when |
|---|---|---|---|
| 3.1 | **Bedrock is blocked account-wide** (every model returns "Operation not allowed", and the console playground fails too). Open an AWS Support case: "Bedrock model access NOT_AUTHORIZED on account 857229543886, ap-south-1". | AWS owner | Playground answers |
| 3.2 | Then: fill in the Anthropic use-case form if you want Claude models, and run one playground prompt (this also completes the 5th credit task) | AWS owner | +$20 credit task done |
| 3.3 | Set `BedrockModelId=<model or inference profile id>` in `samconfig.toml` `parameter_overrides`, merge to `main` (auto-deploys) | dev, after 3.1 | `POST /explain {"plan_id": …}` returns `"source": "agent"` |
| 3.4 | Confirm the SNS alarm email (check the inbox for "AWS Notification – Subscription Confirmation") | AWS owner | subscription shows Confirmed |
| 3.6 | Leaderboard reads one Query per public site on a cache miss. Precompute a per-division item when receipts arrive. Left until after judging: it changes the DynamoDB write path of the live API (it is also the v0.5 "materialised leaderboard" in plan 7.11) | dev | one read per board load |
| 3.7 | Tag the whole-project release for submission: `git tag v0.3.1 && git push origin v0.3.1` (plan 7.7.e). The CLI already has `cli-v0.3.1` | repo owner | tag on GitHub |
| 3.8 | After the next merge, check that the Deploy run shows no Node 20 warning and that the new `e2e` job runs (both changed on `feat/web-ui-accessibility`, not yet run on GitHub) | dev | warning gone, `e2e` job green |

---

## 4. CLI

| # | Task | Who | Why still open |
|---|---|---|---|
| 4.1 | **Release 0.3.2** so `pip install thirst` gets the fixes on `feat/web-ui-accessibility` (TODO 4.1.a–g and 4.2 items in §7). The version is already 0.3.2 on the branch (`cli/pyproject.toml`, `cli/thirst/__init__.py`). After the merge: `git tag cli-v0.3.2 && git push origin cli-v0.3.2` | repo owner | a tag push is the owner's call, after the branch merges |
| 4.2 | Per-run restore markers. Today one shared `~/.thirst/restore.json` is used, and a second run refuses to start while it exists (exit 5), so two runs cannot fight over it | dev + GPU owner | safety-critical restore code: change it only when it can be tested on a real GPU (4.3) |
| 4.3 | **Hardware checks on a real Linux GPU box** (plan 1.8 / 4.6.h): real NVML power limit and restore, `--fallback-clocks` (`MIN_LOCK_MHZ=210` is an assumption), SIGSTOP/SIGCONT on a live CUDA process, Ctrl-C mid-run restores the limit, an SSH disconnect restores the limit, and the laptop `[warn]` line in `thirst doctor` on a real laptop GPU | GPU owner | needs the hardware |
| 4.4 | Plan 4.11: `thirst plan/run --offline` plans from bundled data | dev | needs the engine packaged with the CLI and an `unverified` receipt path. P2 |

---

## 5. Website

| # | Task | Priority | Why still open |
|---|---|---|---|
| 5.1 | 6.3.j "Describe your job in one sentence" box | P1 after 3.1 | needs Bedrock. Without it, `/explain {text}` only returns a hint |
| 5.2 | 6.8 India finding section on the home page | P1 | needs 2.7 |
| 5.3 | 6.10 Lighthouse report: Chrome DevTools → Lighthouse on `/` and `/plan`, mobile, on the **live** site, and save it in `docs/` | P1 | needs the live site from a normal network |

---

## 6. Model limits we state but have not fixed (P2)

Design changes to the model, each worth its own plan after the hackathon:
- Timing uses the **average** grid mix per hour. India's marginal plant is often coal at any hour, so savings from timing alone may be smaller. The app says so.
- A pausable plan uses only each hour's cheapest level. A tight deadline falls back to a non-pausable plan (`pause_no_room`).
- `sigma_grid = sigma_site` (one stress weight for both waters).
- Grid "Option B" scales solar by radiation relative to the window mean, so a uniformly cloudy day looks like a clear one.
- Jobs over 47 h can exceed the 48-slot window when submitted mid-hour.

---

## 7. Done (for the record)

### On `feat/web-ui-accessibility` (2026-10-11, details in [`implementation-plan/09-ux-overhaul.md`](implementation-plan/09-ux-overhaul.md))

**Submission**
- 1.8 Full-history secret scan: `gitleaks detect --source . --log-opts="--all"` (gitleaks 8.28.0, `.gitleaks.toml`) over all 54 commits on every branch, plus the working tree: **no leaks found**. Evidence: [`gitleaks_full_history.txt`](gitleaks_full_history.txt).

**Real data tooling**
- 2.2 A second `thirst sweep` run is combined with the first: median `tau`, `eps`, `u` and `p_idle_w` per level, every run kept in `history`, raw rows tagged by run. A run with a different workload replaces instead of mixing. The engine reads the file unchanged.

**AWS / CI**
- 3.5 GitHub Actions moved to Node 24 versions: `checkout@v5`, `setup-python@v6`, `setup-node@v5`, `setup-uv@v7`, `setup-sam@v3`, `configure-aws-credentials@v6`, `upload-artifact@v6`, `download-artifact@v7`, `gitleaks-action@v3`. Every input the workflows use exists in the new versions.
- 5.5 Deploy now runs the read-only Playwright + axe suite against the live site after each deploy (new `e2e` job, report kept as an artifact).

**CLI** (each with tests)
- 4.1.a `thirst doctor` on a laptop GPU prints `[warn]` with "use `thirst run --no-cap`", not a misleading `[FAIL]`.
- 4.1.b `thirst plan` prints the full Assumptions URL.
- 4.1.c `thirst run --dry-run` uses the plan's exact start and finish.
- 4.1.d `--modelled` uses the detected GPU when `--gpu-model` and `--gpus` are left out.
- 4.1.e Short jobs show Wh, mL and g instead of `0.00 kWh` and `0.0 L`.
- 4.1.f A `--private` site's receipt prints no link (it would 404). `config.toml` remembers `public`.
- 4.1.g A modelled receipt says "modelled at 70% (plan level)" instead of "uncapped".
- 4.2 `THIRST_TOKEN` no longer reaches the user's command.
- 4.2 The `/plan` answer is checked before use: a bad reply is one plain error, not a traceback.
- 4.2 `nvidia-smi` and `sudo` run by their full paths.
- 4.2 `thirst sweep` sets `CUDA_DEVICE_ORDER=PCI_BUS_ID` so torch and NVML measure the same GPU.
- 4.2 The output tee survives a failing log (disk full) and keeps draining, so the job never blocks.
- 4.2 `POST /sites` (register) is retried with backoff like every other call (now tested).
- 4.2 CLI tests use `timezone.utc`, so they run on Python 3.10 like the CLI.
- 4.1 (prep) CLI version bumped to 0.3.2 in `cli/pyproject.toml` and `cli/thirst/__init__.py`, so the release is one tag push.

**Website**
- 5.4 The phone jump-link e2e waits for the tables to render.
- 5.6 README screenshots and SVGs refreshed in the new palette, plus `actions.png` and `cities.png`.
- 5.7 The slider is hidden while every Pareto point is identical, with a note and a `placeholder` chip.
- The UX overhaul itself: plan views, the "Run this plan" box, share links, recent plans, the Cities page, the glossary, the Monsoon theme, and new e2e specs for all of it.

### Earlier on 2026-10-11
- PR #6: React review leftovers, code-splitting (810 → 249 kB), no mock chunk in production
- PR #7: CLI review fixes (receipt saved before sending, Ctrl-C while sending keeps it for `thirst sync`, SIGHUP handled, SIGCONT after an error while paused, a failed cap restore exits 5)
- PR #8: 31 GPU rows with sources, including the RTX 3050 Laptop (detected correctly on our laptop)
- PR #9: Playwright e2e. The first run found contrast, list-markup and tap-target bugs, now fixed. Live: 74 pass, 4 skip, 1 flaky.
- Deploy fixed: the OIDC role trusts the immutable subject claim (D38)
- The home page says `pip install thirst` instead of the GitHub install line
- `thirst` 0.3.1 published to PyPI by GitHub Actions (Trusted Publishing, no token)
- `ASSUMPTIONS.md` is generated from the live factor table (`make assumptions`, checked by a test). `SPEC.md` has the full score rules, and `web/README.md` replaces the Vite boilerplate
- Two end-to-end user tests against the live site, with both test labs deleted
- Docs PRs merged (#10, #11, #13, #14)
