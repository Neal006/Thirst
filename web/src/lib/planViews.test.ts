import { describe, expect, it } from 'vitest'
import { distinctPlan } from '../test/planFixture'
import {
  calendarFile,
  cleanestStart,
  dayRows,
  hourCells,
  istDeadlineText,
  runCommand,
  shareQuery,
  whyThisTime,
} from './planViews'

describe('plan views helpers', () => {
  const plan = distinctPlan()
  const entry = plan.chosen

  it('marks one cell per hour with a level from 0 to 4 and the run hours', () => {
    const cells = hourCells(plan, entry)
    expect(cells).toHaveLength(plan.series.length)
    expect(cells.every((c) => c.level >= 0 && c.level <= 4)).toBe(true)
    expect(cells.filter((c) => c.state === 'run').length).toBeGreaterThan(0)
    expect(cells.filter((c) => c.inCleanest)).toHaveLength(3)
  })

  it('groups the hours into days of 24 columns', () => {
    const rows = dayRows(hourCells(plan, entry))
    expect(rows.length).toBeGreaterThanOrEqual(2)
    rows.forEach((r) => expect(r.cells).toHaveLength(24))
  })

  it('finds the cleanest three hours, or none for a short series', () => {
    expect(cleanestStart(plan.series)).not.toBeNull()
    expect(cleanestStart(plan.series.slice(0, 2))).toBeNull()
  })

  it('explains the start time in one sentence', () => {
    expect(whyThisTime(plan, entry)).toMatch(/cleanest/i)
  })

  it('writes the run command with the deadline in India time', () => {
    expect(istDeadlineText('2026-10-11T03:30:00Z')).toBe('2026-10-11 09:00')
    const cmd = runCommand(plan)
    expect(cmd).toMatch(/^thirst run --hours \d/)
    expect(cmd).toContain('-- python train.py')
  })

  it('makes a calendar file with one event and a reminder', () => {
    const ics = calendarFile(plan, entry)
    expect(ics).toContain('BEGIN:VEVENT')
    expect(ics).toContain('TRIGGER:-PT10M')
    expect(ics).toMatch(/DTSTART:\d{8}T\d{6}Z/)
  })

  it('makes a share query that names the whole job', () => {
    const q = new URLSearchParams(shareQuery(plan))
    expect(q.get('city')).toBe(plan.inputs.city)
    expect(q.get('gpu')).toBe(plan.inputs.gpu_model)
    expect(q.get('deadline')).toMatch(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/)
  })
})
