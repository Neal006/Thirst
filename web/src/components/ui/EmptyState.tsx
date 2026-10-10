import type { ReactNode } from 'react'

interface EmptyStateProps {
  title: string
  children?: ReactNode
}

/** Shown when there is nothing to list yet. Says what to do next. */
export function EmptyState({ title, children }: EmptyStateProps) {
  return (
    <div className="card">
      <h2>{title}</h2>
      {children}
    </div>
  )
}
