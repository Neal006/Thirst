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

  it('discards a slow answer made for an old key', async () => {
    const resolvers: Array<(value: string) => void> = []
    const load = () => new Promise<string>((resolve) => resolvers.push(resolve))
    const { result, rerender } = renderHook(({ k }) => useLoad(load, k), {
      wrapper,
      initialProps: { k: 'one' },
    })
    await waitFor(() => expect(resolvers).toHaveLength(1))
    rerender({ k: 'two' })
    await waitFor(() => expect(resolvers).toHaveLength(2))
    // The answer for "one" arrives late, after the key moved on: it must not show.
    await act(async () => resolvers[0]('old answer'))
    expect(result.current.state).toEqual({ status: 'loading' })
    await act(async () => resolvers[1]('new answer'))
    expect(result.current.state).toEqual({ status: 'ready', data: 'new answer' })
  })

  it('discards the answer of an earlier attempt after a reload', async () => {
    const resolvers: Array<(value: string) => void> = []
    const load = () => new Promise<string>((resolve) => resolvers.push(resolve))
    const { result } = renderHook(() => useLoad(load, 'a'), { wrapper })
    await waitFor(() => expect(resolvers).toHaveLength(1))
    act(() => result.current.reload())
    await waitFor(() => expect(resolvers).toHaveLength(2))
    await act(async () => resolvers[0]('stale'))
    expect(result.current.state).toEqual({ status: 'loading' })
    await act(async () => resolvers[1]('fresh'))
    expect(result.current.state).toEqual({ status: 'ready', data: 'fresh' })
  })

  it('does not loop when the caller passes a new load function on every render', async () => {
    const calls = vi.fn()
    // Not memoised on purpose: a new function each render.
    const { result } = renderHook(() =>
      useLoad(async () => {
        calls()
        return 'x'
      }, 'a'),
    { wrapper })
    await waitFor(() => expect(result.current.state.status).toBe('ready'))
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 50))
    })
    expect(calls).toHaveBeenCalledTimes(1)
  })

  it('uses the newest load function when the key changes', async () => {
    const { result, rerender } = renderHook(
      ({ k, value }) => useLoad(async () => value, k),
      { wrapper, initialProps: { k: 'one', value: 'first' } },
    )
    await waitFor(() => expect(result.current.state).toEqual({ status: 'ready', data: 'first' }))
    rerender({ k: 'two', value: 'second' })
    await waitFor(() => expect(result.current.state).toEqual({ status: 'ready', data: 'second' }))
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
