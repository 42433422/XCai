export interface AuthTokens {
  access_token?: string
  refresh_token?: string
}

export interface CurrentUser {
  id: number
  username: string
  email?: string
  is_admin?: boolean
}
