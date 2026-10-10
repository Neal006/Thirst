import { FactorTable } from '../components/FactorTable'
import { CityTable, GpuTable, SourceList, StatusLegend } from '../components/ReferenceTables'
import { Banner } from '../components/ui/Banner'
import { Spinner } from '../components/ui/Spinner'
import { useAssumptions } from '../hooks/useAssumptions'
import { usePageTitle } from '../hooks/usePageTitle'
import { groupFactors } from '../lib/assumptionsView'

/** F6: every number the model uses, where it came from and how sure we are. */
export function AssumptionsPage() {
  usePageTitle('Assumptions')
  const { state, reload } = useAssumptions()
  return (
    <div>
      <h1>Assumptions</h1>
      <p>
        Energy is measured from the GPU when you use <code>thirst run</code>. Water and CO₂ are
        modelled from that energy. We use the average grid mix, not the marginal plant. We leave out
        the water and carbon used to make the GPU.
      </p>
      <StatusLegend />
      {state.status === 'loading' ? <Spinner label="Loading the assumptions…" lines={6} /> : null}
      {state.status === 'error' ? (
        <Banner kind="error" actionLabel="Try again" onAction={reload}>
          {state.message}
        </Banner>
      ) : null}
      {state.status === 'ready' ? (
        <>
          <p className="muted">Version {state.data.version}</p>
          {groupFactors(state.data.factors).map((group) => (
            <FactorTable key={group.id} group={group} />
          ))}
          <GpuTable gpus={state.data.gpus} />
          <CityTable cities={state.data.cities} />
          <SourceList sources={state.data.sources} />
        </>
      ) : null}
    </div>
  )
}
