import { useState, type FormEvent } from 'react'
import type { CityRow, GpuRow, PlanRequestBody } from '../api/types'
import {
  defaultValues,
  validateJobForm,
  type FieldErrors,
  type JobFormValues,
} from '../lib/jobForm'
import { CoolingFields } from './CoolingFields'
import { FormField } from './FormField'

interface JobFormProps {
  gpus: readonly GpuRow[]
  cities: readonly CityRow[]
  /** True while a plan request is running: the button is disabled. */
  busy: boolean
  onSubmit: (body: PlanRequestBody) => void
  /** The clock, replaceable in tests. */
  now?: () => number
}

/** F1: the job description. Checks the input here, so a bad value makes no request. */
export function JobForm({ gpus, cities, busy, onSubmit, now = Date.now }: JobFormProps) {
  const [values, setValues] = useState<JobFormValues>(() => defaultValues(now(), gpus, cities))
  const [errors, setErrors] = useState<FieldErrors>({})
  const set = (patch: Partial<JobFormValues>) => setValues((current) => ({ ...current, ...patch }))

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const result = validateJobForm(values, now(), gpus, cities)
    if (result.ok) {
      setErrors({})
      onSubmit(result.body)
    } else {
      setErrors(result.errors)
    }
  }

  return (
    <form onSubmit={handleSubmit} noValidate aria-label="Your job">
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
