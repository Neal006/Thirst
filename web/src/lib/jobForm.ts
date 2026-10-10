// Job form values, defaults and validation (plan 6.2). Kept free of React so it can be tested
// alone. The checks mirror the server (08 section 3.1) so a bad value never costs a request.

import type { CityRow, GpuRow, PlanRequestBody } from '../api/types'
import { defaultDeadline, istLocalToIso, istLocalToMs, msToIstLocal } from './deadline'
import { formatClock, formatDay } from './format'

export const COOLING_OPTIONS = [
  { id: 'room_ac', label: 'Room AC' },
  { id: 'air_chiller', label: 'Air-cooled chiller' },
  { id: 'evaporative', label: 'Cooling tower' },
] as const

export type CoolingId = (typeof COOLING_OPTIONS)[number]['id']

export const LIMITS = {
  gpuMin: 1,
  gpuMax: 4096,
  hoursMin: 0.5,
  hoursMax: 48,
  pueMin: 1,
  pueMax: 3,
} as const

const DEFAULT_GPU = 'RTX-4090'
const DEFAULT_CITY = 'Chennai'
const DEFAULT_PUE = '1.4'
const HOUR_MS = 3_600_000
/**
 * How far the browser clock may be off before the form refuses a deadline. The server checks the
 * deadline against its own clock (deadline_in_past, deadline_too_soon) and has the last word.
 */
const CLOCK_SKEW_MS = 10 * 60_000

export interface JobFormValues {
  gpuModel: string
  gpuCount: string
  workHours: string
  /** datetime-local text, read as India time. */
  deadline: string
  pausable: boolean
  city: string
  cooling: CoolingId
  pue: string
}

export type FieldName = keyof JobFormValues
export type FieldErrors = Partial<Record<FieldName, string>>

/** The fields in the order the form shows them, so messages and focus follow the page. */
const FIELD_ORDER: readonly FieldName[] = ['gpuModel', 'gpuCount', 'workHours', 'deadline', 'city', 'pue']

/** The error messages, top of the form first. */
export function orderedMessages(errors: FieldErrors): string[] {
  return FIELD_ORDER.flatMap((name) => {
    const message = errors[name]
    return message ? [message] : []
  })
}

export type ValidationResult =
  | { ok: true; body: PlanRequestBody }
  | { ok: false; errors: FieldErrors }

export function defaultValues(
  nowMs: number,
  gpus: readonly GpuRow[],
  cities: readonly CityRow[],
): JobFormValues {
  const pick = <T extends { id: string }>(list: readonly T[], preferred: string): string =>
    list.find((item) => item.id === preferred)?.id ?? list[0]?.id ?? ''
  return {
    gpuModel: pick(gpus, DEFAULT_GPU),
    gpuCount: '2',
    workHours: '6',
    deadline: defaultDeadline(nowMs),
    pausable: true,
    city: pick(cities, DEFAULT_CITY),
    cooling: 'room_ac',
    pue: DEFAULT_PUE,
  }
}

export interface Preset {
  id: string
  label: string
  hint: string
  gpuModel: string
  gpuCount: number
  workHours: number
  pausable: boolean
  /** Hours from now to the deadline, or null for the usual "tomorrow 09:00". */
  deadlineInHours: number | null
}

/** One-click examples. Multi-GPU runs are not pausable: distributed jobs can't pause yet. */
export const PRESETS: readonly Preset[] = [
  {
    id: 'overnight',
    label: 'Overnight fine-tune',
    hint: '2 × RTX 4090 · 6 h · by 9 AM',
    gpuModel: 'RTX-4090',
    gpuCount: 2,
    workHours: 6,
    pausable: true,
    deadlineInHours: null,
  },
  {
    id: 'quick',
    label: 'Quick experiment',
    hint: '1 × RTX 3090 · 2 h · by 9 AM',
    gpuModel: 'RTX-3090',
    gpuCount: 1,
    workHours: 2,
    pausable: true,
    deadlineInHours: null,
  },
  {
    id: 'pretrain',
    label: 'Two-day pretrain',
    hint: '8 × A100 · 30 h · not pausable',
    gpuModel: 'A100-PCIE-40GB',
    gpuCount: 8,
    workHours: 30,
    pausable: false,
    deadlineInHours: 46,
  },
]

const IST_MS = 5.5 * HOUR_MS

/** The preset's form values, keeping the city and cooling the person already picked. */
export function presetValues(preset: Preset, current: JobFormValues, nowMs: number): JobFormValues {
  let deadline = defaultDeadline(nowMs)
  if (preset.deadlineInHours !== null) {
    // whole IST hour, so it stays inside the 48-hour planning window
    const at = Math.floor((nowMs + preset.deadlineInHours * HOUR_MS + IST_MS) / HOUR_MS) * HOUR_MS - IST_MS
    deadline = msToIstLocal(at)
  }
  return {
    ...current,
    gpuModel: preset.gpuModel,
    gpuCount: String(preset.gpuCount),
    workHours: String(preset.workHours),
    pausable: preset.pausable,
    deadline,
  }
}

/** A finite number from text, or null for empty, junk, NaN and Infinity. */
function toNumber(text: string): number | null {
  if (text.trim() === '') return null
  const value = Number(text)
  return Number.isFinite(value) ? value : null
}

function earliest(nowMs: number, hours: number): string {
  const at = new Date(nowMs + hours * HOUR_MS).toISOString()
  return `${formatDay(at)} ${formatClock(at)}`
}

function deadlineError(text: string, nowMs: number, hours: number | null): string | undefined {
  const deadlineMs = istLocalToMs(text)
  if (deadlineMs === null) return 'Pick a deadline: a date and a time in India time.'
  if (deadlineMs < nowMs - CLOCK_SKEW_MS) return 'The deadline is in the past. Pick a later one.'
  if (hours !== null && deadlineMs < nowMs + hours * HOUR_MS - CLOCK_SKEW_MS) {
    return `This job needs ${hours} hours at full power. Pick a deadline after ${earliest(nowMs, hours)} (India time).`
  }
  return undefined
}

export function validateJobForm(
  values: JobFormValues,
  nowMs: number,
  gpus: readonly GpuRow[],
  cities: readonly CityRow[],
): ValidationResult {
  const errors: FieldErrors = {}
  const count = toNumber(values.gpuCount)
  const hours = toNumber(values.workHours)
  const pue = toNumber(values.pue)
  const tower = values.cooling === 'evaporative'

  if (!gpus.some((g) => g.id === values.gpuModel)) errors.gpuModel = 'Pick a GPU from the list.'
  if (!cities.some((c) => c.id === values.city)) errors.city = 'Pick a city from the list.'
  if (count === null || !Number.isInteger(count) || count < LIMITS.gpuMin || count > LIMITS.gpuMax) {
    errors.gpuCount = `Enter a whole number of GPUs from ${LIMITS.gpuMin} to ${LIMITS.gpuMax}.`
  }
  const hoursOk = hours !== null && hours >= LIMITS.hoursMin && hours <= LIMITS.hoursMax
  if (!hoursOk) errors.workHours = `Enter the hours of work from ${LIMITS.hoursMin} to ${LIMITS.hoursMax}.`
  if (tower && (pue === null || pue < LIMITS.pueMin || pue > LIMITS.pueMax)) {
    errors.pue = `Enter a PUE from ${LIMITS.pueMin.toFixed(1)} to ${LIMITS.pueMax.toFixed(1)}.`
  }
  const deadline = deadlineError(values.deadline, nowMs, hoursOk ? hours : null)
  if (deadline) errors.deadline = deadline

  const iso = istLocalToIso(values.deadline)
  if (Object.keys(errors).length > 0 || count === null || hours === null || iso === null) {
    return { ok: false, errors }
  }
  const body: PlanRequestBody = {
    city: values.city,
    cooling: values.cooling,
    gpu_model: values.gpuModel,
    gpu_count: count,
    work_hours: hours,
    deadline: iso,
    pausable: values.pausable,
    ...(tower && pue !== null ? { pue } : {}),
  }
  return { ok: true, body }
}
