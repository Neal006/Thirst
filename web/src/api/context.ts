import { createContext, useContext } from 'react'
import type { ApiClient } from './client'

export const ApiContext = createContext<ApiClient | null>(null)

/** The API client for this app. Tests provide a client that talks to a fetch stub. */
export function useApi(): ApiClient {
  const client = useContext(ApiContext)
  if (!client) throw new Error('useApi must be used inside an ApiContext provider.')
  return client
}
