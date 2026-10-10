import type { FactorStatus } from '../api/types'
import { formatAmount } from '../lib/format'
import { TagChip } from './TagChip'

interface AmountProps {
  value: number
  /** "kWh", "L", "kg" or a word such as "person-days". */
  unit: string
  tag: FactorStatus
  /** What the number is, for screen readers. */
  label?: string
}

/**
 * One central value with its unit and tag. Receipts and boards only carry central values (D29);
 * anything that has a low-to-high range goes through Range instead.
 */
export function Amount({ value, unit, tag, label }: AmountProps) {
  return (
    <span className="range">
      {label ? <span className="visually-hidden">{label}: </span> : null}
      <span className="range-value">{formatAmount(value, unit)}</span> <TagChip tag={tag} />
    </span>
  )
}
