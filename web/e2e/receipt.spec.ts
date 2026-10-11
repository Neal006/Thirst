import { expect, test } from './fixtures'
import { openFirstSiteFromBoard } from './helpers'

test.describe('receipt page', () => {
  test('opens from a site\'s recent receipts and shows base, best and actual', async ({ page, diag }) => {
    await openFirstSiteFromBoard(page)
    const receipts = page.getByRole('region', { name: 'Recent receipts' })
    await expect(receipts).toBeVisible()

    const viewLinks = receipts.getByRole('link', { name: 'View' })
    test.skip((await viewLinks.count()) === 0, 'the first D1 demo site has no receipts, so there is no receipt page to open')

    await viewLinks.first().click()
    await page.waitForURL(/\/receipts\/[^/]+\/[^/]+$/)
    await expect(page.getByRole('heading', { level: 1, name: 'Your receipt' })).toBeVisible()

    await test.step('the three ways to run the job are side by side', async () => {
      await expect(page.getByText('If you had started right away')).toBeVisible()
      await expect(page.getByText('Best plan', { exact: true })).toBeVisible()
      await expect(page.getByText('What you did', { exact: true })).toBeVisible()
    })

    await test.step('the scoring explanation is there and links back to the site', async () => {
      await expect(page.getByRole('heading', { name: 'How this was scored' })).toBeVisible()
      await expect(page.getByRole('link', { name: 'See your site' })).toBeVisible()
    })

    expect(diag.consoleErrors).toEqual([])
  })

  test('an unknown receipt id gives a clear error', async ({ page }) => {
    await page.goto('/receipts/s_zzzzzzzzzz/j_zzzzzzzzzzzz')
    await expect(page.getByRole('heading', { level: 1, name: 'Your receipt' })).toBeVisible()
    const failure = page.getByRole('alert').or(page.getByRole('button', { name: 'Try again' }))
    await expect(failure.first()).toBeVisible({ timeout: 20_000 })
  })
})
