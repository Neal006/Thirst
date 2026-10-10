import { useEffect } from 'react'

const SUFFIX = 'Thirst'

/** Sets the browser tab title for the page, so screen readers hear where they are. */
export function usePageTitle(title: string): void {
  useEffect(() => {
    document.title = title ? `${title} - ${SUFFIX}` : SUFFIX
  }, [title])
}
