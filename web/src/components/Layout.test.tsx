import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createMemoryRouter, Link, RouterProvider } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
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
  it('shows the four main links in the navigation', () => {
    renderAt('/')
    const nav = screen.getByRole('navigation', { name: /main/i })
    expect(within(nav).getByRole('link', { name: 'Plan' })).toHaveAttribute('href', '/plan')
    expect(within(nav).getByRole('link', { name: 'Leaderboard' })).toHaveAttribute(
      'href',
      '/leaderboard',
    )
    expect(within(nav).getByRole('link', { name: 'Cities' })).toHaveAttribute('href', '/cities')
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

  it('links the brand to the home page', () => {
    renderAt('/leaderboard')
    expect(screen.getByRole('link', { name: /thirst home/i })).toHaveAttribute('href', '/')
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

describe('Layout on a route change', () => {
  // jsdom has no scrollIntoView; the stub is removed again so other tests see the real thing.
  const original = Element.prototype.scrollIntoView
  const scroll = vi.fn()

  beforeEach(() => {
    scroll.mockClear()
    Element.prototype.scrollIntoView = scroll
  })

  afterEach(() => {
    if (original === undefined) delete (Element.prototype as { scrollIntoView?: unknown }).scrollIntoView
    else Element.prototype.scrollIntoView = original
  })

  function renderRouter(path: string) {
    const router = createMemoryRouter(
      [
        {
          path: '/',
          element: <Layout />,
          children: [
            {
              index: true,
              element: (
                <div>
                  <h1>Plan heading</h1>
                  <Link to="/assumptions#status-modelled">modelled chip</Link>
                  <Link to="/assumptions#nothing-here">broken chip</Link>
                  <Link to="/leaderboard">to board</Link>
                  <Link to="/?division=D2">same page, other query</Link>
                </div>
              ),
            },
            { path: 'leaderboard', element: <h1>Board heading</h1> },
            {
              path: 'assumptions',
              element: (
                <div>
                  <h1>Assumptions heading</h1>
                  <ul>
                    <li id="status-modelled">what modelled means</li>
                  </ul>
                  <Link to="/">back to plan</Link>
                </div>
              ),
            },
          ],
        },
      ],
      { initialEntries: [path] },
    )
    return render(<RouterProvider router={router} />)
  }

  it('moves focus to the new page heading when a link is followed', async () => {
    renderRouter('/')
    await userEvent.click(screen.getByRole('link', { name: 'to board' }))
    expect(screen.getByRole('heading', { name: 'Board heading' })).toHaveFocus()
  })

  it('moves focus to the main area when the new page has no heading', async () => {
    const router = createMemoryRouter(
      [
        {
          path: '/',
          element: <Layout />,
          children: [
            { index: true, element: <Link to="/blank">go blank</Link> },
            { path: 'blank', element: <p>no heading here</p> },
          ],
        },
      ],
      { initialEntries: ['/'] },
    )
    render(<RouterProvider router={router} />)
    await userEvent.click(screen.getByRole('link', { name: 'go blank' }))
    expect(screen.getByRole('main')).toHaveFocus()
  })

  it('leaves focus alone when only the query string changes (the division tabs)', async () => {
    renderRouter('/')
    const link = screen.getByRole('link', { name: 'same page, other query' })
    await userEvent.click(link)
    expect(link).toHaveFocus()
  })

  it('does not take focus on the first page load', () => {
    renderRouter('/')
    expect(document.body).toHaveFocus()
  })

  it('scrolls to the element named in the address and focuses it', async () => {
    renderRouter('/')
    await userEvent.click(screen.getByRole('link', { name: 'modelled chip' }))
    const target = screen.getByText('what modelled means')
    expect(scroll).toHaveBeenCalledTimes(1)
    expect(scroll.mock.contexts[0]).toBe(target)
    expect(target).toHaveFocus()
  })

  it('scrolls to the element when the page is opened with the address', () => {
    renderRouter('/assumptions#status-modelled')
    expect(scroll.mock.contexts[0]).toBe(screen.getByText('what modelled means'))
  })

  it('falls back to the heading when the address names nothing on the page', async () => {
    renderRouter('/')
    await userEvent.click(screen.getByRole('link', { name: 'broken chip' }))
    expect(scroll).not.toHaveBeenCalled()
    expect(screen.getByRole('heading', { name: 'Assumptions heading' })).toHaveFocus()
  })

  it('does not break when scrolling is not available', async () => {
    Element.prototype.scrollIntoView = undefined as unknown as typeof Element.prototype.scrollIntoView
    renderRouter('/')
    await userEvent.click(screen.getByRole('link', { name: 'modelled chip' }))
    expect(screen.getByText('what modelled means')).toHaveFocus()
  })
})
