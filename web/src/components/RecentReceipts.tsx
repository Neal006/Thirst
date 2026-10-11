import { Link } from 'react-router-dom'
import type { SiteResponse } from '../api/types'
import { formatClock, formatDay } from '../lib/format'
import { isMeasuredMethod } from '../lib/receiptText'
import { Amount } from './Amount'
import { CopyCommand } from './CopyCommand'
import { Range } from './Range'

type ReceiptRow = SiteResponse['recent_receipts'][number]

const MAX_ROWS = 10
const EXAMPLE_COMMAND = 'thirst run --hours 6 --deadline "2026-10-10 09:00" --pausable -- python train.py'

function Row({ siteId, receipt }: { siteId: string; receipt: ReceiptRow }) {
  const capture = receipt.capture === null ? null : receipt.capture * 100
  return (
    <tr>
      <td data-label="Finished">{formatDay(receipt.end_ts)} {formatClock(receipt.end_ts)}</td>
      <td data-label="GPU energy">
        <Amount value={receipt.kwh} unit="kWh" tag={isMeasuredMethod(receipt.method) ? 'measured' : 'modelled'} />
      </td>
      <td data-label="Saving taken">
        {capture === null || receipt.no_room ? (
          'No room to shift'
        ) : (
          <Range range={[capture, capture]} unit="%" tag="modelled" />
        )}
      </td>
      <td>
        <Link to={`/receipts/${encodeURIComponent(siteId)}/${encodeURIComponent(receipt.job_id)}`}>
          View
        </Link>
      </td>
    </tr>
  )
}

/** The last 10 receipts of a site, or the first-run hint when there are none. */
export function RecentReceipts({ siteId, receipts }: { siteId: string; receipts: readonly ReceiptRow[] }) {
  return (
    <section className="card" aria-labelledby="receipts-heading">
      <h2 id="receipts-heading">Recent receipts</h2>
      {receipts.length === 0 ? (
        <>
          <p>
            No receipts yet. Run <code>thirst run …</code> to get your first one.
          </p>
          <CopyCommand command={EXAMPLE_COMMAND} />
        </>
      ) : (
        <table className="data-table cards-on-phone">
          <thead>
            <tr>
              <th scope="col">Finished</th>
              <th scope="col">GPU energy</th>
              <th scope="col">Saving taken</th>
              <th scope="col"><span className="visually-hidden">Receipt</span></th>
            </tr>
          </thead>
          <tbody>
            {receipts.slice(0, MAX_ROWS).map((r) => (
              <Row key={r.job_id} siteId={siteId} receipt={r} />
            ))}
          </tbody>
        </table>
      )}
    </section>
  )
}
