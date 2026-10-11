import AxeBuilder from '@axe-core/playwright'
import type { Page } from '@playwright/test'
import { expect, test } from './fixtures'
import { openFirstSiteFromBoard, PAGES, submitDefaultPlan } from './helpers'

const WCAG_TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'] as const
const BLOCKING_IMPACTS = new Set(['serious', 'critical'])

interface Finding {
  readonly id: string
  readonly impact: string
  readonly help: string
  readonly nodes: readonly string[]
}

/** Runs axe on the current page and returns the serious and critical violations only. */
async function seriousViolations(page: Page): Promise<Finding[]> {
  const results = await new AxeBuilder({ page }).withTags([...WCAG_TAGS]).analyze()
  return results.violations
    .filter((v) => v.impact !== null && v.impact !== undefined && BLOCKING_IMPACTS.has(v.impact))
    .map((v) => ({
      id: v.id,
      impact: v.impact ?? 'unknown',
      help: v.help,
      nodes: v.nodes.slice(0, 5).map((n) => `${n.target.join(' ')} :: ${n.failureSummary?.split('\n')[1]?.trim() ?? ''}`),
    }))
}

function format(findings: readonly Finding[]): string {
  return findings.map((f) => `[${f.impact}] ${f.id}: ${f.help}\n    ${f.nodes.join('\n    ')}`).join('\n')
}

async function audit(page: Page, label: string): Promise<void> {
  const findings = await seriousViolations(page)
  if (findings.length > 0) {
    test.info().annotations.push({ type: 'a11y', description: `${label}: ${findings.map((f) => f.id).join(', ')}` })
  }
  expect(findings, `serious or critical axe violations on ${label}:\n${format(findings)}`).toEqual([])
}

test.describe('accessibility (axe, serious and critical)', () => {
  for (const entry of PAGES) {
    test(`${entry.path}`, async ({ page }) => {
      await page.goto(entry.path)
      await expect(page.getByRole('heading', { level: 1, name: entry.heading })).toBeVisible()
      await page.waitForLoadState('networkidle')
      await audit(page, entry.path)
    })
  }

  test('/plan with a result', async ({ page }) => {
    await submitDefaultPlan(page)
    await page.waitForLoadState('networkidle')
    await audit(page, '/plan with a result')
  })

  test('a site page', async ({ page }) => {
    await openFirstSiteFromBoard(page)
    await expect(page.getByRole('region', { name: 'Score' })).toBeVisible({ timeout: 20_000 })
    await page.waitForLoadState('networkidle')
    await audit(page, 'a site page')
  })

  test('a receipt page', async ({ page }) => {
    await openFirstSiteFromBoard(page)
    const view = page.getByRole('region', { name: 'Recent receipts' }).getByRole('link', { name: 'View' }).first()
    test.skip((await view.count()) === 0, 'the demo site has no receipts')
    await view.click()
    await expect(page.getByRole('heading', { name: 'How this was scored' })).toBeVisible({ timeout: 20_000 })
    await audit(page, 'a receipt page')
  })

  test('the 404 page', async ({ page }) => {
    await page.goto('/no-such-page')
    await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
    await audit(page, 'the 404 page')
  })
})
