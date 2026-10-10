interface SpinnerProps {
  /** What is loading, in plain words ("Planning…"). */
  label: string
  lines?: number
}

/** A grey skeleton with a status line for screen readers. */
export function Spinner({ label, lines = 3 }: SpinnerProps) {
  return (
    <div className="card" role="status" aria-live="polite">
      <p>{label}</p>
      {Array.from({ length: lines }, (_, i) => (
        <span key={i} className="skeleton" aria-hidden="true" />
      ))}
    </div>
  )
}
