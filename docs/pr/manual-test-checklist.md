# Manual test checklist for `feat/web-ui-accessibility`

What was already run, and what is left to check by hand. Tick each box as you go. The step-by-step walkthrough for a normal user is [`docs/USER_TEST_GUIDE.md`](../USER_TEST_GUIDE.md).

## Already run (2026-10-11, after merging PR #11)

| Area | How | Result |
|---|---|---|
| Web unit tests, lint, build | `npm --prefix web test -- --run`, `run lint`, `run build` | 526 passed, 0 warnings, build passes |
| Python | `ruff check .`, `mypy`, `pytest -m "not gpu and not aws"`, `check_skeleton.py` | clean, clean, 1381 passed + 1 skipped, OK |
| e2e + axe | `main`'s Playwright suite plus the new specs, desktop and 360 px phone, against a production build of the branch and `scripts/local_api.py --offline` | 82 passed, 9 skipped, 0 failed |
| CLI against the real API code | `register --private`, `plan`, `run --dry-run`, `run --now --modelled` (2 min job), `doctor` | New output as in `USER_TEST_GUIDE.md` Part B |

Not reachable from the test machine: the live site, the live API and Google Fonts. So **the deployed site is not verified** (section 3), and the laptop `[warn]` line in `doctor` has not been seen on a real laptop GPU yet (section 1).

## Fixed in this branch (were open)

- `thirst doctor` on a laptop GPU: `[warn]` with "use `--no-cap`", not a misleading `[FAIL]` (TODO 4.1.a).
- `thirst plan` prints the full Assumptions URL (4.1.b).
- `thirst run --dry-run` uses the plan's exact start and end (4.1.c).
- `--modelled` uses the detected GPU (4.1.d).
- Short jobs show Wh, mL and g (4.1.e).
- Private sites get no 404 receipt link (4.1.f).
- `THIRST_TOKEN` no longer reaches the user's command (4.2).
- Website: tag chip and stamp contrast, keyboard access to the timetable scroll, the phone menu, the hidden slider note.

---

## 1. CLI checks (needs a machine with an NVIDIA GPU)

Install this branch's CLI: `pip install ./cli` from a checkout (PyPI 0.3.1 does not have the fixes yet). Use a future date for every `--deadline`.

**Laptop GPU (for example the RTX 3050 Laptop)**

- [ ] `thirst doctor` shows `[warn] GPU power cap permission: … common on laptops …` and exits 0 (not `[FAIL]`)
- [ ] `thirst run --now --modelled --hours 0.05 --deadline "…" -- python -c "import time; time.sleep(120)"` runs **without** `--gpu-model` and `--gpus` and names the laptop GPU on the receipt
- [ ] That receipt shows Wh, mL and g, not zeros
- [ ] Registered with `--private`: the receipt says "Private site: receipts are kept off the website" instead of a link
- [ ] `thirst run --no-cap …` runs and the receipt energy says `(measured)`

**Desktop GPU (Linux, root or NVML admin rights)**

- [ ] `thirst doctor` is all `[ok]`
- [ ] `thirst plan` ends with a clickable `https://…/assumptions` link
- [ ] `thirst run --dry-run …` start and end match the plan line
- [ ] A short real run caps the GPU (`nvidia-smi -q -d POWER`), measures energy and restores the limit afterwards
- [ ] Ctrl-C mid-run restores the limit, and `thirst doctor` shows no restore marker
- [ ] Inside the job, `python -c "import os; print('THIRST_TOKEN' in os.environ)"` prints `False`, even with `THIRST_TOKEN` set in your shell
- [ ] The receipt link opens the receipt page with the same numbers

## 2. Website checks (new UI)

Run the branch with `cd web && npm run dev` (mock data) or against `scripts/local_api.py`. Check at desktop width and on a phone.

**Home**

- [ ] Every section is visible without scrolling first
- [ ] **Best start** matches the "Start" time under the right-hand beaker
- [ ] "Plan a job" opens the planner for the chosen city. "Compare cities" opens Cities
- [ ] The menu reads Plan · Cities · Leaderboard · Assumptions, and no word breaks on a 360 px phone

**Planner**

- [ ] Quick fill, then **Plan**, shows the card with the "why this time" line and "Forecast updated …"
- [ ] Timetable, Hourly, Calendar and Chart all show the same run hours. Arrow keys move between tabs. The chosen tab survives a reload
- [ ] On a phone, Tab reaches the timetable and the arrow keys scroll it sideways
- [ ] **Copy** gives a `thirst run …` command that `thirst run --dry-run` accepts
- [ ] **Add to calendar** imports into Google Calendar and Outlook at the right IST time with a 10 minute reminder
- [ ] **Copy share link** in a private window fills and plans the same job
- [ ] **Recent** lists the job and replans it in one click
- [ ] With placeholder data the slider is hidden and the note with a `placeholder` chip shows. With differing Pareto points (unit tests use one), the slider shows and changes the card without a request

**Cities, leaderboard, site, receipt, assumptions**

- [ ] Cities: six cards, Room AC and Cooling tower switch them, "Plan here" opens the planner for that city and cooling
- [ ] Leaderboard: "Last 30 days · D1", "Pick your weight class", an empty class shows "Plan your first job"
- [ ] Site page: "Plan a job here" opens the planner for that city
- [ ] Receipt page: "Plan your next job" goes to the planner. The Capture column and banner read correctly for negative capture
- [ ] `/assumptions#glossary` shows "Words we use", including Capture and weight class
- [ ] Every label chip is readable and links to its factor row
- [ ] With "reduce motion" on in the OS, nothing animates

## 3. After merging (live site)

- [ ] Merge `main` into the branch first (PR #12 is there), then merge the PR
- [ ] The Deploy workflow is green and the live site shows the teal and amber look
- [ ] `npm --prefix web run e2e` against the live site passes (expect the slider skips while the data is placeholder)
- [ ] Deep links such as `/cities` and `/plan?city=Pune` load directly (Amplify rewrite rule)
- [ ] If any video shot was recorded on the old site, it still matches the voice-over, or re-record it from the updated `VIDEO_SCRIPT.md`
- [ ] Release CLI 0.3.2 through the PR #12 workflow so `pip install thirst` gets the 4.1 fixes, then update `USER_TEST_GUIDE.md` B1
