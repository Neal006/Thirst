import { screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { MOCK_ASSUMPTIONS } from '../api/mocks/assumptions'
import { mockFetch } from '../api/mocks/mockFetch'
import { fetchSpy, jsonReply, renderWithApi, type FetchFn } from '../test/api'
import { AssumptionsPage } from './AssumptionsPage'

afterEach(() => {
  vi.restoreAllMocks()
})

const renderPage = (path = '/assumptions', fetchImpl: FetchFn = mockFetch) =>
  renderWithApi(<AssumptionsPage />, { path, spy: fetchSpy(fetchImpl) })

describe('AssumptionsPage', () => {
  it('opens with the plain-words summary of how the numbers are made', async () => {
    renderPage()
    const intro = await screen.findByText(/energy is measured from the gpu/i)
    expect(intro).toHaveTextContent(
      'Energy is measured from the GPU when you use thirst run. Water and CO₂ are modelled from that energy. ' +
        'We use the average grid mix, not the marginal plant. We leave out the water and carbon used to make the GPU.',
    )
  })

  it('groups the factors under plain headings', async () => {
    renderPage()
    await screen.findByRole('heading', { name: 'Cooling' })
    for (const name of ['Grid carbon', 'Grid water', 'Water stress', 'GPU and power cap', 'Score', 'People']) {
      expect(screen.getByRole('heading', { name })).toBeInTheDocument()
    }
  })

  it('gives every factor row its id, so chips can link to it', async () => {
    renderPage()
    await screen.findByRole('heading', { name: 'Cooling' })
    for (const f of MOCK_ASSUMPTIONS.factors) {
      const el = document.getElementById(f.id)
      expect(el, f.id).not.toBeNull()
      expect(el?.tagName).toBe('TR')
    }
  })

  it('shows value, spread, unit, status chip and source for a factor', async () => {
    renderPage()
    await screen.findByRole('heading', { name: 'Cooling' })
    const row = document.getElementById('cop_rated_room_ac') as HTMLElement
    expect(row).toHaveTextContent('Rated COP of a room AC')
    expect(row).toHaveTextContent('3')
    expect(row).toHaveTextContent('2.55 to 3.45')
    expect(row).toHaveTextContent('kW heat per kW')
    expect(row.querySelector('.tag-placeholder')).not.toBeNull()
    expect(row).toHaveTextContent('trd.md 5')
  })

  it('says a GPU placeholder will be replaced by the measured sweep', async () => {
    renderPage()
    await screen.findByRole('heading', { name: 'GPU and power cap' })
    expect(document.getElementById('tau_70')).toHaveTextContent(
      'Placeholder: to be replaced by our measured sweep',
    )
  })

  it('highlights and scrolls to the row named in the address', async () => {
    const scroll = vi.fn()
    Element.prototype.scrollIntoView = scroll
    renderPage('/assumptions#tau_70')
    await screen.findByRole('heading', { name: 'Cooling' })
    expect(document.getElementById('tau_70')).toHaveClass('is-target')
    expect(document.getElementById('cop_rated_room_ac')).not.toHaveClass('is-target')
    expect(scroll).toHaveBeenCalled()
  })

  it('has an anchor for every kind of label, so the chips land somewhere', async () => {
    renderPage()
    await screen.findByRole('heading', { name: 'Cooling' })
    for (const tag of ['measured', 'modelled', 'placeholder', 'sourced', 'calibrated', 'design_choice', 'unverified']) {
      expect(document.getElementById(`status-${tag}`), tag).not.toBeNull()
    }
  })

  it('lists GPUs with their maximum power, cities with their stress, and the sources', async () => {
    renderPage()
    const gpus = within(await screen.findByRole('region', { name: /gpus/i }))
    expect(gpus.getByText('NVIDIA GeForce RTX 4090')).toBeInTheDocument()
    expect(gpus.getByText('450 W')).toBeInTheDocument()
    const cities = within(screen.getByRole('region', { name: /cities/i }))
    expect(cities.getByText('Chennai')).toBeInTheDocument()
    const sources = within(screen.getByRole('region', { name: /sources/i }))
    const link = sources.getByRole('link', { name: 'Open-Meteo' })
    expect(link).toHaveAttribute('href', 'https://open-meteo.com/')
    expect(link).toHaveAttribute('rel', expect.stringContaining('noopener'))
  })

  it('does not turn an unsafe source address into a link', async () => {
    const evil = {
      ...MOCK_ASSUMPTIONS,
      sources: [{ name: 'Evil', url: 'javascript:alert(1)', licence: 'x', used_for: 'y' }],
    }
    renderPage('/assumptions', async () => jsonReply(200, evil))
    const sources = within(await screen.findByRole('region', { name: /sources/i }))
    expect(sources.getByText('Evil')).toBeInTheDocument()
    expect(sources.queryByRole('link', { name: 'Evil' })).not.toBeInTheDocument()
  })

  it('shows text from the API as text, never as markup', async () => {
    const tricky = {
      ...MOCK_ASSUMPTIONS,
      factors: [{ ...MOCK_ASSUMPTIONS.factors[0], label: '<img src=x onerror=alert(1)>' }],
    }
    const { container } = renderPage('/assumptions', async () => jsonReply(200, tricky))
    await screen.findByRole('heading', { name: 'Cooling' })
    expect(container.querySelector('img')).toBeNull()
    expect(container).toHaveTextContent('<img src=x onerror=alert(1)>')
  })

  it('shows the server message when the assumptions cannot be loaded', async () => {
    renderPage('/assumptions', async () => jsonReply(503, { error: 'try_again', message: 'Something went wrong on our side. Please try again.' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(/something went wrong on our side/i)
  })
})
