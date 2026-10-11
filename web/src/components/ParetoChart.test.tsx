import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
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

  it('hides the drawing from assistive technology and has no mouse-only control inside it', async () => {
    const { container } = setup()
    await waitFor(() => expect(dots(container)).toHaveLength(11))
    const box = container.querySelector('.chart-box')
    expect(box).toHaveAttribute('aria-hidden', 'true')
    // Nothing in the drawing takes keyboard focus: the slider is the keyboard path.
    expect(box?.querySelectorAll('[tabindex]:not([tabindex="-1"]), button, a, input')).toHaveLength(0)
    expect(screen.queryByRole('img', { name: /scatter chart/i })).not.toBeInTheDocument()
  })

  it('gives the same 11 choices as a table with the numbers, and points to the slider', () => {
    setup()
    const table = screen.getByRole('table', { name: /slider positions/i })
    const rows = within(table).getAllByRole('row').slice(1)
    expect(rows).toHaveLength(11)
    expect(rows[0]).toHaveTextContent('Water 0%, carbon 100%')
    expect(rows[10]).toHaveTextContent('Water 100%, carbon 0%')
    expect(rows[3]).toHaveTextContent('43') // stress-weighted litres of entry 3
    expect(within(table).getByRole('columnheader', { name: /stress-weighted water \(L\)/i })).toBeInTheDocument()
    expect(screen.getByText(/use the slider/i)).toBeInTheDocument()
  })

  it('marks the selected position in the table', () => {
    setup(0.3)
    const table = screen.getByRole('table', { name: /slider positions/i })
    const current = within(table).getAllByRole('row').filter((r) => r.getAttribute('aria-current') === 'true')
    expect(current).toHaveLength(1)
    expect(current[0]).toHaveTextContent('Water 30%, carbon 70%')
  })

  describe('dots that sit on top of each other', () => {
    function coincident(selectedAlpha: number) {
      const plan = distinctPlan()
      // Entries 3, 4 and 5 give exactly the same plan, so their dots are drawn on one spot.
      // A spot no other fixture entry uses (entry 10 sits at 50 / 4).
      const same = { W_l: 60, C_kg: 3 }
      const pareto = plan.pareto.map((e, i) => (i >= 3 && i <= 5 ? { ...e, point: same } : e))
      const onSelect = vi.fn<(alpha: number) => void>()
      const view = render(
        <MemoryRouter>
          <ParetoChart entries={pareto} tags={plan.tags} selectedAlpha={selectedAlpha} onSelect={onSelect} />
        </MemoryRouter>,
      )
      return { ...view, onSelect }
    }

    it('picks the position closest to the current one, not whichever dot is on top', async () => {
      const { container, onSelect } = coincident(0.1)
      await waitFor(() => expect(dots(container)).toHaveLength(11))
      fireEvent.click(container.querySelector('.pareto-dot[data-alpha="0.5"]') as Element)
      expect(onSelect).toHaveBeenCalledWith(0.3)
    })

    it('picks the other end of the pile when the current position is above it', async () => {
      const { container, onSelect } = coincident(0.9)
      await waitFor(() => expect(dots(container)).toHaveLength(11))
      fireEvent.click(container.querySelector('.pareto-dot[data-alpha="0.3"]') as Element)
      expect(onSelect).toHaveBeenCalledWith(0.5)
    })

    it('still picks the clicked position when no other dot is on the same spot', async () => {
      const { container, onSelect } = coincident(0.1)
      await waitFor(() => expect(dots(container)).toHaveLength(11))
      fireEvent.click(container.querySelector('.pareto-dot[data-alpha="0.8"]') as Element)
      expect(onSelect).toHaveBeenCalledWith(0.8)
    })
  })
})
