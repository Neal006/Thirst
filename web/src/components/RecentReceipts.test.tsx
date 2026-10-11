import { render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import type { SiteResponse } from '../api/types'
import { exampleCommand } from '../lib/receiptText'
import { RecentReceipts } from './RecentReceipts'

type Receipt = SiteResponse['recent_receipts'][number]

const receipt = (patch: Partial<Receipt> = {}): Receipt => ({
  job_id: 'j_abcdefghijkl',
  end_ts: '2026-10-09T08:30:00+05:30',
  kwh: 4.5,
  capture: 0.8,
  no_room: false,
  method: 'nvml_energy',
  ...patch,
})

function setup(receipts: Receipt[], now?: () => number) {
  return render(
    <MemoryRouter>
      <RecentReceipts siteId="s_abcdefghij" receipts={receipts} now={now} />
    </MemoryRouter>,
  )
}

describe('RecentReceipts', () => {
  it('says a negative capture in words, never as a negative percentage', () => {
    setup([receipt({ capture: -0.2 })])
    const row = screen.getAllByRole('row')[1]
    expect(row).toHaveTextContent(/more than the base plan/i)
    expect(row).not.toHaveTextContent(/-\s?20|−\s?20|\b20\s?%/)
    expect(row.querySelector('td[data-label="Capture"] .range')).toBeNull()
  })

  it('still shows a positive capture as a tagged range', () => {
    setup([receipt({ capture: 0.8 })])
    const row = screen.getAllByRole('row')[1]
    expect(row.querySelector('td[data-label="Capture"] .range')).not.toBeNull()
    expect(row).toHaveTextContent('about 80%')
  })

  it('names the receipt date in every View link, so the links differ for a screen reader', () => {
    setup([receipt(), receipt({ job_id: 'j_abcdefghijkm', end_ts: '2026-10-08T21:05:00+05:30' })])
    const links = screen.getAllByRole('link', { name: /view/i })
    expect(links.map((l) => l.getAttribute('aria-label'))).toEqual([
      'View receipt from Fri 9 Oct 08:30',
      'View receipt from Thu 8 Oct 21:05',
    ])
  })

  it('suggests an example command with a deadline that is tomorrow, not a fixed past date', () => {
    const day = 86_400_000
    const base = Date.parse('2027-03-04T10:00:00+05:30')
    setup([], () => base)
    expect(screen.getByText(/--deadline "2027-03-05 09:00"/)).toBeInTheDocument()
    expect(document.body).not.toHaveTextContent('2026-10-10')
    expect(exampleCommand(base + 10 * day)).toContain('"2027-03-15 09:00"')
  })

  it('shows the first-run hint with the command when there are no receipts', () => {
    setup([])
    const section = screen.getByRole('region', { name: /recent receipts/i })
    expect(within(section).getByText(/no receipts yet/i)).toBeInTheDocument()
    expect(within(section).getByText(/thirst run --hours/)).toBeInTheDocument()
  })
})
