// Text and grouping for the Assumptions page (plan 6.7). Everything from the API is treated as
// text, and links are only followed when they are plain http(s).

import type { AssumptionRow } from '../api/types'

const GROUPS: { id: string; label: string }[] = [
  { id: 'cooling', label: 'Cooling' },
  { id: 'it', label: 'IT load' },
  { id: 'grid_carbon', label: 'Grid carbon' },
  { id: 'grid_water', label: 'Grid water' },
  { id: 'grid', label: 'Grid mix' },
  { id: 'stress', label: 'Water stress' },
  { id: 'gpu', label: 'GPU and power cap' },
  { id: 'score', label: 'Score' },
  { id: 'planner', label: 'Planner' },
  { id: 'people', label: 'People' },
  { id: 'checks', label: 'Plausibility checks' },
]

export interface FactorGroup {
  id: string
  label: string
  rows: AssumptionRow[]
}

/** Up to four significant digits, no trailing zeros, never NaN. */
export function plainNumber(value: number): string {
  if (!Number.isFinite(value)) return '--'
  return String(Number(value.toPrecision(4)))
}

/** "2.55 to 3.45", or null when low and high are the same. */
export function rangeText(row: AssumptionRow): string | null {
  const [lo, hi] = [row.low, row.high].sort((a, b) => a - b)
  if (!Number.isFinite(lo) || !Number.isFinite(hi) || plainNumber(lo) === plainNumber(hi)) return null
  return `${plainNumber(lo)} to ${plainNumber(hi)}`
}

function readable(id: string): string {
  const text = id.replace(/_/g, ' ')
  return text.charAt(0).toUpperCase() + text.slice(1)
}

export function groupFactors(rows: readonly AssumptionRow[]): FactorGroup[] {
  const byGroup = new Map<string, AssumptionRow[]>()
  for (const row of rows) byGroup.set(row.group, [...(byGroup.get(row.group) ?? []), row])
  const known = GROUPS.filter((g) => byGroup.has(g.id)).map((g) => ({ ...g, rows: byGroup.get(g.id) ?? [] }))
  const unknown = [...byGroup.keys()]
    .filter((id) => !GROUPS.some((g) => g.id === id))
    .sort()
    .map((id) => ({ id, label: readable(id), rows: byGroup.get(id) ?? [] }))
  return [...known, ...unknown]
}

/** The sentence that goes with a placeholder value (PRD section 7). */
export function statusNote(row: AssumptionRow): string | null {
  if (row.status !== 'placeholder') return null
  return row.group === 'gpu'
    ? 'Placeholder: to be replaced by our measured sweep'
    : 'Placeholder: to be replaced by a sourced or measured value'
}

/** The link when it is plain http or https, otherwise null (no javascript: or data: links). */
export function safeUrl(url: string): string | null {
  try {
    const parsed = new URL(url)
    return parsed.protocol === 'https:' || parsed.protocol === 'http:' ? url : null
  } catch {
    return null
  }
}
