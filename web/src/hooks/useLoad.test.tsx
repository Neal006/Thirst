import { act, renderHook, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { describe, expect, it, vi } from 'vitest'
import { ApiError } from '../api/client'
import { ApiContext } from '../api/context'
import { clientWith, fetchSpy } from '../test/api'
import { useLoad } from './useLoad'

const wrapper = ({ children }: { children: ReactNode }) => (
  <ApiContext.Provider value={clientWith(fetchSpy())}>{children}</ApiContext.Provider>
)

describe('useLoad', () => {
  it('starts loading, then gives the data', async () => {
    const load = vi.fn(async () => 'hello')
    const { result } = renderHook(() => useLoad(load, 'a'), { wrapper })
    expect(result.current.state.status).toBe('loading')
    await waitFor(() => expect(result.current.state.status).toBe('ready'))
    expect(result.current.state).toEqual({ status: 'ready', data: 'hello' })
  })

  it('turns an API error into its plain-words message', async () => {
    const load = vi.fn(async () => {
      throw new ApiError(404, 'site_not_found', "We couldn't find that site.")
    })
    const { result } = renderHook(() => useLoad(load, 'a'), { wrapper })
    await waitFor(() => expect(result.current.state.status).toBe('error'))
    expect(result.current.state).toEqual({ status: 'error', message: "We couldn't find that site." })
  })

  it('hides the text of unexpected errors', async () => {
    const load = vi.fn(async () => {
      throw new TypeError('x is not a function')
    })
    const { result } = renderHook(() => useLoad(load, 'a'), { wrapper })
    await waitFor(() => expect(result.current.state.status).toBe('error'))
    const state = result.current.state
    expect(state.status === 'error' && state.message).not.toMatch(/function|TypeError/)
  })

  it('loads again when the key changes and shows loading in between', async () => {
    const load = vi.fn(async () => 'x')
    const { result, rerender } = renderHook(({ k }) => useLoad(load, k), {
      wrapper,
      initialProps: { k: 'one' },
    })
    await waitFor(() => expect(result.current.state.status).toBe('ready'))
    rerender({ k: 'two' })
    expect(result.current.state.status).toBe('loading')
    await waitFor(() => expect(result.current.state.status).toBe('ready'))
    expect(load).toHaveBeenCalledTimes(2)
  })

  it('reload asks again', async () => {
    const load = vi.fn(async () => 'x')
    const { result } = renderHook(() => useLoad(load, 'a'), { wrapper })
    await waitFor(() => expect(result.current.state.status).toBe('ready'))
    act(() => result.current.reload())
    await waitFor(() => expect(load).toHaveBeenCalledTimes(2))
  })

  it('passes an abort signal that fires when the component goes away', async () => {
    let seen: AbortSignal | undefined
    const load = vi.fn(async (_api: unknown, signal: AbortSignal) => {
      seen = signal
      return new Promise<string>(() => {})
    })
    const { unmount } = renderHook(() => useLoad(load, 'a'), { wrapper })
    await waitFor(() => expect(seen).toBeDefined())
    unmount()
    expect(seen?.aborted).toBe(true)
  })
})
