import type { Router } from 'vue-router'
import { DEFAULT_POST_AUTH, safeRedirectPath } from '../authPaths'
import { useAuthStore } from '../stores/auth'

export function installAuthGuards(router: Router): void {
  router.beforeEach(async (to) => {
    const matched = Array.isArray(to.matched) ? to.matched : []
    const requiresAuth = matched.some((record) => record.meta.auth) || Boolean(to.meta.auth)
    const requiresAdmin = matched.some((record) => record.meta.admin) || Boolean(to.meta.admin)

    if ((String(to.name) === 'home' || String(to.name) === 'about') && to.hash === '#ai-market') {
      return { name: 'ai-store', replace: true }
    }

    const guestNames = new Set(['login', 'login-email', 'register', 'forgot-password'])
    const auth = useAuthStore()
    if (guestNames.has(String(to.name))) {
      if (auth.hasToken()) {
        const user = await auth.refreshSession()
        if (user) {
          const q = to.query.redirect
          const raw = Array.isArray(q) ? q[0] : q
          if (typeof raw === 'string' && raw.length > 0) {
            return safeRedirectPath(raw)
          }
          return DEFAULT_POST_AUTH
        }
      }
    }

    if (requiresAuth && !auth.hasToken()) {
      return { name: 'login', query: { redirect: to.fullPath } }
    }
    if (requiresAdmin) {
      const user = await auth.refreshSession()
      if (!user) return { name: 'login' }
      if (!user?.is_admin) return { name: 'home' }
    }
    return undefined
  })
}
