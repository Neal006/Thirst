import { describe, expect, it } from 'vitest'
import type { AssumptionRow } from '../api/types'
import { groupFactors, plainNumber, rangeText, safeUrl, statusNote } from './assumptionsView'

function row(over: Partial<AssumptionRow>): AssumptionRow {
  return {
    id: 'x',
    group: 'cooling',
    label: 'X',
    value: 1,
    low: 1,
    high: 1,
    unit: 'ratio',
    status: 'sourced',
    source: 's',
    source_url: '',
    notes: '',
    ...over,
  }
}

describe('plainNumber', () => {
  it.each([
    [0.727, '0.727'],
    [3, '3'],
    [2.55, '2.55'],
    [1234.5678, '1235'],
    [0.000123, '0.000123'],
    [0, '0'],
    [-4.5, '-4.5'],
  ])('writes %p as %p', (value, text) => {
    expect(plainNumber(value)).toBe(text)
  })

  it.each([Number.NaN, Number.POSITIVE_INFINITY, Number.NEGATIVE_INFINITY])('never shows %p', (value) => {
    expect(plainNumber(value)).toBe('--')
  })
})

describe('rangeText', () => {
  it('is "low to high" when they differ', () => {
    expect(rangeText(row({ low: 2.55, high: 3.45 }))).toBe('2.55 to 3.45')
  })

  it('is empty when there is no spread', () => {
    expect(rangeText(row({ low: 5, high: 5 }))).toBeNull()
  })

  it('sorts a swapped pair', () => {
    expect(rangeText(row({ low: 9, high: 4 }))).toBe('4 to 9')
  })
})

describe('groupFactors', () => {
  it('orders groups as the Assumptions page lists them and names them in plain words', () => {
    const groups = groupFactors([
      row({ id: 'a', group: 'people' }),
      row({ id: 'b', group: 'cooling' }),
      row({ id: 'c', group: 'gpu' }),
      row({ id: 'd', group: 'grid_carbon' }),
      row({ id: 'e', group: 'cooling' }),
    ])
    expect(groups.map((g) => g.label)).toEqual(['Cooling', 'Grid carbon', 'GPU and power cap', 'People'])
    expect(groups[0].rows.map((r) => r.id)).toEqual(['b', 'e'])
  })

  it('puts unknown groups last under a readable name', () => {
    const groups = groupFactors([row({ group: 'zzz_new' }), row({ group: 'cooling' })])
    expect(groups.map((g) => g.label)).toEqual(['Cooling', 'Zzz new'])
  })

  it('returns nothing for no rows', () => {
    expect(groupFactors([])).toEqual([])
  })
})

describe('statusNote', () => {
  it('says what a placeholder GPU factor will be replaced by', () => {
    expect(statusNote(row({ group: 'gpu', status: 'placeholder' }))).toBe(
      'Placeholder: to be replaced by our measured sweep',
    )
  })

  it('has a note for other placeholders and none for sourced values', () => {
    expect(statusNote(row({ status: 'placeholder' }))).toMatch(/^Placeholder:/)
    expect(statusNote(row({ status: 'sourced' }))).toBeNull()
  })
})

describe('safeUrl', () => {
  it('lets https and http links through', () => {
    expect(safeUrl('https://open-meteo.com/')).toBe('https://open-meteo.com/')
    expect(safeUrl('http://example.org/a')).toBe('http://example.org/a')
  })

  it.each(['', 'javascript:alert(1)', 'data:text/html,hi', 'ftp://x', '//evil.test', 'not a url'])(
    'refuses %p',
    (url) => {
      expect(safeUrl(url)).toBeNull()
    },
  )
})
