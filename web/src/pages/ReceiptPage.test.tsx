import { screen, within } from '@testing-library/react'
import { Route, Routes } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import receiptFixture from '../api/mocks/fixtures/receipt_response.json'
import { mockFetch } from '../api/mocks/mockFetch'
import { fetchSpy, jsonReply, renderWithApi, type FetchFn } from '../test/api'
import { ReceiptPage } from './ReceiptPage'

const PATH = '/receipts/s_abcdefghij/j_abcdefghijkl'

function renderReceipt(fetchImpl: FetchFn = mockFetch) {
  return renderWithApi(
    <Routes>
      <Route path="/receipts/:siteId/:jobId" element={<ReceiptPage />} />
    </Routes>,
    { path: PATH, spy: fetchSpy(fetchImpl) },
  )
}

const withReceipt = (patch: Record<string, unknown>): FetchFn =>
  async (input, init) => {
    const reply = await mockFetch(input, init)
    return jsonReply(200, { ...(await reply.json()), ...patch })
  }

const column = (name: RegExp) => within(screen.getByRole('region', { name }))

describe('ReceiptPage', () => {
  it('shows the three ways side by side', async () => {
    renderReceipt()
    await screen.findByRole('heading', { name: 'What you did' })
    expect(screen.getByRole('heading', { name: 'If you had started right away' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Best plan' })).toBeInTheDocument()
  })

  it('gives every number its unit and a tag, measured energy only for what you did', async () => {
    renderReceipt()
    await screen.findByRole('heading', { name: 'What you did' })
    const actual = column(/what you did/i)
    expect(actual.getByText('3.9 kWh')).toBeInTheDocument()
    const energy = actual.getByText('3.9 kWh').closest('li')
    expect(energy?.querySelector('.tag-measured')).not.toBeNull()
    const base = column(/started right away/i)
    expect(base.getByText('4.9 kWh').closest('li')?.querySelector('.tag-modelled')).not.toBeNull()
    expect(actual.getByText(/person-days/)).toBeInTheDocument()
    expect(actual.getByText(/stress-weighted/i)).toBeInTheDocument()
  })

  it('says how much of the possible saving was taken', async () => {
    renderReceipt()
    expect(await screen.findByText(/you took/i)).toHaveTextContent(
      /you took about 96% modelled.*of the possible saving/i,
    )
  })

  it('says when there was no room to shift', async () => {
    renderReceipt(withReceipt({ capture: null, no_room: true, flexible: false }))
    expect(await screen.findByText(/no room to shift/i)).toHaveTextContent(
      "No room to shift: this job doesn't count toward your score.",
    )
    expect(screen.queryByText(/you took/i)).not.toBeInTheDocument()
  })

  it('explains how it was scored, with the observed share of the hours', async () => {
    renderReceipt()
    expect(await screen.findByText(/scored with the forecast saved when you planned/i)).toBeInTheDocument()
    expect(screen.getByText(/0 of 7 hours/)).toBeInTheDocument()
    expect(screen.getByText(/power cap applied/i)).toHaveTextContent(/yes/i)
    expect(screen.getByText(/energy method/i)).toHaveTextContent(/nvml energy counter/i)
    expect(screen.getByText(/NVIDIA GeForce RTX 4090/)).toBeInTheDocument()
  })

  it('shows the site score as provisional and links to the site', async () => {
    renderReceipt()
    const link = await screen.findByRole('link', { name: /see your site/i })
    expect(link).toHaveAttribute('href', '/sites/s_abcdefghij')
    expect(screen.getByText(/provisional/i)).toBeInTheDocument()
  })

  it('warns that an unverified receipt was not checked', async () => {
    renderReceipt(withReceipt({ method: 'unverified', tags: { energy: 'unverified', water: 'modelled', co2: 'modelled' } }))
    expect(
      await screen.findByText(/this energy was reported by the tool but not checked against the hardware/i),
    ).toBeInTheDocument()
  })

  it('never shows the number of GPUs', async () => {
    renderReceipt(withReceipt({ gpu: { name: 'NVIDIA GeForce RTX 4090', count: 4096 } }))
    await screen.findByRole('heading', { name: 'What you did' })
    expect(document.body).not.toHaveTextContent('4096')
  })

  it('shows the server message when the receipt does not exist', async () => {
    renderReceipt(async () => jsonReply(404, { error: 'receipt_not_found', message: "We couldn't find that receipt." }))
    expect(await screen.findByRole('alert')).toHaveTextContent("We couldn't find that receipt.")
    expect(document.body).not.toHaveTextContent(/undefined|NaN/)
  })

  it('refuses a reply with the wrong shape in plain words', async () => {
    renderReceipt(async () => jsonReply(200, { hello: 'world' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(/could not read/i)
  })

  it('uses the fixture the engine produced', () => {
    expect(receiptFixture.capture).toBeGreaterThan(0.9)
  })
})
