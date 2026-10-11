import type { ComponentType } from 'react'
import type { RouteObject } from 'react-router-dom'
import { Layout } from './components/Layout'
import { LandingPage } from './pages/LandingPage'
import { NotFound } from './pages/NotFound'
import { RouteError } from './pages/RouteError'

/**
 * Pages other than home load on first visit (each is its own chunk; the charts library only comes
 * with the planner), so the home page stays light.
 */
const lazyPage = (load: () => Promise<ComponentType>) => async () => ({ Component: await load() })

const planPage = lazyPage(async () => (await import('./pages/PlanPage')).PlanPage)
const receiptPage = lazyPage(async () => (await import('./pages/ReceiptPage')).ReceiptPage)
const leaderboardPage = lazyPage(async () => (await import('./pages/LeaderboardPage')).LeaderboardPage)
const sitePage = lazyPage(async () => (await import('./pages/SitePage')).SitePage)
const assumptionsPage = lazyPage(async () => (await import('./pages/AssumptionsPage')).AssumptionsPage)

/**
 * Home (/), plan (/plan), receipt, leaderboard, site and assumptions (anchors like /assumptions#tau_70).
 *
 * A page that throws is caught by the error element of the group around the pages, so the header
 * and navigation stay. The root one is the last resort for a failure in the layout itself.
 * `extraPages` is for tests that need a page that crashes.
 */
export function createAppRoutes(extraPages: RouteObject[] = []): RouteObject[] {
  return [
    {
      path: '/',
      element: <Layout />,
      errorElement: <RouteError />,
      children: [
        {
          errorElement: <RouteError />,
          children: [
            { index: true, element: <LandingPage /> },
            { path: 'plan', lazy: planPage },
            { path: 'receipts/:siteId/:jobId', lazy: receiptPage },
            { path: 'leaderboard', lazy: leaderboardPage },
            { path: 'sites/:siteId', lazy: sitePage },
            { path: 'assumptions', lazy: assumptionsPage },
            ...extraPages,
            { path: '*', element: <NotFound /> },
          ],
        },
      ],
    },
  ]
}

export const appRoutes: RouteObject[] = createAppRoutes()
