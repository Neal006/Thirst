import { Link } from 'react-router-dom'
import type { LeaderboardRow } from '../../api/types'
import { useLeaderboard } from '../../hooks/useLeaderboard'
import { DIVISIONS } from '../../lib/divisions'
import { ratedFirst } from '../../lib/leaderboardView'
import { Amount } from '../Amount'
import { Badge } from '../Badge'
import { SimulatedChip } from '../SimulatedChip'

const RING = 2 * Math.PI * 34

function ScoreRing({ score }: { score: number | null }) {
  const share = score === null ? 0 : Math.max(0, Math.min(1, score / 100))
  return (
    <div className="ring">
      <svg viewBox="0 0 80 80" aria-hidden="true" focusable="false">
        <circle className="ring-track" cx="40" cy="40" r="34" />
        <circle
          className="ring-fill"
          cx="40"
          cy="40"
          r="34"
          strokeDasharray={RING}
          style={{ '--ring-off': RING * (1 - share), '--ring-len': RING } as React.CSSProperties}
        />
      </svg>
      <span className="ring-value">
        {score === null ? '–' : Math.round(score)}
        <span className="visually-hidden"> out of 100</span>
      </span>
    </div>
  )
}

function Podium({ row, place }: { row: LeaderboardRow; place: number }) {
  return (
    <li className={`podium podium-${place}`}>
      <span className="podium-rank" aria-hidden="true">
        {place}
      </span>
      <ScoreRing score={row.score} />
      <div className="podium-body">
        <Link className="podium-name" to={`/sites/${encodeURIComponent(row.site_id)}`}>
          <span className="visually-hidden">Rank {place}: </span>
          {row.name}
        </Link>
        <div className="podium-chips">
          <Badge badge={row.badge} />
          {row.simulated ? <SimulatedChip /> : null}
          {row.provisional ? <span className="chip">Provisional</span> : null}
        </div>
        <p className="podium-foot">
          Monthly water <Amount value={row.monthly_absolute.litres} unit="L" tag="modelled" />
        </p>
      </div>
    </li>
  )
}

export function BoardPreview() {
  const { state, reload } = useLeaderboard('D1')
  const top = state.status === 'ready' ? ratedFirst(state.data.rows).slice(0, 3) : []

  return (
    <section className="section board reveal" aria-labelledby="board-title">
      <div className="section-head section-head-split">
        <div>
          <p className="eyebrow">Leaderboard · small labs</p>
          <h2 id="board-title" className="section-title">
            Score the choice, not the climate
          </h2>
        </div>
        <div className="capture-formula" aria-label="Capture equals one minus J actual, over one minus J best">
          <span className="cf-name">Capture</span>
          <span className="cf-eq">=</span>
          <span className="cf-frac">
            <span>1 − J<sub>actual</sub></span>
            <span>1 − J<sub>best</sub></span>
          </span>
          <span className="cf-note">share of the possible saving you took</span>
        </div>
      </div>
      {state.status === 'loading' ? (
        <ol className="podiums" aria-busy="true">
          {[1, 2, 3].map((n) => (
            <li key={n} className="podium podium-ghost">
              <span className="skeleton" aria-hidden="true" />
              <span className="skeleton" aria-hidden="true" />
            </li>
          ))}
        </ol>
      ) : null}
      {state.status === 'error' ? (
        <div className="banner banner-error" role="alert">
          <p>{state.message}</p>
          <button type="button" className="btn" onClick={reload}>
            Try again
          </button>
        </div>
      ) : null}
      {state.status === 'ready' && top.length === 0 ? (
        <p className="muted">No small labs on the board yet. Yours could be the first.</p>
      ) : null}
      {top.length > 0 ? (
        <ol className="podiums" aria-label="Top small labs this month">
          {top.map((row, i) => (
            <Podium key={row.site_id} row={row} place={i + 1} />
          ))}
        </ol>
      ) : null}
      <ol className="classes" aria-label="Size groups">
        {DIVISIONS.map((d, i) => (
          <li key={d.id} className={i === 0 ? 'class is-here' : 'class'} style={{ '--i': i } as React.CSSProperties}>
            <span className="class-id">{d.id}</span>
            <span className="class-label">{d.label}</span>
          </li>
        ))}
      </ol>
      <p className="board-more">
        <Link className="btn" to="/leaderboard">
          See the full board <span className="btn-arrow" aria-hidden="true">→</span>
        </Link>
        <span className="muted">Demo sites are marked Simulated.</span>
      </p>
    </section>
  )
}
