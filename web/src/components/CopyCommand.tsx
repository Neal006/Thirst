import { useState } from 'react'

type CopyState = 'idle' | 'copied' | 'failed'

/** A command in a code box with a Copy button. Says so plainly when copying is not possible. */
export function CopyCommand({ command }: { command: string }) {
  const [state, setState] = useState<CopyState>('idle')

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(command)
      setState('copied')
    } catch {
      setState('failed')
    }
  }

  return (
    <div className="copy-row">
      <code>{command}</code>
      <button type="button" className="btn" onClick={copy}>
        Copy
      </button>
      <span role="status">
        {state === 'copied' ? 'Copied' : null}
        {state === 'failed' ? 'Could not copy. Select the text and copy it by hand.' : null}
      </span>
    </div>
  )
}
