# Thirst: what is left to do

Status on **2026-10-11, 13:00 IST**:
- The site and API are live on AWS.
- CI and the Deploy workflow are green.
- PRs #1–#9 are merged, and `main` is the only branch.
- Submission window: **Sun 11 Oct 14:00–16:00 IST**.

Each item says who can do it, how long it takes, and how you know it is done. Priority:
- **P0**: needed to submit.
- **P1**: makes the demo honest and strong.
- **P2**: after the hackathon.

Related docs:
- [`SUBMISSION.md`](SUBMISSION.md): the checklist with evidence
- [`WRITEUP.md`](WRITEUP.md): the submission text
- [`USER_TEST_GUIDE.md`](USER_TEST_GUIDE.md): end-to-end test as a normal user
- [`VIDEO_SCRIPT.md`](VIDEO_SCRIPT.md): the 3-minute video
- issue #5: the running tracker

---

## 1. Submission today (P0, people only)

| # | Task | Who | Time | Done when |
|---|---|---|---|---|
| 1.1 | Merge the open docs PRs (#10 and the one that adds this file) | anyone with write access | 2 min | `main` has `docs/WRITEUP.md`, `docs/TODO.md`, `docs/USER_TEST_GUIDE.md`, `docs/VIDEO_SCRIPT.md` |
| 1.2 | Every team member registered and on the team on the hackathon site | each member | 5 min | team page lists everyone |
| 1.3 | Record the video from [`VIDEO_SCRIPT.md`](VIDEO_SCRIPT.md) (< 3:00, captions, AWS named out loud) | 1 person | 90 min | exported file shows < 3:00 |
| 1.4 | Upload to YouTube as **unlisted**; open it in a private window, signed out | same | 10 min | it plays signed out |
| 1.5 | Write and publish the Builder Center blog (900–1,200 words, from `WRITEUP.md`) | 1 person | 60 min | public URL |
| 1.6 | Put the video and blog links in `docs/WRITEUP.md` (top table) and in the README | anyone | 5 min | links work |
| 1.7 | Delete the PyPI token that was pasted in chat (pypi.org → Account settings → API tokens) | PyPI owner | 2 min | token gone |
| 1.8 | Full-history secret scan: `gitleaks detect --source . --log-opts="--all"` (or Docker `zricethezav/gitleaks`) | anyone | 5 min | "no leaks found" |
| 1.9 | Cost Explorer screenshot (1–11 Oct, $0.00 so far). Hide the account id. | AWS owner | 3 min | PNG saved |
| 1.10 | Make the repo public: `gh repo edit Neal006/Thirst --visibility public --accept-visibility-change-consequences` | repo owner | 1 min | repo opens signed out |
| 1.11 | Fill in and submit the form (links in `SUBMISSION.md`), then re-open it | team lead | 10 min | the submission page shows the saved entry |
| 1.12 | After submitting, leave everything running: don't delete the stack, don't wipe data, keep the budget alerts | everyone | — | site still up during judging |

---

## 2. Real data: the biggest honesty gap (P1)

Today **18 of 57 factors are placeholders**. The worst is the power-cap curve:
- Every plan picks 70%.
- All 11 trade-off points are identical, so the water/carbon slider changes nothing.
- The "18–21% less" ranges come mostly from placeholder numbers.

| # | Task | Who | Needs | Done when |
|---|---|---|---|---|
| 2.1 | **Power-cap sweep** on a desktop NVIDIA GPU (see 2.1 notes): `pip install "thirst[sweep]"` then `thirst sweep --out src/engine/data/powercap_sweep.json` | GPU owner | Linux + desktop RTX/A-series, root for power limits, ~30 min | `powercap_sweep.json` has measured rows; `tau`/`eps` tags say `measured`; plans stop always picking 70% |
| 2.2 | Run 2.1 twice and use the per-level median (plan 4.5.d; today a second run replaces the first) | dev | 2.1 | code + test |
| 2.3 | One **real overnight receipt** with method `nvml_*` from a public real lab (plan 4.9) | GPU owner | 2.1 machine | the leaderboard shows a non-simulated site with a measured receipt |
| 2.4 | Real national grid mix by hour from the CSEP tracker → `grid_shares.json` (plan 1.7.b) | data person | 1–2 h | `grid_shares.json` status `sourced` |
| 2.5 | City water-stress categories from WRI Aqueduct → `cities.json` (plan 1.7.d) | data person | 1 h | status `sourced` |
| 2.6 | Other placeholders on `/assumptions` (idle power = 10% of max, etc.): source or measure each | data person | — | placeholder count goes down |
| 2.7 | Phase 03 "India finding" notebook: does midday solar beat cool nights? Export `docs/india_finding.png` | data person | 2–3 h | chart in repo; used in the video and blog |
| 2.8 | After any data change: `make fixtures` (or `python scripts/gen_fixtures.py`), then commit the fixtures; CI fails if they are stale | dev | — | CI green |

Notes for 2.1:
- Laptop GPUs usually block power-limit changes. Our RTX 3050 Laptop reports `power.limit [N/A]`.
- The 31 new GPU rows (PR #8) only give each GPU's maximum power. They do not replace the sweep.

---

## 3. AWS (P1)

| # | Task | Who | Done when |
|---|---|---|---|
| 3.1 | **Bedrock is blocked account-wide** (every model returns "Operation not allowed"; the console playground fails too). Open an AWS Support case: "Bedrock model access NOT_AUTHORIZED on account 857229543886, ap-south-1". | AWS owner | Playground answers |
| 3.2 | Then: fill in the Anthropic use-case form if you want Claude models, and run one playground prompt (this also completes the 5th credit task) | AWS owner | +$20 credit task done |
| 3.3 | Set `BedrockModelId=<model or inference profile id>` in `samconfig.toml` `parameter_overrides`, merge to `main` (auto-deploys) | dev | `POST /explain {"plan_id": …}` returns `"source": "agent"` |
| 3.4 | Confirm the SNS alarm email (check the inbox for "AWS Notification – Subscription Confirmation") | AWS owner | subscription shows Confirmed |
| 3.5 | Bump GitHub Actions to Node 24 versions (`actions/checkout@v5`, `setup-node@v5`, `setup-python@v6`, `configure-aws-credentials@v5`, …): Deploy logs warn that Node 20 is deprecated | dev | no warning |
| 3.6 | Leaderboard reads one Query per public site on a cache miss; precompute a per-division item when receipts arrive | dev | one read per board load |
| 3.7 | Tag the release: `git tag v0.3.0 && git push --tags` (plan 7.7.e) | dev | tag on GitHub |

---

## 4. CLI

### 4.1 Problems found in today's live walkthrough (P1, small)

| # | What happens | What it should do |
|---|---|---|
| 4.1.a | `thirst doctor` on a laptop GPU says **"The NVIDIA driver reported an error while reading the GPU"** and exits 1. The real cause is that the GPU does not allow power-limit changes (`nvidia-smi` shows `[N/A]`). | Say "This GPU does not let software change its power limit (common on laptops). Jobs still run and are measured: use `--no-cap`." Count it as a warning, not a failure. |
| 4.1.b | `thirst plan` ends with `Assumptions: /assumptions`, a relative path a user can't click | Print the full URL, `https://main.dzxkrtlc7xqfx.amplifyapp.com/assumptions` (the `DEFAULT_WEB_URL`) |
| 4.1.c | `thirst run --dry-run` lists `12:00 start … 18:00 planned end` while the plan line says `start 12:47 … done by 17:14` | Show the same times, or label them as hour slots |
| 4.1.d | `--modelled` refuses to run without `--gpu-model` and `--gpus` even when a GPU is detected; the README example `thirst run --modelled …` leaves them out | Use the detected GPU when there is one, and fix the README example |
| 4.1.e | A 2-minute job prints `Energy 0.00 kWh`, `Water 0.0 L` | Below 0.1 kWh, show Wh and mL |
| 4.1.f | For a `--private` site the receipt prints a web link that returns 404 (private sites hide receipts, D26) | Don't print the link for private sites, or say it is private |
| 4.1.g | PyPI has 0.3.0, published **before** the PR #7 fixes (receipt saved before sending, SIGHUP, …) | Release 0.3.1 (4.3.a) |

### 4.2 Review leftovers (P1/P2)

- Per-run restore markers and marker validation. Today one shared `~/.thirst/restore.json` is used.
- Don't pass `THIRST_TOKEN` into the user's command environment.
- Validate server responses more strictly before using them.
- Call `nvidia-smi` by absolute path.
- Set `CUDA_DEVICE_ORDER` consistently in `thirst sweep`.
- `datetime.UTC` in tests breaks Python 3.10, which the CLI supports.
- Handle `OSError` in the output tee thread.
- Add a retry for `POST /sites` (register).
- Plan 4.11: `--offline` plans from bundled data.

### 4.3 Release and hardware checks (P1)

- **4.3.a PyPI.** Add PyPI Trusted Publishing (GitHub OIDC, no token) plus a release workflow. Bump `cli/pyproject.toml` to 0.3.1 and publish.
- **4.3.b Hardware checks on a real Linux GPU box** (plan 1.8 / 4.6.h). Each of these is still untested on real hardware:
  - real NVML power limit and restore
  - `--fallback-clocks` (`MIN_LOCK_MHZ=210` is an assumption)
  - SIGSTOP/SIGCONT on a live CUDA process
  - Ctrl-C mid-run restores the limit
  - SSH disconnect restores the limit

---

## 5. Website

| # | Task | Priority |
|---|---|---|
| 5.1 | 6.3.j "Describe your job in one sentence" box: needs Bedrock (3.1). Without it, `/explain {text}` only returns a hint. | P1 after 3.1 |
| 5.2 | 6.8 India finding section on the home page (needs 2.7) | P1 |
| 5.3 | 6.10 Lighthouse report: run Chrome DevTools → Lighthouse on `/` and `/plan`, mobile; save it in `docs/` | P1 |
| 5.4 | e2e: the phone "jump links scroll" test failed once on the live site, then passed 12/12 on re-run; make the wait more robust | P2 |
| 5.5 | Run Playwright in CI after each deploy (it is read-only, so it is safe against the live site) | P2 |
| 5.6 | Refresh the README screenshots (`docs/readme/*.png`) after the colour-contrast change | P2 |
| 5.7 | The slider has no visible effect until 2.1 lands; consider hiding it while every Pareto point is identical | P1 if 2.1 slips |

---

## 6. Model limits we state but have not fixed (P2)

- Timing uses the **average** grid mix per hour. India's marginal plant is often coal at any hour, so savings from timing alone may be smaller. The app says so.
- A pausable plan uses only each hour's cheapest level. A tight deadline falls back to a non-pausable plan (`pause_no_room`).
- `sigma_grid = sigma_site` (one stress weight for both waters).
- Grid "Option B" scales solar by radiation relative to the window mean, so a uniformly cloudy day looks like a clear one.
- Jobs over 47 h can exceed the 48-slot window when submitted mid-hour.

---

## 7. Done today (for the record)

- PR #6: React review leftovers, code-splitting (810 → 249 kB), no mock chunk in production
- PR #7: CLI review fixes
  - the receipt is saved before sending
  - Ctrl-C while sending keeps it for `thirst sync`
  - SIGHUP is handled
  - SIGCONT is sent after an error while paused
  - a failed cap restore exits 5
- PR #8: 31 GPU rows with sources, including the RTX 3050 Laptop (detected correctly on our laptop)
- PR #9: Playwright e2e. The first run found contrast, list-markup and tap-target bugs, now fixed. Live: 74 pass, 4 skip, 1 flaky.
- Deploy fixed: the OIDC role trusts the immutable subject claim (D38)
- Branches cleaned up: only `main` is left
- The home page now says `pip install thirst` instead of the GitHub install line
