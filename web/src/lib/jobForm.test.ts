import { describe, expect, it } from 'vitest'
import { MOCK_ASSUMPTIONS } from '../api/mocks/assumptions'
import { defaultValues, validateJobForm, type JobFormValues } from './jobForm'

const { gpus, cities } = MOCK_ASSUMPTIONS
// 10 Oct 2026, 20:00 India time.
const NOW = Date.parse('2026-10-10T20:00:00+05:30')

const defaults = (): JobFormValues => defaultValues(NOW, gpus, cities)
const withValues = (patch: Partial<JobFormValues>): JobFormValues => ({ ...defaults(), ...patch })

describe('defaultValues', () => {
  it('follows the plan: 2 GPUs, 6 hours, tomorrow 09:00 IST, can pause, Chennai, room AC, PUE 1.4', () => {
    expect(defaults()).toEqual({
      gpuModel: 'RTX-4090',
      gpuCount: '2',
      workHours: '6',
      deadline: '2026-10-11T09:00',
      pausable: true,
      city: 'Chennai',
      cooling: 'room_ac',
      pue: '1.4',
    })
  })

  it('falls back to the first GPU and city when the usual defaults are missing', () => {
    const values = defaultValues(NOW, [gpus[2]], [cities[3]])
    expect(values.gpuModel).toBe(gpus[2].id)
    expect(values.city).toBe(cities[3].id)
  })

  it('has empty choices when the lists are empty', () => {
    const values = defaultValues(NOW, [], [])
    expect(values.gpuModel).toBe('')
    expect(values.city).toBe('')
  })
})

describe('validateJobForm: the request body (08 section 3.1)', () => {
  it('builds the body for the default values', () => {
    const result = validateJobForm(defaults(), NOW, gpus, cities)
    expect(result).toEqual({
      ok: true,
      body: {
        city: 'Chennai',
        cooling: 'room_ac',
        gpu_model: 'RTX-4090',
        gpu_count: 2,
        work_hours: 6,
        deadline: '2026-10-11T09:00:00+05:30',
        pausable: true,
      },
    })
  })

  it('sends pue only for a cooling tower', () => {
    const tower = validateJobForm(withValues({ cooling: 'evaporative', pue: '1.8' }), NOW, gpus, cities)
    expect(tower.ok && tower.body).toMatchObject({ cooling: 'evaporative', pue: 1.8 })
    const room = validateJobForm(withValues({ pue: '9' }), NOW, gpus, cities)
    expect(room.ok && 'pue' in room.body).toBe(false)
  })

  it('sends pausable false when the toggle is off', () => {
    const result = validateJobForm(withValues({ pausable: false }), NOW, gpus, cities)
    expect(result.ok && result.body.pausable).toBe(false)
  })

  it('accepts the limits: 1 and 4096 GPUs, 0.5 and 48 hours', () => {
    expect(validateJobForm(withValues({ gpuCount: '1', workHours: '0.5' }), NOW, gpus, cities).ok).toBe(true)
    const far = withValues({ gpuCount: '4096', workHours: '48', deadline: '2026-10-13T09:00' })
    expect(validateJobForm(far, NOW, gpus, cities).ok).toBe(true)
  })
})

describe('validateJobForm: bad input gets a plain message next to its field', () => {
  const errorsFor = (patch: Partial<JobFormValues>) => {
    const result = validateJobForm(withValues(patch), NOW, gpus, cities)
    return result.ok ? {} : result.errors
  }

  it.each(['', '0', '4097', '1.5', 'abc', '-2', 'NaN', 'Infinity'])('rejects %p GPUs', (value) => {
    expect(errorsFor({ gpuCount: value }).gpuCount).toMatch(/whole number.*1.*4096/i)
  })

  it.each(['', '0', '0.4', '48.5', 'abc', '-1', 'Infinity'])('rejects %p hours', (value) => {
    expect(errorsFor({ workHours: value }).workHours).toMatch(/0\.5.*48/)
  })

  it('rejects a PUE outside 1.0 to 3.0, but only for a cooling tower', () => {
    expect(errorsFor({ cooling: 'evaporative', pue: '0.9' }).pue).toMatch(/1\.0.*3\.0/)
    expect(errorsFor({ cooling: 'evaporative', pue: '3.1' }).pue).toMatch(/1\.0.*3\.0/)
    expect(errorsFor({ cooling: 'evaporative', pue: '' }).pue).toMatch(/1\.0.*3\.0/)
    expect(errorsFor({ cooling: 'air_chiller', pue: 'junk' }).pue).toBeUndefined()
  })

  it('rejects a missing or unreal deadline', () => {
    expect(errorsFor({ deadline: '' }).deadline).toMatch(/pick a deadline/i)
    expect(errorsFor({ deadline: '2026-02-30T09:00' }).deadline).toMatch(/pick a deadline/i)
  })

  it('rejects a deadline in the past', () => {
    expect(errorsFor({ deadline: '2026-10-09T09:00' }).deadline).toMatch(/in the past/i)
  })

  it('rejects a deadline earlier than now plus the work hours, and says when is earliest', () => {
    // now 20:00 + 6 h = 02:00 on 11 Oct; 01:00 is too soon.
    const message = errorsFor({ deadline: '2026-10-11T01:00' }).deadline
    expect(message).toMatch(/6 hours/)
    expect(message).toMatch(/Sun 11 Oct 02:00/)
    expect(message).toMatch(/India time/)
  })

  it('accepts a deadline exactly now plus the work hours', () => {
    expect(errorsFor({ deadline: '2026-10-11T02:00' }).deadline).toBeUndefined()
  })

  it('rejects a GPU or city that is not in the lists', () => {
    expect(errorsFor({ gpuModel: 'Nope' }).gpuModel).toMatch(/pick a gpu/i)
    expect(errorsFor({ gpuModel: '' }).gpuModel).toMatch(/pick a gpu/i)
    expect(errorsFor({ city: 'Atlantis' }).city).toMatch(/pick a city/i)
  })

  it('reports every problem at once', () => {
    const errors = errorsFor({ gpuCount: '0', workHours: '0', deadline: '' })
    expect(Object.keys(errors).sort()).toEqual(['deadline', 'gpuCount', 'workHours'])
  })
})
