import { useCallback, useEffect, useRef, useState } from 'react'
import type { ApiClient } from '../api/client'
import { useApi } from '../api/context'
import { errorMessage, isAborted } from '../api/errors'

export type Loadable<T> =
  | { status: 'loading' }
  | { status: 'ready'; data: T }
  | { status: 'error'; message: string }

const LOADING = { status: 'loading' } as const

type Loader<T> = (api: ApiClient, signal: AbortSignal) => Promise<T>

interface Settled<T> {
  requestKey: string
  value: Loadable<T>
}

/**
 * Runs `load` when `key` or the client changes (or after `reload`). The result belongs to the
 * key it was made for, so a stale answer is never shown for a new key. `load` is kept in a ref and
 * read when the request starts, so a caller that passes a new function every render cannot make
 * it loop: put everything the request depends on into `key`.
 */
export function useLoad<T>(load: Loader<T>, key: string) {
  const api = useApi()
  const [attempt, setAttempt] = useState(0)
  const [settled, setSettled] = useState<Settled<T> | null>(null)
  const requestKey = `${key}#${attempt}`
  const loadRef = useRef(load)

  // Declared before the request effect, so the request below sees this render's `load`.
  useEffect(() => {
    loadRef.current = load
  })

  useEffect(() => {
    const controller = new AbortController()
    loadRef.current(api, controller.signal)
      .then((data) => {
        if (!controller.signal.aborted) {
          setSettled({ requestKey, value: { status: 'ready', data } })
        }
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted || isAborted(error)) return
        setSettled({ requestKey, value: { status: 'error', message: errorMessage(error) } })
      })
    return () => controller.abort()
  }, [api, requestKey])

  const reload = useCallback(() => setAttempt((n) => n + 1), [])
  const state: Loadable<T> = settled?.requestKey === requestKey ? settled.value : LOADING
  return { state, reload }
}
