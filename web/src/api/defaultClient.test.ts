import { describe, expect, it } from 'vitest'
import { ApiError } from './client'
import { checked, errorMessage } from './errors'
import { createDefaultClient } from './defaultClient'
import { isLeaderboardResponse } from './guards'

describe('createDefaultClient', () => {
  it('serves the fixtures when VITE_USE_MOCKS is "true"', async () => {
    const client = createDefaultClient({ VITE_USE_MOCKS: 'true' })
    const board = await client.get<unknown>('/leaderboard', { division: 'D1' })
    expect(isLeaderboardResponse(board)).toBe(true)
  })

  it('mock mode needs no API address', () => {
    expect(() => createDefaultClient({ VITE_USE_MOCKS: 'true', VITE_API_URL: '' })).not.toThrow()
  })

  it('fails with a plain-words message when no address is set', () => {
    expect(() => createDefaultClient({ VITE_USE_MOCKS: 'false' })).toThrow(/VITE_API_URL/)
  })

  it('ignores values that are not strings', () => {
    expect(() => createDefaultClient({ VITE_USE_MOCKS: true, VITE_API_URL: 5 })).toThrow(
      /VITE_API_URL/,
    )
  })

  it('builds a real client when an address is given', () => {
    expect(() => createDefaultClient({ VITE_API_URL: 'https://api.example.test' })).not.toThrow()
  })
})

describe('errorMessage', () => {
  it('uses the message of an API error', () => {
    expect(errorMessage(new ApiError(422, 'deadline_too_soon', 'Pick a later deadline.'))).toBe(
      'Pick a later deadline.',
    )
  })

  it('never shows the text of other errors', () => {
    const text = errorMessage(new TypeError('Cannot read properties of undefined'))
    expect(text).not.toMatch(/undefined|TypeError/)
    expect(text.length).toBeGreaterThan(10)
  })

  it('handles values that are not errors', () => {
    expect(errorMessage('boom')).toMatch(/something went wrong/i)
    expect(errorMessage(null)).toMatch(/something went wrong/i)
  })
})

describe('checked', () => {
  const isString = (v: unknown): v is string => typeof v === 'string'

  it('returns the value when the guard accepts it', () => {
    expect(checked(isString, 'ok')).toBe('ok')
  })

  it('throws an API error in plain words when the shape is wrong', () => {
    expect(() => checked(isString, 5)).toThrow(ApiError)
    try {
      checked(isString, 5)
    } catch (error) {
      expect((error as ApiError).code).toBe('unexpected_reply')
      expect((error as ApiError).message).not.toMatch(/undefined|NaN/)
    }
  })
})
