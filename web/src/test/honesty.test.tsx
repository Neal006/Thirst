import { render } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import { Amount } from '../components/Amount'
import { Range } from '../components/Range'
import { findUntaggedNumbers } from './honesty'

function scan(ui: React.ReactElement): string[] {
  const { container } = render(<MemoryRouter>{ui}</MemoryRouter>)
  return findUntaggedNumbers(container)
}

describe('findUntaggedNumbers', () => {
  it('accepts numbers made by Range and Amount', () => {
    expect(scan(<p><Range range={[15, 30]} unit="%" tag="modelled" /></p>)).toEqual([])
    expect(scan(<p><Amount value={3.9} unit="kWh" tag="measured" /></p>)).toEqual([])
  })

  it.each([
    ['a bare percent range', <p key="a">Saves 15 to 30%</p>],
    ['a bare energy', <p key="b">Used 3.9 kWh</p>],
    ['a bare mass', <p key="c">That is 4 kg of CO₂</p>],
    ['bare litres', <p key="d">Used 120 L of water</p>],
    ['a negative percent', <p key="e">Change: -4%</p>],
    ['a number in a table cell with no chip in the row', <table key="f"><tbody><tr><td>9 kWh</td></tr></tbody></table>],
  ])('catches %s', (_name, ui) => {
    expect(scan(ui).length).toBeGreaterThan(0)
  })

  it('accepts a number whose chip is next to it in the same list item or row', () => {
    expect(
      scan(
        <ul>
          <li>
            Used 120 L <a className="tag tag-modelled" href="/assumptions">modelled</a>
          </li>
        </ul>,
      ),
    ).toEqual([])
  })

  it('does not accept a chip that is far away', () => {
    const found = scan(
      <section>
        <div><div><p>Used 120 L</p></div></div>
        <a className="tag tag-modelled" href="/assumptions">modelled</a>
      </section>,
    )
    expect(found.length).toBe(1)
  })

  it('exempts a setting the person picks, such as the GPU power level', () => {
    expect(scan(<p>GPU at <strong data-kind="setting">85%</strong></p>)).toEqual([])
  })

  it('does not mistake words for units', () => {
    expect(scan(<p>Step 5 Large jobs, 2 Lab sites, 3 Layers</p>)).toEqual([])
    expect(scan(<p>1.4 is a common value</p>)).toEqual([])
  })

  it('needs a tag in the figure for numbers inside a chart', () => {
    const bare = scan(<figure><svg><text>12 kg</text></svg><figcaption>no chip</figcaption></figure>)
    expect(bare.length).toBe(1)
    const tagged = scan(
      <figure>
        <svg><text>12 kg</text></svg>
        <figcaption><a className="tag tag-modelled" href="/assumptions">modelled</a></figcaption>
      </figure>,
    )
    expect(tagged).toEqual([])
  })
})
