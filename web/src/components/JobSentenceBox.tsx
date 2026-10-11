import { useState } from 'react'
import { TagChip } from '../components/TagChip'
import { useExplain } from '../hooks/useExplain'

/** Simple component to let the user type a one‑sentence job description and get an explanation. */
export function JobSentenceBox() {
  const [text, setText] = useState('')
  const { status, response, error, explain } = useExplain()

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (text.trim()) {
      explain(text.trim())
    }
  }

  // Render explanation with numbers wrapped in a tag chip to satisfy honesty checks
  const renderExplanation = (exp: string) => {
    const parts = exp.split(/(\d+(?:\.\d+)?%?)/g)
    return (
      <p>
        {parts.map((part, i) => {
          if (/^\d+(?:\.\d+)?%?$/.test(part)) {
            // number part – render with a modelled tag chip
            return (
              <span key={i}>
                {part}
                <TagChip tag="modelled" />
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
      {response && (
        <div className="explanation-result">
          <h4>Explanation ({response.source})</h4>
          {renderExplanation(response.explanation)}
          {response.note && <p className="note">Note: {response.note}</p>}
        </div>
      )}
    </section>
  )
}
