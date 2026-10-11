# Thirst: Technical Requirements Document (TRD)

> **Implementation status (11 Oct 2026).** Built and live as specified, with these changes:
> - **Limits (D37):** throttle 200/400, and 1000 sites, 2000 receipts per site and 3000 explain calls per day.
> - **Build:** the Strands layer is built without Docker (`scripts/build_layer.py`).
> - **Deploy:** GitHub Actions with OIDC (D38).
> - **CLI release:** to PyPI by Trusted Publishing.
> - **Bedrock:** model access is blocked for the account, so `/explain` returns the template.
> - **Data:** the power-cap sweep and 17 other factors are still placeholders.
>
> The score rules as built are in [`SPEC.md`](SPEC.md), the factor table in [`ASSUMPTIONS.md`](ASSUMPTIONS.md), and decisions D27–D39 in [`AGENTS.md`](AGENTS.md).

Version 0.3 · 9 Oct 2026 · Read `Idea.md` (why) and `prd.md` (what) first.
Budget: AWS Free Tier credits (target spend under $15) · Region: `ap-south-1` (Mumbai)

New words are explained in the Glossary in `Idea.md` (section 14). Anything marked **PLACEHOLDER** must show a "modelled" tag in the UI and be listed in `ASSUMPTIONS.md`.

---

## 1. Design principles

1. **The engine is plain Python with no AWS imports.** It runs in a notebook, in tests, in Lambda and offline. If AWS fails, the demo still runs locally.
2. **The solver decides; the AI only reads and explains.** The demo works with the AI turned off.
3. **Measured beats modelled, and both are labelled.** Energy from NVML is "measured". Water and CO₂ are "modelled from measured energy".
4. **Ranges, never single savings numbers.** Every saving is computed with a low, central and high factor set.
5. **One unit system.** kWh for energy, litres for water, kg CO₂e for carbon, IST for time, one-hour slots for planning.
6. **Small and boring infrastructure.** Three Lambdas, four tables, no servers, no GPUs on AWS.

---

## 2. Architecture

```
            ┌──────────── User's machine (lab GPU box) ─────────────┐
            │  thirst CLI (Python, nvidia-ml-py)                    │
            │  register → plan → wait → cap → run → pause/resume    │
            │  → measure (NVML every 1 s) → restore cap → receipt   │
            └──────────────────────┬────────────────────────────────┘
                                   │ HTTPS, HMAC-signed receipts
 Browser ──► Amplify Hosting (React + Vite + Recharts)
                                   │
                                   ▼
                     API Gateway (HTTP API, throttled)
                       │                         │
                       ▼                         ▼
              Lambda "api"                 Lambda "explain"
              (engine: plan, receipts,     (Strands Agents SDK
               score, board, assumptions)   + Amazon Bedrock, optional)
                       │
                       ▼
               DynamoDB (on-demand)
        weather · sites · plans · receipts
                       ▲
                       │ hourly
  EventBridge Scheduler ──► Lambda "refresh" ──► Open-Meteo (no key)
```

| Piece | Choice | Why |
|---|---|---|
| IaC | AWS SAM CLI (`template.yaml`) | AWS open source; counts for "Build It" and deploys for "Ship It" |
| Lambdas | Python 3.12, `arm64`, 512 MB; timeout 10 s (`api`, `refresh`), 29 s (`explain`, because HTTP API integrations stop at 30 s) | Cheap and fast |
| Router | Powertools for AWS Lambda (Python) `APIGatewayHttpResolver`, or a 30-line dict router | Powertools is AWS open source and adds logging and validation |
| Web | Vite + React + Recharts on Amplify Hosting | Fast deploy, live URL |
| Data | DynamoDB on-demand, TTL on time-series | No idle cost |
| Schedule | EventBridge Scheduler, `rate(1 hour)` | Forecast refresh |
| AI | Strands Agents SDK + Bedrock small model (`BEDROCK_MODEL_ID` env var) | Optional explain layer |
| Secrets | One server secret in SSM Parameter Store (SecureString), read at cold start | Site tokens are derived, not stored |

**Bedrock region:** check model access in `ap-south-1` first. If the chosen model is not offered there, deploy only `explain` in `us-east-1` or use a cross-region inference profile.

---

## 3. Repo layout

```
thirst/
├─ README.md            # what, why, how to run, AWS services, AI tools used, credits, licences
├─ SPEC.md              # Thirst Score spec v0.2 (from Idea.md section 7)
├─ ASSUMPTIONS.md       # every factor: value, unit, source, status
├─ Idea.md  prd.md  trd.md
├─ template.yaml        # SAM
├─ src/
│  ├─ engine/           # pure Python, no AWS imports
│  │  ├─ units.py
│  │  ├─ wetbulb.py
│  │  ├─ cooling.py     # PUE(h), WUE(h) per cooling type
│  │  ├─ grid.py        # hourly shares → CI(h), EWIF(h)
│  │  ├─ footprint.py   # E, D, I, W, C per hour
│  │  ├─ planner.py     # non-pausable, pausable, Pareto, ranges
│  │  ├─ score.py       # J, Capture, site score, badges, divisions
│  │  ├─ factors.json   # all constants with source and status
│  │  └─ gpus.json      # GPU models with max power (W) and idle power (W)
│  └─ handlers/
│     ├─ api.py         # /plan /sites /receipts /leaderboard /assumptions
│     ├─ refresh.py
│     └─ explain.py
├─ cli/
│  ├─ pyproject.toml
│  └─ thirst/  __main__.py  config.py  client.py  meter.py  powercap.py  runner.py  sweep.py
├─ web/                 # Vite + React + Recharts
├─ data/                # cities.json, grid_shares.json, powercap_sweep.json, sample_forecast.json
├─ notebooks/india_tradeoff_check.ipynb
└─ tests/
```

**Rule:** the repo must only have commits from 8 Oct 2026 onwards. If the repo is not created yet, create it now and commit every 1 to 2 hours.

---

## 4. Data sources

| Data | Source | How we use it | Licence or attribution |
|---|---|---|---|
| Hourly temperature, humidity, solar radiation (forecast + past days) | Open-Meteo forecast API (`hourly=temperature_2m,relative_humidity_2m,shortwave_radiation`, `timezone=Asia/Kolkata`, `forecast_days=3`, `past_days=1`) | Wet-bulb, AC efficiency, solar proxy | Credit Open-Meteo in README; check terms for non-commercial use |
| Last 14 days of weather (Step 0) | Open-Meteo historical/archive API | Step 0 notebook | Same |
| National generation by source, 5-minute | CSEP Electricity and Carbon Tracker (carbontracker.in), underlying data from MERIT India / NLDC SCADA | **Option A** grid model: real hourly share profile | Cite "The CSEP Electricity and Carbon Tracker" as they request. National only, excludes non-SCADA generation |
| Annual generation shares | Ember India data (state and national) | **Option B** grid model and calibration | Ember data licence (check; usually CC-BY) |
| Grid CO₂ factor | CEA CO₂ Baseline Database, 2023-24 weighted average 0.727 t/MWh | Calibrate coal factor | Cite CEA |
| Coal plant water limit | MoEFCC notification 7 Dec 2015, amended 28 Jun 2018 | Coal water factor range | Cite |
| Gas and nuclear water factors | Macknick et al. 2012 (NREL) medians | Other water factors (**verify**) | Cite |
| Water stress category per city | WRI Aqueduct (baseline water stress) | Stress weights | Credit WRI (CC-BY 4.0, check) |
| City water norm | CPHEEO 135 L per person per day | "Person-days of water" | Cite |
| Sanity check of grid shape | Electricity Maps app (visual only; hourly API is paid) | Compare shape | Do not copy data |

---

## 5. Engine specification

### 5.1 Time grid

- Planning window: 48 one-hour slots, starting at the hour of submission (`floor(submit_ts)`), all in IST.
- Deadline index `H_d` = number of whole slots before the deadline. Plans must finish at or before `H_d`.

### 5.2 Wet-bulb temperature (Stull 2011)

T in °C, RH in %, angles in radians:

```
Tw = T·atan(0.151977·(RH + 8.313659)^0.5) + atan(T + RH) − atan(RH − 1.676331)
     + 0.00391838·RH^1.5·atan(0.023101·RH) − 4.686035
```

Test: T = 20 °C, RH = 50% → Tw = 13.7 ± 0.1 °C. Valid roughly for RH 5 to 99% and T −20 to 50 °C.

### 5.3 Cooling models

All IT electricity becomes heat; the cooling system must remove it.

| Type (`cooling`) | PUE(h) | Direct water WUE(h), L per kWh of IT |
|---|---|---|
| `room_ac` (college lab) | `1 + 1/COP(T) + 0.05` with `COP(T) = clip(3.0·(1 − 0.025·(T − 35)), 1.5, 6)` **PLACEHOLDER** | 0 |
| `air_chiller` (air-cooled chiller) | same formula with rated COP 4.5 **PLACEHOLDER** | 0 |
| `evaporative` (cooling tower) | user value, default 1.4 **PLACEHOLDER** | `clip(a + b·Tw, 0, 4)` with a = 0.2, b = 0.1 **PLACEHOLDER** until fitted to the WUE vs wet-bulb curve in Li et al. |

The `+ 0.05` covers fans, lights and UPS losses (**PLACEHOLDER**).

### 5.4 Grid model: hourly carbon (CI) and water (EWIF) per kWh

Sources `k` ∈ {coal, gas, nuclear, hydro, solar, wind, other}. `share_k(h)` sums to 1.

**Option A (preferred if we can export data by Friday 12:00):** take the last 14 days of national 5-minute generation by source from the CSEP tracker, average into an hour-of-day profile `share_k(hod)`. For the forecast, scale the solar share by the forecast radiation ratio and take the difference from coal:

```
s_solar(h) = min(0.6, share_solar(hod) × rad(h) / mean_radiation_profile(hod))
coal(h)    = max(0, share_coal(hod) − (s_solar(h) − share_solar(hod)))
```

**Option B (fallback):** annual shares from Ember, and the same two lines with `share_solar(hod)` replaced by `s_avg × rad(h) / mean_24h(rad)`.

Then:

```
CI(h)   = Σ_k share_k(h) × EF_k        # kg CO₂ per kWh
EWIF(h) = Σ_k share_k(h) × WF_k        # litres consumed per kWh
```

**Carbon factors (direct combustion basis, same as CEA and CSEP):**

| Source | EF, kg CO₂/kWh | Status |
|---|---|---|
| Coal | **calibrated:** `EF_coal = (0.727 − s_gas·EF_gas) / s_coal` using 2023-24 annual shares, so the yearly mix matches CEA (expect about 0.95 to 1.0) | Calibrated to CEA |
| Gas | 0.49 | Sourced (IPCC median), verify |
| Nuclear, hydro, solar, wind | 0 on direct basis (lifecycle toggle in v0.4) | Sourced (CEA method) |

**Water factors (consumption):**

| Source | WF, L/kWh low / central / high | Status |
|---|---|---|
| Coal | 3.0 / 3.25 / 3.5 (MoEFCC limits; note seawater plants are exempt and many plants self-report non-compliance) | Sourced |
| Gas (combined cycle) | 0.5 / 0.75 / 1.0 | Macknick 2012, **verify** |
| Nuclear | 1.75 / 2.5 / 3.25 | Macknick 2012, **verify** |
| Hydro | 0 by default (reservoir evaporation is disputed); toggle on Assumptions page | Design choice |
| Solar PV | 0 (panel cleaning is small) | Design choice |
| Wind | 0 | Sourced |

Transmission losses are **not** applied in v0 (`grid_loss_factor = 1.0`); add in v0.4 with the current CEA figure.

### 5.5 Water stress weights

`data/cities.json`: for each of the 6 seed cities, the WRI Aqueduct baseline water stress category, looked up by the data owner during the build and recorded with the date. Weights (design choice, in `SPEC.md`): Low 1.0, Low-medium 1.25, Medium-high 1.5, High 2.0, Extremely high 2.5.

`σ_site` = weight of the site's city. `σ_grid` = same value in v0 (labelled). v0.4 maps each grid region to the basins of its main coal plants.

### 5.6 GPU power levels and the power-cap sweep

Levels `l` ∈ {100%, 85%, 70%} of the GPU's default power limit.

| Level | τ_l (work per hour, relative) | ε_l (energy per unit of work, relative) | Status |
|---|---|---|---|
| 100% | 1.00 | 1.00 | Definition |
| 85% | 0.97 | 0.88 | **PLACEHOLDER → measured sweep** |
| 70% | 0.90 | 0.80 | **PLACEHOLDER → measured sweep** |

Power in an hour at level `l`: `P_l = u × P_max × ε_l × τ_l` per GPU, where `u × P_max` is the average draw at 100% (default `u = 0.9`, **PLACEHOLDER**, replaced by the sweep's measured average).

Idle power while paused: `P_idle` per GPU from `gpus.json` (default 0.1 × P_max, **PLACEHOLDER**, replaced by a 60-second idle reading in the sweep).

### 5.7 Footprint per hour

For GPU energy `g(h)` in kWh in slot `h`:

```
E_IT(h)  = g(h) × 1.2                      # CPU, RAM, fans: PLACEHOLDER
E_fac(h) = E_IT(h) × PUE(h)
D(h)     = E_IT(h) × WUE(h)                # direct water, litres
I(h)     = E_fac(h) × EWIF(h)              # indirect water, litres
W(h)     = D(h) × σ_site + I(h) × σ_grid   # stress-weighted litres
C(h)     = E_fac(h) × CI(h)                # kg CO₂
```

People unit: `person_days = (D + I) / 135` (unweighted litres; label "of city water at the CPHEEO norm").

### 5.8 Planner

**Inputs:** `city, cooling, pue (if evaporative), gpu_model, gpu_count N, work_hours, deadline, pausable, alpha ∈ [0, 1]`.

**Step 1, Base plan:** start at slot 0, level 100%, run `work_hours` slots (last slot partial). Compute totals `W_base, C_base, E_base`.

**Step 2, slot cost per unit of work:**

```
cost(h, l) = [ wW·W(h,l)/W_base + wC·C(h,l)/C_base + wE·E_fac(h,l)/E_base ] / τ_l
wW = 0.8·alpha,  wC = 0.8·(1 − alpha),  wE = 0.2
```

**Step 3a, not pausable:** for every start `s` and every constant level `l`: duration `n = work_hours / τ_l` slots; valid if `s + ceil(n) ≤ H_d`; total = sum of slot costs (partial last slot). Pick the lowest. At most 48 × 3 candidates, so this is exact and instant.

**Step 3b, pausable:**
1. For each slot `h < H_d`, choose `l*(h) = argmin_l cost(h, l)`.
2. Sort slots by `cost(h, l*(h))`; take the cheapest until `Σ τ ≥ work_hours` (last slot partial).
3. **Add idle cost** for every unselected slot between the first and last selected slot (GPU memory stays allocated): `N × P_idle` kWh per idle slot, through the same footprint formulas.
4. **Limit fragmentation:** if there are more than 3 pause gaps, fill the shortest gap with running slots at their `l*` and drop the most expensive selected slot; repeat until 3 gaps or fewer.
5. Compare with the best non-pausable plan (Step 3a) and return the cheaper one.

**Step 4, Pareto:** run Steps 2 to 3 for `alpha = 0, 0.1, ..., 1`. Return unique `(W_total, C_total)` points and mark the chosen one.

**Step 5, ranges:** repeat Base and the chosen plan with the low and high factor sets (WUE ±40%, coal WF 3.0 vs 3.5, other WF low/high from 5.4, EF ±15%, COP ±15%). Report each saving as `min% to max%` across low, central and high. Absolute numbers are also shown as ranges.

**Output:** schedule (list of `{slot_start, level, run|pause}`), finish time, totals for Base and plan under three factor sets, Pareto points, hourly series for the chart, a `forecast_snapshot` (the hourly PUE, WUE, CI, EWIF arrays used).

### 5.9 Score

**Fairness rule:** Base, Best and Actual are scored with the `forecast_snapshot` saved at submit time. Absolute numbers on the receipt use observed weather from the `weather` table.

**Turning a receipt into three footprints:**

- **Actual:** measured GPU kWh per slot `g_run(h)` and idle kWh `g_idle(h)`, through 5.7 with the snapshot.
- **Base:** work done at full power. `E_base_GPU = Σ_h g_run(h) / ε_l(h)`. Spread evenly over slots starting at slot 0, length `Σ_h τ_l(h)` (work done in hours at full power).
- **Best:** the Best plan from submit time, with every slot's energy scaled by `E_base_GPU / E_base_GPU_model`. This works because all footprint terms are linear in energy for fixed hours.

```
J = 0.45·W/W_base + 0.35·C/C_base + 0.20·E_fac/E_base_fac
Capture = clip((1 − J_actual) / (1 − J_best), 0, 1)
If (1 − J_best) < 0.03 → "no room to shift", excluded from Capture
```

**Site score (rolling 30 days):**

```
A = 50 × Σ(Capture_j × E_j) / Σ E_j            (flexible jobs only)
B = "Not rated" in v0
C = 10 × (NVML-measured kWh / all reported kWh)
  + 5 × [coverage ≥ 80%]   (v0: self-declared at register, tagged "self-declared")
  + 5 × [site publishes receipts]
Provisional score = (A + C) / 70 × 100
```

Badges: Platinum ≥ 90, Gold ≥ 75, Silver ≥ 60, Bronze ≥ 45. Gold and Platinum need flexible energy ≥ 30% of total. Divisions by GPU count: D1 ≤ 16, D2 17 to 256, D3 257 to 4,096, D4 > 4,096. **The public board shows the division, not the exact GPU count** (privacy for companies).

---

## 6. Hardware layer (CLI)

### 6.1 Energy measurement

- Package `nvidia-ml-py` (`import pynvml`).
- Sampler thread every 1 s per GPU:
  - Volta and newer: `nvmlDeviceGetTotalEnergyConsumption` (millijoules since driver load). Energy = difference between samples.
  - Older GPUs: integrate `nvmlDeviceGetPowerUsage` (milliwatts) × 1 s.
- Bucket energy into IST one-hour slots and into `run` vs `idle` by the runner's state.
- Record GPU name, driver version, power limit used, and measurement method in the receipt.

### 6.2 Power cap

- Read allowed range: `nvmlDeviceGetPowerManagementLimitConstraints` (min, max in mW) and default `nvmlDeviceGetPowerManagementDefaultLimit`.
- Set: `nvmlDeviceSetPowerManagementLimit` or `nvidia-smi -i <i> -pl <watts>`. **Needs root.** If refused, continue uncapped and write `cap_applied: false` in the receipt.
- Clamp the target to the allowed range.
- **Always restore** the original limit: `atexit`, `SIGINT`, `SIGTERM` handlers, and in `finally`.
- Laptops often block power limits. Fallback knob: `nvidia-smi -lgc <min>,<max>` (lock clocks), then `-rgc` to reset.
- Power limits reset on reboot or driver reload. Persistence mode (`nvidia-smi -pm 1`) keeps the driver loaded between runs.

### 6.3 Pause and resume

- Start the user's command with `subprocess.Popen(cmd, start_new_session=True)` so it gets its own process group (data-loader workers included).
- Pause: `os.killpg(pgid, SIGSTOP)`. Resume: `os.killpg(pgid, SIGCONT)`.
- GPU memory stays allocated; **idle power is measured and counted**.
- **Supported in v0:** single-process jobs (one Python process, any number of data-loader workers). **Not supported in v0:** multi-process distributed jobs (`torchrun`, NCCL), because collective timeouts and network clients (for example experiment trackers) may fail after a long pause. For those, the CLI forces non-pausable mode and says so. v1 adds checkpoint and restart.

### 6.4 Power-cap sweep (`thirst sweep`, Friday afternoon, about 45 minutes)

- Workload: ResNet-18 training on random tensors (batch 128, 3×32×32, 10 classes), 300 steps after 30 warm-up steps. No dataset download, so results repeat.
- For each level 100%, 85%, 70%: record wall time and NVML energy. Also record 60 s idle power.
- Compute `τ_l = time_100 / time_l` and `ε_l = (energy_l / steps) / (energy_100 / steps)`. Save to `data/powercap_sweep.json` with GPU name and driver.
- The engine loads this file if present and marks τ and ε as **measured** for that GPU model.

### 6.5 No NVIDIA GPU

`--modelled` estimates power as `u × P_max × ε_l × τ_l` from `gpus.json` and tags the receipt "Modelled". It gets no measurement points in score part C.

### 6.6 Optional (P2): wall meter

A smart plug with energy metering gives whole-machine energy. Read it over the local network, and if present, replace the 1.2 overhead factor with the measured ratio. Tag "measured at wall".

---

## 7. API

All bodies are JSON. Times are ISO 8601 with `+05:30`. Errors: `{ "error": "code", "message": "plain words" }`.

| Method + path | Body / params | Returns |
|---|---|---|
| `POST /plan` | `city, cooling, pue?, gpu_model, gpu_count, work_hours, deadline, pausable, alpha, site_id?` | `plan_id, submit_ts, base, chosen, pareto[], savings_ranges, series[], person_days_range, tags` |
| `POST /sites` | `name, org?, city, cooling, gpu_count, coverage_declared` | `site_id, token` (shown once), `division` |
| `GET /sites/{id}` | | site, score parts, badge, recent receipts, monthly absolute footprint |
| `POST /receipts` | `site_id, plan_id, job_id, start_ts, end_ts, slots[{hour, run_kwh, idle_kwh, level}], cap_applied, method` + headers `X-Thirst-Timestamp`, `X-Thirst-Signature` | receipt: base/best/actual (scoring and absolute), Capture, tags |
| `GET /leaderboard` | `division=D1`, `period=30d`, `board=score` | ranked rows |
| `GET /assumptions` | | every factor with value, unit, source, status |
| `POST /explain` | `{ "text": "..." }` or `{ "plan_id": "..." }` | `{ form?, explanation, source: "agent" or "template" }` |

**Example `/plan` response (trimmed):**

```json
{
  "plan_id": "p_7f3a",
  "submit_ts": "2026-10-09T21:14:00+05:30",
  "chosen": {
    "schedule": [{"slot": "2026-10-10T01:00+05:30", "level": 0.85, "state": "run"}],
    "finish": "2026-10-10T08:10+05:30",
    "level_summary": "85%"
  },
  "savings_ranges": {"water_pct": [14, 29], "co2_pct": [9, 18], "energy_pct": [10, 13]},
  "person_days_range": [0.1, 0.2],
  "tags": {"energy": "modelled", "water": "modelled", "tau": "measured"}
}
```

### 7.1 Receipt security and checks

- Site token: `token = HMAC_SHA256(server_secret, site_id)`. Nothing to store; the server recomputes it.
- Signature: `hex(HMAC_SHA256(token, timestamp + "." + raw_body))`. Reject if the timestamp is more than 10 minutes off (stops replay).
- Reject if `Σ kWh > gpu_count × P_max_kW × hours × 1.1`, if `plan_id` belongs to another site, if `job_id` already exists, or if any slot is outside `[start_ts, end_ts]`.
- API Gateway throttling: rate 10 req/s, burst 20 (raised to 200 req/s, burst 400 in D37 so judges are never throttled). CORS: the Amplify domain and `localhost:5173` only.
- Validate every input (types, ranges, lengths). No personal data is collected. Site names are free text, shown publicly, so the form says so.

---

## 8. Data model (DynamoDB, on-demand)

| Table | Keys | Main fields | TTL |
|---|---|---|---|
| `weather` | PK `city`, SK `hour` (ISO) | `fc_temp, fc_rh, fc_rad, fc_issued, obs_temp, obs_rh, obs_rad, tw, pue_inputs, ci, ewif` | 10 days |
| `sites` | PK `site_id` | `name, org, city, cooling, gpu_count, division, coverage_declared, simulated, created_at` | none |
| `plans` | PK `plan_id` | `site_id, submit_ts, inputs, base, best, forecast_snapshot` (compressed JSON) | 14 days |
| `receipts` | PK `site_id`, SK `end_ts#job_id` | `plan_id, slots, actual/base/best (scoring + absolute), capture, method, cap_applied` | none |

- Leaderboard is computed on read: scan `sites` (small), query the last 30 days of `receipts` per site, cache 60 s in Lambda memory. A materialised board is a v1 task.
- **Seed data:** the team's real lab, plus 6 to 10 sites named like "Demo Lab, Chennai (simulated)" with `simulated = true`, generated from real weather and the grid model. Never use real company names.

---

## 9. The "refresh" Lambda

- Runs every hour from EventBridge Scheduler.
- For each seed city: call Open-Meteo with `forecast_days=3` and `past_days=1`. Write forecast fields for future hours and observed fields for past hours.
- Compute `tw`, PUE inputs, `ci`, `ewif` per hour with the engine.
- If Open-Meteo fails: keep the last rows and log a warning. `/plan` falls back to `data/sample_forecast.json` and tags the plan "cached forecast".

---

## 10. Agent (Strands Agents SDK, optional)

- **Role:** turn one English sentence into planner inputs, call `make_plan`, explain the result in 3 short sentences. Always say which numbers are modelled. Never invent numbers.
- **Tools:**

```python
from strands import Agent, tool
from strands.models import BedrockModel
from engine import planner, factors

@tool
def make_plan(city: str, cooling: str, gpu_model: str, gpu_count: int,
              work_hours: float, deadline_iso: str, pausable: bool,
              alpha: float = 0.5) -> dict:
    """Make the lowest-cost plan that meets the deadline. Returns schedule, savings ranges and tags."""
    return planner.plan(city, cooling, gpu_model, gpu_count, work_hours, deadline_iso, pausable, alpha)

@tool
def get_assumptions() -> list:
    """Return every factor with its value, source and status."""
    return factors.table()

agent = Agent(
    model=BedrockModel(model_id=os.environ["BEDROCK_MODEL_ID"]),
    tools=[make_plan, get_assumptions],
    system_prompt=SYSTEM_PROMPT,
)
```

- **Guardrails:** input capped at 500 characters; output capped at 1,000 tokens; a daily counter in DynamoDB refuses calls after 300 per day (3000 since D37); on any error or timeout, return the template explanation.
- **Template explanation (default):** built from plan JSON, for example: "Start at {start} with the GPU at {level}. This finishes by {finish}, before your deadline. Compared with starting now, it saves about {w_lo} to {w_hi}% stress-weighted water and {c_lo} to {c_hi}% CO₂. Energy is modelled from your GPU type; water and CO₂ are modelled from that energy."

---

## 11. Frontend

- Vite + React + Recharts. One API base URL from `VITE_API_URL`.
- Pages: Plan (home), Receipt, Leaderboard, Site, Assumptions.
- **Plan chart (Recharts `ComposedChart`):** stacked bars for direct and grid water per kWh, line for CO₂ per kWh, `ReferenceArea` for planned slots, step line for power level on a second axis.
- **Slider:** the `/plan` response already contains the 11 Pareto plans, so the slider switches between them on the client with no new request. A new request is made only when the form changes.
- Every number renders with a small tag chip ("measured", "modelled", "placeholder") that links to the Assumptions row.
- Phone layout at 360 px: form above, chart full width with horizontal scroll disabled, result card first on small screens.
- Loading and error states in plain words ("Weather data is 2 hours old; using the last forecast").

---

## 12. Infrastructure and cost guardrails

`template.yaml` outline:

```yaml
Globals:
  Function:
    Runtime: python3.12
    Architectures: [arm64]
    MemorySize: 512
    Timeout: 10
Resources:
  Api:        { Type: AWS::Serverless::HttpApi }   # throttling + CORS here
  ApiFn:      { Type: AWS::Serverless::Function }  # handlers/api.handler
  ExplainFn:  { Type: AWS::Serverless::Function }  # Timeout: 29
  RefreshFn:  { Type: AWS::Serverless::Function }  # ScheduleV2 event, rate(1 hour)
  WeatherTbl, SitesTbl, PlansTbl, ReceiptsTbl:     # PAY_PER_REQUEST, TTL where listed
  LogGroups:  # RetentionInDays: 7 for each function
```

| Guardrail | Setting |
|---|---|
| AWS Budgets | Alerts at $10, $25, $50 to two team emails |
| Logs | 7-day retention on every function |
| Bedrock | Small model, 1,000 output tokens, 300 calls per day |
| Never create | EC2 GPU, SageMaker endpoints, OpenSearch domains or Serverless, NAT Gateway, RDS or Aurora, provisioned concurrency |
| Daily check | Billing → Cost Explorer |
| Extra credits | If the free credits run out, the team leader can request $25 more on the event page |

Expected cost for the weekend: under $15 (mostly Bedrock and Amplify).

---

## 13. Step 0 notebook: does the trade-off exist in India?

`notebooks/india_tradeoff_check.ipynb`, about 1.5 hours, owner: data/story.

1. Weather: Open-Meteo archive, last 14 days, Chennai, Bengaluru, Delhi.
2. Grid: Option A (CSEP 5-minute national mix, hour-of-day profile) if exportable; otherwise Option B.
3. For 1 kWh of IT load in every hour, for `evaporative` and `room_ac`: compute W(h) and C(h).
4. Per day: hour of lowest W, hour of lowest C, the gap in hours, and the rank correlation (Spearman) between W(h) and C(h).

| Result | Headline |
|---|---|
| Median gap ≥ 4 h or correlation < 0.3 | "Solar hours vs cool nights: here is the best balance" |
| Otherwise | "Midday wins in India, and here is by how much" (novelty then rests on the power cap, stress weighting, receipts and the rating) |

Save the chart as `docs/india_finding.png` for the video and the blog.

---

## 14. Tests

| Test | Pass condition |
|---|---|
| Stull formula | 20 °C / 50% → 13.7 ± 0.1 °C |
| COP clip | COP stays in [1.5, 6] for T in [0, 50] |
| Grid shares | Shares sum to 1 ± 1e-6 every hour; yearly CI with annual shares = 0.727 ± 0.005 |
| Flat intensities | Best plan = Base plan; Capture marked "no room to shift" |
| Deadline (property test, 500 random inputs) | No plan ends after the deadline; work done ≥ work_hours |
| Idle cost | A pausable plan with a 10-hour gap costs more than the same run hours without the gap |
| Capture bounds | Always in [0, 1] |
| Base energy | With all slots at 100%, `E_base_GPU` = measured run energy |
| Receipt plausibility | Rejects energy above GPU limits |
| Signature | Rejects a changed body and an old timestamp |
| Power cap restore | After Ctrl-C mid-run, the power limit equals the original |
| End to end | CLI receipt appears on the board within 1 minute |
| Phone | All pages usable at 360 px |
| Cost | Cost Explorer under $5 by Saturday night |

---

## 15. Schedule from now (IST) and roles

Roles for 3 people. With 2 people, merge B and C's data tasks into A and C.

- **A, Backend/AWS:** SAM, Lambdas, DynamoDB, API, signing, budgets, deploy, agent.
- **B, Engine/CLI/Hardware:** engine, planner, score, tests, NVML, power cap, sweep, overnight run. Must own the NVIDIA GPU machine.
- **C, Frontend + Data/Story:** React, charts, Amplify, Step 0 notebook, factors and sources, `ASSUMPTIONS.md`, video, writeup, Builder Center blog.

### Friday 9 Oct

| Time | A | B | C |
|---|---|---|---|
| 09:00 to 13:00 | Repo check (history from 8 Oct), budgets, SAM deploy of `api` stub, tables | `wetbulb`, `cooling`, `grid`, `footprint`, `planner` + tests | Step 0 notebook, `factors.json`, `cities.json` (Aqueduct lookup); **headline decided by 13:00** |
| 13:00 to 18:00 | `/plan` on Lambda, `/sites`, `/receipts` with HMAC, `refresh` + schedule | `score.py`, NVML meter, **power-cap sweep**, `thirst plan` | Web skeleton on Amplify, Plan page wired to `/plan`, chart, slider |
| 18:00 to 22:00 | `/leaderboard`, `/assumptions`, throttling, CORS, seed simulated sites | `thirst run` with cap, pause/resume, receipt post | Receipt, Leaderboard, Site, Assumptions pages |
| **22:00** | **Scope lock.** B starts the **real overnight job** with `thirst run --deadline "2026-10-10 09:00" --pausable` so it waits and runs at the planned hours | | |

### Saturday 10 Oct

| Time | Focus |
|---|---|
| 09:00 to 12:00 | Check the overnight receipt and the board. Fix bugs. A: `explain` with Strands (template stays default) |
| 12:00 to 17:00 | Polish: ranges, tags, empty states, phone layout, "person-days" line. India finding chart on home if done |
| 17:00 to 21:00 | **Clean-machine test** (fresh clone, install CLI, register, plan, run with `--modelled`, see board). README, `SPEC.md`, `ASSUMPTIONS.md`, blog draft, rough video cut |
| 21:00 to 23:00 | Fix list only. No new features |

### Sunday 11 Oct

| Time | Focus |
|---|---|
| 08:00 | Check the schedule page for the exact deadline time; move everything earlier if needed |
| 08:00 to 11:00 | Final fixes. **Code freeze 11:00** |
| 11:00 to 14:00 | Record final video (under 3:00, AWS visible), upload unlisted, test signed-out. Writeup with AI tools used |
| 14:00 to 16:00 | **Submit.** Publish the Builder Center blog and link it. Keep buffer |

---

## 16. Risks and fallbacks

| Problem | Fallback |
|---|---|
| No NVIDIA GPU available | `--modelled` mode; borrow a lab machine for the one real recording |
| Power limit refused | `nvidia-smi -lgc` clock lock, or record the sweep on whichever machine allows it |
| Distributed job needs pause | Non-pausable mode (forced by the CLI) |
| CSEP data cannot be exported | Option B grid model (Ember + radiation proxy), labelled |
| Bedrock access late | Template explanation (already default) |
| Amplify build fails | S3 static site + CloudFront |
| Open-Meteo down | Last rows in DynamoDB + `data/sample_forecast.json` |
| Step 0 shows no trade-off | "Midday wins" headline |
| Running late | Cut order from `prd.md` 5.4. Never cut the receipt, slider, result card or assumptions |

---

## 17. Submission checklist

- [ ] Public repo, commits only from 8 Oct onwards, MIT licence
- [ ] README: problem, how to run CLI and web, architecture, AWS services, **AI coding tools used**, credits and licences (Open-Meteo, CSEP, Ember, CEA, WRI Aqueduct, Recharts, nvidia-ml-py, Strands, Powertools)
- [ ] Live URL works signed-out and on a phone
- [ ] Video under 3:00, unlisted, opens signed-out, AWS on screen and named out loud
- [ ] Writeup: problem → what we built → where AWS fits (Lambda, API Gateway, DynamoDB, EventBridge Scheduler, Amplify, Bedrock, Strands Agents SDK, SAM CLI) → limits → AI tools
- [ ] Builder Center blog published and linked
- [ ] Every team member registered and on the team **before** submitting
- [ ] Billing checked
