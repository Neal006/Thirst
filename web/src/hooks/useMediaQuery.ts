import { useCallback, useSyncExternalStore } from 'react'

export const PHONE_QUERY = '(max-width: 639px)'

const canMatch = (): boolean => typeof window !== 'undefined' && typeof window.matchMedia === 'function'

/** True while the media query matches. False where matchMedia does not exist (tests, old browsers). */
export function useMediaQuery(query: string): boolean {
  const subscribe = useCallback(
    (notify: () => void) => {
      if (!canMatch()) return () => {}
      const list = window.matchMedia(query)
      list.addEventListener('change', notify)
      return () => list.removeEventListener('change', notify)
    },
    [query],
  )
  const snapshot = useCallback(() => (canMatch() ? window.matchMedia(query).matches : false), [query])
  return useSyncExternalStore(subscribe, snapshot, () => false)
}
