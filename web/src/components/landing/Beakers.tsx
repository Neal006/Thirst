import { useState, type ReactNode } from 'react'
import type { PlanEntry, PlanResponse } from '../../api/types'
import { useCityForecast } from '../../hooks/useCityForecast'
import { formatClock } from '../../lib/format'
import type { SampleCooling } from '../../lib/landing'
import { Range } from '../Range'
import { TagChip } from '../TagChip'

const COOLING: { id: SampleCooling; label: string }[] = [
  { id: 'room_ac', label: 'Lab · room AC' },
  { id: 'evaporative', label: 'Data centre · cooling tower' },
]

const H = 220
const W = 120
const TOP = 14

function litres(entry: PlanEntry, i: 0 | 1 | 2): { site: number; grid: number } {
  return { site: entry.totals.D_l[i] ?? 0, grid: entry.totals.I_l[i] ?? 0 }
}

function Beaker({ entry, max, name, sub, tags }: { entry: PlanEntry; max: number; name: string; sub: ReactNode; tags: PlanResponse['tags'] }) {
  const { site, grid } = litres(entry, 1)
  const scale = max > 0 ? (H - TOP) / max : 0
  const gridH = grid * scale
  const siteH = site * scale
  const lo = litres(entry, 0)
  const hi = litres(entry, 2)
  const ticks = [0.25, 0.5, 0.75, 1]
  return (
    <div className="beaker">
      <svg viewBox={`0 0 ${W + 30} ${H + 8}`} aria-hidden="true" focusable="false">
        <defs>
          <pattern id={`hatch-${name.replace(/\W/g, '')}`} width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
            <rect width="6" height="6" className="beaker-site-bg" />
            <line x1="0" y1="0" x2="0" y2="6" className="beaker-site-line" />
          </pattern>
        </defs>
        <rect className="beaker-grid" x={4} y={H - gridH} width={W - 8} height={gridH} style={{ '--h': `${gridH}px` } as React.CSSProperties} />
        {siteH > 0.5 ? (
          <rect className="beaker-site" x={4} y={H - gridH - siteH} width={W - 8} height={siteH} fill={`url(#hatch-${name.replace(/\W/g, '')})`} />
        ) : null}
        {ticks.map((t) => {
          const y = H - t * (H - TOP)
          return <line key={t} className="beaker-tick" x1={W} x2={W + 10} y1={y} y2={y} />
        })}
        <path className="beaker-glass" d={`M2 ${TOP - 8} V${H} Q2 ${H + 4} 8 ${H + 4} H${W - 8} Q${W - 2} ${H + 4} ${W - 2} ${H} V${TOP - 8}`} />
      </svg>
      <p className="beaker-name">{name}</p>
      <p className="beaker-sub">{sub}</p>
      <p className="beaker-val">
        <Range range={[lo.site + lo.grid, hi.site + hi.grid]} unit="L" tag={tags.water} label="water" />
      </p>
      <p className="beaker-val beaker-val-co2">
        <Range range={[entry.totals.C_kg[0], entry.totals.C_kg[2]]} unit="kg CO₂" tag={tags.co2} label="carbon" />
      </p>
    </div>
  )
}

/** The same job twice: start now at full power vs the Thirst plan, water split by where it goes. */
export function Beakers({ city }: { city: string }) {
  const [cooling, setCooling] = useState<SampleCooling>('room_ac')
  const { state, reload } = useCityForecast(city, cooling)

  return (
    <div className="beakers">
      <div className="seg" role="group" aria-label="Where the GPUs live">
        {COOLING.map((c) => (
          <button key={c.id} type="button" className="seg-btn" aria-pressed={cooling === c.id} onClick={() => setCooling(c.id)}>
            {c.label}
          </button>
        ))}
      </div>
      {state.status === 'loading' ? (
        <div className="beakers-stage beakers-loading" role="status">
          <span className="visually-hidden">Planning the sample job…</span>
          <span className="skeleton" aria-hidden="true" />
          <span className="skeleton" aria-hidden="true" />
        </div>
      ) : null}
      {state.status === 'error' ? (
        <div className="banner banner-error" role="alert">
          <p>{state.message}</p>
          <button type="button" className="btn" onClick={reload}>
            Try again
          </button>
        </div>
      ) : null}
      {state.status === 'ready' ? <Stage response={state.data} /> : null}
    </div>
  )
}

function Stage({ response }: { response: PlanResponse }) {
  const { base, chosen, tags } = response
  const total = (e: PlanEntry) => e.totals.D_l[1] + e.totals.I_l[1]
  const max = Math.max(total(base), total(chosen))
  const noSite = base.totals.D_l[1] < 0.01
  return (
    <figure className="beakers-stage">
      <div className="beakers-row">
        <Beaker entry={base} max={max} name="Start now" sub="full power" tags={tags} />
        <div className="beakers-delta">
          <span className="delta-arrow" aria-hidden="true">
            →
          </span>
          <span className="delta-num">
            <Range range={chosen.savings_ranges.water_pct} unit="%" tag={tags.water} label="less water" />
          </span>
          <span className="delta-cap">less water</span>
        </div>
        <Beaker
          entry={chosen}
          max={max}
          name={`Start ${formatClock(chosen.start)}`}
          sub={
            <>
              GPU <span data-kind="setting">{chosen.level_summary}</span> · done {formatClock(chosen.finish)}
            </>
          }
          tags={tags}
        />
      </div>
      <p className="beakers-job">
        Sample job: 2 × RTX 4090 · 6 h · deadline {formatClock(response.inputs.deadline)}
      </p>
      <figcaption className="beakers-legend">
        <span>
          <i className="swatch swatch-grid" aria-hidden="true" /> at the power plant
        </span>
        <span>
          <i className="swatch swatch-site" aria-hidden="true" /> at the building
        </span>
        <span className="muted">
          {noSite ? 'Room AC: the water leaves at the power plant.' : 'Cooling tower: it drinks twice.'}{' '}
          <TagChip tag={tags.water} />
        </span>
      </figcaption>
    </figure>
  )
}
