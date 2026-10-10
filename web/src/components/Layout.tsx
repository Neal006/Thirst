import { useRef } from 'react'
import { Link, NavLink, Outlet } from 'react-router-dom'
import { useRouteFocus } from '../hooks/useRouteFocus'

const NAV_ITEMS = [
  { to: '/', label: 'Plan', end: true },
  { to: '/leaderboard', label: 'Leaderboard', end: false },
  { to: '/assumptions', label: 'Assumptions', end: false },
] as const

/** The frame around every page: skip link, header with navigation, main area and footer. */
export function Layout() {
  const mainRef = useRef<HTMLElement>(null)
  useRouteFocus(mainRef)
  return (
    <div className="app-shell">
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <header className="app-header">
        <Link to="/" className="brand">
          Thirst
        </Link>
        <nav aria-label="Main">
          <ul className="nav-list">
            {NAV_ITEMS.map((item) => (
              <li key={item.to}>
                <NavLink to={item.to} end={item.end} className="nav-link">
                  {item.label}
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>
      </header>
      <main id="main" ref={mainRef} tabIndex={-1} className="app-main">
        <Outlet />
      </main>
      <footer className="app-footer">
        <p>
          Every number is labelled measured or modelled.{' '}
          <Link to="/assumptions">How do we know?</Link>
        </p>
      </footer>
    </div>
  )
}
