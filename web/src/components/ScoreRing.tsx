const R = 34
const RING = 2 * Math.PI * R

interface ScoreRingProps {
  score: number | null
  /** "sm" for table rows, "lg" for the site page. */
  size?: 'sm' | 'md' | 'lg'
  /** Ink instead of cobalt, for the top spot. */
  lead?: boolean
}

/** A 0 to 100 score as a ring that fills up. The number in the middle is the score. */
export function ScoreRing({ score, size = 'md', lead = false }: ScoreRingProps) {
  const share = score === null ? 0 : Math.max(0, Math.min(1, score / 100))
  return (
    <div className={`ring ring-${size}${lead ? ' ring-lead' : ''}`}>
      <svg viewBox="0 0 80 80" aria-hidden="true" focusable="false">
        <circle className="ring-track" cx="40" cy="40" r={R} />
        <circle
          className="ring-fill"
          cx="40"
          cy="40"
          r={R}
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

/** A horizontal meter in ten segments; decorative, the number next to it says the value. */
export function MeterBar({ value, max, tone = 'cobalt' }: { value: number; max: number; tone?: 'cobalt' | 'ink' | 'signal' }) {
  const share = max > 0 && Number.isFinite(value) ? Math.max(0, Math.min(1, value / max)) : 0
  return (
    <span className={`meter-bar meter-bar-${tone}`} aria-hidden="true">
      <span className="meter-bar-fill" style={{ width: `${share * 100}%` }} />
    </span>
  )
}
