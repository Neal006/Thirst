import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import type { ParetoEntry, PlanResponse } from '../api/types'
import { distinctPlan } from '../test/planFixture'
import { PlanChart } from './PlanChart'

function renderChart(response: PlanResponse, entry: ParetoEntry = response.chosen) {
  return render(
    <MemoryRouter>
      <PlanChart response={response} entry={entry} />
    </MemoryRouter>,
  )
}

describe('PlanChart', () => {
  it('has a text summary of the best hours for screen readers', () => {
    renderChart(distinctPlan())
    const caption = screen.getByText(/lowest water hours/i).closest('figcaption')
    expect(caption).toHaveTextContent(/lowest water hours: \d\d:00 to \d\d:00/i)
    expect(caption).toHaveTextContent(/lowest CO₂ hours: \d\d:00 to \d\d:00/i)
  })

  it('tags the summary with the water and CO2 tags of the plan', () => {
    const plan = distinctPlan({ tags: { ...distinctPlan().tags, co2: 'placeholder' } })
    renderChart(plan)
    const caption = screen.getByText(/lowest water hours/i).closest('figcaption')
    expect(caption?.querySelector('.tag-modelled')).not.toBeNull()
    expect(caption?.querySelector('.tag-placeholder')).not.toBeNull()
  })

  it('describes the chart as one image with a name', () => {
    renderChart(distinctPlan())
    expect(screen.getByRole('img', { name: /water and CO₂ per kWh over the next 48 hours/i })).toBeInTheDocument()
  })

  it('shades the run blocks of the selected plan and redraws for another one', async () => {
    const plan = distinctPlan()
    const { container, rerender } = renderChart(plan, plan.pareto[0])
    const shaded = () => container.querySelectorAll('.recharts-reference-area').length
    await waitFor(() => expect(shaded()).toBe(1))
    // Entry 8 pauses in the middle, so its run is two blocks.
    rerender(
      <MemoryRouter>
        <PlanChart response={plan} entry={plan.pareto[8]} />
      </MemoryRouter>,
    )
    await waitFor(() => expect(shaded()).toBe(2))
  })

  it('draws 48 hours of bars, the CO2 line, the power line and the deadline', async () => {
    const { container } = renderChart(distinctPlan())
    await waitFor(() => expect(container.querySelectorAll('.recharts-bar-rectangle')).toHaveLength(48))
    expect(container.querySelectorAll('.recharts-line-curve')).toHaveLength(2)
    expect(container.querySelectorAll('.recharts-reference-line')).toHaveLength(1)
    expect(container.querySelector('.recharts-legend-wrapper')).toHaveTextContent(/GPU power/)
  })

  it('shows no NaN or undefined when the series has bad numbers', () => {
    const plan = distinctPlan()
    const series = plan.series.map((row, i) => (i === 3 ? { ...row, grid_l_per_kwh: Number.NaN } : row))
    renderChart({ ...plan, series })
    expect(document.body).not.toHaveTextContent(/NaN|undefined|Infinity/)
  })
})
