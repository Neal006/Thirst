import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import leaderboardFixture from '../api/mocks/fixtures/leaderboard_response.json'
import { mockFetch } from '../api/mocks/mockFetch'
import { calledPaths, fetchSpy, jsonReply, renderWithApi, type FetchFn } from '../test/api'
import { LeaderboardPage } from './LeaderboardPage'

function renderBoard(path = '/leaderboard', fetchImpl: FetchFn = mockFetch) {
  const spy = fetchSpy(fetchImpl)
  const view = renderWithApi(
    <Routes>
      <Route path="/leaderboard" element={<LeaderboardPage />} />
    </Routes>,
    { path, spy },
  )
  return { ...view, spy }
}

const withRows = (rows: unknown[]): FetchFn => async () =>
  jsonReply(200, { ...leaderboardFixture, rows })

const dataRows = () => screen.getAllByRole('row').slice(1)

describe('LeaderboardPage', () => {
  it('shows the small labs division first and asks for it', async () => {
    const { spy } = renderBoard()
    await screen.findByRole('link', { name: /demo lab, chennai/i })
    expect(calledPaths(spy)[0]).toContain('division=D1')
    expect(screen.getByRole('button', { name: /small labs \(up to 16 gpus\)/i })).toHaveAttribute('aria-pressed', 'true')
  })

  it('has the four division tabs with their size ranges', async () => {
    renderBoard()
    await screen.findByRole('table')
    for (const name of [/small labs/i, /clusters \(17 to 256\)/i, /facilities \(257 to 4,096\)/i, /hyperscale \(above 4,096\)/i]) {
      expect(screen.getByRole('button', { name })).toBeInTheDocument()
    }
  })

  it('changes the query when a division tab is pressed', async () => {
    const { spy } = renderBoard()
    await screen.findByRole('table')
    await userEvent.click(screen.getByRole('button', { name: /clusters/i }))
    expect(await screen.findByText(/no sites in this division yet/i)).toBeInTheDocument()
    expect(calledPaths(spy).some((p) => p.includes('division=D2'))).toBe(true)
    expect(screen.getByRole('button', { name: /clusters/i })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('button', { name: /small labs/i })).toHaveAttribute('aria-pressed', 'false')
  })

  it('starts on the division in the address and falls back to D1 for an unknown one', async () => {
    const d3 = renderBoard('/leaderboard?division=D3')
    await screen.findByText(/no sites in this division yet/i)
    expect(calledPaths(d3.spy)[0]).toContain('division=D3')
    d3.unmount()
    const bad = renderBoard('/leaderboard?division=D9')
    await screen.findByRole('table')
    expect(calledPaths(bad.spy)[0]).toContain('division=D1')
  })

  it('marks simulated sites with a Simulated chip', async () => {
    renderBoard()
    await screen.findByRole('table')
    const first = dataRows()[0]
    expect(within(first).getByText('Simulated')).toBeInTheDocument()
  })

  it('shows rank, name, badge, score, flexible share, monthly footprint and receipts', async () => {
    renderBoard()
    await screen.findByRole('table')
    const first = dataRows()[0]
    expect(within(first).getByRole('link', { name: /demo lab, chennai/i })).toHaveAttribute('href', '/sites/s_demoaaaaaa')
    expect(first).toHaveTextContent('1')
    expect(first).toHaveTextContent(/platinum/i)
    expect(first).toHaveTextContent('99')
    expect(first).toHaveTextContent('Provisional')
    expect(first).toHaveTextContent('about 100%')
    expect(first).toHaveTextContent('14 kWh')
    expect(first).toHaveTextContent('58 L')
    expect(first).toHaveTextContent('17 kg')
    expect(first.querySelectorAll('.tag').length).toBeGreaterThanOrEqual(4)
  })

  it('lists unrated sites last with "Not rated yet"', async () => {
    const base = leaderboardFixture.rows[0]
    const rows = [
      { ...base, site_id: 's_unratedaaa', name: 'Quiet Lab', simulated: false, score: null, badge: null, rank: null },
      { ...base, site_id: 's_ratedaaaaa', name: 'Busy Lab', simulated: false, rank: 1 },
    ]
    renderBoard('/leaderboard', withRows(rows))
    await screen.findByRole('table')
    const names = dataRows().map((r) => r.textContent)
    expect(names[0]).toContain('Busy Lab')
    expect(names[1]).toContain('Quiet Lab')
    expect(dataRows()[1]).toHaveTextContent('Not rated yet')
  })

  it('never shows the number of GPUs of a site', async () => {
    const rows = leaderboardFixture.rows.map((r) => ({ ...r, gpu_count: 777, gpus: 777 }))
    renderBoard('/leaderboard', withRows(rows))
    await screen.findByRole('table')
    expect(document.body).not.toHaveTextContent('777')
  })

  it('becomes cards on a phone (the table carries the cards class and cell labels)', async () => {
    renderBoard()
    const table = await screen.findByRole('table')
    expect(table).toHaveClass('cards-on-phone')
    expect(dataRows()[0].querySelector('td[data-label="Score"]')).not.toBeNull()
  })

  it('shows the server message when the board cannot load, and no table', async () => {
    renderBoard('/leaderboard', async () => jsonReply(503, { error: 'try_again', message: 'Something went wrong on our side. Please try again.' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(/something went wrong on our side/i)
    expect(screen.queryByRole('table')).not.toBeInTheDocument()
  })

  describe('with malformed rows the guard refuses the whole answer', () => {
    const base = leaderboardFixture.rows[0]
    const cases: Array<[string, unknown]> = [
      ['a row that is null', null],
      ['a row that is a string', 'not a row'],
      ['a score that is text', { ...base, score: '99' }],
      ['a missing site id', { ...base, site_id: undefined }],
      ['a monthly footprint that is null', { ...base, monthly_absolute: null }],
      ['a monthly litre figure that is text', { ...base, monthly_absolute: { ...base.monthly_absolute, litres: 'lots' } }],
      ['a receipts count that is missing', { ...base, receipts: undefined }],
    ]
    it.each(cases)('%s', async (_name, bad) => {
      renderBoard('/leaderboard', withRows([base, bad]))
      expect(await screen.findByRole('alert')).toHaveTextContent(/could not read/i)
      expect(screen.queryByRole('table')).not.toBeInTheDocument()
      expect(document.body).not.toHaveTextContent(/demo lab/i)
    })
  })

  it('shows no NaN or undefined for odd numbers', async () => {
    const base = leaderboardFixture.rows[0]
    const rows = [{ ...base, monthly_absolute: { ...base.monthly_absolute, litres: 0 }, flex_share: 0 }]
    renderBoard('/leaderboard', withRows(rows))
    await screen.findByRole('table')
    expect(document.body).not.toHaveTextContent(/NaN|undefined|Infinity/)
  })
})
