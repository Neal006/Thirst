import type { RouteObject } from 'react-router-dom'
import { Layout } from './components/Layout'
import { AssumptionsPage } from './pages/AssumptionsPage'
import { LandingPage } from './pages/LandingPage'
import { LeaderboardPage } from './pages/LeaderboardPage'
import { NotFound } from './pages/NotFound'
import { PlanPage } from './pages/PlanPage'
import { ReceiptPage } from './pages/ReceiptPage'
import { RouteError } from './pages/RouteError'
import { SitePage } from './pages/SitePage'

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
            { path: 'plan', element: <PlanPage /> },
            { path: 'receipts/:siteId/:jobId', element: <ReceiptPage /> },
            { path: 'leaderboard', element: <LeaderboardPage /> },
            { path: 'sites/:siteId', element: <SitePage /> },
            { path: 'assumptions', element: <AssumptionsPage /> },
            ...extraPages,
            { path: '*', element: <NotFound /> },
          ],
        },
      ],
    },
  ]
}

export const appRoutes: RouteObject[] = createAppRoutes()
