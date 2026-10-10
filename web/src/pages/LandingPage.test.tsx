import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { calledPaths, fetchSpy, renderWithApi } from '../test/api'
import { findUntaggedNumbers } from '../test/honesty'
import { LandingPage } from './LandingPage'

type PlanBody = { city: string; cooling: string; gpu_model: string; pausable: boolean }

function planBodies(spy: ReturnType<typeof fetchSpy>): PlanBody[] {
  return spy.mock.calls
    .filter(([input]) => new URL(String(input)).pathname === '/plan')
    .map(([, init]) => JSON.parse(String(init?.body)) as PlanBody)
}

describe('LandingPage', () => {
  it('leads with the headline and a way into the planner for the chosen city', () => {
    renderWithApi(<LandingPage />)
    expect(screen.getByRole('heading', { level: 1, name: /every gpu hour drinks water twice/i })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /^plan a job/i })).toHaveAttribute('href', '/plan?city=Chennai')
  })

  it('draws the next 24 hours for Chennai with one shared request for the sample job', async () => {
    const { spy } = renderWithApi(<LandingPage />)
    expect(await screen.findByRole('heading', { name: /next 24 h · chennai/i })).toBeInTheDocument()
    await screen.findByText('Start now')
    const bodies = planBodies(spy)
    expect(bodies).toHaveLength(1)
    expect(bodies[0]).toMatchObject({ city: 'Chennai', cooling: 'room_ac', gpu_model: 'RTX-4090', pausable: true })
  })

  it('reads any hour of the clock, with labels on the numbers', async () => {
    renderWithApi(<LandingPage />)
    const hour = await screen.findByRole('slider', { name: /hour to read/i })
    fireEvent.change(hour, { target: { value: '5' } })
    const face = document.querySelector('.clock-face') as HTMLElement
    expect(face).not.toHaveTextContent(/best start/i)
    expect(within(face).getAllByRole('link', { name: /modelled/i })).toHaveLength(2)
    expect(findUntaggedNumbers(face)).toEqual([])
  })

  it('switches city and remembers the answer', async () => {
    const { spy } = renderWithApi(<LandingPage />)
    const group = await screen.findByRole('group', { name: /pick a city/i })
    await waitFor(() => expect(within(group).getAllByRole('button')).toHaveLength(6))
    await screen.findByText('Start now')

    await userEvent.click(within(group).getByRole('button', { name: 'Mumbai' }))
    expect(await screen.findByRole('heading', { name: /next 24 h · mumbai/i })).toBeInTheDocument()
    expect(within(group).getByRole('button', { name: 'Mumbai' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('link', { name: /^plan a job/i })).toHaveAttribute('href', '/plan?city=Mumbai')
    await waitFor(() => expect(planBodies(spy).map((b) => b.city)).toEqual(['Chennai', 'Mumbai']))

    await userEvent.click(within(group).getByRole('button', { name: 'Chennai' }))
    await screen.findByRole('heading', { name: /next 24 h · chennai/i })
    expect(planBodies(spy).map((b) => b.city)).toEqual(['Chennai', 'Mumbai'])
  })

  it('compares the same job started now and on plan, and can switch to a cooling tower', async () => {
    const { spy } = renderWithApi(<LandingPage />)
    expect(await screen.findByText('Start now')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /cooling tower/i }))
    expect(screen.getByRole('button', { name: /cooling tower/i })).toHaveAttribute('aria-pressed', 'true')
    await waitFor(() => expect(planBodies(spy).map((b) => b.cooling)).toEqual(['room_ac', 'evaporative']))
    expect(await screen.findByText('Start now')).toBeInTheDocument()
  })

  it('shows the power cap trade from the assumptions, labelled', async () => {
    renderWithApi(<LandingPage />)
    const group = await screen.findByRole('group', { name: /gpu power limit/i })
    // the mock assumptions carry tau and eps for 70% only
    await waitFor(() => expect(within(group).getAllByRole('button').map((b) => b.textContent)).toEqual(['100%', '70%']))
    expect(screen.getByText('−20%')).toBeInTheDocument()
    expect(screen.getByText('+11%')).toBeInTheDocument()
    await userEvent.click(within(group).getByRole('button', { name: '100%' }))
    expect(screen.getAllByText('±0%')).toHaveLength(2)
  })

  it('previews the top small labs and links to the board', async () => {
    const { spy } = renderWithApi(<LandingPage />)
    const podium = await screen.findByRole('list', { name: /top small labs/i })
    expect(within(podium).getAllByRole('listitem').length).toBeGreaterThan(0)
    expect(within(podium).getAllByText('Simulated').length).toBeGreaterThan(0)
    expect(screen.getByRole('link', { name: /see the full board/i })).toHaveAttribute('href', '/leaderboard')
    expect(calledPaths(spy)).toContain('/leaderboard?division=D1&period=30d&board=score')
  })

  it('marks the sample receipt as a picture, not a measurement', () => {
    renderWithApi(<LandingPage />)
    expect(screen.getByRole('img', { name: /sample water receipt/i })).toBeInTheDocument()
  })

  it('gives copyable commands to get started', () => {
    renderWithApi(<LandingPage />)
    expect(screen.getByText(/^pip install "git\+https:\/\/github.com\/Neal006\/Thirst#subdirectory=cli"$/)).toBeInTheDocument()
    expect(screen.getAllByRole('button', { name: 'Copy' })).toHaveLength(3)
  })
})
