# Phase 09: UX overhaul after the user test

Goal: make Thirst feel like one finished product. Every page answers one question, points to the next step and uses plain words.

Branch: `feat/web-ui-accessibility`. Palette: Monsoon. Layout ideas kept: Timetable, Hourly forecast, City board, Calendar. Skipped: Data journal and the large console, because they repeat what other pages already show. From "Three questions" we kept the plain-language cooling help and the shorter form.

[← Index](README.md) · PR description: [`docs/pr/ux-overhaul.md`](../pr/ux-overhaul.md) · Hand test: [`docs/pr/manual-test-checklist.md`](../pr/manual-test-checklist.md)

---

## 9.1 User test problems and the fix for each

| # | Problem found in the test | Fix | Where |
|---|---|---|---|
| 1 | Home sections stay blank until you scroll past them | Sections are visible by default. The scroll animation only lifts them a few pixels | `landing.css` |
| 2 | Home says the best start is 11:00 but the sample job starts at 02:00 | "Best start" shows the sample job's planned start. The clock centre says "Cleanest hour" | `Hero.tsx`, `WaterClock.tsx` |
| 3 | The plan skips the cleanest hours and does not say why | One "why this time" line under the plan | `ResultCard.tsx`, `lib/planViews.ts` |
| 4 | Jargon: stress-weighted, person-days, PUE, Capture formula | Plain words in the UI. A glossary on the Assumptions page explains the words that stay (Capture, weight class, PUE) | pages, `AssumptionsPage.tsx` |
| 5 | Nine form fields before anything happens | Quick fill first. Pausing, cooling and PUE move into "More options", which shows the current choice | `JobForm.tsx` |
| 6 | Chart labels overlap | Fewer ticks, shorter labels | `PlanChart.tsx` |
| 7 | The trade-off slider does nothing (all 11 options are the same plan) | Hidden while the options are identical, with one line saying why and a `placeholder` chip (TODO 5.7) | `PlanResults.tsx` |
| 8 | Measured and modelled chips clutter every line | Smaller, softer chips. Every number still has one, at 4.5:1 contrast | `index.css` |
| 9 | All caps, graph paper, cobalt and yellow compete for attention | Monsoon palette, sentence case, plain background, soft shadows | all CSS |
| 10 | Long site names wrap into a huge heading | Smaller site heading | `index.css` |
| 11 | City tabs overflow on a phone | Tabs wrap | `landing.css` |
| 12 | Empty weight classes look broken | Short message and a "Plan your first job" button | `LeaderboardPage.tsx` |
| 13 | Small print users do not need (AWS list, data list, label legend on home) | Removed. One footer line keeps "How do we know?" | `Layout.tsx`, `LandingPage.tsx` |
| 14 | No way to act on a plan | "Run this plan": copy command, add to calendar, copy share link | `PlanActions.tsx` |
| 15 | No way to compare cities | `/cities` page | `CitiesPage.tsx` |
| 16 | Pages feel like separate demos | Every page links to a next step (9.3) | all pages |

## 9.2 Features added

1. **Plan views.** Timetable (default), Hourly, Calendar and Chart tabs over the same 48 hours. Arrow keys move between tabs. The last tab is remembered in this browser.
2. **Run this plan.** The exact `thirst run --hours … --deadline "…" [--pausable] -- python train.py` command, a `.ics` calendar event with a 10 minute reminder, and a share link.
3. **Share links.** `/plan?city=&gpu=&n=&hours=&deadline=&pause=&cooling=` fills the form. A link that names the whole job plans it straight away.
4. **Why this time** and **forecast freshness** lines in the plan card.
5. **Recent plans.** The last five jobs, saved in this browser, one click to plan again.
6. **Compare cities.** The sample job in six cities, room AC or cooling tower, each with "Plan here".
7. **Glossary** at `/assumptions#glossary`.

## 9.3 How the pages connect

```
Home ──► Plan (city picked on Home) ──► Copy command · Add to calendar · Copy share link
  │        ├─► Compare cities ──► Cities ──► Plan here
  │        └─► How do we know? ──► Assumptions (glossary, every factor)
  ├─► Compare cities
  └─► Leaderboard ──► Site ──► Plan a job here
                        └─► Receipt ──► Plan your next job
```

Navigation: **Plan, Cities, Leaderboard, Assumptions**.

## 9.4 Look and motion

- Monsoon tokens in `index.css`: background `#F7F8F6`, ink `#1D2321`, primary teal `#126E6B`, water `#2B8C88`, run window amber `#F0B43C`. The old token names (`--cobalt`, `--signal`) point at the new colours.
- Every text colour is at least 4.5:1 on white, paper and the sunk background (AGENTS.md rule, checked by axe in e2e).
- Page enter: fade and rise 8 px. Cards follow in a short stagger. Tabs cross fade. All motion stops under `prefers-reduced-motion`.

---

## 9.5 Round 2: after merging `main` (PRs #7 to #11)

The merge brought code-split routes, Playwright e2e with axe, the Pareto table, receipt fixes and four new docs (`TODO.md`, `USER_TEST_GUIDE.md`, `VIDEO_SCRIPT.md`, `SUBMISSION.md`). This round reviews the conflict fixes and works through what those docs ask for.

### Merge review

| File | Decision taken in the merge | Review |
|---|---|---|
| `routes.tsx` | Kept `main`'s lazy routes and added `/cities` as a lazy route | Correct. Cities gets its own chunk |
| `LandingPage.tsx` | `pip install thirst` from `main`, layout from this branch | Correct |
| `PlanPage.test.tsx` | Timetable checks plus `main`'s "Slider positions" table check | Correct |
| `RecentReceipts.tsx` | `main`'s negative-capture cell and per-row link labels. Column label back to "Capture" | Kept "Capture": the CLI receipt, the score parts and the video all use the word. It is now in the glossary |
| `index.css` | Monsoon tokens, but `--text-faint` took the old slate `#566675` | Changed to Monsoon `#5f6a66` (5.3:1 on paper) |

### Problems found by running `main`'s e2e suite on this branch

| Problem | Fix |
|---|---|
| The softer tag chips failed axe contrast (3.2 to 3.7:1) | Darker tag colours, no opacity, 0.68 rem: all at least 4.5:1 |
| The "Sample" stamp on the home receipt failed contrast (opacity 0.8) | Full opacity |
| The timetable's sideways scroll area was not keyboard focusable (axe) | Focusable scroll regions with labels |
| Renaming "Assumptions" to "Method" broke the e2e, the video script and the README | Back to "Assumptions" everywhere |
| "Last 30 days · D1" and "Pick your weight class" were removed, but the e2e and the video rely on them | Restored |
| "Score the choice, not the climate" was replaced, but it is the team's line in the README, writeup and video | Restored |
| The slider tests fail when the slider is hidden | They now skip with the reason, like `main`'s own identical-Pareto skip |
| Four nav items broke words on a 360 px phone ("Pla n") | Links never wrap, and share the row on phones. New e2e check |

### Items from `docs/TODO.md` done here

| TODO | What changed |
|---|---|
| 4.1.a | `thirst doctor` on a laptop GPU prints `[warn]` with "use `thirst run --no-cap`" instead of a misleading `[FAIL]` |
| 4.1.b | `thirst plan` prints the full Assumptions URL |
| 4.1.c | `thirst run --dry-run` uses the plan's exact start and finish |
| 4.1.d | `--modelled` uses the detected GPU when `--gpu-model` and `--gpus` are left out |
| 4.1.e | Short jobs show Wh, mL and g instead of `0.00 kWh` and `0.0 L` |
| 4.1.f | A `--private` site's receipt prints no link (it would be a 404). `config.toml` remembers `public` |
| 5.4 | The phone jump-link e2e waits for the tables to finish rendering |
| 5.6 | README screenshots and SVGs refreshed in the new palette, plus two new ones (actions, cities) |
| 5.7 | Slider hidden while all Pareto points are identical, with an honest note |
| e2e | New specs for the plan views, the run box, share links, the Cities page and the phone nav |
| Docs | `USER_TEST_GUIDE.md` and `VIDEO_SCRIPT.md` describe the new screens |

### Not done here (needs people, hardware or AWS)

- Power-cap sweep, a real `nvml_*` receipt, CSEP and Aqueduct data (TODO 2.x).
- Bedrock access, SNS confirmation, Node 24 action versions, leaderboard precompute (TODO 3.x). Bumping the deploy workflow during judging is a risk, so 3.5 is left for after.
- Lighthouse on the live site (5.3): needs the live site with real network, not this sandbox.
- CLI review leftovers 4.2 (per-run restore markers, token in the child env, and so on).
- Releasing the CLI fixes above needs a new PyPI version (0.3.2) through the workflow from PR #12.
