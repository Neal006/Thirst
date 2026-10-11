import { useEffect, useRef } from 'react'

interface SpinnerProps {
  /** What is loading, in plain words ("Planning…"). */
  label: string
  lines?: number
}

/**
 * A grey skeleton with a status line for screen readers. The status region is in the page first
 * and the text is put into it right after, because screen readers announce changes to a live
 * region, not a region that arrives with its text. React renders the region empty and the effect
 * writes the text, so there is no second render.
 */
export function Spinner({ label, lines = 3 }: SpinnerProps) {
  const status = useRef<HTMLParagraphElement>(null)
  useEffect(() => {
    if (status.current) status.current.textContent = label
  }, [label])
  return (
    <div className="card" aria-busy="true">
      <p ref={status} role="status" aria-live="polite" />
      {Array.from({ length: lines }, (_, i) => (
        <span key={i} className="skeleton" aria-hidden="true" />
      ))}
    </div>
  )
}
