import { useParams } from 'react-router-dom'
import { Amount } from '../components/Amount'
import { Badge } from '../components/Badge'
import { RecentReceipts } from '../components/RecentReceipts'
import { ScoreBreakdown } from '../components/ScoreBreakdown'
import { SimulatedChip } from '../components/SimulatedChip'
import { Banner } from '../components/ui/Banner'
import { Spinner } from '../components/ui/Spinner'
import { usePageTitle } from '../hooks/usePageTitle'
import { useSite } from '../hooks/useSite'
import type { MonthlyAbsolute, SiteResponse } from '../api/types'
import { coolingLabel, divisionLabel } from '../lib/divisions'

function Header({ site, badge }: { site: SiteResponse['site']; badge: string | null }) {
  return (
    <section aria-label="Site details">
      <h1>
        {site.name} {site.simulated ? <SimulatedChip /> : null}
      </h1>
      <p>
        {site.city} - {coolingLabel(site.cooling)} - {divisionLabel(site.division)} <Badge badge={badge} />
      </p>
    </section>
  )
}

function Monthly({ month }: { month: MonthlyAbsolute }) {
  return (
    <section className="card" aria-labelledby="month-heading">
      <h2 id="month-heading">Last 30 days</h2>
      <ul className="stat-list">
        <li><span className="stat-label">GPU energy</span><Amount value={month.kwh} unit="kWh" tag="modelled" /></li>
        <li><span className="stat-label">Water used</span><Amount value={month.litres} unit="L" tag="modelled" /></li>
        <li><span className="stat-label">Stress-weighted water</span><Amount value={month.stress_litres} unit="L" tag="modelled" /></li>
        <li><span className="stat-label">CO₂</span><Amount value={month.kg_co2} unit="kg" tag="modelled" /></li>
        <li><span className="stat-label">City water</span><Amount value={month.person_days} unit="person-days" tag="modelled" /></li>
      </ul>
    </section>
  )
}

export function SitePage() {
  const { siteId = '' } = useParams()
  usePageTitle('Site')
  const { state, reload } = useSite(siteId)
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
    <div>
      <Header site={site} badge={score.badge} />
      <ScoreBreakdown score={score} />
      {month ? <Monthly month={month} /> : null}
      <RecentReceipts siteId={site.site_id} receipts={receipts} />
    </div>
  )
}
