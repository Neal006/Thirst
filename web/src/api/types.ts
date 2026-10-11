// Mirrors docs/implementation-plan/08-reference-contracts.md section 3 (as built, 3.8).
// The fixtures in ../tests/fixtures are produced by the real engine; guards.test.ts parses every
// copy of them, so a change in the backend shape fails the web build instead of the demo.

export type Tag =
  | 'measured'
  | 'modelled'
  | 'placeholder'
  | 'sourced'
  | 'calibrated'
  | 'unverified'

/** [low, central, high] factor sets. */
export type Triple = [number, number, number]
/** [min %, max %] as whole numbers. */
export type PercentRange = [number, number]

export interface Totals {
  E_gpu_kwh: Triple
  E_fac_kwh: Triple
  W_l: Triple
  C_kg: Triple
  D_l: Triple
  I_l: Triple
}

export interface ScheduleRow {
  slot: string
  level: number
  state: 'run' | 'pause'
  fraction: number
}

export interface OverlayRow {
  slot: string
  level: number
  state: 'off' | 'run' | 'pause'
}

export interface SavingsRanges {
  water_pct: PercentRange
  co2_pct: PercentRange
  energy_pct: PercentRange
}

export interface PlanEntry {
  kind: 'base' | 'non_pausable' | 'pausable'
  start: string
  finish: string
  level_summary: string
  schedule: ScheduleRow[]
  totals: Totals
  savings_ranges: SavingsRanges
  point: { W_l: number; C_kg: number }
  series_overlay: OverlayRow[]
  gpu_kwh: number[]
  notes: string[]
}

export interface ParetoEntry extends PlanEntry {
  alpha: number
}

export interface SeriesRow {
  slot: string
  direct_l_per_kwh: number
  grid_l_per_kwh: number
  co2_kg_per_kwh: number
  temp_c: number
  tw_c: number
  level: number
  state: 'off' | 'run' | 'pause'
}

export interface PlanTags {
  energy: Tag
  water: Tag
  co2: Tag
  tau: Tag
  forecast: 'live' | 'cached'
}

export interface PlanInputs {
  city: string
  cooling: string
  pue: number | null
  gpu_model: string
  gpu_count: number
  work_hours: number
  deadline: string
  pausable: boolean
  pausable_allowed: boolean
  alpha: number
  force_now: boolean
  site_id: string | null
}

export interface ExplainResponse {
  explanation: string
  source: string
  note: string | null
  form: Record<string, any> | null
}

export interface PlanResponse {
  plan_id: string
  submit_ts: string
  inputs: PlanInputs
  base: PlanEntry
  best: PlanEntry
  chosen: ParetoEntry
  pareto: ParetoEntry[]
  series: SeriesRow[]
  person_days_range: [number, number]
  tags: PlanTags
  notes: string[]
  forecast_age_hours?: number | null
  factor_version: string
  assumptions_url: string
}

export interface FootprintTotals {
  E_gpu_kwh: number
  E_fac_kwh: number
  litres: number
  W_l: number
  C_kg: number
  person_days: number
}

export interface ThreeWay<T> {
  base: T
  best: T
  actual: T
}

export interface ReceiptResponse {
  receipt_id: string
  scoring: ThreeWay<FootprintTotals> & { J: ThreeWay<number> }
  absolute: ThreeWay<FootprintTotals> & { basis: { observed: number; forecast: number } }
  capture: number | null
  no_room: boolean
  flexible: boolean
  tags: { energy: Tag; water: Tag; co2: Tag }
  site_score: { value: number | null; badge: string | null; provisional: boolean }
  url: string
}

/** GET /receipts/{site_id}/{job_id} (08 §3.4b): the POST reply plus these fields. Never the GPU count. */
export interface ReceiptDetail extends ReceiptResponse {
  start_ts?: string
  end_ts?: string
  method?: string
  cap_applied?: boolean
  cap_method?: string
  gpu?: { name: string }
}

export interface MonthlyAbsolute {
  kwh: number
  facility_kwh: number
  litres: number
  stress_litres: number
  kg_co2: number
  person_days: number
}

export interface LeaderboardRow {
  rank: number | null
  site_id: string
  name: string
  simulated: boolean
  division: string
  badge: string | null
  score: number | null
  provisional: boolean
  A: number
  C: number
  flex_share: number
  monthly_absolute: MonthlyAbsolute
  receipts: number
}

export interface LeaderboardResponse {
  division: string
  period: string
  board: string
  generated_at: string
  rows: LeaderboardRow[]
}

export interface SiteResponse {
  site: {
    site_id: string
    name: string
    org: string | null
    city: string
    cooling: string
    division: string
    simulated: boolean
    public: boolean
  }
  score: {
    value: number | null
    provisional: boolean
    badge: string | null
    A: number
    B: 'not_rated'
    C: number
    C_parts: { measured_share: number; coverage: number; public: number }
    flex_share: number
    reason: string | null
  }
  monthly_absolute: MonthlyAbsolute | null
  recent_receipts: {
    job_id: string
    end_ts: string
    kwh: number
    capture: number | null
    no_room: boolean
    method: string
  }[]
}

export type FactorStatus = Tag | 'design_choice'

export interface AssumptionRow {
  id: string
  group: string
  label: string
  value: number
  low: number
  high: number
  unit: string
  status: FactorStatus
  source: string
  source_url: string
  notes: string
}

export interface GpuRow {
  id: string
  label: string
  p_max_w: number
  p_idle_w: number
  sweep_status: Tag
}

export interface CityRow {
  id: string
  stress_category: string
  stress_weight: number
  status: Tag
}

export interface SourceRow {
  name: string
  url: string
  licence: string
  used_for: string
}

export interface AssumptionsResponse {
  version: string
  factors: AssumptionRow[]
  gpus: GpuRow[]
  cities: CityRow[]
  stress_weights: Record<string, number>
  sources: SourceRow[]
}

export interface PlanRequestBody {
  city?: string
  cooling?: string
  pue?: number
  gpu_model: string
  gpu_count: number
  work_hours: number
  deadline: string
  pausable: boolean
  pausable_allowed?: boolean
  alpha?: number
  force_now?: boolean
  site_id?: string
}

export interface ApiErrorBody {
  error: string
  message: string
}
