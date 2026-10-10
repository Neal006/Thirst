import type { PlanTags } from '../api/types'
import { formatNumber } from '../lib/format'
import type { ChartSummary } from '../lib/planView'
import { tagInfo } from '../lib/tags'

interface ChartDataTableProps {
  summary: ChartSummary
  tags: Pick<PlanTags, 'water' | 'co2'>
}

/**
 * The plan chart as text for screen readers (visually hidden). The units are in the column
 * headings and the tags are named in the caption, so no cell holds a bare number with a unit.
 */
export function ChartDataTable({ summary, tags }: ChartDataTableProps) {
  return (
    <div className="visually-hidden">
      <p>{summary.text}</p>
      <table>
        <caption>
          {`Hourly data behind the chart. Water is ${tagInfo(tags.water).label}; CO₂ is ${tagInfo(tags.co2).label}.`}
        </caption>
        <thead>
          <tr>
            <th scope="col">Hour</th>
            <th scope="col">Water used on site (L per kWh)</th>
            <th scope="col">Water from the grid (L per kWh)</th>
            <th scope="col">CO₂ (kg per kWh)</th>
            <th scope="col">GPU power</th>
          </tr>
        </thead>
        <tbody>
          {summary.rows.map((row) => (
            <tr key={row.time}>
              <th scope="row">{row.time}</th>
              <td>{formatNumber(row.direct)}</td>
              <td>{formatNumber(row.grid)}</td>
              <td>{formatNumber(row.co2)}</td>
              <td data-kind="setting">{row.power}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
