import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'

// jsdom has no layout and no ResizeObserver. Recharts' ResponsiveContainer needs both, so the
// stub reports a fixed 600 x 260 box as soon as an element is observed.
class ResizeObserverStub {
  private readonly callback: ResizeObserverCallback

  constructor(callback: ResizeObserverCallback) {
    this.callback = callback
  }

  private static readonly reported = new WeakSet<Element>()

  observe(target: Element): void {
    // Report once per element, after the current render, or the chart would re-render forever.
    if (ResizeObserverStub.reported.has(target)) return
    ResizeObserverStub.reported.add(target)
    const contentRect = { width: 600, height: 260, top: 0, left: 0, right: 600, bottom: 260, x: 0, y: 0 }
    const entry = { target, contentRect } as unknown as ResizeObserverEntry
    queueMicrotask(() => this.callback([entry], this as unknown as ResizeObserver))
  }

  unobserve(): void {}
  disconnect(): void {}
}

if (typeof globalThis.ResizeObserver === 'undefined') {
  globalThis.ResizeObserver = ResizeObserverStub as unknown as typeof ResizeObserver
}

afterEach(() => {
  cleanup()
})
