import { useCallback, useRef, useState } from 'react'
import { useApi } from '../api/context'
import { checked, errorMessage, isAborted } from '../api/errors'
import { isPlanResponse } from '../api/guards'
import type { ParetoEntry, PlanRequestBody, PlanResponse } from '../api/types'
import { selectPareto } from '../lib/format'
import { snapAlpha } from '../lib/planView'

export type PlanStatus = 'idle' | 'loading' | 'ready' | 'error'
export type PlanController = ReturnType<typeof usePlan>

interface PlanState {
  status: PlanStatus
  response: PlanResponse | null
  error: string | null
  alpha: number
  lastBody: PlanRequestBody | null
}

const INITIAL: PlanState = {
  status: 'idle',
  response: null,
  error: null,
  alpha: 0.5,
  lastBody: null,
}

/**
 * The plan the person asked for. `/plan` is called when the form is submitted, never when the
 * slider moves: the slider only picks another of the 11 Pareto entries already in the answer.
 */
export function usePlan() {
  const api = useApi()
  const [state, setState] = useState<PlanState>(INITIAL)
  const alphaRef = useRef(INITIAL.alpha)
  const requestId = useRef(0)
  const controller = useRef<AbortController | null>(null)

  const run = useCallback(
    (body: PlanRequestBody) => {
      controller.current?.abort()
      const mine = ++requestId.current
      const abort = new AbortController()
      controller.current = abort
      setState((s) => ({ ...s, status: 'loading', response: null, error: null, lastBody: body }))
      api
        .post<unknown>('/plan', { ...body, alpha: alphaRef.current }, abort.signal)
        .then((data) => {
          const response = checked(isPlanResponse, data)
          if (mine === requestId.current) {
            setState((s) => ({ ...s, status: 'ready', response, error: null }))
          }
        })
        .catch((error: unknown) => {
          if (mine !== requestId.current || isAborted(error)) return
          setState((s) => ({ ...s, status: 'error', response: null, error: errorMessage(error) }))
        })
    },
    [api],
  )

  const setAlpha = useCallback((value: number) => {
    const alpha = snapAlpha(value)
    alphaRef.current = alpha
    setState((s) => ({ ...s, alpha }))
  }, [])

  const retry = useCallback(() => {
    if (state.lastBody) run(state.lastBody)
  }, [run, state.lastBody])

  const selected: ParetoEntry | null = state.response
    ? selectPareto(state.response.pareto, state.alpha)
    : null

  return {
    status: state.status,
    response: state.response,
    error: state.error,
    alpha: state.alpha,
    selected,
    submit: run,
    retry,
    setAlpha,
  }
}
