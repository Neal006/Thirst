import { DIVISIONS } from '../lib/divisions'

interface DivisionTabsProps {
  value: string
  onChange: (division: string) => void
}

/** Size groups (US6), drawn as weight classes that grow. Pressing one changes the board. */
export function DivisionTabs({ value, onChange }: DivisionTabsProps) {
  return (
    <div className="classes classes-pick" role="group" aria-label="Division">
      {DIVISIONS.map((d, i) => (
        <button
          key={d.id}
          type="button"
          className={d.id === value ? 'class is-here' : 'class'}
          style={{ '--i': i } as React.CSSProperties}
          aria-pressed={d.id === value}
          onClick={() => onChange(d.id)}
        >
          <span className="class-id" aria-hidden="true">
            {d.id}
          </span>
          <span className="class-label">{d.label}</span>
        </button>
      ))}
    </div>
  )
}
