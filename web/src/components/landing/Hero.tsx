import { Link } from 'react-router-dom'
import type { CityRow, PlanResponse } from '../../api/types'
import type { Loadable } from '../../hooks/useLoad'
import { formatClock } from '../../lib/format'
import { bestVsWorstPct, co2PerKwh, stressWords, waterPerKwh } from '../../lib/landing'
import { TagChip } from '../TagChip'
import { WaterClock } from './WaterClock'

interface HeroProps {
  cities: readonly string[]
  cityRows?: readonly CityRow[]
  city: string
  onCity: (city: string) => void
  forecast: Loadable<PlanResponse>
  reload: () => void
}

function Meters({ response }: { response: PlanResponse }) {
  const day = response.series.slice(0, 24)
  const start = response.chosen.start
  const { tags } = response
  return (
    <dl className="meters">
      <div className="meter">
        <dt>Best start, 6 h job</dt>
        <dd>
          <span className="meter-num">{formatClock(start)}</span>
        </dd>
      </div>
      <div className="meter">
        <dt>Water, best vs worst hour</dt>
        <dd>
          <span className="meter-num">−{bestVsWorstPct(day, waterPerKwh)}%</span> <TagChip tag={tags.water} />
        </dd>
      </div>
      <div className="meter">
        <dt>CO₂, best vs worst hour</dt>
        <dd>
          <span className="meter-num">−{bestVsWorstPct(day, co2PerKwh)}%</span> <TagChip tag={tags.co2} />
        </dd>
      </div>
    </dl>
  )
}

export function Hero({ cities, cityRows, city, onCity, forecast, reload }: HeroProps) {
  const meta = cityRows?.find((c) => c.id === city)
  const live = forecast.status === 'ready' && forecast.data.tags.forecast === 'live'
  return (
    <section className="hero" aria-labelledby="hero-title">
      <div className="hero-copy">
        <h1 id="hero-title" className="hero-title hero-in" style={{ '--d': '60ms' } as React.CSSProperties}>
          Every GPU hour drinks water <em>twice</em>.
        </h1>
        <p className="hero-sub hero-in" style={{ '--d': '140ms' } as React.CSSProperties}>
          Thirst tells you <b>when</b> and <b>how fast</b> to run your GPU job so it uses less water
          and CO₂.
        </p>
        <div className="hero-actions hero-in" style={{ '--d': '220ms' } as React.CSSProperties}>
          <Link className="btn btn-primary btn-lg" to={`/plan?city=${encodeURIComponent(city)}`}>
            Plan a job <span className="btn-arrow" aria-hidden="true">→</span>
          </Link>
          <Link className="btn btn-ghost btn-lg" to="/cities">
            Compare cities
          </Link>
        </div>
        <div className="hero-in" style={{ '--d': '300ms' } as React.CSSProperties}>
          {forecast.status === 'ready' ? <Meters response={forecast.data} /> : <div className="meters meters-empty" aria-hidden="true" />}
        </div>
      </div>

      <figure className="clock-card hero-in" style={{ '--d': '120ms' } as React.CSSProperties} aria-labelledby="clock-title">
        <div className="clock-head">
          <h2 id="clock-title" className="clock-title">
            Next 24 h · {city}
          </h2>
          <span className={live ? 'live' : 'live live-off'}>{forecast.status === 'ready' ? (live ? 'live' : 'cached') : '…'}</span>
        </div>
        {forecast.status === 'loading' ? (
          <div className="clock clock-loading" role="status">
            <span className="visually-hidden">Loading the forecast for {city}…</span>
          </div>
        ) : null}
        {forecast.status === 'error' ? (
          <div className="banner banner-error" role="alert">
            <p>{forecast.message}</p>
            <button type="button" className="btn" onClick={reload}>
              Try again
            </button>
          </div>
        ) : null}
        {forecast.status === 'ready' ? <WaterClock key={city} response={forecast.data} /> : null}
        <div className="city-switch" role="group" aria-label="Pick a city">
          {cities.map((name) => (
            <button key={name} type="button" className="city-chip" aria-pressed={name === city} onClick={() => onCity(name)}>
              {name}
            </button>
          ))}
        </div>
        <figcaption className="clock-legend">
          <span>
            <i className="swatch swatch-grid" aria-hidden="true" /> water / kWh
          </span>
          <span>
            <i className="swatch swatch-co2" aria-hidden="true" /> CO₂ / kWh
          </span>
          <span>
            <i className="swatch swatch-run" aria-hidden="true" /> cleanest 3 h
          </span>
          {meta ? (
            <span className="clock-stress">
              water stress <b>{stressWords(meta.stress_category)}</b> <TagChip tag={meta.status} />
            </span>
          ) : null}
        </figcaption>
      </figure>
    </section>
  )
}
