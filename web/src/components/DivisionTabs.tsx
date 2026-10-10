import { DIVISIONS } from '../lib/divisions'

interface DivisionTabsProps {
  value: string
  onChange: (division: string) => void
}

/** Size groups (US6). Pressing one changes the board; the address keeps the choice. */
export function DivisionTabs({ value, onChange }: DivisionTabsProps) {
  return (
    <div className="tab-group" role="group" aria-label="Division">
      {DIVISIONS.map((d) => (
        <button
          key={d.id}
          type="button"
          className="btn"
          aria-pressed={d.id === value}
          onClick={() => onChange(d.id)}
        >
          {d.label}
        </button>
      ))}
    </div>
  )
}
