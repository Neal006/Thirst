// A plan response whose 11 Pareto entries differ from each other (the engine fixture has the
// same entry 11 times because the placeholder data makes 70% always best). Tests use it to
// prove that the slider and the cards really follow the selected entry.

import planFixture from '../api/mocks/fixtures/plan_response.json'
import { isPlanResponse } from '../api/guards'
import type { ParetoEntry, PlanResponse, ScheduleRow } from '../api/types'

if (!isPlanResponse(planFixture)) throw new Error('The plan fixture does not match the API types.')
export const BASE_PLAN: PlanResponse = planFixture

const two = (n: number): string => String(n).padStart(2, '0')
const slot = (hour: number): string => `2026-10-10T${two(hour)}:00:00+05:30`

function levelFor(index: number): number {
  if (index < 4) return 0.7
  return index < 8 ? 0.85 : 1
}

function schedule(index: number): ScheduleRow[] {
  const first = 1 + index
  const level = levelFor(index)
  // Entry 8 pauses for one hour in the middle of the job.
  return Array.from({ length: 7 }, (_, i) => ({
    slot: slot(first + i),
    level,
    state: index === 8 && i === 3 ? ('pause' as const) : ('run' as const),
    fraction: 1,
  }))
}

function entry(index: number): ParetoEntry {
  const first = 1 + index
  const rows = schedule(index)
  return {
    ...BASE_PLAN.pareto[index],
    alpha: index / 10,
    start: slot(first),
    finish: `2026-10-10T${two(first + 7)}:10:00+05:30`,
    level_summary: `${Math.round(levelFor(index) * 100)}%`,
    schedule: rows,
    savings_ranges: {
      water_pct: [index + 5, index + 15],
      co2_pct: [20 - index, 30 - index],
      energy_pct: [5, 8],
    },
    point: { W_l: 40 + index, C_kg: 5 - index / 10 },
    series_overlay: BASE_PLAN.pareto[index].series_overlay.map((row) => {
      const hit = rows.find((r) => Date.parse(r.slot) === Date.parse(row.slot))
      return hit ? { slot: row.slot, level: hit.level, state: hit.state } : { ...row, level: 0, state: 'off' as const }
    }),
    notes: [],
  }
}

export function distinctPlan(patch: Partial<PlanResponse> = {}): PlanResponse {
  const pareto = Array.from({ length: 11 }, (_, i) => entry(i))
  return { ...BASE_PLAN, pareto, chosen: pareto[5], notes: [], ...patch }
}
