<template>
  <div class="account-page">
    <header class="account-hero">
      <div class="hero-avatar" aria-hidden="true">{{ avatarInitial }}</div>
      <div class="hero-main">
        <h1 class="page-title">账户中心</h1>
        <p class="hero-sub">
          <span class="hero-name">{{ displayUsername }}</span>
          <span v-if="email" class="hero-email">{{ email }}</span>
        </p>
        <div class="hero-badges">
          <span v-if="level" class="badge badge-lv" title="账号成长等级"
            >Lv.{{ level.level }} · {{ level.title || '成长等级' }}</span
          >
          <span
            :class="['badge', 'badge-tier', membershipTier ? `badge-tier--${membershipTier}` : 'badge-tier--free']"
            :title="membershipLabel"
            >{{ membershipLabel }}</span
          >
        </div>
      </div>
    </header>

    <div v-if="msg" class="flash flash-ok">{{ msg }}</div>
    <div v-if="err" class="flash flash-err">{{ err }}</div>

    <div class="stats-row" v-if="level">
      <div class="stat-card">
        <div class="stat-label">账号等级</div>
        <div class="stat-value">Lv.{{ level.level }}</div>
        <div class="stat-foot">{{ level.title || '—' }}</div>
      </div>
      <div class="stat-card stat-card--vip">
        <div class="stat-label">会员身份</div>
        <div
          :class="['stat-value', 'stat-value--tier', membershipTier ? `stat-value--${membershipTier}` : 'stat-value--free']"
        >
          {{ membershipLabel }}
        </div>
        <div class="stat-foot">{{ membershipHint }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">累计经验</div>
        <div class="stat-value stat-value--num">{{ level.experience.toLocaleString() }}</div>
        <div class="stat-foot">实付 1 元 = 100 经验（含商品 / 会员 / 钱包充值）</div>
      </div>
    </div>

    <div class="account-grid">
      <section v-if="level" class="card card-level">
        <h3 class="card-title">等级进度</h3>
        <div class="level-head level-head--inline">
          <div class="level-badge">Lv.{{ level.level }}</div>
          <div class="level-meta">
            <div class="level-title">{{ level.title || '账号等级' }}</div>
            <div class="level-sub">累计经验 {{ level.experience.toLocaleString() }}</div>
          </div>
        </div>
        <div class="level-progress">
          <div class="progress-track">
            <div class="progress-fill" :style="{ width: progressPercent + '%' }"></div>
          </div>
          <div class="progress-meta">
            <span v-if="level.nextLevelMinExp !== null">
              距 Lv.{{ level.level + 1 }} 还需
              <strong>{{ Math.max(0, level.nextLevelMinExp - level.experience).toLocaleString() }}</strong>
              经验
            </span>
            <span v-else>已达成最高等级</span>
            <span class="progress-pct">{{ progressPercent }}%</span>
          </div>
        </div>
        <p class="level-hint">
          每实付 1 元 = 100 经验（商品 / 会员 / 钱包充值都计入），退款成功会扣回相应经验。
        </p>
      </section>

      <section class="card card-spotlight">
        <h3 class="card-title">会员与权益</h3>
        <p class="spotlight-lead">
          当前身份：
          <strong :class="['spotlight-tier', membershipTier ? `spotlight-tier--${membershipTier}` : '']">{{
            membershipLabel
          }}</strong>
        </p>
        <p class="spotlight-desc">{{ membershipHint }}</p>
        <div class="spotlight-actions">
          <RouterLink to="/plans" class="btn btn-primary">查看与购买套餐</RouterLink>
          <RouterLink to="/wallet" class="btn btn-ghost">钱包与流水</RouterLink>
        </div>
      </section>
    </div>

    <nav class="quick-nav" aria-label="快捷入口">
      <RouterLink to="/wallet" class="quick-link">钱包</RouterLink>
      <RouterLink :to="{ name: 'wallet-purchased' }" class="quick-link">已购</RouterLink>
      <RouterLink to="/notifications" class="quick-link">通知中心</RouterLink>
      <RouterLink to="/plans" class="quick-link">会员购买</RouterLink>
    </nav>

    <div class="forms-grid">
      <section class="card">
        <h3 class="card-title">基本信息</h3>
        <div class="form-group">
          <label>用户名</label>
          <input v-model="username" class="input" :disabled="saving" />
        </div>
        <div class="form-group">
          <label>邮箱</label>
          <input :value="email" class="input" type="email" disabled />
          <span class="hint">邮箱修改请联系管理员</span>
        </div>
        <button type="button" class="btn btn-primary" :disabled="saving" @click="saveProfile">保存</button>
      </section>

      <section class="card">
        <h3 class="card-title">修改密码</h3>
        <div class="form-group">
          <label>当前密码</label>
          <input v-model="pw.current" type="password" class="input" autocomplete="current-password" />
        </div>
        <div class="form-group">
          <label>新密码</label>
          <input v-model="pw.new1" type="password" class="input" autocomplete="new-password" />
        </div>
        <div class="form-group">
          <label>确认新密码</label>
          <input v-model="pw.new2" type="password" class="input" autocomplete="new-password" />
        </div>
        <button type="button" class="btn btn-primary" :disabled="!canChangePw || savingPw" @click="changePw">
          {{ savingPw ? '提交中…' : '修改密码' }}
        </button>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { storeToRefs } from 'pinia'
import { api } from '../api'
import { normalizeMeResponse } from '../domain/accountLevel'
import { useAuthStore } from '../stores/auth'

const authStore = useAuthStore()
const { levelProfile, membership, membershipTier, username: storeUsername } = storeToRefs(authStore)

const username = ref('')
const email = ref('')
const saving = ref(false)
const savingPw = ref(false)
const msg = ref('')
const err = ref('')
const pw = ref({ current: '', new1: '', new2: '' })

const canChangePw = computed(
  () =>
    pw.value.current.length > 0 &&
    pw.value.new1.length >= 6 &&
    pw.value.new1 === pw.value.new2,
)

const level = computed(() => levelProfile.value)
const progressPercent = computed(() => Math.round(((level.value?.progress ?? 0) as number) * 100))

const displayUsername = computed(() => (username.value || storeUsername.value || '用户').trim() || '用户')
const avatarInitial = computed(() => {
  const s = displayUsername.value.trim()
  if (!s) return '?'
  return s.slice(0, 1).toUpperCase()
})

const membershipLabel = computed(() => {
  const m = membership.value
  if (m?.label) return String(m.label)
  if (m?.tier && m.tier !== 'free') return String(m.tier)
  return '普通用户'
})

const membershipHint = computed(() => {
  const t = (membershipTier.value || 'free').toLowerCase()
  if (t === 'free' || !membership.value?.is_member) {
    return '未开通会员。升级可享受更高 AI 额度、BYOK、会员标识等权益。'
  }
  if (t === 'vip' || t === 'vip_plus') {
    return '你正在使用付费会员能力，可在「会员购买」中继续升级。'
  }
  if (t.startsWith('svip')) {
    return '你正在使用 SVIP 系列权益。可在套餐页按档升级。'
  }
  return '感谢支持，更多权益可在「会员购买」中查看。'
})

onMounted(async () => {
  try {
    const me = normalizeMeResponse(await api.me())
    username.value = me.username || ''
    email.value = me.email || ''
    await authStore.refreshSession(true)
    await authStore.refreshMembership()
  } catch (e: any) {
    err.value = e?.message || '加载失败'
  }
})

async function saveProfile() {
  msg.value = ''
  err.value = ''
  saving.value = true
  try {
    await api.updateProfile(username.value.trim())
    msg.value = '已保存'
    await authStore.refreshSession(true)
  } catch (e: any) {
    err.value = e?.message || '保存失败'
  } finally {
    saving.value = false
  }
}

async function changePw() {
  msg.value = ''
  err.value = ''
  savingPw.value = true
  try {
    await api.changePassword(pw.value.current, pw.value.new1)
    msg.value = '密码已更新'
    pw.value = { current: '', new1: '', new2: '' }
  } catch (e: any) {
    err.value = e?.message || '修改失败'
  } finally {
    savingPw.value = false
  }
}
</script>

<style scoped>
.account-page {
  max-width: 960px;
  margin: 0 auto;
  padding: clamp(3rem, 8vw, 5rem) 24px 3rem;
  color: #fff;
}

/* ---- Hero ---- */
.account-hero {
  display: flex;
  align-items: flex-start;
  gap: 1.25rem;
  margin-bottom: 1.75rem;
  padding-bottom: 1.5rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}
.hero-avatar {
  flex-shrink: 0;
  width: 4.5rem;
  height: 4.5rem;
  border-radius: 1rem;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.75rem;
  font-weight: 700;
  background: linear-gradient(145deg, rgba(99, 102, 241, 0.45), rgba(14, 165, 233, 0.25));
  border: 1px solid rgba(99, 102, 241, 0.45);
  box-shadow: 0 8px 28px rgba(0, 0, 0, 0.35);
}
.hero-main {
  min-width: 0;
  flex: 1;
}
.page-title {
  margin: 0 0 0.35rem;
  font-size: clamp(1.5rem, 2.5vw, 1.85rem);
  font-weight: 700;
  letter-spacing: -0.02em;
}
.hero-sub {
  margin: 0 0 0.75rem;
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 0.5rem 1rem;
  font-size: 0.9rem;
  color: rgba(255, 255, 255, 0.65);
}
.hero-name {
  color: #fff;
  font-weight: 600;
  font-size: 1rem;
}
.hero-email {
  font-size: 0.85rem;
  color: rgba(255, 255, 255, 0.5);
  word-break: break-all;
}
.hero-badges {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}
.badge {
  display: inline-flex;
  align-items: center;
  padding: 0.35rem 0.7rem;
  border-radius: 999px;
  font-size: 0.8rem;
  font-weight: 600;
  border: 1px solid rgba(255, 255, 255, 0.12);
  background: rgba(255, 255, 255, 0.06);
}
.badge-lv {
  background: rgba(99, 102, 241, 0.2);
  border-color: rgba(99, 102, 241, 0.35);
  color: #c7d2fe;
}
.badge-tier {
  border-width: 1px;
}
.badge-tier--free {
  color: rgba(255, 255, 255, 0.75);
}
.badge-tier--vip {
  color: #67e8f9;
  border-color: rgba(103, 232, 249, 0.45);
  box-shadow: 0 0 12px rgba(103, 232, 249, 0.15);
}
.badge-tier--vip_plus {
  color: #fde047;
  border-color: rgba(253, 224, 71, 0.45);
  box-shadow: 0 0 12px rgba(253, 224, 71, 0.2);
}
.badge-tier--svip1 { color: #c084fc; border-color: rgba(192, 132, 252, 0.4); }
.badge-tier--svip2 { color: #f472b6; border-color: rgba(244, 114, 182, 0.4); }
.badge-tier--svip3 { color: #34d399; border-color: rgba(52, 211, 153, 0.4); }
.badge-tier--svip4 { color: #fb923c; border-color: rgba(251, 146, 60, 0.45); }
.badge-tier--svip5 { color: #fb7185; border-color: rgba(251, 113, 133, 0.45); }
.badge-tier--svip6 { color: #818cf8; border-color: rgba(129, 140, 248, 0.45); }
.badge-tier--svip7 { color: #fbbf24; border-color: rgba(251, 191, 36, 0.5); }
.badge-tier--svip8 {
  color: #fff;
  border: none;
  background: linear-gradient(120deg, #f472b6, #fbbf24, #34d399, #38bdf8, #a78bfa);
  background-clip: padding-box;
  box-shadow: 0 0 16px rgba(248, 113, 113, 0.25);
}

/* ---- Stats ---- */
.stats-row {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 0.75rem;
  margin-bottom: 1.5rem;
}
@media (max-width: 720px) {
  .stats-row {
    grid-template-columns: 1fr;
  }
}
.stat-card {
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 12px;
  padding: 1rem 1.1rem;
  min-width: 0;
}
.stat-card--vip {
  background: linear-gradient(145deg, rgba(99, 102, 241, 0.12), rgba(8, 145, 178, 0.08));
  border-color: rgba(99, 102, 241, 0.2);
}
.stat-label {
  font-size: 0.72rem;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: rgba(255, 255, 255, 0.5);
  margin-bottom: 0.35rem;
}
.stat-value {
  font-size: 1.25rem;
  font-weight: 700;
  line-height: 1.2;
  word-break: break-word;
}
.stat-value--num {
  font-variant-numeric: tabular-nums;
  background: linear-gradient(90deg, #e0e7ff, #a5b4fc);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}
.stat-value--tier {
  font-size: 1.1rem;
}
.stat-value--free { color: rgba(255, 255, 255, 0.8); }
.stat-value--vip { color: #67e8f9; text-shadow: 0 0 8px rgba(103, 232, 249, 0.25); }
.stat-value--vip_plus { color: #fde047; text-shadow: 0 0 8px rgba(253, 224, 71, 0.25); }
.stat-value--svip1 { color: #c084fc; }
.stat-value--svip2 { color: #f472b6; }
.stat-value--svip3 { color: #34d399; }
.stat-value--svip4 { color: #fb923c; }
.stat-value--svip5 { color: #fb7185; }
.stat-value--svip6 { color: #818cf8; }
.stat-value--svip7 { color: #fbbf24; }
.stat-value--svip8 {
  background: linear-gradient(90deg, #f87171, #fbbf24, #34d399, #38bdf8, #a78bfa);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}
.stat-foot {
  margin-top: 0.4rem;
  font-size: 0.75rem;
  color: rgba(255, 255, 255, 0.45);
  line-height: 1.4;
}

/* ---- Grid: level + membership ---- */
.account-grid {
  display: grid;
  grid-template-columns: 1.15fr 1fr;
  gap: 1rem;
  margin-bottom: 1.5rem;
}
@media (max-width: 800px) {
  .account-grid {
    grid-template-columns: 1fr;
  }
}

.card {
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 12px;
  padding: 1.25rem;
}
.card-title {
  margin: 0 0 1rem;
  font-size: 1.05rem;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.92);
}
.card-level {
  background: linear-gradient(160deg, rgba(99, 102, 241, 0.12), rgba(8, 145, 178, 0.06));
  border-color: rgba(99, 102, 241, 0.2);
}
.level-head--inline {
  margin-bottom: 0.9rem;
}
.card-spotlight {
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.05), rgba(0, 0, 0, 0.12));
  border-color: rgba(255, 255, 255, 0.1);
  display: flex;
  flex-direction: column;
  justify-content: space-between;
}
.spotlight-lead {
  margin: 0 0 0.5rem;
  font-size: 0.95rem;
  color: rgba(255, 255, 255, 0.85);
}
.spotlight-tier {
  font-weight: 700;
  font-size: 1.1rem;
}
.spotlight-tier--free { color: rgba(255, 255, 255, 0.8); }
.spotlight-tier--vip { color: #67e8f9; }
.spotlight-tier--vip_plus { color: #fde047; }
.spotlight-tier--svip1 { color: #c084fc; }
.spotlight-tier--svip2 { color: #f472b6; }
.spotlight-tier--svip3 { color: #34d399; }
.spotlight-tier--svip4 { color: #fb923c; }
.spotlight-tier--svip5 { color: #fb7185; }
.spotlight-tier--svip6 { color: #818cf8; }
.spotlight-tier--svip7 { color: #fbbf24; }
.spotlight-tier--svip8 {
  background: linear-gradient(90deg, #f472b6, #fbbf24, #60a5fa, #a78bfa, #c084fc);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}
.spotlight-desc {
  margin: 0 0 1.1rem;
  font-size: 0.85rem;
  line-height: 1.55;
  color: rgba(255, 255, 255, 0.55);
  flex: 1;
}
.spotlight-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.6rem;
}

/* ---- Quick nav ---- */
.quick-nav {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-bottom: 1.5rem;
  padding: 0.2rem 0;
}
.quick-link {
  display: inline-flex;
  align-items: center;
  padding: 0.45rem 0.85rem;
  border-radius: 8px;
  font-size: 0.88rem;
  color: rgba(255, 255, 255, 0.85);
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.1);
  text-decoration: none;
  transition: background 0.2s, border-color 0.2s;
}
.quick-link:hover {
  background: rgba(99, 102, 241, 0.2);
  border-color: rgba(99, 102, 241, 0.35);
}

/* ---- Forms ---- */
.forms-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 1rem;
  align-items: start;
}
@media (max-width: 720px) {
  .forms-grid {
    grid-template-columns: 1fr;
  }
}

.form-group {
  margin-bottom: 1rem;
}
.form-group label {
  display: block;
  margin-bottom: 0.35rem;
  font-size: 0.85rem;
  color: rgba(255, 255, 255, 0.65);
}
.input {
  width: 100%;
  padding: 0.6rem 0.75rem;
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.15);
  background: #0a0a0a;
  color: #fff;
  box-sizing: border-box;
}
.hint {
  display: block;
  font-size: 0.75rem;
  color: rgba(255, 255, 255, 0.45);
  margin-top: 0.25rem;
}
.btn {
  padding: 0.55rem 1.25rem;
  border-radius: 8px;
  border: none;
  background: #6366f1;
  color: #fff;
  font-weight: 600;
  cursor: pointer;
  text-decoration: none;
  display: inline-block;
  text-align: center;
  font-size: 0.9rem;
  box-sizing: border-box;
}
.btn-ghost {
  background: transparent;
  border: 1px solid rgba(255, 255, 255, 0.2);
  color: rgba(255, 255, 255, 0.9);
}
.btn-ghost:hover {
  border-color: rgba(99, 102, 241, 0.5);
  color: #c7d2fe;
}
.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.flash {
  padding: 0.65rem 0.85rem;
  border-radius: 8px;
  margin-bottom: 0.75rem;
  font-size: 0.9rem;
}
.flash-ok {
  background: rgba(34, 197, 94, 0.15);
  color: #86efac;
}
.flash-err {
  background: rgba(239, 68, 68, 0.15);
  color: #fca5a5;
}

/* Level card body (reused) */
.level-head {
  display: flex;
  align-items: center;
  gap: 14px;
}
.level-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 48px;
  height: 48px;
  padding: 0 10px;
  border-radius: 12px;
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
  color: #fff;
  font-weight: 700;
  font-size: 1rem;
  box-shadow: 0 6px 18px rgba(99, 102, 241, 0.35);
}
.level-meta {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.level-title {
  font-size: 0.95rem;
  font-weight: 600;
}
.level-sub {
  font-size: 0.8rem;
  color: rgba(255, 255, 255, 0.65);
}
.level-progress {
  margin-bottom: 0.6rem;
}
.progress-track {
  width: 100%;
  height: 8px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.08);
  overflow: hidden;
}
.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #6366f1, #38bdf8);
  border-radius: inherit;
  transition: width 0.4s ease;
}
.progress-meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 0.45rem;
  font-size: 0.8rem;
  color: rgba(255, 255, 255, 0.7);
}
.progress-meta strong {
  color: #fff;
  font-weight: 600;
}
.progress-pct {
  font-variant-numeric: tabular-nums;
  color: rgba(255, 255, 255, 0.55);
}
.level-hint {
  margin: 0;
  font-size: 0.75rem;
  color: rgba(255, 255, 255, 0.45);
}
</style>
