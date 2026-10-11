import React, { useState } from 'react'
import { parseJobSentence } from '../lib/jobSentenceParser'
import type { Tag } from '../api/types'
import { useExplain } from '../hooks/useExplain'

/** Simple component to let the user type a one‑sentence job description and get an explanation. */
export function JobSentenceBox() {
  const [text, setText] = useState('')
  const { status, response, error, explain } = useExplain()
  const parsed = parseJobSentence(text)
  const fillPlanner = () => {
    if (parsed.city) {
      const params = new URLSearchParams(window.location.search)
      params.set('city', parsed.city)
      window.history.pushState({}, '', `${window.location.pathname}?${params.toString()}`)
    }
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (text.trim()) {
      explain(text.trim())
    }
  }

  // Render explanation with number tags based on source and user input
  const renderExplanation = (exp: string) => {
    const parts = exp.split(/(\d+(?:\.\d+)?%?)/g)
    // collect numbers present in the original user text for possible "input" tagging
    const userNums = new Set((text.match(/\d+(?:\.\d+)?%?/g) || []))
    return (
      <p>
        {parts.map((part, i) => {
          if (/^\d+(?:\.\d+)?%?$/.test(part)) {
            let tag: Tag = 'modelled'
            if (response?.source === 'template') tag = 'template'
            else if (response?.source === 'agent' || response?.source === 'bedrock') tag = 'ai_generated'
            if (userNums.has(part)) tag = 'input'
            return (
              <span key={i}>
                {part}
                <TagChip tag={tag} />
              </span>
            )
          }
          return <span key={i}>{part}</span>
        })}
      </p>
    )
  }

  return (
    <section className="job-sentence-box">
      <h3>Describe your job in one sentence</h3>
      <form onSubmit={handleSubmit} noValidate>
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          maxLength={280}
          rows={3}
          aria-label="Job description"
          placeholder="e.g. LoRA on 2 x 4090, 6 hours, need it by 9 AM, can pause, Chennai lab with AC"
          style={{ width: '100%', minHeight: '44px' }}
        />
        <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '4px' }}>
          <span>{text.length}/280</span>
          <button type="submit" disabled={status === 'loading'}>
            {status === 'loading' ? 'Thinking…' : 'Explain'}
          </button>
        </div>
      </form>
      {status === 'error' && <p className="error">{error}</p>}
{parsed.found.length > 0 && (
  <div className="parsed-form">
    {parsed.work_hours !== null && (
      <div>
        <label>Work hours</label>
        <input type="number" value={parsed.work_hours} readOnly />
      </div>
    )}
    {parsed.gpu_count !== null && (
      <div>
        <label>GPU count</label>
        <input type="number" value={parsed.gpu_count} readOnly />
      </div>
    )}
    {parsed.city && (
      <div>
        <label>City</label>
        <input type="text" value={parsed.city} readOnly />
      </div>
    )}
    {parsed.workload && (
      <div>
        <label>Workload</label>
        <input type="text" value={parsed.workload} readOnly />
      </div>
    )}
  </div>
)}
        {response && (
          <>
            <div className="explanation">
              {response.explanation}
            </div>
            <button type="button" onClick={fillPlanner}>Use parameters</button>
          </>
        )}
    </section>
  )
}
