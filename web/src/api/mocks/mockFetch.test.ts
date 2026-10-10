import { describe, expect, it } from 'vitest'
import {
  isAssumptionsResponse,
  isLeaderboardResponse,
  isPlanResponse,
  isReceiptResponse,
  isSiteResponse,
} from '../guards'
import { mockFetch } from './mockFetch'
import { EMPTY_SITE_ID } from './site'

const BASE = 'http://mock.local'

async function get(path: string): Promise<{ status: number; body: unknown }> {
  const reply = await mockFetch(`${BASE}${path}`, { method: 'GET' })
  return { status: reply.status, body: await reply.json() }
}

async function post(path: string, body: unknown): Promise<{ status: number; body: unknown }> {
  const reply = await mockFetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  return { status: reply.status, body: await reply.json() }
}

const PLAN_BODY = {
  city: 'Chennai',
  cooling: 'room_ac',
  gpu_model: 'RTX-4090',
  gpu_count: 2,
  work_hours: 6,
  deadline: '2026-10-11T09:00:00+05:30',
  pausable: true,
}

describe('mock API', () => {
  it('serves assumptions that satisfy the guard', async () => {
    const { status, body } = await get('/assumptions')
    expect(status).toBe(200)
    expect(isAssumptionsResponse(body)).toBe(true)
  })

  it('serves the D1 board from the engine fixture and an empty board for other divisions', async () => {
    const d1 = await get('/leaderboard?division=D1&period=30d&board=score')
    expect(isLeaderboardResponse(d1.body)).toBe(true)
    expect((d1.body as { rows: unknown[] }).rows.length).toBeGreaterThan(0)
    const d2 = await get('/leaderboard?division=D2')
    expect(isLeaderboardResponse(d2.body)).toBe(true)
    expect((d2.body as { division: string; rows: unknown[] }).division).toBe('D2')
    expect((d2.body as { rows: unknown[] }).rows).toEqual([])
  })

  it('refuses an unknown division in plain words', async () => {
    const { status, body } = await get('/leaderboard?division=D9')
    expect(status).toBe(400)
    expect(body).toMatchObject({ error: 'invalid_field' })
  })

  it('serves a site page for a board row, an empty site, and 404 for an unknown id', async () => {
    const board = (await get('/leaderboard?division=D1')).body as { rows: { site_id: string }[] }
    const site = await get(`/sites/${board.rows[0].site_id}`)
    expect(isSiteResponse(site.body)).toBe(true)
    const empty = await get(`/sites/${EMPTY_SITE_ID}`)
    expect(isSiteResponse(empty.body)).toBe(true)
    expect((empty.body as { recent_receipts: unknown[] }).recent_receipts).toEqual([])
    const missing = await get('/sites/s_zzzzzzzzzz')
    expect(missing.status).toBe(404)
    expect(missing.body).toMatchObject({ error: 'site_not_found' })
  })

  it('serves a receipt with the three-way breakdown', async () => {
    const { status, body } = await get('/receipts/s_abcdefghij/j_abcdefghijkl')
    expect(status).toBe(200)
    expect(isReceiptResponse(body)).toBe(true)
    expect(body).toMatchObject({ method: 'nvml_energy', cap_applied: true })
  })

  it('serves a plan and echoes the request in the inputs', async () => {
    const { status, body } = await post('/plan', PLAN_BODY)
    expect(status).toBe(200)
    expect(isPlanResponse(body)).toBe(true)
    expect((body as { inputs: { city: string } }).inputs.city).toBe('Chennai')
  })

  it('rejects an impossible plan request with the server error shape', async () => {
    const { status, body } = await post('/plan', { ...PLAN_BODY, gpu_count: 5000 })
    expect(status).toBe(400)
    expect(body).toMatchObject({ error: 'invalid_field' })
    expect(typeof (body as { message: unknown }).message).toBe('string')
  })

  it('answers unknown routes with a 404 in the same error shape', async () => {
    const { status, body } = await get('/nothing-here')
    expect(status).toBe(404)
    expect(body).toMatchObject({ error: 'not_found' })
  })
})
