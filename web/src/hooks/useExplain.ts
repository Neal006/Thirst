import { useCallback, useRef, useState } from 'react'
import { useApi } from '../api/context'
import { checked, errorMessage, isAborted } from '../api/errors'
import { isExplainResponse } from '../api/guards'

export type ExplainStatus = 'idle' | 'loading' | 'ready' | 'error'

interface ExplainState {
  status: ExplainStatus
  response: ExplainResponse | null
  error: string | null
}

interface ExplainResponse {
  explanation: string
  source: string
  note: string | null
  form: Record<string, any> | null
}

const INITIAL: ExplainState = {
  status: 'idle',
  response: null,
  error: null,
}

export function useExplain() {
  const api = useApi()
  const [state, setState] = useState<ExplainState>(INITIAL)
  const requestId = useRef(0)
  const controller = useRef<AbortController | null>(null)

  const run = useCallback((text: string) => {
    controller.current?.abort()
    const id = ++requestId.current
    const abort = new AbortController()
    controller.current = abort
    setState({ status: 'loading', response: null, error: null })
    api
      .post<unknown>('/explain', { text }, abort.signal)
      .then((data) => {
        const resp = checked(isExplainResponse, data)
        if (id === requestId.current) {
          setState({ status: 'ready', response: resp, error: null })
        }
      })
      .catch((error: unknown) => {
        if (id !== requestId.current || isAborted(error)) return
        setState({ status: 'error', response: null, error: errorMessage(error) })
      })
  }, [api])

  const retry = useCallback(() => {
    // no automatic retry payload stored; caller should re‑invoke run if needed
  }, [])

  return { ...state, explain: run, retry }
}
