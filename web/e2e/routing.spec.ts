import { expect, test } from './fixtures'
import { expectHeading, openFirstSiteFromBoard, PAGES } from './helpers'

const SPA_REWRITE_MISSING = 'SPA rewrite rule missing in Amplify console'

test.describe('routing', () => {
  test('an unknown path shows the 404 page inside the app shell', async ({ page }) => {
    const response = await page.goto('/no-such-page')
    // A single page app answers 200 for every path (Amplify rewrite); a real 404 here means the
    // rewrite is missing and the host is serving its own error page.
    expect(response?.status(), SPA_REWRITE_MISSING).toBeLessThan(400)
    await expect(page.getByRole('heading', { level: 1, name: "We couldn't find that page" }), SPA_REWRITE_MISSING).toBeVisible()
    await expect(page.getByRole('link', { name: 'Go to the planner' })).toBeVisible()
    await expect(page.getByRole('navigation', { name: 'Main' })).toBeVisible()
    await expect(page).toHaveTitle(/not found/i)
  })

  test('the 404 page links lead somewhere', async ({ page }) => {
    await page.goto('/no-such-page')
    await page.getByRole('link', { name: 'Go to the planner' }).click()
    await expectHeading(page, /when should your gpu job run/i)
  })

  for (const entry of PAGES) {
    test(`deep link ${entry.path} loads directly and survives a refresh`, async ({ page }) => {
      const response = await page.goto(entry.path)
      expect(response?.status(), SPA_REWRITE_MISSING).toBeLessThan(400)
      await expect(page.getByRole('heading', { level: 1, name: entry.heading }), SPA_REWRITE_MISSING).toBeVisible()
      await page.reload()
      await expect(page.getByRole('heading', { level: 1, name: entry.heading }), SPA_REWRITE_MISSING).toBeVisible()
    })
  }

  test('a site page deep link survives a refresh', async ({ page }) => {
    const path = await openFirstSiteFromBoard(page)
    const response = await page.goto(path)
    expect(response?.status(), SPA_REWRITE_MISSING).toBeLessThan(400)
    await expect(page.getByRole('region', { name: 'Score' }), SPA_REWRITE_MISSING).toBeVisible({ timeout: 20_000 })
    await page.reload()
    await expect(page.getByRole('region', { name: 'Score' }), SPA_REWRITE_MISSING).toBeVisible({ timeout: 20_000 })
  })

  test('the browser back button returns to the previous page', async ({ page }) => {
    await page.goto('/leaderboard')
    await expectHeading(page, /^leaderboard$/i)
    await page.getByRole('navigation', { name: 'Main' }).getByRole('link', { name: 'Assumptions' }).click()
    await expectHeading(page, /^assumptions$/i)
    await page.goBack()
    await expectHeading(page, /^leaderboard$/i)
  })

  test('each page sets a distinct document title', async ({ page }) => {
    const titles = new Set<string>()
    for (const entry of PAGES) {
      await page.goto(entry.path)
      await expect(page.getByRole('heading', { level: 1, name: entry.heading })).toBeVisible()
      titles.add(await page.title())
    }
    expect(titles.size, `titles: ${[...titles].join(' | ')}`).toBe(PAGES.length)
  })
})
