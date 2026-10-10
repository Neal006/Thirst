import { useSearchParams } from 'react-router-dom'
import { DivisionTabs } from '../components/DivisionTabs'
import { LeaderboardTable } from '../components/LeaderboardTable'
import { Banner } from '../components/ui/Banner'
import { EmptyState } from '../components/ui/EmptyState'
import { Spinner } from '../components/ui/Spinner'
import { useLeaderboard } from '../hooks/useLeaderboard'
import { usePageTitle } from '../hooks/usePageTitle'
import { parseDivision } from '../lib/divisions'

export function LeaderboardPage() {
  usePageTitle('Leaderboard')
  const [params, setParams] = useSearchParams()
  const division = parseDivision(params.get('division'))
  const { state, reload } = useLeaderboard(division)

  return (
    <div>
      <h1>Leaderboard</h1>
      <p className="muted">
        Score over the last 30 days. Scores are provisional until building efficiency is rated.
      </p>
      <DivisionTabs value={division} onChange={(d) => setParams({ division: d })} />
      {state.status === 'loading' ? <Spinner label="Loading the board…" lines={4} /> : null}
      {state.status === 'error' ? (
        <Banner kind="error" actionLabel="Try again" onAction={reload}>
          {state.message}
        </Banner>
      ) : null}
      {state.status === 'ready' && state.data.rows.length === 0 ? (
        <EmptyState title="No sites in this division yet">
          <p>Register a site and send a receipt to appear here.</p>
        </EmptyState>
      ) : null}
      {state.status === 'ready' && state.data.rows.length > 0 ? (
        <LeaderboardTable rows={state.data.rows} />
      ) : null}
    </div>
  )
}
