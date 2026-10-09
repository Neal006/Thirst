# Phase 03 — Step 0: does the water vs carbon trade-off exist in India?

Owner: **C** (data/story) · Window: **Fri 09:30 to 13:00** · Hard deadline: **headline decided by 13:00** (PRD §11)
Source: TRD §13, Idea §6.6. Output feeds F13 (home-page chart, P1), the video (0:20 to 0:40) and the blog.

[← Index](README.md)

---

## 3.0 Why this runs first

The headline of the whole pitch depends on this result. It is one of two:

| Result | Headline |
|---|---|
| Median gap ≥ 4 h **or** Spearman ρ < 0.3 | "Solar hours vs cool nights: here is the best balance" |
| Otherwise | "Midday wins in India, and here is by how much" (novelty then rests on the power cap, stress weighting, receipts and rating) |

Both are real findings. The only bad outcome is having no answer by 13:00.

---

## 3.1 Notebook setup (15 min)

- **3.1.a** Create `notebooks/india_tradeoff_check.ipynb`. The first cell adds `../src` to `sys.path` and imports `engine.wetbulb`, `engine.cooling`, `engine.grid`, `engine.footprint`, `engine.factors`.
  **The notebook must use the engine's functions, not copies.** The finding must match what the product computes.
- **3.1.b** Notebook-only dependencies: `pandas`, `matplotlib`, `scipy` (for Spearman), `requests`. Put them in `notebooks/requirements.txt`, not in the engine.
- **3.1.c** Until 02.4 and 02.5 merge (about 11:00), use the TRD formulas in a clearly marked temporary cell `# TEMP until engine merges`. The 13:00 headline (gate M1a) **may** come from the TEMP cell, because grid.py realistically lands at about 12:30. Delete the TEMP cell and re-run once the engine merges (3.7.e).

---

## 3.2 Weather data (20 min)

- **3.2.a** Open-Meteo archive, last 14 available days, hourly `temperature_2m, relative_humidity_2m, shortwave_radiation`, `timezone=Asia/Kolkata`, for **Chennai, Bengaluru, Delhi** (TRD §13.1).
- **3.2.b** Cache the raw responses to `data/raw/archive_<city>_<start>_<end>.json` so re-runs are offline and repeatable.
- **3.2.c** Sanity checks printed in the notebook: 336 rows per city, no missing values (or the count of missing values, filled forward at most 2 h), temperature 10 to 45 °C, RH 5 to 100%, radiation ≥ 0 and 0 at night.

---

## 3.3 Grid data (30 min, decision at 12:00)

- **3.3.a Option A** (if 1.7.c succeeded): CSEP national 5-minute generation by source → resample to hourly → average by hour of day over 14 days → `share_k(hod)`, normalised to 1. Also compute `mean_radiation_profile(hod)` from the national-average radiation proxy. Use the mean of the three cities' radiation, labelled as a proxy.
- **3.3.b Option B** (fallback): Ember annual shares, with solar scaled by the radiation shape (TRD 5.4 Option B).
- **3.3.c** Write the result to `src/engine/data/grid_shares.json` in the 08 §2.4 schema, including `source`, `period` and `exported_at`. **This file is shared with B (engine) and A (Lambda)**, so commit it in its own PR so everyone gets it fast.
- **3.3.d** Calibration check: compute the annual-share CI with the calibrated coal factor and print `0.727 ± 0.005`.
- **3.3.e** Post the decision in the team chat with one line: "Grid model = Option A/B because …". Record it in `AGENTS.md` Decisions.

---

## 3.4 Compute W(h) and C(h) for 1 kWh of IT load (30 min)

For every hour of the 14 days × 3 cities × 2 cooling types (`evaporative`, `room_ac`):

- **3.4.a** `tw = stull_tw(T, RH)`, then `pue(cooling, T)` and `wue(cooling, tw)`.
- **3.4.b** `shares(h)` from the grid model with that hour's radiation, then `CI(h)` and `EWIF(h)`.
- **3.4.c** `footprint(g=[1/1.2])` gives E_IT = 1 kWh, then `W(h)` (stress-weighted, using the city's σ) and `C(h)`.
- **3.4.d** Put everything into one tidy DataFrame: `city, cooling, ts, hod, T, RH, rad, tw, pue, wue, ci, ewif, D, I, W, C`. Save it to `data/notebook/step0_hourly.parquet` (or CSV).

---

## 3.5 Metrics per day (20 min)

For each `(city, cooling, day)`:

- **3.5.a** `hod_min_W`, `hod_min_C`, and `gap_h = circular distance between them` (0 to 12 h, because hour 23 and hour 1 are 2 h apart).
- **3.5.b** Spearman ρ between W(h) and C(h) over the 24 hours.
- **3.5.c** `% saving` of the best hour vs the 24-h mean, for W and for C (this gives the "by how much" in the "Midday wins" headline).
- **3.5.d** Summary table: median gap, median ρ, and median savings per (city, cooling). Apply the decision rule from 3.0 **per cooling type**. `room_ac` is the main persona (Arjun), so its result decides the headline. `evaporative` goes in the blog as a second finding.

---

## 3.6 The chart (30 min)

- **3.6.a** One figure, 2 panels (room AC on the left, cooling tower on the right). The x-axis is hour of day (0 to 23). Plot the median W(h) normalised to its daily mean (blue) and the median C(h) normalised (dark grey), with an inter-quartile band, one line style per city.
- **3.6.b** Mark the minimum-W and minimum-C hours with dots. The title is the headline itself, not a description.
- **3.6.c** Footer: "Average grid mix, not marginal. Water modelled from energy. Sources: Open-Meteo, CSEP/Ember, CEA, MoEFCC, WRI Aqueduct."
- **3.6.d** Export `docs/india_finding.png` at 1600 × 900 (video) and `web/public/india_finding.png` at 1200 px wide (home page, F13), plus `docs/india_finding.svg`.
- **3.6.e** Check colour-blind safety (blue against dark grey, not red against green) and that the text is readable at phone width.

---

## 3.7 Decide, record, hand off (15 min, by 13:00)

- **3.7.a** Post the headline in the chat, with the median gap, ρ and saving numbers.
- **3.7.b** Add a "Step 0 finding" section to `README.md` (3 lines plus the PNG).
- **3.7.c** `AGENTS.md` Decisions: `2026-10-09 — Headline: "<text>" — median gap X h, ρ = Y (room AC, 3 cities, 14 days)`.
- **3.7.d** Run the notebook top to bottom with **Restart & Run All** and commit the outputs. Judges may open it.

- **3.7.e** **By Sat 12:00**: re-run the notebook with engine code only (no TEMP cell). If the headline flips, update the README, the chart and the video script, and post it in the chat.

**Done when:** the PNG is committed, the headline is posted and recorded, and the notebook runs clean from the cached raw data in under 2 minutes.

---

## 3.8 Factors and sources ownership (C, continuous, P0)

C also owns data quality for the whole product:

- **3.8.a** `cities.json` (from 1.7.e): coordinates, Aqueduct category, weight, lookup date, URL.
- **3.8.b** Review every `factors.json` entry's `source_url` and `status`. Anything still marked **verify** in the TRD (gas EF, gas/nuclear WF) is either checked against Macknick et al. 2012 and IPCC, or left `placeholder` with a note. Never upgrade a status without a source.
- **3.8.c** Keep `ASSUMPTIONS.md` generated (07.5.b), never hand-edited.
