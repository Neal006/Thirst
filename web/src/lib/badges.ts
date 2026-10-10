import type { AssumptionRow } from '../api/types'

export interface BadgeStep {
  name: string
  at: number
}

const ORDER = ['bronze', 'silver', 'gold', 'platinum'] as const

/** Badge thresholds from the assumptions (badge_bronze ... badge_platinum), lowest first. */
export function badgeSteps(factors: readonly AssumptionRow[] | undefined): BadgeStep[] {
  if (!factors) return []
  return ORDER.flatMap((name) => {
    const row = factors.find((f) => f.id === `badge_${name}`)
    return row && Number.isFinite(row.value) ? [{ name, at: row.value }] : []
  }).sort((a, b) => a.at - b.at)
}

/** The next badge above a score and how many points are missing, or null at the top or unknown. */
export function nextBadge(score: number | null, steps: readonly BadgeStep[]): { name: string; gap: number } | null {
  if (score === null || !Number.isFinite(score)) return null
  const next = steps.find((s) => s.at > score)
  return next ? { name: next.name, gap: Math.ceil(next.at - score) } : null
}
