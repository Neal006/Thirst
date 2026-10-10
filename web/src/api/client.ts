// Small fetch wrapper for the Thirst API (plan 6.1). One place for the timeout, the JSON
// handling and the plain-words error messages, so no page has to know about HTTP.

import type { ApiErrorBody } from './types'

export const DEFAULT_TIMEOUT_MS = 10_000
const MAX_SERVER_MESSAGE = 300

const TRY_AGAIN = 'Something went wrong on our side. Please try again in a minute.'
const TOO_SLOW = 'That took too long. Please try again.'
const OFFLINE = 'We could not reach the server. Check your connection and try again.'

export type ErrorCode = string

export class ApiError extends Error {
  readonly status: number
  readonly code: ErrorCode

  constructor(status: number, code: ErrorCode, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
  }
}

export interface ClientOptions {
  baseUrl: string
  fetchImpl?: typeof fetch
  timeoutMs?: number
}

export interface ApiClient {
  get<T>(path: string, query?: Record<string, string>, signal?: AbortSignal): Promise<T>
  post<T>(path: string, body: unknown, signal?: AbortSignal): Promise<T>
}

function isErrorBody(value: unknown): value is ApiErrorBody {
  return (
    typeof value === 'object' &&
    value !== null &&
    typeof (value as ApiErrorBody).error === 'string' &&
    typeof (value as ApiErrorBody).message === 'string'
  )
}

async function readJson(reply: Response): Promise<unknown> {
  try {
    return await reply.json()
  } catch {
    return undefined
  }
}

function joinUrl(base: string, path: string, query?: Record<string, string>): string {
  const url = `${base.replace(/\/+$/, '')}${path.startsWith('/') ? path : `/${path}`}`
  if (!query || Object.keys(query).length === 0) return url
  return `${url}?${new URLSearchParams(query).toString()}`
}

export function createClient(options: ClientOptions): ApiClient {
  if (!options.baseUrl) {
    throw new Error('The API address is missing. Set VITE_API_URL (or VITE_USE_MOCKS=true).')
  }
  const timeoutMs = options.timeoutMs ?? DEFAULT_TIMEOUT_MS

  async function request<T>(
    method: 'GET' | 'POST',
    path: string,
    query: Record<string, string> | undefined,
    body: unknown,
    external?: AbortSignal,
  ): Promise<T> {
    const doFetch = options.fetchImpl ?? fetch
    const controller = new AbortController()
    let timedOut = false
    const timer = setTimeout(() => {
      timedOut = true
      controller.abort()
    }, timeoutMs)
    const onExternalAbort = () => controller.abort()
    external?.addEventListener('abort', onExternalAbort)
    try {
      const init: RequestInit = { method, signal: controller.signal }
      if (method === 'POST') {
        init.headers = { 'Content-Type': 'application/json' }
        init.body = JSON.stringify(body)
      }
      let reply: Response
      try {
        reply = await doFetch(joinUrl(options.baseUrl, path, query), init)
      } catch (error) {
        if (timedOut) throw new ApiError(0, 'timeout', TOO_SLOW)
        if (error instanceof DOMException && error.name === 'AbortError') {
          throw new ApiError(0, 'aborted', 'The request was cancelled.')
        }
        throw new ApiError(0, 'network', OFFLINE)
      }
      const data = await readJson(reply)
      if (!reply.ok) {
        if (isErrorBody(data)) {
          throw new ApiError(reply.status, data.error, data.message.slice(0, MAX_SERVER_MESSAGE))
        }
        throw new ApiError(reply.status, 'unexpected_reply', TRY_AGAIN)
      }
      if (data === undefined) throw new ApiError(reply.status, 'unexpected_reply', TRY_AGAIN)
      return data as T
    } finally {
      clearTimeout(timer)
      external?.removeEventListener('abort', onExternalAbort)
    }
  }

  return {
    get: (path, query, signal) => request('GET', path, query, undefined, signal),
    post: (path, body, signal) => request('POST', path, undefined, body, signal),
  }
}
