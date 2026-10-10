import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import type { SiteResponse } from '../api/types'
import { ScoreBreakdown } from './ScoreBreakdown'

const GOOD: SiteResponse['score'] = {
  value: 62,
  provisional: true,
  badge: null,
  A: 31.25,
  B: 'not_rated',
  C: 12,
  C_parts: { measured_share: 7.5, coverage: 2.5, public: 2 },
  flex_share: 0.5,
  reason: null,
}

const show = (score: SiteResponse['score']) =>
  render(
    <MemoryRouter>
      <ScoreBreakdown score={score} />
    </MemoryRouter>,
  )

describe('ScoreBreakdown numbers', () => {
  it('shows one decimal for the parts', () => {
    show(GOOD)
    expect(screen.getByText('31.3 of 50')).toBeInTheDocument()
    expect(screen.getByText('12.0 of 20')).toBeInTheDocument()
    expect(screen.getByText(/Measured share of energy: 7\.5 of 10/)).toBeInTheDocument()
  })

  it.each([
    ['NaN', Number.NaN],
    ['Infinity', Number.POSITIVE_INFINITY],
    ['undefined', undefined as unknown as number],
  ])('prints -- instead of a fake 0.0 when a part is %s', (_name, bad) => {
    show({ ...GOOD, A: bad, C: bad, C_parts: { measured_share: bad, coverage: bad, public: bad } })
    expect(screen.getByText('-- of 50')).toBeInTheDocument()
    expect(screen.getByText('-- of 20')).toBeInTheDocument()
    expect(screen.getByText(/Measured share of energy: -- of 10/)).toBeInTheDocument()
    expect(screen.getByText(/Coverage you declared: -- of 5/)).toBeInTheDocument()
    expect(screen.getByText(/Public site: -- of 5/)).toBeInTheDocument()
    expect(document.body).not.toHaveTextContent(/0\.0|NaN|undefined|Infinity/)
  })
})

describe('ScoreBreakdown badge ladder', () => {
  const steps = [
    { name: 'bronze', at: 45 },
    { name: 'silver', at: 60 },
    { name: 'gold', at: 75 },
    { name: 'platinum', at: 90 },
  ]

  it('says how many points to the next badge', () => {
    render(<MemoryRouter><ScoreBreakdown score={{ ...GOOD, value: 72.4 }} steps={steps} /></MemoryRouter>)
    expect(screen.getByText(/points to/i)).toHaveTextContent('3 points to gold')
  })

  it('leaves the ladder out without thresholds', () => {
    render(<MemoryRouter><ScoreBreakdown score={{ ...GOOD, value: 72.4 }} /></MemoryRouter>)
    expect(screen.queryByText(/points to/i)).toBeNull()
  })
})
