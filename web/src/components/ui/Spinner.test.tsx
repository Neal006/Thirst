import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { Spinner } from './Spinner'

describe('Spinner', () => {
  it('shows what is loading in a polite status region', () => {
    render(<Spinner label="Planning…" />)
    const status = screen.getByRole('status')
    expect(status).toHaveTextContent('Planning…')
    expect(status).toHaveAttribute('aria-live', 'polite')
  })

  it('puts the text into the status region after the region is in the page, so it is announced', () => {
    const observer = new MutationObserver(() => {})
    observer.observe(document.body, { childList: true, subtree: true, characterData: true })
    render(<Spinner label="Loading the board…" />)
    const records = observer.takeRecords()
    observer.disconnect()
    const region = screen.getByRole('status')
    // A record that added the text to the region itself: it was filled in after it existed.
    const filledLater = records.some(
      (r) => r.target === region && Array.from(r.addedNodes).some((n) => n.textContent === 'Loading the board…'),
    )
    expect(filledLater).toBe(true)
  })

  it('announces a new label when the text changes', () => {
    const { rerender } = render(<Spinner label="Planning…" />)
    rerender(<Spinner label="Still planning…" />)
    expect(screen.getByRole('status')).toHaveTextContent('Still planning…')
  })

  it('hides the skeleton bars from screen readers and marks the card busy', () => {
    const { container } = render(<Spinner label="Planning…" lines={4} />)
    const bars = container.querySelectorAll('.skeleton')
    expect(bars).toHaveLength(4)
    bars.forEach((bar) => expect(bar).toHaveAttribute('aria-hidden', 'true'))
    expect(container.firstElementChild).toHaveAttribute('aria-busy', 'true')
  })
})
