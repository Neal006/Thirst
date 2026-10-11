# Testing Thirst end to end, as a normal user

This guide walks through Thirst the way a student or lab head would meet it: first the website, then the `thirst` command on their own computer. Each step says **what to do**, **what you should see**, and **what counts as a problem**.

The terminal outputs below are real. They were first captured on 2026-10-11 against the live service, on a Windows laptop with an RTX 3050 Laptop GPU, using `thirst` 0.3.1 from PyPI, and the project owner then ran the same steps. Part B was re-run for the CLI fixes on the `feat/web-ui-accessibility` branch, against the same API code run locally (`scripts/local_api.py`). Times, ids and numbers will differ for you, and the test labs shown were deleted afterwards.

This version describes the website after the UX overhaul (`docs/implementation-plan/09-ux-overhaul.md`). If the live site still shows cobalt and yellow, that branch has not been deployed yet: use the previous version of this guide from `main`.

| | |
|---|---|
| Website | https://main.dzxkrtlc7xqfx.amplifyapp.com |
| CLI | `pip install thirst` (Python 3.10+) |
| Time needed | Part A (website): 15 min · Part B (CLI, any computer, incl. checking your lab on the site): 15 min · Part C (NVIDIA GPU): 30 min+ |

> **Note:** Today the power-cap numbers are **placeholders** until our GPU sweep is measured. That has three visible effects:
> - Every plan picks a 70% power cap.
> - All 11 water/carbon options are the same plan, so the planner hides the slider and says why.
> - Savings show as about **18–20% water and CO₂, 20–21% energy** in every city.
>
> All three are expected, and the app tags those numbers `placeholder`.

---

## Part A: The website (no install)

Use any browser. Then repeat A1–A3 on a phone, or with your browser's phone view at about 360 px wide.

### A1. Home page `/`

| Do | You should see |
|---|---|
| Open the site | A light page titled **"Every GPU hour drinks water *twice*."** with **Plan a job →** and **Compare cities** buttons. The menu at the top says **Plan · Cities · Leaderboard · Assumptions**. |
| Look under the buttons | Three meters: **Best start** (a clock time), **Water, best vs worst hour** and **CO₂, best vs worst hour**, the last two each a negative % with a small label chip (e.g. `modelled`) |
| Look at the round dial (the **water clock**) | The next 24 hours around a dial. Longer teal wedges are thirstier hours, and an amber **RUN** arc marks the cleanest 3 hours. The centre reads **Cleanest hour**. A green **live** marker means the weather came from today's forecast. |
| Change the city (Chennai, Bengaluru, Hyderabad, Mumbai, Delhi, Pune) | The dial, meters and beakers redraw within a second or two. On a phone the city buttons wrap onto two lines. |
| Compare **Best start** with the **Start** time under the right-hand beaker | They match: both are the planned start of the same sample job |
| Scroll to **"Where the water goes"** | Two beakers: **Start now** (full power) vs the planned start. Each splits into building water and power-plant water. |
| Switch **Lab · room AC** ↔ **Data centre · cooling tower** | Room AC: only power-plant water ("the water leaves at the power plant"). Cooling tower: a second, building-water layer appears. |
| Scroll to **"A slower GPU drinks less"**, press **100% / 85% / 70%** | **Time to finish** goes up and **Energy for the job** goes down, each tagged `placeholder` |
| Scroll to **"How it works"** | The four steps (Plan, Run, Receipt, Rating), the `thirst run` command and a sample receipt stamped **Sample** |
| Scroll to **"Score the choice, not the climate"** | The top small labs, each marked **(simulated)**, with scores and badges |
| Scroll to the end | **"Start in two steps"** with two copyable commands, `pip install thirst` and `thirst register …`, and **Open the planner →**. Press **Copy** and paste somewhere to check. |
| Click any label chip (`modelled`, `placeholder`, …) | It opens the **Assumptions** page at that factor |

Every section should be visible as you scroll, with no blank gaps.

**Problems to report:**
- A blank area, or a spinner that never stops.
- A red error box.
- A number with no label chip next to it.
- Text you can't read.
- On a phone, the page scrolls sideways, or a menu word breaks over two lines.

### A2. Planner `/plan`

| Do | You should see |
|---|---|
| Press **Plan a job →** on the home page | **"When should your GPU job run?"** with the city already filled in |
| Press the **Overnight fine-tune** quick fill (2 × RTX 4090 · 6 h · by 9 AM) | The form fills in: GPU model, **How many GPUs?**, **Hours of work at full GPU power**, **Deadline (India time)** and City |
| Open **More options** | Pausing and cooling. The summary line shows the current choice (for example "Can pause · Room AC"). Picking **Cooling tower** asks for PUE. |
| Press **Plan** | Within about 1 second, a **"Your plan"** card: one sentence with when to start, the GPU power % and when it ends. Under it, a **why this time** line, the saving as ranges such as **19 to 20%** with chips, and "Forecast updated …". |
| Look below the card | **Run this plan** with the exact `thirst run …` command, **Copy**, **Add to calendar** and **Copy share link** |
| Press **Add to calendar** | `thirst-plan.ics` downloads. It opens in Google Calendar or Outlook at the planned IST time, with a 10 minute reminder. |
| Press **Copy share link** and open the link in a private window | The same job is filled in and planned straight away |
| Use the **Timetable · Hourly · Calendar · Chart** tabs under **Next 48 hours** | The same run hours in four views. Timetable is a 48-hour grid (amber bars = job runs, dashed = cleanest 3 hours, red edge = deadline). The arrow keys move between tabs. |
| Look for the water/carbon slider | *Today it is hidden*, with the line "With today's placeholder power-cap data every option gives the same plan" and a `placeholder` chip (see the note at the top). With measured data the **Water or CO₂ first?** slider appears. |
| Look at **Recent** under the form | The job you just planned. Clicking it plans it again. |
| Press **How do we know?** | The Assumptions page |
| Press **Compare cities** next to "Your job" | The Cities page |
| Try a bad input: deadline in the past, 0 hours, or 1,000 GPUs | A clear message next to the field and an error summary at the top. No request, no crash. |
| Try **Two-day pretrain** (8 × A100 · 30 h · not pausable) | A plan that runs over two days. The card shows the finish **day** when it differs from the start day. |

**Problems to report:**
- The plan takes more than 3 seconds.
- A savings number shown without a range.
- The four views disagree on when the job runs.
- The copied command does not match the job in the form.

### A3. Compare cities `/cities`

| Do | You should see |
|---|---|
| Open **Cities** in the top menu | **"Compare cities"**: the same job (2 × RTX 4090, 6 h, done by 9 AM) in six cities. Each card has the water stress, **Best start**, a 48-hour strip (darker = more water per kWh, amber marks = when the job runs), **Water for the job** and **Saving vs now**, each with a chip. |
| Switch **Room AC** ↔ **Cooling tower** | Every card updates |
| Press **Plan here** on a card | The planner, with that city and cooling filled in |

### A4. Leaderboard `/leaderboard`

| Do | You should see |
|---|---|
| Open **Leaderboard** in the top menu | "Last 30 days · D1", **Pick your weight class** tabs (Small labs ≤ 16 GPUs, Clusters, Facilities, Hyperscale) and a ranked table with medals for the top 3, score rings and badges (Bronze 45+, Silver 60+, Gold 75+, Platinum 90+) |
| Switch the tabs | Each class shows only its own labs. An empty class says so and offers **Plan your first job**. |
| Click **Demo Lab, Chennai (simulated)** | Its site page |

### A5. A lab's page `/sites/<id>`

You should see:
- The lab name, city, cooling and class, and **Plan a job here →** (opens the planner for that city).
- A 0–100 score with a badge ladder showing the points needed for the next badge.
- The score's parts: behaviour, facility efficiency, measurement and openness.
- **Recent receipts**, with a **Capture** column.

Demo labs are labelled simulated.

Then click a receipt (for example `/receipts/s_simaaaaaaa/j_zrwzqebwoeb5`) to open **Your receipt**. It shows:
- the run window and GPUs
- energy, with `measured` or `modelled`
- water and CO₂ against "if you had started right away"
- the capture %
- **Plan your next job →** at the top

### A6. Assumptions `/assumptions`

You should see:
- **Words we use**: a short glossary (water per kWh, water stress, GPU power level, pausing, PUE, receipt, Capture, measured or modelled, weight class).
- A **"How sure we are"** bar. Today it shows 30 design choices, 18 placeholders, 8 sourced and 1 calibrated, out of 57 factors.
- Jump chips for each group: Data, GPUs, Cities, Sources, …
- Every factor with its value, its range, a status chip and a source link.

Click a jump chip and the page should scroll to that group.

### A7. Edge cases

| Do | You should see |
|---|---|
| Open `/nothing-here` | **"We couldn't find that page"** with a link back to the planner |
| Open `/sites/s_aaaaaaaaaa` (no such lab) | A clear "not found" message, not a blank page |
| Refresh while on `/plan`, `/cities`, `/leaderboard` or a site page | The same page loads again (no 404 from the host) |
| Use only the keyboard (Tab, Enter, arrow keys on the view tabs) | Every control can be reached and used, with a visible focus ring. The timetable can be scrolled sideways with the arrow keys after tabbing to it. |
| Turn on "reduce motion" in your OS | Pages appear without fading or sliding |

---

## Part B: The CLI on any computer (no GPU needed)

This is what a lab member sees in the terminal. The steps below use **PowerShell on Windows**; on Linux or macOS use `source thirst-test/bin/activate` and `export THIRST_HOME=/tmp/thirst-home`.

Register **public** if you want to check your lab on the website afterwards (Part B8). Use `--private` to keep it off the board.

> **Clean up afterwards.** A test lab stays in the live database. Only a maintainer with AWS access can delete it, so send them the `s_...` id:
> ```
> python scripts/seed.py --profile thirst --stage dev --delete-site <site_id>
> ```

### B1. Install into a fresh environment

```powershell
cd $env:TEMP
python -m venv thirst-test
.\thirst-test\Scripts\Activate.ps1      # if blocked: call .\thirst-test\Scripts\thirst.exe instead of thirst
pip install --no-cache-dir thirst
thirst --version
$env:THIRST_HOME = "$env:TEMP\thirst-home"   # keeps this test's config separate from ~/.thirst
```
Expected: `thirst 0.3.1` or newer.

The output below is from the CLI on the `feat/web-ui-accessibility` branch, which fixes the walkthrough problems in `docs/TODO.md` 4.1.a–g. Until those fixes are on PyPI (0.3.2), install them from a checkout with `pip install ./cli`. With 0.3.1 you will still see the old messages, noted under each step.

### B2. Check the setup before registering

On the RTX 3050 laptop. The `[warn]` line is the new message from the fix. It has not been re-captured on that laptop yet.

```
$ thirst doctor
[ok]   Python 3.12.5
[FAIL] Config: Run `thirst register` first.  -> run `thirst register`
[ok]   NVIDIA GPU: 1 x NVIDIA GeForce RTX 3050 6GB Laptop GPU (model RTX-3050-Laptop)
[ok]   GPU energy counter
[warn] GPU power cap permission: This GPU does not let software read or change its power limit (common on laptops; `nvidia-smi` shows [N/A]). Jobs still run and their energy is still measured  -> use `thirst run --no-cap`
[ok]   Restore marker: none left over
```

What each line means:
- **Config FAIL**: expected, because you haven't registered yet.
- **GPU lines**: on a computer without an NVIDIA GPU, they fail. That's fine: use `--modelled` later.
- **Power cap `[warn]` on a laptop**: expected. Most laptops don't let software change the GPU power limit. It is a warning, not a failure: jobs still run and are measured with `--no-cap`. (0.3.1 prints this as a misleading `[FAIL]` about a driver error.)

### B3. Register the lab

```
$ thirst register --name "My Test Lab" --city Chennai --cooling room_ac --gpus 1
Registered site s_duronhjo6o (division D1).
Site page: https://main.dzxkrtlc7xqfx.amplifyapp.com/sites/s_duronhjo6o
The site key was saved to ~/.thirst/config.toml (private to your user). It is not shown again.
Note: site names are public. Use --private to keep this site off the leaderboard.
```

- **Write down the `s_...` id.**
- The key is never printed.
- `--cooling` is one of `room_ac`, `air_chiller` or `evaporative`.
- Add `--private` to stay off the leaderboard. The config remembers it, and receipts then print no web link, because private receipts are hidden on the site. (0.3.1 prints a link that returns 404.)

Run `thirst doctor` again. Now **Config**, **API reachable** and **Your clock vs the server: 0 s apart** are `[ok]`.

### B4. Get a plan without running anything

```
$ thirst plan --hours 4 --deadline "2026-10-12 09:00"
Plan: start 14:33, cap 70%, done by 19:00
Expected savings compared with starting right away (ranges, modelled):
  Water  19 to 20%
  CO2    19 to 20%
  Energy 20 to 21%
Plan id: p_brya2ma7h5. Assumptions: https://main.dzxkrtlc7xqfx.amplifyapp.com/assumptions
```

- The deadline is India time.
- `--pausable` allows pauses. On Windows it prints "Pausing is not available on Windows, so the job will run without pauses."
- `--alpha 0` means least CO₂ and `--alpha 1` means least water.
- `--json` prints the full server answer.
- The Assumptions link is a full URL you can click. (0.3.1 prints just `/assumptions`.)
- The website gives the same plan: open **Plan**, fill in the same job, and press **Copy share link** to compare.

### B5. See what a run would do

```
$ thirst run --hours 4 --deadline "2026-10-12 09:00" --dry-run -- python train.py
Plan: start 14:33, cap 70%, done by 19:00
Dry run: nothing is started. The CLI would make these changes:
  11 Oct 14:33  start the command at 70% power
  11 Oct 19:00  planned end
```

The dry run uses the same start and end as the plan line. (0.3.1 shows the hour slots instead, 14:00 and 20:00.)

### B6. A real short run that follows the plan

`--modelled` estimates the energy from the GPU model instead of reading the hardware, so nothing on your GPU changes. Without `--now`, Thirst follows the plan. Today the plan starts right away, so this 2.5-minute "training" job starts at once:

```
$ thirst run --modelled --gpu-model RTX-3050-Laptop --gpus 1 --hours 0.05 --deadline "2026-10-12 09:00" -- python -c "import time; print('training...', flush=True); time.sleep(150); print('done', flush=True)"
Plan: start 15:22, cap 70%, done by 15:25
training...
done
Thirst receipt j_a3ry5skdhjon
  Ran      11 Oct 15:22 to 15:24 IST (2 min) on 1 x NVIDIA GeForce RTX 3050 Laptop GPU, modelled at 70% (plan level)
  Energy   2.2 Wh GPU (modelled)
  Water    8 mL (modelled); if you had started right away: 10 mL
  Carbon   2 g CO2 (modelled); if you had started right away: 3 g
  Saved    20% water and 20% CO2 compared with starting right away (modelled)
  Capture  You took 100% of the possible saving
  Score    Site score 78.5 gold (Provisional)
  Receipt  https://main.dzxkrtlc7xqfx.amplifyapp.com/receipts/s_duronhjo6o/j_a3ry5skdhjon
```

Why the receipt looks like this:
- **`--gpu-model` and `--gpus` are only needed without an NVIDIA GPU.** On a machine where the GPU is detected, `thirst run --modelled …` uses it. GPU ids are on the Assumptions page under GPUs. (0.3.1 always asks for both flags.)
- **Small numbers are shown in Wh, mL and g.** About 2 Wh would print as `0.00 kWh` in 0.3.1.
- **"modelled at 70% (plan level)".** The modelled meter assumes the plan's 70% level was followed, which is where the 20% saving comes from. (0.3.1 says "uncapped" here, which read as a contradiction.)
- **The score is 78.5.** A = 50 (capture 100%) and C = 5 (public lab), so 55 / 70 × 100 = 78.57, which is Gold (Provisional). See [`SPEC.md`](../SPEC.md) §4.
- **A private site gets no link.** Registered with `--private`, the last line reads "Private site: receipts are kept off the website".
- **Your command's output still shows.** It also goes to a log under `$THIRST_HOME/logs/` (default `~/.thirst/logs/`).

To compare, add `--now`. The plan line then says `full power (no cap)`, the saving and capture are 0%, and the site score is 0 for that receipt.

### B7. Saved receipts, the outbox and Ctrl-C

```
$ thirst receipt show j_a3ry5skdhjon
Thirst receipt j_a3ry5skdhjon
  ... (the same receipt, read from $THIRST_HOME/receipts/)

$ thirst sync
Nothing to send: the outbox is empty.
```

- **Ctrl-C:** run B6 again and press Ctrl-C after `training...`. The job stops, and you still get a receipt marked as interrupted.
- **Offline:** turn off the network just before a short run ends.
  1. The receipt is saved on disk and the CLI says it is **queued**.
  2. Turn the network back on.
  3. `thirst sync` sends it.
- **Ctrl-C while sending:** the CLI exits with code 130 and says to run `thirst sync`.

### B8. Check your lab on the website (public labs only)

| Open | You should see |
|---|---|
| The **Site page** link from B3 | Your lab's name, Chennai and D1, a score of about **78.5 Gold (Provisional)**, a badge ladder with the points to Platinum, and **1 receipt** under Recent receipts |
| The **Receipt** link from B6 | The run window, the GPU, energy tagged **modelled**, water and CO₂ against "if you had started right away", and capture **100%** |
| **Leaderboard → D1** | Your lab at about **#3**, between the simulated demo labs. If it isn't there yet, refresh after a minute (the board is cached briefly). |

For a `--private` lab, the site page shows no receipts, and the CLI prints no receipt link (private receipts are hidden).

### B9. Clean up

```powershell
deactivate
Remove-Item -Recurse -Force $env:TEMP\thirst-test, $env:TEMP\thirst-home
```
Then send the `s_...` id to a maintainer so the test lab is removed from the live board.

---

## Part C: On a machine with an NVIDIA GPU (the real thing)

Best on **Linux with a desktop GPU** (RTX 30/40, A-series, A100, L4, …).

### C1. Doctor
`thirst doctor` should be all `[ok]`.

If **GPU power cap permission** fails, power limits need admin rights. Run it with `sudo`, or give your user NVML admin rights.

### C2. A capped, measured run
```
thirst run --hours 1 --deadline "<tomorrow> 09:00" -- python train.py
```
- The CLI waits for the planned hour, printing a countdown.
- At the start it sets the power limit. Check it in another terminal: `nvidia-smi -q -d POWER` shows the lower **Power Limit**.
- When the job ends, the receipt says **`(measured)`** for energy and names the cap method (e.g. `cap 70%`).
- Afterwards `nvidia-smi -q -d POWER` shows the **original** limit again.

### C3. Safety checks (the important ones)
| Do | Expect |
|---|---|
| Press **Ctrl-C** during the job | The job stops, the original power limit comes back, and a receipt marked interrupted is still made |
| Close the SSH window during a job (Linux) | Same: the limit comes back (SIGHUP is handled) |
| Kill the CLI with `kill -9` (simulates a crash) | The next `thirst run` refuses to start until you run `thirst doctor --restore`, which puts the limit back |
| `--pausable` with a single-process job | At pause hours the job is frozen (no GPU use) and then resumed |
| `--pausable` with `torchrun`/DeepSpeed/MPI | The CLI says it will run without pauses |

### C4. Measure the power-cap curve (helps the whole project)
```
pip install "thirst[sweep]"
thirst sweep --out powercap_sweep.json
```
This runs a short PyTorch workload at several power levels and records the speed and energy at each. Send the file to the team: it replaces the placeholder data (`docs/TODO.md` 2.1).

---

## Part D: Developer checks (optional)

```
uv venv --python 3.12 .venv && uv pip install -e ".[dev]" -e ./cli
npm --prefix web ci

python -m ruff check . && python -m mypy && python -m pytest -m "not gpu and not aws"
npm --prefix web test -- --run && npm --prefix web run lint && npm --prefix web run build

python scripts/gen_assumptions.py --check                     # ASSUMPTIONS.md matches the factor data
python scripts/local_api.py                                   # real API on :3000, in-memory DB
cd web && VITE_API_URL=http://127.0.0.1:3000 npm run dev       # site on :5173

npm --prefix web run e2e                                       # Playwright against the live site (read-only)
bash scripts/smoke.sh https://l6y3i40hh4.execute-api.ap-south-1.amazonaws.com
```

The e2e result on 2026-10-11 against the live site was 74 passed, 4 skipped and 1 flaky. The flaky one was the phone jump-link test, which now waits for the tables to render (TODO 5.4).

On the `feat/web-ui-accessibility` branch, the suite also covers the plan views, the run box, share links, the Cities page and the phone menu. Against a production build of the branch with the local API: 82 passed, 9 skipped (the slider tests, while every Pareto option is the same plan, and the receipt page when the first demo site has none).

---

## What a normal user should come away with

1. **"My job uses water twice, and my city's hours differ."** That comes from the water clock and the beakers.
2. **"There is a simple plan: start at X, GPU at Y%, done by Z."** That comes from the planner card.
3. **"Running it is one command, and my GPU is safe."** That comes from `thirst run`, which always restores the power limit.
4. **"I get proof, and my lab can climb a fair board."** That comes from the receipt, the score and the weight classes.
5. **"They tell me which numbers are measured and which are guesses."** That comes from the label chips and the Assumptions page.

If any of these doesn't come across during your test, write down where you got stuck. That is the most useful feedback.
