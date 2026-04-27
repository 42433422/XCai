import type { RouteLocationNormalizedLoaded, RouteLocationRaw } from 'vue-router'

export function safeRedirectPath(raw: unknown): string {
  if (typeof raw !== 'string' || !raw.startsWith('/')) return '/'
  if (raw.startsWith('//')) return '/'
  if (raw.startsWith('/login')) return '/'
  return raw
}

/**
 * 登录/注册成功后无 ``redirect`` 时的落地页。
 * 使用命名路由，保证在 ``https://xiu-ci.com/market/`` 等子路径（Vite ``base=/market/``）下解析正确。
 */
export const DEFAULT_POST_AUTH: RouteLocationRaw = { name: 'workbench-home' }

export function pickRedirectFromRoute(route: Pick<RouteLocationNormalizedLoaded, 'query'>): RouteLocationRaw {
  const q = route.query.redirect
  const raw = Array.isArray(q) ? q[0] : q
  if (typeof raw === 'string' && raw.length > 0) return safeRedirectPath(raw)
  return DEFAULT_POST_AUTH
}
