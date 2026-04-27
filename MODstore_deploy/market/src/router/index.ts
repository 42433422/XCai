import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import { installAuthGuards } from './guards'

const routes: RouteRecordRaw[] = [
  { path: '/', name: 'home', component: () => import('../views/WorkbenchHomeView.vue') },
  { path: '/about', name: 'about', component: () => import('../views/HomeView.vue') },
  { path: '/ai-store', name: 'ai-store', component: () => import('../views/AiStoreView.vue') },
  { path: '/login', name: 'login', component: () => import('../react/wrappers/LoginReactView.vue') },
  { path: '/legacy-login', name: 'legacy-login', component: () => import('../views/LoginView.vue') },
  { path: '/login-email', name: 'login-email', component: () => import('../react/wrappers/LoginByEmailReactView.vue') },
  { path: '/legacy-login-email', name: 'legacy-login-email', component: () => import('../views/LoginByEmailView.vue') },
  { path: '/forgot-password', name: 'forgot-password', component: () => import('../react/wrappers/ForgotPasswordReactView.vue') },
  { path: '/legacy-forgot-password', name: 'legacy-forgot-password', component: () => import('../views/ForgotPasswordView.vue') },
  { path: '/register', name: 'register', component: () => import('../react/wrappers/RegisterReactView.vue') },
  { path: '/legacy-register', name: 'legacy-register', component: () => import('../views/RegisterView.vue') },
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
  { path: '/notifications', name: 'notifications', component: () => import('../views/NotificationCenter.vue'), meta: { auth: true } },
  { path: '/analytics', name: 'analytics', component: () => import('../views/AnalyticsView.vue'), meta: { auth: true } },
  { path: '/refunds', name: 'refunds', component: () => import('../views/RefundApplyView.vue'), meta: { auth: true } },
  { path: '/recharge', name: 'recharge', component: () => import('../views/WalletRechargeView.vue'), meta: { auth: true } },
  { path: '/plans', name: 'plans', component: () => import('../views/PaymentPlansView.vue') },
  { path: '/workflow', name: 'workflow', component: () => import('../views/WorkflowView.vue'), meta: { auth: true } },
  {
    path: '/workbench',
    component: () => import('../views/WorkbenchView.vue'),
    meta: { auth: true },
    children: [
      { path: '', redirect: { name: 'workbench-home' } },
      { path: 'home', name: 'workbench-home', component: () => import('../views/WorkbenchHomeView.vue') },
      { path: 'unified', name: 'workbench-unified', component: () => import('../views/UnifiedWorkbenchView.vue') },
      {
        path: 'repository',
        name: 'workbench-repository',
        redirect: (to: any) => ({ name: 'workbench-unified', query: { ...to.query, focus: 'repository' } }),
      },
      {
        path: 'workflow',
        name: 'workbench-workflow',
        redirect: (to: any) => ({ name: 'workbench-unified', query: { ...to.query, focus: 'workflow' } }),
      },
      {
        path: 'employee',
        name: 'workbench-employee',
        redirect: (to: any) => ({ name: 'workbench-unified', query: { ...to.query, focus: 'employee' } }),
      },
      { path: 'mod/:modId', name: 'mod-authoring', component: () => import('../views/ModAuthoringView.vue') },
    ],
  },
  { path: '/repository', redirect: '/workbench/repository' },
  {
    path: '/repository/mod/:modId',
    redirect: (to: any) => ({ name: 'mod-authoring', params: { modId: to.params.modId } }),
  },
  { path: '/admin', redirect: '/admin/database', meta: { auth: true, admin: true } },
  { path: '/admin/database', name: 'admin-database', component: () => import('../views/AdminDatabaseView.vue'), meta: { auth: true, admin: true } },
  { path: '/checkout/:orderId', name: 'checkout', component: () => import('../views/PaymentCheckoutView.vue'), meta: { auth: true } },
  { path: '/order/:orderId', name: 'order-detail', component: () => import('../views/OrderDetailView.vue'), meta: { auth: true } },
  { path: '/orders', name: 'orders', component: () => import('../views/OrderListView.vue'), meta: { auth: true } },
  { path: '/account', name: 'account', component: () => import('../views/AccountSettingsView.vue'), meta: { auth: true } },
  { path: '/:pathMatch(.*)*', name: 'not-found', component: () => import('../views/NotFoundView.vue') },
]

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
  scrollBehavior(to, _from, savedPosition) {
    if (savedPosition) return savedPosition
    if (to.hash) return { el: to.hash, behavior: 'smooth' }
    return { top: 0 }
  },
})

installAuthGuards(router)

export default router
