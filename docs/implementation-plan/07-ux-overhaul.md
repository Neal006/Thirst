# Phase 07: UX overhaul after the user test

Goal: make Thirst feel like one finished product. Every page should answer one question, point to the next step, and use plain words.

Palette: Monsoon. Layout ideas kept: Timetable, Hourly forecast, City board, Calendar. Skipped: Data journal and the large console, because they repeat what other pages already do. The useful part of "Three questions" (plain choices instead of a long form) goes into the planner form.

[← Index](README.md)

---

## 7.1 User test problems and the fix for each

| # | Problem found in the test | Fix | Where |
|---|---|---|---|
| 1 | Home sections stay blank until you scroll past them | Sections are visible by default. The scroll animation only moves them a few pixels | `index.css`, `landing.css` |
| 2 | Home says the best start is 11:00 but the sample job starts at 02:00 | The hero shows the planned start of the sample job, so both numbers match | `Hero.tsx` |
| 3 | The plan skips the cleanest hours and does not say why | One line under the plan: "why this time" | `ResultCard.tsx`, `lib/planViews.ts` |
| 4 | Jargon: stress-weighted, person-days, PUE, capture, D1 to D4 | Plain words in the UI. A short glossary on the Method page explains the rest | all pages, `AssumptionsPage.tsx` |
| 5 | Nine form fields before anything happens | Quick picks first. Pausing, cooling and PUE move into "More options" | `JobForm.tsx` |
| 6 | Chart labels overlap | Fewer ticks, shorter labels | `PlanChart.tsx` |
| 7 | The trade-off chart shows one dot | Hidden when all options are the same | `PlanResults.tsx` |
| 8 | Too many "modelled" chips | Chips are smaller and quieter. They stay in place so every number is still labelled | `index.css` |
| 9 | Shouting headings, graph paper, cobalt and yellow fight for attention | Monsoon palette, sentence case, plain background | `index.css`, `landing.css` |
| 10 | Long site names wrap into a huge heading | Smaller heading that wraps cleanly | `index.css` |
| 11 | City tabs overflow on a phone | Tabs wrap onto two lines | `landing.css` |
| 12 | Empty D2 to D4 tabs look broken | A short message says no labs are in that group yet | `LeaderboardTable.tsx` |
| 13 | Lots of small print that users do not need | Remove the AWS and data lists, the label legend on home, extra eyebrows and notes | `Layout.tsx`, pages |
| 14 | No way to act on a plan | Copy run command, add to calendar, share link | new `PlanActions.tsx` |
| 15 | Hard to compare cities | New Cities page | new `CitiesPage.tsx` |
| 16 | Pages feel disconnected | Every page ends with a clear next step (see 7.3) | all pages |

## 7.2 Features added (small and easy to fit in)

1. **Plan views.** Tabs above the chart: Timetable (48 hour grid), Hourly (list with bars), Calendar (day columns), Chart (the existing chart). Same data, four ways to read it.
2. **Plan actions.** Copy the `thirst run` command, download a calendar file with a 10 minute reminder, copy a link that reopens the same plan.
3. **Shareable planner links.** `/plan?city=&gpu=&n=&hours=&deadline=&pause=&cooling=` fills the form.
4. **Why this time.** One sentence that explains the start time.
5. **Forecast freshness.** "Forecast updated N hours ago" under the plan.
6. **Recent plans.** The last five jobs you planned, saved in this browser, one click to plan again.
7. **City board.** Six cities side by side: the cleanest start tomorrow, a small 48 hour strip, and a "Plan here" button.
8. **Glossary.** Short definitions on the Method page, linked from the plan.

Not added now (bigger work): cost in rupees, lab queue, monthly report, email reminders.

## 7.3 How the pages connect

```
Home ──► Plan (city chosen on home)
  │        ├─► Copy command / Calendar / Share link
  │        ├─► Compare cities ──► Cities ──► Plan here
  │        └─► What do these words mean? ──► Method#glossary
  ├─► Cities
  └─► Leaderboard ──► Site ──► Receipt ──► Plan your next job
```

Navigation: Plan, Cities, Leaderboard, Method.

## 7.4 Look and motion

- Monsoon tokens: background `#F7F8F6`, ink `#1D2321`, primary teal `#126E6B`, water `#2B8C88`, carbon `#55605D`, run window mango `#F0B43C`.
- Archivo for text, IBM Plex Mono only for numbers and commands.
- Page enter: fade and rise 8 px over 250 ms. Cards follow in a short stagger.
- Tabs and views cross fade. Buttons lift slightly on hover.
- All motion turns off with `prefers-reduced-motion`.

## 7.5 Order of work

1. Pure helpers in `lib/planViews.ts` with tests.
2. `PlanViews`, `PlanActions`, recent plans, wired into `PlanResults` and `ResultCard`.
3. Planner form: "More options" and link prefill.
4. Cities page, route and nav.
5. Theme, motion and copy cleanup across pages.
6. Tests, lint, build, screenshots at 360 px and 1280 px.
