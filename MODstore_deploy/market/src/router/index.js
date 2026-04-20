import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/', name: 'home', component: () => import('../views/HomeView.vue') },
  { path: '/login', name: 'login', component: () => import('../views/LoginView.vue') },
  { path: '/login-email', name: 'login-email', component: () => import('../views/LoginByEmailView.vue') },
  { path: '/register', name: 'register', component: () => import('../views/RegisterView.vue') },
  { path: '/catalog/:id', name: 'catalog-detail', component: () => import('../views/CatalogDetailView.vue') },
  { path: '/my-store', name: 'my-store', component: () => import('../views/MyStoreView.vue'), meta: { auth: true } },
  { path: '/wallet', name: 'wallet', component: () => import('../views/WalletView.vue'), meta: { auth: true } },
  { path: '/plans', name: 'plans', component: () => import('../views/PaymentPlansView.vue') },
  { path: '/repository', name: 'repository', component: () => import('../views/RepositoryView.vue'), meta: { auth: true } },
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

router.beforeEach(async (to) => {
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
