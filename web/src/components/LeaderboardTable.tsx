import { Link } from 'react-router-dom'
import type { LeaderboardRow } from '../api/types'
import { ratedFirst } from '../lib/leaderboardView'
import { Amount } from './Amount'
import { Badge } from './Badge'
import { Range } from './Range'
import { MeterBar, ScoreRing } from './ScoreRing'
import { SimulatedChip } from './SimulatedChip'

function Footprint({ row }: { row: LeaderboardRow }) {
  const m = row.monthly_absolute
  return (
    <ul className="stat-list footprint">
      <li><Amount value={m.kwh} unit="kWh" tag="modelled" /></li>
      <li><Amount value={m.litres} unit="L" tag="modelled" /></li>
      <li><Amount value={m.kg_co2} unit="kg" tag="modelled" /></li>
    </ul>
  )
}

function Row({ row, place }: { row: LeaderboardRow; place: number | null }) {
  const share = row.flex_share * 100
  const medal = place !== null && place <= 3 ? ` medal medal-${place}` : ''
  return (
    <tr className={`board-row${medal}`}>
      <td data-label="Rank" className="rank-cell">
        <span className="rank-num">{row.rank ?? '-'}</span>
      </td>
      <td data-label="Site" className="site-cell">
        <Link to={`/sites/${encodeURIComponent(row.site_id)}`}>{row.name}</Link>{' '}
        {row.simulated ? <SimulatedChip /> : null}
      </td>
      <td data-label="Badge"><Badge badge={row.badge} /></td>
      <td data-label="Score" className="score-cell">
        {row.score === null ? (
          <span className="unrated">Not rated yet</span>
        ) : (
          <span className="score-wrap">
            <ScoreRing score={row.score} size="sm" lead={place === 1} />
            {row.provisional ? <span className="chip">Provisional</span> : null}
          </span>
        )}
      </td>
      <td data-label="Flexible share">
        <MeterBar value={share} max={100} tone="signal" />
        <Range range={[share, share]} unit="%" tag="modelled" />
      </td>
      <td data-label="Monthly footprint"><Footprint row={row} /></td>
      <td data-label="Receipts" className="receipts-cell">{row.receipts}</td>
    </tr>
  )
}

export function LeaderboardTable({ rows }: { rows: readonly LeaderboardRow[] }) {
  const ordered = ratedFirst(rows)
  return (
    <div className="board-scroll">
      <table className="data-table cards-on-phone board-table">
        <caption className="visually-hidden">Sites ranked by score over the last 30 days</caption>
        <thead>
          <tr>
            <th scope="col">Rank</th>
            <th scope="col">Site</th>
            <th scope="col">Badge</th>
            <th scope="col">Score</th>
            <th scope="col">Flexible share</th>
            <th scope="col">Monthly footprint</th>
            <th scope="col">Receipts</th>
          </tr>
        </thead>
        <tbody>
          {ordered.map((row, i) => (
            <Row key={row.site_id} row={row} place={row.score === null ? null : i + 1} />
          ))}
        </tbody>
      </table>
    </div>
  )
}
