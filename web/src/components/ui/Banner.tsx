import type { ReactNode } from 'react'

interface BannerProps {
  kind: 'error' | 'warn'
  children: ReactNode
  /** Label for an optional action button, such as "Try again". */
  actionLabel?: string
  onAction?: () => void
}

/** A message bar. Errors are announced at once; warnings are read politely. */
export function Banner({ kind, children, actionLabel, onAction }: BannerProps) {
  return (
    <div className={`banner banner-${kind}`} role={kind === 'error' ? 'alert' : 'status'}>
      <p>{children}</p>
      {actionLabel && onAction ? (
        <button type="button" className="btn" onClick={onAction}>
          {actionLabel}
        </button>
      ) : null}
    </div>
  )
}
