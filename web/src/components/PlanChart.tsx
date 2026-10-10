import { useMemo } from 'react'
import {
  Bar,
  ComposedChart,
  Legend,
  Line,
  ReferenceArea,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  type TooltipContentProps,
} from 'recharts'
import type { ParetoEntry, PlanResponse } from '../api/types'
import { PHONE_QUERY, useMediaQuery } from '../hooks/useMediaQuery'
import { formatAmount, formatClock, formatDay, paceBlocks } from '../lib/format'
import { buildChartData, buildSummary, deadlineSlot, lowWindows, type ChartPoint } from '../lib/planView'
import { ChartDataTable } from './ChartDataTable'
import { ChartTooltip } from './ChartTooltip'
import { TagChip } from './TagChip'

interface PlanChartProps {
  response: PlanResponse
  /** The Pareto entry the slider has selected: it sets the shading and the power line. */
  entry: ParetoEntry
}

const CHART_HEIGHT = 260
const INITIAL = { width: 640, height: CHART_HEIGHT }

function isPoint(value: unknown): value is ChartPoint {
  return typeof value === 'object' && value !== null && typeof (value as ChartPoint).slot === 'string'
}

const slotLabel = (slot: string): string => `${formatDay(slot)} ${formatClock(slot)}`

function tickLabel(slot: string): string {
  const clock = formatClock(slot)
  return clock === '00:00' ? `${formatDay(slot).split(' ')[0]} 00:00` : clock
}

/** F2: water and CO2 per kWh for the next 48 hours, with the selected plan on top. */
export function PlanChart({ response, entry }: PlanChartProps) {
  const phone = useMediaQuery(PHONE_QUERY)
  const data = useMemo(() => buildChartData(response.series, entry.series_overlay), [response.series, entry])
  const blocks = useMemo(() => paceBlocks(entry.series_overlay, 'run'), [entry])
  const deadline = deadlineSlot(response.series, response.inputs.deadline)
  const best = useMemo(() => lowWindows(response.series, response.submit_ts), [response.series, response.submit_ts])
  const summary = useMemo(() => buildSummary(response, entry), [response, entry])
  const { tags } = response

  const tooltip = ({ active, payload }: TooltipContentProps) => {
    const point: unknown = payload[0]?.payload
    if (!active || !isPoint(point)) return null
    return (
      <ChartTooltip
        title={slotLabel(point.slot)}
        lines={[
          { label: 'Water used on site', value: formatAmount(point.direct, 'L per kWh'), tag: tags.water },
          { label: 'Water from the grid', value: formatAmount(point.grid, 'L per kWh'), tag: tags.water },
          { label: 'CO₂', value: formatAmount(point.co2, 'kg per kWh'), tag: tags.co2 },
          { label: 'GPU power', value: point.levelPct > 0 ? `${point.levelPct}%` : 'off', tag: 'design_choice' },
        ]}
      />
    )
  }

  return (
    <figure className="chart-figure">
      <div className="chart-head">
        <h3>Next 48 hours</h3>
        <span className="chart-units">
          <span>bars: litres per kWh</span>
          <span>line: kg CO₂ per kWh</span>
        </span>
      </div>
      <div
        className="chart-box"
        role="img"
        aria-label="Chart of water and CO₂ per kWh over the next 48 hours, with your plan shaded in yellow"
      >
        <ResponsiveContainer width="100%" height={CHART_HEIGHT} initialDimension={INITIAL}>
          <ComposedChart data={data} margin={{ top: 8, right: 4, bottom: 0, left: 0 }}>
            <defs>
              <pattern id="plan-site-hatch" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
                <rect width="6" height="6" fill="#ffffff" />
                <line x1="0" y1="0" x2="0" y2="6" stroke="var(--sky)" strokeWidth="3" />
              </pattern>
            </defs>
            <XAxis dataKey="slot" interval={phone ? 5 : 2} tickFormatter={tickLabel} tick={{ fontSize: 12 }} />
            <YAxis yAxisId="water" width={40} tick={{ fontSize: 12 }} />
            <YAxis yAxisId="co2" orientation="right" width={40} tick={{ fontSize: 12 }} />
            <YAxis yAxisId="level" hide domain={[0, 100]} />
            <Tooltip content={tooltip} />
            <Legend wrapperStyle={{ fontSize: 13, color: 'var(--ink)' }} />
            {blocks.map((b) => (
              <ReferenceArea key={b.from} yAxisId="water" x1={data[b.from]?.slot} x2={data[b.to]?.slot} fill="var(--signal)" fillOpacity={0.55} />
            ))}
            <Bar yAxisId="water" stackId="water" dataKey="grid" name="Water from the grid" fill="var(--water)" fillOpacity={0.42} isAnimationActive={false} />
            <Bar yAxisId="water" stackId="water" dataKey="direct" name="Water used on site" fill="url(#plan-site-hatch)" stroke="var(--sky)" isAnimationActive={false} />
            <Line yAxisId="co2" dataKey="co2" name="CO₂" stroke="var(--carbon)" strokeWidth={3} dot={false} isAnimationActive={false} />
            <Line yAxisId="level" dataKey="levelPct" name="GPU power" type="stepAfter" stroke="var(--level-line)" strokeWidth={2} dot={false} isAnimationActive={false} />
            {deadline ? <ReferenceLine yAxisId="water" x={deadline} stroke="var(--deadline)" strokeDasharray="4 3" label={{ value: 'Deadline', fontSize: 12, position: 'insideTopRight', fill: 'var(--deadline)' }} /> : null}
          </ComposedChart>
        </ResponsiveContainer>
      </div>
      <ChartDataTable summary={summary} tags={tags} />
      <figcaption>
        {best.water && best.co2 ? (
          <>
            Lowest water hours: {best.water} <TagChip tag={tags.water} />; lowest CO₂ hours: {best.co2}{' '}
            <TagChip tag={tags.co2} />. The yellow shading is when your job runs.
          </>
        ) : (
          <>Not enough hours to name the best window.</>
        )}
      </figcaption>
    </figure>
  )
}
