import { act, fireEvent, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { mockFetch } from '../api/mocks/mockFetch'
import { calledPaths, fetchSpy, jsonReply, renderWithApi, type FetchFn } from '../test/api'
import { distinctPlan } from '../test/planFixture'
import { PlanPage } from './PlanPage'

afterEach(() => {
  vi.unstubAllGlobals()
})

/** The mock API, except that /plan answers with a plan whose 11 entries differ. */
function distinctApi(plan = distinctPlan()): FetchFn {
  return async (input, init) =>
    new URL(String(input)).pathname === '/plan' ? jsonReply(200, plan) : mockFetch(input, init)
}

async function planIt(spy = fetchSpy(distinctApi())) {
  const view = renderWithApi(<PlanPage />, { spy })
  await userEvent.click(await screen.findByRole('button', { name: 'Plan' }))
  await screen.findByRole('region', { name: /your plan/i })
  return { ...view, spy }
}

const card = () => screen.getByRole('region', { name: /your plan/i })

describe('PlanPage before a plan', () => {
  it('loads the GPU list, shows the form and asks for no plan yet', async () => {
    const { spy } = renderWithApi(<PlanPage />)
    expect(await screen.findByLabelText(/gpu model/i)).toBeInTheDocument()
    expect(screen.getByText(/press plan/i)).toBeInTheDocument()
    expect(calledPaths(spy)).toEqual(['/assumptions'])
  })

  it('says so in plain words when the GPU list cannot be loaded, and can try again', async () => {
    let calls = 0
    const spy = fetchSpy(async (input, init) => {
      calls += 1
      return calls === 1
        ? jsonReply(503, { error: 'try_again', message: 'Something went wrong on our side. Please try again.' })
        : mockFetch(input, init)
    })
    renderWithApi(<PlanPage />, { spy })
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent(/something went wrong on our side/i)
    expect(screen.queryByLabelText(/gpu model/i)).not.toBeInTheDocument()
    await userEvent.click(within(alert).getByRole('button', { name: /try again/i }))
    expect(await screen.findByLabelText(/gpu model/i)).toBeInTheDocument()
  })
})

describe('PlanPage with a plan', () => {
  it('posts the form once and shows the card, chart, slider and Pareto chart', async () => {
    const { spy } = await planIt()
    expect(calledPaths(spy)).toEqual(['/assumptions', '/plan'])
    const body = JSON.parse(String(spy.mock.calls[1][1]?.body)) as Record<string, unknown>
    expect(body).toMatchObject({ city: 'Chennai', gpu_model: 'RTX-4090', gpu_count: 2, alpha: 0.5 })
    expect(card()).toHaveTextContent('Start at 06:00')
    expect(screen.getByRole('slider')).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Timetable' })).toHaveAttribute('aria-selected', 'true')
    expect(screen.getByRole('table', { name: /timetable/i })).toBeInTheDocument()
    expect(screen.getAllByRole('img').length).toBeGreaterThanOrEqual(1)
    expect(screen.getByRole('region', { name: 'Run this plan' })).toHaveTextContent('thirst run --hours')
  })

  it('moves the slider and changes the card without any request', async () => {
    const { spy } = await planIt()
    spy.mockClear()
    fireEvent.change(screen.getByRole('slider'), { target: { value: '1' } })
    await waitFor(() => expect(card()).toHaveTextContent('Start at 11:00'))
    expect(card()).toHaveTextContent('GPU at 100%')
    expect(card()).toHaveTextContent(/uses about 15 to 25%/i)
    fireEvent.change(screen.getByRole('slider'), { target: { value: '0' } })
    await waitFor(() => expect(card()).toHaveTextContent('Start at 01:00'))
    expect(spy).not.toHaveBeenCalled()
  })

  it('moves the slider when a Pareto dot is clicked', async () => {
    const { container } = await planIt()
    await waitFor(() => expect(container.querySelectorAll('.pareto-dot')).toHaveLength(11))
    fireEvent.click(container.querySelector('.pareto-dot[data-alpha="0.2"]') as Element)
    expect(screen.getByRole('slider')).toHaveAttribute('aria-valuetext', 'Water 20%, carbon 80%')
    await waitFor(() => expect(card()).toHaveTextContent('Start at 03:00'))
  })

  it('uses the slider position for the next plan', async () => {
    const { spy } = await planIt()
    fireEvent.change(screen.getByRole('slider'), { target: { value: '0.8' } })
    await userEvent.click(screen.getByRole('button', { name: 'Plan' }))
    await waitFor(() => expect(spy.mock.calls.filter(([i]) => String(i).endsWith('/plan'))).toHaveLength(2))
    const second = JSON.parse(String(spy.mock.calls[2][1]?.body)) as { alpha: number }
    expect(second.alpha).toBe(0.8)
  })

  it('shows the little-room copy when the plan says no_room', async () => {
    await planIt(fetchSpy(distinctApi(distinctPlan({ notes: ['no_room'] }))))
    expect(card()).toHaveTextContent('Little room to shift before your deadline, so starting now is fine.')
  })

  it('warns when the forecast is old', async () => {
    const plan = distinctPlan({ tags: { ...distinctPlan().tags, forecast: 'cached' }, forecast_age_hours: 5 })
    await planIt(fetchSpy(distinctApi(plan)))
    const banner = screen.getByText('Weather data is 5 hours old; using the last forecast.')
    expect(banner.closest('[role="status"]')).not.toBeNull()
  })

  it('does not warn when the forecast is live', async () => {
    await planIt()
    expect(screen.queryByText(/weather data is/i)).not.toBeInTheDocument()
  })

  it('says the forecast is not live when its age is unknown', async () => {
    const plan = distinctPlan({ tags: { ...distinctPlan().tags, forecast: 'cached' }, forecast_age_hours: null })
    await planIt(fetchSpy(distinctApi(plan)))
    expect(screen.getByText(/weather data is not live/i).closest('[role="status"]')).not.toBeNull()
  })
})

describe('PlanPage while loading and when it fails', () => {
  it('shows Planning while the plan is on its way and disables the button', async () => {
    const spy = fetchSpy(async (input, init) =>
      new URL(String(input)).pathname === '/plan' ? new Promise<Response>(() => {}) : mockFetch(input, init),
    )
    renderWithApi(<PlanPage />, { spy })
    await userEvent.click(await screen.findByRole('button', { name: 'Plan' }))
    expect(await screen.findAllByText(/planning/i)).not.toHaveLength(0)
    expect(screen.getByRole('button', { name: /planning/i })).toBeDisabled()
  })

  it('shows the server message and a Try again button, then recovers', async () => {
    let plans = 0
    const spy = fetchSpy(async (input, init) => {
      if (new URL(String(input)).pathname !== '/plan') return mockFetch(input, init)
      plans += 1
      return plans === 1
        ? jsonReply(422, { error: 'deadline_too_soon', message: 'This job needs until 21:00 at full power. Pick a later deadline.' })
        : jsonReply(200, distinctPlan())
    })
    renderWithApi(<PlanPage />, { spy })
    await userEvent.click(await screen.findByRole('button', { name: 'Plan' }))
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('Pick a later deadline.')
    expect(document.body).not.toHaveTextContent(/stack|TypeError|undefined/)
    await userEvent.click(within(alert).getByRole('button', { name: /try again/i }))
    expect(await screen.findByRole('region', { name: /your plan/i })).toBeInTheDocument()
  })

  it('makes no request for an invalid form', async () => {
    const { spy } = renderWithApi(<PlanPage />)
    fireEvent.change(await screen.findByLabelText(/how many gpus/i), { target: { value: '0' } })
    await userEvent.click(screen.getByRole('button', { name: 'Plan' }))
    expect(calledPaths(spy)).toEqual(['/assumptions'])
    expect(screen.getByLabelText(/how many gpus/i)).toBeInvalid()
  })
})

/** A matchMedia stub whose answer can change later, like a window that is resized. */
function controllableViewport(initial: boolean) {
  let matches = initial
  const listeners = new Set<() => void>()
  vi.stubGlobal('matchMedia', (query: string) => ({
    get matches() {
      return matches
    },
    media: query,
    addEventListener: (_type: string, listener: () => void) => listeners.add(listener),
    removeEventListener: (_type: string, listener: () => void) => listeners.delete(listener),
  }))
  return (next: boolean) => {
    matches = next
    act(() => listeners.forEach((listener) => listener()))
  }
}

describe('PlanPage on a phone', () => {
  it('keeps what was typed in the form after planning, under "Change job"', async () => {
    controllableViewport(true)
    const spy = fetchSpy(distinctApi())
    renderWithApi(<PlanPage />, { spy })
    fireEvent.change(await screen.findByLabelText(/how many gpus/i), { target: { value: '8' } })
    await userEvent.selectOptions(screen.getByLabelText(/^city$/i), 'Mumbai')
    fireEvent.change(screen.getByLabelText(/deadline/i), { target: { value: '2030-01-05T17:30' } })
    await userEvent.click(screen.getByRole('button', { name: 'Plan' }))
    await screen.findByRole('region', { name: /your plan/i })

    await userEvent.click(screen.getByText('Change job'))
    expect(screen.getByLabelText(/how many gpus/i)).toHaveValue(8)
    expect(screen.getByLabelText(/^city$/i)).toHaveValue('Mumbai')
    expect(screen.getByLabelText(/deadline/i)).toHaveValue('2030-01-05T17:30')
  })

  it('keeps the form values when the window is resized across the phone width', async () => {
    const resize = controllableViewport(false)
    renderWithApi(<PlanPage />, { spy: fetchSpy(distinctApi()) })
    fireEvent.change(await screen.findByLabelText(/how many gpus/i), { target: { value: '8' } })
    await userEvent.click(screen.getByRole('button', { name: 'Plan' }))
    await screen.findByRole('region', { name: /your plan/i })

    resize(true)
    await userEvent.click(screen.getByText('Change job'))
    expect(screen.getByLabelText(/how many gpus/i)).toHaveValue(8)

    resize(false)
    expect(screen.getByLabelText(/how many gpus/i)).toHaveValue(8)
  })

  it('puts the card first and the form under "Change job"', async () => {
    controllableViewport(true)
    await planIt()
    const details = screen.getByText('Change job').closest('details')
    expect(details).not.toBeNull()
    expect(details).not.toHaveAttribute('open')
    const order = card().compareDocumentPosition(details as Element)
    expect(order & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  })
})

describe('PlanPage with a reply that has the wrong shape', () => {
  it.each([
    ['without the water tag', ['tags', 'water']],
    ['without the deadline in its inputs', ['inputs', 'deadline']],
    ['without gpu_kwh in an entry', ['chosen', 'gpu_kwh']],
  ])('shows a plain-words error for a plan %s, not "undefined"', async (_name, path) => {
    const bad = structuredClone(distinctPlan()) as unknown as Record<string, Record<string, unknown>>
    delete bad[path[0]][path[1]]
    renderWithApi(<PlanPage />, { spy: fetchSpy(distinctApi(bad as never)) })
    await userEvent.click(await screen.findByRole('button', { name: 'Plan' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(/could not read/i)
    expect(screen.queryByRole('region', { name: /your plan/i })).not.toBeInTheDocument()
    expect(document.body).not.toHaveTextContent(/undefined|NaN/)
  })
})

describe('PlanPage opened from a link', () => {
  it('starts with the city named in the address', async () => {
    renderWithApi(<PlanPage />, { path: '/plan?city=Mumbai' })
    expect(await screen.findByLabelText(/^city/i)).toHaveDisplayValue('Mumbai')
  })

  it('ignores a city it does not know', async () => {
    renderWithApi(<PlanPage />, { path: '/plan?city=Atlantis' })
    expect(await screen.findByLabelText(/^city/i)).toHaveDisplayValue('Chennai')
  })
})
