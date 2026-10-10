// Chooses the API client from the build environment (plan 6.1): mock fixtures with
// VITE_USE_MOCKS=true, otherwise the real API at VITE_API_URL.

import { createClient, type ApiClient } from './client'

const MOCK_BASE_URL = 'http://mock.thirst.local'

/** Loaded on first use, so the fixtures are not part of the main bundle. */
async function lazyMockFetch(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  const { mockFetch } = await import('./mocks/mockFetch')
  return mockFetch(input, init)
}

const text = (value: unknown): string => (typeof value === 'string' ? value : '')

export function createDefaultClient(env: Record<string, unknown>): ApiClient {
  if (text(env.VITE_USE_MOCKS) === 'true') {
    return createClient({ baseUrl: MOCK_BASE_URL, fetchImpl: lazyMockFetch })
  }
  return createClient({ baseUrl: text(env.VITE_API_URL) })
}
