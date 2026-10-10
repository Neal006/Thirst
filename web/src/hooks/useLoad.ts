import { useCallback, useEffect, useState } from 'react'
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
 * Runs `load` when it, `key` or the client changes (or after `reload`). The result belongs to the
 * key it was made for, so a stale answer is never shown for a new key. Wrap `load` in useCallback
 * (or define it outside the component) so it only changes with `key`.
 */
export function useLoad<T>(load: Loader<T>, key: string) {
  const api = useApi()
  const [attempt, setAttempt] = useState(0)
  const [settled, setSettled] = useState<Settled<T> | null>(null)
  const requestKey = `${key}#${attempt}`

  useEffect(() => {
    const controller = new AbortController()
    load(api, controller.signal)
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
  }, [api, load, requestKey])

  const reload = useCallback(() => setAttempt((n) => n + 1), [])
  const state: Loadable<T> = settled?.requestKey === requestKey ? settled.value : LOADING
  return { state, reload }
}
