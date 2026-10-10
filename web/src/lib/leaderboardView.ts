import type { LeaderboardRow } from '../api/types'

/** Rated sites keep the server's order; sites with no score yet go last. */
export function ratedFirst(rows: readonly LeaderboardRow[]): LeaderboardRow[] {
  return [...rows.filter((r) => r.score !== null), ...rows.filter((r) => r.score === null)]
}
