// Deadlines are India time (IST, +05:30) whatever the browser's time zone is (plan 6.2.d).
// Only UTC getters and Date.parse with an explicit offset are used, never local-time ones.

const IST_OFFSET_MS = 5.5 * 3_600_000
const DAY_MS = 86_400_000
const LOCAL_FORMAT = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/
const DEFAULT_HOUR = '09:00'

const two = (n: number): string => String(n).padStart(2, '0')

/** "2026-10-11T09:00" (what <input type="datetime-local"> gives) for a moment, in IST. */
export function msToIstLocal(ms: number): string {
  const t = new Date(ms + IST_OFFSET_MS)
  return (
    `${t.getUTCFullYear()}-${two(t.getUTCMonth() + 1)}-${two(t.getUTCDate())}` +
    `T${two(t.getUTCHours())}:${two(t.getUTCMinutes())}`
  )
}

/** The moment a datetime-local value means in IST, or null when it is not a real date and time. */
export function istLocalToMs(local: string): number | null {
  if (!LOCAL_FORMAT.test(local)) return null
  const ms = Date.parse(`${local}:00+05:30`)
  if (Number.isNaN(ms)) return null
  // Date.parse rolls some impossible dates over (31 Feb); writing it back catches them.
  return msToIstLocal(ms) === local ? ms : null
}

/** "2026-10-11T09:00:00+05:30", the form the API wants, or null for an invalid value. */
export function istLocalToIso(local: string): string | null {
  return istLocalToMs(local) === null ? null : `${local}:00+05:30`
}

/** Tomorrow at 09:00 India time (PRD F1). */
export function defaultDeadline(nowMs: number): string {
  const tomorrow = msToIstLocal(nowMs + DAY_MS).slice(0, 10)
  return `${tomorrow}T${DEFAULT_HOUR}`
}
