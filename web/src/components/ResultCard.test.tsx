import { render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import type { ParetoEntry, PlanResponse } from '../api/types'
import { distinctPlan } from '../test/planFixture'
import { ResultCard } from './ResultCard'

function renderCard(response: PlanResponse, entry: ParetoEntry = response.chosen) {
  render(
    <MemoryRouter>
      <ResultCard response={response} entry={entry} />
    </MemoryRouter>,
  )
  return screen.getByRole('region', { name: /your plan/i })
}

describe('ResultCard', () => {
  it('says when to start, how fast, and when it is done', () => {
    const card = renderCard(distinctPlan())
    expect(card).toHaveTextContent('Start at 06:00')
    expect(card).toHaveTextContent('GPU at 85%')
    expect(card).toHaveTextContent('done by 13:10')
  })

  it('leaves the finish day out when the job ends on its start day', () => {
    expect(renderCard(distinctPlan())).toHaveTextContent(/done by 13:10\./)
  })

  it('names the finish day when the job ends on another day', () => {
    const plan = distinctPlan()
    const card = renderCard(plan, { ...plan.chosen, finish: '2026-10-11T17:20:00+05:30' })
    expect(card).toHaveTextContent(/done by 17:20 \(Sun 11 Oct\)\./)
  })

  it('says "now" when the plan starts at once', () => {
    const plan = distinctPlan()
    const entry = { ...plan.chosen, start: plan.submit_ts }
    const card = renderCard(plan, entry)
    expect(card).toHaveTextContent('Start now')
    expect(card).not.toHaveTextContent('Start at')
  })

  it('shows the pause window when the job pauses', () => {
    const plan = distinctPlan()
    const card = renderCard(plan, plan.pareto[8])
    expect(card).toHaveTextContent('pause 12:00 to 13:00')
  })

  it('shows the saving as ranges, each with a modelled chip', () => {
    const card = renderCard(distinctPlan())
    expect(card).toHaveTextContent(/saves about 10 to 20% modelled.*stress-weighted water/i)
    expect(card).toHaveTextContent(/15 to 25% modelled.*CO₂/)
    expect(card).toHaveTextContent(/compared with starting now/i)
    const values = card.querySelectorAll('.range-value')
    expect(values.length).toBeGreaterThanOrEqual(3)
    values.forEach((value) => {
      expect(value.parentElement?.querySelector('.tag')).not.toBeNull()
    })
  })

  it('uses the tag the server gave, not a fixed one', () => {
    const plan = distinctPlan({ tags: { ...distinctPlan().tags, water: 'placeholder' } })
    const card = renderCard(plan)
    const water = card.querySelector('.range')
    expect(water?.querySelector('.tag-placeholder')).not.toBeNull()
  })

  it('shows person-days of city water as a range', () => {
    const card = renderCard(distinctPlan())
    expect(card).toHaveTextContent(/0\.11 to 0\.14 person-days/)
    expect(card).toHaveTextContent(/of city water/i)
  })

  it('says energy is modelled and that a receipt shows measured energy', () => {
    const card = renderCard(distinctPlan())
    expect(card).toHaveTextContent(/energy comes from your gpu type/i)
    expect(card).toHaveTextContent(/after a real run, your receipt shows measured energy/i)
  })

  it('warns that the power-cap factors are placeholders when the server says so', () => {
    const card = renderCard(distinctPlan())
    expect(card).toHaveTextContent(/power-cap factors are placeholders/i)
    expect(within(card).getAllByRole('link', { name: /placeholder/i }).length).toBeGreaterThan(0)
  })

  it('says there is little room to shift when the notes say no_room', () => {
    const plan = distinctPlan({ notes: ['no_room'] })
    expect(renderCard(plan)).toHaveTextContent(
      'Little room to shift before your deadline; starting now is fine.',
    )
  })

  it('does not say it otherwise', () => {
    expect(renderCard(distinctPlan())).not.toHaveTextContent(/little room to shift/i)
  })

  it('is honest when the plan does not reduce the footprint', () => {
    const plan = distinctPlan()
    const entry: ParetoEntry = {
      ...plan.chosen,
      savings_ranges: { water_pct: [-5, 0], co2_pct: [-3, 0], energy_pct: [0, 0] },
    }
    const card = renderCard(plan, entry)
    expect(card).toHaveTextContent(/does not reduce your footprint/i)
    expect(card).not.toHaveTextContent(/saves about/i)
  })

  it('says the effect is uncertain when the low end is negative', () => {
    const plan = distinctPlan()
    const entry: ParetoEntry = {
      ...plan.chosen,
      savings_ranges: { water_pct: [-4, 12], co2_pct: [1, 9], energy_pct: [0, 3] },
    }
    const card = renderCard(plan, entry)
    expect(card).toHaveTextContent(/uncertain/i)
    expect(card).toHaveTextContent('-4 to 12%')
  })

  it('links to the assumptions page under the card', () => {
    const card = renderCard(distinctPlan())
    expect(within(card).getByRole('link', { name: /how do we know/i })).toHaveAttribute(
      'href',
      '/assumptions',
    )
  })

  it('shows no NaN, Infinity or undefined', () => {
    const plan = distinctPlan({ person_days_range: [Number.NaN, Number.POSITIVE_INFINITY] })
    const card = renderCard(plan)
    expect(card).not.toHaveTextContent(/NaN|Infinity|undefined/)
  })
})
