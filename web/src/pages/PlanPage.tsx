import { useRef } from 'react'
import { useSearchParams } from 'react-router-dom'
import { JobForm } from '../components/JobForm'
import { PlanResults } from '../components/PlanResults'
import { Banner } from '../components/ui/Banner'
import { Spinner } from '../components/ui/Spinner'
import { PHONE_QUERY, useMediaQuery } from '../hooks/useMediaQuery'
import { usePageTitle } from '../hooks/usePageTitle'
import { useAssumptions } from '../hooks/useAssumptions'
import { usePlan } from '../hooks/usePlan'
import { defaultValues, type JobFormValues } from '../lib/jobForm'
import { JobSentenceBox } from '../components/JobSentenceBox'

/** F1 to F5: the form, and the plan with its charts and slider. */
export function PlanPage() {
  usePageTitle('Plan')
  const assumptions = useAssumptions()
  const plan = usePlan()
  const phone = useMediaQuery(PHONE_QUERY)
  const [params] = useSearchParams()
  const wantedCity = params.get('city')
  // On a phone the form moves under the plan, which mounts a new JobForm. The draft is kept here
  // (a ref: typing must not re-render the charts) and read by the new form when it mounts.
  const draft = useRef<JobFormValues | undefined>(undefined)
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
    const { gpus, cities } = state.data
    // A link from the home page can name the city (/plan?city=Mumbai); unknown names are ignored.
    const fromLink = (): JobFormValues | undefined => {
      if (!wantedCity || !cities.some((c) => c.id === wantedCity)) return undefined
      return { ...defaultValues(Date.now(), gpus, cities), city: wantedCity }
    }
    form = (
      <>
        <div className="form-heading">
          <h2>Your job</h2>
          <span className="muted">India time</span>
        </div>
<JobForm
           gpus={gpus}
           cities={cities}
           busy={plan.status === 'loading'}
           onSubmit={plan.submit}
           getDraft={() => draft.current ?? fromLink()}
           onValuesChange={(values) => {
             draft.current = values
           }}
         />
         <JobSentenceBox />
      </>
    )
  }

  const results = <PlanResults plan={plan} />
  const showResultsFirst = phone && plan.status !== 'idle'

  return (
    <div>
      <div className="page-intro">
        <p className="eyebrow">Planner</p>
        <h1>When should your GPU job run?</h1>
        <p className="lede">
          Tell us about the job. We pick the start time, pauses and GPU power that use the least
          stress-weighted water and CO₂, and still finish before your deadline.
        </p>
      </div>
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
            <div className="card">{form}</div>
            <div>{results}</div>
          </>
        )}
      </div>
    </div>
  )
}
