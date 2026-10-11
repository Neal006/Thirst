import { expect, test } from './fixtures'
import { expectHeading } from './helpers'

const CITY_COUNT = 6

test.describe('cities page', () => {
  test('compares the same job in every city, with a way into the planner', async ({ page, diag }) => {
    await page.goto('/cities')
    await expectHeading(page, /^compare cities$/i)
    const planHere = page.getByRole('link', { name: /plan here/i })
    await expect(planHere).toHaveCount(CITY_COUNT, { timeout: 30_000 })

    await test.step('each card has a best start and labelled numbers', async () => {
      await expect(page.getByText('Best start', { exact: true })).toHaveCount(CITY_COUNT)
      const chips = page.locator('.city-card .tag')
      expect(await chips.count(), 'every number on a card wears a label').toBeGreaterThanOrEqual(CITY_COUNT * 2)
    })

    await test.step('cooling tower switches every card', async () => {
      await page.getByRole('group', { name: 'Cooling' }).getByRole('button', { name: 'Cooling tower' }).click()
      await expect(planHere.first()).toHaveAttribute('href', /cooling=evaporative/, { timeout: 30_000 })
    })

    await test.step('"Plan here" opens the planner for that city', async () => {
      const href = (await planHere.first().getAttribute('href')) ?? ''
      const city = new URLSearchParams(href.split('?')[1]).get('city') ?? ''
      await planHere.first().click()
      await expectHeading(page, /when should your gpu job run/i)
      await expect(page.getByLabel('City')).toHaveValue(city)
    })

    // One sample /plan per city and cooling, shared with the home page.
    expect(diag.planRequests.length).toBeLessThanOrEqual(CITY_COUNT * 2)
  })
})
