<template>
  <div class="catalog-detail">
    <div v-if="loading" class="loading">加载中...</div>
    <div v-else-if="err" class="flash flash-err">{{ err }}</div>
    <template v-else-if="item">
      <div class="detail-header">
        <div>
          <h1>{{ item.name }}</h1>
          <p class="meta">
            {{ item.pkg_id }} · v{{ item.version }} · {{ item.industry || '通用' }} · {{ getArtifactLabel(item.artifact) }}
          </p>
          <p v-if="item.description" class="desc">{{ item.description }}</p>
        </div>
        <div class="detail-actions">
          <span class="price-tag" :class="{ free: item.price <= 0 }">
            {{ item.price <= 0 ? '免费' : '¥' + item.price.toFixed(2) }}
          </span>
          <button
            v-if="hasToken"
            type="button"
            class="btn btn-fav"
            :class="{ 'btn-fav--on': item.favorited }"
            :disabled="favBusy"
            @click="toggleFavorite"
          >
            {{ item.favorited ? '已收藏' : '收藏' }}
          </button>
          <template v-if="item.purchased">
            <button class="btn btn-success" @click="doDownload">下载</button>
            <span class="owned-badge">已拥有</span>
          </template>
          <template v-else>
            <button class="btn btn-primary-solid" @click="doBuy" :disabled="buying">
              {{ buying ? '购买中...' : '购买' }}
            </button>
          </template>
          <button
            v-if="authStore.isAdmin"
            class="btn btn-danger"
            :disabled="delisting"
            @click="delistItem"
          >
            {{ delisting ? '下架中...' : '下架' }}
          </button>
        </div>
      </div>

      <div v-if="item" class="detail-section reviews-section">
        <h2 class="section-title">评价</h2>
        <p v-if="reviewsData.total > 0" class="reviews-summary">
          平均 {{ reviewsData.average_rating }} 分 · 共 {{ reviewsData.total }} 条
        </p>
        <div v-if="reviewsLoading" class="loading">加载评价...</div>
        <div v-else-if="reviewsErr" class="flash flash-err">{{ reviewsErr }}</div>
        <ul v-else class="review-list">
          <li v-for="r in reviewsData.reviews" :key="r.id" class="review-item">
            <div class="review-head">
              <strong>{{ r.user_name }}</strong>
              <span class="review-stars">{{ '★'.repeat(r.rating) }}{{ '☆'.repeat(5 - r.rating) }}</span>
              <span class="review-date">{{ r.created_at }}</span>
            </div>
            <p v-if="r.content" class="review-body">{{ r.content }}</p>
          </li>
        </ul>
        <div
          v-if="hasToken && item.purchased && !item.user_has_review"
          class="review-form"
        >
          <h3 class="review-form-title">写评价</h3>
          <label class="label">评分（1–5）</label>
          <select v-model.number="reviewRating" class="input">
            <option v-for="n in 5" :key="n" :value="n">{{ n }} 分</option>
          </select>
          <label class="label">内容（可选）</label>
          <textarea v-model="reviewContent" class="input textarea" rows="3" maxlength="4000" placeholder="使用体验、建议等" />
          <button type="button" class="btn btn-primary-solid" :disabled="reviewSubmitting" @click="submitReview">
            {{ reviewSubmitting ? '提交中...' : '提交评价' }}
          </button>
        </div>
        <p v-else-if="hasToken && item.purchased && item.user_has_review" class="review-note">您已评价过该商品。</p>
        <p v-else-if="hasToken && !item.purchased" class="review-note">购买后可发表评价。</p>
      </div>

      <!-- 员工能力详情 -->
      <div v-if="item.artifact === 'employee_pack'" class="detail-section">
        <h2 class="section-title">员工能力</h2>
        <div class="capabilities-grid">
          <div class="capability-card">
            <h3>任务类型</h3>
            <ul class="capability-list">
              <li>分析文档</li>
              <li>处理数据</li>
              <li>生成报告</li>
            </ul>
          </div>
          <div class="capability-card">
            <h3>行业适配</h3>
            <p>{{ item.industry || '通用' }}</p>
          </div>
          <div class="capability-card">
            <h3>版本信息</h3>
            <p>v{{ item.version }}</p>
          </div>
        </div>
      </div>

      <!-- 员工状态 -->
      <div v-if="item.artifact === 'employee_pack' && item.purchased" class="detail-section">
        <h2 class="section-title">员工状态</h2>
        <div v-if="employeeStatus.loading" class="loading">加载中...</div>
        <div v-else-if="employeeStatus.error" class="flash flash-err">{{ employeeStatus.error }}</div>
        <div v-else-if="employeeStatus.data" class="status-grid">
          <div class="status-item">
            <span class="status-label">状态</span>
            <span class="status-value">{{ employeeStatus.data.status }}</span>
          </div>
          <div class="status-item">
            <span class="status-label">总执行次数</span>
            <span class="status-value">{{ employeeStatus.data.execution_stats.total_executions }}</span>
          </div>
          <div class="status-item">
            <span class="status-label">成功率</span>
            <span class="status-value">{{ employeeStatus.data.execution_stats.success_rate.toFixed(1) }}%</span>
          </div>
        </div>
      </div>

      <!-- 工作流配置 -->
      <div v-if="item.artifact === 'employee_pack' && item.purchased" class="detail-section">
        <h2 class="section-title">工作流配置</h2>
        <p class="section-desc">将此员工添加到工作流中，配置任务参数</p>
        <div class="workflow-config">
          <button class="btn btn-primary" @click="navigateToWorkflow">添加到工作流</button>
          <p class="config-hint">在工作流编辑器中，您可以为员工配置具体的任务类型和参数</p>
        </div>
      </div>

      <!-- 使用示例 -->
      <div v-if="item.artifact === 'employee_pack'" class="detail-section">
        <h2 class="section-title">使用示例</h2>
        <div class="example-card">
          <h3>文档分析</h3>
          <pre class="example-code">{
  "document_content": "这是一份需要分析的文档内容..."
}</pre>
        </div>
        <div class="example-card">
          <h3>数据处理</h3>
          <pre class="example-code">{
  "data": [1, 2, 3, 4, 5]
}</pre>
        </div>
        <div class="example-card">
          <h3>报告生成</h3>
          <pre class="example-code">{
  "title": "月度报告",
  "content": "本月工作总结..."
}</pre>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '../api'
import { useAuthStore } from '../stores/auth'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const item = ref(null)
const loading = ref(true)
const err = ref('')
const buying = ref(false)
const delisting = ref(false)
const hasToken = ref(false)
const favBusy = ref(false)
const reviewsLoading = ref(false)
const reviewsErr = ref('')
const reviewsData = ref({ reviews: [], average_rating: 0, total: 0 })
const reviewRating = ref(5)
const reviewContent = ref('')
const reviewSubmitting = ref(false)

// 员工状态
const employeeStatus = ref({
  loading: false,
  error: '',
  data: null
})

// 工件类型标签
const artifactLabels = {
  mod: 'MOD 插件',
  employee_pack: 'AI 员工包',
  bundle: '资源包',
  surface: '界面扩展'
}

function getArtifactLabel(artifact) {
  return artifactLabels[artifact] || artifact || '其他'
}

onMounted(async () => {
  hasToken.value = !!localStorage.getItem('modstore_token')
  try {
    item.value = await api.catalogDetail(route.params.id)
    await loadReviews()
    // 如果是员工包且已购买，加载员工状态
    if (item.value.artifact === 'employee_pack' && item.value.purchased) {
      await loadEmployeeStatus()
    }
  } catch (e) {
    err.value = e.message
  } finally {
    loading.value = false
  }
})

async function loadReviews() {
  if (!route.params.id) return
  reviewsLoading.value = true
  reviewsErr.value = ''
  try {
    reviewsData.value = await api.catalogReviews(route.params.id)
  } catch (e) {
    reviewsErr.value = e.message || '加载评价失败'
  } finally {
    reviewsLoading.value = false
  }
}

async function toggleFavorite() {
  if (!item.value) return
  if (!localStorage.getItem('modstore_token')) {
    await router.push({ name: 'login', query: { redirect: `/catalog/${route.params.id}` } })
    return
  }
  favBusy.value = true
  try {
    const r = await api.catalogToggleFavorite(route.params.id)
    item.value.favorited = !!r.favorited
  } catch (e) {
    alert(e.message)
  } finally {
    favBusy.value = false
  }
}

async function submitReview() {
  if (!item.value || item.value.user_has_review) return
  reviewSubmitting.value = true
  try {
    await api.catalogSubmitReview(route.params.id, reviewRating.value, reviewContent.value.trim())
    item.value.user_has_review = true
    reviewContent.value = ''
    await loadReviews()
  } catch (e) {
    alert(e.message)
  } finally {
    reviewSubmitting.value = false
  }
}

async function loadEmployeeStatus() {
  if (!item.value) return
  
  employeeStatus.value.loading = true
  employeeStatus.value.error = ''
  
  try {
    const status = await api.getEmployeeStatus(item.value.pkg_id)
    employeeStatus.value.data = status
  } catch (e) {
    employeeStatus.value.error = e.message
  } finally {
    employeeStatus.value.loading = false
  }
}

async function doBuy() {
  if (!localStorage.getItem('modstore_token')) {
    await router.push({
      name: 'login',
      query: { redirect: `/catalog/${route.params.id}` },
    })
    return
  }
  const it = item.value
  if (!it) return

  if (it.price <= 0) {
    buying.value = true
    try {
      const res = await api.buyItem(route.params.id)
      alert(res.message)
      item.value = await api.catalogDetail(route.params.id)
      if (item.value.artifact === 'employee_pack' && item.value.purchased) {
        await loadEmployeeStatus()
      }
    } catch (e) {
      alert(e.message)
    } finally {
      buying.value = false
    }
    return
  }

  buying.value = true
  try {
    const res = await api.paymentCheckout({
      item_id: Number(it.id),
      subject: it.name,
    })
    if (!res.ok) {
      alert(res.message || '下单失败')
      return
    }
    if (res.type === 'page' || res.type === 'wap') {
      window.location.href = res.redirect_url
    } else if (res.type === 'precreate' || res.type === 'wechat_native') {
      await router.push({ name: 'checkout', params: { orderId: res.order_id } })
    } else {
      alert('未知的支付类型')
    }
  } catch (e) {
    alert(e.message)
  } finally {
    buying.value = false
  }
}

async function doDownload() {
  try {
    await api.downloadItem(route.params.id)
  } catch (e) {
    alert(e.message)
  }
}

async function delistItem() {
  const it = item.value
  if (!it || delisting.value) return
  const ok = window.confirm(`确定下架「${it.name}」吗？下架后市场将不再展示该商品。`)
  if (!ok) return
  delisting.value = true
  try {
    await api.adminDeleteCatalog(it.id)
    await router.push({ name: 'ai-store' })
  } catch (e) {
    alert(e?.message || String(e))
  } finally {
    delisting.value = false
  }
}

function navigateToWorkflow() {
  router.push('/workflow')
}
</script>

<style scoped>
.catalog-detail {
  width: 100%;
  max-width: var(--layout-max);
  margin: 0 auto;
  padding: var(--page-pad-y) var(--layout-pad-x);
  box-sizing: border-box;
}

.detail-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 24px;
  margin-bottom: 2rem;
  padding-bottom: 1.5rem;
  border-bottom: 0.5px solid rgba(255,255,255,0.1);
}

.detail-header h1 {
  font-size: 24px;
  color: #ffffff;
  margin-bottom: 8px;
}

.meta {
  font-size: 13px;
  color: rgba(255,255,255,0.3);
  margin-bottom: 8px;
}

.desc {
  font-size: 14px;
  color: rgba(255,255,255,0.5);
  max-width: 600px;
  line-height: 1.5;
}

.detail-actions {
  display: flex;
  gap: 12px;
  align-items: center;
  flex-shrink: 0;
}

.price-tag {
  font-size: 20px;
  font-weight: 700;
  color: #ff6b6b;
}

.price-tag.free {
  color: #4ade80;
}

.owned-badge {
  font-size: 14px;
  color: #4ade80;
  background: rgba(74,222,128,0.1);
  padding: 6px 14px;
  border-radius: 12px;
}

.loading {
  text-align: center;
  padding: 40px;
  color: rgba(255,255,255,0.4);
}

.flash {
  padding: 10px 16px;
  border-radius: 8px;
  margin-bottom: 16px;
  font-size: 14px;
}

.flash-err {
  background: rgba(255,80,80,0.1);
  color: #ff8a8a;
}

.btn {
  padding: 0.5rem 1rem;
  border: 0.5px solid rgba(255,255,255,0.15);
  border-radius: 6px;
  background: transparent;
  color: rgba(255,255,255,0.7);
  font-size: 0.875rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}

.btn:hover {
  background: rgba(255,255,255,0.06);
  color: #ffffff;
}

.btn-primary {
  background: #60a5fa;
  color: #0a0a0a;
  border: none;
}

.btn-primary:hover {
  background: #3b82f6;
  color: #0a0a0a;
}

.btn-primary-solid {
  background: #ffffff;
  color: #0a0a0a;
  border: none;
}

.btn-primary-solid:hover {
  opacity: 0.9;
  color: #0a0a0a;
}

.btn-success {
  background: rgba(74,222,128,0.1);
  color: #4ade80;
  border-color: rgba(74,222,128,0.3);
}

.btn-success:hover {
  background: rgba(74,222,128,0.2);
  color: #4ade80;
}

.btn-danger {
  color: #fca5a5;
  border-color: rgba(248, 113, 113, 0.35);
  background: rgba(127, 29, 29, 0.18);
}

.btn-danger:hover {
  color: #fecaca;
  background: rgba(127, 29, 29, 0.28);
}

.btn-fav {
  border-color: rgba(250, 204, 21, 0.35);
  color: rgba(250, 204, 21, 0.9);
}

.btn-fav--on {
  background: rgba(250, 204, 21, 0.12);
  border-color: rgba(250, 204, 21, 0.5);
}

.reviews-section .reviews-summary {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.45);
  margin: 0 0 12px;
}

.review-list {
  list-style: none;
  margin: 0;
  padding: 0;
}

.review-item {
  padding: 12px 0;
  border-bottom: 0.5px solid rgba(255, 255, 255, 0.08);
}

.review-head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px 12px;
  font-size: 13px;
  color: rgba(255, 255, 255, 0.85);
}

.review-stars {
  color: #fbbf24;
  letter-spacing: 1px;
}

.review-date {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.35);
}

.review-body {
  margin: 8px 0 0;
  font-size: 14px;
  color: rgba(255, 255, 255, 0.55);
  line-height: 1.5;
}

.review-form {
  margin-top: 20px;
  padding-top: 16px;
  border-top: 0.5px solid rgba(255, 255, 255, 0.1);
}

.review-form-title {
  font-size: 15px;
  margin: 0 0 10px;
  color: #fff;
}

.review-form .label {
  display: block;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.45);
  margin: 8px 0 4px;
}

.review-form .input {
  width: 100%;
  max-width: 420px;
  box-sizing: border-box;
  padding: 8px 10px;
  border-radius: 6px;
  border: 0.5px solid rgba(255, 255, 255, 0.12);
  background: #111;
  color: #fff;
  font-size: 14px;
}

.review-form .textarea {
  resize: vertical;
  min-height: 72px;
}

.review-form .btn-primary-solid {
  margin-top: 12px;
}

.review-note {
  margin-top: 12px;
  font-size: 13px;
  color: rgba(255, 255, 255, 0.4);
}

.detail-section {
  margin-bottom: 2rem;
  padding-bottom: 1.5rem;
  border-bottom: 0.5px solid rgba(255,255,255,0.1);
}

.section-title {
  font-size: 18px;
  font-weight: 600;
  color: #ffffff;
  margin-bottom: 1rem;
}

.section-desc {
  font-size: 14px;
  color: rgba(255,255,255,0.5);
  margin-bottom: 1rem;
}

.capabilities-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 15.625rem), 1fr));
  gap: 1rem;
}

.capability-card {
  background: #111111;
  border: 0.5px solid rgba(255,255,255,0.1);
  border-radius: 12px;
  padding: 1.25rem;
}

.capability-card h3 {
  font-size: 14px;
  font-weight: 600;
  color: #ffffff;
  margin-bottom: 0.75rem;
}

.capability-list {
  list-style: none;
  padding: 0;
  margin: 0;
}

.capability-list li {
  font-size: 13px;
  color: rgba(255,255,255,0.5);
  margin-bottom: 0.5rem;
  position: relative;
  padding-left: 1.25rem;
}

.capability-list li::before {
  content: '•';
  position: absolute;
  left: 0;
  color: #60a5fa;
}

.capability-card p {
  font-size: 13px;
  color: rgba(255,255,255,0.5);
  margin: 0;
}

.status-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 12.5rem), 1fr));
  gap: 1rem;
}

.status-item {
  background: #111111;
  border: 0.5px solid rgba(255,255,255,0.1);
  border-radius: 12px;
  padding: 1.25rem;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.status-label {
  font-size: 12px;
  color: rgba(255,255,255,0.3);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.status-value {
  font-size: 18px;
  font-weight: 600;
  color: #ffffff;
}

.workflow-config {
  background: #111111;
  border: 0.5px solid rgba(255,255,255,0.1);
  border-radius: 12px;
  padding: 1.5rem;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.config-hint {
  font-size: 13px;
  color: rgba(255,255,255,0.4);
  margin: 0;
}

.example-card {
  background: #111111;
  border: 0.5px solid rgba(255,255,255,0.1);
  border-radius: 12px;
  padding: 1.25rem;
  margin-bottom: 1rem;
}

.example-card h3 {
  font-size: 14px;
  font-weight: 600;
  color: #ffffff;
  margin-bottom: 0.75rem;
}

.example-code {
  background: rgba(0,0,0,0.3);
  border-radius: 8px;
  padding: 1rem;
  font-size: 13px;
  color: rgba(255,255,255,0.8);
  overflow-x: auto;
  margin: 0;
}

@media (max-width: 768px) {
  .detail-header {
    flex-direction: column;
    align-items: flex-start;
  }
  
  .detail-actions {
    align-items: flex-start;
    flex-direction: column;
    width: 100%;
  }
  
  .capabilities-grid,
  .status-grid {
    grid-template-columns: 1fr;
  }
}
</style>
