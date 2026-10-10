import { useState } from 'react'
import type { AssumptionRow } from '../../api/types'
import { capLevels } from '../../lib/landing'
import { TagChip } from '../TagChip'

const TRACK = 1.3 // the bars show 0 to 130% of the full-power job

function signed(n: number): string {
  if (n === 0) return '±0%'
  return `${n > 0 ? '+' : '−'}${Math.abs(n)}%`
}

function Fan({ cx, cy, speed }: { cx: number; cy: number; speed: number }) {
  return (
    <g className="fan" style={{ '--spin': `${(0.5 / speed ** 2).toFixed(2)}s` } as React.CSSProperties}>
      <circle cx={cx} cy={cy} r={22} className="fan-ring" />
      <g className="fan-blades" style={{ transformOrigin: `${cx}px ${cy}px` }}>
        {[0, 72, 144, 216, 288].map((a) => (
          <path key={a} d={`M${cx} ${cy} q8 -6 4 -18 q-8 2 -4 18z`} transform={`rotate(${a} ${cx} ${cy})`} />
        ))}
      </g>
      <circle cx={cx} cy={cy} r={4} className="fan-hub" />
    </g>
  )
}

export function PowerCap({ factors }: { factors: readonly AssumptionRow[] | undefined }) {
  const levels = capLevels(factors)
  // until the person picks, show the deepest cap the assumptions know about
  const [picked, setPicked] = useState<number | null>(null)
  const level = levels.find((l) => l.pct === picked) ?? levels[levels.length - 1]
  const pct = level.pct
  const time = 1 / level.tau
  const timeDelta = Math.round((time - 1) * 100)
  const energyDelta = Math.round((level.eps - 1) * 100)
  const speed = level.pct / 100

  return (
    <div className="cap">
      <div className="cap-gpu">
        <svg viewBox="0 0 260 150" aria-hidden="true" focusable="false">
          {[0, 1, 2].map((i) => (
            <path
              key={i}
              className="cap-heat"
              d={`M${90 + i * 40} 34 c-8 -8 8 -12 0 -22`}
              style={{ opacity: 0.25 + 0.75 * (speed - 0.6) / 0.4, animationDelay: `${i * 0.4}s` }}
            />
          ))}
          <rect x="20" y="44" width="220" height="86" rx="6" className="cap-card" />
          <rect x="20" y="130" width="160" height="10" className="cap-pins" />
          <Fan cx={86} cy={87} speed={speed} />
          <Fan cx={154} cy={87} speed={speed} />
          <rect x="196" y="58" width="30" height="58" rx="3" className="cap-meter" />
          <rect
            x="199"
            y={61 + 52 * (1 - speed)}
            width="24"
            height={52 * speed}
            className="cap-meter-fill"
          />
        </svg>
        <div className="seg seg-tight" role="group" aria-label="GPU power limit">
          {levels.map((l) => (
            <button key={l.pct} type="button" className="seg-btn" aria-pressed={l.pct === pct} onClick={() => setPicked(l.pct)}>
              <span data-kind="setting">{l.pct}%</span>
            </button>
          ))}
        </div>
      </div>
      <dl className="cap-bars">
        <div className="cap-row">
          <dt>Time to finish</dt>
          <dd>
            <span className="cap-track">
              <span className="cap-fill cap-fill-time" style={{ width: `${(time / TRACK) * 100}%` }} />
              <span className="cap-base" style={{ left: `${100 / TRACK}%` }} />
            </span>
            <span className="cap-num">
              <span className="range-value">{signed(timeDelta)}</span> <TagChip tag={level.status} factor={level.factor?.replace('eps', 'tau')} />
            </span>
          </dd>
        </div>
        <div className="cap-row">
          <dt>Energy for the job</dt>
          <dd>
            <span className="cap-track">
              <span className="cap-fill cap-fill-energy" style={{ width: `${(level.eps / TRACK) * 100}%` }} />
              <span className="cap-base" style={{ left: `${100 / TRACK}%` }} />
            </span>
            <span className="cap-num cap-num-big">
              <span className="range-value">{signed(energyDelta)}</span> <TagChip tag={level.status} factor={level.factor} />
            </span>
          </dd>
        </div>
        <p className="cap-note">Less energy means less water and less CO₂. A real cut, not a shift.</p>
      </dl>
    </div>
  )
}
