import { Link } from 'react-router-dom'
import { usePageTitle } from '../hooks/usePageTitle'

/**
 * Shown when a page throws while it renders. It says nothing about the cause on purpose: error
 * text and stacks mean nothing to the person and can reveal how the app is built.
 */
export function RouteError() {
  usePageTitle('Something went wrong')
  return (
    <section>
      <h1>Something went wrong</h1>
      <p>This page ran into a problem. Your other pages still work.</p>
      <p>
        <Link to="/">Go to the planner</Link> or <Link to="/leaderboard">see the leaderboard</Link>.
      </p>
    </section>
  )
}
