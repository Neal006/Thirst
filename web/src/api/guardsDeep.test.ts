// The guards must check everything a component reads, or a bad reply shows "undefined" or crashes
// the page instead of the plain-words error (review finding 2). Each case breaks one field of a
// good reply and expects the guard to refuse it; the untouched reply must still pass.

import { describe, expect, it } from 'vitest'
import {
  isAssumptionsResponse,
  isPlanResponse,
  isReceiptResponse,
  isSiteResponse,
} from './guards'
import { MOCK_ASSUMPTIONS } from './mocks/assumptions'
import plan from './mocks/fixtures/plan_response.json'
import receipt from './mocks/fixtures/receipt_response.json'
import { emptySite } from './mocks/site'
import { distinctPlan } from '../test/planFixture'

type Json = Record<string, unknown>

/** A deep copy with the value at `path` replaced (or removed when `value` is undefined). */
function broken<T>(base: T, path: readonly (string | number)[], value: unknown): unknown {
  const copy: unknown = structuredClone(base)
  let node = copy as Json
  for (const key of path.slice(0, -1)) node = node[key] as Json
  const last = path[path.length - 1]
  if (value === undefined) delete node[last]
  else node[last] = value
  return copy
}

describe('isPlanResponse reads what the plan page reads', () => {
  it('still accepts the untouched reply', () => {
    expect(isPlanResponse(plan)).toBe(true)
  })

  it.each([
    ['tags.water missing', ['tags', 'water'], undefined],
    ['tags.water a number', ['tags', 'water'], 5],
    ['tags.co2 missing', ['tags', 'co2'], undefined],
    ['tags.energy missing', ['tags', 'energy'], undefined],
    ['inputs.deadline missing', ['inputs', 'deadline'], undefined],
    ['inputs.deadline a number', ['inputs', 'deadline'], 20261010],
    ['chosen.gpu_kwh missing', ['chosen', 'gpu_kwh'], undefined],
    ['base.gpu_kwh not numbers', ['base', 'gpu_kwh'], ['a']],
    ['pareto[3].gpu_kwh missing', ['pareto', 3, 'gpu_kwh'], undefined],
  ])('refuses %s', (_name, path, value) => {
    expect(isPlanResponse(broken(plan, path, value))).toBe(false)
  })
})

describe('isPlanResponse needs the 11 entries in slider order', () => {
  it('refuses a response whose entries are reordered', () => {
    const reordered = structuredClone(plan)
    reordered.pareto = [...reordered.pareto].reverse()
    expect(isPlanResponse(reordered)).toBe(false)
  })

  it('refuses a response with a repeated alpha', () => {
    expect(isPlanResponse(broken(plan, ['pareto', 4, 'alpha'], 0.3))).toBe(false)
  })

  it('accepts alphas that are off by floating point noise only', () => {
    expect(isPlanResponse(broken(plan, ['pareto', 3, 'alpha'], 0.30000000000000004))).toBe(true)
  })

  it('accepts the distinct test plan', () => {
    expect(isPlanResponse(distinctPlan())).toBe(true)
  })
})

describe('isReceiptResponse reads what the receipt page reads', () => {
  it('still accepts the untouched reply', () => {
    expect(isReceiptResponse(receipt)).toBe(true)
  })

  it.each([
    ['tags.water missing', ['tags', 'water'], undefined],
    ['tags.co2 missing', ['tags', 'co2'], undefined],
    ['tags.co2 a number', ['tags', 'co2'], 1],
  ])('refuses %s', (_name, path, value) => {
    expect(isReceiptResponse(broken(receipt, path, value))).toBe(false)
  })
})

describe('isAssumptionsResponse reads what the assumptions page reads', () => {
  it('still accepts the mock reply', () => {
    expect(isAssumptionsResponse(MOCK_ASSUMPTIONS)).toBe(true)
  })

  it.each([
    ['a city without stress_category', ['cities', 0, 'stress_category'], undefined],
    ['a city whose stress_category is a number', ['cities', 1, 'stress_category'], 3],
    ['a city without stress_weight', ['cities', 0, 'stress_weight'], undefined],
    ['a city without status', ['cities', 2, 'status'], undefined],
    ['a gpu without sweep_status', ['gpus', 0, 'sweep_status'], undefined],
    ['a source that is a string', ['sources', 0], 'Open-Meteo'],
    ['a source without a name', ['sources', 0, 'name'], undefined],
    ['a source without used_for', ['sources', 1, 'used_for'], undefined],
    ['a source without a licence', ['sources', 1, 'licence'], undefined],
    ['a source whose url is a number', ['sources', 0, 'url'], 7],
  ])('refuses %s', (_name, path, value) => {
    expect(isAssumptionsResponse(broken(MOCK_ASSUMPTIONS, path, value))).toBe(false)
  })
})

describe('isSiteResponse reads what the site page reads', () => {
  const withReceipt = (patch: Json) => {
    const site = emptySite()
    return {
      ...site,
      recent_receipts: [
        { job_id: 'j_abcdefghijkl', end_ts: '2026-10-09T08:00:00+05:30', kwh: 1.2, capture: 0.4, no_room: false, method: 'nvml_energy', ...patch },
      ],
    }
  }

  it('still accepts a site, with and without receipts', () => {
    expect(isSiteResponse(emptySite())).toBe(true)
    expect(isSiteResponse(withReceipt({}))).toBe(true)
    expect(isSiteResponse(withReceipt({ capture: null }))).toBe(true)
  })

  it.each([
    ['C_parts.measured_share missing', ['score', 'C_parts', 'measured_share'], undefined],
    ['C_parts.coverage a string', ['score', 'C_parts', 'coverage'], 'x'],
    ['C_parts.public missing', ['score', 'C_parts', 'public'], undefined],
    ['C_parts missing', ['score', 'C_parts'], undefined],
  ])('refuses %s', (_name, path, value) => {
    expect(isSiteResponse(broken(emptySite(), path, value))).toBe(false)
  })

  it.each([
    ['not an object', null],
    ['without a job_id', { job_id: undefined }],
    ['without kwh', { kwh: undefined }],
    ['with kwh as text', { kwh: 'a lot' }],
    ['without end_ts', { end_ts: undefined }],
    ['with capture as text', { capture: 'high' }],
    ['without no_room', { no_room: undefined }],
    ['without method', { method: undefined }],
  ])('refuses a recent receipt %s', (_name, patch) => {
    const site = patch === null ? { ...emptySite(), recent_receipts: [null] } : withReceipt(patch)
    expect(isSiteResponse(site)).toBe(false)
  })
})
