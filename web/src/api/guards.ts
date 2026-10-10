// Hand-written type guards for the API shapes (plan 6.1.b). They check what the pages rely on,
// not every field: enough that a renamed or missing field is caught by the contract test and
// at run time, before a chart receives undefined.

import type {
  AssumptionsResponse,
  LeaderboardResponse,
  PlanResponse,
  ReceiptResponse,
  SiteResponse,
} from './types'

type Obj = Record<string, unknown>

const isObj = (v: unknown): v is Obj => typeof v === 'object' && v !== null && !Array.isArray(v)
const isNum = (v: unknown): v is number => typeof v === 'number' && Number.isFinite(v)
const isStr = (v: unknown): v is string => typeof v === 'string'
const isBool = (v: unknown): v is boolean => typeof v === 'boolean'
const isArr = (v: unknown): v is unknown[] => Array.isArray(v)
const numbers = (v: unknown, n: number): boolean => isArr(v) && v.length === n && v.every(isNum)
const nullable = (check: (v: unknown) => boolean) => (v: unknown) => v === null || check(v)

const SLOTS = 48
const PARETO_ENTRIES = 11

function isTotals(v: unknown): boolean {
  return (
    isObj(v) &&
    ['E_gpu_kwh', 'E_fac_kwh', 'W_l', 'C_kg', 'D_l', 'I_l'].every((k) => numbers(v[k], 3))
  )
}

function isRanges(v: unknown): boolean {
  return isObj(v) && ['water_pct', 'co2_pct', 'energy_pct'].every((k) => numbers(v[k], 2))
}

function isScheduleRow(v: unknown): boolean {
  return (
    isObj(v) &&
    isStr(v.slot) &&
    isNum(v.level) &&
    (v.state === 'run' || v.state === 'pause') &&
    isNum(v.fraction)
  )
}

function isOverlayRow(v: unknown): boolean {
  return isObj(v) && isStr(v.slot) && isNum(v.level) && isStr(v.state)
}

function isPlanEntry(v: unknown): boolean {
  return (
    isObj(v) &&
    isStr(v.kind) &&
    isStr(v.start) &&
    isStr(v.finish) &&
    isStr(v.level_summary) &&
    isArr(v.schedule) &&
    v.schedule.every(isScheduleRow) &&
    isTotals(v.totals) &&
    isRanges(v.savings_ranges) &&
    isObj(v.point) &&
    isNum(v.point.W_l) &&
    isNum(v.point.C_kg) &&
    isArr(v.series_overlay) &&
    v.series_overlay.length === SLOTS &&
    v.series_overlay.every(isOverlayRow) &&
    isArr(v.notes)
  )
}

function isSeriesRow(v: unknown): boolean {
  return (
    isObj(v) &&
    isStr(v.slot) &&
    ['direct_l_per_kwh', 'grid_l_per_kwh', 'co2_kg_per_kwh', 'temp_c', 'tw_c', 'level'].every((k) =>
      isNum(v[k]),
    ) &&
    isStr(v.state)
  )
}

export function isPlanResponse(v: unknown): v is PlanResponse {
  return (
    isObj(v) &&
    isStr(v.plan_id) &&
    isStr(v.submit_ts) &&
    isObj(v.inputs) &&
    isPlanEntry(v.base) &&
    isPlanEntry(v.best) &&
    isPlanEntry(v.chosen) &&
    isNum((v.chosen as Obj).alpha) &&
    isArr(v.pareto) &&
    v.pareto.length === PARETO_ENTRIES &&
    v.pareto.every((e) => isPlanEntry(e) && isNum((e as Obj).alpha)) &&
    isArr(v.series) &&
    v.series.length === SLOTS &&
    v.series.every(isSeriesRow) &&
    numbers(v.person_days_range, 2) &&
    isObj(v.tags) &&
    isStr(v.tags.forecast) &&
    isStr(v.tags.tau) &&
    isArr(v.notes) &&
    isStr(v.factor_version)
  )
}

function isFootprint(v: unknown): boolean {
  return (
    isObj(v) &&
    ['E_gpu_kwh', 'E_fac_kwh', 'litres', 'W_l', 'C_kg', 'person_days'].every((k) => isNum(v[k]))
  )
}

function isThreeWay(v: unknown, check: (x: unknown) => boolean): boolean {
  return isObj(v) && check(v.base) && check(v.best) && check(v.actual)
}

export function isReceiptResponse(v: unknown): v is ReceiptResponse {
  return (
    isObj(v) &&
    isStr(v.receipt_id) &&
    isThreeWay(v.scoring, isFootprint) &&
    isObj(v.scoring) &&
    isThreeWay(v.scoring.J, isNum) &&
    isThreeWay(v.absolute, isFootprint) &&
    isObj(v.absolute) &&
    isObj(v.absolute.basis) &&
    isNum(v.absolute.basis.observed) &&
    isNum(v.absolute.basis.forecast) &&
    'capture' in v &&
    nullable(isNum)(v.capture) &&
    isBool(v.no_room) &&
    isBool(v.flexible) &&
    isObj(v.tags) &&
    isStr(v.tags.energy) &&
    isObj(v.site_score) &&
    nullable(isNum)(v.site_score.value) &&
    isBool(v.site_score.provisional) &&
    isStr(v.url)
  )
}

function isMonthly(v: unknown): boolean {
  return (
    isObj(v) &&
    ['kwh', 'facility_kwh', 'litres', 'stress_litres', 'kg_co2', 'person_days'].every((k) =>
      isNum(v[k]),
    )
  )
}

function isLeaderboardRow(v: unknown): boolean {
  return (
    isObj(v) &&
    nullable(isNum)(v.rank) &&
    isStr(v.site_id) &&
    isStr(v.name) &&
    isBool(v.simulated) &&
    isStr(v.division) &&
    nullable(isStr)(v.badge) &&
    nullable(isNum)(v.score) &&
    isBool(v.provisional) &&
    isNum(v.flex_share) &&
    isMonthly(v.monthly_absolute) &&
    isNum(v.receipts)
  )
}

export function isLeaderboardResponse(v: unknown): v is LeaderboardResponse {
  return (
    isObj(v) &&
    isStr(v.division) &&
    isStr(v.generated_at) &&
    isArr(v.rows) &&
    v.rows.every(isLeaderboardRow)
  )
}

export function isSiteResponse(v: unknown): v is SiteResponse {
  return (
    isObj(v) &&
    isObj(v.site) &&
    isStr(v.site.site_id) &&
    isStr(v.site.name) &&
    isStr(v.site.division) &&
    isBool(v.site.simulated) &&
    isObj(v.score) &&
    nullable(isNum)(v.score.value) &&
    isBool(v.score.provisional) &&
    v.score.B === 'not_rated' &&
    isNum(v.score.A) &&
    isNum(v.score.C) &&
    isObj(v.score.C_parts) &&
    isNum(v.score.flex_share) &&
    nullable(isMonthly)(v.monthly_absolute) &&
    isArr(v.recent_receipts)
  )
}

export function isAssumptionsResponse(v: unknown): v is AssumptionsResponse {
  return (
    isObj(v) &&
    isStr(v.version) &&
    isArr(v.factors) &&
    v.factors.every(
      (f) =>
        isObj(f) && isStr(f.id) && isStr(f.group) && isStr(f.label) && isNum(f.value) && isStr(f.status),
    ) &&
    isArr(v.gpus) &&
    v.gpus.every((g) => isObj(g) && isStr(g.id) && isStr(g.label) && isNum(g.p_max_w)) &&
    isArr(v.cities) &&
    v.cities.every((c) => isObj(c) && isStr(c.id)) &&
    isObj(v.stress_weights) &&
    isArr(v.sources)
  )
}
