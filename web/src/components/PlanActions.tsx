import { useState } from 'react'
import type { ParetoEntry, PlanResponse } from '../api/types'
import { calendarFile, runCommand, shareQuery } from '../lib/planViews'
import { CopyCommand } from './CopyCommand'

interface PlanActionsProps {
  response: PlanResponse
  entry: ParetoEntry
}

/** What to do with a plan: run it, put it in a calendar, or send it to someone. */
export function PlanActions({ response, entry }: PlanActionsProps) {
  const [status, setStatus] = useState('')

  const downloadCalendar = () => {
    const blob = new Blob([calendarFile(response, entry)], { type: 'text/calendar' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'thirst-plan.ics'
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
    setStatus('Calendar file downloaded. Open it to add the run with a 10 minute reminder.')
  }

  const copyLink = async () => {
    const link = `${window.location.origin}/plan?${shareQuery(response)}`
    try {
      await navigator.clipboard.writeText(link)
      setStatus('Link copied. Anyone who opens it sees this job in the planner.')
    } catch {
      setStatus(`Could not copy. The link is ${link}`)
    }
  }

  return (
    <section className="card plan-actions" aria-labelledby="actions-heading">
      <h3 id="actions-heading">Run this plan</h3>
      <p className="muted">Start the job with this command. It waits and runs at the planned times.</p>
      <CopyCommand command={runCommand(response)} />
      <div className="action-row">
        <button type="button" className="btn" onClick={downloadCalendar}>
          Add to calendar
        </button>
        <button type="button" className="btn" onClick={copyLink}>
          Copy share link
        </button>
      </div>
      <p role="status" className="action-status">
        {status}
      </p>
    </section>
  )
}
