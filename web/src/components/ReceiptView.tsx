import { Link } from 'react-router-dom'
import type { ReceiptDetail } from '../api/types'
import { formatClock, formatDay } from '../lib/format'
import { capMethodLabel, methodLabel } from '../lib/receiptText'
import { Range } from './Range'
import { ReceiptColumn } from './ReceiptColumn'
import { MeterBar } from './ScoreRing'

interface ReceiptViewProps {
  receipt: ReceiptDetail
  siteId: string
}

function CaptureBanner({ receipt }: { receipt: ReceiptDetail }) {
  if (receipt.no_room) {
    return <p className="card">No room to shift: this job doesn't count toward your score.</p>
  }
  if (receipt.capture === null) {
    return <p className="card">A Capture number is not available for this receipt.</p>
  }
  if (receipt.capture < 0) {
    // Worse than the base plan: say so in words. "You took -20%" would read as nonsense.
    return (
      <p className="card">
        You used more than the base plan, so there was no saving to capture this time.
      </p>
    )
  }
  const percent = receipt.capture * 100
  return (
    <div className="card capture-card">
      <p className="plan-sentence">
        You took <Range range={[percent, percent]} unit="%" tag={receipt.tags.water} /> of the possible
        saving.
      </p>
      <MeterBar value={percent} max={100} tone="signal" />
    </div>
  )
}

/** F8: Base, Best and Actual side by side, how it was scored, and what it did to the site score. */
export function ReceiptView({ receipt, siteId }: ReceiptViewProps) {
  const { absolute, tags, site_score: score } = receipt
  const { basis } = absolute
  const hours = basis.observed + basis.forecast
  return (
    <div>
      <CaptureBanner receipt={receipt} />
      {receipt.method === 'unverified' ? (
        <p className="banner banner-warn">
          This energy was reported by the tool but not checked against the hardware.
        </p>
      ) : null}
      <div className="three-ways">
        <ReceiptColumn id="col-base" title="If you had started right away" totals={absolute.base} energyTag="modelled" tags={tags} />
        <ReceiptColumn id="col-best" title="Best plan" totals={absolute.best} energyTag="modelled" tags={tags} />
        <ReceiptColumn id="col-actual" title="What you did" totals={absolute.actual} energyTag={tags.energy} tags={tags} />
      </div>
      <section className="card" aria-labelledby="how-scored">
        <h2 id="how-scored">How this was scored</h2>
        <p>
          Scored with the forecast saved when you planned (fair to you). Absolute litres use observed
          weather where available ({`${basis.observed} of ${hours} hours`}).
        </p>
        <ul>
          {receipt.end_ts ? (
            <li>Finished: {formatDay(receipt.end_ts)} {formatClock(receipt.end_ts)} (India time)</li>
          ) : null}
          {typeof receipt.cap_applied === 'boolean' ? (
            <li>
              Power cap applied: {receipt.cap_applied ? 'yes' : 'no'}
              {receipt.cap_method ? ` (${capMethodLabel(receipt.cap_method)})` : ''}
            </li>
          ) : null}
          {receipt.method ? <li>Energy method: {methodLabel(receipt.method)}</li> : null}
          {receipt.gpu ? <li>GPU: {receipt.gpu.name}</li> : null}
        </ul>
      </section>
      <p>
        {score.value === null
          ? 'Your site has no score yet.'
          : `Your site score is now ${Math.round(score.value)}${score.provisional ? ' (provisional)' : ''}.`}{' '}
        <Link to={`/sites/${encodeURIComponent(siteId)}`}>See your site</Link>
      </p>
    </div>
  )
}
