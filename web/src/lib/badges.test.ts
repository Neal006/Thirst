import { describe, expect, it } from 'vitest'
import type { AssumptionRow } from '../api/types'
import { badgeSteps, nextBadge } from './badges'

const factors = [
  { id: 'badge_gold', value: 75 },
  { id: 'badge_bronze', value: 45 },
  { id: 'badge_platinum', value: 90 },
  { id: 'badge_silver', value: 60 },
  { id: 'cop_min', value: 1.5 },
] as AssumptionRow[]

describe('badge ladder', () => {
  it('reads the thresholds from the assumptions, lowest first', () => {
    expect(badgeSteps(factors)).toEqual([
      { name: 'bronze', at: 45 },
      { name: 'silver', at: 60 },
      { name: 'gold', at: 75 },
      { name: 'platinum', at: 90 },
    ])
    expect(badgeSteps(undefined)).toEqual([])
  })

  it('names the next badge and the points still missing', () => {
    const steps = badgeSteps(factors)
    expect(nextBadge(10, steps)).toEqual({ name: 'bronze', gap: 35 })
    expect(nextBadge(74.2, steps)).toEqual({ name: 'gold', gap: 1 })
    expect(nextBadge(75, steps)).toEqual({ name: 'platinum', gap: 15 })
    expect(nextBadge(95, steps)).toBeNull()
    expect(nextBadge(null, steps)).toBeNull()
  })
})
