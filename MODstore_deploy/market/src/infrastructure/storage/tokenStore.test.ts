import { describe, expect, it } from 'vitest'
import {
  ACCESS_TOKEN_KEY,
  REFRESH_TOKEN_KEY,
  clearAuthTokens,
  getAccessToken,
  getRefreshToken,
  setAuthTokens,
} from './tokenStore'

describe('tokenStore', () => {
  it('stores and clears access and refresh tokens', () => {
    setAuthTokens({ access_token: 'access-1', refresh_token: 'refresh-1' })

    expect(getAccessToken()).toBe('access-1')
    expect(getRefreshToken()).toBe('refresh-1')
    expect(localStorage.getItem(ACCESS_TOKEN_KEY)).toBe('access-1')
    expect(localStorage.getItem(REFRESH_TOKEN_KEY)).toBe('refresh-1')

    clearAuthTokens()

    expect(getAccessToken()).toBe('')
    expect(getRefreshToken()).toBe('')
  })

  it('ignores missing token fields', () => {
    setAuthTokens(null)
    setAuthTokens({})

    expect(getAccessToken()).toBe('')
    expect(getRefreshToken()).toBe('')
  })
})
