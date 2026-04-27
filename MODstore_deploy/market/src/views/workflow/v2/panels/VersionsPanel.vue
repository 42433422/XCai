<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '../../../../api'

const props = defineProps<{
  workflowId: number
  open: boolean
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'rolled-back', versionNo: number): void
}>()

interface VersionRow {
  id: number
  version_no: number
  note: string
  is_current: boolean
  created_at: string
}

const rows = ref<VersionRow[]>([])
const loading = ref(false)
const errMsg = ref('')

async function refresh() {
  loading.value = true
  errMsg.value = ''
  try {
    const list: any = await api.listWorkflowVersions(props.workflowId)
    rows.value = Array.isArray(list) ? list : []
  } catch (e: any) {
    errMsg.value = e?.detail || e?.message || '加载失败'
  } finally {
    loading.value = false
  }
}

onMounted(refresh)

async function rollback(row: VersionRow) {
  if (row.is_current) return
  if (!confirm(`确认回滚到 v${row.version_no}？\n\n该操作会用此版本快照覆盖当前画布的节点与连线，触发器不变。`)) return
  try {
    await api.rollbackWorkflowVersion(props.workflowId, row.id)
    await refresh()
    emit('rolled-back', row.version_no)
  } catch (e: any) {
    errMsg.value = e?.detail || e?.message || '回滚失败'
  }
}

function formatTime(iso: string): string {
  if (!iso) return ''
  try {
    const d = new Date(iso)
    return d.toLocaleString()
  } catch {
    return iso
  }
}

defineExpose({ refresh })
</script>

<template>
  <transition name="vp-fade">
    <aside v-if="open" class="vp">
      <header class="vp__head">
        <h3>版本历史</h3>
        <button class="vp__btn" type="button" @click="emit('close')">关闭</button>
      </header>
      <div class="vp__body">
        <p v-if="loading" class="vp__hint">加载中…</p>
        <p v-else-if="errMsg" class="vp__err">{{ errMsg }}</p>
        <p v-else-if="!rows.length" class="vp__hint">还没有发布过版本，点击顶栏「发布版本」开始记录历史。</p>

        <ul v-else class="vp__list">
          <li
            v-for="r in rows"
            :key="r.id"
            class="vp__item"
            :class="{ 'vp__item--current': r.is_current }"
          >
            <div class="vp__row">
              <span class="vp__no">v{{ r.version_no }}</span>
              <span v-if="r.is_current" class="vp__chip">当前</span>
              <span class="vp__time">{{ formatTime(r.created_at) }}</span>
            </div>
            <p v-if="r.note" class="vp__note">{{ r.note }}</p>
            <p v-else class="vp__note vp__note--empty">无备注</p>
            <div class="vp__actions">
              <button
                class="vp__btn"
                type="button"
                :disabled="r.is_current"
                @click="rollback(r)"
              >
                {{ r.is_current ? '当前版本' : '回滚到此' }}
              </button>
            </div>
          </li>
        </ul>
      </div>
    </aside>
  </transition>
</template>

<style scoped>
.vp {
  position: absolute;
  right: 12px;
  top: 60px;
  width: 340px;
  max-height: calc(100vh - 80px);
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  box-shadow: 0 16px 36px -16px rgba(15, 23, 42, 0.3);
  z-index: 25;
  display: flex;
  flex-direction: column;
}

.vp__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 14px;
  border-bottom: 1px solid #e2e8f0;
}

.vp__head h3 {
  margin: 0;
  font-size: 14px;
  color: #0f172a;
}

.vp__body {
  padding: 8px 0;
  overflow-y: auto;
}

.vp__hint,
.vp__err {
  padding: 16px;
  margin: 0;
  color: #64748b;
  font-size: 13px;
  text-align: center;
}

.vp__err {
  color: #b91c1c;
}

.vp__list {
  list-style: none;
  margin: 0;
  padding: 0;
}

.vp__item {
  padding: 10px 14px;
  border-bottom: 1px dashed #e2e8f0;
}

.vp__item--current {
  background: #f0fdf4;
}

.vp__row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.vp__no {
  font-weight: 600;
  color: #0f172a;
}

.vp__chip {
  font-size: 11px;
  background: #dcfce7;
  color: #166534;
  padding: 1px 6px;
  border-radius: 999px;
}

.vp__time {
  margin-left: auto;
  font-size: 11px;
  color: #94a3b8;
}

.vp__note {
  margin: 4px 0 6px;
  font-size: 12px;
  color: #334155;
  line-height: 1.4;
  white-space: pre-wrap;
}

.vp__note--empty {
  color: #94a3b8;
}

.vp__actions {
  display: flex;
  justify-content: flex-end;
}

.vp__btn {
  font-size: 12px;
  border: 1px solid #cbd5e1;
  background: #fff;
  color: #334155;
  padding: 4px 10px;
  border-radius: 6px;
  cursor: pointer;
}

.vp__btn:hover:not(:disabled) {
  background: #f1f5f9;
}

.vp__btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.vp-fade-enter-active,
.vp-fade-leave-active {
  transition: opacity 0.15s ease, transform 0.15s ease;
}

.vp-fade-enter-from,
.vp-fade-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}
</style>
