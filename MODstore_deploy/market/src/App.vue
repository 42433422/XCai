<template>
  <div
    class="app-shell"
    :class="{ 'app-shell--wb-home': isWorkbenchHome, 'app-shell--viewport-locked': isLoggedIn }"
  >
    <div v-if="isLoggedIn" class="app-body" :style="{ '--wb-sidebar-w': wbSidebar.sidebarCollapsed ? '56px' : '240px' }">
      <aside class="wb-sidebar" :class="{ 'wb-sidebar--collapsed': wbSidebar.sidebarCollapsed }">
        <div class="wb-sidebar-top">
          <button type="button" class="wb-sidebar-toggle" @click="wbSidebar.toggleSidebar()">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4"><rect x="0.5" y="2" width="15" height="12" rx="1.5" fill="none"/><rect x="2" y="4" width="3.5" height="8" rx="0.5" fill="currentColor"/></svg>
          </button>
          <button v-if="currentMode !== 'admin'" type="button" class="wb-sidebar-new-chat" @click="handleNewChat">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"><line x1="8" y1="2" x2="8" y2="14"/><line x1="2" y1="8" x2="14" y2="8"/></svg>
            <span>新对话</span>
          </button>
          <span v-else class="wb-sidebar-admin-label">管理端</span>
        </div>

        <div class="wb-sidebar-conv-list" v-if="currentMode !== 'admin'">
          <div v-for="conv in wbSidebar.conversations" :key="conv.id" class="wb-sidebar-conv-item-wrap">
            <div class="wb-sidebar-conv-item" :class="{ 'wb-sidebar-conv-item--active': conv.id === wbSidebar.activeConversationId }" :style="{ transform: convSwipeOffset[conv.id] ? `translateX(-${convSwipeOffset[conv.id]}px)` : '' }" @click="handlePickConversation(conv.id)" @touchstart.passive="onConvTouchStart($event, conv.id)" @touchmove.passive="onConvTouchMove($event, conv.id)" @touchend="onConvTouchEnd(conv.id)" @mousedown.prevent="onConvMouseDown($event, conv.id)">
              <span class="wb-sidebar-conv-title">{{ conv.title || '新对话' }}</span>
              <span class="wb-sidebar-conv-time">{{ formatConvTime(conv.updatedAt) }}</span>
            </div>
            <button type="button" class="wb-sidebar-conv-delete" :style="{ opacity: convSwipeOffset[conv.id] ? 1 : 0, pointerEvents: convSwipeOffset[conv.id] ? 'auto' : 'none' }" @click.stop="wbSidebar.removeConversation(conv.id)" aria-label="删除对话">
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"><path d="M2 4h10M5 4V2.5a.5.5 0 01.5-.5h3a.5.5 0 01.5.5V4M3.5 4v7.5a1 1 0 001 1h5a1 1 0 001-1V4"/></svg>
            </button>
          </div>
        </div>

        <div class="wb-sidebar-admin-nav" v-if="currentMode === 'admin'">
          <div class="wb-sidebar-admin-nav-title">管理端</div>
          <router-link :to="{ name: 'admin-database' }" class="wb-sidebar-mode-btn" :class="{ 'wb-sidebar-mode-btn--active': route.name === 'admin-database' }">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"><ellipse cx="8" cy="4" rx="5.5" ry="2.5"/><path d="M2.5 4v8c0 1.38 2.46 2.5 5.5 2.5s5.5-1.12 5.5-2.5V4"/><path d="M2.5 8c0 1.38 2.46 2.5 5.5 2.5s5.5-1.12 5.5-2.5"/></svg>
            <span>数据库管理</span>
          </router-link>
          <router-link :to="{ name: 'admin-duty-employees' }" class="wb-sidebar-mode-btn" :class="{ 'wb-sidebar-mode-btn--active': route.name === 'admin-duty-employees' }">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"><circle cx="8" cy="4.5" r="2.5"/><path d="M3 14v-1a4 4 0 018 0v1"/><path d="M12 3l1.5 1.5M12 3l1.5-1.5"/></svg>
            <span>值班员工</span>
          </router-link>
          <router-link :to="{ name: 'admin-ops-audit' }" class="wb-sidebar-mode-btn" :class="{ 'wb-sidebar-mode-btn--active': route.name === 'admin-ops-audit' }">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"><path d="M2 3h12v10H2z"/><path d="M5 7h6M5 10h4"/></svg>
            <span>运维审计</span>
          </router-link>
          <router-link :to="{ name: 'admin-employee-autonomy' }" class="wb-sidebar-mode-btn" :class="{ 'wb-sidebar-mode-btn--active': route.name === 'admin-employee-autonomy' }">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"><path d="M8 1v2M8 13v2M1 8h2M13 8h2"/><circle cx="8" cy="8" r="3"/><path d="M3.05 3.05l1.41 1.41M11.54 11.54l1.41 1.41M3.05 12.95l1.41-1.41M11.54 4.46l1.41-1.41"/></svg>
            <span>员工自主决策</span>
          </router-link>
          <router-link :to="{ name: 'admin-change-requests' }" class="wb-sidebar-mode-btn" :class="{ 'wb-sidebar-mode-btn--active': route.name === 'admin-change-requests' }">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"><path d="M2 4l3-2 3 2v4l-3 2-3-2V4z"/><path d="M8 4l3-2 3 2v4l-3 2-3-2V4z"/></svg>
            <span>变更请求</span>
          </router-link>
          <router-link :to="{ name: 'admin-yuangon-onboard' }" class="wb-sidebar-mode-btn" :class="{ 'wb-sidebar-mode-btn--active': route.name === 'admin-yuangon-onboard' }">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"><path d="M8 1.5v4M8 10.5v4M1.5 8h4M10.5 8h4"/><circle cx="8" cy="8" r="2.5"/></svg>
            <span>员工入职</span>
          </router-link>
          <router-link :to="{ name: 'admin-orchestrate-jobs' }" class="wb-sidebar-mode-btn" :class="{ 'wb-sidebar-mode-btn--active': route.name === 'admin-orchestrate-jobs' }">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"><path d="M1.5 2h5v5h-5z"/><path d="M9.5 2h5v5h-5z"/><path d="M1.5 9h5v5h-5z"/><path d="M9.5 9h5v5h-5z"/></svg>
            <span>编排任务</span>
          </router-link>
          <router-link :to="{ name: 'admin-customer-service' }" class="wb-sidebar-mode-btn" :class="{ 'wb-sidebar-mode-btn--active': route.name === 'admin-customer-service' }">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"><path d="M3 7a5 5 0 0110 0v2a5 5 0 01-10 0V7z"/><path d="M1 10v1a2 2 0 004 0V9"/><path d="M11 9v2a2 2 0 004 0v-1"/><path d="M6 13a2 2 0 004 0"/></svg>
            <span>客服审核</span>
          </router-link>
          <router-link :to="{ name: 'admin-butler-skills' }" class="wb-sidebar-mode-btn" :class="{ 'wb-sidebar-mode-btn--active': route.name === 'admin-butler-skills' }">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"><path d="M8 1l1.5 3.5L13 5.3l-2.5 2.4.6 3.3L8 9.3l-3.1 1.7.6-3.3L3 5.3l3.5-.8z"/></svg>
            <span>管家技能</span>
          </router-link>
          <router-link :to="{ name: 'admin-ai-accounts' }" class="wb-sidebar-mode-btn" :class="{ 'wb-sidebar-mode-btn--active': route.name === 'admin-ai-accounts' }">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="2" width="12" height="12" rx="2"/><path d="M2 6h12"/><circle cx="5" cy="4" r="0.5" fill="currentColor"/><circle cx="8" cy="4" r="0.5" fill="currentColor"/></svg>
            <span>AI 账号池</span>
          </router-link>
        </div>

        <div class="wb-sidebar-divider"></div>

        <div class="wb-sidebar-modes" v-if="currentMode !== 'admin'">
          <button type="button" class="wb-sidebar-mode-btn" :class="{ 'wb-sidebar-mode-btn--active': wbSidebar.activeMode === 'direct' }" @click="handleModeClick('direct')">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"><path d="M2 4h12M2 8h8M2 12h5"/></svg>
            <span>聊</span>
          </button>
          <button type="button" class="wb-sidebar-mode-btn" :class="{ 'wb-sidebar-mode-btn--active': wbSidebar.activeMode === 'make' }" @click="handleModeClick('make')">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"><rect x="1.5" y="1.5" width="13" height="13" rx="2"/><path d="M8 5v6M5 8h6"/></svg>
            <span>做</span>
          </button>
          <button type="button" class="wb-sidebar-mode-btn" :class="{ 'wb-sidebar-mode-btn--active': wbSidebar.activeMode === 'voice' }" @click="handleModeClick('voice')">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"><path d="M8 2v8"/><path d="M5 6a3 3 0 016 0v2a3 3 0 01-6 0V6z"/><path d="M2 10v1a6 6 0 0012 0v-1"/></svg>
            <span>说</span>
          </button>
        </div>

        <div class="wb-sidebar-bottom">
          <div class="wb-sidebar-nav-links">
            <router-link :to="{ name: 'workbench-home' }" class="wb-sidebar-mode-btn" :class="{ 'wb-sidebar-mode-btn--active': isWorkbenchHome }">
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"><rect x="1.5" y="2.5" width="13" height="9" rx="1.5"/><path d="M1.5 5.5h13"/><path d="M5 11.5h2"/></svg>
              <span>工作台</span>
            </router-link>
            <router-link :to="{ name: 'plans' }" class="wb-sidebar-mode-btn">
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"><path d="M8 1.5l1.85 3.75 4.15.6-3 2.93.71 4.12L8 10.87l-3.71 1.95.71-4.12-3-2.93 4.15-.6z"/></svg>
              <span>会员</span>
            </router-link>
            <router-link :to="{ name: 'ai-store' }" class="wb-sidebar-mode-btn wb-sidebar-nav-gradient">
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"><path d="M3 2h10l-1.2 7.2a2 2 0 01-2 1.6H6.2a2 2 0 01-2-1.6L3 2z"/><path d="M5.5 13a1.5 1.5 0 003 0M3 2h10"/></svg>
              <span>AI 市场</span>
            </router-link>
            <router-link :to="{ name: 'customer-service' }" class="wb-sidebar-mode-btn wb-sidebar-mode-btn--cs">
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"><path d="M3 7a5 5 0 0110 0v2a5 5 0 01-10 0V7z"/><path d="M1 10v1a2 2 0 004 0V9"/><path d="M11 9v2a2 2 0 004 0v-1"/><path d="M6 13a2 2 0 004 0"/></svg>
              <span>AI 客服</span>
            </router-link>
            <router-link :to="{ name: 'sandbox' }" class="wb-sidebar-mode-btn">
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"><path d="M2 5l6-3 6 3v6l-6 3-6-3V5z"/><path d="M8 2v14"/><path d="M2 5l6 3 6-3"/></svg>
              <span>沙箱测试</span>
            </router-link>
            <a href="/index.html" class="wb-sidebar-mode-btn" target="_blank" rel="noopener">
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"><circle cx="8" cy="8" r="6.5"/><path d="M1.5 8h13"/><path d="M8 1.5a10 10 0 012.5 6.5A10 10 0 018 14.5a10 10 0 01-2.5-6.5A10 10 0 018 1.5z"/></svg>
              <span>官网首页</span>
            </a>
            <button v-if="isAdmin" type="button" class="wb-sidebar-mode-btn" :class="{ 'wb-sidebar-mode-btn--active': currentMode === 'admin' }" @click="switchMode('admin')">
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"><path d="M8 1l1 3h3l-2.5 1.8.9 2.7L8 7l-2.4 1.5.9-2.7L4 4h3z"/><path d="M3 10.5l1 1.5h8l1-1.5"/><path d="M4 13h8"/></svg>
              <span>管理端</span>
            </button>
          </div>
          <div class="wb-sidebar-divider"></div>
          <button v-if="currentMode === 'admin'" type="button" class="wb-sidebar-mode-btn wb-sidebar-back-btn" @click="switchMode('client')">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"><path d="M10 3L5 8l5 5"/></svg>
            <span>返回客户端</span>
          </button>
          <template v-if="currentMode !== 'admin'">
          <button type="button" class="wb-sidebar-mode-btn" @click="handleSidebarSettings">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"><circle cx="8" cy="8" r="2.5"/><path d="M8 1.5v1.2M8 13.3v1.2M1.5 8h1.2M13.3 8h1.2M3.4 3.4l.85.85M11.75 11.75l.85.85M3.4 12.6l.85-.85M11.75 4.25l.85-.85"/></svg>
            <span>设置</span>
          </button>
          <router-link :to="{ name: 'notifications' }" class="wb-sidebar-mode-btn" title="通知">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"><path d="M8 2a4 4 0 0 0-4 4v2.07l-.56 1.12A1.6 1.6 0 0 0 4.87 11.8h6.26a1.6 1.6 0 0 0 1.43-2.61L12 8.07V6a4 4 0 0 0-4-4z"/><path d="M6.5 13a1.5 1.5 0 0 0 3 0"/></svg>
            <span>通知</span>
          </router-link>
          <router-link :to="{ name: 'wallet' }" class="wb-sidebar-mode-btn" title="钱包">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"><rect x="1.5" y="4" width="13" height="9" rx="1.5"/><path d="M1.5 7h13"/><path d="M11 9.5h1.5"/></svg>
            <span>钱包</span>
          </router-link>
          </template>
          <div class="wb-sidebar-user-row">
            <router-link :to="{ name: 'account' }" class="wb-sidebar-user-link">{{ username || '' }}</router-link>
            <router-link v-if="levelProfile" :to="{ name: 'account' }" class="wb-sidebar-level-badge" :title="`${levelProfile?.title || '新手'} · 累计经验 ${levelProfile?.experience}`">Lv.{{ levelProfile?.level }}</router-link>
            <span v-if="balance !== null" class="wb-sidebar-balance">¥{{ balance.toFixed(2) }}</span>
            <span v-else class="wb-sidebar-balance wb-sidebar-balance--loading">...</span>
            <button type="button" class="wb-sidebar-logout-btn" @click="doLogout">退出</button>
          </div>
        </div>
      </aside>
      <main
        class="main-content main-content--with-sidebar"
        :class="{
          'main-content--home': isHome,
          'main-content--employee-full': isEmployeeWorkbench,
          'main-content--wb-home': isWorkbenchHome,
          'main-content--account': isAccountPage,
        }"
      >
        <div class="main-content-router">
          <router-view v-slot="{ Component }">
            <keep-alive :max="6">
              <component v-if="Component" :is="Component" :key="topLevelRouterCacheKey" />
            </keep-alive>
          </router-view>
        </div>
      </main>
    </div>
    <main
      v-if="!isLoggedIn"
      class="main-content"
      :class="{
        'main-content--home': isHome,
        'main-content--employee-full': isEmployeeWorkbench,
        'main-content--wb-home': isWorkbenchHome,
        'main-content--account': isAccountPage,
      }"
    >
      <div class="main-content-router">
        <router-view v-slot="{ Component }">
          <!-- keep-alive：从 AI 客服、脚本工作流沙箱等返回时保留工作台内存态（「做」规划、一档聊天等），避免整页重新挂载丢进度 -->
          <!-- max 从 24 降为 6：限制同时持有响应式订阅的实例数，减少内存与后台 watcher 开销 -->
          <keep-alive :max="6">
            <component v-if="Component" :is="Component" :key="topLevelRouterCacheKey" />
          </keep-alive>
        </router-view>
      </div>
    </main>
    <Teleport to="body">
      <FloatingAgentRoot v-if="shouldShowButler" />
      <div
        v-if="selfCreditOpen"
        class="nav-self-credit-overlay"
        role="presentation"
        @click.self="closeSelfCreditModal"
      >
        <div
          class="nav-self-credit-dialog"
          role="dialog"
          aria-modal="true"
          :aria-label="t('nav.adminSelfCreditTitle')"
          @click.stop
        >
          <h3 class="nav-self-credit-dialog__title">{{ t('nav.adminSelfCreditTitle') }}</h3>
          <p class="nav-self-credit-dialog__hint">{{ t('nav.adminSelfCreditHint') }}</p>
          <label class="nav-self-credit-dialog__label">{{ t('nav.adminSelfCreditAmount') }}</label>
          <input
            v-model="selfCreditAmount"
            type="number"
            min="0.01"
            step="0.01"
            class="nav-self-credit-dialog__input"
            autocomplete="off"
          />
          <label class="nav-self-credit-dialog__label">{{ t('nav.adminSelfCreditNote') }}</label>
          <input v-model="selfCreditNote" type="text" class="nav-self-credit-dialog__input" autocomplete="off" />
          <p v-if="selfCreditErr" class="nav-self-credit-dialog__err">{{ selfCreditErr }}</p>
          <div class="nav-self-credit-dialog__actions">
            <button type="button" class="nav-self-credit-dialog__primary" :disabled="selfCreditBusy" @click="submitSelfCredit">
              {{ t('nav.adminSelfCreditSubmit') }}
            </button>
            <button type="button" class="nav-self-credit-dialog__secondary" :disabled="selfCreditBusy" @click="closeSelfCreditModal">
              {{ t('nav.adminSelfCreditCancel') }}
            </button>
          </div>
        </div>
      </div>
      <div
        v-if="adminUnlockOpen"
        class="nav-self-credit-overlay"
        role="presentation"
        @click.self="closeAdminUnlockModal"
      >
        <div
          class="nav-self-credit-dialog"
          role="dialog"
          aria-modal="true"
          aria-label="管理端解锁"
          @click.stop
        >
          <h3 class="nav-self-credit-dialog__title">解锁管理端</h3>
          <p class="nav-self-credit-dialog__hint">
            请输入<strong>连续 6 位</strong>十六进制身份校验码（可从 XCmax「服务器功能」页眉<strong>身份码</strong>复制，或从当日摘要邮件正文中复制）。<br />
            <span class="nav-admin-unlock__hint-warn">须与<strong>当前浏览器所连市场 API</strong>为同一套 MODstore，或运维已配置<strong>跨库校验</strong>（自建签发 + 公网消费，见服务器 .env.example）。</span><br />
            <span class="nav-admin-unlock__hint-warn"
              >若摘要邮件由<strong>自建服务器</strong>发出，而当前站点为公网修茈市场，则<strong>本页无法校验该码</strong>；请用 XCmax 页眉的<strong>打开市场</strong>或自建站点解锁。</span
            ><br />
            <span class="nav-admin-unlock__hint-warn">请勿填示例；可含空格，失焦或提交时会自动去掉非十六进制字符并只取前 6 位。</span>
          </p>
          <label class="nav-self-credit-dialog__label">身份校验码</label>
          <input
            v-model="adminUnlockCode"
            type="text"
            maxlength="32"
            inputmode="text"
            autocomplete="off"
            spellcheck="false"
            class="nav-self-credit-dialog__input nav-admin-unlock__code"
            placeholder="粘贴 6 位码"
            @blur="onAdminUnlockInputBlur"
            @keyup.enter="submitAdminUnlock"
          />
          <p v-if="adminUnlockErr" class="nav-self-credit-dialog__err">{{ adminUnlockErr }}</p>
          <div class="nav-self-credit-dialog__actions">
            <button type="button" class="nav-self-credit-dialog__primary" :disabled="adminUnlockBusy" @click="submitAdminUnlock">
              {{ adminUnlockBusy ? '校验中…' : '解锁管理端' }}
            </button>
            <button type="button" class="nav-self-credit-dialog__secondary" :disabled="adminUnlockBusy" @click="closeAdminUnlockModal">
              取消
            </button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, onUnmounted, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from './i18n'
import { useAuthStore } from './stores/auth'
import { useNotificationStore } from './stores/notifications'
import { useWalletStore } from './stores/wallet'
import { connectRealtime, disconnectRealtime } from './realtimeClient'
import { api } from './api'
import FloatingAgentRoot from './components/floating-agent/FloatingAgentRoot.vue'
import { useWorkbenchSidebarStore } from './stores/workbenchSidebar'
import { resolveTopLevelRouterCacheKey } from './router/topLevelCacheKey'

const router = useRouter()
const route = useRoute()

const topLevelRouterCacheKey = computed(() =>
  resolveTopLevelRouterCacheKey({
    path: route.path,
    name: route.name,
    fullPath: route.fullPath,
  }),
)

const isAccountPage = computed(() => route.name === 'account')
const isWorkbenchHome = computed(() => {
  const n = String(route.name || '')
  const p = route.path
  return p === '/' || p === '/workbench/home' || n === 'home' || n === 'workbench-home'
})
const { t } = useI18n()
const authStore = useAuthStore()
const walletStore = useWalletStore()
const notificationStore = useNotificationStore()
const wbSidebar = useWorkbenchSidebarStore()
const { isLoggedIn, isAdmin, username, currentMode, levelProfile } = storeToRefs(authStore)
const { balance } = storeToRefs(walletStore)
const initialPath = String(router.currentRoute.value.path || '/')
const isHome = ref(initialPath === '/about')
const isEmployeeWorkbench = ref(
  initialPath.startsWith('/workbench/employee') ||
  initialPath.startsWith('/workbench/shell') ||
  initialPath.startsWith('/workbench/unified') ||
  initialPath.startsWith('/workbench/mod/'),
)

const BUTLER_EXCLUDED_PATHS = ['/about', '/login', '/login-email', '/forgot-password', '/register']
const shouldShowButler = computed(() => {
  const p = route.path || ''
  if (!isLoggedIn.value) return false
  return !BUTLER_EXCLUDED_PATHS.some((ep) => p === ep || p.startsWith(ep + '/'))
})

const selfCreditOpen = ref(false)
const selfCreditAmount = ref('')
const selfCreditNote = ref('')
const selfCreditErr = ref('')
const selfCreditBusy = ref(false)

function openSelfCreditModal() {
  selfCreditErr.value = ''
  selfCreditAmount.value = ''
  selfCreditNote.value = ''
  selfCreditOpen.value = true
}

function closeSelfCreditModal() {
  if (selfCreditBusy.value) return
  selfCreditOpen.value = false
}

async function submitSelfCredit() {
  const n = Number(selfCreditAmount.value)
  if (!Number.isFinite(n) || n <= 0) {
    selfCreditErr.value = t('nav.adminSelfCreditAmountInvalid')
    return
  }
  selfCreditBusy.value = true
  selfCreditErr.value = ''
  try {
    await api.walletAdminSelfCredit(n, selfCreditNote.value.trim())
    await walletStore.refreshBalance()
    selfCreditOpen.value = false
  } catch (e) {
    selfCreditErr.value = (e as Error)?.message || String(e)
  } finally {
    selfCreditBusy.value = false
  }
}

onMounted(() => {
  checkHome()
  wbSidebar.initConversations()
  void refreshGlobalState()
})

// afterEach 去抖：checkHome 轻量立即执行；refreshGlobalState（3 个网络请求）
// 推迟到浏览器空闲再执行，并在 1500ms 内对相同 path 去重，避免路由切换期间
// 同时占主线程。
let _lastRefreshPath = ''
let _lastRefreshAt = 0
let _refreshIdleId: ReturnType<typeof setTimeout> | null = null

function _scheduleGlobalRefresh() {
  const path = String(router.currentRoute.value.path || '/')
  const now = Date.now()
  // 1500ms 内同路径不重复触发
  if (path === _lastRefreshPath && now - _lastRefreshAt < 1500) return
  if (_refreshIdleId !== null) { clearTimeout(_refreshIdleId); _refreshIdleId = null }
  const run = () => {
    _refreshIdleId = null
    _lastRefreshPath = String(router.currentRoute.value.path || '/')
    _lastRefreshAt = Date.now()
    void refreshGlobalState()
  }
  if (typeof window.requestIdleCallback === 'function') {
    const id = window.requestIdleCallback(run, { timeout: 2000 })
    // 用 setTimeout 包装确保可清理
    _refreshIdleId = setTimeout(() => { window.cancelIdleCallback(id) }, 3000)
    // 在 idle 完成后清除
    window.requestIdleCallback(() => {
      if (_refreshIdleId !== null) { clearTimeout(_refreshIdleId); _refreshIdleId = null }
    })
  } else {
    // 不支持 requestIdleCallback 的环境（如 Safari < 15.4）降级到 300ms delay
    _refreshIdleId = setTimeout(run, 300)
  }
}

router.afterEach(() => {
  checkHome()
  _scheduleGlobalRefresh()
})

function checkHome() {
  const path = String(router.currentRoute.value.path || '/')
  isHome.value = path === '/about'
  isEmployeeWorkbench.value =
    path.startsWith('/workbench/employee') ||
    path.startsWith('/workbench/shell') ||
    path.startsWith('/workbench/unified') ||
    path.startsWith('/workbench/mod/')
}

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

function switchMode(mode: 'client' | 'admin') {
  if (mode === 'admin' && isAdmin.value && !authStore.adminUiUnlocked) {
    openAdminUnlockModal()
    return
  }
  currentMode.value = mode
  if (mode === 'admin') {
    void router.push({ name: 'admin-database' })
  } else {
    void router.push({ name: 'workbench-home' })
  }
}

const adminUnlockOpen = ref(false)
const adminUnlockCode = ref('')
const adminUnlockErr = ref('')
const adminUnlockBusy = ref(false)

function normalizeAdminUnlockCode(raw: string): string {
  return (raw || '').replace(/[^0-9A-Fa-f]/gi, '').toUpperCase().slice(0, 6)
}

/** 失焦时把「A 5 0 6 E 7」收成连续 6 位，避免误以为带空格也能原样提交。 */
function onAdminUnlockInputBlur() {
  const hex = normalizeAdminUnlockCode(adminUnlockCode.value || '')
  adminUnlockCode.value = hex
}

function openAdminUnlockModal() {
  adminUnlockCode.value = ''
  adminUnlockErr.value = ''
  adminUnlockOpen.value = true
}

function closeAdminUnlockModal() {
  if (adminUnlockBusy.value) return
  adminUnlockOpen.value = false
}

async function submitAdminUnlock() {
  const raw = normalizeAdminUnlockCode(adminUnlockCode.value || '')
  if (raw.length !== 6 || !/^[0-9A-F]{6}$/.test(raw)) {
    adminUnlockErr.value = '请输入恰好 6 位十六进制（0–9、A–F），可从 XCmax 身份码或摘要邮件复制，勿填示例'
    return
  }
  adminUnlockBusy.value = true
  adminUnlockErr.value = ''
  adminUnlockCode.value = raw
  const VERIFY_MS = 45000
  let verifyTimer: ReturnType<typeof setTimeout> | undefined
  const timeoutReject = new Promise<never>((_, rej) => {
    verifyTimer = window.setTimeout(
      () => rej(new Error(`校验请求超时（${VERIFY_MS / 1000}s），请检查网络或稍后重试`)),
      VERIFY_MS,
    )
  })
  try {
    const res = (await Promise.race([
      (api.verifyAdminDigestCode(raw) as Promise<{ ok?: boolean; expires_at?: string }>).finally(() => {
        if (verifyTimer !== undefined) window.clearTimeout(verifyTimer)
      }),
      timeoutReject,
    ])) as { ok?: boolean; expires_at?: string }
    if (!res?.ok) {
      adminUnlockErr.value = '校验失败：请粘贴页眉身份码或当日摘要中的 6 位码（勿含空格/示例），或刷新 XCmax 后重试'
      return
    }
    authStore.setAdminDigestUnlock(String(res.expires_at || ''))
    adminUnlockOpen.value = false
    currentMode.value = 'admin'
    void router.push({ name: 'admin-database' })
  } catch (e) {
    const baseMsg = e instanceof Error ? e.message : String(e)
    const hint =
      /身份码无效|已过期|校验失败|400/i.test(baseMsg) &&
      !/MODSTORE_DIGEST|UPSTREAM|digest_api/i.test(baseMsg)
        ? ' 请确认：浏览器里打开的修茈市场与该身份码的 API 源一致（见 XCmax「服务器功能」页眉下方提示）。'
        : ''
    adminUnlockErr.value = baseMsg + hint
  } finally {
    adminUnlockBusy.value = false
  }
}

async function refreshGlobalState() {
  await authStore.refreshSession()
  // 首次 /api/auth/me 若遇 502/网络抖动，user 会被清空但 JWT 仍保留，顶栏会误显示「登录」；短延迟后强刷一次
  if (!authStore.isLoggedIn && authStore.hasToken()) {
    await new Promise((r) => setTimeout(r, 350))
    await authStore.refreshSession(true)
  }
  if (authStore.isLoggedIn) {
    await Promise.all([walletStore.refreshBalance(), notificationStore.refreshUnread()])
  } else {
    walletStore.clear()
    notificationStore.clear()
  }
}

function handleSidebarSettings() {
  const event = new CustomEvent('wb-open-settings')
  window.dispatchEvent(event)
}

function handleNewChat() {
  if (!isWorkbenchHome.value) {
    router.push({ name: 'workbench-home' })
  }
  window.dispatchEvent(new CustomEvent('wb-new-chat'))
}

function handlePickConversation(id: string) {
  if (convJustSwiped.value) {
    convJustSwiped.value = false
    return
  }
  if (convSwipeOffset[id]) {
    convSwipeOffset[id] = 0
    return
  }
  Object.keys(convSwipeOffset).forEach((k) => {
    if (k !== id && convSwipeOffset[k]) convSwipeOffset[k] = 0
  })
  wbSidebar.pickConversation(id)
  if (!isWorkbenchHome.value) {
    router.push({ name: 'workbench-home' })
  }
}

function handleModeClick(mode: 'direct' | 'make' | 'voice') {
  if (!isWorkbenchHome.value) {
    wbSidebar.setActiveMode(mode)
    router.push({ name: 'workbench-home' })
  } else {
    window.dispatchEvent(new CustomEvent('wb-mode-switch', { detail: mode }))
  }
}

const convSwipeOffset = reactive<Record<string, number>>({})
const convTouchStartX = reactive<Record<string, number>>({})
const DELETE_BTN_WIDTH = 56

function onConvTouchStart(e: TouchEvent, id: string) {
  convTouchStartX[id] = e.touches[0].clientX
}

function onConvTouchMove(e: TouchEvent, id: string) {
  const startX = convTouchStartX[id] ?? 0
  const dx = startX - e.touches[0].clientX
  convSwipeOffset[id] = Math.max(0, Math.min(dx, DELETE_BTN_WIDTH))
}

function onConvTouchEnd(id: string) {
  const offset = convSwipeOffset[id] ?? 0
  if (offset < DELETE_BTN_WIDTH / 2) {
    convSwipeOffset[id] = 0
  } else {
    convSwipeOffset[id] = DELETE_BTN_WIDTH
    convJustSwiped.value = true
  }
  delete convTouchStartX[id]
}

const convMouseDragging = ref(false)
const convMouseStartX = ref(0)
const convMouseId = ref('')
const convJustSwiped = ref(false)

function onConvMouseDown(e: MouseEvent, id: string) {
  convMouseDragging.value = true
  convMouseStartX.value = e.clientX
  convMouseId.value = id
}

function onConvMouseMove(e: MouseEvent) {
  if (!convMouseDragging.value) return
  const dx = convMouseStartX.value - e.clientX
  convSwipeOffset[convMouseId.value] = Math.max(0, Math.min(dx, DELETE_BTN_WIDTH))
}

function onConvMouseUp() {
  if (!convMouseDragging.value) return
  const id = convMouseId.value
  const offset = convSwipeOffset[id] ?? 0
  if (offset < DELETE_BTN_WIDTH / 2) {
    convSwipeOffset[id] = 0
  } else {
    convSwipeOffset[id] = DELETE_BTN_WIDTH
    convJustSwiped.value = true
  }
  convMouseDragging.value = false
}

onMounted(() => {
  window.addEventListener('mousemove', onConvMouseMove)
  window.addEventListener('mouseup', onConvMouseUp)
})

onUnmounted(() => {
  window.removeEventListener('mousemove', onConvMouseMove)
  window.removeEventListener('mouseup', onConvMouseUp)
})

function formatConvTime(ts: number | undefined): string {
  if (!ts) return ''
  const d = new Date(ts)
  const now = new Date()
  const diffMs = now.getTime() - d.getTime()
  if (diffMs < 60000) return '刚刚'
  if (diffMs < 3600000) return `${Math.floor(diffMs / 60000)}分钟前`
  if (diffMs < 86400000) return `${Math.floor(diffMs / 3600000)}小时前`
  if (diffMs < 604800000) return `${Math.floor(diffMs / 86400000)}天前`
  return `${d.getMonth() + 1}/${d.getDate()}`
}

async function doLogout() {
  disconnectRealtime(true)
  authStore.logout()
  walletStore.clear()
  notificationStore.clear()
  await router.push({ name: 'login' })
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
  background: var(--color-bg-body);
  color: var(--color-text-primary);
  -webkit-font-smoothing: antialiased;
}
/* 与顶栏同一套水平节奏：大屏可放宽到 1600px，小屏边距随 vw 变粗/变细 */
:root {
  --layout-gutter: clamp(12px, 3.5vw, 40px);
  --layout-max: min(1600px, calc(100vw - 2 * var(--layout-gutter)));
  --layout-pad-x: var(--layout-gutter);
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

.app-body {
  display: flex;
  flex: 1 1 0%;
  min-height: 0;
  overflow: hidden;
}

.main-content--with-sidebar {
  flex: 1 1 0%;
  min-width: 0;
  min-height: 0;
  overflow: auto;
  max-width: none;
  margin-inline: 0;
  width: auto;
  padding: 0;
}
a { text-decoration: none; color: inherit; }

.nav-self-credit-overlay {
  position: fixed;
  inset: 0;
  z-index: 12000;
  background: rgba(0, 0, 0, 0.55);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
}
.nav-self-credit-dialog {
  width: min(420px, 100%);
  background: #141414;
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 12px;
  padding: 20px 22px 18px;
  box-shadow: 0 20px 50px rgba(0, 0, 0, 0.45);
}
.nav-self-credit-dialog__title {
  margin: 0 0 10px;
  font-size: 1.05rem;
  font-weight: 700;
  color: #fff;
}
.nav-self-credit-dialog__hint {
  margin: 0 0 16px;
  font-size: 0.82rem;
  line-height: 1.45;
  color: rgba(255, 255, 255, 0.5);
}
.nav-self-credit-dialog__label {
  display: block;
  margin: 10px 0 6px;
  font-size: 0.78rem;
  color: rgba(255, 255, 255, 0.55);
}
.nav-self-credit-dialog__input {
  width: 100%;
  padding: 8px 10px;
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  background: #0a0a0a;
  color: #fff;
  font-size: 0.95rem;
}
.nav-admin-unlock__code {
  font-family: 'JetBrains Mono', 'Menlo', 'Consolas', monospace;
  letter-spacing: 6px;
  text-align: center;
  text-transform: uppercase;
  font-size: 1.2rem;
}
.nav-admin-unlock__hint-warn {
  display: inline-block;
  margin-top: 8px;
  font-size: 0.78rem;
  color: rgba(251, 191, 36, 0.95);
  line-height: 1.4;
}
.nav-self-credit-dialog__hint code {
  background: rgba(255, 255, 255, 0.08);
  padding: 1px 6px;
  border-radius: 4px;
  font-size: 0.85em;
}
.nav-self-credit-dialog__err {
  margin: 10px 0 0;
  font-size: 0.82rem;
  color: #f87171;
}
.nav-self-credit-dialog__actions {
  display: flex;
  gap: 10px;
  margin-top: 18px;
  justify-content: flex-end;
  flex-wrap: wrap;
}
.nav-self-credit-dialog__primary,
.nav-self-credit-dialog__secondary {
  padding: 8px 16px;
  border-radius: 8px;
  font-size: 0.9rem;
  font-weight: 600;
  cursor: pointer;
  border: none;
}
.nav-self-credit-dialog__primary {
  background: linear-gradient(135deg, #4ade80, #22c55e);
  color: #0a0a0a;
}
.nav-self-credit-dialog__primary:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}
.nav-self-credit-dialog__secondary {
  background: rgba(255, 255, 255, 0.08);
  color: rgba(255, 255, 255, 0.85);
}

.main-content {
  /* 0% 伸缩基准：在 app-shell 列 flex 里可靠吃掉顶栏以下剩余高度 */
  flex: 1 1 0%;
  display: flex;
  flex-direction: column;
  width: 100%;
  /* 全宽铺底：避免 max-width + margin auto 在两侧露出 body 背景（扩展/窄视口「黑边」） */
  max-width: none;
  margin-inline: 0;
  padding: var(--page-pad-y) 0;
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

.main-content--with-sidebar {
  padding: 0;
}

/* 账户中心：纵向节奏；横向宽度交给 .account-page 自身 max-width */
.main-content--account {
  --page-pad-y: clamp(0.75rem, 2vw, 1.25rem);
}

/* 工作台首页 / 与窗口等高，禁页面级纵向滚轮，避免与右侧长条档杆冲突；内容在 .wb-gear-scene 内自行滚动 */
/* 已登录全局侧栏布局：与上相同，避免侧栏随主区内容被撑高（仅主内容区 .main-content--with-sidebar 滚动） */
html:has(.app-shell--wb-home),
html:has(.app-shell--viewport-locked),
body:has(.app-shell--wb-home),
body:has(.app-shell--viewport-locked) {
  height: 100%;
  max-height: 100%;
  overflow: hidden;
}
#app:has(.app-shell--wb-home),
#app:has(.app-shell--viewport-locked) {
  min-height: 0;
  max-height: 100dvh;
  height: 100dvh;
  overflow: hidden;
}
.app-shell--wb-home,
.app-shell--viewport-locked {
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
    --page-pad-y: 12px;
  }
  html {
    font-size: 16px;
  }
  .main-content {
    padding: var(--page-pad-y) 0;
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

.wb-sidebar {
  display: flex;
  flex-direction: column;
  flex: none;
  width: 240px;
  height: 100%;
  overflow: hidden;
  background: #121212;
  border-right: 1px solid rgba(240, 240, 245, 0.05);
  transition: width 200ms cubic-bezier(0.4, 0, 0.2, 1);
  box-sizing: border-box;
}

.wb-sidebar--collapsed {
  width: 56px;
}

.wb-sidebar--collapsed .wb-sidebar-new-chat span,
.wb-sidebar--collapsed .wb-sidebar-conv-title,
.wb-sidebar--collapsed .wb-sidebar-conv-time,
.wb-sidebar--collapsed .wb-sidebar-mode-btn span,
.wb-sidebar--collapsed .wb-sidebar-user-link,
.wb-sidebar--collapsed .wb-sidebar-level-badge,
.wb-sidebar--collapsed .wb-sidebar-balance,
.wb-sidebar--collapsed .wb-sidebar-conv-list {
  display: none;
}

.wb-sidebar--collapsed .wb-sidebar-new-chat {
  display: none;
}

.wb-sidebar--collapsed .wb-sidebar-mode-btn {
  justify-content: center;
  padding: 8px;
}

.wb-sidebar--collapsed .wb-sidebar-user-row {
  justify-content: center;
}

.wb-sidebar-top {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 12px 12px 8px;
  flex-shrink: 0;
}

.wb-sidebar-toggle {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: rgba(240, 240, 245, 0.45);
  cursor: pointer;
  padding: 0;
  flex-shrink: 0;
  transition: background 180ms ease, color 180ms ease;
}

.wb-sidebar-toggle:hover {
  background: rgba(129, 140, 248, 0.08);
  color: rgba(240, 240, 245, 0.85);
}

.wb-sidebar-new-chat {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
  padding: 8px 12px;
  border: none;
  border-radius: 10px;
  background: transparent;
  color: rgba(240, 240, 245, 0.55);
  font-size: 13px;
  font-weight: 400;
  cursor: pointer;
  transition: background 180ms ease, color 180ms ease;
}

.wb-sidebar-new-chat:hover {
  background: rgba(129, 140, 248, 0.08);
  color: rgba(240, 240, 245, 0.9);
}

.wb-sidebar-conv-list {
  flex: 1 1 0%;
  min-height: 0;
  overflow-y: auto;
  padding: 4px 8px;
  scrollbar-width: thin;
  scrollbar-color: rgba(129, 140, 248, 0.15) transparent;
  overscroll-behavior: contain;
}

.wb-sidebar-conv-item-wrap {
  position: relative;
  overflow: hidden;
  border-radius: 10px;
  margin-bottom: 2px;
}

.wb-sidebar-conv-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  border-radius: 10px;
  cursor: pointer;
  transition: background 180ms ease, transform 200ms cubic-bezier(0.22, 1, 0.36, 1);
  position: relative;
  z-index: 1;
  background: #08080c;
}

.wb-sidebar-conv-item:hover {
  background: rgba(129, 140, 248, 0.06);
}

.wb-sidebar-conv-item--active {
  background: #212121;
}

.wb-sidebar-conv-title {
  font-size: 13px;
  color: rgba(240, 240, 245, 0.85);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  flex: 1;
  margin-right: 8px;
}

.wb-sidebar-conv-time {
  font-size: 11px;
  color: rgba(240, 240, 245, 0.3);
  white-space: nowrap;
  flex-shrink: 0;
}

.wb-sidebar-conv-delete {
  position: absolute;
  right: 0;
  top: 0;
  bottom: 0;
  width: 56px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  background: rgba(239, 68, 68, 0.85);
  color: #fff;
  cursor: pointer;
  z-index: 0;
  border-radius: 0 10px 10px 0;
  transition: opacity 150ms ease;
  opacity: 0;
  pointer-events: none;
}

.wb-sidebar-conv-delete:hover {
  background: rgba(239, 68, 68, 1);
}

.wb-sidebar-divider {
  height: 1px;
  background: rgba(240, 240, 245, 0.05);
  margin: 8px 12px;
  flex-shrink: 0;
}

.wb-sidebar-modes {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 4px 8px;
  flex-shrink: 0;
}

.wb-sidebar-mode-btn {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 12px;
  border: none;
  border-radius: 10px;
  background: transparent;
  color: rgba(240, 240, 245, 0.45);
  font-size: 13px;
  font-weight: 400;
  cursor: pointer;
  text-align: left;
  transition: background 180ms ease, color 180ms ease;
}

.wb-sidebar-mode-btn:hover {
  background: rgba(129, 140, 248, 0.06);
  color: rgba(240, 240, 245, 0.8);
}

.wb-sidebar-mode-btn--active {
  background: rgba(129, 140, 248, 0.1);
  color: rgba(240, 240, 245, 0.95);
}

.wb-sidebar-mode-btn--cs span {
  color: #c676bf;
}

.wb-sidebar-bottom {
  flex-shrink: 0;
  padding: 8px;
  border-top: 1px solid rgba(240, 240, 245, 0.05);
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.wb-sidebar-nav-links {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.wb-sidebar-nav-gradient {
  background: linear-gradient(135deg, #818cf8, #c084fc);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.wb-sidebar-user-row {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  border-radius: 10px;
  flex-wrap: wrap;
}

.wb-sidebar-user-link {
  font-size: 13px;
  font-weight: 600;
  color: rgba(240, 240, 245, 0.7);
  text-decoration: none;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 100px;
  transition: color 150ms ease;
}

.wb-sidebar-user-link:hover {
  color: rgba(240, 240, 245, 0.95);
}

.wb-sidebar-level-badge {
  display: inline-flex;
  align-items: center;
  height: 18px;
  padding: 0 6px;
  border-radius: 9px;
  background: rgba(129, 140, 248, 0.12);
  color: rgba(129, 140, 248, 0.9);
  font-size: 11px;
  font-weight: 600;
  text-decoration: none;
  white-space: nowrap;
  transition: background 150ms ease;
}

.wb-sidebar-level-badge:hover {
  background: rgba(129, 140, 248, 0.22);
}

.wb-sidebar-balance {
  font-size: 12px;
  color: rgba(240, 240, 245, 0.4);
  white-space: nowrap;
  margin-left: auto;
}

.wb-sidebar-balance--loading {
  animation: wb-sidebar-balance-pulse 1.5s ease-in-out infinite;
}

@keyframes wb-sidebar-balance-pulse {
  0%, 100% { opacity: 0.4; }
  50% { opacity: 0.8; }
}

.wb-sidebar-logout-btn {
  margin-left: auto;
  border: none;
  background: none;
  color: rgba(240, 240, 245, 0.3);
  font-size: 12px;
  cursor: pointer;
  padding: 2px 6px;
  border-radius: 4px;
  transition: color 150ms ease, background 150ms ease;
}

.wb-sidebar-logout-btn:hover {
  color: rgba(239, 68, 68, 0.85);
  background: rgba(239, 68, 68, 0.08);
}

.wb-sidebar-admin-nav {
  flex: 1 1 0%;
  min-height: 0;
  overflow-y: auto;
  padding: 4px 8px;
  scrollbar-width: thin;
  scrollbar-color: rgba(129, 140, 248, 0.15) transparent;
}

.wb-sidebar-admin-nav-title {
  font-size: 11px;
  font-weight: 600;
  color: rgba(129, 140, 248, 0.6);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  padding: 8px 12px 4px;
}

.wb-sidebar-back-btn {
  color: rgba(129, 140, 248, 0.7) !important;
}

.wb-sidebar-back-btn:hover {
  background: rgba(129, 140, 248, 0.1) !important;
  color: rgba(129, 140, 248, 0.95) !important;
}

.wb-sidebar-admin-label {
  flex: 1;
  font-size: 13px;
  font-weight: 600;
  color: rgba(129, 140, 248, 0.8);
  padding: 8px 12px;
}
</style>
