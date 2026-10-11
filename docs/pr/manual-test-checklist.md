# Manual test checklist: Thirst CLI and website

What I already ran, what I found, and what is left for you to check by hand. Tick each box as you go.

## What I ran

| Area | How | Result |
|---|---|---|
| `pip install thirst` | Fresh virtualenv, from PyPI | Installs `thirst 0.3.0`. The code matches `cli/` in the repo |
| CLI against the real API code | `python scripts/local_api.py --offline` (moto, no AWS) | `register`, `plan`, `plan --json`, `run --dry-run`, `run --now --modelled`, `run --pausable --slot-seconds`, `receipt show`, `sync`, `doctor` all work |
| CLI error messages | Past deadline, bad date, unknown city, short name, no `--`, API down, no GPU | Clear messages and the right exit codes |
| Outbox | API stopped during a run | Receipt saved to `~/.thirst/outbox`. `thirst sync` posts it or moves it to `rejected/` with a reason |
| CLI tests | `pytest tests/cli` | All pass |
| Website against the local API | Playwright, 30 checks across every page | 29 pass. The trade-off slider is hidden because placeholder factors make all 11 options the same (expected) |
| Web tests, lint, build | `npx vitest run`, `npm run lint`, `npm run build` | 486 tests pass, no lint warnings, build passes |

I could not reach the deployed API or the Amplify site from either test machine, so **the live deployment is not verified**. Section 3 covers it.

## Issues found in the CLI

None of these block a demo. They are small polish items. (Testing against a local API also needs `THIRST_WEB_URL=http://localhost:5173` so the printed links point at the local site.)

| # | What happens | Where to look |
|---|---|---|
| 1 | `thirst plan` ends with `Assumptions: /assumptions`, a relative path that cannot be clicked | `cmd_plan` in `cli/thirst/commands.py`. Join it with `web_url()` |
| 2 | `thirst run --dry-run` says the plan starts at 12:47, then lists the first action at `12:00` (the start of that hour slot) | `_print_dry_run` in `cli/thirst/jobrun.py` |
| 3 | A run under 1 Wh prints `Status slots: a receipt needs at least 1 Wh…`. The `slots:` prefix is the raw field name from the server | Message in `src/engine/score.py`, printed by `cli/thirst/receipt.py` |
| 4 | If the server is unreachable when you start, `thirst run --now` stops before running anything. A user might expect the job to run and the receipt to wait in the outbox | `cli/thirst/jobrun.py` |

---

## 1. CLI checks (needs a machine with an NVIDIA GPU)

Use a fresh virtualenv. Use a date in the future for every `--deadline`.

**Install**

- [ ] `pip install thirst` works, and `thirst --version` prints `thirst 0.3.0`
- [ ] `pip install "git+https://github.com/Neal006/Thirst#subdirectory=cli"` (the command on the home page) also works
- [ ] On Windows, `thirst` is on PATH after install

**Setup**

- [ ] `thirst doctor` before registering shows `[FAIL] Config` and tells you to register
- [ ] `thirst register --name "Your Lab" --city Chennai --cooling room_ac --gpus 1` prints a site id and a site link that opens on the live website
- [ ] Running register again without `--force` refuses, and `--force` replaces it
- [ ] `thirst doctor` now shows Config ok, API reachable, clock ok, GPU found and power-cap permission
- [ ] Without admin or root, doctor explains how to allow power capping

**Plan**

- [ ] `thirst plan --hours 2 --deadline "YYYY-MM-DD 09:00"` detects the GPU model and count by itself
- [ ] The start time and cap match what the website shows for the same job (use the website's share link fields)
- [ ] `--alpha 0` and `--alpha 1` can give different plans with live data
- [ ] `--json` prints valid JSON

**Run (real GPU)**

- [ ] `thirst run --now --hours 0.2 --deadline "…" -- python -c "import time; time.sleep(120)"` runs and prints a receipt with **measured** energy
- [ ] During the run, `nvidia-smi -q -d POWER` shows the lowered power limit
- [ ] After the run, the power limit is back to the default
- [ ] Press Ctrl-C in the middle of a run: the limit is still restored, and `thirst doctor` shows no restore marker left over
- [ ] A planned run (no `--now`) waits until the start time, then starts by itself
- [ ] A `--pausable` single-GPU job pauses and resumes at the planned hours
- [ ] The receipt link opens the receipt page on the website, with the same numbers
- [ ] `--no-cap` runs at full power and the receipt says uncapped
- [ ] `--modelled` on a laptop without a GPU labels energy as modelled

**Offline**

- [ ] Turn off Wi-Fi during a run: the receipt is saved to `~/.thirst/outbox`
- [ ] Turn Wi-Fi back on and run `thirst sync`: the receipt is posted and shows on your site page
- [ ] `thirst receipt show <job_id>` prints a saved receipt

## 2. Website checks (new UI)

Run it with `cd web && npm run dev`, then repeat on the deployed site. Check at desktop width and on a phone.

**Home**

- [ ] Every section is visible without scrolling first, and nothing is blank
- [ ] City buttons change the clock and the beakers, and wrap on a phone
- [ ] "Best start, 6 h job" matches the "Start" time in the beakers below
- [ ] "Plan a job" opens the planner with the chosen city. "Compare cities" opens the Cities page
- [ ] The two Copy buttons in "Start in two steps" copy the commands

**Planner**

- [ ] A quick fill button fills the form, then **Plan** shows the plan card
- [ ] The "why this time" line makes sense for the plan shown
- [ ] Timetable, Hourly, Calendar and Chart tabs all show the same run hours. Arrow keys move between tabs
- [ ] The tab you chose is still selected after a page reload
- [ ] "More options" opens and closes and shows pausing and cooling. Picking Cooling tower asks for PUE
- [ ] A past deadline shows an inline error and makes no request
- [ ] **Copy** copies a `thirst run …` command that works when pasted into a terminal
- [ ] **Add to calendar** downloads `thirst-plan.ics`, which imports into Google Calendar and Outlook at the right IST time with a 10 minute reminder
- [ ] **Copy share link**, opened in a private window, fills the same job and plans it straight away
- [ ] The job appears under **Recent**, and clicking it plans it again
- [ ] With live data, the "Water or CO₂ first?" slider appears and moving it changes the plan without a new request
- [ ] On a phone, the plan shows first and the form sits under "Change job"

**Cities**

- [ ] Six cards load, each with a best start, a 48 hour strip and two numbers with labels
- [ ] Room AC and Cooling tower switch every card
- [ ] "Plan here" opens the planner for that city and cooling

**Leaderboard, site, receipt, method**

- [ ] Leaderboard rows link to site pages. Empty lab-size groups show the message and a "Plan your first job" button
- [ ] Your registered lab's site page loads, the name wraps cleanly, and "Plan a job here" opens the planner for your city
- [ ] A receipt page from the CLI link loads, and "Plan your next job" goes to the planner
- [ ] Method page shows "Words we use" at `/assumptions#glossary`, and the factor tables load
- [ ] Every "modelled" or "measured" chip links to the right row on the Method page
- [ ] An unknown address shows the not-found page with the header still there

**Everywhere**

- [ ] Nav shows Plan, Cities, Leaderboard, Method, and the current page is highlighted
- [ ] Pages fade in gently when you navigate. With "reduce motion" on in your OS, nothing moves
- [ ] Tab through a page with the keyboard: focus is always visible and the skip link works
- [ ] No errors in the browser console

## 3. Deployed site and API

- [ ] `curl https://l6y3i40hh4.execute-api.ap-south-1.amazonaws.com/assumptions` returns JSON
- [ ] https://main.dzxkrtlc7xqfx.amplifyapp.com loads the new design after this branch is deployed
- [ ] The live forecast shows "live" (not "cached") on the home clock
- [ ] A receipt posted by the CLI appears on the live leaderboard within a minute
- [ ] Deep links such as `/cities` and `/plan?city=Pune` load directly (Amplify rewrite rule for a single-page app)
