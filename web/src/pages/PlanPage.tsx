import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useLocation, useSearchParams } from 'react-router-dom'
import { JobForm } from '../components/JobForm'
import { PlanResults } from '../components/PlanResults'
import { Banner } from '../components/ui/Banner'
import { Spinner } from '../components/ui/Spinner'
import { PHONE_QUERY, useMediaQuery } from '../hooks/useMediaQuery'
import { usePageTitle } from '../hooks/usePageTitle'
import { useAssumptions } from '../hooks/useAssumptions'
import { usePlan } from '../hooks/usePlan'
<<<<<<< HEAD
import { defaultValues, type JobFormValues } from '../lib/jobForm'
import { JobSentenceBox } from '../components/JobSentenceBox'
=======
import { defaultValues, validateJobForm, valuesFromQuery, type JobFormValues } from '../lib/jobForm'
import { readRecent, type RecentPlan } from '../lib/recentPlans'
>>>>>>> upstream/main

/** Jobs planned before in this browser, one click to open them again. */
function RecentPlans() {
  const [list, setList] = useState<RecentPlan[]>(readRecent)
  useEffect(() => {
    const update = () => setList(readRecent())
    window.addEventListener('thirst:recent', update)
    return () => window.removeEventListener('thirst:recent', update)
  }, [])
  if (list.length === 0) return null
  return (
    <nav className="recent" aria-label="Recent plans">
      <h2 className="recent-title">Recent</h2>
      <ul>
        {list.map((r) => (
          <li key={r.query}>
            <Link to={`/plan?${r.query}`}>
              <b>{r.label}</b>
              <span>{r.detail}</span>
            </Link>
          </li>
        ))}
      </ul>
    </nav>
  )
}

/** F1 to F5: the form, and the plan with its views, actions and slider. */
export function PlanPage() {
  usePageTitle('Plan')
  const assumptions = useAssumptions()
  const plan = usePlan()
  const phone = useMediaQuery(PHONE_QUERY)
  const [params] = useSearchParams()
  const { search } = useLocation()
  // On a phone the form moves under the plan, which mounts a new JobForm. The draft is kept here
  // (a ref: typing must not re-render the charts) and read by the new form when it mounts. A draft
  // belongs to one link, so a new link (a recent plan, a shared plan, a city card) starts fresh.
  const draft = useRef<{ search: string; values: JobFormValues } | undefined>(undefined)
  const { state } = assumptions
  const ready = state.status === 'ready' ? state.data : null
  const linkValues = useCallback(
    () =>
      ready
        ? valuesFromQuery(params, defaultValues(Date.now(), ready.gpus, ready.cities), ready.gpus, ready.cities)
        : null,
    [ready, params],
  )

  // A share link describes a whole job: plan it straight away, once per link.
  const planned = useRef<string | null>(null)
  const { submit } = plan
  useEffect(() => {
    const link = linkValues()
    if (!ready || !link?.full || planned.current === search) return
    planned.current = search
    const result = validateJobForm(link.values, Date.now(), ready.gpus, ready.cities)
    if (result.ok) submit(result.body)
  }, [ready, linkValues, search, submit])

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
    form = (
      <>
        <div className="form-heading">
          <h2>Your job</h2>
          <Link to="/cities" className="form-link">
            Compare cities
          </Link>
        </div>
<JobForm
  key={search}
  gpus={gpus}
  cities={cities}
  busy={plan.status === 'loading'}
  onSubmit={plan.submit}
  getDraft={() => (draft.current?.search === search ? draft.current.values : undefined) ?? linkValues()?.values}
  onValuesChange={(values) => {
    draft.current = { search, values }
  }}
/>
<JobSentenceBox />
      </>
    )
  }

  const results = <PlanResults plan={plan} />
  const showResultsFirst = phone && plan.status !== 'idle'

  return (
    <div className="plan-page">
      <div className="page-intro">
        <h1>When should your GPU job run?</h1>
        <p className="lede">We find the hours that use the least water and CO₂ and still finish on time.</p>
      </div>
      <div className="plan-layout">
        {showResultsFirst ? (
          <>
            <div className="plan-results">{results}</div>
            <details className="card">
              <summary>Change job</summary>
              {form}
            </details>
            <RecentPlans />
          </>
        ) : (
          <>
            <div className="plan-side">
              <div className="card">{form}</div>
              <RecentPlans />
            </div>
            <div className="plan-results">{results}</div>
          </>
        )}
      </div>
    </div>
  )
}
