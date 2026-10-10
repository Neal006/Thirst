import type { PlanController } from '../hooks/usePlan'
import { AlphaSlider } from './AlphaSlider'
import { ParetoChart } from './ParetoChart'
import { PlanChart } from './PlanChart'
import { ResultCard } from './ResultCard'
import { Banner } from './ui/Banner'
import { EmptyState } from './ui/EmptyState'
import { Spinner } from './ui/Spinner'

function staleText(age: number | null | undefined): string {
  if (typeof age !== 'number' || !Number.isFinite(age) || age < 0) {
    return 'Weather data is not live; using the last forecast we have.'
  }
  return `Weather data is ${age} ${age === 1 ? 'hour' : 'hours'} old; using the last forecast.`
}

/** Everything right of the form: card, charts and slider, or the loading, error and idle states. */
export function PlanResults({ plan }: { plan: PlanController }) {
  const { status, response, selected } = plan
  if (status === 'idle') {
    return (
      <EmptyState title="Plan your job">
        <p>Fill in the form and press Plan. You will see when to start, how fast to run, and what it saves.</p>
      </EmptyState>
    )
  }
  if (status === 'loading') return <Spinner label="Planning…" />
  if (status === 'error' || !response || !selected) {
    return (
      <Banner kind="error" actionLabel="Try again" onAction={plan.retry}>
        {plan.error ?? 'Something went wrong. Please try again.'}
      </Banner>
    )
  }
  return (
    <>
      {response.tags.forecast === 'cached' ? (
        <Banner kind="warn">{staleText(response.forecast_age_hours)}</Banner>
      ) : null}
      <ResultCard response={response} entry={selected} />
      <PlanChart response={response} entry={selected} />
      <AlphaSlider value={plan.alpha} onChange={plan.setAlpha} />
      <ParetoChart
        entries={response.pareto}
        tags={response.tags}
        selectedAlpha={plan.alpha}
        onSelect={plan.setAlpha}
      />
    </>
  )
}
