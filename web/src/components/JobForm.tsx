import { useEffect, useRef, useState, type FormEvent } from 'react'
import type { CityRow, GpuRow, PlanRequestBody } from '../api/types'
import {
  defaultValues,
  presetValues,
  PRESETS,
  validateJobForm,
  type FieldErrors,
  type JobFormValues,
  type Preset,
} from '../lib/jobForm'
import { CoolingFields } from './CoolingFields'
import { ErrorSummary } from './ErrorSummary'
import { FormField } from './FormField'

interface JobFormProps {
  gpus: readonly GpuRow[]
  cities: readonly CityRow[]
  /** True while a plan request is running: the button is disabled. */
  busy: boolean
  onSubmit: (body: PlanRequestBody) => void
  /** The clock, replaceable in tests. */
  now?: () => number
  /** Asked once, when the form mounts: a draft kept by the parent to start from, if it has one. */
  getDraft?: () => JobFormValues | undefined
  /** Called with all values after every change, so the parent can keep the draft. */
  onValuesChange?: (values: JobFormValues) => void
}

/** F1: the job description. Checks the input here, so a bad value makes no request. */
export function JobForm({
  gpus,
  cities,
  busy,
  onSubmit,
  now = Date.now,
  getDraft,
  onValuesChange,
}: JobFormProps) {
  const [values, setValues] = useState<JobFormValues>(
    () => getDraft?.() ?? defaultValues(now(), gpus, cities),
  )
  const [errors, setErrors] = useState<FieldErrors>({})
  const [preset, setPreset] = useState<string | null>(null)
  // Counts failed submits: each one moves focus to the first invalid field, even if the same one.
  const [failedSubmits, setFailedSubmits] = useState(0)
  const formRef = useRef<HTMLFormElement>(null)
  const update = (next: JobFormValues) => {
    setValues(next)
    onValuesChange?.(next)
  }
  const set = (patch: Partial<JobFormValues>) => {
    setPreset(null)
    update({ ...values, ...patch })
  }
  const applyPreset = (p: Preset) => {
    setPreset(p.id)
    setErrors({})
    update(presetValues(p, values, now()))
  }
  const presets = PRESETS.filter((p) => gpus.some((g) => g.id === p.gpuModel))

  useEffect(() => {
    if (failedSubmits === 0) return
    formRef.current?.querySelector<HTMLElement>('[aria-invalid="true"]')?.focus()
  }, [failedSubmits])

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const result = validateJobForm(values, now(), gpus, cities)
    if (result.ok) {
      setErrors({})
      onSubmit(result.body)
    } else {
      setErrors(result.errors)
      setFailedSubmits((n) => n + 1)
    }
  }

  return (
    <form ref={formRef} onSubmit={handleSubmit} noValidate aria-label="Your job">
      <ErrorSummary errors={errors} />
      {presets.length > 0 ? (
        <div className="presets" role="group" aria-labelledby="presets-label">
          <span id="presets-label" className="presets-label">
            Quick fill
          </span>
          <div className="preset-list">
            {presets.map((p) => (
              <button
                key={p.id}
                type="button"
                className="preset"
                aria-pressed={preset === p.id}
                title={p.hint}
                onClick={() => applyPreset(p)}
              >
                {p.label}
              </button>
            ))}
          </div>
        </div>
      ) : null}
      <FormField id="gpu-model" label="GPU model" error={errors.gpuModel}>
        {(c) => (
          <select {...c} value={values.gpuModel} onChange={(e) => set({ gpuModel: e.target.value })}>
            {gpus.map((gpu) => (
              <option key={gpu.id} value={gpu.id}>
                {`${gpu.label} (${gpu.p_max_w} W)`}
              </option>
            ))}
          </select>
        )}
      </FormField>
      <FormField id="gpu-count" label="How many GPUs?" error={errors.gpuCount}>
        {(c) => (
          <input
            {...c}
            type="number"
            inputMode="numeric"
            min={1}
            max={4096}
            step={1}
            value={values.gpuCount}
            onChange={(e) => set({ gpuCount: e.target.value })}
          />
        )}
      </FormField>
      <FormField id="work-hours" label="Hours of work at full GPU power" error={errors.workHours}>
        {(c) => (
          <input
            {...c}
            type="number"
            inputMode="decimal"
            min={0.5}
            max={48}
            step={0.5}
            value={values.workHours}
            onChange={(e) => set({ workHours: e.target.value })}
          />
        )}
      </FormField>
      <FormField
        id="deadline"
        label="Deadline (India time)"
        help="Read as India time (IST), whatever your computer's clock says."
        error={errors.deadline}
      >
        {(c) => (
          <input
            {...c}
            type="datetime-local"
            value={values.deadline}
            onChange={(e) => set({ deadline: e.target.value })}
          />
        )}
      </FormField>
      <FormField
        id="pausable"
        inline
        label="Can the job be paused and resumed safely?"
        help="Single-process training only. Multi-GPU distributed jobs can't pause yet."
      >
        {(c) => (
          <input
            {...c}
            type="checkbox"
            checked={values.pausable}
            onChange={(e) => set({ pausable: e.target.checked })}
          />
        )}
      </FormField>
      <FormField id="city" label="City" error={errors.city}>
        {(c) => (
          <select {...c} value={values.city} onChange={(e) => set({ city: e.target.value })}>
            {cities.map((city) => (
              <option key={city.id} value={city.id}>
                {city.id}
              </option>
            ))}
          </select>
        )}
      </FormField>
      <CoolingFields
        cooling={values.cooling}
        pue={values.pue}
        pueError={errors.pue}
        onCooling={(cooling) => set({ cooling })}
        onPue={(pue) => set({ pue })}
      />
      <button type="submit" className="btn btn-primary" disabled={busy}>
        {busy ? 'Planning…' : 'Plan'}
      </button>
    </form>
  )
}
