// A fetch stand-in that serves the engine fixtures, so the app runs without a backend
// (VITE_USE_MOCKS=true). Error replies use the same {error, message} shape as the real API.

import { isLeaderboardResponse, isPlanResponse, isReceiptResponse } from '../guards'
import type { LeaderboardResponse, PlanResponse, ReceiptResponse } from '../types'
import { MOCK_ASSUMPTIONS } from './assumptions'
import leaderboardFixture from './fixtures/leaderboard_response.json'
import planFixture from './fixtures/plan_response.json'
import receiptFixture from './fixtures/receipt_response.json'
import { EMPTY_SITE_ID, emptySite, siteFromRow } from './site'

const DIVISIONS = ['D1', 'D2', 'D3', 'D4']
const MAX_GPUS = 4096
const MAX_WORK_HOURS = 48

function reply(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

const failure = (status: number, error: string, message: string): Response =>
  reply(status, { error, message })

function fixture<T>(value: unknown, guard: (v: unknown) => v is T, name: string): T {
  if (!guard(value)) throw new Error(`The ${name} fixture no longer matches the API types.`)
  return value
}

function parseBody(init?: RequestInit): Record<string, unknown> {
  try {
    const parsed: unknown = JSON.parse(typeof init?.body === 'string' ? init.body : '')
    return typeof parsed === 'object' && parsed !== null ? (parsed as Record<string, unknown>) : {}
  } catch {
    return {}
  }
}

function plan(init?: RequestInit): Response {
  const body = parseBody(init)
  const count = body.gpu_count
  const hours = body.work_hours
  if (typeof count !== 'number' || count < 1 || count > MAX_GPUS) {
    return failure(400, 'invalid_field', `gpu_count: use a whole number from 1 to ${MAX_GPUS}.`)
  }
  if (typeof hours !== 'number' || hours <= 0 || hours > MAX_WORK_HOURS) {
    return failure(400, 'invalid_field', `work_hours: use a number above 0 and up to ${MAX_WORK_HOURS}.`)
  }
  const base = fixture<PlanResponse>(planFixture, isPlanResponse, 'plan')
  return reply(200, { ...base, inputs: { ...base.inputs, ...body } })
}

function leaderboard(division: string): Response {
  if (!DIVISIONS.includes(division)) {
    return failure(400, 'invalid_field', `division: use one of ${DIVISIONS.join(', ')}.`)
  }
  const base = fixture<LeaderboardResponse>(leaderboardFixture, isLeaderboardResponse, 'leaderboard')
  return reply(200, {
    ...base,
    division,
    rows: division === base.division ? base.rows : [],
  })
}

function site(siteId: string): Response {
  if (siteId === EMPTY_SITE_ID) return reply(200, emptySite())
  const board = fixture<LeaderboardResponse>(leaderboardFixture, isLeaderboardResponse, 'leaderboard')
  const row = board.rows.find((r) => r.site_id === siteId)
  if (!row) return failure(404, 'site_not_found', "We couldn't find that site.")
  return reply(200, siteFromRow(row))
}

function receipt(siteId: string, jobId: string): Response {
  const base = fixture<ReceiptResponse>(receiptFixture, isReceiptResponse, 'receipt')
  return reply(200, {
    ...base,
    url: `/receipts/${siteId}/${jobId}`,
    start_ts: '2026-10-10T02:00:00+05:30',
    end_ts: '2026-10-10T08:00:00+05:30',
    method: 'nvml_energy',
    cap_applied: true,
    cap_method: 'nvml',
    gpu: { name: 'NVIDIA GeForce RTX 4090' },
  })
}

export async function mockFetch(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  const raw = input instanceof Request ? input.url : String(input)
  const url = new URL(raw)
  const method = (init?.method ?? 'GET').toUpperCase()
  const parts = url.pathname.split('/').filter(Boolean)

  if (method === 'POST' && url.pathname === '/plan') return plan(init)
  if (method === 'POST' && url.pathname === '/explain') {
    const body = parseBody(init)
    const text = typeof body.text === 'string' ? body.text : ''
    // simple deterministic mock: echo back a placeholder explanation
    return reply(200, {
      explanation: `Explanation for: ${text.substring(0, 50)}`,
      source: 'template',
      note: 'agent_disabled',
      form: null,
    })
  }
  if (method === 'GET' && url.pathname === '/assumptions') return reply(200, MOCK_ASSUMPTIONS)
  if (method === 'GET' && url.pathname === '/leaderboard') {
    return leaderboard(url.searchParams.get('division') ?? 'D1')
  }
  if (method === 'GET' && parts.length === 2 && parts[0] === 'sites') return site(parts[1])
  if (method === 'GET' && parts.length === 3 && parts[0] === 'receipts') {
    return receipt(parts[1], parts[2])
  }
  if (method === 'POST' && url.pathname === '/parse-sentence') {
    const body = parseBody(init)
    const sentence = typeof body.sentence === 'string' ? body.sentence : ''
    const result: any = { work_hours: null, gpu_count: null, city: null, workload: null, found: [] }
    // hours
    const hMatch = sentence.match(/(\d+(?:\.\d+)?)\s*(hours?|hrs?)/i)
    if (hMatch) { result.work_hours = parseFloat(hMatch[1]); result.found.push('work_hours') }
    // gpu count
    const gMatch = sentence.match(/(\d+)\s*[xX]\s*\d+/)
    if (gMatch) { result.gpu_count = parseInt(gMatch[1]); result.found.push('gpu_count') }
    // city list
    const cities = ['Chennai','Bengaluru','Hyderabad','Mumbai','Delhi','Pune']
    for (const city of cities) {
      const re = new RegExp(`\\b${city}\\b`, 'i')
      if (re.test(sentence)) { result.city = city; result.found.push('city'); break }
    }
    // workload keywords
    const workloads = ['lora','training','inference','finetune','fine‑tune']
    for (const kw of workloads) {
      const re = new RegExp(`\\b${kw}\\b`, 'i')
      if (re.test(sentence)) { result.workload = kw; result.found.push('workload'); break }
    }
    result.found = Array.from(new Set(result.found)).sort()
    return reply(200, result)
  }
  return failure(404, 'not_found', "We couldn't find that page of the API.")
}
