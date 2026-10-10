import { describe, expect, it } from 'vitest'
import type { AssumptionRow, SeriesRow } from '../api/types'
import {
  arcPath,
  bestVsWorstPct,
  capLevels,
  cheapestStart,
  co2PerKwh,
  istDayFraction,
  istHour,
  polar,
  ringSegment,
  sampleJob,
  stressWords,
  waterPerKwh,
} from './landing'

function row(slot: string, direct: number, grid: number, co2: number): SeriesRow {
  return {
    slot,
    direct_l_per_kwh: direct,
    grid_l_per_kwh: grid,
    co2_kg_per_kwh: co2,
    temp_c: 30,
    tw_c: 24,
    level: 0,
    state: 'off',
  }
}

describe('sampleJob', () => {
  it('is the PRD example job for the city, with a deadline tomorrow at 09:00 IST', () => {
    const now = Date.parse('2026-10-10T22:00:00+05:30')
    expect(sampleJob('Pune', now)).toEqual({
      city: 'Pune',
      cooling: 'room_ac',
      gpu_model: 'RTX-4090',
      gpu_count: 2,
      work_hours: 6,
      deadline: '2026-10-11T09:00:00+05:30',
      pausable: true,
    })
    expect(sampleJob('Pune', now, 'evaporative').cooling).toBe('evaporative')
  })
})

describe('windows', () => {
  const series = [5, 4, 1, 1, 1, 6, 2].map((v, i) => row(`2026-10-10T0${i}:00:00+05:30`, 0, v, 7 - v))

  it('finds the first hour of the cheapest window', () => {
    expect(cheapestStart(series, waterPerKwh, 3)).toBe(2)
    expect(cheapestStart(series, co2PerKwh, 2)).toBe(0)
  })

  it('says -1 when the series is shorter than the window', () => {
    expect(cheapestStart(series.slice(0, 2), waterPerKwh, 3)).toBe(-1)
  })

  it('treats NaN readings as zero instead of breaking', () => {
    const odd = [row('a', Number.NaN, 1, 1), row('b', 5, 5, 5), row('c', 5, 5, 5)]
    expect(cheapestStart(odd, waterPerKwh, 1)).toBe(0)
  })

  it('compares the best window with the worst one', () => {
    // windows of 3: 10, 6, 3, 8, 9 -> 1 - 3/10
    expect(bestVsWorstPct(series, waterPerKwh, 3)).toBe(70)
    expect(bestVsWorstPct([], waterPerKwh)).toBe(0)
    expect(bestVsWorstPct([row('a', 0, 0, 0), row('b', 0, 0, 0), row('c', 0, 0, 0)], waterPerKwh)).toBe(0)
  })
})

describe('clock geometry', () => {
  it('puts turn 0 at the top and a quarter turn on the right', () => {
    const top = polar(100, 100, 50, 0)
    expect(top.x).toBeCloseTo(100)
    expect(top.y).toBeCloseTo(50)
    const right = polar(100, 100, 50, 0.25)
    expect(right.x).toBeCloseTo(150)
    expect(right.y).toBeCloseTo(100)
  })

  it('draws a closed ring segment and an open arc', () => {
    const seg = ringSegment(100, 100, 40, 60, 0, 0.25)
    expect(seg.startsWith('M100,40 A60,60 0 0 1 160,100')).toBe(true)
    expect(seg.endsWith('Z')).toBe(true)
    expect(arcPath(100, 100, 50, 0, 0.75)).toContain(' 0 1 1 ')
  })

  it('reads IST hours and day fractions', () => {
    expect(istHour('2026-10-10T13:00:00+05:30')).toBe(13)
    expect(istHour('2026-10-10T20:30:00Z')).toBe(2)
    expect(istHour('nonsense')).toBe(-1)
    expect(istDayFraction('2026-10-10T18:00:00+05:30')).toBeCloseTo(0.75)
    expect(istDayFraction('nonsense')).toBe(-1)
  })

  it('turns a stress category into words', () => {
    expect(stressWords('extremely_high')).toBe('extremely high')
  })
})

describe('capLevels', () => {
  it('always has full power, then each level the assumptions describe', () => {
    expect(capLevels(undefined)).toEqual([{ pct: 100, tau: 1, eps: 1, status: 'design_choice' }])
    const factors = [
      { id: 'tau_70', value: 0.9, status: 'placeholder' },
      { id: 'eps_70', value: 0.8, status: 'placeholder' },
      { id: 'tau_85', value: 0.97, status: 'placeholder' },
    ] as AssumptionRow[]
    expect(capLevels(factors).map((l) => l.pct)).toEqual([100, 70])
    expect(capLevels(factors)[1]).toMatchObject({ tau: 0.9, eps: 0.8, factor: 'eps_70' })
  })
})
