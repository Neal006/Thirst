import { useCallback } from 'react'
import type { ApiClient } from '../api/client'
import { checked } from '../api/errors'
import { isPlanResponse } from '../api/guards'
import type { PlanResponse } from '../api/types'
import { sampleJob, type SampleCooling } from '../lib/landing'
import { useLoad } from './useLoad'

// One request per city and cooling per client, shared by every graphic that needs it. Not tied to
// one caller's abort signal: useLoad already drops answers that arrive after it moved on.
const pending = new WeakMap<ApiClient, Map<string, Promise<PlanResponse>>>()

function fetchOnce(api: ApiClient, city: string, cooling: SampleCooling): Promise<PlanResponse> {
  const key = `${city}|${cooling}`
  const byKey = pending.get(api) ?? new Map<string, Promise<PlanResponse>>()
  pending.set(api, byKey)
  const known = byKey.get(key)
  if (known) return known
  const body = { ...sampleJob(city, Date.now(), cooling), alpha: 0.5 }
  const request = api
    .post<unknown>('/plan', body)
    .then((data) => checked(isPlanResponse, data))
    .catch((error: unknown) => {
      byKey.delete(key) // a failure is not remembered, so "Try again" asks again
      throw error
    })
  byKey.set(key, request)
  return request
}

/** POST /plan with the home page's sample job: the 48-hour series plus Base and the chosen plan. */
export function useCityForecast(city: string, cooling: SampleCooling = 'room_ac') {
  const load = useCallback((api: ApiClient) => fetchOnce(api, city, cooling), [city, cooling])
  return useLoad<PlanResponse>(load, `forecast:${city}|${cooling}`)
}
