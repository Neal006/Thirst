import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { AlphaSlider } from './AlphaSlider'

describe('AlphaSlider', () => {
  it('is a labelled range from 0 to 1 in steps of 0.1', () => {
    render(<AlphaSlider value={0.5} onChange={() => {}} />)
    const slider = screen.getByRole('slider', { name: /save carbon.*save water/i })
    expect(slider).toHaveAttribute('min', '0')
    expect(slider).toHaveAttribute('max', '1')
    expect(slider).toHaveAttribute('step', '0.1')
    expect(slider).toHaveValue('0.5')
  })

  it('reads the position as water and carbon shares for screen readers', () => {
    const { rerender } = render(<AlphaSlider value={0.5} onChange={() => {}} />)
    expect(screen.getByRole('slider')).toHaveAttribute('aria-valuetext', 'Water 50%, carbon 50%')
    rerender(<AlphaSlider value={0.8} onChange={() => {}} />)
    expect(screen.getByRole('slider')).toHaveAttribute('aria-valuetext', 'Water 80%, carbon 20%')
  })

  it('describes the position in words next to the slider', () => {
    render(<AlphaSlider value={1} onChange={() => {}} />)
    expect(screen.getByText('Water only')).toBeInTheDocument()
  })

  it('reports each move as a value on the 0.1 grid', () => {
    const onChange = vi.fn()
    render(<AlphaSlider value={0.5} onChange={onChange} />)
    fireEvent.change(screen.getByRole('slider'), { target: { value: '0.8' } })
    expect(onChange).toHaveBeenCalledWith(0.8)
  })

  it('turns junk typed into the slider into a value on the grid', () => {
    const onChange = vi.fn()
    render(<AlphaSlider value={0.2} onChange={onChange} />)
    // The browser sanitises junk in a range input to its midpoint; the slider reports exactly that.
    fireEvent.change(screen.getByRole('slider'), { target: { value: 'abc' } })
    expect(onChange).toHaveBeenCalledTimes(1)
    expect(onChange).toHaveBeenCalledWith(0.5)
  })

  it('never reports NaN: a reading that is not a number falls back to the middle', () => {
    const onChange = vi.fn()
    render(<AlphaSlider value={0.2} onChange={onChange} />)
    const slider = screen.getByRole('slider')
    Object.defineProperty(slider, 'valueAsNumber', { configurable: true, get: () => Number.NaN })
    fireEvent.change(slider, { target: { value: '0.9' } })
    expect(onChange).toHaveBeenCalledTimes(1)
    expect(onChange).toHaveBeenCalledWith(0.5)
  })
})
