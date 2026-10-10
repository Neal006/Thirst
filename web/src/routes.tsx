import type { RouteObject } from 'react-router-dom'
import { Layout } from './components/Layout'
import { AssumptionsPage } from './pages/AssumptionsPage'
import { LeaderboardPage } from './pages/LeaderboardPage'
import { NotFound } from './pages/NotFound'
import { PlanPage } from './pages/PlanPage'
import { ReceiptPage } from './pages/ReceiptPage'
import { SitePage } from './pages/SitePage'

/** Plan (/), receipt, leaderboard, site and assumptions (anchors like /assumptions#tau_70). */
export const appRoutes: RouteObject[] = [
  {
    path: '/',
    element: <Layout />,
    children: [
      { index: true, element: <PlanPage /> },
      { path: 'receipts/:siteId/:jobId', element: <ReceiptPage /> },
      { path: 'leaderboard', element: <LeaderboardPage /> },
      { path: 'sites/:siteId', element: <SitePage /> },
      { path: 'assumptions', element: <AssumptionsPage /> },
      { path: '*', element: <NotFound /> },
    ],
  },
]
