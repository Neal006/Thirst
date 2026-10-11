import type { ParetoEntry, PlanTags } from '../api/types'
import { formatClock, formatNumber } from '../lib/format'
import { alphaText, snapAlpha } from '../lib/planView'
import { tagInfo } from '../lib/tags'

interface ParetoTableProps {
  entries: readonly ParetoEntry[]
  tags: Pick<PlanTags, 'water' | 'co2'>
  selectedAlpha: number
}

/**
 * The Pareto chart as text (visually hidden): the 11 slider positions with their numbers. The
 * dots can only be clicked, so this table and the slider are the way in for a keyboard or a
 * screen reader. Units sit in the column headings, so no cell holds a bare number with a unit.
 */
export function ParetoTable({ entries, tags, selectedAlpha }: ParetoTableProps) {
  const selected = snapAlpha(selectedAlpha)
  return (
    <div className="visually-hidden">
      <p>Use the slider to choose a position. The same choices are listed here.</p>
      <table>
        <caption>
          {`The 11 slider positions. Water is ${tagInfo(tags.water).label}; CO₂ is ${tagInfo(tags.co2).label}.`}
        </caption>
        <thead>
          <tr>
            <th scope="col">Slider position</th>
            <th scope="col">Stress-weighted water (L)</th>
            <th scope="col">CO₂ (kg)</th>
            <th scope="col">Start</th>
            <th scope="col">GPU power</th>
          </tr>
        </thead>
        <tbody>
          {entries.map((entry) => (
            <tr key={entry.alpha} aria-current={entry.alpha === selected ? 'true' : undefined}>
              <th scope="row" data-kind="setting">
                {alphaText(entry.alpha)}
              </th>
              <td>{formatNumber(entry.point.W_l)}</td>
              <td>{formatNumber(entry.point.C_kg)}</td>
              <td>{formatClock(entry.start)}</td>
              <td data-kind="setting">{entry.level_summary}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
