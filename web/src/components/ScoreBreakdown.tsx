import type { SiteResponse } from '../api/types'
import type { BadgeStep } from '../lib/badges'
import { nextBadge } from '../lib/badges'
import { Range } from './Range'
import { MeterBar, ScoreRing } from './ScoreRing'

const one = (value: number): string => (Number.isFinite(value) ? value.toFixed(1) : '--')

interface ScoreBreakdownProps {
  score: SiteResponse['score']
  /** Badge thresholds from the assumptions; without them the "next badge" line is left out. */
  steps?: readonly BadgeStep[]
}

function Ladder({ score, steps }: { score: number; steps: readonly BadgeStep[] }) {
  const next = nextBadge(score, steps)
  return (
    <div className="ladder">
      <div className="ladder-track" aria-hidden="true">
        <span className="ladder-fill" style={{ width: `${Math.max(0, Math.min(100, score))}%` }} />
        {steps.map((s) => (
          <span key={s.name} className={`ladder-step step-${s.name}`} style={{ left: `${s.at}%` }}>
            <i />
            <b>{s.name}</b>
          </span>
        ))}
      </div>
      <p className="ladder-text">
        {next ? (
          <>
            <strong>{next.gap}</strong> points to <span className="cap-word">{next.name}</span>
          </>
        ) : (
          <>Top badge reached</>
        )}
      </p>
    </div>
  )
}

/** F10: A Behaviour, B Facility efficiency (never rated in v0), C Measurement and openness. */
export function ScoreBreakdown({ score, steps = [] }: ScoreBreakdownProps) {
  const parts = score.C_parts
  const share = score.flex_share * 100
  return (
    <section className="card score-card" aria-labelledby="score-heading">
      <h2 id="score-heading">Score</h2>
      {score.value === null ? (
        <p>No score yet: it needs at least one receipt with room to shift.</p>
      ) : (
        <div className="score-hero">
          <ScoreRing score={score.value} size="lg" lead />
          <div className="score-hero-body">
            <p className="plan-sentence">
              Score <strong>{Math.round(score.value)}</strong>{' '}
              {score.provisional ? <span className="chip">Provisional</span> : null}
            </p>
            {steps.length > 0 ? <Ladder score={score.value} steps={steps} /> : null}
          </div>
        </div>
      )}
      <ul className="stat-list parts">
        <li>
          <strong>A. Behaviour</strong> <span>{one(score.A)} of 50</span>
          <MeterBar value={score.A} max={50} />
          <span className="stat-label">
            Share of energy in jobs that had room to shift:{' '}
            <Range range={[share, share]} unit="%" tag="modelled" />
          </span>
        </li>
        <li>
          <strong>B. Facility efficiency</strong> <span>Not rated</span>
          <MeterBar value={0} max={30} />
          <span className="stat-label">Needs metered building data</span>
        </li>
        <li>
          <strong>C. Measurement and openness</strong> <span>{one(score.C)} of 20</span>
          <MeterBar value={score.C} max={20} tone="ink" />
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
