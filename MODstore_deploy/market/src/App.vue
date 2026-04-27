<template>
  <div class="app-shell" :class="{ 'app-shell--wb-home': isWorkbenchHome }">
    <nav v-if="!isHome && !isEmployeeWorkbench" class="navbar">
      <div class="nav-inner">
        <a href="/" class="nav-brand" @click="switchMode('client')">{{ t('nav.brand') }}</a>
        <div class="nav-links">
          <div class="nav-section">
            <template v-if="isAdmin">
              <button :class="['mode-tab', { active: currentMode === 'client' }]" @click="switchMode('client')">{{ t('nav.client') }}</button>
              <button :class="['mode-tab', { active: currentMode === 'admin' }]" @click="switchMode('admin')">{{ t('nav.admin') }}</button>
            </template>
          </div>

          <div class="nav-section">
            <template v-if="currentMode === 'admin' && isAdmin">
              <a href="/admin/database" class="nav-link nav-admin-link">{{ t('nav.database') }}</a>
              <span class="nav-balance nav-badge">{{ t('nav.adminMode') }}</span>
            </template>

            <template v-else>
              <a href="/workbench" class="nav-link">{{ t('nav.workbench') }}</a>
              <a href="/plans" class="nav-link">{{ t('nav.plans') }}</a>
              <a href="/ai-store" class="nav-link nav-gradient">{{ t('nav.aiStore') }}</a>
            </template>
          </div>

          <div class="nav-section nav-section--user">
            <template v-if="isLoggedIn">
              <a
                v-if="username"
                href="/account"
                :class="['nav-username', membershipTier ? `nav-username--${membershipTier}` : '']"
                :title="membershipLabel ? `${membershipLabel} · ${username}` : username"
              >{{ username }}</a>
              <a
                v-if="levelProfile"
                href="/account"
                class="nav-level-badge"
                :title="`${levelProfile.title || '账号等级'} · 累计经验 ${levelProfile.experience}`"
              >Lv.{{ levelProfile.level }}</a>
              <router-link
                to="/notifications"
                class="nav-link nav-notifications"
                aria-label="通知中心"
              >
                <span class="nav-bell-wrap">
                  <svg class="nav-bell" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
                    <path
                      d="M12 3a5 5 0 0 0-5 5v2.59l-.7 1.4A2 2 0 0 0 8 15h8a2 2 0 0 0 1.7-3.01L17 10.59V8a5 5 0 0 0-5-5z"
                      stroke="currentColor"
                      stroke-width="1.5"
                      stroke-linecap="round"
                      stroke-linejoin="round"
                    />
                    <path d="M10 18a2 2 0 0 0 4 0" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" />
                  </svg>
                  <span v-if="unreadNotifications > 0" class="nav-notif-badge">{{ unreadBadgeText }}</span>
                </span>
              </router-link>
              <a href="/wallet" class="nav-link">{{ t('nav.wallet') }}</a>
              <span class="nav-balance" v-if="balance !== null">¥{{ balance.toFixed(2) }}</span>
              <button class="nav-link btn-logout" @click="doLogout">{{ t('nav.logout') }}</button>
            </template>
            <template v-else>
              <a href="/login" class="nav-link">{{ t('nav.login') }}</a>
              <a href="/register" class="nav-link btn-primary">{{ t('nav.register') }}</a>
            </template>
          </div>
        </div>
      </div>
    </nav>
    <main
      class="main-content"
      :class="{
        'main-content--home': isHome,
        'main-content--employee-full': isEmployeeWorkbench,
        'main-content--wb-home': isWorkbenchHome,
      }"
    >
      <div class="main-content-router">
        <router-view v-slot="{ Component }">
          <transition name="page-fade" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </div>
    </main>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from './i18n'
import { useAuthStore } from './stores/auth'
import { useNotificationStore } from './stores/notifications'
import { useWalletStore } from './stores/wallet'
import { connectRealtime, disconnectRealtime } from './realtimeClient'

const router = useRouter()
const route = useRoute()
const isWorkbenchHome = computed(() => {
  const n = String(route.name || '')
  const p = route.path
  return p === '/' || p === '/workbench/home' || n === 'home' || n === 'workbench-home'
})
const { t } = useI18n()
const authStore = useAuthStore()
const walletStore = useWalletStore()
const notificationStore = useNotificationStore()
const { isLoggedIn, isAdmin, username, currentMode, levelProfile, membership, membershipTier } = storeToRefs(authStore)
const membershipLabel = computed(() => membership.value?.label || '')
const { balance } = storeToRefs(walletStore)
const { unreadCount: unreadNotifications, badgeText: unreadBadgeText } = storeToRefs(notificationStore)
const initialPath = String(router.currentRoute.value.path || '/')
const isHome = ref(initialPath === '/about')
const isEmployeeWorkbench = ref(initialPath.startsWith('/workbench/employee'))

onMounted(() => {
  checkHome()
  void refreshGlobalState()
})

router.afterEach(() => {
  checkHome()
  void refreshGlobalState()
})

function checkHome() {
  const path = String(router.currentRoute.value.path || '/')
  isHome.value = path === '/about'
  isEmployeeWorkbench.value = path.startsWith('/workbench/employee')
}

watch(currentMode, (mode) => {
  if (mode === 'admin') {
    router.push('/admin/database')
  } else {
    router.push('/')
  }
})

watch(
  isLoggedIn,
  (v) => {
    if (v) {
      connectRealtime(() => void notificationStore.refreshUnread())
    } else {
      disconnectRealtime(true)
    }
  },
  { immediate: true },
)

function switchMode(mode) {
  currentMode.value = mode
}

async function refreshGlobalState() {
  await authStore.refreshSession()
  if (authStore.isLoggedIn) {
    await Promise.all([walletStore.refreshBalance(), notificationStore.refreshUnread()])
  } else {
    walletStore.clear()
    notificationStore.clear()
  }
}

async function doLogout() {
  disconnectRealtime(true)
  authStore.logout()
  walletStore.clear()
  notificationStore.clear()
  await router.push('/')
}
</script>

<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
html,
body {
  height: 100%;
}
/* 全局基准字号：大屏略放大，避免整页显得「字小、控件挤」；依赖 rem 的区块会一起变 */
html {
  font-size: clamp(16px, 14px + 0.55vw, 20px);
}
body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  font-size: 1rem;
  line-height: 1.5;
  background: #0a0a0a;
  color: #ffffff;
  -webkit-font-smoothing: antialiased;
}
/* 与顶栏同一套水平节奏：大屏可放宽到 1600px，小屏边距随 vw 变粗/变细 */
:root {
  --layout-gutter: clamp(12px, 3.5vw, 40px);
  --layout-max: min(1600px, calc(100vw - 2 * var(--layout-gutter)));
  --layout-pad-x: var(--layout-gutter);
  /* 与 .nav-inner 高度一致，供首页 scroll-margin、padding-top 等复用 */
  --nav-h: clamp(3.5rem, 3.25rem + 0.6vw, 4rem);
  --page-pad-y: clamp(16px, 2.5vw, 24px);
}
/* 挂载点 #app 在 index.html；至少一屏高，dvh 避免移动端地址栏裁切 */
#app { min-height: 100vh; min-height: 100dvh; display: flex; flex-direction: column; }
.app-shell {
  flex: 1 1 auto;
  display: flex;
  flex-direction: column;
  min-height: 100vh;
  min-height: 100dvh;
  width: 100%;
  min-width: 0;
}
a { text-decoration: none; color: inherit; }

.navbar { background: #111111; border-bottom: 0.5px solid rgba(255,255,255,0.1); position: sticky; top: 0; z-index: 100; }
.nav-inner {
  width: 100%;
  max-width: var(--layout-max);
  margin: 0 auto;
  padding: 0 var(--layout-pad-x);
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-width: 0;
  min-height: var(--nav-h);
  height: var(--nav-h);
}
.nav-brand {
  font-size: clamp(1.125rem, 1rem + 0.35vw, 1.35rem);
  font-weight: 700;
  color: #ffffff;
}
.nav-links { display: flex; align-items: center; gap: 24px; flex-wrap: wrap; }
.nav-section { display: flex; align-items: center; gap: 16px; }
.nav-section--user { border-left: 0.5px solid rgba(255,255,255,0.1); padding-left: 24px; }

.nav-username {
  font-size: 0.875rem;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.75);
  max-width: 120px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  transition: color 0.2s ease, text-shadow 0.2s ease;
  text-decoration: none;
  cursor: pointer;
}
.nav-username:hover {
  filter: brightness(1.08);
}

/* 会员档位用户名配色：tier 由后端 /api/payment/my-plan 的 membership.tier 决定。
   顺序与价格梯度一致：白 → 青 → 金 → 紫 → 玫红 → 翠绿 → 橙 → 红 → 靛 → 太阳金 → 彩虹 */
.nav-username--free {
  color: rgba(255, 255, 255, 0.75);
}
.nav-username--vip {
  color: #67e8f9; /* sky cyan */
  text-shadow: 0 0 8px rgba(103, 232, 249, 0.35);
}
.nav-username--vip_plus {
  color: #fde047; /* warm gold */
  text-shadow: 0 0 8px rgba(253, 224, 71, 0.4);
}
.nav-username--svip1 {
  color: #c084fc; /* violet */
  text-shadow: 0 0 10px rgba(192, 132, 252, 0.45);
}
.nav-username--svip2 {
  color: #f472b6; /* pink */
  text-shadow: 0 0 10px rgba(244, 114, 182, 0.45);
}
.nav-username--svip3 {
  color: #34d399; /* emerald */
  text-shadow: 0 0 10px rgba(52, 211, 153, 0.45);
}
.nav-username--svip4 {
  color: #fb923c; /* orange */
  text-shadow: 0 0 10px rgba(251, 146, 60, 0.5);
}
.nav-username--svip5 {
  color: #fb7185; /* rose */
  text-shadow: 0 0 10px rgba(251, 113, 133, 0.5);
}
.nav-username--svip6 {
  color: #818cf8; /* indigo */
  text-shadow: 0 0 12px rgba(129, 140, 248, 0.55);
}
.nav-username--svip7 {
  color: #fbbf24; /* sun gold */
  text-shadow: 0 0 12px rgba(251, 191, 36, 0.6);
}
/* SVIP8：彩虹渐变填充 + 微动效，凸显顶级会员身份 */
.nav-username--svip8 {
  background: linear-gradient(
    90deg,
    #f87171 0%,
    #fbbf24 18%,
    #34d399 36%,
    #38bdf8 54%,
    #818cf8 72%,
    #c084fc 90%,
    #f472b6 100%
  );
  background-size: 200% 100%;
  -webkit-background-clip: text;
          background-clip: text;
  -webkit-text-fill-color: transparent;
          color: transparent;
  animation: nav-username-rainbow 6s linear infinite;
  text-shadow: none;
  filter: drop-shadow(0 0 6px rgba(255, 255, 255, 0.25));
}
@keyframes nav-username-rainbow {
  0%   { background-position: 0% 50%; }
  100% { background-position: 200% 50%; }
}
.nav-level-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  height: 22px;
  padding: 0 8px;
  border-radius: 999px;
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.02em;
  color: #fff;
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
  white-space: nowrap;
  flex-shrink: 0;
}
.nav-level-badge:hover { filter: brightness(1.1); }

@media (max-width: 768px) {
  .nav-links { gap: 16px; }
  .nav-section { gap: 12px; }
  .nav-section--user { padding-left: 16px; }
  .nav-link { font-size: 0.9rem; padding: 3px 6px; }
  .mode-tab { font-size: 0.85rem; padding: 3px 8px; }
  .nav-balance { font-size: 0.9rem; padding: 3px 8px; }
  .nav-level-badge { height: 20px; font-size: 0.68rem; padding: 0 6px; }
}
.nav-link {
  font-size: 1rem;
  color: rgba(255, 255, 255, 0.5);
  cursor: pointer;
  padding: 0.35rem 0.55rem;
  border-radius: 4px;
  transition: all 0.2s;
}
.nav-link:hover { background: rgba(255,255,255,0.06); color: #ffffff; }
.nav-link.router-link-active { color: #ffffff; font-weight: 600; }

.nav-notifications {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0.35rem 0.5rem;
  position: relative;
}
.nav-bell-wrap {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 1.35rem;
  height: 1.35rem;
}
.nav-bell {
  width: 1.25rem;
  height: 1.25rem;
  color: rgba(255, 255, 255, 0.55);
}
.nav-notifications:hover .nav-bell {
  color: #ffffff;
}
.nav-notif-badge {
  position: absolute;
  top: -4px;
  right: -8px;
  min-width: 1rem;
  padding: 0 0.28rem;
  height: 1rem;
  line-height: 1rem;
  font-size: 0.65rem;
  font-weight: 700;
  text-align: center;
  color: #0a0a0a;
  background: #f87171;
  border-radius: 999px;
  box-shadow: 0 0 0 2px #111;
}
.nav-balance {
  font-size: 1rem;
  color: #4ade80;
  font-weight: 600;
  background: rgba(74, 222, 128, 0.1);
  padding: 0.35rem 0.65rem;
  border-radius: 12px;
}
.nav-badge {
  background: rgba(96, 165, 250, 0.15);
  color: #60a5fa;
  font-size: 0.85rem;
  font-weight: 700;
}

.mode-tab {
  font-size: 0.95rem;
  font-weight: 600;
  padding: 0.35rem 0.65rem;
  border-radius: 4px;
  cursor: pointer;
  border: none;
  background: transparent;
  color: rgba(255, 255, 255, 0.35);
  transition: all 0.2s;
}
.mode-tab:hover { color: rgba(255,255,255,0.7); }
.mode-tab.active { color: #ffffff; background: rgba(255,255,255,0.06); }

.nav-admin-link { color: #60a5fa !important; font-weight: 600; }

.nav-gradient {
  font-size: 0.95rem;
  font-weight: 700;
  color: transparent;
  background: linear-gradient(135deg, #60a5fa, #818cf8);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}
.nav-link.nav-gradient:hover {
  opacity: 0.92;
}
.btn-primary { background: #ffffff; color: #0a0a0a !important; border: none; }
.btn-primary:hover { opacity: 0.9; }
.btn-logout { border: none; background-color: #1f1f1f; }

.main-content {
  /* 0% 伸缩基准：在 app-shell 列 flex 里可靠吃掉顶栏以下剩余高度 */
  flex: 1 1 0%;
  display: flex;
  flex-direction: column;
  width: 100%;
  max-width: var(--layout-max);
  margin-inline: auto;
  padding: var(--page-pad-y) var(--layout-pad-x);
  min-width: 0;
  min-height: 0;
}
/* Grid 单行 1fr：子页面根节点必定被拉到可用高度（flex 列里子项 flex:1 常因 min-height:auto 失效） */
.main-content-router {
  flex: 1 1 0%;
  min-height: 0;
  width: 100%;
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  grid-template-rows: 1fr;
}
.main-content-router > * {
  min-width: 0;
  min-height: 0;
  width: 100%;
  align-self: stretch;
  justify-self: stretch;
}
/* 首页落地页自带全宽布局，外层不再限 1200px */
.main-content--home {
  max-width: none;
  padding: 0;
}

.main-content--employee-full {
  max-width: none;
  padding: 0;
}

/* 工作台首页 / 与窗口等高，禁页面级纵向滚轮，避免与右侧长条档杆冲突；内容在 .wb-gear-scene 内自行滚动 */
html:has(.app-shell--wb-home),
body:has(.app-shell--wb-home) {
  height: 100%;
  max-height: 100%;
  overflow: hidden;
}
#app:has(.app-shell--wb-home) {
  min-height: 0;
  max-height: 100dvh;
  height: 100dvh;
  overflow: hidden;
}
.app-shell--wb-home {
  min-height: 0;
  flex: 1 1 0%;
  max-height: 100%;
  overflow: hidden;
}
.main-content--wb-home {
  max-width: none;
  margin-inline: 0;
  width: 100%;
  padding: 0;
  flex: 1 1 0%;
  min-height: 0;
  overflow: hidden;
}

/* 路由级页面过渡（工作台嵌套路由同名复用） */
.page-fade-enter-active,
.page-fade-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}
.page-fade-enter-from {
  opacity: 0;
  transform: translateY(6px);
}
.page-fade-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}

.flash {
  padding: 0.65rem 1rem;
  border-radius: 6px;
  margin-bottom: 1rem;
  font-size: 1rem;
}
.flash-ok { background: rgba(74,222,128,0.1); color: #4ade80; }
.flash-err { background: rgba(255,80,80,0.1); color: #ff6b6b; }

.card { background: #111111; border-radius: 12px; border: 0.5px solid rgba(255,255,255,0.1); padding: 20px; margin-bottom: 16px; }
.card-title {
  font-size: 1.1rem;
  font-weight: 600;
  margin-bottom: 0.75rem;
}

.btn {
  display: inline-block;
  padding: 0.55rem 1rem;
  border-radius: 8px;
  font-size: 1rem;
  cursor: pointer;
  border: 0.5px solid rgba(255, 255, 255, 0.15);
  background: #111111;
  color: #ffffff;
  transition: all 0.2s;
}
.btn:hover { background: rgba(255,255,255,0.06); }
.btn-primary-solid { background: #ffffff; color: #0a0a0a; border: none; }
.btn-primary-solid:hover { opacity: 0.9; }
.btn-success { background: rgba(74,222,128,0.15); color: #4ade80; border: none; }
.btn-success:hover { background: rgba(74,222,128,0.25); }
.btn-danger { background: rgba(255,80,80,0.15); color: #ff6b6b; border: none; }
.btn-danger:hover { background: rgba(255,80,80,0.25); }
.btn:disabled { opacity: 0.5; cursor: not-allowed; }

.input {
  width: 100%;
  padding: 0.65rem 0.85rem;
  border: 0.5px solid rgba(255, 255, 255, 0.15);
  border-radius: 8px;
  font-size: 1rem;
  outline: none;
  transition: border-color 0.2s;
  background: rgba(255, 255, 255, 0.03);
  color: #ffffff;
}
.input:focus { border-color: rgba(255,255,255,0.3); }
.input::placeholder { color: rgba(255,255,255,0.3); }

.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(min(100%, 17.5rem), 1fr));
  gap: 16px;
}

@media (max-width: 640px) {
  :root {
    --layout-gutter: 12px;
    --nav-h: auto;
    --page-pad-y: 12px;
  }
  html {
    font-size: 16px;
  }
  .navbar {
    position: sticky;
  }
  .nav-inner {
    height: auto;
    min-height: 0;
    align-items: flex-start;
    gap: 0.75rem;
    padding-top: 0.75rem;
    padding-bottom: 0.75rem;
  }
  .nav-brand {
    flex: 0 0 auto;
    padding-top: 0.2rem;
  }
  .nav-links {
    flex: 1 1 auto;
    justify-content: flex-end;
    gap: 0.5rem;
    max-height: 42vh;
    overflow-y: auto;
  }
  .nav-section {
    gap: 0.35rem;
    justify-content: flex-end;
    flex-wrap: wrap;
  }
  .nav-section--user {
    border-left: none;
    padding-left: 0;
    width: 100%;
  }
  .nav-username,
  .nav-balance {
    display: none;
  }
  .nav-link,
  .mode-tab {
    min-height: 36px;
    display: inline-flex;
    align-items: center;
    padding: 0.35rem 0.55rem;
  }
  .main-content {
    padding: var(--page-pad-y) var(--layout-pad-x);
  }
  .main-content--wb-home {
    padding: 0;
  }
  .card {
    padding: 16px;
  }
  .btn {
    min-height: 40px;
  }
}
</style>
