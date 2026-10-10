import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { mockFetch } from '../api/mocks/mockFetch'
import { EMPTY_SITE_ID } from '../api/mocks/site'
import { fetchSpy, jsonReply, renderWithApi, type FetchFn } from '../test/api'
import { SitePage } from './SitePage'

afterEach(() => {
  vi.unstubAllGlobals()
})

function renderSite(siteId: string, fetchImpl: FetchFn = mockFetch) {
  return renderWithApi(
    <Routes>
      <Route path="/sites/:siteId" element={<SitePage />} />
    </Routes>,
    { path: `/sites/${siteId}`, spy: fetchSpy(fetchImpl) },
  )
}

const withSite = (patch: (site: Record<string, unknown>) => Record<string, unknown>, id = 's_demoaaaaaa'): FetchFn =>
  async (input, init) => {
    const reply = await mockFetch(new URL(`/sites/${id}`, String(input)).toString(), init)
    return jsonReply(200, patch((await reply.json()) as Record<string, unknown>))
  }

describe('SitePage with receipts', () => {
  it('shows the name, the Simulated chip, city, cooling, division and badge', async () => {
    renderSite('s_demoaaaaaa')
    expect(await screen.findByRole('heading', { level: 1, name: /demo lab, chennai/i })).toBeInTheDocument()
    const header = screen.getByRole('region', { name: /site details/i })
    expect(header).toHaveTextContent('Simulated')
    expect(header).toHaveTextContent('Chennai')
    expect(header).toHaveTextContent('Room AC')
    expect(header).toHaveTextContent('Small labs')
    expect(header).toHaveTextContent(/platinum/i)
  })

  it('breaks the score into A, B (never rated) and C with its parts', async () => {
    renderSite('s_demoaaaaaa')
    await screen.findByRole('heading', { level: 1 })
    const parts = within(screen.getByRole('region', { name: /score/i }))
    expect(parts.getByText(/behaviour/i).closest('li')).toHaveTextContent(/of 50/)
    const b = parts.getByText(/facility efficiency/i).closest('li')
    expect(b).toHaveTextContent('Not rated')
    expect(b).toHaveTextContent('Needs metered building data')
    expect(b).not.toHaveTextContent(/\d+ of/)
    const c = parts.getByText(/measurement and openness/i).closest('li')
    expect(c).toHaveTextContent(/of 20/)
    expect(c).toHaveTextContent(/measured share/i)
    expect(c).toHaveTextContent(/of 10/)
    expect(c).toHaveTextContent(/coverage you declared/i)
    expect(c).toHaveTextContent(/public/i)
  })

  it('says the score is provisional because building efficiency is not rated', async () => {
    renderSite('s_demoaaaaaa')
    expect(await screen.findByText('Provisional: building efficiency not rated yet')).toBeInTheDocument()
  })

  it('lists the last receipts with date, energy, capture and a link', async () => {
    renderSite('s_demoaaaaaa')
    await screen.findByRole('heading', { level: 1 })
    const rows = within(screen.getByRole('table')).getAllByRole('row').slice(1)
    expect(rows).toHaveLength(3)
    expect(rows[0]).toHaveTextContent(/9 Oct/)
    expect(rows[0]).toHaveTextContent('4.5 kWh')
    expect(rows[0]).toHaveTextContent('about 86%')
    expect(within(rows[0]).getByRole('link', { name: /view/i })).toHaveAttribute('href', '/receipts/s_demoaaaaaa/j_abcdefghijkl')
    expect(rows[2]).toHaveTextContent('No room to shift')
    rows.forEach((row) => expect(row.querySelector('.tag')).not.toBeNull())
  })

  it('shows at most the last 10 receipts', async () => {
    const many = (site: Record<string, unknown>) => ({
      ...site,
      recent_receipts: Array.from({ length: 14 }, (_, i) => ({
        job_id: `j_abcdefghijk${String.fromCharCode(97 + i)}`,
        end_ts: '2026-10-09T08:00:00+05:30',
        kwh: 2,
        capture: 0.5,
        no_room: false,
        method: 'nvml_energy',
      })),
    })
    renderSite('s_demoaaaaaa', withSite(many))
    await screen.findByRole('heading', { level: 1 })
    expect(within(screen.getByRole('table')).getAllByRole('row').slice(1)).toHaveLength(10)
  })

  it('shows the monthly footprint with tags and person-days', async () => {
    renderSite('s_demoaaaaaa')
    await screen.findByRole('heading', { level: 1 })
    const month = screen.getByRole('region', { name: /last 30 days/i })
    expect(month).toHaveTextContent('14 kWh')
    expect(month).toHaveTextContent('58 L')
    expect(month).toHaveTextContent('17 kg')
    expect(month).toHaveTextContent(/person-days/)
    expect(month.querySelectorAll('.tag').length).toBeGreaterThanOrEqual(4)
  })

  it('never shows the number of GPUs', async () => {
    renderSite('s_demoaaaaaa', withSite((s) => ({ ...s, gpu_count: 777, site: { ...(s.site as object), gpu_count: 777 } })))
    await screen.findByRole('heading', { level: 1 })
    expect(document.body).not.toHaveTextContent('777')
  })

  it('refuses a reply where B has a number', async () => {
    renderSite('s_demoaaaaaa', withSite((s) => ({ ...s, score: { ...(s.score as object), B: 12 } })))
    expect(await screen.findByRole('alert')).toHaveTextContent(/could not read/i)
    expect(document.body).not.toHaveTextContent(/\b12\b/)
  })
})

describe('SitePage without receipts', () => {
  it('says what to do and offers a copy button for the command', async () => {
    const writeText = vi.fn(async () => {})
    vi.stubGlobal('navigator', { ...navigator, clipboard: { writeText } })
    renderSite(EMPTY_SITE_ID)
    expect(await screen.findByText(/no receipts yet/i)).toHaveTextContent(/run thirst run/i)
    await userEvent.click(screen.getByRole('button', { name: /copy/i }))
    expect(writeText).toHaveBeenCalledWith(expect.stringContaining('thirst run'))
    expect(await screen.findByText('Copied')).toBeInTheDocument()
  })

  it('tells the person to select the text when copying is not possible', async () => {
    vi.stubGlobal('navigator', { ...navigator, clipboard: undefined })
    renderSite(EMPTY_SITE_ID)
    await userEvent.click(await screen.findByRole('button', { name: /copy/i }))
    expect(await screen.findByText(/could not copy/i)).toBeInTheDocument()
  })

  it('explains why there is no score yet', async () => {
    renderSite(EMPTY_SITE_ID)
    expect(await screen.findByText(/no score yet/i)).toHaveTextContent(/at least one receipt/i)
    expect(screen.queryByRole('table')).not.toBeInTheDocument()
    expect(screen.queryByRole('region', { name: /last 30 days/i })).not.toBeInTheDocument()
  })
})

describe('SitePage errors', () => {
  it('shows the server message for an unknown site', async () => {
    renderSite('s_zzzzzzzzzz')
    expect(await screen.findByRole('alert')).toHaveTextContent("We couldn't find that site.")
  })
})
