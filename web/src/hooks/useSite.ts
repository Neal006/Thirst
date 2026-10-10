import { useCallback } from 'react'
import type { ApiClient } from '../api/client'
import { checked } from '../api/errors'
import { isSiteResponse } from '../api/guards'
import type { SiteResponse } from '../api/types'
import { useLoad } from './useLoad'

/** GET /sites/{id}: score, parts, monthly footprint and recent receipts. */
export function useSite(siteId: string) {
  const load = useCallback(
    async (api: ApiClient, signal: AbortSignal): Promise<SiteResponse> =>
      checked(
        isSiteResponse,
        await api.get<unknown>(`/sites/${encodeURIComponent(siteId)}`, undefined, signal),
      ),
    [siteId],
  )
  return useLoad<SiteResponse>(load, `site:${siteId}`)
}
