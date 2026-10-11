import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { findUntaggedNumbers } from '../test/honesty'
import { renderWithApi } from '../test/api'
import { CitiesPage } from './CitiesPage'

describe('CitiesPage', () => {
  it('shows a card per city with a best start and a link into the planner', async () => {
    const { container } = renderWithApi(<CitiesPage />)
    expect(screen.getByRole('heading', { level: 1, name: 'Compare cities' })).toBeInTheDocument()
    const links = await screen.findAllByRole('link', { name: /plan here/i })
    expect(links).toHaveLength(6)
    expect(links[0].getAttribute('href')).toMatch(/^\/plan\?city=\w+&cooling=room_ac$/)
    expect(screen.getAllByText('Best start').length).toBe(6)
    expect(findUntaggedNumbers(container)).toEqual([])
  })

  it('switches every card to a cooling tower', async () => {
    renderWithApi(<CitiesPage />)
    await screen.findAllByRole('link', { name: /plan here/i })
    await userEvent.click(within(screen.getByRole('group', { name: 'Cooling' })).getByRole('button', { name: 'Cooling tower' }))
    const links = await screen.findAllByRole('link', { name: /plan here/i })
    expect(links[0].getAttribute('href')).toContain('cooling=evaporative')
  })
})
