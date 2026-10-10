interface BadgeProps {
  badge: string | null
}

const KNOWN = new Set(['platinum', 'gold', 'silver', 'bronze'])

const capitalise = (text: string): string => text.charAt(0).toUpperCase() + text.slice(1)

export function Badge({ badge }: BadgeProps) {
  const key = badge?.toLowerCase() ?? ''
  const tone = KNOWN.has(key) ? `badge-${key}` : 'badge-none'
  return <span className={`badge ${tone}`}>{badge ? capitalise(badge) : 'No badge yet'}</span>
}
