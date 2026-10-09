# 08 — Reference contracts

Read-only reference for all phases. If code and this file disagree, fix one of them **in the same PR**
and note it in `AGENTS.md`. Times are ISO 8601 with `+05:30`. Energy is in kWh, water in litres, carbon in kg CO₂e.

[← Index](README.md)

---

## 1. Environment variables

| Variable | Where | Example | Notes |
|---|---|---|---|
| `TABLE_WEATHER` / `TABLE_SITES` / `TABLE_PLANS` / `TABLE_RECEIPTS` | Lambdas | `thirst-dev-sites` | Set by SAM |
| `SERVER_SECRET_PARAM` | `api`, `explain` | `/thirst/server_secret` | SSM SecureString, read once per cold start |
| `BEDROCK_MODEL_ID` | `explain` | *(set after access is approved)* | Empty → template only |
| `BEDROCK_REGION` | `explain` | `ap-south-1` or `us-east-1` | TRD §2 |
| `POWERTOOLS_SERVICE_NAME`, `LOG_LEVEL` | Lambdas | `thirst`, `INFO` | |
| `VITE_API_URL` | web build | `https://abc.execute-api.ap-south-1.amazonaws.com` | Amplify env |
| `VITE_USE_MOCKS` | web | `false` | `true` in local dev before the API exists |
| `THIRST_API_URL`, `THIRST_TOKEN` | CLI | | Override `config.toml` |

---

## 2. Data file schemas

### 2.1 `src/engine/data/factors.json`

```json
{
  "version": "2026-10-09.1",
  "factors": [
    {
      "id": "wf_coal",
      "group": "grid_water",
      "label": "Coal plant water consumption",
      "value": 3.25, "low": 3.0, "high": 3.5,
      "unit": "L/kWh",
      "status": "sourced",
      "source": "MoEFCC notification 7 Dec 2015, amended 28 Jun 2018",
      "source_url": "https://powermin.gov.in/sites/default/files/uploads/LS_13122018_Eng.pdf",
      "notes": "Seawater plants exempt; many plants self-report non-compliance."
    }
  ]
}
```

`status` ∈ `measured | sourced | calibrated | placeholder | design_choice | definition`. `low ≤ value ≤ high`. `group` ∈ `cooling | it | grid_carbon | grid_water | grid | stress | gpu | score | planner | people | checks`.

### 2.2 `src/engine/data/gpus.json` (also copied to `cli/thirst/data/gpus.json`, D19)

```json
{ "models": [
  { "id": "RTX-4090", "label": "NVIDIA GeForce RTX 4090", "p_max_w": 450, "p_idle_w": 45,
    "nvml_name_patterns": ["RTX 4090"], "status": "sourced", "source_url": "https://www.nvidia.com/..." }
] }
```

### 2.3 `src/engine/data/cities.json`

```json
{ "cities": [
  { "id": "Chennai", "lat": 13.0827, "lon": 80.2707,
    "stress_category": "extremely_high", "stress_weight": 2.5,
    "source": "WRI Aqueduct 4.0 baseline water stress", "source_url": "https://www.wri.org/aqueduct",
    "lookup_date": "2026-10-09" }
] }
```

`stress_category` ∈ `low | low_medium | medium_high | high | extremely_high`. The value above is an **example**; the real category comes from the 1.7.e lookup.

### 2.4 `src/engine/data/grid_shares.json`

Option A:
```json
{ "kind": "hod_profile", "source": "CSEP Electricity and Carbon Tracker", "period": "2026-09-25/2026-10-08",
  "exported_at": "2026-10-09T11:30+05:30",
  "profiles": { "0": {"coal":0.78,"gas":0.03,"nuclear":0.03,"hydro":0.10,"solar":0.0,"wind":0.05,"other":0.01}, "...": {} },
  "mean_radiation_profile": { "0": 0, "12": 780, "...": 0 },
  "annual_shares": { "coal":0.74,"gas":0.03,"nuclear":0.03,"hydro":0.09,"solar":0.06,"wind":0.04,"other":0.01 } }
```
Option B:
```json
{ "kind": "annual", "source": "Ember", "period": "FY2023-24", "exported_at": "...",
  "annual_shares": { "...": 0 }, "s_avg_solar": 0.06 }
```
Every share map has all 7 sources and sums to 1 ± 1e-6. The numbers above are **illustrative**, not data.

### 2.5 `src/engine/data/powercap_sweep.json`

```json
{ "gpus": {
  "RTX-4090": {
    "gpu_name": "NVIDIA GeForce RTX 4090", "driver": "550.xx", "measured_at": "2026-10-09T16:40+05:30",
    "workload": "resnet18 random 128x3x32x32, 30 warmup + 300 steps",
    "levels": { "1.0": {"tau":1.0,"eps":1.0}, "0.85": {"tau":0.0,"eps":0.0}, "0.7": {"tau":0.0,"eps":0.0} },
    "u": 0.0, "p_idle_w": 0.0, "runs": 2, "raw": []
  } } }
```
(The zeros are placeholders for the shape. The real values come from 04.5.)

### 2.6 `~/.thirst/config.toml`

```toml
api_url = "https://abc.execute-api.ap-south-1.amazonaws.com"
site_id = "s_abcdefghij"
token   = "<64 hex chars, shown once by register>"
```
File mode 0600. Never committed or printed.

### 2.7 `src/engine/data/sample_forecast.json`

A raw Open-Meteo multi-location response (an array of 6) saved on 1.7.a. It is used when the `weather` table has fewer than 48 future rows. Hours are matched by **hour of day**, not by date.

---

## 3. API contract

Base: `ApiUrl`. JSON only. Errors: `{"error": "<code>", "message": "<plain words>"}` (TRD §7). Body size limits: 8 KB (`/plan`, `/sites`, `/explain`), 64 KB (`/receipts`).

### 3.1 `POST /plan`

Request:

| Field | Type | Rule | Default |
|---|---|---|---|
| `city` | string | one of the 6 seed city ids | required **unless `site_id`** is given (D23) |
| `cooling` | string | `room_ac` · `air_chiller` · `evaporative` | required **unless `site_id`** is given (D23) |
| `pue` | number | 1.0 to 3.0, only used for `evaporative` | 1.4 |
| `gpu_model` | string | an id in `gpus.json` | required |
| `gpu_count` | int | 1 to 4096 | required |
| `work_hours` | number | > 0 and ≤ 48 | required |
| `deadline` | string | ISO with an offset; > now; converted to IST | required |
| `pausable` | bool | | `false` |
| `pausable_allowed` | bool | `false` forces non-pausable (D15) | `true` |
| `alpha` | number | 0 to 1, **on the 0.1 grid** (0, 0.1, …, 1) | 0.5 |
| `force_now` | bool | `true` → chosen = Base (`thirst run --now`) | `false` |
| `site_id` | string | `^s_[a-z2-7]{10}$`, must exist | none |

Response 200 (abridged; the full shape is in `tests/fixtures/plan_response.json`):

```json
{
  "plan_id": "p_7f3a2b9c1d",
  "submit_ts": "2026-10-09T21:14:00+05:30",
  "inputs": { "...": "echo of the validated request" },
  "base":   { "start": "2026-10-09T21:14+05:30", "finish": "...", "totals": {"E_fac_kwh":[7.1,7.8,8.6], "W_l":[], "C_kg":[], "D_l":[], "I_l":[]} },
  "chosen": { "alpha": 0.5, "start": "2026-10-10T01:00+05:30", "finish": "2026-10-10T08:10+05:30", "level_summary": "85%",
              "schedule": [ {"slot": "2026-10-10T01:00+05:30", "level": 0.85, "state": "run", "fraction": 1.0} ],
              "totals": {}, "savings_ranges": {"water_pct": [14, 29], "co2_pct": [9, 18], "energy_pct": [10, 13]} },
  "pareto": [ { "alpha": 0.0, "start": "...", "finish": "...", "level_summary": "...", "schedule": [], "totals": {}, "savings_ranges": {}, "point": {"W_l": 0, "C_kg": 0},
                "series_overlay": [ {"slot": "2026-10-09T21:00+05:30", "level": 0.0, "state": "idle_or_off"} ] } ],
  "series": [ {"slot": "2026-10-09T21:00+05:30", "direct_l_per_kwh": 0.0, "grid_l_per_kwh": 2.4, "co2_kg_per_kwh": 0.71, "temp_c": 29.1, "tw_c": 25.3, "level": 0.0, "state": "off"} ],
  "person_days_range": [0.1, 0.2],
  "tags": {"energy": "modelled", "water": "modelled", "co2": "modelled", "tau": "measured", "forecast": "live"},
  "notes": ["pausable_won"],
  "assumptions_url": "/assumptions"
}
```

- Totals are `[low, central, high]` triples. Savings are `[min%, max%]` integers.
- `pareto` always has 11 entries in alpha order (D11). `chosen` equals `pareto[int(round(alpha*10 + 1e-9))]`; the client uses `Math.round(alpha*10)`.
- `series` (48 rows) carries the intensities **plus** the chosen plan's `level`/`state` per slot (`state` ∈ `off | run | pause`). Each Pareto entry's `series_overlay` (48 rows, `level` + `state` only) lets the slider redraw the shading and the level line without a request.
- Errors: 400 `invalid_field`/`unknown_city`/`unknown_gpu`/`deadline_in_past`, 404 `site_not_found`, 413 `body_too_large`, 422 `deadline_too_soon`, 503 `try_again`.

### 3.2 `POST /sites`

Request: `name` (3 to 60), `org?` (≤ 80), `city`, `cooling`, `gpu_count` (1 to 100000), `coverage_declared` (0 to 1), `public` (bool, default true).
Response 201: `{ "site_id": "s_abcdefghij", "token": "<hex>", "division": "D1" }`. The token is shown **once** and never stored (TRD 7.1).

### 3.3 `GET /sites/{id}`

```json
{ "site": {"site_id":"s_…","name":"CSE GPU Lab","org":null,"city":"Chennai","cooling":"room_ac","division":"D1","simulated":false,"public":true},
  "score": { "value": 78, "provisional": true, "badge": "gold", "A": 41.2, "B": "not_rated", "C": 13.4,
             "C_parts": {"measured_share": 9.4, "coverage": 0, "public": 5}, "flex_share": 0.62, "reason": null },
  "monthly_absolute": { "kwh": [], "litres": [], "stress_litres": [], "kg_co2": [], "person_days": [] },
  "recent_receipts": [ {"job_id":"j_…","end_ts":"…","kwh":7.4,"capture":0.86,"no_room":false,"method":"nvml_energy"} ] }
```
`score.value` is `null` with `reason: "needs_flexible_receipt"` when there are no flexible receipts (D10). The exact GPU count is **never** returned (TRD 5.9).

### 3.4 `POST /receipts`

Headers: `X-Thirst-Timestamp` (unix seconds), `X-Thirst-Signature` (hex), `X-Thirst-Site`.

Request body:

| Field | Type | Rule |
|---|---|---|
| `site_id` | string | must equal `X-Thirst-Site` |
| `plan_id` | string \| null | must exist and have `plan.site_id == site_id` (D23). `null` only when `method = "unverified"` (D20, P1) |
| `job_id` | string | `^j_[a-z2-7]{12}$`, unique per site (D12, D22) |
| `start_ts`, `end_ts` | ISO | `start < end`, duration ≤ 72 h |
| `slots[]` | array ≤ 72 | `{hour (ISO, on the hour), run_kwh ≥ 0, idle_kwh ≥ 0, level ∈ {1.0, 0.85, 0.7}}` |
| `cap_applied` | bool | |
| `cap_method` | string | `nvml` · `nvidia_smi` · `clock_lock` · `none` |
| `method` | string | `nvml_energy` · `nvml_power_integration` · `modelled` · `unverified` |
| `gpu` | object | `{name, driver, count}` |
| `exit_code`, `interrupted`, `overran`, `cli_version` | | informational |

Response 200:
```json
{ "receipt_id": "s_…#2026-10-10T08:10+05:30#j_…",
  "scoring":  { "base": {"W_l":0,"C_kg":0,"E_fac_kwh":0}, "best": {}, "actual": {}, "J": {"base":1.0,"best":0.82,"actual":0.845} },
  "absolute": { "base": {}, "best": {}, "actual": {}, "basis": {"observed": 7, "forecast": 1} },
  "capture": 0.86, "no_room": false, "flexible": true,
  "tags": {"energy": "measured", "water": "modelled", "co2": "modelled"},
  "site_score": { "value": 78, "badge": "gold", "provisional": true },
  "url": "/receipts/s_…/j_…" }
```
Errors: 400 `invalid_field`, 401 `bad_signature`/`stale_timestamp`/`missing_signature`, 403 `plan_site_mismatch`, 404 `site_not_found`/`plan_not_found`, 409 `duplicate_job`, 413, 422 `implausible_energy`/`slot_out_of_range`.

### 3.4b `GET /receipts/{site_id}/{job_id}` (D24)

Returns the same shape as the `POST /receipts` 200 response, plus `slots`, `start_ts`, `end_ts`, `method`, `cap_applied`, `cap_method` and `gpu.name` (not the count). 404 `receipt_not_found`; private sites (D26) → 404. `Cache-Control: no-store`. Slot hours past the snapshot carry `"extrapolated": true`.

### 3.5 `GET /leaderboard?division=D1&period=30d&board=score`

```json
{ "division": "D1", "period": "30d", "board": "score", "generated_at": "…",
  "rows": [ { "rank": 1, "site_id": "s_…", "name": "Demo Lab, Chennai (simulated)", "simulated": true, "badge": "gold",
              "score": 81, "provisional": true, "A": 43.0, "C": 13.7, "flex_share": 0.7,
              "monthly_absolute": {"kwh": 0, "litres": 0, "kg_co2": 0, "person_days": 0}, "receipts": 23 } ] }
```

### 3.6 `GET /assumptions`

`{ "version": "...", "factors": [rows from factors.table()], "gpus": [{id, label, p_max_w, p_idle_w, sweep_status}], "cities": [{id, stress_category, stress_weight}], "stress_weights": {...}, "sources": [{name, url, licence}] }`
The web form fills its GPU and city lists from this response (06.2.a).

### 3.7 `POST /explain` (P1)

Request: `{ "text": "≤ 500 chars" }` or `{ "plan_id": "p_…" }`.
Response: `{ "form": {…} | null, "explanation": "3 sentences", "source": "agent" | "template", "note": "daily_limit" | null }`.

---

## 4. Error codes

| Code | HTTP | Plain-words message (shown to users) |
|---|---|---|
| `invalid_field` | 400 | "<field>: <what is wrong>" |
| `unknown_city` | 400 | "We only have data for Chennai, Bengaluru, Hyderabad, Mumbai, Delhi and Pune right now." |
| `unknown_gpu` | 400 | "Pick a GPU from the list." |
| `deadline_in_past` | 400 | "The deadline is in the past." |
| `text_too_long` | 400 | "Please keep it under 500 characters." |
| `missing_signature` / `bad_signature` | 401 | "This receipt could not be verified. Run `thirst doctor`." |
| `stale_timestamp` | 401 | "Your computer clock is more than 10 minutes off." |
| `plan_site_mismatch` | 403 | "This plan belongs to another site." |
| `site_not_found` / `plan_not_found` / `receipt_not_found` | 404 | "We couldn't find that site / plan / receipt." |
| `duplicate_job` | 409 | "This receipt was already recorded." |
| `body_too_large` | 413 | "Request too large." |
| `deadline_too_soon` | 422 | "This job needs until <time> at full power. Pick a later deadline." |
| `implausible_energy` | 422 | "This energy is more than your GPUs can draw. Receipt rejected." |
| `slot_out_of_range` | 422 | "Some hours are outside the job's start and end." |
| `try_again` | 503 | "Something went wrong on our side. Please try again." |

---

## 5. DynamoDB item shapes

### 5.1 `weather`
`{ city, hour, fc_temp, fc_rh, fc_rad, fc_issued, obs_temp?, obs_rh?, obs_rad?, tw, pue_inputs:{t_c}, ci, ewif, ttl }`
Forecast fields are written once per issue and **never overwritten by observations** (05.4 test 2).

### 5.2 `sites`
`{ site_id, name, org?, city, cooling, gpu_count, division, coverage_declared, public, simulated, created_at }`. **No token** (TRD 7.1).

### 5.3 `plans`
`{ plan_id, site_id?, submit_ts, inputs, base, best, pareto_gz (B), forecast_snapshot_gz (B), factor_version, ttl }`. Gzip keeps the item under 100 KB; the hard limit is 400 KB.
Quota items (D13): `{ plan_id: "quota#2026-10-10", n, ttl }`.

### 5.4 `receipts`
`end_ts` in `sk` is always normalised to `YYYY-MM-DDTHH:MM:SS+05:30` (05.7.c), so string order equals time order. All expressions use `ExpressionAttributeNames` for reserved words (`ttl`, `hour`, `name`, `public`).
Receipt: `{ site_id, sk: "<end_ts>#<job_id>", job_id, plan_id, start_ts, end_ts, slots, method, cap_applied, cap_method, gpu, scoring, absolute, capture, no_room, flexible, scored, exit_code, interrupted, overran, created_at }`.
Guard (D12): `{ site_id, sk: "job#<job_id>", sk_receipt: "<end_ts>#<job_id>", created_at }`. `sk_receipt` lets `GET /receipts/{site_id}/{job_id}` find the receipt with 2 reads.

---

## 6. HMAC test vectors

`tests/vectors/hmac.json` is **generated** by `scripts/gen_hmac_vectors.py` (commit both; never hand-copy the hex). The script must reproduce the table below, which was computed with Python `hmac` + `hashlib.sha256` while writing this plan. A CI test re-runs the script and diffs the output. Tests must freeze the clock at `ts` so the skew check passes.

- Token: `token = hex(HMAC_SHA256(key = server_secret_bytes, msg = site_id_utf8))`.
- Signature: `hex(HMAC_SHA256(key = token_hex_string_as_ascii_bytes, msg = ts_ascii + b"." + raw_body_bytes))`.

| # | server_secret | site_id | ts | raw body (exact bytes) | expected |
|---|---|---|---|---|---|
| T1 | `test-secret-not-for-prod` | `s_abcdefghij` | — | — | token `93ec2d429dfd3e011895ec55f2c376fed4534e588f27488ecc3bf1074433d80f` |
| S1 | (token T1) | | `1760030000` | `{"job_id":"j_aaaaaaaaaaaa","site_id":"s_abcdefghij"}` | `f969e9b3fea80e79e243c8f7c82ad61e3b79b113a8d46ad635e4641f0ad8f515` |
| S2 | (token T1) | | `1760030000` | the same body plus **one trailing space** | `d62b451ad1b317247175753360ecd53887d309fb50ae048424d891fba1ab4e0c` (must **not** match S1) |

The secret in these vectors is a test value only. The real secret lives only in SSM (1.6.f).
