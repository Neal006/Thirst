# Thirst: Product Requirements Document (PRD)

Version 0.3 · 9 Oct 2026 · Track 02: Heat and Water · Read `Idea.md` first for the why.
Owner: team hello_world · Status: **approved for build** · Code freeze: Sun 11 Oct, 11:00 IST

New words are explained in the Glossary in `Idea.md` (section 14).

---

## 1. Summary

Thirst is a free tool for people who run GPU jobs in India. It answers one question before the job starts, "when and how fast should I run this?", and one question after it ends, "what did it really cost in water and CO₂?". Receipts add up to a fair public score per site.

The weekend goal is **one working loop, shown end to end on video**: plan on the web, run with the CLI on a real GPU, get a measured receipt, see the site move on the board. Everything else is optional.

---

## 2. Goals and non-goals

### 2.1 Goals (this weekend)

| # | Goal | How we know it is met |
|---|---|---|
| G1 | A user gets a clear plan (start time, pauses, power cap) in plain words | Plan page returns a result card in under 3 seconds |
| G2 | The plan shows the water vs carbon trade-off visually | Moving the slider changes the chosen plan and the chart within 1 second |
| G3 | A real GPU job runs with the plan and produces a measured receipt | One recorded overnight job with NVML energy, posted to the API |
| G4 | Receipts turn into a fair score | Site page shows Capture, score parts A and C, Provisional tag |
| G5 | Every number is honest | Every number has a "measured" or "modelled" tag and links to the Assumptions page |
| G6 | AWS is visible | Live URL on Amplify, API on Lambda, shown in the video |

### 2.2 Non-goals (this weekend)

- Ranking any real company that did not opt in.
- Login accounts (a site token is enough).
- Slurm or Kubernetes plugins.
- Heat recovery or any hardware product.
- GPU instances on AWS.
- Exact litre savings (ranges only).

---

## 3. Users

### 3.1 Primary users (they use the product)

| Persona | Situation | What they need | What they fear |
|---|---|---|---|
| **Arjun, M.Tech student**, CSE GPU lab in Chennai | 4 × RTX 4090, room AC, runs LoRA fine-tunes of 4 to 8 hours, deadline is usually "next morning" | One command that just works; a clear reason to change the start time | Losing time; a tool that breaks his training script |
| **Dr. Meera, lab head** | Owns the lab's power bill and reports to the department | Monthly totals, a badge, simple numbers for reports | Extra work for students; numbers she cannot defend |
| **Kabir, ML engineer at a startup** | Rents GPUs in a colocation site in Hyderabad with a cooling tower | Per-job receipts and a Gold badge for enterprise customers | Sharing sensitive GPU counts |

### 3.2 Later users

- Data centre and colocation operators (direct water planning with wet-bulb, receipts for their customers).
- Sustainability teams at listed companies (BRSR Core water and energy intensity).

### 3.3 People who benefit but do not use the app

Residents of water-stressed basins (Chennai, Bengaluru, Hyderabad, Mumbai). The product shows impact in **person-days of city water** (135 L per person per day, CPHEEO norm) so their stake is visible.

---

## 4. User stories and acceptance criteria

Format: As a [user], I want [thing], so that [reason]. Then the test that proves it works.

| ID | Story | Acceptance criteria | Priority |
|---|---|---|---|
| US1 | As Arjun, I want to type my job details and get the best start time and power cap, so that I know what to do without reading research papers | Given GPU type, count, work hours, deadline, pausable, city and cooling, when I press "Plan", then I see start time, pauses, power cap, finish time and savings as a range, in under 3 seconds | P0 |
| US2 | As Arjun, I want to move a slider between "save water" and "save carbon", so that I can see the trade-off | When I move the slider, the chosen plan, the shaded hours on the chart and the result card update within 1 second | P0 |
| US3 | As Arjun, I want to run my training with one command that follows the plan, so that I don't have to stay awake | `thirst run --hours 6 --deadline "..." --pausable -- python train.py` waits, sets the cap, starts, pauses and resumes as planned, restores the power limit at the end and on Ctrl-C | P0 |
| US4 | As Arjun, I want a receipt at the end, so that I know what the job cost and what I saved | The CLI prints kWh (measured), litres and kg CO₂ (modelled, as ranges), the Base comparison, Capture and the site score, and posts a signed receipt | P0 |
| US5 | As Dr. Meera, I want a site page with our score and recent receipts, so that I can show progress | Site page shows score, badge, parts A/B/C with B "Not rated", Provisional tag, last 10 receipts, absolute monthly footprint | P0 |
| US6 | As anyone, I want to see a board of sites in my size group, so that small labs get noticed | Leaderboard shows D1 sites by default with division tabs; simulated sites are tagged "Simulated"; each row shows absolute footprint | P0 |
| US7 | As a judge or skeptic, I want to see every assumption with a source, so that I can trust the numbers | Assumptions page lists every factor with value, unit, source link and status (measured, sourced, placeholder) | P0 |
| US8 | As Arjun, I want to describe my job in one English sentence, so that I don't fill a form | "LoRA on 2 × 4090, 6 hours, need it by 9 AM, can pause, Chennai lab with AC" fills the form and shows a 3-sentence explanation that names modelled numbers | P1 |
| US9 | As anyone, I want to see the India finding (which hours are best for water and for carbon), so that I understand why the plan looks like this | A chart from Step 0 with a one-line headline is on the home page | P1 |
| US10 | As Arjun, I want a shareable receipt card, so that I can post it | "Share" makes a PNG of the receipt card | P2 |
| US11 | As Kabir, I want to compare the same job in 2 to 3 cities | Spatial comparison table | P2 |
| US12 | As Dr. Meera, I want to measure the whole machine at the wall | Optional smart-plug reading in the receipt | P2 |

---

## 5. Features

### 5.1 P0 (the demo depends on these)

| ID | Feature | Details |
|---|---|---|
| F1 | **Job form** | Fields: GPU model (list with max power), GPU count, work hours (at full power), deadline (date and time), can pause (yes/no), city (6 seed cities: Chennai, Bengaluru, Hyderabad, Mumbai, Delhi, Pune), cooling (room AC, air-cooled chiller, cooling tower). Defaults filled. Plain labels |
| F2 | **48-hour chart** | Bars: direct water and grid water per kWh (stacked). Line: CO₂ per kWh. Shaded: planned hours. Step line: power cap. Hover shows numbers with tags |
| F3 | **Water vs carbon slider** | 0 = carbon only, 1 = water only, default 0.5. Re-plans on change (client calls `/plan` with debounce, or uses the Pareto points already returned) |
| F4 | **Pareto chart** | 11 dots (slider at 0, 0.1, ... 1), x = stress-weighted litres, y = kg CO₂; chosen plan highlighted |
| F5 | **Result card** | "Start at 01:00, GPU at 85%, pause 04:00 to 05:00, done by 08:10." Savings as ranges vs "start now". Also "equals about X person-days of city water". Tags: measured / modelled |
| F6 | **Assumptions page** | Table from `/assumptions`. Linked from every number |
| F7 | **CLI** | `thirst register`, `thirst plan`, `thirst run`, `thirst run --now`, `--modelled` for machines without NVIDIA GPU |
| F8 | **Receipt** | Printed in the terminal and posted to the API; web page shows Base vs Best vs Actual and Capture |
| F9 | **Score and board** | Site score (A + C, scaled, Provisional), badges, divisions, one board (Score). Simulated sites tagged |
| F10 | **Site page** | Score parts, recent receipts, absolute footprint |
| F11 | **Deployed on AWS** | Amplify (web), API Gateway + Lambda (API), DynamoDB (data), EventBridge Scheduler (hourly forecast refresh) |

### 5.2 P1 (only if all P0 work by Friday 22:00)

| ID | Feature |
|---|---|
| F12 | Strands agent: sentence to form, and a 3-sentence explanation. Template explanation is the default and stays if Bedrock is late |
| F13 | "India finding" chart from Step 0 on the home page |
| F14 | Extra boards: Most improved, Basin guardian |

### 5.3 P2 (after the hackathon)

Spatial comparison, sensitivity view (low/high factor sets as a separate chart), share card, wall-meter mode (smart plug), checkpoint-based pause, Slurm plugin, company page, BRSR export.

### 5.4 Cut order if we are late

Cut in this order: F14 → F13 → F12 → F4 (keep slider, drop Pareto dots) → extra cooling types (keep room AC and cooling tower). **Never cut:** F5 result card, F7/F8 real receipt, F3 slider, F6 assumptions.

---

## 6. User flows

### 6.1 Web flow (first visit)

1. Home page opens on the **Plan** screen with a pre-filled example (Chennai, room AC, 2 × RTX 4090, 6 h, deadline tomorrow 09:00, can pause).
2. User changes anything and presses **Plan**.
3. Chart, slider, Pareto dots and result card appear.
4. User moves the slider and watches the plan change.
5. User clicks "How do we know?" and lands on **Assumptions**.
6. User clicks **Leaderboard**, sees D1, opens a site page.

### 6.2 CLI flow (lab member)

1. `pip install thirst` (from the repo).
2. `thirst register --name "CSE GPU Lab" --city Chennai --cooling room_ac --gpus 4` prints the site id and saves the token to `~/.thirst/config.toml`.
3. `thirst run --hours 6 --deadline "2026-10-10 09:00" --pausable -- python train.py`
4. CLI prints one line: "Plan: start 01:00, cap 85%, pause 04:00 to 05:00, done by 08:10". It waits.
5. At 01:00 it sets the cap, starts the command, measures energy every second, pauses and resumes on plan.
6. At the end it restores the power limit, prints the receipt and posts it.
7. The site page and the board update within 1 minute.

---

## 7. Screens and words on screen

Write for a busy student. Short words. Units always shown. No jargon without a tooltip.

| Screen | Must show | Example words |
|---|---|---|
| Plan | Form, chart, slider, Pareto, result card | "Best time to start", "GPU power", "Done by", "Saves about 15 to 30% water (modelled)" |
| Receipt | Base vs Best vs Actual, Capture, tags | "If you had started right away", "What you did", "You took 86% of the possible saving" |
| Leaderboard | Division tabs, board switcher, rows | "Small labs (up to 16 GPUs)", "Simulated" chip, "Monthly footprint" |
| Site | Score, parts, receipts | "Provisional: building efficiency not rated yet" |
| Assumptions | Every factor | "Placeholder: to be replaced by our measured sweep" |

Must work at phone width (360 px). Judges may open the URL on a phone.

---

## 8. Success metrics

### 8.1 Hackathon (checked before submit)

| Metric | Target |
|---|---|
| Live URL loads signed-out on a phone | Yes |
| `/plan` response time (p95) | Under 2 s |
| Real overnight receipt recorded with NVML | 1 or more |
| Measured power-cap sweep (100/85/70%) | Done, τ values replace placeholders |
| Clean-machine test: fresh clone → register → plan → run → board | Passes in under 15 minutes |
| AWS spend by Saturday night | Under $5 |
| Video length | Under 3:00 |

### 8.2 Product (first 3 months after the hackathon)

| Metric | Target |
|---|---|
| Labs with at least one receipt | 10 |
| Share of GPU energy in those labs that goes through `thirst run` | 50% |
| Energy-weighted average Capture | 0.7 or more |
| Stress-weighted litres avoided (reported as a range) | Published monthly |

---

## 9. How the PRD maps to the judging criteria

| Criterion | What answers it |
|---|---|
| Idea and impact | Water-stressed Indian cities, person-days of water, real power-cap cut, rating that rewards small labs |
| Built on AWS | Amplify, API Gateway, Lambda, DynamoDB, EventBridge Scheduler, Bedrock + Strands Agents SDK, SAM CLI, shown in the video |
| Design and usability | One form, one chart, one card, one command. Plain words, phone-ready |
| Execution | One real loop on a real GPU. Engine works without AWS and without AI |
| Demo video | Slider moment, real receipt, board, AWS console, assumptions |

---

## 10. Demo video plan (under 3:00)

| Time | Show | Say |
|---|---|---|
| 0:00 to 0:20 | A water tanker queue or dry reservoir in an Indian city (credit the footage), then a GPU lab | "Every GPU hour uses water twice: at the building and at a coal plant. In Chennai, that water is scarce." |
| 0:20 to 0:40 | Step 0 chart | Our India finding in one sentence |
| 0:40 to 1:30 | Live URL in the address bar. Fill the job, press Plan, move the slider | "Not just when, but how fast. Our measured sweep: 85% power costs X% speed and saves Y% energy." |
| 1:30 to 2:00 | Terminal: the real overnight receipt | "Energy measured from the GPU. Water modelled from it, and labelled." |
| 2:00 to 2:25 | Leaderboard D1 and the site page | "We score the choice, not the climate, so a 4-GPU lab can beat a giant's lab." |
| 2:25 to 2:50 | Architecture slide, AWS console (Lambda, DynamoDB, Amplify), Strands code | Name every AWS service out loud |
| 2:50 to 3:00 | Assumptions page | "Every modelled number is labelled. The spec is open. Labs first." |

---

## 11. Open decisions

| Decision | Options | Owner | Decide by |
|---|---|---|---|
| Headline | "Solar vs cool nights" or "Midday wins" | Data/story | Fri 13:00 (from Step 0) |
| Grid data | CSEP 5-minute national mix, or radiation proxy | Engine | Fri 12:00 |
| Bedrock model and region | Whatever small model is enabled first; `ap-south-1` or cross-region | Backend | Fri 12:00 |
| Team | Context file lists 2 members; any third member must register and join **before** submission | Leader | Today |
| Deadline time | Still not posted on the schedule page | Leader | Check Sat and Sun morning |

---

## 12. Release plan

| Release | When | Content |
|---|---|---|
| v0.3 (hackathon) | Sun 11 Oct | P0 + whatever P1 is done |
| v0.4 | +2 weeks | Fit WUE curve to Li et al., CSEP or Ember-based hourly mix for each region, checkpoint pause |
| v0.5 | +6 weeks | Slurm plugin, company page, first 10 college labs onboarded |
| v1.0 | +3 months | "Thirst Verified" spot audits, BRSR export, spec v1 published for comment |
