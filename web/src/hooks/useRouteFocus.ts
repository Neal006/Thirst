import { useEffect, useRef, type RefObject } from 'react'
import { useLocation } from 'react-router-dom'

function targetFor(hash: string): HTMLElement | null {
  if (hash.length < 2) return null
  try {
    return document.getElementById(decodeURIComponent(hash.slice(1)))
  } catch {
    return null
  }
}

function focusElement(element: HTMLElement): void {
  // Headings and list items are not focusable by default; -1 lets a script focus them
  // without adding them to the tab order.
  if (!element.hasAttribute('tabindex')) element.setAttribute('tabindex', '-1')
  element.focus({ preventScroll: true })
}

/**
 * Client-side navigation neither scrolls to a #hash nor moves focus, so a keyboard or screen
 * reader user would stay on the link they used. After each change of address this scrolls to the
 * element the hash names and focuses it, or else focuses the new page's heading (or the main
 * area when there is none). The first page load is left alone: the browser starts at the top.
 */
export function useRouteFocus(mainRef: RefObject<HTMLElement | null>): void {
  // The query string is left out on purpose: the division tabs change it and keep their focus.
  const { pathname, hash } = useLocation()
  const previous = useRef<string | null>(null)

  useEffect(() => {
    const here = `${pathname}${hash}`
    const moved = previous.current !== null && previous.current !== here
    previous.current = here

    const target = targetFor(hash)
    if (target) {
      if (typeof target.scrollIntoView === 'function') target.scrollIntoView({ block: 'start' })
      if (moved) focusElement(target)
      return
    }
    if (!moved) return
    const main = mainRef.current
    const heading = main?.querySelector<HTMLElement>('h1')
    const next = heading ?? main
    if (next) focusElement(next)
  }, [pathname, hash, mainRef])
}
