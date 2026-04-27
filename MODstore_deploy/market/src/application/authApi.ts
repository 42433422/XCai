import { requestJson } from '../infrastructure/http/client'
import { setAuthTokens } from '../infrastructure/storage/tokenStore'
import type { AuthTokens, CurrentUser } from '../domain/auth/types'

export async function login(username: string, password: string): Promise<AuthTokens> {
  const res = await requestJson<AuthTokens>('/api/auth/login', {
    method: 'POST',
    body: JSON.stringify({ username, password }),
  })
  setAuthTokens(res)
  return res
}

export function me(): Promise<CurrentUser> {
  return requestJson<CurrentUser>('/api/auth/me')
}
