import { describe, expect, it } from 'vitest'
import {
  formatAmount,
  formatClock,
  formatDay,
  formatPercentRange,
  formatRange,
  levelPercent,
  paceBlocks,
  pauseWindows,
  selectPareto,
} from './format'
import plan from '../api/mocks/fixtures/plan_response.json'
import type { OverlayRow, ParetoEntry, ScheduleRow } from '../api/types'

describe('IST clock text', () => {
  it('reads the hour and minute out of the IST string, whatever the browser zone', () => {
    expect(formatClock('2026-10-10T01:00:00+05:30')).toBe('01:00')
    expect(formatClock('2026-10-10T08:40:00+05:30')).toBe('08:40')
    expect(formatClock('2026-10-10T23:59+05:30')).toBe('23:59')
  })

  it('converts other offsets to IST instead of showing a wrong time', () => {
    expect(formatClock('2026-10-09T19:30:00Z')).toBe('01:00')
    expect(formatClock('2026-10-10T00:00:00-05:00')).toBe('10:30')
  })

  it('says so when the text is not a time', () => {
    expect(formatClock('soon')).toBe('--:--')
  })

  it('formats the day with a weekday', () => {
    expect(formatDay('2026-10-10T01:00:00+05:30')).toBe('Sat 10 Oct')
    expect(formatDay('2026-10-09T23:30:00+05:30')).toBe('Fri 9 Oct')
  })
})

describe('ranges are never a bare number', () => {
  it('writes a range with the unit', () => {
    expect(formatPercentRange([15, 30])).toBe('15 to 30%')
    expect(formatRange([0.1, 0.2], 'person-days')).toBe('0.1 to 0.2 person-days')
  })

  it('says "about" when both ends round to the same number', () => {
    expect(formatPercentRange([20, 20])).toBe('about 20%')
    expect(formatRange([4.001, 4.004], 'kg')).toBe('about 4 kg')
  })

  it('keeps the order low to high even if the data is swapped', () => {
    expect(formatPercentRange([30, 15])).toBe('15 to 30%')
  })

  it('shows a negative saving as "uses N% more", not as a minus sign', () => {
    expect(formatPercentRange([-5, 3])).toBe('-5 to 3%')
  })

  it('shows 0 to 0 as no saving', () => {
    expect(formatPercentRange([0, 0])).toBe('about 0%')
  })
})

describe('amounts use a sensible number of digits', () => {
  it.each([
    [1234.5, 'L', '1,235 L'],
    [41.1316, 'L', '41 L'],
    [4.79, 'kg', '4.8 kg'],
    [0.1219, 'person-days', '0.12 person-days'],
    [0, 'kWh', '0 kWh'],
    [0.004, 'kWh', '0.004 kWh'],
  ])('%p %s -> %s', (value, unit, text) => {
    expect(formatAmount(value, unit)).toBe(text)
  })

  it('does not print NaN or Infinity', () => {
    expect(formatAmount(Number.NaN, 'L')).toBe('-- L')
    expect(formatAmount(Number.POSITIVE_INFINITY, 'L')).toBe('-- L')
  })
})

describe('levels', () => {
  it('turns a power level into a percent', () => {
    expect(levelPercent(0.85)).toBe(85)
    expect(levelPercent(0.7)).toBe(70)
    expect(levelPercent(1)).toBe(100)
  })
})

describe('Pareto selection matches the server index', () => {
  const entries = plan.pareto as unknown as ParetoEntry[]

  it('uses round(alpha * 10)', () => {
    expect(selectPareto(entries, 0).alpha).toBe(0)
    expect(selectPareto(entries, 0.5).alpha).toBe(0.5)
    expect(selectPareto(entries, 1).alpha).toBe(1)
    expect(selectPareto(entries, 0.30000000000000004).alpha).toBe(0.3)
  })

  it('clamps out-of-range values', () => {
    expect(selectPareto(entries, -1).alpha).toBe(0)
    expect(selectPareto(entries, 7).alpha).toBe(1)
  })

  it('refuses an empty list', () => {
    expect(() => selectPareto([], 0.5)).toThrow()
  })

  it('agrees with the engine: chosen equals the entry at the plan alpha', () => {
    const chosen = plan.chosen as unknown as ParetoEntry
    expect(selectPareto(entries, plan.inputs.alpha)).toEqual(chosen)
  })
})

describe('schedule blocks', () => {
  const row = (i: number, state: OverlayRow['state'], level = 0.85): OverlayRow => ({
    slot: `2026-10-10T${String(i).padStart(2, '0')}:00:00+05:30`,
    level: state === 'off' ? 0 : level,
    state,
  })

  it('groups consecutive run slots into blocks of slot indexes', () => {
    const overlay = [row(0, 'off'), row(1, 'run'), row(2, 'run'), row(3, 'pause'), row(4, 'run'), row(5, 'off')]
    expect(paceBlocks(overlay, 'run')).toEqual([
      { from: 1, to: 2 },
      { from: 4, to: 4 },
    ])
    expect(paceBlocks(overlay, 'pause')).toEqual([{ from: 3, to: 3 }])
  })

  it('returns nothing when there is no such state', () => {
    expect(paceBlocks([row(0, 'off')], 'run')).toEqual([])
  })

  it('names the pause windows for the result card', () => {
    const schedule: ScheduleRow[] = [
      { slot: '2026-10-10T01:00:00+05:30', level: 0.85, state: 'run', fraction: 1 },
      { slot: '2026-10-10T02:00:00+05:30', level: 0.85, state: 'pause', fraction: 1 },
      { slot: '2026-10-10T03:00:00+05:30', level: 0.85, state: 'pause', fraction: 1 },
      { slot: '2026-10-10T04:00:00+05:30', level: 0.85, state: 'run', fraction: 1 },
    ]
    expect(pauseWindows(schedule)).toEqual([{ from: '02:00', to: '04:00' }])
  })

  it('has no pause windows for a plan that never pauses', () => {
    expect(pauseWindows(plan.chosen.schedule as ScheduleRow[])).toEqual([])
  })
})
