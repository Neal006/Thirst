import { JobForm } from '../components/JobForm'
import { PlanResults } from '../components/PlanResults'
import { Banner } from '../components/ui/Banner'
import { Spinner } from '../components/ui/Spinner'
import { PHONE_QUERY, useMediaQuery } from '../hooks/useMediaQuery'
import { usePageTitle } from '../hooks/usePageTitle'
import { useAssumptions } from '../hooks/useAssumptions'
import { usePlan } from '../hooks/usePlan'

/** F1 to F5: the form, and the plan with its charts and slider. */
export function PlanPage() {
  usePageTitle('Plan')
  const assumptions = useAssumptions()
  const plan = usePlan()
  const phone = useMediaQuery(PHONE_QUERY)
  const { state } = assumptions

  let form
  if (state.status === 'loading') {
    form = <Spinner label="Loading the GPU list…" lines={4} />
  } else if (state.status === 'error') {
    form = (
      <Banner kind="error" actionLabel="Try again" onAction={assumptions.reload}>
        {state.message}
      </Banner>
    )
  } else {
    form = (
      <JobForm
        gpus={state.data.gpus}
        cities={state.data.cities}
        busy={plan.status === 'loading'}
        onSubmit={plan.submit}
      />
    )
  }

  const results = <PlanResults plan={plan} />
  const showResultsFirst = phone && plan.status !== 'idle'

  return (
    <div>
      <h1>When should your GPU job run?</h1>
      <div className="plan-layout">
        {showResultsFirst ? (
          <>
            <div>{results}</div>
            <details className="card">
              <summary>Change job</summary>
              {form}
            </details>
          </>
        ) : (
          <>
            <section className="card" aria-label="Your job">
              {form}
            </section>
            <div>{results}</div>
          </>
        )}
      </div>
    </div>
  )
}
