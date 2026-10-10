import { useSearchParams } from 'react-router-dom'
import { DivisionTabs } from '../components/DivisionTabs'
import { LeaderboardTable } from '../components/LeaderboardTable'
import { Banner } from '../components/ui/Banner'
import { EmptyState } from '../components/ui/EmptyState'
import { Spinner } from '../components/ui/Spinner'
import { useLeaderboard } from '../hooks/useLeaderboard'
import { usePageTitle } from '../hooks/usePageTitle'
import { divisionLabel, parseDivision } from '../lib/divisions'

export function LeaderboardPage() {
  usePageTitle('Leaderboard')
  const [params, setParams] = useSearchParams()
  const division = parseDivision(params.get('division'))
  const { state, reload } = useLeaderboard(division)
  const rated = state.status === 'ready' ? state.data.rows.filter((r) => r.score !== null).length : 0

  return (
    <div className="board-page">
      <div className="page-head">
        <div>
          <p className="eyebrow">Last 30 days · {division}</p>
          <h1>Leaderboard</h1>
          <p className="muted">
            Score over the last 30 days. Scores are provisional until building efficiency is rated.
          </p>
        </div>
        {state.status === 'ready' ? (
          <dl className="head-stats">
            <div>
              <dt>Sites</dt>
              <dd>{state.data.rows.length}</dd>
            </div>
            <div>
              <dt>Rated</dt>
              <dd>{rated}</dd>
            </div>
          </dl>
        ) : null}
      </div>
      <p className="pick-label">Pick your weight class</p>
      <DivisionTabs value={division} onChange={(d) => setParams({ division: d })} />
      {state.status === 'loading' ? <Spinner label="Loading the board…" lines={4} /> : null}
      {state.status === 'error' ? (
        <Banner kind="error" actionLabel="Try again" onAction={reload}>
          {state.message}
        </Banner>
      ) : null}
      {state.status === 'ready' && state.data.rows.length === 0 ? (
        <EmptyState title="No sites in this division yet" className="empty-board">
          <p>
            Register a site and send a receipt to appear here. The {divisionLabel(division).toLowerCase()} podium is
            empty: first receipt takes first place.
          </p>
        </EmptyState>
      ) : null}
      {state.status === 'ready' && state.data.rows.length > 0 ? (
        <LeaderboardTable rows={state.data.rows} />
      ) : null}
    </div>
  )
}
