import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createMemoryRouter, RouterProvider } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import { ApiContext } from './api/context'
import { mockFetch } from './api/mocks/mockFetch'
import { EMPTY_SITE_ID } from './api/mocks/site'
import { appRoutes, createAppRoutes } from './routes'
import { clientWith, fetchSpy, jsonReply, type FetchFn } from './test/api'
import { findUntaggedNumbers } from './test/honesty'
import { distinctPlan } from './test/planFixture'

// Pages load on first visit; the planner chunk (charts) can take over a second cold in jsdom.
const PAGE_LOAD = { timeout: 5000 }

const distinctApi: FetchFn = async (input, init) =>
  new URL(String(input)).pathname === '/plan' ? jsonReply(200, distinctPlan()) : mockFetch(input, init)

function renderAt(path: string, fetchImpl: FetchFn = distinctApi) {
  const router = createMemoryRouter(appRoutes, { initialEntries: [path] })
  return render(
    <ApiContext.Provider value={clientWith(fetchSpy(fetchImpl))}>
      <RouterProvider router={router} />
    </ApiContext.Provider>,
  )
}

describe('routes', () => {
  it.each([
    ['/leaderboard', /^Leaderboard$/],
    ['/assumptions', /^Assumptions$/],
    ['/sites/s_demoaaaaaa', /demo lab, chennai/i],
    ['/receipts/s_abcdefghij/j_abcdefghijkl', /^Your receipt$/],
  ])('deep link %s loads its page', async (path, heading) => {
    renderAt(path)
    expect(await screen.findByRole('heading', { level: 1, name: heading })).toBeInTheDocument()
  })

  it('shows a friendly page for an unknown address', async () => {
    renderAt('/no/such/page')
    expect(await screen.findByRole('heading', { name: /couldn't find that page/i })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /go to the planner/i })).toHaveAttribute('href', '/plan')
  })

  it('opens the planner at /plan', async () => {
    renderAt('/plan')
    expect(await screen.findByRole('heading', { level: 1, name: /when should your gpu job run/i }, PAGE_LOAD)).toBeInTheDocument()
  })

  it('moves between pages with the navigation', async () => {
    renderAt('/')
    await userEvent.click(screen.getByRole('link', { name: 'Leaderboard' }))
    expect(await screen.findByRole('heading', { level: 1, name: 'Leaderboard' })).toBeInTheDocument()
    await userEvent.click(screen.getByRole('link', { name: 'Assumptions' }))
    expect(await screen.findByRole('heading', { level: 1, name: 'Assumptions' })).toBeInTheDocument()
    await userEvent.click(within(screen.getByRole('navigation', { name: /main/i })).getByRole('link', { name: 'Cities' }))
    expect(await screen.findByRole('heading', { level: 1, name: 'Compare cities' })).toBeInTheDocument()
  })

  it('sets the tab title for each page', async () => {
    renderAt('/leaderboard')
    await screen.findByRole('heading', { level: 1, name: 'Leaderboard' })
    await waitFor(() => expect(document.title).toBe('Leaderboard - Thirst'))
  })

  it('"How do we know?" on the plan page goes to the assumptions', async () => {
    renderAt('/plan')
    await userEvent.click(await screen.findByRole('button', { name: 'Plan' }))
    await screen.findByRole('region', { name: /your plan/i })
    const link = screen.getAllByRole('link', { name: /how do we know/i })[0]
    expect(link).toHaveAttribute('href', '/assumptions')
  })
})

describe('a page that crashes', () => {
  function Boom(): never {
    throw new Error('secret internal detail at line 42')
  }

  function renderBroken(path = '/boom') {
    const routes = createAppRoutes([{ path: 'boom', element: <Boom /> }])
    const router = createMemoryRouter(routes, { initialEntries: [path] })
    return render(
      <ApiContext.Provider value={clientWith(fetchSpy(distinctApi))}>
        <RouterProvider router={router} />
      </ApiContext.Provider>,
    )
  }

  // React logs a crash to the console; keep the test output clean.
  const quietly = () => vi.spyOn(console, 'error').mockImplementation(() => {})

  it('shows a plain-words message and a way back instead of a blank page', async () => {
    const spy = quietly()
    renderBroken()
    expect(await screen.findByRole('heading', { name: /something went wrong/i })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /go to the planner/i })).toHaveAttribute('href', '/plan')
    spy.mockRestore()
  })

  it('does not show the error text or a stack to the person', async () => {
    const spy = quietly()
    renderBroken()
    await screen.findByRole('heading', { name: /something went wrong/i })
    expect(document.body).not.toHaveTextContent(/secret internal detail|line 42|Error:|at /)
    spy.mockRestore()
  })

  it('keeps the navigation, so the person can leave the broken page', async () => {
    const spy = quietly()
    renderBroken()
    await screen.findByRole('heading', { name: /something went wrong/i })
    await userEvent.click(screen.getByRole('link', { name: 'Leaderboard' }))
    expect(await screen.findByRole('heading', { level: 1, name: 'Leaderboard' })).toBeInTheDocument()
    spy.mockRestore()
  })

  it('goes back to a working planner from the message', async () => {
    const spy = quietly()
    renderBroken()
    await userEvent.click(await screen.findByRole('link', { name: /go to the planner/i }))
    expect(await screen.findByRole('heading', { level: 1, name: /when should your gpu job run/i }, PAGE_LOAD)).toBeInTheDocument()
    spy.mockRestore()
  })
})

describe('G5: no number with a unit is shown without a tag (plan 6.4.c)', () => {
  // `hasNumbers` guards against a vacuous pass: the page must really show numbers with units.
  const honest = async (ready: () => Promise<unknown>, hasNumbers = true) => {
    await ready()
    await waitFor(() => expect(document.querySelector('.skeleton')).toBeNull())
    if (hasNumbers) expect(document.body.textContent).toMatch(/\d\s?(%|kWh|kg|L)(?![A-Za-z])/)
    expect(findUntaggedNumbers(document.body)).toEqual([])
  }

  it('the plan page with a plan, a moved slider and a stale-forecast banner', async () => {
    const plan = distinctPlan({ tags: { ...distinctPlan().tags, forecast: 'cached' }, forecast_age_hours: 3, notes: ['no_room'] })
    renderAt('/plan', async (input, init) =>
      new URL(String(input)).pathname === '/plan' ? jsonReply(200, plan) : mockFetch(input, init),
    )
    await userEvent.click(await screen.findByRole('button', { name: 'Plan' }))
    await honest(() => screen.findByRole('region', { name: /your plan/i }))
    fireEvent.change(screen.getByRole('slider'), { target: { value: '0.8' } })
    await honest(async () => {})
  })

  it('the home page with the live forecast, facts and the board preview', async () => {
    renderAt('/')
    await honest(async () => {
      await screen.findAllByText('Cleanest hour')
      await screen.findByText('Start now')
      await screen.findByRole('list', { name: /top small labs/i })
    })
  })

  it('the plan page before a plan', async () => {
    renderAt('/plan')
    await honest(() => screen.findByLabelText(/gpu model/i), false)
  })

  it('the leaderboard', async () => {
    renderAt('/leaderboard')
    await honest(() => screen.findByRole('table'))
  })

  it('a site page with receipts and one without', async () => {
    const view = renderAt('/sites/s_demoaaaaaa')
    await honest(() => screen.findByRole('heading', { level: 1, name: /demo lab/i }))
    view.unmount()
    renderAt(`/sites/${EMPTY_SITE_ID}`)
    await honest(() => screen.findByText(/no receipts yet/i), false)
  })

  it('a receipt', async () => {
    renderAt('/receipts/s_abcdefghij/j_abcdefghijkl')
    await honest(() => screen.findByRole('heading', { name: 'What you did' }))
  })

  it('the assumptions page', async () => {
    renderAt('/assumptions')
    await honest(() => screen.findByRole('heading', { name: 'Cooling' }), false)
  })
})
