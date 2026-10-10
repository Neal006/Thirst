import type { ReactNode } from 'react'

export interface ControlProps {
  id: string
  'aria-invalid': boolean
  'aria-describedby': string | undefined
}

interface FormFieldProps {
  id: string
  label: string
  help?: string
  error?: string
  /** Gets the props that tie the control to its label, help and error text. */
  children: (control: ControlProps) => ReactNode
  /** Puts a checkbox before its label on one line. */
  inline?: boolean
}

/** A label, a control, helper text and an inline error, wired together for screen readers. */
export function FormField({ id, label, help, error, children, inline = false }: FormFieldProps) {
  const helpId = `${id}-help`
  const errorId = `${id}-error`
  const described = [help ? helpId : '', error ? errorId : ''].filter(Boolean).join(' ')
  const control = children({
    id,
    'aria-invalid': Boolean(error),
    'aria-describedby': described || undefined,
  })
  return (
    <div className={inline ? 'field field-check' : 'field'}>
      {inline ? control : null}
      <label htmlFor={id}>{label}</label>
      {inline ? null : control}
      {help ? (
        <small id={helpId} className="field-help">
          {help}
        </small>
      ) : null}
      {error ? (
        <p id={errorId} className="field-error">
          {error}
        </p>
      ) : null}
    </div>
  )
}
