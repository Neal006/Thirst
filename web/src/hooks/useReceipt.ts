import { useCallback } from 'react'
import type { ApiClient } from '../api/client'
import { checked } from '../api/errors'
import { isReceiptResponse } from '../api/guards'
import type { ReceiptDetail } from '../api/types'
import { useLoad } from './useLoad'

/** GET /receipts/{site_id}/{job_id}: the full Base / Best / Actual breakdown (D24). */
export function useReceipt(siteId: string, jobId: string) {
  const load = useCallback(
    async (api: ApiClient, signal: AbortSignal): Promise<ReceiptDetail> =>
      checked(
        isReceiptResponse,
        await api.get<unknown>(
          `/receipts/${encodeURIComponent(siteId)}/${encodeURIComponent(jobId)}`,
          undefined,
          signal,
        ),
      ),
    [siteId, jobId],
  )
  return useLoad<ReceiptDetail>(load, `receipt:${siteId}:${jobId}`)
}
