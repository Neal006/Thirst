import type { SiteResponse } from '../api/types'
import { Range } from './Range'

const one = (value: number): string => (Number.isFinite(value) ? value.toFixed(1) : '--')

/** F10: A Behaviour, B Facility efficiency (never rated in v0), C Measurement and openness. */
export function ScoreBreakdown({ score }: { score: SiteResponse['score'] }) {
  const parts = score.C_parts
  const share = score.flex_share * 100
  return (
    <section className="card" aria-labelledby="score-heading">
      <h2 id="score-heading">Score</h2>
      {score.value === null ? (
        <p>No score yet: it needs at least one receipt with room to shift.</p>
      ) : (
        <p className="plan-sentence">
          Score <strong>{Math.round(score.value)}</strong>{' '}
          {score.provisional ? <span className="chip">Provisional</span> : null}
        </p>
      )}
      <ul className="stat-list">
        <li>
          <strong>A. Behaviour</strong> <span>{one(score.A)} of 50</span>
          <span className="stat-label">
            Share of energy in jobs that had room to shift:{' '}
            <Range range={[share, share]} unit="%" tag="modelled" />
          </span>
        </li>
        <li>
          <strong>B. Facility efficiency</strong> <span>Not rated</span>
          <span className="stat-label">Needs metered building data</span>
        </li>
        <li>
          <strong>C. Measurement and openness</strong> <span>{one(score.C)} of 20</span>
          <ul>
            <li>Measured share of energy: {one(parts.measured_share)} of 10</li>
            <li>Coverage you declared: {one(parts.coverage)} of 5</li>
            <li>Public site: {one(parts.public)} of 5</li>
          </ul>
        </li>
      </ul>
      <p className="muted">Provisional: building efficiency not rated yet</p>
    </section>
  )
}
