import { renderHook, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { describe, expect, it } from 'vitest'
import { ApiContext } from '../api/context'
import { mockFetch } from '../api/mocks/mockFetch'
import { calledPaths, clientWith, fetchSpy, jsonReply, type FetchSpy } from '../test/api'
import { useAssumptions } from './useAssumptions'
import { useLeaderboard } from './useLeaderboard'
import { useReceipt } from './useReceipt'
import { useSite } from './useSite'

function wrapperFor(spy: FetchSpy) {
  return ({ children }: { children: ReactNode }) => (
    <ApiContext.Provider value={clientWith(spy)}>{children}</ApiContext.Provider>
  )
}

describe('useAssumptions', () => {
  it('loads the GPU and city lists', async () => {
    const spy = fetchSpy()
    const { result } = renderHook(() => useAssumptions(), { wrapper: wrapperFor(spy) })
    await waitFor(() => expect(result.current.state.status).toBe('ready'))
    const state = result.current.state
    expect(state.status === 'ready' && state.data.gpus.length).toBeGreaterThan(0)
    expect(calledPaths(spy)).toEqual(['/assumptions'])
  })

  it('shows plain words when the reply has the wrong shape', async () => {
    const spy = fetchSpy(async () => jsonReply(200, { unexpected: true }))
    const { result } = renderHook(() => useAssumptions(), { wrapper: wrapperFor(spy) })
    await waitFor(() => expect(result.current.state.status).toBe('error'))
    const state = result.current.state
    expect(state.status === 'error' && state.message).toMatch(/could not read/i)
  })
})

describe('useLeaderboard', () => {
  it('asks for the chosen division, and again when it changes', async () => {
    const spy = fetchSpy()
    const { result, rerender } = renderHook(({ d }) => useLeaderboard(d), {
      wrapper: wrapperFor(spy),
      initialProps: { d: 'D1' },
    })
    await waitFor(() => expect(result.current.state.status).toBe('ready'))
    rerender({ d: 'D3' })
    await waitFor(() => expect(calledPaths(spy)).toHaveLength(2))
    expect(calledPaths(spy)[0]).toContain('division=D1')
    expect(calledPaths(spy)[1]).toContain('division=D3')
  })
})

describe('useSite', () => {
  it('shows the server message for an unknown site', async () => {
    const spy = fetchSpy(mockFetch)
    const { result } = renderHook(() => useSite('s_zzzzzzzzzz'), { wrapper: wrapperFor(spy) })
    await waitFor(() => expect(result.current.state.status).toBe('error'))
    const state = result.current.state
    expect(state.status === 'error' && state.message).toMatch(/couldn't find that site/i)
  })

  it('escapes the id in the path', async () => {
    const spy = fetchSpy(async () => jsonReply(404, { error: 'site_not_found', message: 'No.' }))
    renderHook(() => useSite('a/b?c'), { wrapper: wrapperFor(spy) })
    await waitFor(() => expect(spy).toHaveBeenCalled())
    expect(calledPaths(spy)[0]).toBe('/sites/a%2Fb%3Fc')
  })
})

describe('useReceipt', () => {
  it('loads one receipt', async () => {
    const spy = fetchSpy()
    const { result } = renderHook(() => useReceipt('s_abcdefghij', 'j_abcdefghijkl'), {
      wrapper: wrapperFor(spy),
    })
    await waitFor(() => expect(result.current.state.status).toBe('ready'))
    expect(calledPaths(spy)).toEqual(['/receipts/s_abcdefghij/j_abcdefghijkl'])
  })
})
