<template>
  <div class="analytics-page">
    <h1 class="page-title">使用统计</h1>
    <p class="page-desc">员工执行次数、成功率、LLM Token 与目录消费概览。</p>
    <div v-if="err" class="flash flash-err">{{ err }}</div>
    <div v-if="loading" class="loading">加载中…</div>
    <template v-else-if="dash">
      <div class="grid">
        <div class="card">
          <h3 class="card-title">执行</h3>
          <p class="stat">总次数 <strong>{{ dash.execution.total }}</strong></p>
          <p class="stat">成功 <strong>{{ dash.execution.success }}</strong> · 失败 <strong>{{ dash.execution.failed }}</strong></p>
          <p class="stat">成功率 <strong>{{ dash.execution.success_rate.toFixed(1) }}%</strong></p>
          <p class="stat">累计 Token <strong>{{ dash.execution.total_tokens }}</strong></p>
        </div>
        <div class="card">
          <h3 class="card-title">消费</h3>
          <p class="stat">已购商品金额合计 <strong>¥{{ Number(dash.spending.total).toFixed(2) }}</strong></p>
          <p class="hint">基于「购买」记录汇总，不含钱包充值余额。</p>
        </div>
      </div>
      <div class="card">
        <h3 class="card-title">最近执行</h3>
        <table v-if="dash.recent_executions.length" class="tbl">
          <thead>
            <tr>
              <th>员工</th>
              <th>任务</th>
              <th>状态</th>
              <th>Token</th>
              <th>时间</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="r in dash.recent_executions" :key="r.id">
              <td>{{ r.employee_id }}</td>
              <td>{{ r.task }}</td>
              <td>{{ r.status }}</td>
              <td>{{ r.llm_tokens }}</td>
              <td>{{ r.created_at }}</td>
            </tr>
          </tbody>
        </table>
        <div v-else class="empty">暂无执行记录</div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '../api'

const loading = ref(true)
const err = ref('')
const dash = ref(null)

onMounted(async () => {
  loading.value = true
  err.value = ''
  try {
    dash.value = await api.analyticsDashboard()
  } catch (e) {
    err.value = e?.message || String(e)
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.analytics-page {
  max-width: var(--layout-max, 960px);
  margin: 0 auto;
  padding: var(--page-pad-y, 1.5rem) var(--layout-pad-x, 1rem);
}
.page-title {
  font-size: 1.75rem;
  margin: 0 0 0.5rem;
  color: #fff;
}
.page-desc {
  color: rgba(255, 255, 255, 0.45);
  margin: 0 0 1.25rem;
  font-size: 0.9rem;
}
.grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 1rem;
  margin-bottom: 1rem;
}
.card {
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 12px;
  padding: 1rem 1.25rem;
}
.card-title {
  margin: 0 0 0.75rem;
  font-size: 1rem;
  color: rgba(255, 255, 255, 0.85);
}
.stat {
  margin: 0.35rem 0;
  color: rgba(255, 255, 255, 0.75);
  font-size: 0.95rem;
}
.hint {
  font-size: 0.8rem;
  color: rgba(255, 255, 255, 0.45);
  margin: 0.5rem 0 0;
}
.tbl {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.85rem;
}
.tbl th,
.tbl td {
  text-align: left;
  padding: 0.5rem 0.35rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  color: rgba(255, 255, 255, 0.8);
}
.flash-err {
  background: rgba(220, 53, 69, 0.15);
  color: #f8a0a8;
  padding: 0.75rem 1rem;
  border-radius: 8px;
  margin-bottom: 1rem;
}
.loading,
.empty {
  color: rgba(255, 255, 255, 0.5);
}
</style>
