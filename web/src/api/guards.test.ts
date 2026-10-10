import { describe, expect, it } from 'vitest'
import originalLeaderboard from '../../../tests/fixtures/leaderboard_response.json'
import originalPlan from '../../../tests/fixtures/plan_response.json'
import originalReceipt from '../../../tests/fixtures/receipt_response.json'
import {
  isAssumptionsResponse,
  isLeaderboardResponse,
  isPlanResponse,
  isReceiptResponse,
  isSiteResponse,
} from './guards'
import leaderboard from './mocks/fixtures/leaderboard_response.json'
import plan from './mocks/fixtures/plan_response.json'
import receipt from './mocks/fixtures/receipt_response.json'

const clone = <T,>(value: T): T => structuredClone(value)

describe('contract: the engine fixtures satisfy the web types', () => {
  it('plan_response.json is a PlanResponse', () => {
    expect(isPlanResponse(plan)).toBe(true)
  })

  it('receipt_response.json is a ReceiptResponse', () => {
    expect(isReceiptResponse(receipt)).toBe(true)
  })

  it('leaderboard_response.json is a LeaderboardResponse', () => {
    expect(isLeaderboardResponse(leaderboard)).toBe(true)
  })

  it('the copies equal the backend fixtures they came from', () => {
    const pairs = [
      ['plan', plan, originalPlan],
      ['receipt', receipt, originalReceipt],
      ['leaderboard', leaderboard, originalLeaderboard],
    ] as const
    for (const [name, copy, original] of pairs) {
      expect(copy, `${name}: run npm run fixtures`).toEqual(original)
    }
  })
})

describe('guards reject a changed shape', () => {
  it('a plan needs 11 pareto entries', () => {
    const broken = clone(plan)
    broken.pareto = broken.pareto.slice(0, 10)
    expect(isPlanResponse(broken)).toBe(false)
  })

  it('a plan needs ranges as two numbers', () => {
    const broken = clone(plan)
    ;(broken.chosen.savings_ranges as { water_pct: unknown }).water_pct = [1]
    expect(isPlanResponse(broken)).toBe(false)
  })

  it('a plan needs 48 series rows', () => {
    const broken = clone(plan)
    broken.series = broken.series.slice(1)
    expect(isPlanResponse(broken)).toBe(false)
  })

  it('a plan with a renamed field fails', () => {
    const broken = clone(plan) as Record<string, unknown>
    broken.person_days_range = undefined
    expect(isPlanResponse(broken)).toBe(false)
  })

  it('a receipt without a capture field fails', () => {
    const broken = clone(receipt) as Record<string, unknown>
    delete broken.capture
    expect(isReceiptResponse(broken)).toBe(false)
  })

  it('a leaderboard row needs a monthly footprint', () => {
    const broken = clone(leaderboard)
    delete (broken.rows[0] as { monthly_absolute?: unknown }).monthly_absolute
    expect(isLeaderboardResponse(broken)).toBe(false)
  })

  it.each([null, undefined, 5, 'x', [], {}])('rejects %p everywhere', (value) => {
    expect(isPlanResponse(value)).toBe(false)
    expect(isReceiptResponse(value)).toBe(false)
    expect(isLeaderboardResponse(value)).toBe(false)
    expect(isSiteResponse(value)).toBe(false)
    expect(isAssumptionsResponse(value)).toBe(false)
  })
})

describe('site and assumptions guards', () => {
  const site = {
    site: {
      site_id: 's_aaaaaaaaaa',
      name: 'Lab',
      org: null,
      city: 'Chennai',
      cooling: 'room_ac',
      division: 'D1',
      simulated: false,
      public: true,
    },
    score: {
      value: null,
      provisional: true,
      badge: null,
      A: 0,
      B: 'not_rated',
      C: 5,
      C_parts: { measured_share: 0, coverage: 0, public: 5 },
      flex_share: 0,
      reason: 'needs_flexible_receipt',
    },
    monthly_absolute: null,
    recent_receipts: [],
  }

  it('accepts a site with no receipts yet', () => {
    expect(isSiteResponse(site)).toBe(true)
  })

  it('rejects a site whose B is not "not_rated"', () => {
    expect(isSiteResponse({ ...site, score: { ...site.score, B: 12 } })).toBe(false)
  })

  it('accepts assumptions with factors, gpus and cities', () => {
    expect(
      isAssumptionsResponse({
        version: 'v1',
        factors: [
          { id: 'tau_70', group: 'gpu', label: 'x', value: 1, low: 1, high: 1, unit: '', status: 'placeholder' },
        ],
        gpus: [{ id: 'RTX-4090', label: 'RTX 4090', p_max_w: 450, p_idle_w: 25, sweep_status: 'placeholder' }],
        cities: [{ id: 'Chennai', stress_category: 'extremely_high', stress_weight: 2, status: 'placeholder' }],
        stress_weights: {},
        sources: [],
      }),
    ).toBe(true)
  })
})
