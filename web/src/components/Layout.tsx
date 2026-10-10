import { useRef } from 'react'
import { Link, NavLink, Outlet } from 'react-router-dom'
import { useRouteFocus } from '../hooks/useRouteFocus'
import { BrandMark } from './BrandMark'

const NAV_ITEMS = [
  { to: '/plan', label: 'Plan', end: false },
  { to: '/leaderboard', label: 'Leaderboard', end: false },
  { to: '/assumptions', label: 'Assumptions', end: false },
] as const

const AWS_SERVICES = [
  'Amplify',
  'API Gateway',
  'Lambda',
  'DynamoDB',
  'EventBridge Scheduler',
  'Bedrock + Strands Agents',
  'SAM',
] as const

const DATA_CREDITS = ['Open-Meteo', 'CEA', 'CSEP', 'WRI Aqueduct', 'MoEFCC', 'CPHEEO'] as const

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
        <Outlet />
      </main>
      <footer className="app-footer">
        <div className="footer-grid">
          <p>
            Every number is labelled measured or modelled.{' '}
            <Link to="/assumptions">How do we know?</Link>
          </p>
          <div>
            <h2>Built on AWS</h2>
            <ul className="footer-list">
              {AWS_SERVICES.map((name) => (
                <li key={name}>{name}</li>
              ))}
            </ul>
          </div>
          <div>
            <h2>Data</h2>
            <ul className="footer-list">
              {DATA_CREDITS.map((name) => (
                <li key={name}>{name}</li>
              ))}
            </ul>
          </div>
        </div>
        <p className="footer-note">
          Weather data by Open-Meteo (CC BY 4.0) · WeMakeDevs × AWS Environmental Hacks · MIT
        </p>
      </footer>
    </div>
  )
}
