# Phase 02 — Engine (pure Python)

> **Status on 11 Oct 2026: ✅ done and reviewed.**
> - 317 tests, 99% coverage; the fixtures are generated and checked for staleness.
> - `gpus.json` has 42 sourced models (PR #8).
> - **Placeholder data** remains where plan 1.7 is open: 18 of 57 factors, and an empty `powercap_sweep.json` (so every plan picks 70%).
> - The factor table is now generated into [`../../ASSUMPTIONS.md`](../../ASSUMPTIONS.md); the score rules are in [`../../SPEC.md`](../../SPEC.md).

Owner: **B** (2.1 to 2.7, 2.9) · **C** writes the `factors.json`/`gpus.json` content (2.2.a, 2.2.b) · **A** owns `score.py` (2.8, Fri 15:00 to 17:00)
Window: **Fri 09:30 to 15:30** · Gate: **M1b** (see the [load-balancing table](README.md#load-balancing-after-the-ecc-planner-review))
Source: TRD §5 (engine spec), §14 (tests), Idea §6–7.
Rule (TRD §1.1): **no AWS imports, no numpy (D16), no network, no clock reads inside pure functions.**
Every function takes its inputs explicitly (time, factors, forecast). That makes it testable and the same in a notebook, in Lambda and offline.

[← Index](README.md) · Contracts used here: [08 §2 data files](08-reference-contracts.md#2-data-file-schemas)

### Implementation status (9 Oct 2026)

| Step | Status |
|---|---|
| 2.1 units, 2.3 wet-bulb, 2.4 cooling, 2.5 grid | **Done** (tests first; Stull reference points and property tests) |
| 2.2 factors and data files | **Done**, but values marked `placeholder` stay so until plan 1.7: city water-stress categories, the annual national mix (`grid_shares.json`), GPU idle power, gas/nuclear water factors, and the whole power-cap sweep (`powercap_sweep.json` is empty) |
| 2.6 forecast and footprint | **Done** |
| 2.7 planner | **Done**: also returns `best` (D27); fixtures written by `scripts/gen_fixtures.py` (2.7.k) and `explain_template` is in `explain.py` (2.7.l) |
| 2.8 score | **Done** (receipt scoring, site score, badges, divisions, page and leaderboard views); fixtures for receipt and leaderboard written |
| 2.9 review and freeze | **Done**: ECC code and Python reviews run; CRITICAL and HIGH findings fixed (input hardening, read-only caches, private-site view, factor-version hash). Engine coverage 99%. Open: tight-deadline pausable plans do not escalate levels (note `pause_no_room`) |

Differences from the text below: the engine also has `errors.py`, `forecast.py` and `explain.py`; `forecast_snapshot` stores raw weather rounded to 5 decimals; the pausable plan keeps only its last run slot partial.

---

## 2.0 Module map and conventions

| Module | Public API (stable from M1b) | Depends on |
|---|---|---|
| `units.py` | `IST`, `SLOT_H`, `PERSON_DAY_L`, `floor_hour(ts)`, `slot_starts(t0, n)`, `slot0_capacity(submit_ts)`, `mj_to_kwh(x)`, `w_h_to_kwh(w, h)` | stdlib |
| `factors.py` | `load_factors(path=None) -> Factors`, `Factors.central/low/high -> FactorSet`, `Factors.table() -> list[dict]`, `load_gpus()`, `load_cities()`, `load_sweep()` | `units` |
| `wetbulb.py` | `stull_tw(t_c, rh_pct) -> float`, `in_valid_range(t_c, rh_pct) -> bool` | — |
| `cooling.py` | `Cooling` enum, `cop(t_c, rated, fs)`, `pue(cooling, t_c, fs, pue_user=None)`, `wue(cooling, tw_c, fs)` | `wetbulb`, `factors` |
| `grid.py` | `hourly_shares(slots, rad, profile, fs) -> list[dict[str,float]]`, `ci(shares, fs)`, `ewif(shares, fs)`, `calibrate_coal_ef(annual_shares, ef_gas, target)` | `factors` |
| `forecast.py` | `ForecastSnapshot` (frozen), `build_snapshot(city, cooling, weather_rows, fs, submit_ts, pue_user)` | `cooling`, `grid`, `wetbulb` |
| `footprint.py` | `SlotFootprint`, `Totals`, `footprint(gpu_kwh_by_slot, snap, fs, sigma_site, sigma_grid) -> (list[SlotFootprint], Totals)` | `units` |
| `planner.py` | `PlanRequest` (frozen), `plan(req, weather_rows, now=None) -> dict` (API shape), plus internals `base_plan`, `slot_cost`, `plan_non_pausable`, `plan_pausable`, `pareto`, `ranges` | all above |
| `score.py` | `j_value`, `capture`, `receipt_footprints(receipt, plan_record, observed_rows)`, `site_score(receipts_30d, site)`, `badge(score, flex_share)`, `division(gpu_count)` | `footprint`, `forecast` |

Conventions:

- `@dataclass(frozen=True, slots=True)` for every value object. Functions return **new** objects, never change their inputs (immutability rule).
- Timestamps are timezone-aware `datetime` in **IST** (`ZoneInfo("Asia/Kolkata")`). Naive datetimes raise `ValueError`.
- Units are in the names: `_kwh`, `_l` (litres), `_kg`, `_pct`, `_w`, `_c` (°C).
- Errors: `EngineError(code, message)` with codes from 08 §4 (for example `deadline_too_soon`, `unknown_city`, `unknown_gpu`).
- Floats are rounded **only at the API boundary** (handlers), never inside the engine.

`forecast.py` is a small addition to the TRD layout. It holds the `forecast_snapshot`, which TRD §5.8 and §5.9 both need.

---

## 2.1 `units.py` (20 min, P0)

**Tests first** (`tests/engine/test_units.py`)

1. `floor_hour(2026-10-09T21:14+05:30) == 21:00+05:30`.
2. `slot0_capacity(21:14) == 46/60` (D7); `slot0_capacity(21:00) == 1.0`.
3. `slot_starts(t0, 48)` gives 48 hourly IST datetimes, strictly increasing, with no DST (IST has none).
4. `mj_to_kwh(3_600_000_000) == 1.0`; `w_h_to_kwh(400, 6) == 2.4`.
5. A naive datetime raises `ValueError`.

**Implement**

- **2.1.a** `IST = ZoneInfo("Asia/Kolkata")`, `SLOT_H = 1.0`, `WINDOW_SLOTS = 48`, `PERSON_DAY_L = 135.0` (CPHEEO; also listed in `factors.json` so it shows on the Assumptions page).
- **2.1.b** `ensure_ist(ts)` converts aware datetimes to IST and rejects naive ones.
- **2.1.c** `deadline_slots(submit_ts, deadline) -> int` = number of **whole** slots, counted from `floor_hour(submit_ts)`, that end on or before the deadline (TRD 5.1 `H_d`), capped at 48. Return the cap flag too, so the API can say "deadline beyond 48 h; planned within the next 48 h".

**Done when:** tests pass; 100% coverage of the module.

---

## 2.2 `factors.py` + `data/factors.json` + `data/gpus.json` (40 min, P0)

**Tests first** (`tests/engine/test_factors.py`)

1. Every entry in `factors.json` has the required keys (08 §2.1): `id, value, low, high, unit, status, source, source_url, notes`; `status ∈ {measured, sourced, calibrated, placeholder, design_choice, definition}`.
2. `low ≤ value ≤ high` for every numeric factor.
3. `Factors.central().get("wf_coal") == 3.25`, `.low() == 3.0`, `.high() == 3.5`.
4. `table()` returns one row per factor, including GPU-level τ/ε rows tagged `measured` when `powercap_sweep.json` exists for that GPU model, else `placeholder`.
5. `gpus.json`: every model has `p_max_w > 0` and `0 < p_idle_w < p_max_w`.
6. `cities.json`: exactly 6 cities, each with a `stress_category` from the 5 Aqueduct levels and `lookup_date`.
7. D19: `cli/thirst/data/gpus.json` is byte-identical to `src/engine/data/gpus.json`.

**Implement**

- **2.2.a** Write `factors.json` with **every** constant from TRD §5 and Idea §8. Initial content (status in brackets):
  - Cooling: `cop_rated_room_ac` 3.0 [placeholder], `cop_rated_air_chiller` 4.5 [placeholder], `cop_temp_slope` 0.025 [placeholder], `cop_ref_temp_c` 35 [placeholder], `cop_min` 1.5, `cop_max` 6 [design_choice], `pue_misc` 0.05 [placeholder], `pue_evaporative_default` 1.4 [placeholder], `wue_a` 0.2, `wue_b` 0.1 [placeholder, ±40% range], `wue_max` 4 [design_choice].
  - IT overhead: `it_overhead` 1.2 [placeholder].
  - Grid carbon: `ef_gas` 0.49 [sourced, verify, ±15%], `ef_coal` *calibrated at load time* [calibrated], `ef_nuclear/hydro/solar/wind` 0 [sourced: CEA method], `ef_other` 0 [design_choice, note], `cea_grid_ef_2023_24` 0.727 [sourced].
  - Grid water: `wf_coal` 3.25 (3.0 / 3.5) [sourced MoEFCC], `wf_gas` 0.75 (0.5 / 1.0) [verify], `wf_nuclear` 2.5 (1.75 / 3.25) [verify], `wf_hydro` 0 [design_choice, toggle], `wf_solar` 0, `wf_wind` 0, `wf_other` 0 [design_choice].
  - Grid: `solar_share_cap` 0.6 [design_choice], `grid_loss_factor` 1.0 [design_choice, v0.4].
  - Stress weights: `stress_low` 1.0, `stress_low_medium` 1.25, `stress_medium_high` 1.5, `stress_high` 2.0, `stress_extremely_high` 2.5 [design_choice, SPEC.md].
  - GPU: `u_default` 0.9 [placeholder], `p_idle_frac_default` 0.1 [placeholder], `tau_85` 0.97, `eps_85` 0.88, `tau_70` 0.90, `eps_70` 0.80 [placeholder → measured sweep].
  - Score: `j_w_water` 0.45, `j_w_carbon` 0.35, `j_w_energy` 0.20, `no_room_threshold` 0.03, `flex_share_gold` 0.30, badge thresholds 90/75/60/45, division bounds 16/256/4096 [design_choice, SPEC.md].
  - Planner: `plan_w_energy` 0.2, `plan_w_split` 0.8, `max_pause_gaps` 3, `pareto_alphas` [0, 0.1, …, 1] [design_choice].
  - People: `person_day_l` 135 [sourced CPHEEO].
  - Plausibility: `receipt_kwh_tolerance` 1.1, `signature_max_skew_s` 600 [design_choice].
- **2.2.b** Write `gpus.json` with: RTX 4090 (450 W), RTX 4080 (320 W), RTX 3090 (350 W), RTX 3060 (170 W), RTX A6000 (300 W), L4 (72 W), L40S (350 W), T4 (70 W), A100-PCIe-40GB (250 W), A100-PCIe-80GB (300 W), A100-SXM (400 W), H100-PCIe (350 W), H100-SXM (700 W). `p_idle_w = 0.1 × p_max_w` [placeholder]; `source` = NVIDIA product page, `status: sourced (verify)`. Add `nvml_name_patterns` per model (for example `"NVIDIA GeForce RTX 4090"`) so the CLI can map the detected GPU to a model.
- **2.2.c** `FactorSet` is a frozen mapping `id → float` for one of `low/central/high`. `Factors.range_sets()` returns the low and high sets built per TRD 5.8 step 5: WUE ±40%, coal WF 3.0 vs 3.5, other WF low/high, EF ±15%, COP ±15%. **Low set = lower footprint, high set = higher footprint.** COP goes the **other** way: a high COP lowers the footprint, so the low set uses COP × 1.15 and the high set uses COP × 0.85.
- **2.2.d** `load_sweep()`: if `powercap_sweep.json` has an entry for the GPU model, override `tau_*`, `eps_*`, `u` and `p_idle` for that model only, and mark them `measured`.
- **2.2.e** `table()` returns rows `{id, label, value, low, high, unit, status, source, source_url, notes}` sorted by group. `/assumptions` and `ASSUMPTIONS.md` are both generated from this (07.5.b), so they can never drift.
- **2.2.f** Load once and cache with `functools.lru_cache` (Lambda warm starts reuse it).

**Done when:** tests pass, and `python -c "from engine.factors import load_factors; print(len(load_factors().table()))"` prints the factor count.

---

## 2.3 `wetbulb.py` (15 min, P0)

**Tests first**

1. `stull_tw(20, 50) == 13.7 ± 0.1` (TRD §14).
2. A table of extra points computed from the Stull formula (checked while writing this plan), each within ±0.1 °C: 30 °C/60% → 24.0, 35 °C/40% → 24.5, 25 °C/90% → 23.7, 40 °C/20% → 22.7, 10 °C/80% → 7.9.
3. Monotone: Tw rises with T at fixed RH and with RH at fixed T, over the valid range (hypothesis property).
4. `Tw ≤ T` always in the valid range.
5. `in_valid_range` is False for RH < 5 or > 99, or T < −20 or > 50; `stull_tw` still returns a value but the caller tags it `out_of_range`.

**Implement**

- **2.3.a** Write the Stull (2011) formula exactly as in TRD 5.2, using `math.atan`, `math.sqrt` and `** 1.5`.
- **2.3.b** Clamp RH to [5, 99] **for the formula only** and return `(tw, in_range_flag)` through a second function `stull_tw_checked`.

---

## 2.4 `cooling.py` (30 min, P0)

**Tests first**

1. COP clip: for T in [0, 50] in 0.5 steps, `1.5 ≤ cop ≤ 6` (TRD §14).
2. `cop(35, 3.0) == 3.0`; `cop(45, 3.0) == 3.0 × 0.75 == 2.25`.
3. `pue(room_ac, 35) == 1 + 1/3 + 0.05 ≈ 1.3833`.
4. `pue(evaporative, any T, pue_user=1.25) == 1.25`; with no user value it's the default 1.4.
5. `wue(room_ac) == wue(air_chiller) == 0` for any Tw.
6. `wue(evaporative, tw=25) == clip(0.2 + 0.1×25, 0, 4) == 2.7`; `wue(evaporative, tw=50) == 4` (clipped).
7. Range sets: `pue_high ≥ pue_central ≥ pue_low` for the AC types (COP direction, 2.2.c).

**Implement**

- **2.4.a** `class Cooling(StrEnum): ROOM_AC="room_ac"; AIR_CHILLER="air_chiller"; EVAPORATIVE="evaporative"`.
- **2.4.b** `cop(t_c, rated, fs) = clip(rated × (1 − slope × (t_c − ref)), cop_min, cop_max)`.
- **2.4.c** `pue(...)`: AC types use `1 + 1/cop + pue_misc`; evaporative uses `pue_user or pue_evaporative_default`. Validate `1.0 ≤ pue_user ≤ 3.0`.
- **2.4.d** `wue(...)`: 0 for AC types; evaporative uses `clip(a + b × tw, 0, wue_max)`.

---

## 2.5 `grid.py` + `data/grid_shares.json` (45 min, P0)

The input file depends on the Option A/B decision from 1.7.c (deadline Fri 12:00). The code supports **both** through the `kind` field in `grid_shares.json` (08 §2.4).
**Don't wait for C:** tests use synthetic `tests/fixtures/grid_shares_a.json` and `grid_shares_b.json` (illustrative shares), and C's real file drops in later without code changes.

**Tests first**

1. Shares sum to `1 ± 1e-6` in every hour, for 48 random radiation profiles (TRD §14), including zero radiation at night and heavy cloud at noon.
2. `calibrate_coal_ef(annual_shares, ef_gas=0.49, target=0.727)` gives `EF_coal` such that `Σ share_k × EF_k == 0.727 ± 0.005` (TRD §14), and the result is between 0.85 and 1.10 (sanity band around the expected 0.95–1.0).
3. Solar cap: `s_solar(h) ≤ 0.6` always.
4. Coal never goes negative. If the solar surplus is larger than coal, `coal = 0`, the rest is taken from `gas` and then `other`, and the shares are **renormalised** to sum to 1.
5. Clear midday gives a lower CI than midnight for the same day (sign check on the model).
6. `ewif` with all-solar shares == 0; with all-coal shares == `wf_coal`.

**Implement**

- **2.5.a** `grid_shares.json`:
  - `kind: "hod_profile"` (Option A): `profiles[hod][source]` for 24 hours, plus `mean_radiation_profile[hod]`, plus `annual_shares` for calibration, plus `source`, `period`, `exported_at`.
  - `kind: "annual"` (Option B): `annual_shares[source]`, `s_avg_solar`, plus metadata.
- **2.5.b** `hourly_shares(slots, rad, ...)`:
  - Option A: `s_solar = min(cap, share_solar(hod) × rad(h) / mean_rad(hod))`. When `mean_rad(hod) == 0` (night), keep `s_solar = share_solar(hod)`, which is about 0.
  - Option B: `s_solar = min(cap, s_avg × rad(h) / mean_24h(rad))`. When `mean_24h(rad) == 0` (fully overcast), `s_solar = 0`.
  - `coal = max(0, coal_base − (s_solar − solar_base))`, then the overflow rule (test 4), then renormalise.
- **2.5.c** `calibrate_coal_ef` follows TRD 5.4 exactly. Call it once in `load_factors()` and store `ef_coal` with status `calibrated`. Low/high sets apply EF ±15% **after** calibration.
- **2.5.d** `ci(shares, fs) = Σ share_k × ef_k`; `ewif(shares, fs) = Σ share_k × wf_k × grid_loss_factor` (1.0 in v0).
- **2.5.e** Docstring on `ci`: "Average, not marginal, intensity (Idea §6.5)". The UI repeats this.

---

## 2.6 `forecast.py` + `footprint.py` (45 min, P0)

**Tests first**

1. `build_snapshot` for 48 rows gives arrays of length 48: `temp, rh, rad, tw, pue, wue, ci, ewif`, plus `submit_ts`, `slot0_capacity`, `factor_version`, `source ∈ {live, cached}`.
2. Missing weather rows (fewer than 48 future hours) are filled from `sample_forecast.json` by hour-of-day, and the snapshot is marked `source="cached"` (TRD §9).
3. Footprint with `g = [1.0]` kWh, room AC at 35 °C, CI 0.7, EWIF 2.5, σ = 2.5:
   `E_IT = 1.2`, `E_fac = 1.2 × 1.3833 = 1.66`, `D = 0`, `I = 1.66 × 2.5 = 4.15`, `W = 4.15 × 2.5 = 10.375`, `C = 1.66 × 0.7 = 1.162`.
4. **Linearity:** `footprint(k × g) == k × footprint(g)` (the score's Best scaling depends on this, TRD 5.9).
5. `person_days = (D + I) / 135`, computed from **unweighted** litres.
6. Totals equal the sum of the slot values.

**Implement**

- **2.6.a** `ForecastSnapshot` is frozen and stores **both** the raw weather and the derived arrays (central set), plus `factor_version` (a hash of `factors.json`). The low/high arrays are recomputed from the raw weather when needed, so no extra storage is used.
- **2.6.b** `to_json()` / `from_json()`. The JSON must be < 30 KB before gzip (08 §5 explains why).
- **2.6.c** `footprint()` follows TRD 5.7 line by line. `sigma_grid = sigma_site` in v0, labelled (TRD 5.5).

---

## 2.7 `planner.py` (2 h, P0, critical path)

### Tests first (`tests/engine/test_planner.py`)

1. **Flat intensities:** with constant weather and grid, the Best schedule == the Base schedule (100%, start at slot 0), and `1 − J_best < 0.03` gives `no_room` (TRD §14). *Note:* the power cap still saves energy even with flat intensities, so this test uses a sweep where `ε_85 = ε_70 = 1`.
2. **Deadline property** (hypothesis, 500 examples, TRD §14): random `work_hours ∈ [0.5, 20]`, deadline offset ∈ [work_hours, 48] h, `pausable` random, random weather. Check: (a) no running or idle slot ends after the deadline; (b) `Σ τ_l × capacity ≥ work_hours − 1e-9`; (c) at most 3 pause gaps.
3. **Idle cost:** a pausable plan with a 10-hour gap costs more than the same run slots without the gap (TRD §14).
4. **Infeasible:** `work_hours = 6`, deadline in 5 h → `EngineError("deadline_too_soon")` whose message includes the earliest finish time at 100%.
5. **Slot-0 capacity:** submit at 21:40 → slot 0 contributes `20/60 × τ` of work (D7).
6. **Non-pausable exactness:** brute force over every start and level on a small instance equals `plan_non_pausable`.
7. **Pausable never worse:** the pausable result's cost ≤ the best non-pausable result's cost (TRD 5.8 step 3b.5).
8. **Pareto:** 11 entries for alpha 0..1. They aren't necessarily unique; `points` is deduplicated. On **fixed test data only**, W is non-increasing and C non-decreasing as alpha rises, within ±1%. (Strict optimality isn't guaranteed: energy still weighs 0.2 and the pausable planner is greedy.)
9. **Ranges:** for each saving, `min ≤ central ≤ max` across the low/central/high sets. The low/high sets keep the **same schedule** (TRD 5.8 step 5) and only change the factors.
10. **Performance:** `plan()` for 4 × RTX 4090, 8 h, 48 h window, pausable: the **median of 20 runs is < 200 ms on the CI runner** (marked `slow`, run in CI).
11. **Distributed or Windows forced flag:** `pausable_requested=True, pausable_allowed=False` gives a non-pausable plan, with `notes` containing `pause_unsupported`.

### Implement

- **2.7.a `PlanRequest`** (frozen): `city, cooling, pue_user, gpu_model, gpu_count, work_hours, deadline, pausable, alpha, submit_ts, site_id?`. Validation lives in handlers; the engine re-checks invariants and raises `EngineError`.
- **2.7.b Energy per slot:** `gpu_kwh(level, cap) = N × u × P_max × ε_l × τ_l × cap / 1000` (TRD 5.6), where `cap` is the slot capacity (D7). Idle: `N × P_idle × cap / 1000`.
- **2.7.c Base plan** (TRD 5.8 step 1): start at slot 0 (capacity `f0`), level 100%, keep going until `Σ capacity × τ_100 ≥ work_hours`; the last slot is partial. Compute `W_base, C_base, E_base` with the central set.
- **2.7.d `slot_cost(h, l)`** = `[wW·W(h,l)/W_base + wC·C(h,l)/C_base + wE·E_fac(h,l)/E_base] / τ_l`, with `wW = 0.8α`, `wC = 0.8(1−α)`, `wE = 0.2`. Precompute a 48 × 3 matrix per alpha.
- **2.7.e `plan_non_pausable`** (TRD 5.8 step 3a): for each start `s ∈ [0, H_d)` and level `l`, compute the needed slots `n = work_hours / τ_l`. It is valid if the slots fit before `H_d` (slot 0 uses capacity `f0`). The cost is the sum of slot costs, with the last slot partial. Ties go to the earlier start, then the higher level (finishes sooner).
- **2.7.f `plan_pausable`** (TRD 5.8 step 3b, with D8):
  1. `l*(h) = argmin_l cost(h,l)` for each `h < H_d`.
  2. Sort slots by `cost(h, l*(h))` and take the cheapest until the work is covered; the last one is partial. **Order the chosen slots in time.**
  3. Idle slots = unselected slots between the first and last selected slot. Add their idle energy through the footprint.
  4. While gaps > `max_pause_gaps`: fill the **shortest** gap with running slots at `l*`, then drop the most expensive selected slots **while the remaining work ≥ work_hours** (D8), then re-trim the partial last slot. **Only drop slots at the first or last edge of a run block, never one that would split a block** (dropping a middle slot creates a new gap, and the loop might never end). Ties: drop the later slot. Stop after at most 48 iterations. If there are still > 3 gaps, fall back to the best non-pausable plan and add the note `gap_limit_fallback`.
  5. Compare the total cost, **including idle**, with `plan_non_pausable` and return the cheaper one. Record which one won in `notes`.
- **2.7.g Schedule output:** `[{slot_start, level, state: run|pause, fraction}]`, covering every slot from the first run slot to the last. `finish = start of last run slot + fraction × 1 h`. `start = first run slot` (slot 0 means "now").
- **2.7.h Pareto** (TRD 5.8 step 4, D11): run 2.7.d to 2.7.f for each alpha. Each entry is `{alpha, schedule, start, finish, level_summary, totals:{W,C,E,D,I}, savings_ranges, series_overlay}`. `chosen` is `pareto[int(round(alpha * 10 + 1e-9))]`. The API only accepts alpha on the 0.1 grid, and the client indexes with `Math.round(alpha * 10)`. Both give the same index, avoiding Python's banker's rounding and `0.35*10 = 3.4999…`.
- **2.7.i Ranges** (TRD 5.8 step 5): for Base and each Pareto plan, recompute totals with the low and high sets (same schedule). Report each saving as `[min%, max%]` over the 3 sets, and absolute values as `[lo, hi]`. `person_days_range` comes from the saved unweighted litres.
- **2.7.j `plan()` output** follows 08 §3.1 exactly: `plan_id` (left empty; the handler fills it), `submit_ts`, `base`, `chosen`, `pareto[]`, `savings_ranges`, `series[]` (48 rows: `{slot, direct_l_per_kwh, grid_l_per_kwh, co2_kg_per_kwh, level, state}`), `person_days_range`, `tags`, `notes`, `forecast_snapshot`.
  `tags`: `energy: modelled`, `water: modelled`, `co2: modelled`, `tau: measured|placeholder` (from the sweep), `forecast: live|cached`.
- **2.7.k Fixture generator** (`scripts/gen_fixtures.py`, `make fixtures`): runs `plan()` on the PRD §6.1 default example (Chennai, room AC, 2 × RTX 4090, 6 h, deadline tomorrow 09:00, pausable) using `sample_forecast.json`, and **overwrites** the hand-written stub `tests/fixtures/plan_response.json` (05.1.c′). Deliver by M1b (Fri 15:30). C has been building against the stub since 10:45.
- **2.7.l Template explanation** (TRD §10): `explain_template(plan) -> str`. Put it in the engine so both the CLI and `/explain` use it. Test: it mentions "modelled" and never states a single saving number without a range.

**Done when:** all tests pass, the property test runs 500 examples, coverage ≥ 90%, and the fixture is committed.

---

## 2.8 `score.py` (2 h, P0)

### Tests first (`tests/engine/test_score.py`)

1. `J(base) == 1` by construction.
2. **Capture bounds:** for random inputs, `0 ≤ capture ≤ 1` (TRD §14), including Actual being worse than Base (capture clipped to 0) and better than Best (clipped to 1).
3. **Base energy (TRD §14):** with every slot at 100%, `E_base_GPU == Σ g_run`.
4. **Fairness:** the same receipt scored with two different *observed* weather sets gives the **same** Capture, and different absolute litres (Idea §7.2).
5. **No room:** `1 − J_best < 0.03` gives `capture = None`, `flexible = False`.
6. **Splitting invariance:** one job split into two receipts with proportional energy gives the same energy-weighted A (Idea §7.4).
7. **Site score:** A = 50 × energy-weighted capture over flexible jobs; C = 10 × measured share + 5 × coverage ≥ 80% + 5 × public; provisional = (A + C) / 70 × 100.
8. **No flexible jobs:** the score is `None` with the reason `needs_flexible_receipt` (D10); part C is still returned.
9. **Badges:** 90 → Platinum only if flex share ≥ 0.30, otherwise capped at Silver (Gold and Platinum both need flex ≥ 30%); 74.99 → Silver; 44.99 → none.
10. **Divisions:** 16 → D1, 17 → D2, 256 → D2, 257 → D3, 4096 → D3, 4097 → D4.
11. **Modelled receipts** (`method = modelled`) count in A but give 0 measured kWh in C (TRD 6.5). *(P1, only with 04.11 `--offline`)* **Unverified** receipts (D20) are excluded from everything.
12. **30-day window:** a receipt with `end_ts` 31 days ago is excluded.

### Implement

- **2.8.a** `j_value(W, C, E, W_b, C_b, E_b)` uses the weights from factors.
- **2.8.b** `receipt_footprints(receipt, plan_record, observed_rows)` (TRD 5.9):
  - Group `receipt.slots` by hour into `g_run(h)`, `g_idle(h)` and `level(h)`.
  - **Actual (scoring):** run + idle energy through `footprint()` with the **snapshot** factors.
  - **Base (scoring):** `E_base_GPU = Σ g_run(h) / ε_level(h)`, spread evenly from slot 0 (capacity `f0`) over `Σ τ_level(h) × fraction(h)` hours at 100%.
  - **Best (scoring):** the saved Best plan's per-slot GPU energy, scaled by `E_base_GPU / E_base_GPU_model` (linearity, 2.6 test 4).
  - **Hours outside the snapshot:** the snapshot covers 48 slots from `floor_hour(submit_ts)`. A receipt hour **after** slot 47 (an overran job) is scored with the last snapshot hour's intensities and tagged `extrapolated`. A receipt with `start_ts < floor_hour(submit_ts)` is rejected upstream (05.7, 422 `slot_out_of_range`). Test both.
  - **Absolute numbers:** the same three, but using observed weather rows where present. Any hour without an observation falls back to the snapshot and is counted in `absolute_basis = {"observed": n, "forecast": m}`.
  - Return `{scoring:{base,best,actual,J_*}, absolute:{base,best,actual}, capture, flexible, tags}`.
- **2.8.c** `capture()` follows TRD 5.9, plus the no-room rule.
- **2.8.d** `site_score(receipts_30d, site)` returns `{A, B: "not_rated", C, C_parts, score, provisional: True, badge, flex_share, reason?, monthly_absolute:{kwh, litres, stress_litres, kg_co2, person_days}}`.
- **2.8.e** `badge(score, flex_share)` and `division(gpu_count)` read their thresholds from factors.
- **2.8.f** `site_page_view(site, receipts)` returns the data shape for `GET /sites/{id}` (08 §3.3): last 10 receipts, newest first.
- **2.8.g** `leaderboard_rows(sites, receipts_by_site, division)`: one row per site in the division, sorted by score descending, then flex share descending, then site_id. Unrated sites go last with `rank = None`. Each row includes `simulated`, `division`, the monthly absolute footprint, and **no exact GPU count** (TRD 5.9 privacy).

**Done when:** tests pass, coverage ≥ 90%, and `make fixtures` also writes `tests/fixtures/receipt_response.json` and `tests/fixtures/leaderboard_response.json` (for C).

---

## 2.9 Engine review and freeze (30 min, P0)

- **2.9.a** Run `ecc:python-reviewer` and `ecc:code-reviewer` on `src/engine`. Fix CRITICAL and HIGH findings.
- **2.9.b** Freeze the public API listed in 2.0. Any later change needs a note in the PR and a ping to A and C.
- **2.9.c** Tag the commit `engine-m1`.
- **2.9.d** Update `AGENTS.md`: File Map entries for every module, plus Gotchas (calibration, slot-0 capacity, COP direction in range sets).
