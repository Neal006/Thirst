import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import { Range } from './Range'
import { TagChip } from './TagChip'
import { tagInfo } from '../lib/tags'
import type { Tag } from '../api/types'

const inRouter = (ui: React.ReactElement) => render(<MemoryRouter>{ui}</MemoryRouter>)

describe('tag labels', () => {
  const tags: Tag[] = ['measured', 'modelled', 'placeholder', 'sourced', 'calibrated', 'unverified']

  it.each(tags)('%s has a label, a style and an anchor on the assumptions page', (tag) => {
    const info = tagInfo(tag)
    expect(info.label.length).toBeGreaterThan(0)
    expect(info.className).toMatch(/^tag tag-/)
    expect(info.anchor).toBe(`status-${tag}`)
    expect(info.help.length).toBeGreaterThan(10)
  })

  it('treats an unknown status as modelled-looking but never as measured', () => {
    const info = tagInfo('something_new' as Tag)
    expect(info.label).toBe('something new')
    expect(info.className).not.toContain('measured')
  })

  it.each([undefined, null, 5, '', {}])('falls back to "unknown" for %p, never "undefined"', (value) => {
    const info = tagInfo(value as unknown as Tag)
    expect(info.label).toBe('unknown')
    expect(info.className).toBe('tag tag-unknown')
    expect(`${info.label} ${info.className} ${info.anchor} ${info.help}`).not.toMatch(/undefined|null|object/i)
    expect(info.help.length).toBeGreaterThan(10)
  })

  it('renders an "unknown" chip for a missing tag', () => {
    inRouter(<TagChip tag={undefined as unknown as Tag} />)
    expect(screen.getByRole('link', { name: 'unknown' })).toBeInTheDocument()
    expect(document.body).not.toHaveTextContent(/undefined/)
  })

  it('writes design_choice in plain words', () => {
    expect(tagInfo('design_choice' as Tag).label).toBe('design choice')
  })
})

describe('TagChip', () => {
  it('shows the tag and links to its place on the assumptions page', () => {
    inRouter(<TagChip tag="modelled" />)
    const link = screen.getByRole('link', { name: /modelled/i })
    expect(link).toHaveAttribute('href', '/assumptions#status-modelled')
  })

  it('links to one factor when it is given', () => {
    inRouter(<TagChip tag="placeholder" factor="tau_70" />)
    expect(screen.getByRole('link', { name: /placeholder/i })).toHaveAttribute(
      'href',
      '/assumptions#tau_70',
    )
  })

  it('explains itself to screen readers', () => {
    inRouter(<TagChip tag="measured" />)
    expect(screen.getByRole('link', { name: /measured/i })).toHaveAccessibleDescription(
      /read from the hardware/i,
    )
  })
})

describe('Range', () => {
  it('shows low to high, the unit and a tag', () => {
    inRouter(<Range range={[15, 30]} unit="%" tag="modelled" label="stress-weighted water" />)
    expect(screen.getByText('15 to 30%')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /modelled/i })).toBeInTheDocument()
  })

  it('says about X when both ends are the same', () => {
    inRouter(<Range range={[20, 20]} unit="%" tag="modelled" />)
    expect(screen.getByText('about 20%')).toBeInTheDocument()
  })

  it('writes units that are words with a space', () => {
    inRouter(<Range range={[0.1, 0.2]} unit="person-days" tag="modelled" />)
    expect(screen.getByText('0.1 to 0.2 person-days')).toBeInTheDocument()
  })

  it('is always followed by a chip: a bare range cannot be rendered', () => {
    const { container } = inRouter(<Range range={[1, 2]} unit="kg" tag="sourced" />)
    expect(container.querySelectorAll('.tag')).toHaveLength(1)
  })
})
