import { render, screen, waitFor, within } from '@testing-library/react'
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
    expect(caption).toHaveTextContent(/lowest water hours: .*\d\d:00 to .*\d\d:00/i)
    expect(caption).toHaveTextContent(/lowest CO₂ hours: .*\d\d:00 to .*\d\d:00/i)
  })

  describe('the lowest hours are named with their day when they are not on the submit day', () => {
    // The 48 hours run from Fri 9 Oct 21:00; the plan was made on Fri 9 Oct. Make Sun 11 Oct
    // 02:00 to 05:00 clearly the cheapest window for water and for CO2.
    const cheapOn = (plan: PlanResponse, from: string): PlanResponse => ({
      ...plan,
      series: plan.series.map((row) => {
        const cheap = ['02:00', '03:00', '04:00'].some((t) => row.slot.startsWith(`${from}T${t}`))
        return {
          ...row,
          direct_l_per_kwh: cheap ? 0.1 : 5,
          grid_l_per_kwh: cheap ? 0.1 : 5,
          co2_kg_per_kwh: cheap ? 0.1 : 0.9,
        }
      }),
    })

    it('says "Sun 11 Oct" for a window on the second day', () => {
      renderChart(cheapOn(distinctPlan(), '2026-10-11'))
      const caption = screen.getByText(/lowest water hours/i).closest('figcaption')
      expect(caption).toHaveTextContent('Lowest water hours: Sun 11 Oct 02:00 to 05:00')
      expect(caption).toHaveTextContent('lowest CO₂ hours: Sun 11 Oct 02:00 to 05:00')
    })

    it('leaves the day out for a window on the submit day', () => {
      const plan = distinctPlan({ submit_ts: '2026-10-10T08:30:00+05:30' })
      renderChart(cheapOn(plan, '2026-10-10'))
      const caption = screen.getByText(/lowest water hours/i).closest('figcaption')
      expect(caption).toHaveTextContent('Lowest water hours: 02:00 to 05:00')
    })
  })

  describe('the data is also available as text', () => {
    it('has a table with one row per hour, a unit in each column heading and the tags in words', () => {
      renderChart(distinctPlan())
      const table = screen.getByRole('table', { name: /hourly data behind the chart/i })
      expect(within(table).getAllByRole('row')).toHaveLength(49)
      expect(within(table).getByRole('columnheader', { name: /water used on site \(L per kWh\)/i })).toBeInTheDocument()
      expect(within(table).getByRole('columnheader', { name: /CO₂ \(kg per kWh\)/i })).toBeInTheDocument()
      expect(table).toHaveAccessibleName(/water is modelled.*CO₂ is modelled/i)
    })

    it('says in a sentence when the plan runs', () => {
      renderChart(distinctPlan())
      expect(screen.getByText(/your plan runs from/i)).toHaveTextContent(/48 hours from Fri 9 Oct 21:00/)
    })

    it('is outside the picture, so assistive technology can reach it', () => {
      renderChart(distinctPlan())
      const picture = screen.getByRole('img', { name: /water and CO₂ per kWh/i })
      expect(picture).not.toContainElement(screen.getByRole('table'))
    })

    it('follows the selected plan', () => {
      const plan = distinctPlan()
      const { rerender } = renderChart(plan, plan.pareto[0])
      const running = () => within(screen.getByRole('table')).queryAllByRole('cell', { name: /^\d+%$/ }).length
      const before = running()
      expect(before).toBeGreaterThan(0)
      rerender(
        <MemoryRouter>
          <PlanChart response={plan} entry={{ ...plan.pareto[0], series_overlay: plan.pareto[0].series_overlay.map((r) => ({ ...r, state: 'off' as const })) }} />
        </MemoryRouter>,
      )
      expect(running()).toBe(0)
    })
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
