import { useId, useMemo, useState, type KeyboardEvent } from 'react'
import type { ParetoEntry, PlanResponse } from '../api/types'
import { formatClock, formatDay, formatNumber } from '../lib/format'
import { dayRows, hourCells, type HourCell } from '../lib/planViews'
import { PlanChart } from './PlanChart'
import { TagChip } from './TagChip'

interface ViewProps {
  response: PlanResponse
  entry: ParetoEntry
}

const VIEWS = [
  { id: 'timetable', label: 'Timetable' },
  { id: 'hourly', label: 'Hourly' },
  { id: 'calendar', label: 'Calendar' },
  { id: 'chart', label: 'Chart' },
] as const

type ViewId = (typeof VIEWS)[number]['id']
const STORE_KEY = 'thirst.planView'

function readView(): ViewId {
  try {
    const saved = window.localStorage.getItem(STORE_KEY)
    return VIEWS.some((v) => v.id === saved) ? (saved as ViewId) : 'timetable'
  } catch {
    return 'timetable'
  }
}

function saveView(view: ViewId) {
  try {
    window.localStorage.setItem(STORE_KEY, view)
  } catch {
    // storage is a convenience; the page works without it
  }
}

const LEVEL_WORDS = ['lowest', 'low', 'medium', 'high', 'highest'] as const

function cellLabel(cell: HourCell): string {
  const parts = [`${formatDay(cell.slot)} ${formatClock(cell.slot)}`, `water ${LEVEL_WORDS[cell.level]}`]
  if (cell.state === 'run') parts.push('job runs')
  if (cell.state === 'pause') parts.push('job paused')
  if (cell.inCleanest) parts.push('cleanest hours')
  if (cell.isDeadline) parts.push('deadline')
  return parts.join(', ')
}

function Legend() {
  return (
    <ul className="view-legend" aria-label="Legend">
      <li>
        <span className="lv-scale" aria-hidden="true">
          {LEVEL_WORDS.map((w, i) => (
            <i key={w} className={`lv-${i}`} />
          ))}
        </span>
        Less water to more water
      </li>
      <li>
        <i className="key key-run" aria-hidden="true" /> Job runs
      </li>
      <li>
        <i className="key key-clean" aria-hidden="true" /> Cleanest 3 hours
      </li>
      <li>
        <i className="key key-deadline" aria-hidden="true" /> Deadline
      </li>
    </ul>
  )
}

function Caption({ response }: { response: PlanResponse }) {
  return (
    <figcaption>
      Water and CO₂ per kWh from the weather forecast <TagChip tag={response.tags.water} />{' '}
      <TagChip tag={response.tags.co2} />
    </figcaption>
  )
}

function Timetable({ response, entry }: ViewProps) {
  const rows = useMemo(() => dayRows(hourCells(response, entry)), [response, entry])
  return (
    <figure className="view-figure">
      <Legend />
      <div className="table-scroll">
        <table className="timetable">
          <caption className="visually-hidden">Timetable of the next 48 hours, by hour</caption>
          <thead>
            <tr>
              <th scope="col">Day</th>
              {Array.from({ length: 24 }, (_, h) => (
                <th key={h} scope="col" className={h % 3 === 0 ? '' : 'tt-minor'}>
                  {String(h).padStart(2, '0')}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.day}>
                <th scope="row">{row.day}</th>
                {row.cells.map((cell, h) =>
                  cell ? (
                    <td
                      key={h}
                      className={[
                        'tt-cell',
                        `lv-${cell.level}`,
                        cell.state === 'run' ? 'is-run' : '',
                        cell.state === 'pause' ? 'is-pause' : '',
                        cell.inCleanest ? 'is-clean' : '',
                        cell.isDeadline ? 'is-deadline' : '',
                        cell.afterDeadline ? 'is-after' : '',
                      ].join(' ')}
                      title={cellLabel(cell)}
                    >
                      <span className="visually-hidden">{cellLabel(cell)}</span>
                    </td>
                  ) : (
                    <td key={h} className="tt-cell tt-empty" />
                  ),
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <Caption response={response} />
    </figure>
  )
}

function Hourly({ response, entry }: ViewProps) {
  const cells = useMemo(() => hourCells(response, entry), [response, entry])
  const maxWater = Math.max(...cells.map((c) => c.water), 0.0001)
  const [showAll, setShowAll] = useState(false)
  const visible = showAll ? cells : cells.slice(0, 24)
  return (
    <figure className="view-figure">
      <div className="table-scroll">
        <table className="data-table hourly">
          <caption className="visually-hidden">Hour by hour forecast</caption>
          <thead>
            <tr>
              <th scope="col">Time</th>
              <th scope="col">Water (litres per kWh)</th>
              <th scope="col">CO₂ (kg per kWh)</th>
              <th scope="col">Plan</th>
            </tr>
          </thead>
          <tbody>
            {visible.map((cell, i) => {
              const day = formatDay(cell.slot)
              const newDay = i === 0 || formatDay(visible[i - 1].slot) !== day
              return (
                <tr key={cell.slot} className={cell.state === 'run' ? 'is-target' : undefined}>
                  <th scope="row">
                    {newDay ? <span className="hr-day">{day}</span> : null}
                    {formatClock(cell.slot)}
                  </th>
                  <td>
                    <span className="hr-meter" aria-hidden="true">
                      <span className={`meter-fill lv-${cell.level}`} style={{ width: `${(cell.water / maxWater) * 100}%` }} />
                    </span>
                    {formatNumber(cell.water)}
                  </td>
                  <td>{formatNumber(cell.co2)}</td>
                  <td>
                    {cell.state === 'run' ? <span className="pill pill-run">Runs</span> : null}
                    {cell.state === 'pause' ? <span className="pill">Paused</span> : null}
                    {cell.inCleanest ? <span className="pill pill-clean">Cleanest</span> : null}
                    {cell.isDeadline ? <span className="pill pill-deadline">Deadline</span> : null}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      {cells.length > 24 ? (
        <button type="button" className="btn btn-ghost" onClick={() => setShowAll((v) => !v)}>
          {showAll ? 'Show the first 24 hours' : `Show all ${cells.length} hours`}
        </button>
      ) : null}
      <Caption response={response} />
    </figure>
  )
}

function Calendar({ response, entry }: ViewProps) {
  const rows = useMemo(() => dayRows(hourCells(response, entry)), [response, entry])
  const run = entry.series_overlay
  const firstRun = run.findIndex((r) => r.state === 'run')
  const summary = `Calendar: job runs from ${formatDay(entry.start)} ${formatClock(entry.start)} to ${formatClock(entry.finish)}`
  return (
    <figure className="view-figure">
      <Legend />
      <div className="calendar" role="img" aria-label={summary}>
        <div className="cal-hours" aria-hidden="true">
          <span className="cal-head" />
          {Array.from({ length: 24 }, (_, h) => (
            <span key={h} className="cal-hour">
              {h % 3 === 0 ? `${String(h).padStart(2, '0')}:00` : ''}
            </span>
          ))}
        </div>
        {rows.map((row) => (
          <div key={row.day} className="cal-day">
            <span className="cal-head">{row.day}</span>
            {row.cells.map((cell, h) => (
              <span
                key={h}
                className={
                  cell
                    ? [
                        'cal-slot',
                        `lv-${cell.level}`,
                        cell.state === 'run' ? 'is-run' : '',
                        cell.state === 'pause' ? 'is-pause' : '',
                        cell.inCleanest ? 'is-clean' : '',
                        cell.isDeadline ? 'is-deadline' : '',
                      ].join(' ')
                    : 'cal-slot cal-empty'
                }
              >
                {cell && cell.index === firstRun ? <b>GPU job</b> : null}
                {cell?.isDeadline ? <em>Deadline</em> : null}
              </span>
            ))}
          </div>
        ))}
      </div>
      <Caption response={response} />
    </figure>
  )
}

/** The plan read four ways: a timetable, an hourly list, a calendar and the detailed chart. */
export function PlanViews({ response, entry }: ViewProps) {
  const [view, setView] = useState<ViewId>(readView)
  const base = useId()
  const pick = (next: ViewId) => {
    setView(next)
    saveView(next)
  }
  const onKey = (e: KeyboardEvent<HTMLDivElement>) => {
    if (e.key !== 'ArrowRight' && e.key !== 'ArrowLeft') return
    const i = VIEWS.findIndex((v) => v.id === view)
    const next = VIEWS[(i + (e.key === 'ArrowRight' ? 1 : VIEWS.length - 1)) % VIEWS.length]
    pick(next.id)
    document.getElementById(`${base}-${next.id}`)?.focus()
  }
  return (
    <section className="card plan-views" aria-label="Next 48 hours">
      <div className="views-head">
        <h3>Next 48 hours</h3>
        <div className="view-tabs" role="tablist" aria-label="View" onKeyDown={onKey}>
          {VIEWS.map((v) => (
            <button
              key={v.id}
              id={`${base}-${v.id}`}
              type="button"
              role="tab"
              aria-selected={view === v.id}
              aria-controls={`${base}-panel`}
              tabIndex={view === v.id ? 0 : -1}
              className="view-tab"
              onClick={() => pick(v.id)}
            >
              {v.label}
            </button>
          ))}
        </div>
      </div>
      <div id={`${base}-panel`} role="tabpanel" aria-labelledby={`${base}-${view}`} className="view-panel" key={view}>
        {view === 'timetable' ? <Timetable response={response} entry={entry} /> : null}
        {view === 'hourly' ? <Hourly response={response} entry={entry} /> : null}
        {view === 'calendar' ? <Calendar response={response} entry={entry} /> : null}
        {view === 'chart' ? <PlanChart response={response} entry={entry} /> : null}
      </div>
    </section>
  )
}
