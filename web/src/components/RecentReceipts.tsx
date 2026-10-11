import { Link } from 'react-router-dom'
import type { SiteResponse } from '../api/types'
import { formatClock, formatDay } from '../lib/format'
import { exampleCommand, isMeasuredMethod } from '../lib/receiptText'
import { Amount } from './Amount'
import { CopyCommand } from './CopyCommand'
import { Range } from './Range'

type ReceiptRow = SiteResponse['recent_receipts'][number]

const MAX_ROWS = 10

/** Capture below zero means the job used more than the base plan: say that, not "-20%". */
function CaptureCell({ receipt }: { receipt: ReceiptRow }) {
  if (receipt.capture === null || receipt.no_room) return <>No room to shift</>
  if (receipt.capture < 0) return <>More than the base plan</>
  const percent = receipt.capture * 100
  return <Range range={[percent, percent]} unit="%" tag="modelled" />
}

function Row({ siteId, receipt }: { siteId: string; receipt: ReceiptRow }) {
  const when = `${formatDay(receipt.end_ts)} ${formatClock(receipt.end_ts)}`
  return (
    <tr>
      <td data-label="Finished">{when}</td>
      <td data-label="GPU energy">
        <Amount value={receipt.kwh} unit="kWh" tag={isMeasuredMethod(receipt.method) ? 'measured' : 'modelled'} />
      </td>
      <td data-label="Saving taken">
        <CaptureCell receipt={receipt} />
      </td>
      <td>
        <Link
          to={`/receipts/${encodeURIComponent(siteId)}/${encodeURIComponent(receipt.job_id)}`}
          aria-label={`View receipt from ${when}`}
        >
          View
        </Link>
      </td>
    </tr>
  )
}

/** The last 10 receipts of a site, or the first-run hint when there are none. */
export function RecentReceipts({
  siteId,
  receipts,
  now = Date.now,
}: {
  siteId: string
  receipts: readonly ReceiptRow[]
  /** The clock, replaceable in tests (the example command names tomorrow). */
  now?: () => number
}) {
  return (
    <section className="card" aria-labelledby="receipts-heading">
      <h2 id="receipts-heading">Recent receipts</h2>
      {receipts.length === 0 ? (
        <>
          <p>
            No receipts yet. Run <code>thirst run …</code> to get your first one.
          </p>
          <CopyCommand command={exampleCommand(now())} />
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
