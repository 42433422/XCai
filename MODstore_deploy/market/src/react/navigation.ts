import router from '../router/index'
import { safeRedirectPath } from '../authPaths'

export function appHref(path: string): string {
  const base = (import.meta.env.BASE_URL || '/').replace(/\/$/, '')
  return `${base}${path.startsWith('/') ? path : `/${path}`}` || '/'
}

export function navigate(path: string) {
  return router.push(path)
}

export function replace(path: string) {
  return router.replace(path)
}

export function hardReplace(path: string): void {
  window.location.assign(appHref(path))
}

export function redirectAfterAuth(): string {
  const params = new URLSearchParams(window.location.search || '')
  const raw = params.get('redirect')
  return raw ? safeRedirectPath(raw) : '/workbench/home'
}
