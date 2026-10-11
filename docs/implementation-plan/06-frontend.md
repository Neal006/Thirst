# Phase 06 — Frontend (Vite + React + TypeScript + Recharts)

> **Status on 11 Oct 2026: ✅ done and live** (https://main.dzxkrtlc7xqfx.amplifyapp.com).
> - Home page with live-data graphics (PR #2) and a game theme on the inner pages (PR #3).
> - The React review leftovers and code-splitting: main chunk 810 → 249 kB, no mock chunk in production (PR #6).
> - **6.11 Playwright + axe done** (PR #9): 74 pass, 4 skip and 1 flaky against the live site.
> - Amplify takes manual zip deploys (`scripts/deploy_web.py`), so `amplify.yml` only applies if the app is ever Git-connected.
> - Phase 09 UX overhaul on `feat/web-ui-accessibility` ([`09-ux-overhaul.md`](09-ux-overhaul.md)): plan views, run box, share links, Cities page, glossary, Monsoon theme, and e2e for all of it. Deploy runs the e2e suite after each deploy.
>
> Open:
> - 6.3.j sentence box (needs Bedrock).
> - 6.8 India finding (needs phase 03).
> - 6.10 Lighthouse report.

Owner: **C** · Window: **Fri 13:00 to Sat 17:00** · Gates: **M2** (Plan page on the live API by 18:00), **M5**
Source: TRD §11, PRD §5 (F1 to F10), §6.1 (web flow), §7 (screens and words).
Rule: **write for a busy student.** Short words, units always shown, every number tagged, works at **360 px**.

[← Index](README.md) · Contracts: [08 §3 API](08-reference-contracts.md#3-api-contract)

---

## 6.0 App structure

```
web/src/
├─ main.tsx  App.tsx  routes.tsx
├─ api/      client.ts (fetch wrapper, timeout 10 s, error envelope) · types.ts (from 08 §3) · mocks/ (MSW handlers + fixtures)
├─ lib/      format.ts (IST times, ranges, units) · tags.ts (tag → label, colour, assumption anchor) · debounce.ts
├─ hooks/    usePlan.ts · useLeaderboard.ts · useSite.ts · useAssumptions.ts
├─ components/
│  ├─ JobForm.tsx        F1
│  ├─ PlanChart.tsx      F2  (ComposedChart)
│  ├─ AlphaSlider.tsx    F3
│  ├─ ParetoChart.tsx    F4  (ScatterChart)
│  ├─ ResultCard.tsx     F5
│  ├─ TagChip.tsx        G5  ("measured" / "modelled" / "placeholder" → link to /assumptions#id)
│  ├─ Range.tsx          "15 to 30%" formatter with tag
│  ├─ ReceiptView.tsx    F8
│  ├─ ScoreBreakdown.tsx F9/F10
│  ├─ LeaderboardTable.tsx · DivisionTabs.tsx · SimulatedChip.tsx · Badge.tsx
│  └─ ui/ Banner.tsx (errors, stale data) · Spinner.tsx · EmptyState.tsx
└─ pages/ PlanPage.tsx · ReceiptPage.tsx · LeaderboardPage.tsx · SitePage.tsx · AssumptionsPage.tsx · NotFound.tsx
```

Routes: `/` (Plan) · `/receipts/:siteId/:jobId` · `/leaderboard?division=D1` · `/sites/:siteId` · `/assumptions` (with `#factor-id` anchors).

---

## 6.1 Scaffold, API client and mock mode (45 min, P0, Fri 13:00)

**Tests first** (`vitest`)

1. `client.post("/plan")` sends `Content-Type: application/json`, times out after 10 s with a friendly error, and maps `{error, message}` to `ApiError` with the server's plain-words message.
2. With `VITE_USE_MOCKS=true`, MSW serves `tests/fixtures/*.json` (copied by `npm run fixtures` from the repo's `tests/fixtures/`).

**Implement**

- **6.1.a** `types.ts` mirrors 08 §3 exactly (`PlanResponse`, `ParetoEntry`, `SeriesRow`, `SiteResponse`, `ReceiptResponse`, `LeaderboardRow`, `AssumptionRow`, `Tag`).
- **6.1.b** `npm run fixtures` copies `../tests/fixtures/*.json` → `src/api/mocks/fixtures/`. Add a **contract test** that parses each fixture with a hand-written type guard. If the engine output shape changes, the web build fails (07.1.c).
- **6.1.c** Router, layout and nav (Plan · Leaderboard · Assumptions), plus a footer with "Every number is labelled measured or modelled → How do we know?".
- **6.1.d** Global styles: system font, a CSS variables palette (water = blue `#1f6feb`, carbon = dark grey `#4b5563`, plan shading = light green, level line = purple; colour-blind safe), `prefers-color-scheme` dark support, base 16 px.

**Done when:** `npm run dev` with mocks shows the layout; tests pass.

---

## 6.2 `JobForm` (F1) (45 min, P0)

- **6.2.a** Fields and defaults (PRD §6.1, F1): GPU model (select from `/assumptions` GPU list, showing max power: "RTX 4090 (450 W)"), GPU count (1 to 4096, default 2), work hours at full power (0.5 to 48, step 0.5, default 6), deadline (`datetime-local`, default **tomorrow 09:00 IST**), can pause (toggle, default yes), city (6 seed cities, default Chennai), cooling (room AC · air-cooled chiller · cooling tower, default room AC), PUE (shown only for cooling tower, default 1.4, range 1.0 to 3.0).
- **6.2.b** Plain labels and helper text: "Hours of work at full GPU power", "Can the job be paused and resumed safely?" with a tooltip "Single-process training only. Multi-GPU distributed jobs can't pause yet."
- **6.2.c** Client-side checks that match the server: the deadline must be after now plus the work hours. Show the error inline next to the field, in plain words.
- **6.2.d** Deadline handling: the input is read as **IST**, whatever the browser's time zone, and sent as ISO with `+05:30`. Test it with the browser time zone set to UTC.
- **6.2.e** Submit is disabled while loading. Enter submits. Every field has a `<label for>`.

**Tests:** default values render; an invalid deadline shows the inline error and makes no request; the body sent matches 08 §3.1.

---

## 6.3 Plan page (F2, F3, F4, F5) (3 h, P0)

Layout: on desktop, the form on the left and the results on the right. On a phone (< 640 px), **result card first**, then the chart, the slider, Pareto, and the form collapsed under "Change job" (TRD §11).

- **6.3.a `usePlan`**: calls `/plan` when the **form** changes (on submit), never when the slider moves. Keeps `response` and `selectedAlpha`.
- **6.3.b `ResultCard`** (F5): "Start at **01:00**, GPU at **85%**, pause **04:00 to 05:00**, done by **08:10**." Then "Saves about **15 to 30%** stress-weighted water and **10 to 20%** CO₂ compared with starting now" with a `TagChip` (modelled) on each, then "≈ **0.1 to 0.2 person-days** of city water", then "Energy from your GPU type: modelled. After a real run, your receipt shows measured energy." If `notes` contains `no_room`, show "Little room to shift before your deadline; starting now is fine."
- **6.3.c `PlanChart`** (F2, Recharts `ComposedChart`, TRD §11): x = 48 hourly slots (IST labels every 3 h); **stacked bars** `direct_l_per_kwh` + `grid_l_per_kwh` (left axis "litres per kWh"); **line** `co2_kg_per_kwh` (right axis "kg CO₂ per kWh"); **`ReferenceArea`** for each run block of the selected plan; **step line** for the power level (0.7, 0.85, 1.0) on a hidden third axis, labelled with "%" in the tooltip; a `ReferenceLine` at the deadline ("Deadline"). The tooltip shows each value with its tag.
- **6.3.d** Chart mobile: `ResponsiveContainer width="100%" height={260}`, no horizontal scroll (TRD §11), ticks reduced on narrow screens.
- **6.3.e `AlphaSlider`** (F3): `<input type="range" min=0 max=1 step=0.1>`, labelled "Save carbon ←→ Save water", default 0.5. **On change, pick `pareto[Math.round(alpha * 10)]` on the client** (D11; same index as the server, 02.7.h): no request, so the update is under 1 second (US2). Keyboard arrows work; `aria-valuetext` reads "Water 50%, carbon 50%".
- **6.3.f** When the alpha changes: the result card, the shaded areas, the level step line and the highlighted Pareto dot all update from the selected entry.
- **6.3.g `ParetoChart`** (F4): a scatter of the 11 entries (x = stress-weighted litres, y = kg CO₂), the selected one bigger and outlined, a tooltip with α, start and level. Clicking a dot sets the slider. **Cut order (PRD 5.4):** this is the first chart removed if late. The slider stays.
- **6.3.h** "How do we know?" link under the card → `/assumptions`.
- **6.3.i** States: loading (skeleton card plus "Planning…"), error banner (server message plus "Try again"), stale forecast banner from `tags.forecast == "cached"`: "Weather data is N hours old; using the last forecast" (TRD §11).
- **6.3.j (P1)** A sentence box above the form: "Describe your job in one sentence". `POST /explain {text}` → fills the form and shows the 3-sentence explanation with a `source` chip ("AI" / "template"). Hidden if the endpoint returns 404.

**Tests (vitest + RTL):** `ResultCard` renders ranges with tags and never shows a single bare saving number; the slider changes the card text **without any fetch** (spy on `fetch`); the `no_room` copy appears; the Pareto click updates the slider.

---

## 6.4 Number honesty helpers (G5) (30 min, P0)

- **6.4.a** `Range.tsx` always renders `lo to hi` + unit + `TagChip`. With `lo == hi` after rounding, it renders "about X".
- **6.4.b** `TagChip` maps `measured` (green outline), `modelled` (blue outline), `placeholder` (amber), `sourced`, `calibrated`, and links to `/assumptions#<factor-id>` or the section anchor.
- **6.4.c** A lint-like unit test scans the rendered DOM of each page (with fixtures) for numbers with a `%`, `L`, `kg` or `kWh` unit that have **no** sibling `TagChip`, and fails if it finds one. This keeps PRD G5 enforced.

---

## 6.5 Receipt page (F8) (60 min, P0)

- **6.5.a** Route `/receipts/:siteId/:jobId`: data comes from `GET /receipts/{site_id}/{job_id}` (D24, 05.7.e), which has the full Base/Best/Actual breakdown. The CLI prints this URL. Mock with `tests/fixtures/receipt_response.json`.
- **6.5.b** Three columns (one stacked list on a phone): **"If you had started right away"** (Base) · **"Best plan"** (Best) · **"What you did"** (Actual). Each shows kWh, litres (direct and grid), stress-weighted litres, kg CO₂ and person-days, each with a tag. Energy in Actual is **measured** if `method` is NVML.
- **6.5.c** Capture banner: "You took **86%** of the possible saving". If no room: "No room to shift: this job doesn't count toward your score."
- **6.5.d** Footnotes: "Scored with the forecast saved when you planned (fair to you). Absolute litres use observed weather where available (N of M hours)." Then cap applied yes/no, method, GPU.
- **6.5.e (P2)** Share card PNG (US10): `html-to-image`, after the hackathon.

---

## 6.6 Leaderboard and Site pages (F9, F10) (90 min, P0)

- **6.6.a `LeaderboardPage`**: `DivisionTabs` (D1 "Small labs (up to 16 GPUs)", D2 "Clusters (17 to 256)", D3 "Facilities (257 to 4,096)", D4 "Hyperscale (above 4,096)"), default D1 (US6). Board switcher with only "Score" in v0 (P1 adds "Most improved", "Basin guardian").
- **6.6.b** Row: rank · name + `SimulatedChip` ("Simulated") · badge · score + "Provisional" · flexible share · **monthly footprint** (kWh, litres, kg CO₂) · receipts. Unrated sites are listed last with "Not rated yet".
- **6.6.c** On a phone the table becomes cards. No horizontal scroll.
- **6.6.d `SitePage`** (US5): header (name, city, cooling, division, badge); `ScoreBreakdown` with **A Behaviour** (out of 50), **B Facility efficiency: "Not rated"** with the explanation "Needs metered building data", **C Measurement and openness** (out of 20, with sub-parts: measured share, coverage self-declared, public); the line "Provisional: building efficiency not rated yet" (PRD §7); the last 10 receipts (date, kWh, capture, link); the absolute monthly footprint, with person-days.
- **6.6.e** An empty site shows "No receipts yet. Run `thirst run …` to get your first one." with a copy button.

- **6.6.f (P1, F14, first in the PRD 5.4 cut order)** Extra boards `board=improved` (largest Capture rise vs the previous 30 days) and `board=basin` (most stress-weighted litres avoided in High or Extremely-high basins). No work starts unless all P0 is green at Sat 12:00. It needs a matching engine function and a `/leaderboard` `board` value.

**Tests:** the division tabs change the query; the simulated chip is shown; no GPU count is rendered anywhere (privacy, TRD 5.9); B always shows "Not rated".

---

## 6.7 Assumptions page (F6, US7) (45 min, P0)

- **6.7.a** A table from `GET /assumptions`, grouped (Cooling · Grid carbon · Grid water · Water stress · GPU and power cap · Score · People). Columns: name, value (with low to high), unit, status chip, source link.
- **6.7.b** Every row has `id={factor_id}` so `TagChip` links land on it, and the row is highlighted when targeted (`:target`).
- **6.7.c** A text block at the top in plain words: "Energy is measured from the GPU when you use `thirst run`. Water and CO₂ are modelled from that energy. We use the average grid mix, not the marginal plant. We leave out the water and carbon used to make the GPU." (Idea §11).
- **6.7.d** Statuses read "Placeholder: to be replaced by our measured sweep" where that applies (PRD §7).

---

## 6.8 Home India finding (F13, P1)

- **6.8.a** If `public/india_finding.png` exists, show it above the form with the one-line headline from Step 0 and the link "How we got this".
- **6.8.b** `alt` text is the headline plus the key numbers.

---

## 6.9 Amplify Hosting deploy (45 min, P0; hook it up at **Fri 13:15 on the scaffold**, point it at the live API last, by 18:00)

C's Friday afternoon (6.1 + 6.2 + 6.3 + 6.9 ≈ 5 h 15 min) is tight. So connect Amplify first, while the app is still a scaffold, to get build problems out of the way early. Switch `VITE_API_URL` to the live API at the end. If 6.3 runs past 16:30, move 6.3.g (Pareto) to Saturday.

- **6.9.a** Amplify console → Host web app → GitHub → repo `thirst`, branch `main` (a private repo works through the GitHub App).
- **6.9.b** Monorepo: app root `web`. `amplify.yml`:
  ```yaml
  version: 1
  applications:
    - appRoot: web
      frontend:
        phases:
          preBuild: { commands: [ "npm ci" ] }
          build:    { commands: [ "npm run build" ] }
        artifacts: { baseDirectory: dist, files: [ "**/*" ] }
        cache:     { paths: [ "node_modules/**/*" ] }
  ```
- **6.9.c** Environment variables: `VITE_API_URL=<ApiUrl>`, `VITE_USE_MOCKS=false`, and `AMPLIFY_MONOREPO_APP_ROOT=web`.
- **6.9.d** SPA rewrite: source `</^[^.]+$|\.(?!(css|gif|ico|jpg|js|png|txt|svg|woff|woff2|ttf|map|json)$)([^.]+$)/>` → target `/index.html` → `200 (Rewrite)`. Deep links like `/sites/s_x` must load.
- **6.9.e** Give the domain to A for CORS (5.11.b). Re-test from the live URL.
- **6.9.f Fallback** (TRD §16): if the Amplify build fails twice, `npm run build` locally → S3 bucket (private) + CloudFront with OAC → note the domain → update CORS.

**Done when:** the live URL loads signed-out on a phone (PRD §8.1), and Plan works against the live API.

---

## 6.10 Accessibility and phone pass (Sat 12:00 to 17:00, P0)

- **6.10.a** Run every page at **360 × 740** in Chrome DevTools and on one real phone.
- **6.10.b** Keyboard only: tab order, visible focus, the slider works with arrow keys, the dialog/tooltip opens with Enter.
- **6.10.c** Contrast ≥ 4.5:1 for text; the chart colours are distinguishable in a deuteranopia simulation.
- **6.10.d** Charts have a text summary (`<figcaption>`) for screen readers: "Lowest water hours: 12:00 to 15:00; lowest CO₂: 11:00 to 14:00."
- **6.10.e** Lighthouse mobile: Performance ≥ 80, Accessibility ≥ 95. Fix the top issues only.
- **6.10.f** Review: `ecc:react-reviewer` + `ecc:typescript-reviewer` on `web/src`, and the `ecc:frontend-a11y` skill. Fix CRITICAL and HIGH findings.

---

## 6.11 Frontend E2E (Playwright, Sat afternoon, P0)

`web/e2e/`, run against the **live** URL and against mocks in CI:

- `plan.spec.ts`: load `/` → press Plan → the card appears in < 3 s → move the slider to 1.0 → the card text changes within 1 s and **no** `/plan` request was sent → the "How do we know?" link goes to Assumptions.
- `board.spec.ts`: `/leaderboard` → D1 rows with the Simulated chip → click a row → the site page shows "Provisional" and B "Not rated".
- `mobile.spec.ts`: the same flows at a 360 × 740 viewport; `document.scrollingElement.scrollWidth <= 360`.
