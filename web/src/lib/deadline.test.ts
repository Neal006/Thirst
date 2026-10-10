import { afterEach, describe, expect, it, vi } from 'vitest'
import { defaultDeadline, istLocalToIso, istLocalToMs, msToIstLocal } from './deadline'

afterEach(() => {
  vi.unstubAllEnvs()
})

describe('istLocalToIso', () => {
  it('reads a datetime-local value as India time and writes the +05:30 offset', () => {
    expect(istLocalToIso('2026-10-11T09:00')).toBe('2026-10-11T09:00:00+05:30')
  })

  it('gives the right moment: 09:00 IST is 03:30 UTC', () => {
    expect(istLocalToMs('2026-10-11T09:00')).toBe(Date.parse('2026-10-11T03:30:00Z'))
  })

  it.each([
    '',
    'tomorrow',
    '2026-10-11',
    '2026-10-11T9:00',
    '2026-13-01T09:00',
    '2026-02-30T09:00',
    '2026-10-11T25:00',
    '2026-10-11T09:60',
  ])('refuses %p', (value) => {
    expect(istLocalToIso(value)).toBeNull()
    expect(istLocalToMs(value)).toBeNull()
  })
})

describe('msToIstLocal', () => {
  it('writes the India wall-clock time of a moment', () => {
    expect(msToIstLocal(Date.parse('2026-10-11T03:30:00Z'))).toBe('2026-10-11T09:00')
  })

  it('crosses midnight with the 5.5 hour shift', () => {
    expect(msToIstLocal(Date.parse('2026-10-10T20:00:00Z'))).toBe('2026-10-11T01:30')
  })
})

describe('defaultDeadline', () => {
  it('is tomorrow 09:00 India time', () => {
    expect(defaultDeadline(Date.parse('2026-10-10T20:00:00+05:30'))).toBe('2026-10-11T09:00')
  })

  it('uses the India date, not the UTC date, near midnight', () => {
    // 20:00 UTC on 10 Oct is already 11 Oct in India, so tomorrow is 12 Oct.
    expect(defaultDeadline(Date.parse('2026-10-10T20:00:00Z'))).toBe('2026-10-12T09:00')
  })

  it('rolls over month ends', () => {
    expect(defaultDeadline(Date.parse('2026-10-31T12:00:00+05:30'))).toBe('2026-11-01T09:00')
  })
})

describe('browser time zone does not matter', () => {
  const NOW = Date.parse('2026-10-10T20:00:00+05:30')

  // January offsets in minutes (what getTimezoneOffset reports), to prove the stub took effect.
  it.each([
    ['UTC', 0],
    ['America/Los_Angeles', 480],
    ['Asia/Tokyo', -540],
  ])('gives the same text under TZ=%s', (zone, offset) => {
    vi.stubEnv('TZ', zone)
    expect(new Date(2026, 0, 1, 12).getTimezoneOffset()).toBe(offset)
    expect(defaultDeadline(NOW)).toBe('2026-10-11T09:00')
    expect(istLocalToIso('2026-10-11T09:00')).toBe('2026-10-11T09:00:00+05:30')
    expect(istLocalToMs('2026-10-11T09:00')).toBe(Date.parse('2026-10-11T03:30:00Z'))
    expect(msToIstLocal(NOW)).toBe('2026-10-10T20:00')
  })
})
