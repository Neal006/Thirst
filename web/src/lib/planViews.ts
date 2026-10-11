// Pure helpers for the plan's alternative views (timetable, hourly list, calendar) and its actions
// (run command, calendar file, share link). Kept free of React so they can be tested alone.

import type { OverlayRow, ParetoEntry, PlanResponse, SeriesRow } from '../api/types'
import { formatClock, formatDay } from './format'
import { waterPerKwh } from './landing'

const HOUR_MS = 3_600_000
const IST_OFFSET_MS = 5.5 * HOUR_MS
const WINDOW_HOURS = 3

export interface HourCell {
  slot: string
  index: number
  /** 0 (least water per kWh in the 48 hours) to 4 (most). */
  level: number
  water: number
  co2: number
  state: OverlayRow['state']
  afterDeadline: boolean
  isDeadline: boolean
  inCleanest: boolean
}

export interface DayRow {
  day: string
  /** IST hour (0 to 23) of every cell; missing hours are null so columns line up. */
  cells: (HourCell | null)[]
}

const finite = (v: number): number => (Number.isFinite(v) ? v : 0)

export function istHourOf(iso: string): number {
  const ms = Date.parse(iso)
  return Number.isNaN(ms) ? 0 : new Date(ms + IST_OFFSET_MS).getUTCHours()
}

/** The start index of the three hours with the least water per kWh, over the whole series. */
export function cleanestStart(series: readonly SeriesRow[]): number | null {
  if (series.length < WINDOW_HOURS) return null
  let best = 0
  let bestCost = Number.POSITIVE_INFINITY
  for (let i = 0; i + WINDOW_HOURS <= series.length; i++) {
    const cost = series.slice(i, i + WINDOW_HOURS).reduce((s, r) => s + waterPerKwh(r), 0)
    if (cost < bestCost) {
      best = i
      bestCost = cost
    }
  }
  return best
}

export function hourCells(response: PlanResponse, entry: ParetoEntry): HourCell[] {
  const { series } = response
  const deadline = Date.parse(response.inputs.deadline)
  const values = series.map(waterPerKwh)
  const lo = Math.min(...values)
  const hi = Math.max(...values)
  const span = hi - lo || 1
  const clean = cleanestStart(series)
  return series.map((row, i) => {
    const start = Date.parse(row.slot)
    return {
      slot: row.slot,
      index: i,
      level: Math.min(4, Math.floor(((values[i] - lo) / span) * 5)),
      water: values[i],
      co2: finite(row.co2_kg_per_kwh),
      state: entry.series_overlay[i]?.state ?? 'off',
      afterDeadline: !Number.isNaN(deadline) && start >= deadline,
      isDeadline: !Number.isNaN(deadline) && start <= deadline && deadline < start + HOUR_MS,
      inCleanest: clean !== null && i >= clean && i < clean + WINDOW_HOURS,
    }
  })
}

/** Cells grouped by IST day, each day a row of 24 hour columns. */
export function dayRows(cells: readonly HourCell[]): DayRow[] {
  const rows: DayRow[] = []
  for (const cell of cells) {
    const day = formatDay(cell.slot)
    let row = rows.find((r) => r.day === day)
    if (!row) {
      row = { day, cells: Array<HourCell | null>(24).fill(null) }
      rows.push(row)
    }
    row.cells[istHourOf(cell.slot)] = cell
  }
  return rows
}

export interface WhyLine {
  text: string
}

/**
 * One sentence on why the plan starts when it does. The cleanest three hours often fall after the
 * deadline, which is why a plan can skip them; saying so stops people second-guessing the result.
 */
export function whyThisTime(response: PlanResponse, entry: ParetoEntry): string | null {
  const { series } = response
  const clean = cleanestStart(series)
  if (clean === null) return null
  const from = series[clean].slot
  const to = new Date(Date.parse(series[clean + WINDOW_HOURS - 1].slot) + HOUR_MS).toISOString()
  const window = `${formatDay(from)} ${formatClock(from)} to ${formatClock(to)}`
  const deadline = Date.parse(response.inputs.deadline)
  const runs = entry.series_overlay.some((r, i) => r.state === 'run' && i >= clean && i < clean + WINDOW_HOURS)
  if (runs) return `It runs through the cleanest hours of the next two days (${window}).`
  const finishMs = Date.parse(to)
  if (!Number.isNaN(deadline) && finishMs > deadline) {
    return `The cleanest hours (${window}) end after your deadline, so this is the cleanest time that still finishes on time.`
  }
  return `This is the cleanest stretch before your deadline. The overall cleanest hours are ${window}.`
}

// ---------- actions ----------

/** The deadline as "YYYY-MM-DD HH:MM" in IST, the format `thirst run --deadline` reads. */
export function istDeadlineText(iso: string): string {
  const ms = Date.parse(iso)
  if (Number.isNaN(ms)) return iso
  const t = new Date(ms + IST_OFFSET_MS)
  const two = (n: number) => String(n).padStart(2, '0')
  return `${t.getUTCFullYear()}-${two(t.getUTCMonth() + 1)}-${two(t.getUTCDate())} ${two(t.getUTCHours())}:${two(t.getUTCMinutes())}`
}

export function runCommand(response: PlanResponse): string {
  const { work_hours, deadline, pausable } = response.inputs
  return `thirst run --hours ${work_hours} --deadline "${istDeadlineText(deadline)}"${pausable ? ' --pausable' : ''} -- python train.py`
}

const icsStamp = (iso: string): string => new Date(Date.parse(iso)).toISOString().replace(/[-:]/g, '').replace(/\.\d{3}/, '')

/** A one-event iCalendar file for the planned run. Times are UTC, so any calendar shows them right. */
export function calendarFile(response: PlanResponse, entry: ParetoEntry): string {
  const { inputs } = response
  const lines = [
    'BEGIN:VCALENDAR',
    'VERSION:2.0',
    'PRODID:-//Thirst//GPU plan//EN',
    'BEGIN:VEVENT',
    `UID:${response.plan_id}@thirst`,
    `DTSTAMP:${icsStamp(response.submit_ts)}`,
    `DTSTART:${icsStamp(entry.start)}`,
    `DTEND:${icsStamp(entry.finish)}`,
    `SUMMARY:GPU job: ${inputs.gpu_count} x ${inputs.gpu_model}\\, GPU at ${entry.level_summary}`,
    `DESCRIPTION:Planned by Thirst. Run: ${runCommand(response).replace(/[,;]/g, (c) => `\\${c}`)}`,
    'BEGIN:VALARM',
    'TRIGGER:-PT10M',
    'ACTION:DISPLAY',
    'DESCRIPTION:GPU job starts in 10 minutes',
    'END:VALARM',
    'END:VEVENT',
    'END:VCALENDAR',
  ]
  return lines.join('\r\n')
}

/** The query string that reopens the planner with the same job. */
export function shareQuery(response: PlanResponse): string {
  const { inputs } = response
  const params = new URLSearchParams({
    city: inputs.city,
    cooling: inputs.cooling,
    gpu: inputs.gpu_model,
    n: String(inputs.gpu_count),
    hours: String(inputs.work_hours),
    deadline: istDeadlineText(inputs.deadline).replace(' ', 'T'),
    pause: inputs.pausable ? '1' : '0',
  })
  return params.toString()
}
