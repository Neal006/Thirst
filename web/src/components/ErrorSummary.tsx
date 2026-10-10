import { orderedMessages, type FieldErrors } from '../lib/jobForm'

/**
 * What is wrong with the form, read out by screen readers as soon as it appears. The inline
 * messages next to the fields stay; this lists them in one place.
 */
export function ErrorSummary({ errors }: { errors: FieldErrors }) {
  const messages = orderedMessages(errors)
  if (messages.length === 0) return null
  const count = messages.length === 1 ? '1 problem' : `${messages.length} problems`
  return (
    <div className="banner banner-error" role="alert">
      <p>
        <strong>{`Please fix ${count} before planning.`}</strong>
      </p>
      <ul>
        {messages.map((message) => (
          <li key={message}>{message}</li>
        ))}
      </ul>
    </div>
  )
}
