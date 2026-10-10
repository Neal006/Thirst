// Pure helpers for the Plan page (plan 6.3): chart data, the slider's alpha, the person-days
// range of the selected Pareto entry and buildSummary, the chart in words for screen readers.

import type { OverlayRow, ParetoEntry, PlanResponse, SeriesRow } from '../api/types'
import { formatClock, formatDay, levelPercent, paceBlocks } from './format'

const ALPHA_STEPS = 10
const DEFAULT_ALPHA = 0.5
const HOUR_MS = 3_600_000
const WINDOW_HOURS = 3

export function snapAlpha(value: number): number {
  if (!Number.isFinite(value)) return DEFAULT_ALPHA
  const clamped = Math.min(Math.max(value, 0), 1)
  return Math.round(clamped * ALPHA_STEPS) / ALPHA_STEPS
}

export const alphaFromIndex = (index: number): number => snapAlpha(index / ALPHA_STEPS)

/** What a screen reader says for the slider. Alpha is the weight on water. */
export function alphaText(alpha: number): string {
  const water = Math.round(snapAlpha(alpha) * 100)
  return `Water ${water}%, carbon ${100 - water}%`
}

/** The same choice in words, shown beside the slider. */
export function alphaWords(alpha: number): string {
  const a = snapAlpha(alpha)
  if (a === 0) return 'Carbon only'
  if (a === 1) return 'Water only'
  if (a === 0.5) return 'Balanced: water and carbon count the same'
  return a < 0.5 ? 'Leaning towards saving carbon' : 'Leaning towards saving water'
}

const finiteOr = (value: number, fallback: number): number => (Number.isFinite(value) ? value : fallback)

/**
 * Person-days of city water for a Pareto entry. The server sends the range for `chosen` only; the
 * other entries scale from it, because person-days are unweighted litres divided by one constant.
 */
export function personDaysRange(response: PlanResponse, entry: ParetoEntry): [number, number] {
  const litres = (e: ParetoEntry) => e.totals.D_l.map((d, i) => d + e.totals.I_l[i])
  const [lo, hi] = response.person_days_range
  const reference = Math.max(...litres(response.chosen))
  if (!(Number.isFinite(hi) && hi > 0) || !(Number.isFinite(reference) && reference > 0)) return [lo, hi]
  const perDay = reference / hi
  const scaled = litres(entry).map((l) => l / perDay)
  return [Math.min(...scaled), Math.max(...scaled)]
}

export interface ChartPoint {
  slot: string
  direct: number
  grid: number
  co2: number
  /** GPU power level in percent while running, 0 when paused or off. */
  levelPct: number
  state: OverlayRow['state']
}

export function buildChartData(
  series: readonly SeriesRow[],
  overlay: readonly OverlayRow[],
): ChartPoint[] {
  return series.map((row, i) => {
    const slot: OverlayRow | undefined = overlay[i]
    return {
      slot: row.slot,
      direct: finiteOr(row.direct_l_per_kwh, 0),
      grid: finiteOr(row.grid_l_per_kwh, 0),
      co2: finiteOr(row.co2_kg_per_kwh, 0),
      levelPct: slot && slot.state === 'run' ? finiteOr(levelPercent(slot.level), 0) : 0,
      state: slot?.state ?? 'off',
    }
  })
}

/** The series slot (as written in the series) that contains the deadline, or null. */
export function deadlineSlot(series: readonly SeriesRow[], deadlineIso: string): string | null {
  const deadline = Date.parse(deadlineIso)
  if (Number.isNaN(deadline)) return null
  const hit = series.find((row) => {
    const start = Date.parse(row.slot)
    return start <= deadline && deadline < start + HOUR_MS
  })
  return hit?.slot ?? null
}

const slotEnd = (slot: string): string => new Date(Date.parse(slot) + HOUR_MS).toISOString()

/** "Sun 11 Oct 03:00 to 06:00". The day is left out for a start on the submit day. */
function windowText(startIso: string, endIso: string, submitIso: string): string {
  const submitDay = formatDay(submitIso)
  const startDay = formatDay(startIso)
  const endDay = formatDay(endIso)
  const from = startDay === submitDay ? formatClock(startIso) : `${startDay} ${formatClock(startIso)}`
  const to = endDay === startDay ? formatClock(endIso) : `${endDay} ${formatClock(endIso)}`
  return `${from} to ${to}`
}

function cheapestWindow(
  series: readonly SeriesRow[],
  cost: (row: SeriesRow) => number,
  submitIso: string,
): string | null {
  if (series.length < WINDOW_HOURS) return null
  let best = 0
  let bestCost = Number.POSITIVE_INFINITY
  for (let i = 0; i + WINDOW_HOURS <= series.length; i++) {
    const total = series.slice(i, i + WINDOW_HOURS).reduce((sum, row) => sum + cost(row), 0)
    if (total < bestCost) {
      best = i
      bestCost = total
    }
  }
  return windowText(series[best].slot, slotEnd(series[best + WINDOW_HOURS - 1].slot), submitIso)
}

/**
 * The three-hour windows with the least water and the least CO2 per kWh. The series spans 48
 * hours, so a window that is not on the day of `submitIso` says which day it is.
 */
export function lowWindows(
  series: readonly SeriesRow[],
  submitIso: string,
): { water: string | null; co2: string | null } {
  return {
    water: cheapestWindow(
      series,
      (r) => finiteOr(r.direct_l_per_kwh, 0) + finiteOr(r.grid_l_per_kwh, 0),
      submitIso,
    ),
    co2: cheapestWindow(series, (r) => finiteOr(r.co2_kg_per_kwh, 0), submitIso),
  }
}

export interface SummaryRow {
  /** The hour, with its day, as in "Sat 10 Oct 06:00". */
  time: string
  direct: number
  grid: number
  co2: number
  /** "70%" while running, otherwise "paused" or "off". */
  power: string
}

export interface ChartSummary {
  text: string
  rows: SummaryRow[]
}

function powerText(slot: OverlayRow | undefined): string {
  if (slot?.state === 'run') return `${finiteOr(levelPercent(slot.level), 0)}%`
  return slot?.state === 'pause' ? 'paused' : 'off'
}

/**
 * The plan chart as text: a sentence about the hours covered and when the plan runs, and one row
 * per hour. Screen readers cannot read a picture, so the same data goes out as a table.
 */
export function buildSummary(response: PlanResponse, entry: ParetoEntry): ChartSummary {
  const { series } = response
  const rows = buildChartData(series, entry.series_overlay).map((point, i) => ({
    time: `${formatDay(point.slot)} ${formatClock(point.slot)}`,
    direct: point.direct,
    grid: point.grid,
    co2: point.co2,
    power: powerText(entry.series_overlay[i]),
  }))
  const runs = paceBlocks(entry.series_overlay, 'run').map((block) => {
    const first = series[block.from]?.slot
    const last = series[block.to]?.slot
    return first && last ? windowText(first, slotEnd(last), '') : null
  })
  const runText = runs.filter((r): r is string => r !== null)
  const plan = runText.length > 0 ? `Your plan runs from ${runText.join(', then from ')}.` : 'Your plan does not run in this window.'
  const covered =
    series.length > 0
      ? `Water and CO₂ per kWh for ${series.length} hours from ${rows[0].time} to ${formatDay(series[series.length - 1].slot)} ${formatClock(series[series.length - 1].slot)}.`
      : 'There is no hourly data.'
  return { text: `${covered} ${plan}`, rows }
}
