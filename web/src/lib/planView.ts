// Pure helpers for the Plan page (plan 6.3): chart data, the slider's alpha, the person-days
// range of the selected Pareto entry and the text summary of the chart for screen readers.

import type { OverlayRow, ParetoEntry, PlanResponse, SeriesRow } from '../api/types'
import { formatClock, levelPercent } from './format'

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

function cheapestWindow(series: readonly SeriesRow[], cost: (row: SeriesRow) => number): string | null {
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
  const end = new Date(Date.parse(series[best + WINDOW_HOURS - 1].slot) + HOUR_MS).toISOString()
  return `${formatClock(series[best].slot)} to ${formatClock(end)}`
}

/** The three-hour windows with the least water and the least CO2 per kWh. */
export function lowWindows(series: readonly SeriesRow[]): { water: string | null; co2: string | null } {
  return {
    water: cheapestWindow(series, (r) => finiteOr(r.direct_l_per_kwh, 0) + finiteOr(r.grid_l_per_kwh, 0)),
    co2: cheapestWindow(series, (r) => finiteOr(r.co2_kg_per_kwh, 0)),
  }
}
