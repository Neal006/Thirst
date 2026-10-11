// Dots of the Pareto chart can sit on the same spot (the same plan for several slider positions).
// A click can only reach the top one, so the click is turned into the position of that pile that
// is closest to where the slider is now.

export interface PlacedDot {
  x: number
  y: number
  alpha: number
}

const SAME_SPOT = 1e-9

const sameSpot = (a: number, b: number): boolean => Math.abs(a - b) <= SAME_SPOT * (1 + Math.abs(a))

/** The alpha to select after a click on `clicked`: nearest to `current` among the dots under it. */
export function pickAlpha(dots: readonly PlacedDot[], clicked: PlacedDot, current: number): number {
  const pile = dots.filter((d) => sameSpot(d.x, clicked.x) && sameSpot(d.y, clicked.y))
  let best = clicked.alpha
  let bestGap = Number.POSITIVE_INFINITY
  for (const dot of pile) {
    const gap = Math.abs(dot.alpha - current)
    if (gap < bestGap) {
      best = dot.alpha
      bestGap = gap
    }
  }
  return best
}
