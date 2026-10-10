import { useId } from 'react'
import { Link } from 'react-router-dom'
import type { FactorStatus } from '../api/types'
import { tagInfo } from '../lib/tags'

interface TagChipProps {
  tag: FactorStatus
  /** A factor id on the Assumptions page; without it the chip links to the status legend. */
  factor?: string
}

export function TagChip({ tag, factor }: TagChipProps) {
  const info = tagInfo(tag)
  const helpId = useId()
  return (
    <>
      <Link
        to={`/assumptions#${factor ?? info.anchor}`}
        className={info.className}
        aria-describedby={helpId}
      >
        {info.label}
      </Link>
      <span id={helpId} className="visually-hidden">
        {info.help}
      </span>
    </>
  )
}
