// Helpers for the home page graphics. Kept free of React so they can be tested alone.

import type { AssumptionRow, FactorStatus, PlanRequestBody, SeriesRow } from '../api/types'
import { defaultDeadline, istLocalToIso } from './deadline'

export const FALLBACK_CITIES = ['Chennai', 'Bengaluru', 'Hyderabad', 'Mumbai', 'Delhi', 'Pune'] as const
export const WINDOW_HOURS = 3

export type SampleCooling = 'room_ac' | 'evaporative'

/**
 * The sample job behind the home page (PRD 6.1: Chennai, room AC, 2 x RTX 4090, 6 h, tomorrow
 * 09:00, can pause). Only the city and the cooling change.
 */
export function sampleJob(city: string, nowMs: number, cooling: SampleCooling = 'room_ac'): PlanRequestBody {
  return {
    city,
    cooling,
    gpu_model: 'RTX-4090',
    gpu_count: 2,
    work_hours: 6,
    deadline: istLocalToIso(defaultDeadline(nowMs)) ?? '',
    pausable: true,
  }
}

const finite = (value: number): number => (Number.isFinite(value) ? value : 0)

export const waterPerKwh = (row: SeriesRow): number =>
  finite(row.direct_l_per_kwh) + finite(row.grid_l_per_kwh)

export const co2PerKwh = (row: SeriesRow): number => finite(row.co2_kg_per_kwh)

function windowCosts(series: readonly SeriesRow[], cost: (row: SeriesRow) => number, hours: number): number[] {
  const totals: number[] = []
  for (let i = 0; i + hours <= series.length; i++) {
    let total = 0
    for (let j = i; j < i + hours; j++) total += cost(series[j])
    totals.push(total)
  }
  return totals
}

/** Index of the first hour of the cheapest `hours`-long window, or -1 when the series is short. */
export function cheapestStart(
  series: readonly SeriesRow[],
  cost: (row: SeriesRow) => number,
  hours = WINDOW_HOURS,
): number {
  const totals = windowCosts(series, cost, hours)
  if (totals.length === 0) return -1
  return totals.indexOf(Math.min(...totals))
}

/**
 * How much less the best window costs than the worst one, in percent (0 when the series is short
 * or flat). It describes the forecast, not a saving: a plan also has a deadline.
 */
export function bestVsWorstPct(
  series: readonly SeriesRow[],
  cost: (row: SeriesRow) => number,
  hours = WINDOW_HOURS,
): number {
  const totals = windowCosts(series, cost, hours)
  if (totals.length === 0) return 0
  const worst = Math.max(...totals)
  if (!(worst > 0)) return 0
  return Math.round((1 - Math.min(...totals) / worst) * 100)
}

/** "extremely_high" -> "extremely high". */
export function stressWords(category: string): string {
  return category.replace(/_/g, ' ')
}

/** The IST hour of day of a slot (0 to 23), or -1 for a bad time. */
export function istHour(iso: string): number {
  const ms = Date.parse(iso)
  if (Number.isNaN(ms)) return -1
  return new Date(ms + 5.5 * 3_600_000).getUTCHours()
}

/** The IST time of day as a fraction of a day (0 to 1), or -1 for a bad time. */
export function istDayFraction(iso: string): number {
  const ms = Date.parse(iso)
  if (Number.isNaN(ms)) return -1
  const t = new Date(ms + 5.5 * 3_600_000)
  return (t.getUTCHours() * 60 + t.getUTCMinutes()) / 1440
}

/** A point on a circle; angle 0 is the top (midnight on the clock), clockwise. */
export function polar(cx: number, cy: number, r: number, turn: number): { x: number; y: number } {
  const a = turn * 2 * Math.PI - Math.PI / 2
  return { x: cx + r * Math.cos(a), y: cy + r * Math.sin(a) }
}

const f = (n: number): string => (Math.round(n * 100) / 100).toString()

/** An SVG path for a ring segment between radii r0 and r1, from turn t0 to turn t1. */
export function ringSegment(cx: number, cy: number, r0: number, r1: number, t0: number, t1: number): string {
  const large = t1 - t0 > 0.5 ? 1 : 0
  const a = polar(cx, cy, r1, t0)
  const b = polar(cx, cy, r1, t1)
  const c = polar(cx, cy, r0, t1)
  const d = polar(cx, cy, r0, t0)
  return (
    `M${f(a.x)},${f(a.y)} A${r1},${r1} 0 ${large} 1 ${f(b.x)},${f(b.y)} ` +
    `L${f(c.x)},${f(c.y)} A${r0},${r0} 0 ${large} 0 ${f(d.x)},${f(d.y)} Z`
  )
}

/** An SVG arc (stroke only) at radius r from turn t0 to turn t1. */
export function arcPath(cx: number, cy: number, r: number, t0: number, t1: number): string {
  const large = t1 - t0 > 0.5 ? 1 : 0
  const a = polar(cx, cy, r, t0)
  const b = polar(cx, cy, r, t1)
  return `M${f(a.x)},${f(a.y)} A${r},${r} 0 ${large} 1 ${f(b.x)},${f(b.y)}`
}

export interface CapLevel {
  pct: number
  /** Work per hour relative to full power. */
  tau: number
  /** Energy per unit of work relative to full power. */
  eps: number
  status: FactorStatus
  factor?: string
}

/** 100% plus each capped level whose tau and eps are in the assumptions (85%, 70%). */
export function capLevels(factors: readonly AssumptionRow[] | undefined): CapLevel[] {
  const levels: CapLevel[] = [{ pct: 100, tau: 1, eps: 1, status: 'design_choice' }]
  for (const pct of [85, 70]) {
    const tau = factors?.find((f) => f.id === `tau_${pct}`)
    const eps = factors?.find((f) => f.id === `eps_${pct}`)
    if (tau && eps && tau.value > 0 && eps.value > 0) {
      levels.push({ pct, tau: tau.value, eps: eps.value, status: eps.status, factor: eps.id })
    }
  }
  return levels
}
