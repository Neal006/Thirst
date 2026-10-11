import { expect, test } from './fixtures'
import { boardRows, expectHeading } from './helpers'

/** The tab's accessible name is its label: the D1 to D4 id is aria-hidden. */
const DIVISIONS = [
  { id: 'D1', name: /^Small labs/ },
  { id: 'D2', name: /^Clusters/ },
  { id: 'D3', name: /^Facilities/ },
  { id: 'D4', name: /^Hyperscale/ },
] as const

test.describe('leaderboard', () => {
  test('D1 lists sites, marks simulated ones and shows no GPU counts', async ({ page, diag }) => {
    await page.goto('/leaderboard')
    await expectHeading(page, /^leaderboard$/i)
    const rows = boardRows(page)
    await expect(rows.first()).toBeVisible({ timeout: 20_000 })
    expect(await rows.count(), 'the demo data has several D1 sites').toBeGreaterThanOrEqual(2)

    await test.step('simulated sites wear a Simulated chip', async () => {
      for (const row of await rows.all()) {
        const name = (await row.getByRole('link').first().innerText()).trim()
        if (/simulated/i.test(name)) {
          await expect(row.getByText('Simulated', { exact: true })).toBeVisible()
        }
      }
      await expect(page.getByRole('table').getByText('Simulated', { exact: true }).first()).toBeVisible()
    })

    await test.step('no GPU counts are shown (privacy: US6)', async () => {
      const table = page.getByRole('table')
      await expect(table.getByRole('columnheader', { name: /gpu/i })).toHaveCount(0)
      const text = await table.innerText()
      expect(text, 'a number followed by GPUs would reveal the size of a site').not.toMatch(/\b\d[\d,]*\s*GPUs?\b/i)
    })

    expect(diag.consoleErrors).toEqual([])
  })

  test('division tabs change the URL, the pressed state and the rows', async ({ page }) => {
    await page.goto('/leaderboard')
    await expectHeading(page, /^leaderboard$/i)
    const group = page.getByRole('group', { name: 'Division' })
    await expect(group.getByRole('button', { pressed: true })).toHaveText(/Small labs/)
    await expect(boardRows(page).first()).toBeVisible({ timeout: 20_000 })

    const seen = new Map<string, string>()
    for (const { id: division, name } of DIVISIONS) {
      await group.getByRole('button', { name }).click()
      await expect(page).toHaveURL(new RegExp(`division=${division}`))
      await expect(group.getByRole('button', { name })).toHaveAttribute('aria-pressed', 'true')
      await expect(page.getByText(new RegExp(`Last 30 days · ${division}`))).toBeVisible()
      // Either rows or the empty state, never the loading spinner for good.
      const rows = boardRows(page)
      const empty = page.getByText('No sites in this division yet')
      await expect(rows.first().or(empty)).toBeVisible({ timeout: 20_000 })
      const firstName = (await rows.count()) > 0 ? await rows.first().innerText() : 'EMPTY'
      seen.set(division, firstName)
    }
    expect(new Set(seen.values()).size, 'different divisions should show different rows').toBeGreaterThan(1)
  })

  test('an unknown division in the URL falls back to D1', async ({ page }) => {
    await page.goto('/leaderboard?division=ZZ')
    await expectHeading(page, /^leaderboard$/i)
    await expect(page.getByRole('group', { name: 'Division' }).getByRole('button', { pressed: true })).toHaveText(/Small labs/)
  })
})
