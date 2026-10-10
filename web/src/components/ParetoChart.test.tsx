import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import { distinctPlan } from '../test/planFixture'
import { ParetoChart } from './ParetoChart'

function setup(selectedAlpha = 0.5) {
  const plan = distinctPlan()
  const onSelect = vi.fn<(alpha: number) => void>()
  const view = render(
    <MemoryRouter>
      <ParetoChart entries={plan.pareto} tags={plan.tags} selectedAlpha={selectedAlpha} onSelect={onSelect} />
    </MemoryRouter>,
  )
  return { ...view, plan, onSelect }
}

const dots = (container: HTMLElement) => container.querySelectorAll('.pareto-dot')

describe('ParetoChart', () => {
  it('draws one dot for each of the 11 slider positions', async () => {
    const { container } = setup()
    await waitFor(() => expect(dots(container)).toHaveLength(11))
  })

  it('makes the selected dot bigger and marks it', async () => {
    const { container } = setup(0.3)
    await waitFor(() => expect(dots(container)).toHaveLength(11))
    const selected = container.querySelector('.pareto-dot[data-selected="true"]')
    expect(selected).toHaveAttribute('data-alpha', '0.3')
    expect(container.querySelectorAll('.pareto-dot[data-selected="true"]')).toHaveLength(1)
    const radius = (el: Element | null) => Number(el?.getAttribute('r'))
    const other = container.querySelector('.pareto-dot[data-alpha="0.8"]')
    expect(radius(selected)).toBeGreaterThan(radius(other))
  })

  it('picks the slider position of the dot that was clicked', async () => {
    const { container, onSelect } = setup()
    await waitFor(() => expect(dots(container)).toHaveLength(11))
    const dot = container.querySelector('.pareto-dot[data-alpha="0.8"]')
    expect(dot).not.toBeNull()
    fireEvent.click(dot as Element)
    expect(onSelect).toHaveBeenCalledWith(0.8)
  })

  it('has a text summary with tags that tells how to use it', () => {
    setup()
    const caption = screen.getByText(/each dot is one slider position/i).closest('figcaption')
    expect(caption).toHaveTextContent(/closer to the bottom left/i)
    expect(caption?.querySelector('.tag')).not.toBeNull()
  })

  it('describes the chart as one image with a name', () => {
    setup()
    expect(screen.getByRole('img', { name: /stress-weighted water against CO₂/i })).toBeInTheDocument()
  })
})
