import type { FactorStatus } from '../api/types'
import { formatPercentRange, formatRange } from '../lib/format'
import { TagChip } from './TagChip'

interface RangeProps {
  range: readonly [number, number]
  /** "%" or a word such as "kg" or "person-days". */
  unit: string
  tag: FactorStatus
  /** What the number is, for screen readers ("stress-weighted water"). */
  label?: string
  factor?: string
}

/** A number is never shown bare: always a range, its unit and a tag chip (PRD G5). */
export function Range({ range, unit, tag, label, factor }: RangeProps) {
  const text = unit === '%' ? formatPercentRange(range) : formatRange(range, unit)
  return (
    <span className="range">
      {label ? <span className="visually-hidden">{label}: </span> : null}
      <span className="range-value">{text}</span> <TagChip tag={tag} factor={factor} />
    </span>
  )
}
