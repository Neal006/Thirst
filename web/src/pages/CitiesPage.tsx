import { useState } from 'react'
import { Link } from 'react-router-dom'
import type { PlanResponse } from '../api/types'
import { Amount } from '../components/Amount'
import { Range } from '../components/Range'
import { TagChip } from '../components/TagChip'
import { useAssumptions } from '../hooks/useAssumptions'
import { useCityForecast } from '../hooks/useCityForecast'
import { usePageTitle } from '../hooks/usePageTitle'
import { formatClock, formatDay } from '../lib/format'
import { FALLBACK_CITIES, stressWords, type SampleCooling } from '../lib/landing'
import { hourCells } from '../lib/planViews'

const COOLINGS: { id: SampleCooling; label: string }[] = [
  { id: 'room_ac', label: 'Room AC' },
  { id: 'evaporative', label: 'Cooling tower' },
]

function Strip({ response }: { response: PlanResponse }) {
  const cells = hourCells(response, response.chosen)
  return (
    <div className="city-strip" aria-hidden="true">
      {cells.map((c) => (
        <i key={c.slot} className={`lv-${c.level}${c.state === 'run' ? ' is-run' : ''}`} />
      ))}
    </div>
  )
}

interface CityCardProps {
  city: string
  cooling: SampleCooling
  stress?: string
  stressTag?: Parameters<typeof TagChip>[0]['tag']
  index: number
}

function CityCard({ city, cooling, stress, stressTag, index }: CityCardProps) {
  const { state, reload } = useCityForecast(city, cooling)
  const style = { '--i': index } as React.CSSProperties
  if (state.status !== 'ready') {
    return (
      <li className="card city-card" style={style}>
        <h2>{city}</h2>
        {state.status === 'loading' ? <div className="skeleton" role="status"><span className="visually-hidden">Loading {city}…</span></div> : null}
        {state.status === 'error' ? (
          <p>
            Could not load this city.{' '}
            <button type="button" className="btn btn-ghost" onClick={reload}>
              Try again
            </button>
          </p>
        ) : null}
      </li>
    )
  }
  const r = state.data
  const plan = r.chosen
  return (
    <li className="card city-card" style={style}>
      <div className="city-card-head">
        <h2>{city}</h2>
        {stress && stressTag ? (
          <span className="chip">
            Water stress: {stressWords(stress)} <TagChip tag={stressTag} />
          </span>
        ) : null}
      </div>
      <p className="city-start">
        <span className="stat-label">Best start</span>
        <strong>{formatClock(plan.start)}</strong> <span className="muted">{formatDay(plan.start)}</span>
      </p>
      <Strip response={r} />
      <ul className="city-facts">
        <li>
          <span className="stat-label">Water for the job</span>
          <Amount value={plan.point.W_l} unit="L" tag={r.tags.water} />
        </li>
        <li>
          <span className="stat-label">Saving vs now</span>
          <Range range={plan.savings_ranges.water_pct} unit="%" tag={r.tags.water} />
        </li>
      </ul>
      <Link className="btn" to={`/plan?city=${encodeURIComponent(city)}&cooling=${cooling}`}>
        Plan here <span className="btn-arrow" aria-hidden="true">→</span>
      </Link>
    </li>
  )
}

/** Six cities side by side for the same sample job, so a lab can see where and when is cleanest. */
export function CitiesPage() {
  usePageTitle('Cities')
  const [cooling, setCooling] = useState<SampleCooling>('room_ac')
  const { state } = useAssumptions()
  const rows = state.status === 'ready' ? state.data.cities : []
  const cities = rows.length ? rows.map((c) => c.id) : [...FALLBACK_CITIES]
  return (
    <div className="cities-page">
      <div className="page-head">
        <div>
          <h1>Compare cities</h1>
          <p className="lede">The same job in every city: 2 × RTX 4090 for 6 hours, done by 9 AM tomorrow.</p>
        </div>
        <div className="tab-group" role="group" aria-label="Cooling">
          {COOLINGS.map((c) => (
            <button key={c.id} type="button" className="btn" aria-pressed={cooling === c.id} onClick={() => setCooling(c.id)}>
              {c.label}
            </button>
          ))}
        </div>
      </div>
      <ul className="city-grid">
        {cities.map((city, i) => {
          const meta = rows.find((c) => c.id === city)
          return (
            <CityCard
              key={`${city}-${cooling}`}
              city={city}
              cooling={cooling}
              stress={meta?.stress_category}
              stressTag={meta?.status}
              index={i}
            />
          )
        })}
      </ul>
      <p className="muted city-key">
        Each strip is the next 48 hours. Darker means more water per kWh. The orange marks show when the job runs.
      </p>
    </div>
  )
}
