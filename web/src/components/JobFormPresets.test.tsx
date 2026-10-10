import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { MOCK_ASSUMPTIONS } from '../api/mocks/assumptions'
import type { PlanRequestBody } from '../api/types'
import { JobForm } from './JobForm'

const { gpus, cities } = MOCK_ASSUMPTIONS
const NOW = Date.parse('2026-10-10T20:00:00+05:30')

function setup() {
  const onSubmit = vi.fn<(body: PlanRequestBody) => void>()
  const onValuesChange = vi.fn()
  render(
    <JobForm gpus={gpus} cities={cities} busy={false} onSubmit={onSubmit} now={() => NOW} onValuesChange={onValuesChange} />,
  )
  return { onSubmit, onValuesChange }
}

const field = (name: RegExp) => screen.getByLabelText(name)
const presets = () => within(screen.getByRole('group', { name: /quick fill/i }))

describe('JobForm quick fill', () => {
  it('offers the examples whose GPU is in the list', () => {
    setup()
    expect(presets().getAllByRole('button').map((b) => b.textContent)).toEqual([
      'Overnight fine-tune',
      'Quick experiment',
      'Two-day pretrain',
    ])
  })

  it('hides an example whose GPU is not offered', () => {
    render(<JobForm gpus={gpus.filter((g) => g.id !== 'RTX-3090')} cities={cities} busy={false} onSubmit={vi.fn()} now={() => NOW} />)
    expect(presets().queryByRole('button', { name: 'Quick experiment' })).toBeNull()
  })

  it('fills the job, keeps the city and marks the example as chosen', async () => {
    const { onValuesChange } = setup()
    await userEvent.selectOptions(field(/^city/i), 'Pune')
    await userEvent.click(presets().getByRole('button', { name: 'Two-day pretrain' }))

    expect(field(/^gpu model/i)).toHaveValue('A100-PCIE-40GB')
    expect(field(/how many gpus/i)).toHaveValue(8)
    expect(field(/hours of work at full gpu power/i)).toHaveValue(30)
    expect(field(/can the job be paused and resumed safely/i)).not.toBeChecked()
    // 46 h after 20:00 is 12 Oct 18:00, a whole IST hour inside the 48-hour window
    expect(field(/^deadline/i)).toHaveValue('2026-10-12T18:00')
    expect(field(/^city/i)).toHaveDisplayValue('Pune')
    expect(presets().getByRole('button', { name: 'Two-day pretrain' })).toHaveAttribute('aria-pressed', 'true')
    expect(onValuesChange).toHaveBeenLastCalledWith(expect.objectContaining({ gpuCount: '8', city: 'Pune' }))
  })

  it('drops the chosen mark once the person edits a field', async () => {
    setup()
    await userEvent.click(presets().getByRole('button', { name: 'Quick experiment' }))
    await userEvent.clear(field(/how many gpus/i))
    await userEvent.type(field(/how many gpus/i), '3')
    expect(presets().getByRole('button', { name: 'Quick experiment' })).toHaveAttribute('aria-pressed', 'false')
  })

  it('sends a valid plan request straight from an example', async () => {
    const { onSubmit } = setup()
    await userEvent.click(presets().getByRole('button', { name: 'Two-day pretrain' }))
    await userEvent.click(screen.getByRole('button', { name: 'Plan' }))
    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({ gpu_model: 'A100-PCIE-40GB', gpu_count: 8, work_hours: 30, pausable: false, deadline: '2026-10-12T18:00:00+05:30' }),
    )
  })
})
