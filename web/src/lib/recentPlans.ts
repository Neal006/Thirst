// The last few jobs planned in this browser, so a person can plan the same job again in one click.
// Stored in localStorage as a convenience only: every read and write may fail and that is fine.

import type { PlanResponse } from '../api/types'
import { formatClock, formatDay } from './format'
import { shareQuery } from './planViews'

export interface RecentPlan {
  query: string
  label: string
  detail: string
}

const KEY = 'thirst.recentPlans'
const MAX = 5

const isRecent = (v: unknown): v is RecentPlan =>
  typeof v === 'object' &&
  v !== null &&
  typeof (v as RecentPlan).query === 'string' &&
  typeof (v as RecentPlan).label === 'string' &&
  typeof (v as RecentPlan).detail === 'string'

export function readRecent(): RecentPlan[] {
  try {
    const raw: unknown = JSON.parse(window.localStorage.getItem(KEY) ?? '[]')
    return Array.isArray(raw) ? raw.filter(isRecent).slice(0, MAX) : []
  } catch {
    return []
  }
}

export function recentFrom(response: PlanResponse): RecentPlan {
  const { inputs } = response
  return {
    query: shareQuery(response),
    label: `${inputs.gpu_count} × ${inputs.gpu_model.replace(/-/g, ' ')} · ${inputs.work_hours} h`,
    detail: `${inputs.city} · by ${formatDay(inputs.deadline)} ${formatClock(inputs.deadline)}`,
  }
}

/** Puts the plan first, drops an older copy of the same job, keeps five. Returns the new list. */
export function rememberPlan(response: PlanResponse): RecentPlan[] {
  const item = recentFrom(response)
  const list = [item, ...readRecent().filter((r) => r.query !== item.query)].slice(0, MAX)
  try {
    window.localStorage.setItem(KEY, JSON.stringify(list))
  } catch {
    // a full or blocked store only loses the shortcut
  }
  return list
}
