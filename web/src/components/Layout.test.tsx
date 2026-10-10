import { render, screen, within } from '@testing-library/react'
import { createMemoryRouter, RouterProvider } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import { Layout } from './Layout'

function renderAt(path: string) {
  const router = createMemoryRouter(
    [
      {
        path: '/',
        element: <Layout />,
        children: [
          { index: true, element: <p>plan page body</p> },
          { path: 'leaderboard', element: <p>board page body</p> },
          { path: 'assumptions', element: <p>assumptions page body</p> },
        ],
      },
    ],
    { initialEntries: [path] },
  )
  return render(<RouterProvider router={router} />)
}

describe('Layout', () => {
  it('shows the three main links in the navigation', () => {
    renderAt('/')
    const nav = screen.getByRole('navigation', { name: /main/i })
    expect(within(nav).getByRole('link', { name: 'Plan' })).toHaveAttribute('href', '/')
    expect(within(nav).getByRole('link', { name: 'Leaderboard' })).toHaveAttribute(
      'href',
      '/leaderboard',
    )
    expect(within(nav).getByRole('link', { name: 'Assumptions' })).toHaveAttribute(
      'href',
      '/assumptions',
    )
  })

  it('marks only the current page in the navigation', () => {
    renderAt('/leaderboard')
    const nav = screen.getByRole('navigation', { name: /main/i })
    expect(within(nav).getByRole('link', { name: 'Leaderboard' })).toHaveAttribute(
      'aria-current',
      'page',
    )
    expect(within(nav).getByRole('link', { name: 'Plan' })).not.toHaveAttribute('aria-current')
  })

  it('renders the page inside the main landmark', () => {
    renderAt('/assumptions')
    expect(within(screen.getByRole('main')).getByText('assumptions page body')).toBeInTheDocument()
  })

  it('offers a skip link that points at the main landmark', () => {
    renderAt('/')
    const skip = screen.getByRole('link', { name: /skip to content/i })
    expect(skip).toHaveAttribute('href', '#main')
    expect(screen.getByRole('main')).toHaveAttribute('id', 'main')
  })

  it('has a footer that explains the labels and links to the assumptions', () => {
    renderAt('/')
    const footer = screen.getByRole('contentinfo')
    expect(footer).toHaveTextContent(/every number is labelled measured or modelled/i)
    expect(within(footer).getByRole('link', { name: /how do we know/i })).toHaveAttribute(
      'href',
      '/assumptions',
    )
  })
})
