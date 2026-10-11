import { Link } from 'react-router-dom'
import type { ParetoEntry, PlanResponse } from '../api/types'
import { formatClock, formatDay, pauseWindows } from '../lib/format'
import { personDaysRange } from '../lib/planView'
import { whyThisTime } from '../lib/planViews'
import { Range } from './Range'
import { TagChip } from './TagChip'

interface ResultCardProps {
  response: PlanResponse
  /** The Pareto entry the slider has selected. */
  entry: ParetoEntry
}

function SavingLine({ response, entry }: ResultCardProps) {
  const { water_pct, co2_pct } = entry.savings_ranges
  const best = Math.max(water_pct[1], co2_pct[1])
  const worst = Math.min(water_pct[0], co2_pct[0])
  const water = <Range range={water_pct} unit="%" tag={response.tags.water} />
  const co2 = <Range range={co2_pct} unit="%" tag={response.tags.co2} />
  if (!(best > 0)) {
    return <p>Compared with starting now, this plan does not reduce your footprint.</p>
  }
  if (worst < 0) {
    return (
      <p>
        Compared with starting now, the effect is uncertain (a minus sign means more use):
        water {water} and CO₂ {co2}.
      </p>
    )
  }
  return (
    <p>
      Uses about {water} less water and {co2} less CO₂ than starting now.
    </p>
  )
}

function freshness(response: PlanResponse): string {
  const age = response.forecast_age_hours
  if (typeof age !== 'number' || !Number.isFinite(age) || age < 1) return 'Forecast updated within the hour.'
  return `Forecast updated ${Math.round(age)} ${Math.round(age) === 1 ? 'hour' : 'hours'} ago.`
}

/** F5: the answer in one card. Every number is a range with a tag. */
export function ResultCard({ response, entry }: ResultCardProps) {
  const pauses = pauseWindows(entry.schedule)
  const startsNow = Date.parse(entry.start) === Date.parse(response.submit_ts)
  const [daysLo, daysHi] = personDaysRange(response, entry)
  const why = whyThisTime(response, entry)
  return (
    <section className="card result-card" aria-labelledby="plan-heading">
      <h2 id="plan-heading">Your plan</h2>
      <p className="plan-sentence">
        {startsNow ? (
          <>Start now</>
        ) : (
          <>
            Start at <strong>{formatClock(entry.start)}</strong> ({formatDay(entry.start)})
          </>
        )}
        , GPU at <strong data-kind="setting">{entry.level_summary}</strong>
        {pauses.map((p) => (
          <span key={p.from}>
            , pause <strong>{p.from} to {p.to}</strong>
          </span>
        ))}
        , done by <strong>{formatClock(entry.finish)}</strong>
        {formatDay(entry.finish) !== formatDay(entry.start) ? <> ({formatDay(entry.finish)})</> : null}.
      </p>
      {why ? <p className="why-line">{why}</p> : null}
      <SavingLine response={response} entry={entry} />
      {Number.isFinite(daysLo) && Number.isFinite(daysHi) ? (
        <p>
          That water would cover ≈{' '}
          <Range range={[daysLo, daysHi]} unit="days" tag={response.tags.water} /> of one person's daily use in the city.
        </p>
      ) : null}
      {response.notes.includes('no_room') ? (
        <p>Little room to shift before your deadline, so starting now is fine.</p>
      ) : null}
      <p className="card-foot muted">
        <span>
          {freshness(response)}
          {response.tags.tau === 'placeholder' ? <> Power factors are estimates <TagChip tag="placeholder" /></> : null}
        </span>
        <Link to="/assumptions">How do we know?</Link>
      </p>
    </section>
  )
}
