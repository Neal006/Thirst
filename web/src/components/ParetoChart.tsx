import { useMemo } from 'react'
import {
  CartesianGrid,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  type TooltipContentProps,
} from 'recharts'
import type { ParetoEntry, PlanTags } from '../api/types'
import { formatAmount, formatClock } from '../lib/format'
import { alphaText, snapAlpha } from '../lib/planView'
import { ChartTooltip } from './ChartTooltip'
import { TagChip } from './TagChip'

interface ParetoChartProps {
  entries: readonly ParetoEntry[]
  tags: PlanTags
  selectedAlpha: number
  /** Called with the alpha of a clicked dot, so the slider can follow. */
  onSelect: (alpha: number) => void
}

interface Dot {
  x: number
  y: number
  alpha: number
  start: string
  level: string
}

const HEIGHT = 260
const INITIAL = { width: 640, height: HEIGHT }
const SELECTED_RADIUS = 9
const DOT_RADIUS = 5

const isDot = (value: unknown): value is Dot =>
  typeof value === 'object' && value !== null && typeof (value as Dot).alpha === 'number'

/** F4: the 11 trade-offs between water and carbon. The first chart to cut if time runs short. */
export function ParetoChart({ entries, tags, selectedAlpha, onSelect }: ParetoChartProps) {
  const selected = snapAlpha(selectedAlpha)
  const dots = useMemo<Dot[]>(
    () =>
      entries.map((e) => ({
        x: e.point.W_l,
        y: e.point.C_kg,
        alpha: e.alpha,
        start: e.start,
        level: e.level_summary,
      })),
    [entries],
  )

  const tooltip = ({ active, payload }: TooltipContentProps) => {
    const dot: unknown = payload[0]?.payload
    if (!active || !isDot(dot)) return null
    return (
      <ChartTooltip
        title={alphaText(dot.alpha)}
        lines={[
          { label: 'Stress-weighted water', value: formatAmount(dot.x, 'L'), tag: tags.water },
          { label: 'CO₂', value: formatAmount(dot.y, 'kg'), tag: tags.co2 },
          { label: 'Start', value: formatClock(dot.start), tag: 'design_choice' },
          { label: 'GPU power', value: dot.level, tag: 'design_choice' },
        ]}
      />
    )
  }

  return (
    <figure className="chart-figure">
      <div
        className="chart-box"
        role="img"
        aria-label="Scatter chart of stress-weighted water against CO₂ for the 11 slider positions"
      >
        <ResponsiveContainer width="100%" height={HEIGHT} initialDimension={INITIAL}>
          <ScatterChart margin={{ top: 8, right: 16, bottom: 20, left: 4 }}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis type="number" dataKey="x" name="Stress-weighted water" domain={['auto', 'auto']} tick={{ fontSize: 11 }} label={{ value: 'stress-weighted litres', position: 'insideBottom', offset: -10, fontSize: 11 }} />
            <YAxis type="number" dataKey="y" name="CO₂" domain={['auto', 'auto']} width={44} tick={{ fontSize: 11 }} label={{ value: 'kg CO₂', angle: -90, position: 'insideLeft', fontSize: 11 }} />
            <Tooltip content={tooltip} cursor={false} />
            <Scatter
              data={dots}
              isAnimationActive={false}
              shape={({ cx, cy, index }) => {
                const dot = dots[index ?? -1]
                if (!dot || typeof cx !== 'number' || typeof cy !== 'number') return <g />
                const isSelected = dot.alpha === selected
                return (
                  <circle
                    className="pareto-dot"
                    data-alpha={dot.alpha}
                    data-selected={isSelected}
                    cx={cx}
                    cy={cy}
                    r={isSelected ? SELECTED_RADIUS : DOT_RADIUS}
                    fill="var(--water)"
                    fillOpacity={isSelected ? 1 : 0.55}
                    stroke={isSelected ? 'var(--level-line)' : 'none'}
                    strokeWidth={3}
                    cursor="pointer"
                    onClick={() => onSelect(dot.alpha)}
                  />
                )
              }}
            />
          </ScatterChart>
        </ResponsiveContainer>
      </div>
      <figcaption>
        Each dot is one slider position. Closer to the bottom left is better for both water and
        carbon; click a dot or move the slider to choose. Values are{' '}
        <TagChip tag={tags.water} />.
      </figcaption>
    </figure>
  )
}
