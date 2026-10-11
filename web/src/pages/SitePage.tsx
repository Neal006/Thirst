import { Link, useParams } from 'react-router-dom'
import { Amount } from '../components/Amount'
import { Badge } from '../components/Badge'
import { RecentReceipts } from '../components/RecentReceipts'
import { ScoreBreakdown } from '../components/ScoreBreakdown'
import { SimulatedChip } from '../components/SimulatedChip'
import { Banner } from '../components/ui/Banner'
import { Spinner } from '../components/ui/Spinner'
import { useAssumptions } from '../hooks/useAssumptions'
import { usePageTitle } from '../hooks/usePageTitle'
import { useSite } from '../hooks/useSite'
import type { MonthlyAbsolute, SiteResponse } from '../api/types'
import { badgeSteps } from '../lib/badges'
import { coolingLabel, divisionLabel } from '../lib/divisions'

function Header({ site, badge }: { site: SiteResponse['site']; badge: string | null }) {
  return (
    <section aria-label="Site details" className="page-head site-head">
      <div>
        <h1>
          {site.name} {site.simulated ? <SimulatedChip /> : null}
        </h1>
        <p className="site-tags">
          <span className="chip">{site.city}</span> <span className="chip">{coolingLabel(site.cooling)}</span>{' '}
          <span className="chip">{divisionLabel(site.division)}</span> <Badge badge={badge} />
        </p>
      </div>
      <Link className="btn" to={`/plan?city=${encodeURIComponent(site.city)}&cooling=${site.cooling}`}>
        Plan a job here <span className="btn-arrow" aria-hidden="true">→</span>
      </Link>
    </section>
  )
}

function Monthly({ month }: { month: MonthlyAbsolute }) {
  return (
    <section className="card" aria-labelledby="month-heading">
      <h2 id="month-heading">Last 30 days</h2>
      <ul className="stat-list tiles">
        <li><span className="stat-label">GPU energy</span><Amount value={month.kwh} unit="kWh" tag="modelled" /></li>
        <li><span className="stat-label">Water used</span><Amount value={month.litres} unit="L" tag="modelled" /></li>
        <li><span className="stat-label">Water, weighted by scarcity</span><Amount value={month.stress_litres} unit="L" tag="modelled" /></li>
        <li><span className="stat-label">CO₂</span><Amount value={month.kg_co2} unit="kg" tag="modelled" /></li>
        <li><span className="stat-label">One person's city water for</span><Amount value={month.person_days} unit="person-days" tag="modelled" /></li>
      </ul>
    </section>
  )
}

export function SitePage() {
  const { siteId = '' } = useParams()
  usePageTitle('Site')
  const { state, reload } = useSite(siteId)
  const assumptions = useAssumptions().state
  const steps = badgeSteps(assumptions.status === 'ready' ? assumptions.data.factors : undefined)
  if (state.status === 'loading') return <Spinner label="Loading the site…" lines={5} />
  if (state.status === 'error') {
    return (
      <Banner kind="error" actionLabel="Try again" onAction={reload}>
        {state.message}
      </Banner>
    )
  }
  const { site, score, monthly_absolute: month, recent_receipts: receipts } = state.data
  return (
    <div className="site-page">
      <Header site={site} badge={score.badge} />
      <ScoreBreakdown score={score} steps={steps} />
      {month ? <Monthly month={month} /> : null}
      <RecentReceipts siteId={site.site_id} receipts={receipts} />
    </div>
  )
}
