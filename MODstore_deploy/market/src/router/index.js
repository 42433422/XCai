import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/', name: 'home', component: () => import('../views/HomeView.vue') },
  { path: '/ai-store', name: 'ai-store', component: () => import('../views/AiStoreView.vue') },
  { path: '/login', name: 'login', component: () => import('../views/LoginView.vue') },
  { path: '/login-email', name: 'login-email', component: () => import('../views/LoginByEmailView.vue') },
  { path: '/register', name: 'register', component: () => import('../views/RegisterView.vue') },
  { path: '/catalog/:id', name: 'catalog-detail', component: () => import('../views/CatalogDetailView.vue') },
  {
    path: '/wallet',
    component: () => import('../views/WalletLayoutView.vue'),
    meta: { auth: true },
    children: [
      { path: '', name: 'wallet', component: () => import('../views/WalletView.vue') },
      { path: 'purchased', name: 'wallet-purchased', component: () => import('../views/MyStoreView.vue') },
    ],
  },
  { path: '/my-store', redirect: { name: 'wallet-purchased' } },
  { path: '/plans', name: 'plans', component: () => import('../views/PaymentPlansView.vue') },
  {
    path: '/workbench',
    component: () => import('../views/WorkbenchView.vue'),
    meta: { auth: true },
    children: [
      { path: '', redirect: { name: 'workbench-repository' } },
      {
        path: 'repository',
        name: 'workbench-repository',
        component: () => import('../views/RepositoryView.vue'),
      },
      {
        path: 'mod/:modId',
        name: 'mod-authoring',
        component: () => import('../views/ModAuthoringView.vue'),
      },
    ],
  },
  { path: '/repository', redirect: '/workbench/repository' },
  {
    path: '/repository/mod/:modId',
    redirect: (to) => ({ name: 'mod-authoring', params: { modId: to.params.modId } }),
  },
  { path: '/admin', redirect: '/admin/database', meta: { auth: true, admin: true } },
  { path: '/admin/database', name: 'admin-database', component: () => import('../views/AdminDatabaseView.vue'), meta: { auth: true, admin: true } },
  { path: '/checkout/:orderId', name: 'checkout', component: () => import('../views/PaymentCheckoutView.vue'), meta: { auth: true } },
  { path: '/order/:orderId', name: 'order-detail', component: () => import('../views/OrderDetailView.vue'), meta: { auth: true } },
]

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
  scrollBehavior(to, _from, savedPosition) {
    if (savedPosition) return savedPosition
    if (to.hash) {
      return { el: to.hash, behavior: 'smooth' }
    }
    return { top: 0 }
  },
})

function safeRedirectPath(raw) {
  if (typeof raw !== 'string' || !raw.startsWith('/')) return '/'
  if (raw.startsWith('//')) return '/'
  if (raw.startsWith('/login')) return '/'
  return raw
}

router.beforeEach(async (to) => {
  /* 旧链接 /market/#ai-market 或 /#ai-market 仅滚动首页区块；改为进入独立商店页 */
  if (String(to.name) === 'home' && to.hash === '#ai-market') {
    return { name: 'ai-store', replace: true }
  }

  const guestNames = new Set(['login', 'login-email', 'register'])
  if (guestNames.has(String(to.name))) {
    const token = localStorage.getItem('modstore_token')
    if (token) {
      try {
        const res = await fetch('/api/auth/me', {
          headers: { Authorization: `Bearer ${token}` },
        })
        if (res.ok) {
          const q = to.query.redirect
          const raw = Array.isArray(q) ? q[0] : q
          if (typeof raw === 'string' && raw.length > 0) {
            return safeRedirectPath(raw)
          }
          /* 已登录仍打开登录/注册页：默认进工作台，避免重定向到首页像未响应 */
          return '/workbench/repository'
        }
      } catch {
        /* token 无效则留在登录页 */
      }
    }
  }

  if (to.meta.auth && !localStorage.getItem('modstore_token')) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }
  if (to.meta.admin) {
    const token = localStorage.getItem('modstore_token')
    try {
      const res = await fetch('/api/auth/me', {
        headers: { Authorization: `Bearer ${token}` },
      })
      if (!res.ok) return { name: 'login' }
      const data = await res.json()
      if (!data.is_admin) return { name: 'home' }
    } catch {
      return { name: 'home' }
    }
  }
})

export default router
