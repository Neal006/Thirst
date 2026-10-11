import { describe, expect, it } from 'vitest'
import { pickAlpha, type PlacedDot } from './paretoPick'

const dot = (alpha: number, x = alpha, y = 1): PlacedDot => ({ alpha, x, y })

describe('pickAlpha', () => {
  it('returns the clicked alpha when nothing else is on that spot', () => {
    const dots = [dot(0.1), dot(0.2), dot(0.3)]
    expect(pickAlpha(dots, dots[2], 0.1)).toBe(0.3)
  })

  it('returns the alpha of the pile closest to the current one', () => {
    const pile = [dot(0.3, 5), dot(0.4, 5), dot(0.5, 5)]
    expect(pickAlpha(pile, pile[2], 0.0)).toBe(0.3)
    expect(pickAlpha(pile, pile[0], 1.0)).toBe(0.5)
    expect(pickAlpha(pile, pile[0], 0.4)).toBe(0.4)
  })

  it('takes the lower alpha when two are equally close', () => {
    const pile = [dot(0.25, 5), dot(0.75, 5)]
    expect(pickAlpha(pile, pile[1], 0.5)).toBe(0.25)
  })

  it('treats dots that differ in y as different spots', () => {
    const dots = [dot(0.3, 5, 1), dot(0.4, 5, 2)]
    expect(pickAlpha(dots, dots[1], 0.3)).toBe(0.4)
  })

  it('falls back to the clicked alpha when the clicked dot is not in the list', () => {
    expect(pickAlpha([], dot(0.7), 0.1)).toBe(0.7)
  })
})
