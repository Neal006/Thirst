import { useCallback } from 'react'
import type { ApiClient } from '../api/client'
import { checked } from '../api/errors'
import { isLeaderboardResponse } from '../api/guards'
import type { LeaderboardResponse } from '../api/types'
import { useLoad } from './useLoad'

/** GET /leaderboard for one division (the 30-day score board). */
export function useLeaderboard(division: string) {
  const load = useCallback(
    async (api: ApiClient, signal: AbortSignal): Promise<LeaderboardResponse> =>
      checked(
        isLeaderboardResponse,
        await api.get<unknown>('/leaderboard', { division, period: '30d', board: 'score' }, signal),
      ),
    [division],
  )
  return useLoad<LeaderboardResponse>(load, `leaderboard:${division}`)
}
