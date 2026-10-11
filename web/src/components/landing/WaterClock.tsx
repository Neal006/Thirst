import { useMemo, useState, type PointerEvent } from 'react'
import type { PlanResponse } from '../../api/types'
import { formatClock, formatDay } from '../../lib/format'
import {
  arcPath,
  cheapestStart,
  co2PerKwh,
  istDayFraction,
  istHour,
  polar,
  ringSegment,
  waterPerKwh,
  WINDOW_HOURS,
} from '../../lib/landing'
import { TagChip } from '../TagChip'

const S = 400
const C = S / 2
const R_CO2 = [70, 82] as const
const R_WATER = [90, 150] as const
const R_RUN = 158
const GAP = 0.004

const turnOf = (hour: number) => hour / 24

/**
 * The next 24 hours as a 24-hour clock face. Each wedge is one hour: its length is water per kWh,
 * the inner ring is CO2 per kWh, the yellow arc is the best window to run. The hand is now.
 */
export function WaterClock({ response }: { response: PlanResponse }) {
  const [active, setActive] = useState<number | null>(null)
  const day = useMemo(() => response.series.slice(0, 24), [response.series])

  const geo = useMemo(() => {
    const water = day.map(waterPerKwh)
    const co2 = day.map(co2PerKwh)
    const wLo = Math.min(...water)
    const wHi = Math.max(...water)
    const cLo = Math.min(...co2)
    const cHi = Math.max(...co2)
    const norm = (v: number, lo: number, hi: number) => (hi > lo ? (v - lo) / (hi - lo) : 0.5)
    const wedges = day.map((row, i) => {
      const h = istHour(row.slot)
      const t0 = turnOf(h) + GAP
      const t1 = turnOf(h + 1) - GAP
      const len = R_WATER[0] + (0.18 + 0.82 * norm(water[i], wLo, wHi)) * (R_WATER[1] - R_WATER[0])
      return {
        i,
        h,
        water: ringSegment(C, C, R_WATER[0], len, t0, t1),
        co2: ringSegment(C, C, R_CO2[0], R_CO2[1], t0, t1),
        co2Shade: 0.12 + 0.78 * norm(co2[i], cLo, cHi),
      }
    })
    const best = cheapestStart(day, waterPerKwh)
    const bestHour = best >= 0 ? istHour(day[best].slot) : -1
    return { wedges, best, bestHour }
  }, [day])

  const nowTurn = istDayFraction(response.submit_ts)
  const focus = active ?? Math.max(0, geo.best)
  const row = day[focus]
  const { tags } = response

  const onMove = (event: PointerEvent<SVGSVGElement>) => {
    const box = event.currentTarget.getBoundingClientRect()
    if (box.width === 0) return
    const x = ((event.clientX - box.left) / box.width) * S - C
    const y = ((event.clientY - box.top) / box.height) * S - C
    const r = Math.hypot(x, y)
    if (r < R_CO2[0] - 10) return
    const turn = (Math.atan2(y, x) + Math.PI / 2 + 2 * Math.PI) % (2 * Math.PI) / (2 * Math.PI)
    const hour = Math.floor(turn * 24) % 24
    const index = day.findIndex((d) => istHour(d.slot) === hour)
    if (index >= 0) setActive(index)
  }

  const hand = nowTurn >= 0 ? polar(C, C, R_RUN + 6, nowTurn) : null
  const handBase = nowTurn >= 0 ? polar(C, C, R_CO2[0] - 6, nowTurn) : null

  return (
    <div className="clock">
      <svg
        className="clock-svg"
        viewBox={`0 0 ${S} ${S}`}
        onPointerMove={onMove}
        onPointerLeave={() => setActive(null)}
        aria-hidden="true"
        focusable="false"
      >
        {/* night half: 18:00 to 06:00 */}
        <path className="clock-night" d={ringSegment(C, C, R_CO2[0] - 4, R_RUN + 14, 0.75, 1)} />
        <path className="clock-night" d={ringSegment(C, C, R_CO2[0] - 4, R_RUN + 14, 0, 0.25)} />
        {Array.from({ length: 24 }, (_, h) => {
          const a = polar(C, C, R_RUN + 14, turnOf(h))
          const b = polar(C, C, R_RUN + (h % 6 === 0 ? 22 : 18), turnOf(h))
          return <line key={h} className={h % 6 === 0 ? 'clock-tick major' : 'clock-tick'} x1={a.x} y1={a.y} x2={b.x} y2={b.y} />
        })}
        {[0, 6, 12, 18].map((h) => {
          const p = polar(C, C, R_RUN + 33, turnOf(h))
          return (
            <text key={h} className="clock-hour" x={p.x} y={p.y} textAnchor="middle" dominantBaseline="central">
              {String(h).padStart(2, '0')}
            </text>
          )
        })}
        {geo.wedges.map((w) => (
          <g key={w.i} className={w.i === focus ? 'clock-wedge is-active' : 'clock-wedge'} style={{ '--i': w.i } as React.CSSProperties}>
            <path className="clock-water" d={w.water} />
            <path className="clock-co2" d={w.co2} style={{ opacity: w.co2Shade }} />
          </g>
        ))}
        {geo.bestHour >= 0 ? (
          <g className="clock-run">
            <path d={arcPath(C, C, R_RUN, turnOf(geo.bestHour), turnOf(geo.bestHour + WINDOW_HOURS))} />
            {(() => {
              const p = polar(C, C, R_RUN, turnOf(geo.bestHour + WINDOW_HOURS / 2))
              return (
                <g transform={`translate(${p.x} ${p.y})`}>
                  <rect x={-17} y={-9} width={34} height={18} />
                  <text textAnchor="middle" dominantBaseline="central">RUN</text>
                </g>
              )
            })()}
          </g>
        ) : null}
        {hand && handBase ? (
          <g className="clock-hand">
            <line x1={handBase.x} y1={handBase.y} x2={hand.x} y2={hand.y} />
            <circle cx={hand.x} cy={hand.y} r={4} />
          </g>
        ) : null}
      </svg>
      {row ? (
        <div className="clock-face" aria-live="polite">
          <span className="clock-label">{active === null ? 'Cleanest hour' : formatDay(row.slot)}</span>
          <span className="clock-time">{formatClock(row.slot)}</span>
          <span className="clock-read">
            <span className="range-value">{waterPerKwh(row).toFixed(2)} L</span> <TagChip tag={tags.water} />
          </span>
          <span className="clock-read clock-read-co2">
            <span className="range-value">{co2PerKwh(row).toFixed(2)} kg</span> <TagChip tag={tags.co2} />
          </span>
          <span className="clock-unit">per kWh</span>
        </div>
      ) : null}
      <label className="visually-hidden">
        Hour to read
        <input
          type="range"
          min={0}
          max={Math.max(0, day.length - 1)}
          step={1}
          value={focus}
          aria-valuetext={row ? `${formatDay(row.slot)} ${formatClock(row.slot)}` : undefined}
          onChange={(e) => setActive(Number(e.target.value))}
        />
      </label>
    </div>
  )
}
