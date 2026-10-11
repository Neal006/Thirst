# Thirst website (`web/`)

The React site that the live app runs: https://main.dzxkrtlc7xqfx.amplifyapp.com

Built with Vite, React 19, TypeScript, React Router 7 and Recharts. Tests use Vitest + Testing Library, browser tests use Playwright, and lint is oxlint. **Needs Node 22.12+.**

## Run it

```bash
npm ci

# A: against the real API code on your machine (no AWS), in another terminal from the repo root:
#    python scripts/local_api.py           → http://127.0.0.1:3000
VITE_API_URL=http://127.0.0.1:3000 npm run dev      # → http://localhost:5173

# B: against the live API (5173 is an allowed CORS origin)
VITE_API_URL=https://l6y3i40hh4.execute-api.ap-south-1.amazonaws.com npm run dev

# C: offline with fixture data (dev only)
VITE_USE_MOCKS=true npm run dev
```

| Variable | Meaning |
|---|---|
| `VITE_API_URL` | API base URL. A production build **fails** unless it is `https://`. |
| `VITE_USE_MOCKS` | `true` serves fixture data in dev. A production build **fails** if it is `true`, and the mock code is left out of the bundle. |

See `.env.example`.

## Checks

```bash
npm test -- --run        # ~510 Vitest tests, including the honesty scan (src/test/honesty.ts)
npm run lint             # oxlint
npm run build            # tsc -b + vite build
npm run e2e              # Playwright against the live site (read-only guard), desktop + 360 px phone
npm run e2e:typecheck
E2E_BASE_URL=http://localhost:5173 npm run e2e      # against a local `npm run preview -- --port 5173`
npm run fixtures         # copy tests/fixtures/*.json into src/api/mocks/fixtures
```

**Honesty rule.** `src/test/honesty.ts` scans the rendered DOM. A test fails if a user-facing number has no tag chip (`measured`, `modelled`, `sourced`, `calibrated`, `placeholder`) next to it.

**Accessibility.** The e2e suite runs axe and fails on any serious or critical issue. Keep text contrast ≥ 4.5:1 and tap targets ≥ 24 px.

## Map

| Path | What |
|---|---|
| `src/routes.tsx` | `/` home (loaded eagerly). `/plan`, `/leaderboard`, `/sites/:siteId`, `/receipts/:siteId/:jobId` and `/assumptions` load on first visit (react-router `lazy`). |
| `src/pages/` | One file per page. `LandingPage` + `pages/landing.css` is the home page. |
| `src/components/landing/` | Home-page graphics: `Hero`, `WaterClock`, `Beakers`, `PowerCap`, `LoopStrip`, `BoardPreview` |
| `src/components/` | Planner (`JobForm`, `ResultCard`, `PlanChart`, `AlphaSlider`, `ParetoChart`/`ParetoTable`), board (`DivisionTabs`, `LeaderboardTable`, `ScoreRing`), receipts, `TagChip` |
| `src/api/` | `client.ts` (fetch, timeouts, abort), `guards.ts` (runtime checks of every response), `types.ts`, `defaultClient.ts` (picks mocks or the real API), `mocks/` |
| `src/hooks/` | `usePlan`, `useLoad`, `useAssumptions`, `useCityForecast` (one shared `/plan` per city and cooling), `useLeaderboard` |
| `src/lib/` | Formatting, tags, deadlines (IST), job-form presets, badges, landing-page maths |
| `src/index.css`, `theme.css`, `pages.css` | Light theme tokens (Archivo + IBM Plex Mono, cobalt `#0a5cff`, signal yellow `#ffcc00`, ink `#0b1620`) |
| `e2e/` | Playwright specs. `fixtures.ts` holds the read-only guard (only GET and `POST /plan` may leave the browser). |

## Deploy

**Don't deploy by hand in normal use.**
- **Automatic:** merging to `main` runs CI, then `.github/workflows/deploy.yml`. That builds with the stack's API URL and uploads the zip to Amplify app `dzxkrtlc7xqfx` through `scripts/deploy_web.py`.
- **By hand:** `python scripts/deploy_web.py --app-id dzxkrtlc7xqfx --api-url <ApiUrl> --profile thirst`.

`amplify.yml` only applies if the Amplify app is ever connected to Git.
