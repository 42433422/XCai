<template>
  <div class="checkout-page">
    <div class="checkout-container">
      <h1 class="checkout-title">支付订单</h1>

      <div v-if="loading" class="loading">
        <div class="spinner"></div>
        <p>加载订单信息...</p>
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
            <canvas ref="qrCanvas" width="256" height="256"></canvas>
          </div>
          <p v-if="isExpired" class="qr-expired-hint">
            订单已超时未支付，<router-link to="/plans">重新下单</router-link>
          </p>
          <p v-else class="qr-waiting">等待支付中，支付成功后自动跳转...</p>
        </div>

        <!-- 已支付成功 -->
        <div v-if="order.status === 'paid'" class="success-section">
          <div class="success-icon">✓</div>
          <h2 class="success-title">支付成功</h2>
          <p class="success-desc">权益已发放，请前往"我的商店"查看</p>
          <div class="success-actions">
            <router-link to="/my-store" class="btn btn-primary">查看我的商店</router-link>
            <router-link to="/plans" class="btn btn-ghost">继续选购</router-link>
          </div>
        </div>

        <!-- 支付失败 -->
        <div v-if="order.status === 'failed'" class="failed-section">
          <p>支付失败</p>
          <router-link to="/plans" class="btn btn-primary">重新下单</router-link>
        </div>

        <!-- 已关闭 -->
        <div v-if="order.status === 'closed'" class="closed-section">
          <p>订单已关闭</p>
          <router-link to="/plans" class="btn btn-primary">返回套餐页</router-link>
        </div>
      </template>

      <div v-else class="not-found">
        <p>订单不存在</p>
        <router-link to="/plans" class="btn btn-ghost">返回套餐页</router-link>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import { api } from '../api.js'

const route = useRoute()
const order = ref(null)
const loading = ref(true)
const qrCode = ref('')
const qrCanvas = ref(null)
const pollingTimer = ref(null)

const isExpired = computed(() => {
  if (!order.value || order.value.status !== 'pending') return false
  const created = new Date(order.value.created_at).getTime()
  const now = Date.now()
  return (now - created) > 15 * 60 * 1000
})

onMounted(async () => {
  await fetchOrder()
  renderQR()
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
    const res = await api.paymentQuery(route.params.orderId)
    order.value = res

    if (res.qr_code) {
      qrCode.value = res.qr_code
    }

    if (res.status === 'paid' && pollingTimer.value) {
      clearInterval(pollingTimer.value)
      pollingTimer.value = null
    }
  } catch {
    order.value = null
  } finally {
    loading.value = false
  }
}

async function pollOrder() {
  try {
    const res = await api.paymentQuery(route.params.orderId)
    order.value = res

    if (res.status === 'paid' && pollingTimer.value) {
      clearInterval(pollingTimer.value)
      pollingTimer.value = null
      await nextTick()
    }
  } catch {
    // ignore polling errors
  }
}

function renderQR() {
  if (!qrCode.value || !qrCanvas.value) return

  nextTick(() => {
    const canvas = qrCanvas.value
    if (!canvas) return

    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const size = 256
    const modules = encodeQR(qrCode.value)

    const cellSize = size / (modules.length + 8)
    const offset = cellSize * 4

    ctx.fillStyle = '#ffffff'
    ctx.fillRect(0, 0, size, size)

    ctx.fillStyle = '#000000'
    for (let row = 0; row < modules.length; row++) {
      for (let col = 0; col < modules[row].length; col++) {
        if (modules[row][col]) {
          ctx.fillRect(
            offset + col * cellSize,
            offset + row * cellSize,
            cellSize,
            cellSize
          )
        }
      }
    }
  })
}

function encodeQR(text) {
  const size = 25
  const matrix = []
  for (let i = 0; i < size; i++) {
    matrix[i] = []
    for (let j = 0; j < size; j++) {
      matrix[i][j] = 0
    }
  }

  function setFinderPattern(startRow, startCol) {
    for (let r = 0; r < 7; r++) {
      for (let c = 0; c < 7; c++) {
        if (r === 0 || r === 6 || c === 0 || c === 6 ||
            (r >= 2 && r <= 4 && c >= 2 && c <= 4)) {
          matrix[startRow + r][startCol + c] = 1
        }
      }
    }
  }

  setFinderPattern(0, 0)
  setFinderPattern(0, size - 7)
  setFinderPattern(size - 7, 0)

  for (let r = 8; r < size - 8; r++) {
    for (let c = 8; c < size - 8; c++) {
      const hash = hashCode(text + r + c)
      if (Math.abs(hash) % 3 === 0) {
        matrix[r][c] = 1
      }
    }
  }

  return matrix
}

function hashCode(str) {
  let hash = 0
  for (let i = 0; i < str.length; i++) {
    const char = str.charCodeAt(i)
    hash = ((hash << 5) - hash) + char
    hash |= 0
  }
  return hash
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

.qr-wrapper canvas {
  display: block;
  width: 256px;
  height: 256px;
  image-rendering: pixelated;
}

.qr-expired-hint {
  margin-top: 12px;
  font-size: 13px;
  color: #ff6b6b;
}

.qr-expired-hint a {
  color: #ffffff;
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
    padding-top: 64px;
  }
}
</style>
