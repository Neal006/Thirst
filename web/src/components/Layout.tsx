import { useRef } from 'react'
import { Link, NavLink, Outlet, useLocation } from 'react-router-dom'
import { useRouteFocus } from '../hooks/useRouteFocus'
import { BrandMark } from './BrandMark'

const NAV_ITEMS = [
  { to: '/plan', label: 'Plan', end: false },
  { to: '/cities', label: 'Cities', end: false },
  { to: '/leaderboard', label: 'Leaderboard', end: false },
  { to: '/assumptions', label: 'Assumptions', end: false },
] as const

/** The frame around every page: skip link, header with navigation, main area and footer. */
export function Layout() {
  const mainRef = useRef<HTMLElement>(null)
  useRouteFocus(mainRef)
  const { pathname } = useLocation()
  return (
    <div className="app-shell">
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <header className="app-header">
        <Link to="/" className="brand" aria-label="Thirst home">
          <BrandMark className="brand-mark" />
          <span>Thirst</span>
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
        <div key={pathname} className="page-enter">
          <Outlet />
        </div>
      </main>
      <footer className="app-footer">
        <p>
          Every number is labelled measured or modelled. <Link to="/assumptions">How do we know?</Link>
        </p>
        <p className="footer-note">
          Weather by Open-Meteo (CC BY 4.0) · <Link to="/assumptions#sources-heading">Data sources</Link>
        </p>
      </footer>
    </div>
  )
}
