import { expect, test } from './fixtures'
import {
  expectHeading,
  hasTradeoffSlider,
  horizontalOverflow,
  IDENTICAL_PARETO,
  openFirstSiteFromBoard,
  PAGES,
  submitDefaultPlan,
} from './helpers'

const PHONE_WIDTH = 360

test.describe('phone viewport (360 x 740)', () => {
  test.beforeEach(async ({ page }) => {
    const size = page.viewportSize()
    expect(size?.width, 'this spec must run at the phone width').toBe(PHONE_WIDTH)
  })

  for (const entry of PAGES) {
    test(`${entry.path} has no horizontal scroll`, async ({ page }) => {
      await page.goto(entry.path)
      await expect(page.getByRole('heading', { level: 1, name: entry.heading })).toBeVisible()
      await page.waitForLoadState('networkidle')
      expect(await horizontalOverflow(page), 'scrollWidth must not exceed the viewport').toBe(0)
    })
  }

  test('the four header links each fit on one line', async ({ page }) => {
    await page.goto('/')
    const nav = page.getByRole('navigation', { name: 'Main' })
    for (const name of ['Plan', 'Cities', 'Leaderboard', 'Assumptions']) {
      const box = await nav.getByRole('link', { name }).boundingBox()
      expect(box, `${name} link is on screen`).not.toBeNull()
      // One line of nav text is about 36 px tall with its padding; a word broken over two lines is ~60.
      expect(box?.height ?? 0, `${name} must not wrap onto a second line`).toBeLessThan(48)
    }
  })

  test('/plan after a result has no horizontal scroll', async ({ page }) => {
    await submitDefaultPlan(page)
    await page.waitForLoadState('networkidle')
    expect(await horizontalOverflow(page)).toBe(0)
  })

  test('/plan slider still works on the phone', async ({ page, diag }) => {
    await submitDefaultPlan(page)
    test.skip(!(await hasTradeoffSlider(page)), IDENTICAL_PARETO)
    const slider = page.getByRole('slider')
    await slider.scrollIntoViewIfNeeded()
    await slider.fill('1')
    await expect(page.getByText('Water only')).toBeVisible()
    expect(diag.planRequests.length).toBe(1)
  })

  test('/leaderboard rows (cards on phone) have no horizontal scroll in any division', async ({ page }) => {
    for (const division of ['D1', 'D2', 'D3', 'D4']) {
      await page.goto(`/leaderboard?division=${division}`)
      await expectHeading(page, /^leaderboard$/i)
      await expect(page.getByText(new RegExp(`Last 30 days · ${division}`))).toBeVisible()
      await page.waitForLoadState('networkidle')
      expect(await horizontalOverflow(page), `division ${division}`).toBe(0)
    }
  })

  test('a site page and a receipt page have no horizontal scroll', async ({ page }) => {
    await openFirstSiteFromBoard(page)
    await expect(page.getByRole('region', { name: 'Score' })).toBeVisible({ timeout: 20_000 })
    await page.waitForLoadState('networkidle')
    expect(await horizontalOverflow(page), 'site page').toBe(0)

    const view = page.getByRole('region', { name: 'Recent receipts' }).getByRole('link', { name: 'View' }).first()
    test.skip((await view.count()) === 0, 'the demo site has no receipts')
    await view.click()
    await expect(page.getByRole('heading', { name: 'How this was scored' })).toBeVisible({ timeout: 20_000 })
    await page.waitForLoadState('networkidle')
    expect(await horizontalOverflow(page), 'receipt page').toBe(0)
  })

  test('the 404 page has no horizontal scroll', async ({ page }) => {
    await page.goto('/no-such-page')
    await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
    expect(await horizontalOverflow(page)).toBe(0)
  })
})
