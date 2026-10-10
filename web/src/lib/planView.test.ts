import { describe, expect, it } from 'vitest'
import planFixture from '../api/mocks/fixtures/plan_response.json'
import { isPlanResponse } from '../api/guards'
import { distinctPlan } from '../test/planFixture'
import type { OverlayRow, PlanResponse, SeriesRow } from '../api/types'
import {
  alphaFromIndex,
  alphaText,
  alphaWords,
  buildChartData,
  deadlineSlot,
  buildSummary,
  lowWindows,
  personDaysRange,
  snapAlpha,
} from './planView'

if (!isPlanResponse(planFixture)) throw new Error('plan fixture does not match the types')
const plan: PlanResponse = planFixture
const distinctSample = (): PlanResponse => distinctPlan()

function seriesRow(hour: number, direct: number, grid: number, co2: number): SeriesRow {
  const slot = `2026-10-10T${String(hour).padStart(2, '0')}:00:00+05:30`
  return { slot, direct_l_per_kwh: direct, grid_l_per_kwh: grid, co2_kg_per_kwh: co2, temp_c: 25, tw_c: 20, level: 0, state: 'off' }
}

describe('alpha helpers', () => {
  it('snaps slider values to the 0.1 grid the server uses', () => {
    expect(snapAlpha(0.30000000000000004)).toBe(0.3)
    expect(snapAlpha(0.7000000000000001)).toBe(0.7)
    expect(snapAlpha(-1)).toBe(0)
    expect(snapAlpha(4)).toBe(1)
    expect(snapAlpha(Number.NaN)).toBe(0.5)
  })

  it('maps a Pareto index to its alpha', () => {
    expect(alphaFromIndex(0)).toBe(0)
    expect(alphaFromIndex(3)).toBe(0.3)
    expect(alphaFromIndex(10)).toBe(1)
  })

  it('reads the slider for screen readers', () => {
    expect(alphaText(0.5)).toBe('Water 50%, carbon 50%')
    expect(alphaText(0.3)).toBe('Water 30%, carbon 70%')
    expect(alphaText(1)).toBe('Water 100%, carbon 0%')
  })

  it('describes the choice in words, with no numbers', () => {
    expect(alphaWords(0)).toBe('Carbon only')
    expect(alphaWords(0.5)).toBe('Balanced: water and carbon count the same')
    expect(alphaWords(1)).toBe('Water only')
    expect(alphaWords(0.2)).toMatch(/carbon/i)
    expect(alphaWords(0.8)).toMatch(/water/i)
    expect(alphaWords(0.2)).not.toMatch(/\d/)
  })
})

describe('personDaysRange', () => {
  it('is the server range for the chosen plan', () => {
    const [lo, hi] = personDaysRange(plan, plan.chosen)
    expect(lo).toBeCloseTo(plan.person_days_range[0], 3)
    expect(hi).toBeCloseTo(plan.person_days_range[1], 3)
  })

  it('scales with the water of another Pareto entry', () => {
    const doubled = {
      ...plan.chosen,
      totals: {
        ...plan.chosen.totals,
        D_l: plan.chosen.totals.D_l.map((v) => v * 2) as typeof plan.chosen.totals.D_l,
        I_l: plan.chosen.totals.I_l.map((v) => v * 2) as typeof plan.chosen.totals.I_l,
      },
    }
    const [lo, hi] = personDaysRange(plan, doubled)
    expect(lo).toBeCloseTo(plan.person_days_range[0] * 2, 3)
    expect(hi).toBeCloseTo(plan.person_days_range[1] * 2, 3)
  })

  it('falls back to the server range when it cannot scale', () => {
    const empty = { ...plan, person_days_range: [0, 0] as [number, number] }
    expect(personDaysRange(empty, plan.chosen)).toEqual([0, 0])
  })
})

describe('buildChartData', () => {
  const overlay: OverlayRow[] = plan.chosen.series_overlay

  it('gives one point per slot with the intensities', () => {
    const data = buildChartData(plan.series, overlay)
    expect(data).toHaveLength(48)
    expect(data[0]).toMatchObject({
      slot: plan.series[0].slot,
      direct: plan.series[0].direct_l_per_kwh,
      grid: plan.series[0].grid_l_per_kwh,
      co2: plan.series[0].co2_kg_per_kwh,
    })
  })

  it('shows the power level in percent while running and nothing when off or paused', () => {
    const rows: OverlayRow[] = [
      { slot: 'a', level: 0.7, state: 'run' },
      { slot: 'b', level: 0.85, state: 'pause' },
      { slot: 'c', level: 0, state: 'off' },
    ]
    const series = [seriesRow(0, 1, 1, 1), seriesRow(1, 1, 1, 1), seriesRow(2, 1, 1, 1)]
    expect(buildChartData(series, rows).map((p) => p.levelPct)).toEqual([70, 0, 0])
  })

  it('treats a missing overlay row as off', () => {
    const data = buildChartData([seriesRow(0, 1, 1, 1)], [])
    expect(data[0].levelPct).toBe(0)
    expect(data[0].state).toBe('off')
  })

  it('never lets NaN reach the chart', () => {
    const bad = { ...seriesRow(0, Number.NaN, Number.POSITIVE_INFINITY, Number.NaN) }
    const [point] = buildChartData([bad], [])
    expect([point.direct, point.grid, point.co2].every(Number.isFinite)).toBe(true)
  })
})

describe('deadlineSlot', () => {
  it('finds the slot the deadline falls in', () => {
    expect(deadlineSlot(plan.series, '2026-10-10T09:00:00+05:30')).toBe('2026-10-10T09:00:00+05:30')
    expect(deadlineSlot(plan.series, '2026-10-10T09:40:00+05:30')).toBe('2026-10-10T09:00:00+05:30')
  })

  it('works with another offset for the same moment', () => {
    expect(deadlineSlot(plan.series, '2026-10-10T03:30:00Z')).toBe('2026-10-10T09:00:00+05:30')
  })

  it('is null when the deadline is outside the 48 hours or not a date', () => {
    expect(deadlineSlot(plan.series, '2026-10-20T09:00:00+05:30')).toBeNull()
    expect(deadlineSlot(plan.series, '2026-10-01T09:00:00+05:30')).toBeNull()
    expect(deadlineSlot(plan.series, 'soon')).toBeNull()
    expect(deadlineSlot([], '2026-10-10T09:00:00+05:30')).toBeNull()
  })
})

describe('lowWindows', () => {
  const rows = Array.from({ length: 24 }, (_, h) => {
    const water = h >= 12 && h <= 14 ? 1 : 5
    const co2 = h >= 11 && h <= 13 ? 0.2 : 0.8
    return seriesRow(h, water, 0, co2)
  })
  const SUBMIT_DAY = '2026-10-10T08:30:00+05:30'

  it('names the three lowest hours for water and for CO2', () => {
    expect(lowWindows(rows, SUBMIT_DAY)).toEqual({ water: '12:00 to 15:00', co2: '11:00 to 14:00' })
  })

  it('is null for a series shorter than the window', () => {
    expect(lowWindows(rows.slice(0, 2), SUBMIT_DAY)).toEqual({ water: null, co2: null })
  })

  describe('when the series spans 48 hours', () => {
    // 48 hourly rows from 10 Oct 00:00 IST; the cheapest hours are on 11 Oct, 03:00 to 06:00.
    const start = Date.parse('2026-10-10T00:00:00+05:30')
    const span = Array.from({ length: 48 }, (_, i) => {
      const slot = new Date(start + i * 3_600_000).toISOString()
      const cheap = i >= 27 && i <= 29 ? 0.1 : 1
      return { ...seriesRow(0, cheap, 0, cheap), slot }
    })

    it('adds the day when the window is not on the submit day', () => {
      expect(lowWindows(span, SUBMIT_DAY).water).toBe('Sun 11 Oct 03:00 to 06:00')
      expect(lowWindows(span, SUBMIT_DAY).co2).toBe('Sun 11 Oct 03:00 to 06:00')
    })

    it('leaves the day out when the window is on the submit day', () => {
      expect(lowWindows(span, '2026-10-11T01:00:00+05:30').water).toBe('03:00 to 06:00')
    })

    it('adds the day to the end when a window runs past midnight', () => {
      const late = span.map((row, i) => ({ ...row, direct_l_per_kwh: i >= 22 && i <= 24 ? 0.1 : 1 }))
      expect(lowWindows(late, SUBMIT_DAY).water).toBe('22:00 to Sun 11 Oct 01:00')
    })

    it('always names the day when the submit time cannot be read', () => {
      expect(lowWindows(span, 'soon').water).toBe('Sun 11 Oct 03:00 to 06:00')
    })
  })
})

describe('buildSummary: the chart in words for screen readers', () => {
  const response = distinctSample()

  it('names the hours covered and when the plan runs', () => {
    const { text } = buildSummary(response, response.chosen)
    expect(text).toMatch(/48 hours from Fri 9 Oct 21:00 to Sun 11 Oct 20:00/)
    expect(text).toMatch(/plan runs .*Sat 10 Oct/)
  })

  it('has one row per hour with the time and the numbers', () => {
    const { rows } = buildSummary(response, response.chosen)
    expect(rows).toHaveLength(48)
    expect(rows[0].time).toBe('Fri 9 Oct 21:00')
    expect(rows[0]).toMatchObject({ direct: response.series[0].direct_l_per_kwh, co2: response.series[0].co2_kg_per_kwh })
  })

  it('says off, paused or the power level for each hour', () => {
    const { rows } = buildSummary(response, response.chosen)
    const powers = new Set(rows.map((r) => r.power))
    expect(powers.has('off')).toBe(true)
    expect([...powers].some((p) => /^\d+%$/.test(p))).toBe(true)
  })

  it('says so when the plan does not run in the window', () => {
    const idle = { ...response.chosen, series_overlay: response.chosen.series_overlay.map((r) => ({ ...r, state: 'off' as const, level: 0 })) }
    expect(buildSummary(response, idle).text).toMatch(/does not run/i)
  })

  it('never prints NaN or undefined', () => {
    const bad = { ...response, series: response.series.map((r, i) => (i === 2 ? { ...r, direct_l_per_kwh: Number.NaN } : r)) }
    const { text, rows } = buildSummary(bad, response.chosen)
    expect(JSON.stringify(rows)).not.toMatch(/NaN|undefined/)
    expect(text).not.toMatch(/NaN|undefined/)
    expect(Number.isFinite(rows[2].direct)).toBe(true)
  })
})
