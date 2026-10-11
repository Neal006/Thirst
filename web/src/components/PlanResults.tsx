import { useEffect } from 'react'
import type { ParetoEntry } from '../api/types'
import type { PlanController } from '../hooks/usePlan'
import { rememberPlan } from '../lib/recentPlans'
import { AlphaSlider } from './AlphaSlider'
import { ParetoChart } from './ParetoChart'
import { PlanActions } from './PlanActions'
import { PlanViews } from './PlanViews'
import { ResultCard } from './ResultCard'
import { Banner } from './ui/Banner'
import { EmptyState } from './ui/EmptyState'
import { Spinner } from './ui/Spinner'
import { TagChip } from './TagChip'

function staleText(age: number | null | undefined): string {
  if (typeof age !== 'number' || !Number.isFinite(age) || age < 0) {
    return 'Weather data is not live; using the last forecast we have.'
  }
  return `Weather data is ${age} ${age === 1 ? 'hour' : 'hours'} old; using the last forecast.`
}

/** True when the slider has nothing to choose between: every option is the same plan. */
function allSame(entries: readonly ParetoEntry[]): boolean {
  const first = entries[0]
  return entries.every((e) => e.start === first?.start && e.point.W_l === first.point.W_l && e.point.C_kg === first.point.C_kg)
}

/** Everything right of the form: card, charts and slider, or the loading, error and idle states. */
export function PlanResults({ plan }: { plan: PlanController }) {
  const { status, response, selected } = plan
  useEffect(() => {
    if (!response) return
    rememberPlan(response)
    window.dispatchEvent(new Event('thirst:recent'))
  }, [response])
  if (status === 'idle') {
    return (
      <EmptyState title="Plan your job" className="empty-plan">
        <p>Pick a quick fill or describe your job, then press Plan.</p>
        <ul className="empty-steps">
          <li>
            <b>When to start</b>
            The hours that use the least water and CO₂.
          </li>
          <li>
            <b>How fast to run</b>
            A GPU power level that does the same work with less energy.
          </li>
          <li>
            <b>What it saves</b>
            Water and CO₂ compared with starting now.
          </li>
        </ul>
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
      <PlanActions response={response} entry={selected} />
      <PlanViews response={response} entry={selected} />
      {allSame(response.pareto) ? (
        <p className="card tradeoff-note muted">
          <strong>Water or CO₂ first?</strong>{' '}
          {response.tags.tau === 'placeholder' ? (
            <>
              With today's placeholder power-cap data every option gives the same plan, so there is nothing to
              choose between yet <TagChip tag="placeholder" />
            </>
          ) : (
            <>For this job every option gives the same plan, so there is nothing to choose between.</>
          )}
        </p>
      ) : (
        <section className="card tradeoff" aria-labelledby="tradeoff-heading">
          <h3 id="tradeoff-heading">Water or CO₂ first?</h3>
          <AlphaSlider value={plan.alpha} onChange={plan.setAlpha} />
          <ParetoChart
            entries={response.pareto}
            tags={response.tags}
            selectedAlpha={plan.alpha}
            onSelect={plan.setAlpha}
          />
        </section>
      )}
    </>
  )
}
