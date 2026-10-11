import { expect, test } from './fixtures'
import { openFirstSiteFromBoard } from './helpers'

test.describe('site page', () => {
  test('opens from a leaderboard row with a score, its parts, and B "Not rated"', async ({ page, diag }) => {
    const path = await openFirstSiteFromBoard(page)
    expect(path).toMatch(/^\/sites\/s_[a-z2-7]+$/)

    const title = page.getByRole('heading', { level: 1 })
    await expect(title).toBeVisible()
    await expect(page.getByText('Simulated', { exact: true }).first()).toBeVisible()

    const score = page.getByRole('region', { name: 'Score' })
    await expect(score).toBeVisible()

    await test.step('score ring: the number is shown and the score is marked provisional', async () => {
      await expect(score.getByText(/Score\s+\d+/).last()).toBeVisible()
      await expect(score.getByText('Provisional', { exact: true }).first()).toBeVisible()
    })

    await test.step('breakdown: A behaviour, B not rated, C measurement', async () => {
      await expect(score.getByText('A. Behaviour')).toBeVisible()
      await expect(score.getByText(/\d+(\.\d)? of 50/)).toBeVisible()
      const facility = score.getByRole('listitem').filter({ hasText: 'B. Facility efficiency' }).first()
      await expect(facility).toContainText('Not rated')
      await expect(score.getByText('C. Measurement and openness')).toBeVisible()
      await expect(score.getByText(/\d+(\.\d)? of 20/)).toBeVisible()
    })

    await test.step('footprint and receipts sections are present', async () => {
      await expect(page.getByRole('heading', { name: 'Last 30 days' })).toBeVisible()
      await expect(page.getByRole('heading', { name: 'Recent receipts' })).toBeVisible()
    })

    expect(diag.consoleErrors).toEqual([])
  })

  test('an unknown site id gives a clear error, not a blank page', async ({ page }) => {
    await page.goto('/sites/s_zzzzzzzzzz')
    const failure = page
      .getByRole('alert')
      .or(page.getByRole('button', { name: 'Try again' }))
      .or(page.getByText(/not found|couldn't find|could not find|no such site/i))
    await expect(failure.first()).toBeVisible({ timeout: 20_000 })
    await expect(page.getByRole('navigation', { name: 'Main' }), 'header and navigation survive the failure').toBeVisible()
  })
})
