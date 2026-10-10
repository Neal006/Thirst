import { useEffect } from 'react'
import { useLocation } from 'react-router-dom'
import type { AssumptionRow } from '../api/types'
import { plainNumber, rangeText, safeUrl, statusNote, type FactorGroup } from '../lib/assumptionsView'
import { TagChip } from './TagChip'

function targetId(hash: string): string {
  try {
    return decodeURIComponent(hash.replace(/^#/, ''))
  } catch {
    return ''
  }
}

function Source({ row }: { row: AssumptionRow }) {
  const href = safeUrl(row.source_url)
  return href ? (
    <a href={href} target="_blank" rel="noopener noreferrer">
      {row.source}
    </a>
  ) : (
    <>{row.source}</>
  )
}

function FactorRow({ row, targeted }: { row: AssumptionRow; targeted: boolean }) {
  const spread = rangeText(row)
  const note = statusNote(row)
  return (
    <tr id={row.id} className={targeted ? 'is-target' : undefined}>
      <td data-label="Name">{row.label}</td>
      <td data-label="Value">
        <strong>{plainNumber(row.value)}</strong>
        {spread ? <span className="stat-label">{spread}</span> : null}
      </td>
      <td data-label="Unit">{row.unit}</td>
      <td data-label="Status">
        <TagChip tag={row.status} />
        {note ? <span className="stat-label">{note}</span> : null}
      </td>
      <td data-label="Source"><Source row={row} /></td>
    </tr>
  )
}

/** One group of factors. The row named in the address (#factor-id) is highlighted and scrolled to. */
export function FactorTable({ group }: { group: FactorGroup }) {
  const { hash } = useLocation()
  const target = targetId(hash)
  const hasTarget = group.rows.some((r) => r.id === target)

  useEffect(() => {
    if (!hasTarget) return
    const el = document.getElementById(target)
    if (el && typeof el.scrollIntoView === 'function') el.scrollIntoView({ block: 'center' })
  }, [hasTarget, target])

  return (
    <section className="card" aria-labelledby={`group-${group.id}`}>
      <h2 id={`group-${group.id}`}>{group.label}</h2>
      <table className="data-table cards-on-phone">
        <thead>
          <tr>
            <th scope="col">Name</th>
            <th scope="col">Value</th>
            <th scope="col">Unit</th>
            <th scope="col">Status</th>
            <th scope="col">Source</th>
          </tr>
        </thead>
        <tbody>
          {group.rows.map((row) => (
            <FactorRow key={row.id} row={row} targeted={row.id === target} />
          ))}
        </tbody>
      </table>
    </section>
  )
}
