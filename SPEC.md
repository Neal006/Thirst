# Thirst Score spec (v0.2, as implemented)

This is the scoring rulebook. It describes what `src/engine/score.py` actually does. Every constant below is a row in [`ASSUMPTIONS.md`](ASSUMPTIONS.md) with status `design_choice`, so anyone can see it and change it. The reasons behind the design are in [`Idea.md`](Idea.md) §7 and [`trd.md`](trd.md) §5.9.

## 1. Principles (copied from ENERGY STAR)

1. **Fair.** Never punish what a lab can't control, such as its city's climate or its state's coal-heavy grid.
2. **Peer groups.** Compare like with like (divisions, §5).
3. **One number and a badge.**
4. **Measured beats modelled.** Every number carries a data-quality tag, and measurement earns points (§4, part C).

## 2. Three footprints per job

For every receipt the server computes the same job's footprint three ways:

| Version | Meaning | Where it comes from |
|---|---|---|
| **Base** | Start the moment the job was submitted, at full power | The plan's submit time, recorded by the server, so it can't be faked |
| **Best** | The J-optimal plan that meets the deadline, with the same pausable setting | A separate solve, independent of the user's slider (decision D27) |
| **Actual** | What really happened | The receipt's per-hour energy |

A footprint has three parts:
- **W**: stress-weighted water in litres. Litres are multiplied by the city's water-stress weight (§7).
- **C**: CO₂ in kg.
- **E**: facility energy in kWh.

**Fairness rule.** Base, Best and Actual are all scored against the **forecast snapshot saved with the plan**, so a wrong weather forecast never lowers a score. The absolute litres and kg printed on a receipt use the observed data.

## 3. Capture: did you take the saving?

```
J = 0.45 · W/W_base + 0.35 · C/C_base + 0.20 · E/E_base          (so J_base = 1)

Capture = (1 − J_actual) / (1 − J_best),   clamped to [0, 1]
```

- **Capture** answers: of the saving that was possible, what share did you take?
  - Each lab is compared against its own Base. So a lab next to a coal plant and a lab next to a dam can both reach 1.0.
- **No room to shift.** If `1 − J_best < 0.03`, the job is marked `no_room`. It gets no Capture and is not counted as flexible. Urgent jobs are never punished.
- **Receipts too small to score.** A receipt with less than 1 Wh of run energy, or more than 72 hourly slots, is rejected. So is one that claims more energy than its GPUs can draw: count × max power × 1.1 per hour.

| Weight | Factor id | Value |
|---|---|---|
| Water (stress-weighted) | `j_w_water` | 0.45 |
| CO₂ | `j_w_carbon` | 0.35 |
| Facility energy | `j_w_energy` | 0.20 |
| No-room threshold | `no_room_threshold` | 0.03 |

## 4. Site score (0 to 100, last 30 days)

Only signed (verified) receipts from the last 30 days count. Unverified receipts are stored but never counted (D20).

| Part | Max | How it is computed |
|---|---|---|
| **A. Behaviour** | 50 | 50 × the energy-weighted average Capture over **flexible** receipts (`Σ capture·kWh / Σ kWh`) |
| **B. Facility efficiency** | 30 | PUE and WUE against similar sites. It needs metered building data, so it is **Not rated** in v0. |
| **C. Measurement and openness** | 20 | **Measured share**: 10 × the share of energy measured with NVML (`nvml_energy`, `nvml_power_integration`). **Coverage**: 5 if the lab says Thirst covers ≥ 80% of its GPU energy. **Public**: 5 if the site is public. |

While B is Not rated:
```
score = (A + C) / 70 × 100,   tagged "Provisional"
```

- With no flexible receipts there is no score. The reason shown is `needs_flexible_receipt`.
- The value shown is **floored** to one decimal, so a site never appears to reach a badge it missed.

**Worked example.** One public lab, one flexible `--modelled` receipt with Capture 1.0, and coverage not declared:
- A = 50
- C = 0 (measured) + 0 (coverage) + 5 (public) = 5
- score = 55 / 70 × 100 = **78.57 → Gold (Provisional)**

## 5. Badges and divisions

| Badge | Threshold | Extra rule |
|---|---|---|
| 💎 Platinum | 90+ | ≥ 30% of energy from flexible jobs (`flex_share_gold`) |
| 🥇 Gold | 75+ | ≥ 30% of energy from flexible jobs |
| 🥈 Silver | 60+ | — |
| 🥉 Bronze | 45+ | — |

| Division | GPUs in the site | Factor |
|---|---|---|
| D1 Lab | ≤ 16 | `div_d1_max` |
| D2 Cluster | 17–256 | `div_d2_max` |
| D3 Facility | 257–4,096 | `div_d3_max` |
| D4 Hyperscale | > 4,096 | — |

Thirst ranks **sites**, not companies, so a big company's 8-GPU lab competes in D1. Every leaderboard row also shows the site's **absolute** monthly footprint, so a large user can't hide behind a good score. The board shows at most 100 rows and omits private sites (D26).

## 6. Anti-cheating

| Trick | Why it fails |
|---|---|
| Pretend the job would have run at the worst hour | Base uses the server's own submit time |
| Declare a fake, very long deadline | Capture is a ratio: a bigger possible saving is also harder to take |
| Mark every job "not flexible" | Gold and Platinum need ≥ 30% flexible energy |
| Send only the good jobs | The coverage declaration is public, and measured share is scored |
| Split one job into many | Capture is energy-weighted, so splitting changes nothing |
| Send fake energy | Receipts are HMAC-signed per site. Energy above the GPUs' limit is rejected. Receipts more than 10 min in the future or older than 30 days are refused. |
| Replay a receipt | The job id is a duplicate guard: a second post returns "already recorded" |

## 7. Water-stress weights

A litre taken where water is scarce hurts more people. Litres are multiplied by a weight from the city's WRI Aqueduct baseline water-stress category:

| Category | Weight |
|---|---|
| Low | 1.0 |
| Low–medium | 1.25 |
| Medium–high | 1.5 |
| High | 2.0 |
| Extremely high | 2.5 |

These weights are a **design choice**, not a published standard.

## 8. Changing a constant

1. Edit the row in `src/engine/data/factors.json`. Keep its `status`, `source` and `notes` honest.
2. Run `make fixtures` and `make assumptions` (or `python scripts/gen_fixtures.py` and `python scripts/gen_assumptions.py`). Commit the regenerated files: CI fails if they are stale.
3. Merge to `main`. The API redeploys automatically and the website's Assumptions page shows the new value.

Receipts store the `factor_version` they were scored with, and a later change marks them `factor_version_mismatch` instead of silently rescoring.
