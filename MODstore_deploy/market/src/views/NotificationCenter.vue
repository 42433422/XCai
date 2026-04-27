<template>
  <div class="notif-page">
    <h1 class="page-title">通知中心</h1>
    <div class="toolbar">
      <label class="chk"><input type="checkbox" v-model="unreadOnly" @change="load" /> 仅未读</label>
      <button type="button" class="btn btn-sm" :disabled="!items.length" @click="markAll">全部已读</button>
    </div>
    <div class="filters">
      <button
        v-for="c in categories"
        :key="c.value"
        type="button"
        :class="['filter-chip', { active: category === c.value }]"
        @click="setCategory(c.value)"
      >
        {{ c.label }}
      </button>
    </div>
    <div v-if="err" class="flash flash-err">{{ err }}</div>
    <div v-if="loading" class="loading">加载中…</div>
    <ul v-else-if="items.length" class="list">
      <li
        v-for="n in items"
        :key="n.id"
        class="item"
        :class="{ unread: !n.is_read }"
        @click="onItemClick(n)"
      >
        <div class="item-head">
          <span class="item-title">{{ n.title }}</span>
          <span class="item-time">{{ n.created_at }}</span>
        </div>
        <p class="item-body">{{ n.content }}</p>
        <button v-if="!n.is_read" type="button" class="btn btn-sm" @click.stop="markOne(n.id)">标为已读</button>
      </li>
    </ul>
    <div v-else class="empty">暂无通知</div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api'
import { useNotificationStore } from '../stores/notifications'

const router = useRouter()
const notificationStore = useNotificationStore()
const loading = ref(true)
const err = ref('')
const items = ref([])
const unreadOnly = ref(false)
const category = ref('')

const categories = [
  { value: '', label: '全部' },
  { value: 'payment_success', label: '支付' },
  { value: 'employee_execution_done', label: '员工' },
  { value: 'quota_warning', label: '配额' },
  { value: 'system', label: '系统' },
]

function setCategory(v) {
  category.value = v
  void load()
}

async function load() {
  loading.value = true
  err.value = ''
  try {
    const res = await api.notificationsList(unreadOnly.value, 80, category.value || '')
    items.value = res.notifications || []
  } catch (e) {
    err.value = e?.message || String(e)
  } finally {
    loading.value = false
  }
}

async function onItemClick(n) {
  try {
    if (!n.is_read) await notificationStore.markRead(n.id)
  } catch {
    /* ignore */
  }
  const data = n.data || {}
  switch (n.type) {
    case 'payment_success':
      if (data.order_no) router.push({ name: 'order-detail', params: { orderId: data.order_no } })
      break
    case 'employee_execution_done':
      router.push({ path: '/workbench', query: { focus: 'employee' } })
      break
    case 'quota_warning':
      router.push({ name: 'wallet' })
      break
    default:
      break
  }
}

async function markOne(id) {
  try {
    await notificationStore.markRead(id)
    await load()
  } catch (e) {
    err.value = e?.message || String(e)
  }
}

async function markAll() {
  try {
    await notificationStore.markAllRead()
    await load()
  } catch (e) {
    err.value = e?.message || String(e)
  }
}

onMounted(load)
</script>

<style scoped>
.notif-page {
  max-width: 720px;
  margin: 0 auto;
  padding: var(--page-pad-y, 1.5rem) var(--layout-pad-x, 1rem);
}
.page-title {
  font-size: 1.75rem;
  margin: 0 0 1rem;
  color: #fff;
}
.toolbar {
  display: flex;
  align-items: center;
  gap: 1rem;
  margin-bottom: 1rem;
}
.filters {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-bottom: 1rem;
}
.filter-chip {
  border: 1px solid rgba(255, 255, 255, 0.15);
  background: transparent;
  color: rgba(255, 255, 255, 0.75);
  border-radius: 999px;
  padding: 0.35rem 0.75rem;
  font-size: 0.85rem;
  cursor: pointer;
}
.filter-chip.active {
  border-color: #6366f1;
  color: #fff;
  background: rgba(99, 102, 241, 0.2);
}
.chk {
  color: rgba(255, 255, 255, 0.7);
  font-size: 0.9rem;
}
.list {
  list-style: none;
  margin: 0;
  padding: 0;
}
.item {
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 10px;
  padding: 1rem;
  margin-bottom: 0.75rem;
  cursor: pointer;
}
.item.unread {
  border-color: rgba(100, 180, 255, 0.35);
}
.item-head {
  display: flex;
  justify-content: space-between;
  gap: 0.5rem;
  margin-bottom: 0.35rem;
}
.item-title {
  font-weight: 600;
  color: #fff;
}
.item-time {
  font-size: 0.75rem;
  color: rgba(255, 255, 255, 0.45);
}
.item-body {
  margin: 0 0 0.5rem;
  color: rgba(255, 255, 255, 0.75);
  font-size: 0.9rem;
  white-space: pre-wrap;
}
.flash-err {
  background: rgba(220, 53, 69, 0.15);
  color: #f8a0a8;
  padding: 0.75rem 1rem;
  border-radius: 8px;
  margin-bottom: 0.75rem;
}
.loading,
.empty {
  color: rgba(255, 255, 255, 0.5);
}
</style>
