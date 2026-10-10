// A lint-like check for PRD G5 (plan 6.4.c): every number with a %, L, kg or kWh unit on a page
// must sit next to a tag chip. It reads the rendered DOM, so it catches a page that prints a
// bare number no matter which component wrote it.

const UNIT_NUMBER = /(?<![\w.])-?\d[\d,]*(?:\.\d+)?\s?(?:%|kWh|kg|L|litres?)(?![A-Za-z])/g
/** How many parents up a tag chip may be and still count as "next to" the number. */
const REACH = 2

function isExempt(node: Node): boolean {
  const el = node.parentElement
  if (!el) return true
  // Settings the person chooses (a power level) are not measurements; text for screen readers
  // and code are not numbers on the page.
  return el.closest('[data-kind="setting"], script, style, [hidden], code') !== null
}

function hasTagNearby(textNode: Node): boolean {
  const inSvg = textNode.parentElement?.closest('svg')
  if (inSvg) {
    // Chart axes and ticks: the figure's caption must carry the tags.
    return inSvg.closest('figure')?.querySelector('.tag') != null
  }
  let el: Element | null = textNode.parentElement
  for (let step = 0; el && step < REACH; step++) {
    if (el.matches('.tag') || el.querySelector('.tag')) return true
    el = el.parentElement
  }
  return false
}

/** The offending texts: numbers with a unit and no tag chip beside them. Empty means honest. */
export function findUntaggedNumbers(root: HTMLElement): string[] {
  const found: string[] = []
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT)
  for (let node = walker.nextNode(); node; node = walker.nextNode()) {
    const text = node.textContent ?? ''
    const matches = text.match(UNIT_NUMBER)
    if (!matches || isExempt(node) || hasTagNearby(node)) continue
    found.push(...matches.map((m) => `${m.trim()} in "${text.trim().slice(0, 60)}"`))
  }
  return found
}
