import type { ReactNode } from 'react'

interface EmptyStateProps {
  title: string
  children?: ReactNode
  className?: string
}

/** Shown when there is nothing to list yet. Says what to do next. */
export function EmptyState({ title, children, className }: EmptyStateProps) {
  return (
    <div className={className ? `card ${className}` : 'card'}>
      <h2>{title}</h2>
      {children}
    </div>
  )
}
