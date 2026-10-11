import { useEffect, useState } from 'react'

interface SpinnerProps {
  /** What is loading, in plain words ("Planning…"). */
  label: string
  lines?: number
}

/**
 * A grey skeleton with a status line for screen readers. The status region is in the page first
 * and the text is put into it right after, because screen readers announce changes to a live
 * region, not a region that arrives with its text.
 */
export function Spinner({ label, lines = 3 }: SpinnerProps) {
  const [announced, setAnnounced] = useState('')
  useEffect(() => {
    setAnnounced(label)
  }, [label])
  return (
    <div className="card" aria-busy="true">
      <p role="status" aria-live="polite">
        {announced}
      </p>
      {Array.from({ length: lines }, (_, i) => (
        <span key={i} className="skeleton" aria-hidden="true" />
      ))}
    </div>
  )
}
