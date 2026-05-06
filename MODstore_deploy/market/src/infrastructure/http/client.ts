import { clearAuthTokens, getAccessToken, getRefreshToken, setAuthTokens } from '../storage/tokenStore'

const BASE = ''

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly detail?: unknown,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

async function parseResponse(res: Response): Promise<unknown> {
  const text = await res.text()
  if (!text) return null
  try {
    return JSON.parse(text)
  } catch {
    return { detail: text || res.statusText }
  }
}

function looksLikeHtmlErrorBody(s: string): boolean {
  const t = s.trim()
  return t.startsWith('<!') || /^<html/i.test(t)
}

function errorMessage(data: any, fallback: string): string {
  const m = data?.message
  if (typeof m === 'string' && m.trim()) return m.trim()
  const d = data?.detail
  if (Array.isArray(d)) return d.map((x) => x.msg || JSON.stringify(x)).join('; ')
  if (typeof d === 'string') {
    if (looksLikeHtmlErrorBody(d)) {
      if (/504|Gateway Time-out/i.test(d)) {
        return 'HTTP 504 Gateway Time-out（网关读超时：长请求请在 nginx 增大 proxy_read_timeout，见 MODstore_deploy/docs/nginx-https-example.conf）'
      }
      if (/502|Bad Gateway/i.test(d)) {
        return 'HTTP 502 Bad Gateway（上游不可用或连接被重置）'
      }
      return fallback || '网关返回了 HTML 错误页而非 JSON'
    }
    return d
  }
  if (d && typeof d === 'object') return JSON.stringify(d)
  return fallback
}

async function refreshAccessToken(): Promise<string | null> {
  const refreshToken = getRefreshToken()
  if (!refreshToken) return null
  const res = await fetch(`${BASE}/api/auth/refresh`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh_token: refreshToken }),
  })
  const data: any = await parseResponse(res)
  if (!res.ok) {
    clearAuthTokens()
    return null
  }
  setAuthTokens(data)
  return data?.access_token || null
}

let refreshInFlight: Promise<string | null> | null = null

function readCsrfTokenFromCookie(): string | null {
  if (typeof document === 'undefined') return null
  for (const part of document.cookie.split(';')) {
    const s = part.trim()
    if (s.startsWith('csrf_token=')) {
      try {
        return decodeURIComponent(s.slice('csrf_token='.length))
      } catch {
        return s.slice('csrf_token='.length)
      }
    }
  }
  return null
}

/** 与后端 CSRFMiddleware 对齐：无 Bearer 的变更请求需带与 Cookie 一致的 X-CSRF-Token。 */
function attachCsrfHeader(headers: Headers, method: string): void {
  const m = method.toUpperCase()
  if (m === 'GET' || m === 'HEAD' || m === 'OPTIONS') return
  if (headers.has('Authorization')) return
  if (headers.has('X-CSRF-Token')) return
  const tok = readCsrfTokenFromCookie()
  if (tok) headers.set('X-CSRF-Token', tok)
}

function refreshAccessTokenOnce(): Promise<string | null> {
  if (!refreshInFlight) {
    refreshInFlight = refreshAccessToken().finally(() => {
      refreshInFlight = null
    })
  }
  return refreshInFlight
}

function shouldSkipRefresh(path: string): boolean {
  return (
    path.includes('/api/auth/login') ||
    path.includes('/api/auth/register') ||
    path.includes('/api/auth/login-with-code') ||
    path.includes('/api/auth/refresh') ||
    path.includes('/api/auth/send-')
  )
}

export async function requestJson<T>(path: string, opts: RequestInit = {}, authAttempt = 0): Promise<T> {
  const method = (opts.method || 'GET').toUpperCase()
  const headers = new Headers(opts.headers || {})
  const token = getAccessToken()
  if (token && !headers.has('Authorization')) headers.set('Authorization', `Bearer ${token}`)
  const body = opts.body
  if (!(body instanceof FormData) && method !== 'GET' && method !== 'HEAD' && body !== undefined && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }
  attachCsrfHeader(headers, method)

  const res = await fetch(`${BASE}${path}`, { ...opts, method, headers, body, credentials: 'include' })
  const data = await parseResponse(res)
  // 401：常见过期。403：部分网关/Java 对匿名或坏 JWT 仍返回 403（仅 /api/payment 时旧前端不刷新）；/api/auth/me 亦可能 403，需一并尝试 refresh。
  const pathOnly = path.split('?')[0] || path
  const looksLikeAuthFailure =
    res.status === 401 ||
    (res.status === 403 &&
      (path.includes('/api/payment') ||
        path.includes('/api/wallet') ||
        path.includes('/api/refunds') ||
        pathOnly === '/api/auth/me'))
  if (
    looksLikeAuthFailure &&
    authAttempt === 0 &&
    getAccessToken() &&
    !shouldSkipRefresh(path) &&
    !headers.has('X-Skip-Auth-Refresh')
  ) {
    const newToken = await refreshAccessTokenOnce()
    if (newToken) return requestJson<T>(path, opts, 1)
  }
  if (!res.ok) {
    let msg = errorMessage(data, res.statusText)
    if (res.status === 504) {
      msg =
        'HTTP 504 Gateway Time-out（网关在等待上游响应时超时。工作台 LLM / 基准测试可能需数分钟：请为 location /api/ 设置 proxy_read_timeout 3600s 或更高。）'
    } else if (typeof msg === 'string' && msg.length > 600) {
      msg = `${msg.slice(0, 400)}…`
    }
    throw new ApiError(msg, res.status, data)
  }
  return data as T
}

export async function fetchZipBlob(path: string, headers?: HeadersInit): Promise<Blob> {
  const res = await fetch(`${BASE}${path}`, headers ? { headers } : {})
  const buf = await res.arrayBuffer()
  if (!res.ok) {
    throw new ApiError(res.statusText || '请求失败', res.status)
  }
  const u8 = new Uint8Array(buf)
  if (buf.byteLength < 4 || u8[0] !== 0x50 || u8[1] !== 0x4b) {
    throw new Error('响应不是 zip 文件')
  }
  return new Blob([buf], { type: 'application/zip' })
}

/** 与 requestJson 相同的鉴权与 401 刷新逻辑，返回二进制（如 TTS 音频）。 */
export async function requestBlob(path: string, opts: RequestInit = {}, authAttempt = 0): Promise<Blob> {
  const method = (opts.method || 'GET').toUpperCase()
  const headers = new Headers(opts.headers || {})
  const token = getAccessToken()
  if (token && !headers.has('Authorization')) headers.set('Authorization', `Bearer ${token}`)
  const body = opts.body
  if (!(body instanceof FormData) && method !== 'GET' && method !== 'HEAD' && body !== undefined && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }
  attachCsrfHeader(headers, method)

  const res = await fetch(`${BASE}${path}`, { ...opts, method, headers, body, credentials: 'include' })
  const pathOnly = path.split('?')[0] || path
  const looksLikeAuthFailure =
    res.status === 401 ||
    (res.status === 403 &&
      (path.includes('/api/payment') ||
        path.includes('/api/wallet') ||
        path.includes('/api/refunds') ||
        pathOnly === '/api/auth/me'))
  if (
    looksLikeAuthFailure &&
    authAttempt === 0 &&
    getAccessToken() &&
    !shouldSkipRefresh(path) &&
    !headers.has('X-Skip-Auth-Refresh')
  ) {
    const newToken = await refreshAccessTokenOnce()
    if (newToken) return requestBlob(path, opts, 1)
  }
  if (!res.ok) {
    let detail: unknown
    try {
      detail = await res.json()
    } catch {
      try {
        detail = await res.text()
      } catch {
        detail = null
      }
    }
    throw new ApiError(errorMessage(detail as any, res.statusText), res.status, detail)
  }
  return res.blob()
}
