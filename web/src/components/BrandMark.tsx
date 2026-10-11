/** The Thirst mark: a drop with a meter line through it. Decorative, so screen readers skip it. */
export function BrandMark({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 32 32" aria-hidden="true" focusable="false">
      <path d="M16 3c4.9 6.3 8.5 10.9 8.5 15.3a8.5 8.5 0 0 1-17 0C7.5 13.9 11.1 9.3 16 3z" fill="#126e6b" />
      <rect x="6" y="19" width="20" height="3" fill="#f0b43c" />
    </svg>
  )
}
