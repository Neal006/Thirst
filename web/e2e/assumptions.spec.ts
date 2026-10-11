import { expect, test } from './fixtures'
import { expectHeading, isInViewport, submitDefaultPlan } from './helpers'

test.describe('assumptions page', () => {
  test('lists the factors with a version and how sure we are', async ({ page, diag }) => {
    await page.goto('/assumptions')
    await expectHeading(page, /^assumptions$/i)
    await expect(page.getByRole('heading', { name: 'How sure we are' })).toBeVisible({ timeout: 20_000 })
    await expect(page.getByText(/^Version\s/)).toBeVisible()
    expect(await page.getByRole('table').count(), 'factor, GPU and city tables').toBeGreaterThanOrEqual(2)
    expect(diag.consoleErrors).toEqual([])
  })

  test('a tag chip on the plan page scrolls to its explanation', async ({ page }) => {
    await submitDefaultPlan(page)
    const chip = page
      .getByRole('region', { name: 'Your plan' })
      .getByRole('link')
      .filter({ hasText: /^(measured|modelled|placeholder|sourced|calibrated|unverified|design choice)$/i })
      .first()
    await expect(chip).toBeVisible()
    const href = (await chip.getAttribute('href')) ?? ''
    const anchor = href.split('#')[1]
    expect(anchor, 'tag chips link to an anchor on the assumptions page').toBeTruthy()

    await chip.click()
    await expect(page).toHaveURL(new RegExp(`/assumptions#${anchor}$`))
    await expectHeading(page, /^assumptions$/i)
    const target = page.locator(`[id="${anchor}"]`)
    await expect(target, `an element with id ${anchor} exists`).toHaveCount(1, { timeout: 20_000 })
    await expect.poll(() => isInViewport(target), { message: 'the anchor target is scrolled into view', timeout: 5_000 }).toBe(true)
  })

  test('a link to a factor row scrolls to the row', async ({ page }) => {
    await page.goto('/assumptions')
    await expect(page.getByRole('heading', { name: 'How sure we are' })).toBeVisible({ timeout: 20_000 })
    const rowId = await page.locator('tr[id]').first().getAttribute('id')
    expect(rowId, 'factor rows have ids').toBeTruthy()

    await page.goto(`/assumptions#${rowId}`)
    await expectHeading(page, /^assumptions$/i)
    const row = page.locator(`tr[id="${rowId}"]`)
    await expect(row).toBeVisible({ timeout: 20_000 })
    await expect.poll(() => isInViewport(row), { message: 'the factor row is scrolled into view', timeout: 5_000 }).toBe(true)
  })

  test('the jump links scroll to their group', async ({ page }) => {
    await page.goto('/assumptions')
    const jump = page.getByRole('navigation', { name: 'Jump to a group' })
    await expect(jump).toBeVisible({ timeout: 20_000 })
    await jump.getByRole('link', { name: /^Sources/ }).click()
    await expect(page).toHaveURL(/#sources-heading$/)
    const heading = page.locator('#sources-heading')
    await expect(heading).toBeVisible()
    await expect.poll(() => isInViewport(heading), { timeout: 5_000 }).toBe(true)
  })
})
