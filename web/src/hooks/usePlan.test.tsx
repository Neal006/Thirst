import { act, renderHook, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { describe, expect, it } from 'vitest'
import { ApiContext } from '../api/context'
import type { PlanRequestBody } from '../api/types'
import { clientWith, fetchSpy, jsonReply, type FetchSpy } from '../test/api'
import { distinctPlan } from '../test/planFixture'
import { usePlan } from './usePlan'

const BODY: PlanRequestBody = {
  city: 'Chennai',
  cooling: 'room_ac',
  gpu_model: 'RTX-4090',
  gpu_count: 2,
  work_hours: 6,
  deadline: '2026-10-11T09:00:00+05:30',
  pausable: true,
}

const wrapperFor = (spy: FetchSpy) =>
  function Wrapper({ children }: { children: ReactNode }) {
    return <ApiContext.Provider value={clientWith(spy)}>{children}</ApiContext.Provider>
  }

const planSpy = () => fetchSpy(async () => jsonReply(200, distinctPlan()))
const postBodies = (spy: FetchSpy) =>
  spy.mock.calls.map(([, init]) => JSON.parse(String(init?.body)) as Record<string, unknown>)

describe('usePlan', () => {
  it('starts idle and asks for nothing', () => {
    const spy = planSpy()
    const { result } = renderHook(() => usePlan(), { wrapper: wrapperFor(spy) })
    expect(result.current.status).toBe('idle')
    expect(result.current.response).toBeNull()
    expect(result.current.selected).toBeNull()
    expect(result.current.alpha).toBe(0.5)
    expect(spy).not.toHaveBeenCalled()
  })

  it('posts the form body with the current alpha and keeps the answer', async () => {
    const spy = planSpy()
    const { result } = renderHook(() => usePlan(), { wrapper: wrapperFor(spy) })
    act(() => result.current.submit(BODY))
    expect(result.current.status).toBe('loading')
    await waitFor(() => expect(result.current.status).toBe('ready'))
    expect(postBodies(spy)).toEqual([{ ...BODY, alpha: 0.5 }])
    expect(spy.mock.calls[0][1]?.method).toBe('POST')
    expect(result.current.selected?.alpha).toBe(0.5)
  })

  it('picks the Pareto entry for the slider on the client, without a request', async () => {
    const spy = planSpy()
    const { result } = renderHook(() => usePlan(), { wrapper: wrapperFor(spy) })
    act(() => result.current.submit(BODY))
    await waitFor(() => expect(result.current.status).toBe('ready'))
    spy.mockClear()

    act(() => result.current.setAlpha(0.8))
    expect(result.current.alpha).toBe(0.8)
    expect(result.current.selected?.alpha).toBe(0.8)
    expect(result.current.selected).toBe(result.current.response?.pareto[8])
    act(() => result.current.setAlpha(0.30000000000000004))
    expect(result.current.selected?.alpha).toBe(0.3)
    expect(spy).not.toHaveBeenCalled()
  })

  it('sends the slider position with the next plan', async () => {
    const spy = planSpy()
    const { result } = renderHook(() => usePlan(), { wrapper: wrapperFor(spy) })
    act(() => result.current.setAlpha(0.8))
    act(() => result.current.submit(BODY))
    await waitFor(() => expect(result.current.status).toBe('ready'))
    expect(postBodies(spy)[0].alpha).toBe(0.8)
  })

  it('shows the server message on an error, clears the old plan, and retries the same body', async () => {
    let calls = 0
    const spy = fetchSpy(async () => {
      calls += 1
      return calls === 1
        ? jsonReply(422, { error: 'deadline_too_soon', message: 'Pick a later deadline.' })
        : jsonReply(200, distinctPlan())
    })
    const { result } = renderHook(() => usePlan(), { wrapper: wrapperFor(spy) })
    act(() => result.current.submit(BODY))
    await waitFor(() => expect(result.current.status).toBe('error'))
    expect(result.current.error).toBe('Pick a later deadline.')
    expect(result.current.response).toBeNull()

    act(() => result.current.retry())
    await waitFor(() => expect(result.current.status).toBe('ready'))
    expect(result.current.error).toBeNull()
    expect(postBodies(spy)[1]).toEqual(postBodies(spy)[0])
  })

  it('refuses an answer with the wrong shape', async () => {
    const spy = fetchSpy(async () => jsonReply(200, { plan_id: 'p_x' }))
    const { result } = renderHook(() => usePlan(), { wrapper: wrapperFor(spy) })
    act(() => result.current.submit(BODY))
    await waitFor(() => expect(result.current.status).toBe('error'))
    expect(result.current.error).toMatch(/could not read/i)
  })

  it('ignores a slow answer that was overtaken by a newer request', async () => {
    const releases: (() => void)[] = []
    let n = 0
    const spy = fetchSpy(
      () =>
        new Promise<Response>((resolve) => {
          const mine = ++n
          releases.push(() =>
            resolve(jsonReply(200, distinctPlan({ plan_id: mine === 1 ? 'p_old' : 'p_new' }))),
          )
        }),
    )
    const { result } = renderHook(() => usePlan(), { wrapper: wrapperFor(spy) })
    act(() => result.current.submit(BODY))
    act(() => result.current.submit({ ...BODY, gpu_count: 4 }))
    await waitFor(() => expect(releases).toHaveLength(2))
    await act(async () => {
      releases[1]()
    })
    await waitFor(() => expect(result.current.response?.plan_id).toBe('p_new'))
    await act(async () => {
      releases[0]()
    })
    expect(result.current.response?.plan_id).toBe('p_new')
  })

  it('cancels the request that is still running when the page goes away', async () => {
    let seen: AbortSignal | null | undefined
    const spy = fetchSpy((_input, init) => {
      seen = init?.signal
      return new Promise<Response>(() => {})
    })
    const { result, unmount } = renderHook(() => usePlan(), { wrapper: wrapperFor(spy) })
    act(() => result.current.submit(BODY))
    await waitFor(() => expect(seen).toBeDefined())
    expect(seen?.aborted).toBe(false)
    unmount()
    expect(seen?.aborted).toBe(true)
  })

  it('retry with nothing to retry does nothing', () => {
    const spy = planSpy()
    const { result } = renderHook(() => usePlan(), { wrapper: wrapperFor(spy) })
    act(() => result.current.retry())
    expect(spy).not.toHaveBeenCalled()
  })
})
