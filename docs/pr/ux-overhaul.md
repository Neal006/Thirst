# UX overhaul: plan views, plan actions, city board and the Monsoon theme

**Branch:** `feat/web-ui-accessibility` · **Area:** `web/` only (no API, CLI or engine changes) · **Plan:** [docs/implementation-plan/07-ux-overhaul.md](../implementation-plan/07-ux-overhaul.md)

## Summary

We ran a user test on the web app. People could get a plan, but they did not understand all of it, and then had nothing to do with it. This PR fixes the 16 problems from that test and adds 8 small features. Together they turn the site into one connected product: **Home → Plan → run it, share it or compare cities → Leaderboard → Site → Receipt → plan again.**

It also moves the look to a calm, light palette (Monsoon) and removes small print that users did not need.

| Plan page | Cities page |
|---|---|
| ![Plan page](screenshots/plan.png) | ![Cities page](screenshots/cities.png) |

| Home | Plan on a phone |
|---|---|
| ![Home](screenshots/home.png) | ![Plan on a phone](screenshots/plan-phone.png) |

---

## Problems solved

Each row is one finding from the user test.

| # | What users ran into | What this PR does |
|---|---|---|
| 1 | Home sections stayed blank until you scrolled past them | Sections are now visible by default. The scroll effect only lifts them a few pixels |
| 2 | Home said "best start 11:00" while the sample job started at 02:00 | The stat now shows the sample job's planned start. The clock centre is labelled "Cleanest hour" |
| 3 | The plan skipped the cleanest hours and never said why | A "why this time" line under the plan explains it |
| 4 | Jargon: stress-weighted, person-days, Capture, D1 to D4, the Capture formula | Plain words in the UI. A glossary on the Method page explains the rest |
| 5 | Nine form fields before anything happened | City sits with the main fields. Pausing, cooling and PUE move into "More options", which shows the current choice |
| 6 | Chart axis labels overlapped | Fewer ticks and shorter labels |
| 7 | The trade-off chart showed a single dot | The slider and chart are hidden when every option is the same plan |
| 8 | Measured and modelled chips cluttered every line | Chips are smaller and quieter. Every number still has one |
| 9 | All-caps headings, graph paper, cobalt and yellow competed for attention | Monsoon palette, sentence-case headings, plain background, soft shadows |
| 10 | Long site names wrapped into a huge heading | Smaller site heading that wraps cleanly |
| 11 | City tabs overflowed on a phone | Tabs wrap onto a second line |
| 12 | Empty leaderboard groups looked broken | Short message plus a "Plan your first job" button |
| 13 | Footer and pages full of small print (AWS list, data list, label legend, eyebrows) | Removed. One footer line keeps the "How do we know?" link |
| 14 | No way to act on a plan | "Run this plan" card: copy command, add to calendar, copy share link |
| 15 | No way to compare cities | New Cities page |
| 16 | Pages felt like separate demos | Every page now links to a clear next step (see the flow below) |

## New features

All of these are small, use data the app already fetches, and need no backend change.

1. **Plan views** (`PlanViews.tsx`). Tabs above the chart: **Timetable** (48 hour grid, the default), **Hourly** (list with bars), **Calendar** (day columns) and **Chart** (the existing chart). Arrow keys move between tabs. The last tab you picked is remembered in this browser.
2. **Run this plan** (`PlanActions.tsx`). Copies the exact `thirst run --hours … --deadline "…" [--pausable] -- python train.py` command, downloads a `.ics` calendar event with a 10 minute reminder, and copies a share link.
3. **Share links.** `/plan?city=&gpu=&n=&hours=&deadline=&pause=&cooling=` fills the form. A link that names the whole job is planned straight away.
4. **Why this time.** One sentence: the plan uses the cleanest hours, or they end after your deadline, or they come later.
5. **Forecast freshness.** "Forecast updated N hours ago" in the plan card.
6. **Recent plans.** The last five jobs you planned, saved in this browser. One click plans the same job again.
7. **Cities page** (`/cities`). Six cities with the same sample job: best start, a 48 hour strip, water for the job, saving vs now, Room AC or Cooling tower, and a "Plan here" button.
8. **Glossary** on the Method page (`/assumptions#glossary`).

## How the pages connect now

```
Home ──► Plan (city picked on Home)
  │        ├─► Copy command · Add to calendar · Copy share link
  │        ├─► Compare cities ──► Cities ──► Plan here
  │        └─► How do we know? ──► Method (glossary, every factor)
  ├─► Compare cities
  └─► Leaderboard ──► Site ──► Plan a job here
                        └─► Receipt ──► Plan your next job
```

Navigation is now **Plan, Cities, Leaderboard, Method**. "Method" replaces "Assumptions", which read as jargon. The route stays `/assumptions`, so old links keep working.

## Why these choices

- **Four views of one plan, not four pages.** Users read time in different ways. Some think in a calendar, some in a list. The data is the same `series` and `series_overlay`, so the views are cheap and always agree with each other.
- **Timetable is the default.** In the test it was the quickest to read: you can see where the job runs and where the clean hours are without reading axes.
- **Actions next to the answer.** The plan was a dead end. The CLI already takes `--hours`, `--deadline` and `--pausable`, so copying the command closes the loop to a real run and a receipt.
- **Cities page instead of a bigger form.** Comparing places was the most common "what if" in the test. Reusing `useCityForecast` gives one shared request per city, the same one the home page already makes.
- **Skipped on purpose:** the "Data journal" and "Large console" layouts repeated what other pages show. From "Three questions" we kept only the plain-language cooling help and the shorter form.
- **Browser storage only for conveniences** (last tab, recent plans). Every read and write is wrapped in `try/catch`. The app works the same with storage blocked.
- **Labels stay.** The project rule that every number with a unit carries a measured or modelled chip still holds. Chips are quieter but still in the DOM, and the honesty scan (`test/honesty.ts`) runs on the new views and the Cities page.

## Look and motion

- **Monsoon palette.** Background `#F7F8F6`, ink `#1D2321`, primary teal `#126E6B` (6.1:1 on white), water `#2B8C88`, carbon `#55605D`, run window mango `#F0B43C`. The old variable names (`--cobalt`, `--signal`) now point to the new colours, so existing rules pick them up without a rename.
- Five-step teal scale (`--lv-0` to `--lv-4`) for water per kWh, shared by the timetable, calendar, hourly bars and city strips.
- Brand mark and favicon use the new colours.
- **Motion.** Each page fades and rises 8 px on navigation (250 to 300 ms). Cards follow in a short stagger, view tabs cross fade, buttons lift 1 px on hover. All of it turns off under `prefers-reduced-motion`.

## Files changed

**New**

| File | What it is |
|---|---|
| `web/src/lib/planViews.ts` | Pure helpers: hour cells, day rows, cleanest window, why-this-time, run command, `.ics` file, share query |
| `web/src/lib/recentPlans.ts` | Recent plans in localStorage, safe when storage fails |
| `web/src/components/PlanViews.tsx` | Timetable, Hourly, Calendar and Chart tabs |
| `web/src/components/PlanActions.tsx` | Copy command, calendar download, share link |
| `web/src/pages/CitiesPage.tsx` | City board |
| `web/src/lib/planViews.test.ts`, `web/src/pages/CitiesPage.test.tsx` | Tests for the above |
| `docs/implementation-plan/07-ux-overhaul.md` | The plan behind this PR |

**Changed**

| Area | Files |
|---|---|
| Planner | `PlanPage.tsx` (share links, recent plans, auto plan), `PlanResults.tsx`, `ResultCard.tsx`, `JobForm.tsx`, `CoolingFields.tsx`, `AlphaSlider.tsx`, `PlanChart.tsx`, `lib/jobForm.ts` (`valuesFromQuery`) |
| Frame and routes | `Layout.tsx` (nav, slim footer, page motion), `routes.tsx` (`/cities`), `BrandMark.tsx`, `index.html`, `public/favicon.svg` |
| Pages | `LandingPage.tsx`, `Hero.tsx`, `WaterClock.tsx`, `Beakers.tsx`, `BoardPreview.tsx`, `LeaderboardPage.tsx`, `SitePage.tsx`, `ReceiptPage.tsx`, `ReceiptView.tsx`, `RecentReceipts.tsx`, `AssumptionsPage.tsx` |
| Styles | `index.css`, `theme.css`, `pages.css`, `pages/landing.css` |
| Tests updated for new copy | `ResultCard.test.tsx`, `JobForm.test.tsx`, `Layout.test.tsx`, `PlanPage.test.tsx`, `routes.test.tsx`, `lib/jobForm.test.ts` |

## Testing

```bash
cd web
npm ci
npx vitest run   # 486 passed (was 474, plus 12 new)
npm run lint     # oxlint, no warnings
npm run build    # passes
VITE_USE_MOCKS=true npm run dev   # then open the routes below
```

The full hand-test list for the CLI and the website, with what was already run, is in [manual-test-checklist.md](manual-test-checklist.md). The short version, at 1280 px and 390 px wide:

- [ ] `/` loads with every section visible, and "Plan a job" and "Compare cities" work
- [ ] `/plan`: press **Plan**, then switch Timetable, Hourly, Calendar and Chart. Use the arrow keys on the tabs
- [ ] **Copy** puts a `thirst run …` command on the clipboard
- [ ] **Add to calendar** downloads `thirst-plan.ics`, which imports into Google Calendar or Outlook with a 10 minute reminder
- [ ] **Copy share link**, open it in a new tab: the job is filled in and planned
- [ ] The job appears under **Recent** and one click plans it again
- [ ] `/cities`: six cards, Room AC and Cooling tower toggle, "Plan here" opens the planner for that city
- [ ] `/leaderboard`, a site page and a receipt each have a link back into the planner
- [ ] `/assumptions#glossary` shows the glossary
- [ ] With reduced motion turned on in the OS, nothing animates

## Review guide

Suggested order, about 20 minutes:

1. `docs/implementation-plan/07-ux-overhaul.md`: the problem list and the plan.
2. `web/src/lib/planViews.ts` and its test: all the logic for the new views and actions is here, free of React.
3. `PlanViews.tsx`, `PlanActions.tsx`, `PlanResults.tsx`, `ResultCard.tsx`: how the plan page uses it.
4. `PlanPage.tsx` and `lib/jobForm.ts` (`valuesFromQuery`): share links and recent plans.
5. `CitiesPage.tsx`, `routes.tsx`, `Layout.tsx`: the new page and how it is reached.
6. CSS last. The new rules sit together at the end of `index.css` under "Monsoon refresh". The other style files mostly lose uppercase, condensed widths and hard offset shadows.

## Notes and follow-ups

- In mock mode all 11 trade-off options are identical, so the trade-off slider is hidden. It shows with real API data.
- Not in this PR (bigger pieces of work): cost in rupees, a shared lab queue, monthly email report, push reminders.
- The bundle size warning from Vite existed before this PR. Code splitting Recharts would fix it.
