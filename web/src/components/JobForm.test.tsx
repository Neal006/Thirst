import { fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { MOCK_ASSUMPTIONS } from '../api/mocks/assumptions'
import type { PlanRequestBody } from '../api/types'
import { defaultValues } from '../lib/jobForm'
import { JobForm } from './JobForm'

const { gpus, cities } = MOCK_ASSUMPTIONS
// 10 Oct 2026, 20:00 India time: the default deadline is 11 Oct 09:00.
const NOW = Date.parse('2026-10-10T20:00:00+05:30')

afterEach(() => {
  vi.unstubAllEnvs()
})

function setup(busy = false) {
  const onSubmit = vi.fn<(body: PlanRequestBody) => void>()
  render(<JobForm gpus={gpus} cities={cities} busy={busy} onSubmit={onSubmit} now={() => NOW} />)
  return { onSubmit }
}

const field = (name: RegExp) => screen.getByLabelText(name)

describe('JobForm defaults', () => {
  it('shows the defaults from the plan', () => {
    setup()
    expect(field(/^gpu model/i)).toHaveDisplayValue('NVIDIA GeForce RTX 4090 (450 W)')
    expect(field(/how many gpus/i)).toHaveValue(2)
    expect(field(/hours of work at full gpu power/i)).toHaveValue(6)
    expect(field(/^deadline/i)).toHaveValue('2026-10-11T09:00')
    expect(field(/can the job be paused and resumed safely/i)).toBeChecked()
    expect(field(/^city/i)).toHaveDisplayValue('Chennai')
    expect(field(/^cooling/i)).toHaveDisplayValue('Room AC')
  })

  it('lists the GPUs from the assumptions with their maximum power', () => {
    setup()
    const options = Array.from(
      (field(/^gpu model/i) as HTMLSelectElement).options,
      (o) => o.textContent,
    )
    expect(options).toContain('NVIDIA H100 SXM (700 W)')
    expect(options).toHaveLength(gpus.length)
  })

  it('lists the six seed cities and the three cooling types', () => {
    setup()
    expect((field(/^city/i) as HTMLSelectElement).options).toHaveLength(6)
    const cooling = Array.from((field(/^cooling/i) as HTMLSelectElement).options, (o) => o.textContent)
    expect(cooling).toEqual(['Room AC', 'Air-cooled chiller', 'Cooling tower'])
  })

  it('explains that distributed jobs cannot pause yet', () => {
    setup()
    expect(field(/can the job be paused/i)).toHaveAccessibleDescription(/single-machine training only/i)
  })

  it('asks for the PUE only with a cooling tower, starting at 1.4', async () => {
    setup()
    expect(screen.queryByLabelText(/pue/i)).not.toBeInTheDocument()
    await userEvent.selectOptions(field(/^cooling/i), 'evaporative')
    expect(field(/pue/i)).toHaveValue(1.4)
    await userEvent.selectOptions(field(/^cooling/i), 'room_ac')
    expect(screen.queryByLabelText(/pue/i)).not.toBeInTheDocument()
  })
})

describe('JobForm draft', () => {
  it('reports every change, so a parent can keep the values across a remount', async () => {
    const onValuesChange = vi.fn()
    render(
      <JobForm gpus={gpus} cities={cities} busy={false} onSubmit={() => {}} now={() => NOW} onValuesChange={onValuesChange} />,
    )
    await userEvent.selectOptions(field(/^city/i), 'Pune')
    expect(onValuesChange).toHaveBeenLastCalledWith(expect.objectContaining({ city: 'Pune', gpuCount: '2' }))
  })

  it('starts from the values it is given', () => {
    const initial = { ...defaultValues(NOW, gpus, cities), gpuCount: '8', city: 'Pune' }
    render(
      <JobForm gpus={gpus} cities={cities} busy={false} onSubmit={() => {}} now={() => NOW} getDraft={() => initial} />,
    )
    expect(field(/how many gpus/i)).toHaveValue(8)
    expect(field(/^city/i)).toHaveDisplayValue('Pune')
  })
})

describe('JobForm submit', () => {
  it('sends the body from the plan (08 section 3.1) with an IST deadline', async () => {
    const { onSubmit } = setup()
    await userEvent.click(screen.getByRole('button', { name: 'Plan' }))
    expect(onSubmit).toHaveBeenCalledTimes(1)
    expect(onSubmit).toHaveBeenCalledWith({
      city: 'Chennai',
      cooling: 'room_ac',
      gpu_model: 'RTX-4090',
      gpu_count: 2,
      work_hours: 6,
      deadline: '2026-10-11T09:00:00+05:30',
      pausable: true,
    })
  })

  it('reads the deadline as India time when the browser is on UTC', async () => {
    vi.stubEnv('TZ', 'UTC')
    const { onSubmit } = setup()
    fireEvent.change(field(/^deadline/i), { target: { value: '2026-10-12T18:30' } })
    await userEvent.click(screen.getByRole('button', { name: 'Plan' }))
    expect(onSubmit.mock.calls[0][0].deadline).toBe('2026-10-12T18:30:00+05:30')
  })

  it('sends the values the person typed', async () => {
    const { onSubmit } = setup()
    await userEvent.selectOptions(field(/^gpu model/i), 'H100-SXM')
    await userEvent.clear(field(/how many gpus/i))
    await userEvent.type(field(/how many gpus/i), '8')
    await userEvent.clear(field(/hours of work/i))
    await userEvent.type(field(/hours of work/i), '12.5')
    await userEvent.click(field(/can the job be paused/i))
    await userEvent.selectOptions(field(/^city/i), 'Pune')
    await userEvent.selectOptions(field(/^cooling/i), 'evaporative')
    await userEvent.clear(field(/pue/i))
    await userEvent.type(field(/pue/i), '1.8')
    await userEvent.click(screen.getByRole('button', { name: 'Plan' }))
    expect(onSubmit).toHaveBeenCalledWith({
      city: 'Pune',
      cooling: 'evaporative',
      pue: 1.8,
      gpu_model: 'H100-SXM',
      gpu_count: 8,
      work_hours: 12.5,
      deadline: '2026-10-11T09:00:00+05:30',
      pausable: false,
    })
  })

  it('submits with the Enter key', async () => {
    const { onSubmit } = setup()
    await userEvent.type(field(/how many gpus/i), '{Enter}')
    expect(onSubmit).toHaveBeenCalledTimes(1)
  })

  it('is disabled while the plan is loading', () => {
    setup(true)
    const button = screen.getByRole('button', { name: /planning/i })
    expect(button).toBeDisabled()
  })
})

describe('JobForm bad input', () => {
  it('shows an inline error and makes no request for a deadline in the past', async () => {
    const { onSubmit } = setup()
    fireEvent.change(field(/^deadline/i), { target: { value: '2026-10-09T09:00' } })
    await userEvent.click(screen.getByRole('button', { name: 'Plan' }))
    expect(onSubmit).not.toHaveBeenCalled()
    const input = field(/^deadline/i)
    expect(input).toBeInvalid()
    expect(input).toHaveAccessibleDescription(/in the past/i)
  })

  it('shows the earliest possible deadline when the job cannot finish in time', async () => {
    const { onSubmit } = setup()
    fireEvent.change(field(/^deadline/i), { target: { value: '2026-10-11T01:00' } })
    await userEvent.click(screen.getByRole('button', { name: 'Plan' }))
    expect(onSubmit).not.toHaveBeenCalled()
    expect(field(/^deadline/i)).toHaveAccessibleDescription(/Sun 11 Oct 02:00/)
  })

  it('flags several fields at once and clears the errors when they are fixed', async () => {
    const { onSubmit } = setup()
    await userEvent.clear(field(/how many gpus/i))
    await userEvent.type(field(/how many gpus/i), '5000')
    await userEvent.clear(field(/hours of work/i))
    await userEvent.type(field(/hours of work/i), '99')
    await userEvent.click(screen.getByRole('button', { name: 'Plan' }))
    expect(field(/how many gpus/i)).toBeInvalid()
    expect(field(/hours of work/i)).toBeInvalid()
    expect(onSubmit).not.toHaveBeenCalled()

    await userEvent.clear(field(/how many gpus/i))
    await userEvent.type(field(/how many gpus/i), '4')
    await userEvent.clear(field(/hours of work/i))
    await userEvent.type(field(/hours of work/i), '3')
    await userEvent.click(screen.getByRole('button', { name: 'Plan' }))
    expect(field(/how many gpus/i)).toBeValid()
    expect(onSubmit).toHaveBeenCalledTimes(1)
  })

  it('announces the problems in an alert and moves focus to the first invalid field', async () => {
    const { onSubmit } = setup()
    // The deadline is wrong too, but it comes after the GPU count in the form.
    fireEvent.change(field(/^deadline/i), { target: { value: '' } })
    await userEvent.clear(field(/how many gpus/i))
    await userEvent.type(field(/how many gpus/i), '0')
    await userEvent.click(screen.getByRole('button', { name: 'Plan' }))
    expect(onSubmit).not.toHaveBeenCalled()

    const alert = screen.getByRole('alert')
    expect(alert).toHaveTextContent(/2 problems/i)
    expect(alert).toHaveTextContent(/whole number of GPUs/i)
    expect(alert).toHaveTextContent(/pick a deadline/i)
    expect(field(/how many gpus/i)).toHaveFocus()
  })

  it('says "1 problem" for a single error and removes the alert once the form is valid', async () => {
    const { onSubmit } = setup()
    await userEvent.clear(field(/hours of work/i))
    await userEvent.click(screen.getByRole('button', { name: 'Plan' }))
    expect(screen.getByRole('alert')).toHaveTextContent(/1 problem\b/i)
    expect(field(/hours of work/i)).toHaveFocus()

    await userEvent.type(field(/hours of work/i), '3')
    await userEvent.click(screen.getByRole('button', { name: 'Plan' }))
    expect(onSubmit).toHaveBeenCalledTimes(1)
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('moves focus again when the same mistake is submitted twice', async () => {
    setup()
    await userEvent.clear(field(/how many gpus/i))
    await userEvent.click(screen.getByRole('button', { name: 'Plan' }))
    expect(field(/how many gpus/i)).toHaveFocus()
    await userEvent.click(field(/^city/i))
    await userEvent.click(screen.getByRole('button', { name: 'Plan' }))
    expect(field(/how many gpus/i)).toHaveFocus()
  })

  it('never shows NaN, undefined or Infinity', async () => {
    setup()
    await userEvent.clear(field(/how many gpus/i))
    await userEvent.click(screen.getByRole('button', { name: 'Plan' }))
    expect(document.body).not.toHaveTextContent(/NaN|undefined|Infinity/)
  })
})
