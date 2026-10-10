import { Link } from 'react-router-dom'
import type { ParetoEntry, PlanResponse } from '../api/types'
import { formatClock, formatDay, pauseWindows } from '../lib/format'
import { personDaysRange } from '../lib/planView'
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
        stress-weighted water {water} and CO₂ {co2}.
      </p>
    )
  }
  return (
    <p>
      Saves about {water} stress-weighted water and {co2} CO₂ compared with starting now.
    </p>
  )
}

/** F5: the answer in one card. Every number is a range with a tag. */
export function ResultCard({ response, entry }: ResultCardProps) {
  const pauses = pauseWindows(entry.schedule)
  const startsNow = Date.parse(entry.start) === Date.parse(response.submit_ts)
  const [daysLo, daysHi] = personDaysRange(response, entry)
  return (
    <section className="card" aria-labelledby="plan-heading">
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
        , done by <strong>{formatClock(entry.finish)}</strong>.
      </p>
      <SavingLine response={response} entry={entry} />
      {Number.isFinite(daysLo) && Number.isFinite(daysHi) ? (
        <p>
          The job's water is ≈{' '}
          <Range range={[daysLo, daysHi]} unit="person-days" tag={response.tags.water} /> of city water.
        </p>
      ) : null}
      <p className="muted">
        Energy comes from your GPU type <TagChip tag={response.tags.energy} />. After a real run,
        your receipt shows measured energy.
      </p>
      {response.tags.tau === 'placeholder' ? (
        <p className="muted">
          The power-cap factors are placeholders <TagChip tag="placeholder" /> until we measure
          your GPU.
        </p>
      ) : null}
      {response.notes.includes('no_room') ? (
        <p>Little room to shift before your deadline; starting now is fine.</p>
      ) : null}
      <p>
        <Link to="/assumptions">How do we know?</Link>
      </p>
    </section>
  )
}
