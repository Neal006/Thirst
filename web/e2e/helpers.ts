import { expect, type Locator, type Page } from '@playwright/test'

/** Names of the main pages, in the order of the header navigation. */
export const PAGES = [
  { path: '/', heading: /every gpu hour drinks water/i },
  { path: '/plan', heading: /when should your gpu job run/i },
  { path: '/leaderboard', heading: /^leaderboard$/i },
  { path: '/assumptions', heading: /^assumptions$/i },
] as const

/** Waits until the page's single h1 is on screen, which means the route has rendered. */
export async function expectHeading(page: Page, name: RegExp): Promise<void> {
  await expect(page.getByRole('heading', { level: 1, name })).toBeVisible()
}

/** Pixels the page is wider than its viewport (0 means no horizontal scroll). */
export async function horizontalOverflow(page: Page): Promise<number> {
  return page.evaluate(() => {
    const root = document.scrollingElement ?? document.documentElement
    return Math.max(0, root.scrollWidth - window.innerWidth)
  })
}

/** True when the element's box is at least partly inside the viewport. */
export async function isInViewport(target: Locator): Promise<boolean> {
  return target.evaluate((element) => {
    const box = element.getBoundingClientRect()
    return box.bottom > 0 && box.top < window.innerHeight && box.right > 0 && box.left < window.innerWidth
  })
}

/** Submits the planner form as it is (the defaults are a valid job) and waits for the answer. */
export async function submitDefaultPlan(page: Page): Promise<number> {
  await page.goto('/plan')
  await expectHeading(page, /when should your gpu job run/i)
  const submit = page.getByRole('button', { name: 'Plan', exact: true })
  await expect(submit).toBeEnabled()
  const started = Date.now()
  await submit.click()
  await expect(page.getByRole('heading', { name: 'Your plan' })).toBeVisible({ timeout: 20_000 })
  return Date.now() - started
}

/** Reads the leaderboard rows (without the header row) as locators. */
export function boardRows(page: Page): Locator {
  return page.getByRole('table').getByRole('row').filter({ has: page.getByRole('cell') })
}

/** Opens D1 on the leaderboard and clicks the first site link; returns the site page path. */
export async function openFirstSiteFromBoard(page: Page): Promise<string> {
  await page.goto('/leaderboard?division=D1')
  await expectHeading(page, /^leaderboard$/i)
  const firstLink = boardRows(page).first().getByRole('link').first()
  await expect(firstLink).toBeVisible({ timeout: 20_000 })
  await firstLink.click()
  await page.waitForURL(/\/sites\/[^/]+$/)
  return new URL(page.url()).pathname
}
