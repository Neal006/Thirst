// Test helpers: a spy around the mock API, and a render function that provides a router and
// an API client wired to it. Used by hook, component and page tests.

import { render } from '@testing-library/react'
import type { ReactElement } from 'react'
import { MemoryRouter } from 'react-router-dom'
import { vi, type Mock } from 'vitest'
import { createClient } from '../api/client'
import { ApiContext } from '../api/context'
import { mockFetch } from '../api/mocks/mockFetch'

export type FetchFn = (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>
export type FetchSpy = Mock<FetchFn>

export function fetchSpy(impl: FetchFn = mockFetch): FetchSpy {
  return vi.fn<FetchFn>((input, init) => impl(input, init))
}

export function jsonReply(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

export function clientWith(fetchImpl: FetchFn) {
  return createClient({ baseUrl: 'http://test.local', fetchImpl, timeoutMs: 2000 })
}

/** The paths (with query) that a spy has been called with. */
export function calledPaths(spy: FetchSpy): string[] {
  return spy.mock.calls.map(([input]) => {
    const url = new URL(String(input))
    return `${url.pathname}${url.search}`
  })
}

interface Options {
  path?: string
  spy?: FetchSpy
}

export function renderWithApi(ui: ReactElement, options: Options = {}) {
  const spy = options.spy ?? fetchSpy()
  const client = clientWith(spy)
  const view = render(
    <ApiContext.Provider value={client}>
      <MemoryRouter initialEntries={[options.path ?? '/']}>{ui}</MemoryRouter>
    </ApiContext.Provider>,
  )
  return { ...view, spy }
}
