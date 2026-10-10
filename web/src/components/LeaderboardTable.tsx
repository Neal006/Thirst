import { Link } from 'react-router-dom'
import type { LeaderboardRow } from '../api/types'
import { ratedFirst } from '../lib/leaderboardView'
import { Amount } from './Amount'
import { Badge } from './Badge'
import { Range } from './Range'
import { SimulatedChip } from './SimulatedChip'

function Footprint({ row }: { row: LeaderboardRow }) {
  const m = row.monthly_absolute
  return (
    <ul className="stat-list">
      <li><Amount value={m.kwh} unit="kWh" tag="modelled" /></li>
      <li><Amount value={m.litres} unit="L" tag="modelled" /></li>
      <li><Amount value={m.kg_co2} unit="kg" tag="modelled" /></li>
    </ul>
  )
}

function Row({ row }: { row: LeaderboardRow }) {
  const share = row.flex_share * 100
  return (
    <tr>
      <td data-label="Rank">{row.rank ?? '-'}</td>
      <td data-label="Site">
        <Link to={`/sites/${encodeURIComponent(row.site_id)}`}>{row.name}</Link>{' '}
        {row.simulated ? <SimulatedChip /> : null}
      </td>
      <td data-label="Badge"><Badge badge={row.badge} /></td>
      <td data-label="Score">
        {row.score === null ? (
          'Not rated yet'
        ) : (
          <>
            <strong>{Math.round(row.score)}</strong>
            {row.provisional ? <> <span className="chip">Provisional</span></> : null}
          </>
        )}
      </td>
      <td data-label="Flexible share"><Range range={[share, share]} unit="%" tag="modelled" /></td>
      <td data-label="Monthly footprint"><Footprint row={row} /></td>
      <td data-label="Receipts">{row.receipts}</td>
    </tr>
  )
}

export function LeaderboardTable({ rows }: { rows: readonly LeaderboardRow[] }) {
  return (
    <table className="data-table cards-on-phone">
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
        {ratedFirst(rows).map((row) => (
          <Row key={row.site_id} row={row} />
        ))}
      </tbody>
    </table>
  )
}
