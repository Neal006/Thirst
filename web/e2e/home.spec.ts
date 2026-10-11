import { expect, test } from './fixtures'
import { expectHeading } from './helpers'

test.describe('home page', () => {
  test('loads with its live graphics and no console errors', async ({ page, diag }) => {
    await page.goto('/')
    await expectHeading(page, /every gpu hour drinks water/i)

    await test.step('header navigation is present', async () => {
      const nav = page.getByRole('navigation', { name: 'Main' })
      for (const name of ['Plan', 'Cities', 'Leaderboard', 'Assumptions']) {
        await expect(nav.getByRole('link', { name })).toBeVisible()
      }
    })

    await test.step('the live forecast fills the hero meters', async () => {
      // Best start shows a clock time once the sample /plan call has answered; "--:--" means no data.
      const bestStart = page.getByText('Best start', { exact: true }).locator('xpath=following-sibling::dd[1]')
      await expect(bestStart).toHaveText(/\d{1,2}:\d{2}/, { timeout: 20_000 })
      await expect(bestStart).not.toContainText('--:--')
    })

    await test.step('there is at least one drawn graphic (svg) on the page', async () => {
      const graphics = page.locator('main svg')
      await expect.poll(() => graphics.count(), { timeout: 10_000 }).toBeGreaterThan(0)
      await expect(graphics.first()).toBeVisible()
    })

    await test.step('the page asked for live data and was served it', async () => {
      // The home page shares one /plan request per city; the sample job is a POST /plan.
      expect(diag.planRequests.length, 'home page should call POST /plan for the live forecast').toBeGreaterThan(0)
    })

    await page.waitForLoadState('networkidle')
    expect(diag.consoleErrors, 'no console errors or uncaught exceptions').toEqual([])
    expect(diag.failedRequests, 'no failed network requests').toEqual([])
    expect(diag.badResponses, 'no 4xx or 5xx responses').toEqual([])
  })

  test('the primary links lead to the planner and the board', async ({ page }) => {
    await page.goto('/')
    await expectHeading(page, /every gpu hour drinks water/i)
    await page.getByRole('navigation', { name: 'Main' }).getByRole('link', { name: 'Leaderboard' }).click()
    await expect(page).toHaveURL(/\/leaderboard/)
    await page.getByRole('navigation', { name: 'Main' }).getByRole('link', { name: 'Plan' }).click()
    await expect(page).toHaveURL(/\/plan/)
    await expectHeading(page, /when should your gpu job run/i)
  })
})
