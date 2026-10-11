# Testing Thirst end to end, as a normal user

This guide walks through Thirst the way a student or lab head would meet it: first the website, then the `thirst` command on their own computer. Each step says **what to do**, **what you should see**, and **what counts as a problem**.

The terminal outputs below are real. They were captured on 2026-10-11 against the live service, on a Windows laptop with an RTX 3050 Laptop GPU. Times, ids and numbers will differ for you.

| | |
|---|---|
| Website | https://main.dzxkrtlc7xqfx.amplifyapp.com |
| CLI | `pip install thirst` (Python 3.10+) |
| Time needed | Part A (website): 15 min · Part B (CLI, any computer): 15 min · Part C (NVIDIA GPU): 30 min+ |

> **Note:** Today the power-cap numbers are **placeholders** until our GPU sweep is measured. That has three visible effects:
> - Every plan picks a 70% power cap.
> - The water/carbon slider doesn't change the plan.
> - Savings show as about **18–19% water and CO₂, 20–21% energy** in every city.
>
> All three are expected, and the app tags those numbers `placeholder`.

---

## Part A: The website (no install)

Use any browser. Then repeat A1–A3 on a phone, or with your browser's phone view at about 360 px wide.

### A1. Home page `/`

| Do | You should see |
|---|---|
| Open the site | A light page titled **"Every GPU hour drinks water *twice*."** with **Plan a job →** and **How it works** buttons |
| Look under the buttons | Two meters, **"Water / kWh, best vs worst hours"** and **"CO₂ / kWh, best vs worst hours"**, each a negative % with a small label chip (e.g. `modelled`) |
| Look at the round dial (the **water clock**) | The next 24 hours around a dial. Longer blue wedges are thirstier hours, and a yellow **RUN** arc marks the best window. A green **live** marker means the weather came from today's forecast. |
| Change the city (Chennai, Delhi, Mumbai, Bengaluru, Hyderabad, Pune) | The dial, meters and beakers redraw for that city within a second or two |
| Scroll to **"Where the water goes"** | Two beakers: **Start now** (full power) vs the **Thirst plan**. Each splits into building water and power-plant water. |
| Switch **Room AC** ↔ **Data centre · cooling tower** | Room AC: only power-plant water ("the water leaves at the power plant"). Cooling tower: a second, building-water layer appears ("it drinks twice"). |
| Scroll to **"A slower GPU drinks less"**, press **100% / 85% / 70%** | The GPU drawing changes, **Time to finish** goes up and **Energy for the job** goes down, each tagged `placeholder` |
| Scroll to **"Plan · Run · Receipt · Rating"** | The four-step pipeline and a sample receipt stamped **Sample** |
| Scroll to **Leaderboard · small labs** | The top small labs, each marked **(simulated)**, with scores and badges |
| Scroll to the end | **"Tonight's run can drink less."** with two copyable commands: `pip install thirst` and `thirst register …`. Press **Copy** and paste somewhere to check. |
| Click any label chip (`modelled`, `placeholder`, …) | It opens the **Assumptions** page at that factor |

**Problems to report:**
- A blank area, or a spinner that never stops.
- A red error box.
- A number with no label chip next to it.
- Text you can't read.
- On a phone, the page scrolls sideways.

### A2. Planner `/plan`

| Do | You should see |
|---|---|
| Press **Plan a job →** on the home page | **"When should your GPU job run?"** with the city already filled in |
| Press the **Overnight fine-tune** preset (2 × RTX 4090 · 6 h · by 9 AM) | The form fills in: GPU model, **How many GPUs?**, **Hours of work at full GPU power**, **Deadline (India time)** |
| Press **Plan** | Within about 1 second, a **"Your plan"** card appears with one sentence: when to start, the GPU power % and when it ends. Under it, **What it saves** shows ranges such as **18 to 19%** with chips. A chart shows the hours, the plan shading and the deadline line. |
| Move the slider from **Carbon only** to **Water only** | The label changes at once and no new request is sent. *Today the plan itself stays the same (see the note at the top).* |
| Press **How do we know?** | You land on the Assumptions page |
| Try a bad input: deadline in the past, 0 hours, or 1,000 GPUs | A clear message next to the field, and an error summary at the top. No crash. |
| Try **Two-day pretrain** (8 × A100 · 30 h · not pausable) | A plan that runs over two days. The card shows the finish **day** when it differs from the start day. |

**Problems to report:**
- The plan takes more than 3 seconds.
- A savings number shown without a range.
- The page breaks after moving the slider.

### A3. Leaderboard `/leaderboard`

| Do | You should see |
|---|---|
| Open **Leaderboard** in the top menu | Weight-class tabs (**D1** small labs ≤ 16 GPUs, D2, D3, D4) and a ranked table with medals for the top 3, score rings and badges (Bronze 45+, Silver 60+, Gold 75+, Platinum 90+) |
| Switch the tabs | Each class shows only its own labs. Empty classes say so plainly. |
| Click **Demo Lab, Chennai (simulated)** | Its site page |

### A4. A lab's page `/sites/<id>`

You should see:
- The lab name, city and class.
- A 0–100 score with a badge ladder showing the points needed for the next badge.
- The score's parts: capture, measurement, coverage.
- **Recent receipts**.

Demo labs are labelled simulated.

Then click a receipt (for example `/receipts/s_simaaaaaaa/j_zrwzqebwoeb5`) to open **Your receipt**. It shows:
- the run window and GPUs
- energy, with `measured` or `modelled`
- water and CO₂ against "if you had started right away"
- the capture %

### A5. Assumptions `/assumptions`

You should see:
- A **"How sure we are"** bar. Today it shows 30 design choices, 18 placeholders, 8 sourced and 1 calibrated, out of 57 factors.
- Jump chips for each group: Data, GPUs, Cities, Sources, …
- Every factor with its value, its range, a status chip and a source link.

Click a jump chip and the page should scroll to that group.

### A6. Edge cases

| Do | You should see |
|---|---|
| Open `/nothing-here` | **"We couldn't find that page"** with a link back to the planner |
| Open `/sites/s_aaaaaaaaaa` (no such lab) | A clear "not found" message, not a blank page |
| Refresh while on `/plan`, `/leaderboard` or a site page | The same page loads again (no 404 from the host) |
| Use only the keyboard (Tab, Enter, arrow keys on the slider) | Every control can be reached and used, with a visible focus ring |

---

## Part B: The CLI on any computer (no GPU needed)

This shows what a lab member sees in the terminal. To try it without leaving a lab on the public board, register with `--private`.

> **Clean up afterwards.** A test site stays in the live database. Only a maintainer with AWS access can delete it, so tell them the site id:
> ```
> python scripts/seed.py --profile thirst --stage dev --delete-site <site_id>
> ```

### B1. Install

```
pip install thirst
thirst --version
```
Expected: `thirst 0.3.1` (or newer).

To try unreleased changes from `main`, install from a checkout with `pip install ./cli`.

### B2. Check the setup before registering

```
$ thirst doctor
[ok]   Python 3.12.5
[FAIL] Config: Run `thirst register` first.  -> run `thirst register`
[ok]   NVIDIA GPU: 1 x NVIDIA GeForce RTX 3050 6GB Laptop GPU (model RTX-3050-Laptop)
[ok]   GPU energy counter
[FAIL] GPU power cap permission: The NVIDIA driver reported an error while reading the GPU. Run `nvidia-smi`.  -> run `nvidia-smi` to see the GPU state
[ok]   Restore marker: none left over
```

What each line means:
- **Config FAIL**: expected, because you haven't registered yet.
- **GPU lines**: on a computer without an NVIDIA GPU, they fail. That's fine: use `--modelled` later.
- **Power cap FAIL on a laptop**: expected. Most laptops don't let software change the GPU power limit. The message is misleading and is tracked in `docs/TODO.md` 4.1.a. Jobs still run and are measured with `--no-cap`.

### B3. Register the lab

```
$ thirst register --name "Guide Test Lab" --city Chennai --cooling room_ac --gpus 1 --private
Registered site s_bcuta4hrjn (division D1).
Site page: https://main.dzxkrtlc7xqfx.amplifyapp.com/sites/s_bcuta4hrjn
The site key was saved to C:\Users\you\.thirst\config.toml (private to your user). It is not shown again.
```

- The key is never printed.
- `--cooling` is one of `room_ac`, `air_chiller` or `evaporative`.
- Leave out `--private` to appear on the leaderboard.

Run `thirst doctor` again. Now **Config**, **API reachable** and **Your clock vs the server: 0 s apart** are `[ok]`.

### B4. Get a plan without running anything

```
$ thirst plan --hours 4 --deadline "2026-10-12 09:00"
Plan: start 12:47, cap 70%, done by 17:14
Expected savings compared with starting right away (ranges, modelled):
  Water  18 to 19%
  CO2    18 to 19%
  Energy 20 to 21%
Plan id: p_dipzk7zwnx. Assumptions: /assumptions
```

- The deadline is India time.
- `--pausable` allows pauses. On Windows it prints "Pausing is not available on Windows, so the job will run without pauses."
- `--alpha 0` means least CO₂ and `--alpha 1` means least water.
- `--json` prints the full server answer.

### B5. See what a run would do

```
$ thirst run --hours 4 --deadline "2026-10-12 09:00" --dry-run -- python train.py
Plan: start 12:47, cap 70%, done by 17:14
Dry run: nothing is started. The CLI would make these changes:
  11 Oct 12:00  start the command at 70% power
  11 Oct 18:00  planned end
```

The dry run shows hour slots (12:00–18:00) while the plan line shows exact times. That mismatch is known: `docs/TODO.md` 4.1.c.

### B6. A real (short) run, without touching the GPU

`--modelled` estimates the energy from the GPU model instead of reading the hardware. `--now` starts right away. This 2-minute "training" job just sleeps:

```
$ thirst run --now --modelled --gpu-model RTX-3050-Laptop --gpus 1 --hours 0.05 --deadline "2026-10-12 09:00" -- python -c "import time; print('training...', flush=True); time.sleep(120); print('done', flush=True)"
Plan: start 12:48, full power (no cap), done by 12:51
training...
done
Thirst receipt j_5c5ke35mv4b7
  Ran      11 Oct 12:48 to 12:50 IST (2 min) on 1 x NVIDIA GeForce RTX 3050 Laptop GPU, uncapped
  Energy   0.00 kWh GPU (modelled)
  Water    0.0 L (modelled); if you had started right away: 0.0 L
  Carbon   0.00 kg CO2 (modelled); if you had started right away: 0.00 kg
  Saved    0% water and 0% CO2 compared with starting right away (modelled)
  Capture  You took 0% of the possible saving
  Score    Site score 0 (Provisional)
  Receipt  https://main.dzxkrtlc7xqfx.amplifyapp.com/receipts/s_bcuta4hrjn/j_5c5ke35mv4b7
```

Why the receipt looks like this:
- **`--modelled` needs `--gpu-model` and `--gpus`**, even when a GPU is present (`docs/TODO.md` 4.1.d). GPU ids are listed on the Assumptions page under GPUs.
- **Zeros are expected.** A 2-minute job is a few Wh, which rounds to `0.00 kWh` (4.1.e). `--now` means you chose not to wait, so the saving and capture are 0%.
- **The receipt link is 404 for a private site.** Private sites hide their receipts (4.1.f). For a public site, the link opens the receipt page.
- **Your command's output still shows.** It also goes to a log under `~/.thirst/logs/`.

For a meaningful receipt, use a job of at least about 1 hour and let Thirst wait for the planned start (drop `--now`).

### B7. Saved receipts and the outbox

```
$ thirst receipt show j_5c5ke35mv4b7
Thirst receipt j_5c5ke35mv4b7
  ... (the same receipt, read from ~/.thirst/receipts/)

$ thirst sync
Nothing to send: the outbox is empty.
```

To test the offline path, turn off the network just before a short run ends:
1. The receipt is saved on disk and the CLI says it is **queued**.
2. Turn the network back on.
3. `thirst sync` sends it and prints the result.

If you press Ctrl-C while the receipt is being sent, the CLI exits with code 130 and says to run `thirst sync`.

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

python scripts/local_api.py                                   # real API on :3000, in-memory DB
cd web && VITE_API_URL=http://127.0.0.1:3000 npm run dev       # site on :5173

npm --prefix web run e2e                                       # Playwright against the live site (read-only)
bash scripts/smoke.sh https://l6y3i40hh4.execute-api.ap-south-1.amazonaws.com
```

The e2e result on 2026-10-11 against the live site was 74 passed, 4 skipped and 1 flaky. The flaky one was the phone jump-link test, which passed on re-run.

---

## What a normal user should come away with

1. **"My job uses water twice, and my city's hours differ."** That comes from the water clock and the beakers.
2. **"There is a simple plan: start at X, GPU at Y%, done by Z."** That comes from the planner card.
3. **"Running it is one command, and my GPU is safe."** That comes from `thirst run`, which always restores the power limit.
4. **"I get proof, and my lab can climb a fair board."** That comes from the receipt, the score and the weight classes.
5. **"They tell me which numbers are measured and which are guesses."** That comes from the label chips and the Assumptions page.

If any of these doesn't come across during your test, write down where you got stuck. That is the most useful feedback.
