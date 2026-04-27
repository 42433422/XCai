<template>
  <div class="checkout-page">
    <div class="checkout-container">
      <h1 class="checkout-title">支付订单</h1>

      <div v-if="loading" class="loading">
        <div class="spinner"></div>
        <p>加载订单信息...</p>
      </div>

      <div v-if="error" class="error-section">
        <div class="error-icon">!</div>
        <h2 class="error-title">加载失败</h2>
        <p class="error-desc">{{ error }}</p>
        <router-link to="/plans" class="btn btn-primary">返回套餐页</router-link>
      </div>

      <template v-else-if="order">
        <!-- 订单信息 -->
        <div class="order-info">
          <div class="order-field">
            <span class="label">订单号</span>
            <span class="value">{{ order.out_trade_no }}</span>
          </div>
          <div class="order-field">
            <span class="label">商品</span>
            <span class="value">{{ order.subject }}</span>
          </div>
          <div class="order-field">
            <span class="label">金额</span>
            <span class="value price">¥{{ order.total_amount }}</span>
          </div>
          <div class="order-field">
            <span class="label">状态</span>
            <span :class="['value', 'status', `status-${order.status}`]">
              {{ statusText(order.status) }}
            </span>
          </div>
        </div>

        <!-- 二维码展示（precreate 模式） -->
        <div v-if="qrCode && order.status === 'pending'" class="qr-section">
          <p class="qr-hint">打开支付宝扫码支付</p>
          <div class="qr-wrapper">
            <img
              v-if="qrImageUrl"
              class="qr-img"
              :src="qrImageUrl"
              width="280"
              height="280"
              alt="支付宝支付二维码"
            />
          </div>
          <p v-if="isExpired" class="qr-expired-hint">
            订单已超时未支付。
            <button type="button" class="btn-retry" @click="retryPayment">重新支付</button>
            <router-link to="/plans" class="link-muted">或返回套餐页</router-link>
          </p>
          <p v-else class="qr-waiting">等待支付中，支付成功后自动跳转...</p>
        </div>

        <!-- 已支付成功 -->
        <div v-if="order.status === 'paid'" class="success-section">
          <div class="success-icon">✓</div>
          <h2 class="success-title">支付成功</h2>
          <p class="success-desc">资金已进入钱包账本，订单消费与权益发放已完成。</p>
          <div class="success-actions">
            <router-link to="/wallet" class="btn btn-primary">查看钱包资金账户</router-link>
            <router-link :to="{ name: 'wallet-purchased' }" class="btn btn-ghost">已购资产</router-link>
            <router-link to="/plans" class="btn btn-ghost">继续选购</router-link>
          </div>
          <p class="refund-hint">
            如需退款，可
            <router-link
              :to="{ name: 'refunds', query: { order_no: order.out_trade_no } }"
              class="refund-link"
            >
              提交退款申请
            </router-link>
            ，处理进度会显示在钱包资金账户中。
          </p>
        </div>

        <!-- 支付失败 -->
        <div v-if="order.status === 'failed'" class="failed-section">
          <p>支付失败</p>
          <router-link to="/plans" class="btn btn-primary">重新下单</router-link>
        </div>

        <!-- 已关闭 -->
        <div v-if="order.status === 'closed'" class="closed-section">
          <p>订单已关闭</p>
          <button type="button" class="btn btn-primary" @click="retryPayment">重新支付</button>
          <router-link to="/plans" class="btn btn-ghost">返回套餐页</router-link>
        </div>
      </template>

      <div v-else class="not-found">
        <p>订单不存在</p>
        <router-link to="/plans" class="btn btn-ghost">返回套餐页</router-link>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '../api'
import { useAuthStore } from '../stores/auth'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const order = ref(null)
const loading = ref(true)
const error = ref('')
const qrCode = ref('')
const pollingTimer = ref(null)
const pollCount = ref(0)

const qrImageUrl = computed(() => {
  if (!qrCode.value) return ''
  return `https://api.qrserver.com/v1/create-qr-code/?size=280x280&margin=8&data=${encodeURIComponent(qrCode.value)}`
})

const isExpired = computed(() => {
  if (!order.value || order.value.status !== 'pending') return false
  const created = new Date(order.value.created_at).getTime()
  const now = Date.now()
  return (now - created) > 15 * 60 * 1000
})

onMounted(async () => {
  await fetchOrder()
  if (order.value && order.value.status === 'pending' && !isExpired.value) {
    pollingTimer.value = setInterval(pollOrder, 3000)
  }
})

onBeforeUnmount(() => {
  if (pollingTimer.value) {
    clearInterval(pollingTimer.value)
  }
})

async function fetchOrder() {
  try {
    error.value = ''
    const res = await api.paymentQuery(route.params.orderId, { reconcile: true })
    order.value = res

    if (res.qr_code) {
      qrCode.value = String(res.qr_code)
    }

    if (res.status === 'paid') {
      void authStore.refreshSession(true)
      if (String(res.plan_id || '').trim() === 'plan_enterprise') {
        try {
          sessionStorage.setItem('modstore_svip_ladder_reveal', '1')
        } catch {
          /* ignore */
        }
      }
    }
    if (res.status === 'paid' && pollingTimer.value) {
      clearInterval(pollingTimer.value)
      pollingTimer.value = null
    }
  } catch (err) {
    error.value = err.message || '加载订单信息失败，请重试'
    order.value = null
  } finally {
    loading.value = false
  }
}

async function pollOrder() {
  try {
    pollCount.value += 1
    // 每 2 次轮询带一次对账，减轻支付宝侧查询压力
    const res = await api.paymentQuery(route.params.orderId, {
      reconcile: pollCount.value % 2 === 0,
    })
    order.value = res
    if (res.qr_code) qrCode.value = String(res.qr_code)

    if (res.status === 'paid') {
      void authStore.refreshSession(true)
      if (String(res.plan_id || '').trim() === 'plan_enterprise') {
        try {
          sessionStorage.setItem('modstore_svip_ladder_reveal', '1')
        } catch {
          /* ignore */
        }
      }
    }
    if (res.status === 'paid' && pollingTimer.value) {
      clearInterval(pollingTimer.value)
      pollingTimer.value = null
    }
  } catch (err) {
    //  polling errors，不显示错误，避免干扰用户
    console.error('Polling error:', err)
  }
}

function statusText(status) {
  const map = {
    pending: '待支付',
    paid: '已支付',
    failed: '支付失败',
    closed: '已关闭',
  }
  return map[status] || status || '未知'
}

async function retryPayment() {
  const o = order.value
  if (!o) return
  if (pollingTimer.value) {
    clearInterval(pollingTimer.value)
    pollingTimer.value = null
  }
  try {
    if ((o.status === 'pending' || o.status === 'closed') && o.out_trade_no) {
      try {
        await api.paymentCancelOrder(o.out_trade_no)
      } catch {
        /* 非待支付等情况下取消会失败，忽略 */
      }
    }
  } catch {
    /* ignore */
  }

  loading.value = true
  error.value = ''
  try {
    const kind = String(o.order_kind || '').toLowerCase()
    const itemId = Number(o.item_id || 0) || 0
    const planId = String(o.plan_id || '').trim()
    const walletRecharge = kind === 'wallet'
    const payload: Record<string, unknown> = {
      plan_id: planId,
      item_id: itemId,
      subject: o.subject || '',
      wallet_recharge: walletRecharge,
    }
    if (walletRecharge) {
      const ta = Number.parseFloat(String(o.total_amount ?? '0'))
      if (ta > 0) payload.total_amount = ta
    }
    const checkout = await api.paymentCheckout(payload)
    if (!checkout.ok) {
      error.value = checkout.message || '重新下单失败'
      return
    }
    if ((checkout.type === 'precreate' || checkout.type === 'wechat_native') && checkout.order_id) {
      await router.replace({ name: 'checkout', params: { orderId: checkout.order_id } })
      order.value = null
      qrCode.value = ''
      await fetchOrder()
      if (order.value && order.value.status === 'pending' && !isExpired.value) {
        pollingTimer.value = setInterval(pollOrder, 3000)
      }
    } else if (checkout.type === 'page' || checkout.type === 'wap') {
      window.location.href = checkout.redirect_url
    } else {
      error.value = '不支持的支付类型'
    }
  } catch (e) {
    error.value = e.message || '重新支付失败'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.checkout-page {
  min-height: 100vh;
  background: #0a0a0a;
  color: #ffffff;
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
  display: flex;
  justify-content: center;
  padding-top: 80px;
}

.checkout-container {
  width: 100%;
  max-width: 480px;
  padding: 0 24px;
}

.checkout-title {
  font-size: 24px;
  font-weight: 600;
  text-align: center;
  margin: 0 0 32px;
  letter-spacing: -0.02em;
}

.loading, .not-found {
  text-align: center;
  padding: 48px 0;
  color: rgba(255, 255, 255, 0.5);
}

.order-info {
  padding: 24px;
  border: 0.5px solid rgba(255, 255, 255, 0.1);
  border-radius: 12px;
  margin-bottom: 24px;
}

.order-field {
  display: flex;
  justify-content: space-between;
  padding: 12px 0;
  border-bottom: 0.5px solid rgba(255, 255, 255, 0.06);
  font-size: 14px;
}

.order-field:last-child {
  border-bottom: none;
}

.order-field .label {
  color: rgba(255, 255, 255, 0.5);
}

.order-field .value {
  font-weight: 500;
  text-align: right;
  max-width: 60%;
  word-break: break-all;
}

.order-field .value.price {
  font-size: 18px;
  font-weight: 600;
}

.status-pending {
  color: #f0a030;
}

.status-paid {
  color: #4ade80;
}

.status-failed {
  color: #ff6b6b;
}

.status-closed {
  color: rgba(255, 255, 255, 0.4);
}

.qr-section {
  text-align: center;
  padding: 24px;
  border: 0.5px solid rgba(255, 255, 255, 0.1);
  border-radius: 12px;
  margin-bottom: 24px;
}

.qr-hint {
  font-size: 14px;
  color: rgba(255, 255, 255, 0.5);
  margin: 0 0 16px;
}

.qr-wrapper {
  display: inline-block;
  background: #ffffff;
  padding: 16px;
  border-radius: 12px;
}

.qr-img {
  display: block;
  width: 280px;
  height: 280px;
  max-width: 100%;
}

.qr-expired-hint {
  margin-top: 12px;
  font-size: 13px;
  color: #ff6b6b;
}

.qr-expired-hint a,
.qr-expired-hint .link-muted {
  color: rgba(255, 255, 255, 0.75);
  margin-left: 8px;
}

.btn-retry {
  margin-right: 8px;
  padding: 6px 14px;
  border-radius: 6px;
  border: 1px solid rgba(255, 255, 255, 0.25);
  background: rgba(255, 255, 255, 0.08);
  color: #fff;
  font-size: 13px;
  cursor: pointer;
}

.btn-retry:hover {
  background: rgba(255, 255, 255, 0.14);
}

.closed-section .btn-primary {
  margin-right: 8px;
}

.qr-waiting {
  margin-top: 12px;
  font-size: 13px;
  color: rgba(255, 255, 255, 0.4);
}

.success-section {
  text-align: center;
  padding: 48px 24px;
}

.success-icon {
  width: 64px;
  height: 64px;
  line-height: 64px;
  border-radius: 50%;
  background: rgba(74, 222, 128, 0.1);
  border: 1px solid rgba(74, 222, 128, 0.3);
  font-size: 28px;
  color: #4ade80;
  margin: 0 auto 24px;
}

.success-title {
  font-size: 20px;
  font-weight: 600;
  margin: 0 0 8px;
}

.success-desc {
  font-size: 14px;
  color: rgba(255, 255, 255, 0.5);
  margin: 0 0 24px;
}

.success-actions {
  display: flex;
  gap: 12px;
  justify-content: center;
  flex-wrap: wrap;
}

.refund-hint {
  margin-top: 16px;
  color: rgba(255, 255, 255, 0.5);
  font-size: 13px;
}

.refund-link {
  color: #c7d2fe;
  text-decoration: none;
}

.refund-link:hover {
  color: #ffffff;
}

.failed-section, .closed-section {
  text-align: center;
  padding: 48px 24px;
}

.failed-section p, .closed-section p {
  font-size: 16px;
  color: #ff6b6b;
  margin: 0 0 24px;
}

.closed-section p {
  color: rgba(255, 255, 255, 0.5);
}

.error-section {
  text-align: center;
  padding: 48px 24px;
}

.error-icon {
  width: 64px;
  height: 64px;
  line-height: 64px;
  border-radius: 50%;
  background: rgba(255, 107, 107, 0.1);
  border: 1px solid rgba(255, 107, 107, 0.3);
  font-size: 28px;
  color: #ff6b6b;
  margin: 0 auto 24px;
}

.error-title {
  font-size: 20px;
  font-weight: 600;
  margin: 0 0 8px;
  color: #ff6b6b;
}

.error-desc {
  font-size: 14px;
  color: rgba(255, 255, 255, 0.75);
  margin: 0 auto 24px;
  max-width: 100%;
  text-align: left;
  line-height: 1.55;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  word-break: break-word;
}

.btn {
  display: inline-block;
  padding: 12px 24px;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 500;
  text-decoration: none;
  cursor: pointer;
  transition: all 0.2s ease-out;
  border: none;
}

.btn-primary {
  background: #ffffff;
  color: #0a0a0a;
}

.btn-primary:hover {
  opacity: 0.9;
}

.btn-ghost {
  background: transparent;
  color: rgba(255, 255, 255, 0.6);
}

.btn-ghost:hover {
  color: #ffffff;
}

.spinner {
  width: 32px;
  height: 32px;
  border: 2px solid rgba(255, 255, 255, 0.1);
  border-top-color: #ffffff;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  margin: 0 auto 12px;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

@media (max-width: 768px) {
  .checkout-page {
    padding-top: 24px;
    align-items: flex-start;
  }
  .checkout-container {
    padding: 0 12px;
  }
  .order-info {
    padding: 18px;
  }
  .order-field {
    align-items: flex-start;
    gap: 12px;
  }
  .order-field .value {
    max-width: 58vw;
    word-break: break-all;
  }
  .qr-img {
    width: min(280px, calc(100vw - 72px));
    height: min(280px, calc(100vw - 72px));
  }
  .success-actions,
  .closed-section {
    flex-direction: column;
  }
  .success-actions .btn,
  .closed-section .btn {
    width: 100%;
  }
}
</style>
