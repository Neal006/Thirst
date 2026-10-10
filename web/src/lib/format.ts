// Text helpers (plan 6.1.c, 6.4). Every number the pages show goes through here, so ranges are
// never a bare figure, times are always IST, and NaN never reaches the screen.

import type { OverlayRow, ParetoEntry, ScheduleRow } from '../api/types'

const IST_OFFSET_MS = 5.5 * 3_600_000
const HOUR_MS = 3_600_000
const WEEKDAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
const NO_TIME = '--:--'

/** The moment shifted so that its UTC fields read as IST wall-clock time. */
function istFields(iso: string): Date | null {
  const ms = Date.parse(iso)
  return Number.isNaN(ms) ? null : new Date(ms + IST_OFFSET_MS)
}

const two = (n: number): string => String(n).padStart(2, '0')

export function formatClock(iso: string): string {
  const t = istFields(iso)
  return t ? `${two(t.getUTCHours())}:${two(t.getUTCMinutes())}` : NO_TIME
}

export function formatDay(iso: string): string {
  const t = istFields(iso)
  if (!t) return '--'
  return `${WEEKDAYS[t.getUTCDay()]} ${t.getUTCDate()} ${MONTHS[t.getUTCMonth()]}`
}

/** A number with few digits: none above 10, one above 1, two above 0.01, else three. */
function niceNumber(value: number): string {
  const size = Math.abs(value)
  const digits = size >= 10 ? 0 : size >= 1 ? 1 : size >= 0.01 ? 2 : 3
  const text = value.toLocaleString('en-US', {
    minimumFractionDigits: 0,
    maximumFractionDigits: digits,
  })
  return text === '-0' ? '0' : text
}

export function formatAmount(value: number, unit: string): string {
  if (!Number.isFinite(value)) return `-- ${unit}`
  return `${niceNumber(value)} ${unit}`
}

function rangeText(range: readonly [number, number], unit: string, joiner: string): string {
  const [lo, hi] = [...range].sort((a, b) => a - b)
  if (![lo, hi].every(Number.isFinite)) return `--${joiner}${unit}`
  const [a, b] = [niceNumber(lo), niceNumber(hi)]
  return a === b ? `about ${a}${joiner}${unit}` : `${a} to ${b}${joiner}${unit}`
}

/** "15 to 30%", or "about 20%" when both ends round to the same number. */
export function formatPercentRange(range: readonly [number, number]): string {
  return rangeText(range, '%', '')
}

/** "0.1 to 0.2 person-days", with the unit always shown. */
export function formatRange(range: readonly [number, number], unit: string): string {
  return rangeText(range, unit, ' ')
}

export function levelPercent(level: number): number {
  return Math.round(level * 100)
}

/** The Pareto entry for a slider value: the same index the server uses, round(alpha * 10). */
export function selectPareto<T extends ParetoEntry>(entries: readonly T[], alpha: number): T {
  if (entries.length === 0) throw new Error('The plan has no Pareto entries.')
  const index = Math.round(alpha * 10 + 1e-9)
  return entries[Math.min(Math.max(index, 0), entries.length - 1)]
}

export interface SlotBlock {
  from: number
  to: number
}

/** Runs of consecutive slots in one state, as inclusive index pairs (for chart shading). */
export function paceBlocks(overlay: readonly OverlayRow[], state: OverlayRow['state']): SlotBlock[] {
  const blocks: SlotBlock[] = []
  let start = -1
  overlay.forEach((row, i) => {
    if (row.state === state) {
      if (start < 0) start = i
    } else if (start >= 0) {
      blocks.push({ from: start, to: i - 1 })
      start = -1
    }
  })
  if (start >= 0) blocks.push({ from: start, to: overlay.length - 1 })
  return blocks
}

export interface PauseWindow {
  from: string
  to: string
}

/** Pause periods of a schedule as clock times, "02:00 to 04:00" (the end is when it resumes). */
export function pauseWindows(schedule: readonly ScheduleRow[]): PauseWindow[] {
  const windows: PauseWindow[] = []
  let first: ScheduleRow | null = null
  let last: ScheduleRow | null = null
  const close = () => {
    if (first && last) {
      const resumes = Date.parse(last.slot) + HOUR_MS
      windows.push({ from: formatClock(first.slot), to: formatClock(new Date(resumes).toISOString()) })
    }
    first = last = null
  }
  for (const row of schedule) {
    const continues = last !== null && Date.parse(row.slot) - Date.parse(last.slot) === HOUR_MS
    if (row.state !== 'pause' || (last && !continues)) close()
    if (row.state === 'pause') {
      first ??= row
      last = row
    }
  }
  close()
  return windows
}
