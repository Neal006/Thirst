import { checked } from '../api/errors'
import { isAssumptionsResponse } from '../api/guards'
import type { ApiClient } from '../api/client'
import type { AssumptionsResponse } from '../api/types'
import { useLoad } from './useLoad'

const load = async (api: ApiClient, signal: AbortSignal): Promise<AssumptionsResponse> =>
  checked(isAssumptionsResponse, await api.get<unknown>('/assumptions', undefined, signal))

/** GET /assumptions: factors, GPU list, cities and sources. */
export function useAssumptions() {
  return useLoad<AssumptionsResponse>(load, 'assumptions')
}
