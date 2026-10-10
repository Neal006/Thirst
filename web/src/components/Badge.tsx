interface BadgeProps {
  badge: string | null
}

const capitalise = (text: string): string => text.charAt(0).toUpperCase() + text.slice(1)

export function Badge({ badge }: BadgeProps) {
  return <span className="chip">{badge ? capitalise(badge) : 'No badge yet'}</span>
}
