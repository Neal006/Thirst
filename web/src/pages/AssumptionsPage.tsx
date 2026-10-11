import type { AssumptionRow, FactorStatus } from '../api/types'
import { FactorTable } from '../components/FactorTable'
import { CityTable, GpuTable, SourceList, StatusLegend } from '../components/ReferenceTables'
import { TagChip } from '../components/TagChip'
import { Banner } from '../components/ui/Banner'
import { Spinner } from '../components/ui/Spinner'
import { useAssumptions } from '../hooks/useAssumptions'
import { usePageTitle } from '../hooks/usePageTitle'
import { groupFactors } from '../lib/assumptionsView'

const STATUS_ORDER: FactorStatus[] = ['measured', 'sourced', 'calibrated', 'modelled', 'design_choice', 'placeholder', 'unverified']

/** How many factors carry each label, most trustworthy first. */
function StatusMix({ factors }: { factors: readonly AssumptionRow[] }) {
  const counts = STATUS_ORDER.map((status) => ({
    status,
    count: factors.filter((f) => f.status === status).length,
  })).filter((c) => c.count > 0)
  const total = factors.length || 1
  return (
    <section className="card mix" aria-labelledby="mix-heading">
      <h2 id="mix-heading">How sure we are</h2>
      <div className="mix-bar" aria-hidden="true">
        {counts.map((c) => (
          <span key={c.status} className={`mix-seg mix-${c.status.replace('_', '-')}`} style={{ flexGrow: c.count / total }} />
        ))}
      </div>
      <ul className="mix-legend">
        {counts.map((c) => (
          <li key={c.status}>
            <b>{c.count}</b> <TagChip tag={c.status} />
          </li>
        ))}
      </ul>
      <p className="muted">
        {factors.length} factors. Placeholders get replaced as we measure; every one is listed below with its source.
      </p>
    </section>
  )
}

const GLOSSARY: readonly [string, string][] = [
  ['Water per kWh', 'Litres of water behind one kWh of GPU energy: water to cool the room (on site) plus water used by the power plants (from the grid).'],
  ['Water stress', 'How scarce water is in a city. A litre used in a dry city counts for more, so the plan weighs it more.'],
  ['GPU power level', 'Running the GPU below full power. The job takes a little longer but needs less energy for the same work.'],
  ['Pausing', 'Stopping the job during the thirstiest hours and resuming it later. Only for single-machine jobs.'],
  ['PUE', 'Total site power divided by the power of the GPUs and servers. Only asked for cooling towers.'],
  ['Receipt', 'After a real run with thirst run, what the job actually used, compared with starting right away.'],
  ['Capture', 'Of the saving that was possible for a job, the share you actually took. Receipts add up to the site score.'],
  ['Measured or modelled', 'Measured numbers come from the GPU. Modelled numbers are calculated from those, and say so.'],
  ['Weight class (D1 to D4)', 'The leaderboard groups labs by GPU count, so a small college lab only competes with other small labs.'],
]

function Glossary() {
  return (
    <section id="glossary" className="card glossary" aria-labelledby="glossary-heading">
      <h2 id="glossary-heading">Words we use</h2>
      <dl>
        {GLOSSARY.map(([term, meaning]) => (
          <div key={term}>
            <dt>{term}</dt>
            <dd>{meaning}</dd>
          </div>
        ))}
      </dl>
    </section>
  )
}

/** F6: every number the model uses, where it came from and how sure we are. */
export function AssumptionsPage() {
  usePageTitle('Assumptions')
  const { state, reload } = useAssumptions()
  const groups = state.status === 'ready' ? groupFactors(state.data.factors) : []
  return (
    <div className="assumptions-page">
      <div className="page-head">
        <div>
          <h1>Assumptions</h1>
          <p className="lede">
            Energy is measured from the GPU when you use <code>thirst run</code>. Water and CO₂ are
            modelled from that energy. We use the average grid mix, not the marginal plant. We leave out
            the water and carbon used to make the GPU.
          </p>
        </div>
      </div>
      <Glossary />
      {state.status === 'loading' ? <Spinner label="Loading the assumptions…" lines={6} /> : null}
      {state.status === 'error' ? (
        <Banner kind="error" actionLabel="Try again" onAction={reload}>
          {state.message}
        </Banner>
      ) : null}
      <div className="assume-grid">
        <div className="assume-side">
          {state.status === 'ready' ? <StatusMix factors={state.data.factors} /> : null}
          <StatusLegend />
        </div>
        <div className="assume-main">
          {state.status === 'ready' ? (
            <>
              <nav className="jump" aria-label="Jump to a group">
                {groups.map((g) => (
                  <a key={g.id} href={`#group-${g.id}`} className="jump-chip">
                    {g.label} <span>{g.rows.length}</span>
                  </a>
                ))}
                <a href="#gpus-heading" className="jump-chip">GPUs</a>
                <a href="#cities-heading" className="jump-chip">Cities</a>
                <a href="#sources-heading" className="jump-chip">Sources</a>
              </nav>
              <p className="muted version">Version {state.data.version}</p>
              {groups.map((group) => (
                <FactorTable key={group.id} group={group} />
              ))}
              <GpuTable gpus={state.data.gpus} />
              <CityTable cities={state.data.cities} />
              <SourceList sources={state.data.sources} />
            </>
          ) : null}
        </div>
      </div>
    </div>
  )
}

