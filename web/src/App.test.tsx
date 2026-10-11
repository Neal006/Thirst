import { render, screen } from '@testing-library/react'
import { createMemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import App from './App'
import { clientWith, fetchSpy } from './test/api'
import { appRoutes } from './routes'

// Pages load on first visit; the planner chunk (charts) can take over a second cold in jsdom.
const PAGE_LOAD = { timeout: 5000 }

afterEach(() => {
  vi.unstubAllEnvs()
})

describe('App', () => {
  it('shows the layout and the home page at /', async () => {
    const router = createMemoryRouter(appRoutes, { initialEntries: ['/'] })
    render(<App client={clientWith(fetchSpy())} router={router} />)
    expect(screen.getByRole('navigation', { name: /main/i })).toBeInTheDocument()
    expect(await screen.findByRole('heading', { level: 1, name: /every gpu hour drinks water twice/i })).toBeInTheDocument()
  })

  it('shows the planner at /plan', async () => {
    const router = createMemoryRouter(appRoutes, { initialEntries: ['/plan'] })
    render(<App client={clientWith(fetchSpy())} router={router} />)
    expect(await screen.findByRole('heading', { level: 1, name: /when should your gpu job run/i }, PAGE_LOAD)).toBeInTheDocument()
    expect(await screen.findByLabelText(/gpu model/i)).toBeInTheDocument()
  })

  it('says in plain words when the API address is missing', () => {
    vi.stubEnv('VITE_API_URL', '')
    vi.stubEnv('VITE_USE_MOCKS', 'false')
    const router = createMemoryRouter(appRoutes, { initialEntries: ['/'] })
    render(<App router={router} />)
    expect(screen.getByRole('heading', { name: /can't start/i })).toBeInTheDocument()
    expect(screen.getByText(/VITE_API_URL/)).toBeInTheDocument()
  })

  it('runs on the mock fixtures with VITE_USE_MOCKS=true', async () => {
    vi.stubEnv('VITE_USE_MOCKS', 'true')
    const router = createMemoryRouter(appRoutes, { initialEntries: ['/leaderboard'] })
    render(<App router={router} />)
    expect(await screen.findByRole('link', { name: /demo lab, chennai/i })).toBeInTheDocument()
  })
})
