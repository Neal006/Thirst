import type { ReactNode } from 'react'
import type { FactorStatus } from '../api/types'
import { tagInfo } from '../lib/tags'

export interface TooltipLine {
  label: string
  value: string
  tag: FactorStatus
}

interface ChartTooltipProps {
  title: string
  lines: readonly TooltipLine[]
  footer?: ReactNode
}

/** Tooltip body: every value with its tag (plain text, a tooltip cannot hold a link). */
export function ChartTooltip({ title, lines, footer }: ChartTooltipProps) {
  const rows = lines.map((line) => {
    const info = tagInfo(line.tag)
    return (
      <p key={line.label}>
        {line.label}: <strong>{line.value}</strong> <span className={info.className}>{info.label}</span>
      </p>
    )
  })
  return (
    <div className="chart-tooltip">
      <p>
        <strong>{title}</strong>
      </p>
      {rows}
      {footer}
    </div>
  )
}
