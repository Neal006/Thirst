// Chooses the API client from the build environment (plan 6.1): mock fixtures with
// VITE_USE_MOCKS=true, otherwise the real API at VITE_API_URL.

import { createClient, type ApiClient } from './client'

const MOCK_BASE_URL = 'http://mock.thirst.local'

/**
 * Loaded on first use, so the fixtures are not part of the main bundle. `import.meta.env.DEV` is
 * false in a production build, so the bundler drops the import and no mock chunk is emitted.
 */
async function lazyMockFetch(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  if (import.meta.env.DEV) {
    const { mockFetch } = await import('./mocks/mockFetch')
    return mockFetch(input, init)
  }
  throw new Error('Mock data is only available in a development build.')
}

const text = (value: unknown): string => (typeof value === 'string' ? value : '')

function isHttps(address: string): boolean {
  try {
    return new URL(address).protocol === 'https:'
  } catch {
    return false
  }
}

/**
 * A production build fails closed: it never serves mock data (fake numbers under the real name)
 * and only talks to an https address (an http one would be blocked as mixed content anyway).
 */
export function createDefaultClient(env: Record<string, unknown>): ApiClient {
  const production = env.PROD === true
  if (text(env.VITE_USE_MOCKS) === 'true') {
    if (production) {
      throw new Error('Mock data is switched on in a production build. Set VITE_USE_MOCKS=false.')
    }
    return createClient({ baseUrl: MOCK_BASE_URL, fetchImpl: lazyMockFetch })
  }
  const baseUrl = text(env.VITE_API_URL)
  if (production && baseUrl !== '' && !isHttps(baseUrl)) {
    throw new Error('VITE_API_URL must be an https address in a production build.')
  }
  return createClient({ baseUrl })
}
