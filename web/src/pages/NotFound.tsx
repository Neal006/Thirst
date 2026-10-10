import { Link } from 'react-router-dom'
import { usePageTitle } from '../hooks/usePageTitle'

export function NotFound() {
  usePageTitle('Page not found')
  return (
    <section>
      <h1>We couldn't find that page</h1>
      <p>The link may be old or mistyped.</p>
      <p>
        <Link to="/">Go to the planner</Link> or <Link to="/leaderboard">see the leaderboard</Link>.
      </p>
    </section>
  )
}
