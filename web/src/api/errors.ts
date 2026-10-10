// Turns anything thrown during a request into text a student can read (never a stack trace).

import { ApiError } from './client'

const GENERIC = 'Something went wrong. Please try again.'
const UNEXPECTED_SHAPE = 'The server sent an answer we could not read. Please try again in a minute.'

export function errorMessage(error: unknown): string {
  return error instanceof ApiError && error.message ? error.message : GENERIC
}

/** Returns `data` when `guard` accepts it; otherwise throws an ApiError in plain words. */
export function checked<T>(guard: (value: unknown) => value is T, data: unknown): T {
  if (!guard(data)) throw new ApiError(0, 'unexpected_reply', UNEXPECTED_SHAPE)
  return data
}

export function isAborted(error: unknown): boolean {
  return error instanceof ApiError && error.code === 'aborted'
}
