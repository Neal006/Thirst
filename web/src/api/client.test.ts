import { describe, expect, it, vi } from 'vitest'
import { ApiError, createClient } from './client'

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json' },
  })
}

describe('api client', () => {
  it('posts JSON with a content-type header and parses the answer', async () => {
    const fetchImpl = vi.fn().mockResolvedValue(jsonResponse(200, { plan_id: 'p_aaaaaaaaaa' }))
    const client = createClient({ baseUrl: 'https://api.test/', fetchImpl })

    const data = await client.post<{ plan_id: string }>('/plan', { gpu_count: 2 })

    expect(data.plan_id).toBe('p_aaaaaaaaaa')
    const [url, init] = fetchImpl.mock.calls[0] as [string, RequestInit]
    expect(url).toBe('https://api.test/plan') // no double slash
    expect(init.method).toBe('POST')
    expect((init.headers as Record<string, string>)['Content-Type']).toBe('application/json')
    expect(init.body).toBe('{"gpu_count":2}')
  })

  it('gets without a body or content-type', async () => {
    const fetchImpl = vi.fn().mockResolvedValue(jsonResponse(200, { ok: true }))
    const client = createClient({ baseUrl: 'https://api.test', fetchImpl })

    await client.get('/leaderboard', { division: 'D2' })

    const [url, init] = fetchImpl.mock.calls[0] as [string, RequestInit]
    expect(url).toBe('https://api.test/leaderboard?division=D2')
    expect(init.method).toBe('GET')
    expect(init.body).toBeUndefined()
  })

  it('maps the server error envelope to an ApiError with the plain-words message', async () => {
    const fetchImpl = vi
      .fn()
      .mockResolvedValue(
        jsonResponse(422, { error: 'deadline_too_soon', message: 'The job does not fit.' }),
      )
    const client = createClient({ baseUrl: 'https://api.test', fetchImpl })

    const failure = await client.post('/plan', {}).catch((e: unknown) => e)

    expect(failure).toBeInstanceOf(ApiError)
    expect(failure).toMatchObject({
      status: 422,
      code: 'deadline_too_soon',
      message: 'The job does not fit.',
    })
  })

  it('cuts a very long server message so an error banner cannot be flooded', async () => {
    const fetchImpl = vi
      .fn()
      .mockResolvedValue(jsonResponse(400, { error: 'invalid_field', message: 'x'.repeat(5000) }))
    const client = createClient({ baseUrl: 'https://api.test', fetchImpl })

    const failure = (await client.post('/plan', {}).catch((e: unknown) => e)) as ApiError

    expect(failure).toBeInstanceOf(ApiError)
    expect(failure.message.length).toBe(300)
  })

  it('gives a friendly message when the server answers with something that is not JSON', async () => {
    const fetchImpl = vi.fn().mockResolvedValue(new Response('<html>Bad gateway</html>', { status: 502 }))
    const client = createClient({ baseUrl: 'https://api.test', fetchImpl })

    const failure = await client.get('/assumptions').catch((e: unknown) => e)

    expect(failure).toBeInstanceOf(ApiError)
    expect((failure as ApiError).message).toMatch(/try again/i)
    expect((failure as ApiError).message).not.toMatch(/html|gateway/i)
  })

  it('treats a 200 with a broken body as an error, not as data', async () => {
    const fetchImpl = vi.fn().mockResolvedValue(new Response('not json', { status: 200 }))
    const client = createClient({ baseUrl: 'https://api.test', fetchImpl })

    await expect(client.get('/assumptions')).rejects.toBeInstanceOf(ApiError)
  })

  it('times out after the configured time with a friendly error', async () => {
    vi.useFakeTimers()
    try {
      const fetchImpl = vi.fn(
        (_url: RequestInfo | URL, init?: RequestInit) =>
          new Promise<Response>((_resolve, reject) => {
            init?.signal?.addEventListener('abort', () =>
              reject(new DOMException('aborted', 'AbortError')),
            )
          }),
      )
      const client = createClient({ baseUrl: 'https://api.test', fetchImpl, timeoutMs: 10_000 })

      const pending = client.post('/plan', {}).catch((e: unknown) => e)
      await vi.advanceTimersByTimeAsync(10_001)
      const failure = await pending

      expect(failure).toBeInstanceOf(ApiError)
      expect(failure).toMatchObject({ code: 'timeout' })
      expect((failure as ApiError).message).toMatch(/took too long/i)
    } finally {
      vi.useRealTimers()
    }
  })

  it('reports a network failure in plain words', async () => {
    const fetchImpl = vi.fn().mockRejectedValue(new TypeError('Failed to fetch'))
    const client = createClient({ baseUrl: 'https://api.test', fetchImpl })

    const failure = await client.get('/assumptions').catch((e: unknown) => e)

    expect(failure).toMatchObject({ code: 'network' })
    expect((failure as ApiError).message).toMatch(/connection/i)
  })

  it('lets the caller cancel a request without reporting an error', async () => {
    const controller = new AbortController()
    const fetchImpl = vi.fn(
      (_url: RequestInfo | URL, init?: RequestInit) =>
        new Promise<Response>((_resolve, reject) => {
          init?.signal?.addEventListener('abort', () =>
            reject(new DOMException('aborted', 'AbortError')),
          )
        }),
    )
    const client = createClient({ baseUrl: 'https://api.test', fetchImpl })

    const pending = client.get('/assumptions', undefined, controller.signal).catch((e: unknown) => e)
    controller.abort()

    expect(await pending).toMatchObject({ code: 'aborted' })
  })

  it('does not even send a request when the signal is already aborted', async () => {
    const controller = new AbortController()
    controller.abort()
    // A fetch that would hang forever: only the pre-check can end this call.
    const fetchImpl = vi.fn(() => new Promise<Response>(() => {}))
    const client = createClient({ baseUrl: 'https://api.test', fetchImpl })

    const failure = await client.get('/assumptions', undefined, controller.signal).catch((e: unknown) => e)

    expect(failure).toMatchObject({ code: 'aborted' })
    expect(fetchImpl).not.toHaveBeenCalled()
  })

  it('refuses to be built without a base URL', () => {
    expect(() => createClient({ baseUrl: '' })).toThrow(/VITE_API_URL/)
  })
})
