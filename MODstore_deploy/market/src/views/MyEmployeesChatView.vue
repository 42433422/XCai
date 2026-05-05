<template>
  <div class="emp-chat" :class="{ 'emp-chat--embedded': embedded }">
    <header v-if="!embedded" class="emp-chat__head">
      <h1>我的员工</h1>
      <p class="emp-chat__sub">从已登记的员工包中选择一名，通过服务端执行管道对话（调用 <code class="emp-mono">/api/employees</code>）。</p>
      <button type="button" class="emp-btn emp-btn--ghost" :disabled="loadingList" @click="loadEmployees">
        {{ loadingList ? '加载中…' : '刷新列表' }}
      </button>
    </header>
    <div v-else class="emp-chat__toolbar">
      <button type="button" class="emp-btn emp-btn--ghost" :disabled="loadingList" @click="loadEmployees">
        {{ loadingList ? '加载中…' : '刷新列表' }}
      </button>
    </div>

    <div class="emp-chat__layout">
      <aside class="emp-chat__side">
        <h2>员工列表</h2>
        <p v-if="hasV1OnlyEmployees" class="emp-muted emp-muted--hint">
          标记「仅目录」的条目尚未写入 catalog_items；对话执行以数据库登记为准。若发送失败，请管理员「从 XC catalog 同步」或重新登记。
        </p>
        <p v-if="listError" class="emp-chat__err">{{ listError }}</p>
        <p v-else-if="!employees.length && !loadingList" class="emp-muted">
          暂无可用员工包。请先在 Mod 制作或员工制作中登记 employee_pack；若 packages.json 与数据库不一致，请管理员执行「从 XC catalog 同步」或重新登记。
        </p>
        <p v-else-if="!visibleEmployees.length && !loadingList" class="emp-muted emp-muted--hint">
          列表中的员工均已从本机隐藏。
          <button type="button" class="emp-btn emp-btn--ghost emp-btn--inline" @click="clearHiddenPkgIds">显示全部</button>
        </p>
        <ul v-else class="emp-list">
          <li v-for="e in visibleEmployees" :key="e.id" class="emp-list__row">
            <button
              type="button"
              class="emp-list__btn"
              :class="{ 'emp-list__btn--active': e.id === selectedId }"
              @click="selectEmployee(e.id)"
            >
              <span class="emp-list__name">{{ e.name || e.id }}</span>
              <span class="emp-list__id">{{ e.id }}{{ e.source === 'v1_catalog' ? ' · 仅目录' : '' }}</span>
            </button>
            <button
              type="button"
              class="emp-list__action emp-list__action--edit"
              title="在工作台中二次编辑"
              @click.stop="editEmployee(e.id)"
            >
              编辑
            </button>
            <button
              v-if="isAdmin"
              type="button"
              class="emp-list__action emp-list__action--danger"
              title="从服务端删除该员工包"
              :disabled="deletingId === e.id"
              @click.stop="confirmDeleteEmployee(e)"
            >
              {{ deletingId === e.id ? '…' : '删除' }}
            </button>
            <button
              v-else
              type="button"
              class="emp-list__action"
              title="仅从本机列表隐藏"
              @click.stop="hideLocally(e.id)"
            >
              隐藏
            </button>
          </li>
        </ul>
      </aside>

      <main class="emp-chat__main">
        <div v-if="!selectedId" class="emp-chat__empty">请从左侧选择一名员工。</div>
        <template v-else>
          <div class="emp-msgs">
            <div v-for="(m, idx) in messages" :key="idx" :class="['emp-msg', m.role === 'user' ? 'emp-msg--user' : 'emp-msg--bot']">
              <div class="emp-msg__bubble">{{ m.text }}</div>
            </div>
          </div>
          <p v-if="sendError" class="emp-chat__err">{{ sendError }}</p>
          <form class="emp-composer" @submit.prevent="send">
            <textarea v-model="draft" rows="3" placeholder="输入消息后发送（Enter 换行，Ctrl+Enter 发送）" @keydown="onKeydown" />
            <div class="emp-composer__foot">
              <span class="emp-muted">当前：{{ selectedId }}</span>
              <button type="submit" class="emp-btn" :disabled="sending || !draft.trim()">{{ sending ? '发送中…' : '发送' }}</button>
            </div>
          </form>
        </template>
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { storeToRefs } from 'pinia'
import { useRouter } from 'vue-router'
import { api } from '../api'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const { isAdmin } = storeToRefs(auth)
const router = useRouter()

const HIDDEN_PKG_IDS_KEY = 'modstore_emp_chat_hidden_pkg_ids'

function readHiddenPkgIds(): Set<string> {
  try {
    const raw = localStorage.getItem(HIDDEN_PKG_IDS_KEY)
    const arr = raw ? (JSON.parse(raw) as unknown) : []
    if (!Array.isArray(arr)) return new Set()
    return new Set(arr.filter((x): x is string => typeof x === 'string'))
  } catch {
    return new Set()
  }
}

const hiddenPkgIds = ref<Set<string>>(readHiddenPkgIds())
const deletingId = ref('')

function persistHiddenPkgIds() {
  localStorage.setItem(HIDDEN_PKG_IDS_KEY, JSON.stringify([...hiddenPkgIds.value]))
}

function hideLocally(pkgId: string) {
  hiddenPkgIds.value = new Set([...hiddenPkgIds.value, pkgId])
  persistHiddenPkgIds()
  if (selectedId.value === pkgId) {
    selectedId.value = ''
    messages.value = []
    sendError.value = ''
  }
}

function clearHiddenPkgIds() {
  hiddenPkgIds.value = new Set()
  persistHiddenPkgIds()
}

withDefaults(
  defineProps<{
    /** 嵌入统一工作台时隐藏大标题、收紧边距 */
    embedded?: boolean
  }>(),
  { embedded: false },
)

type EmployeeRow = { id: string; name?: string; source?: 'catalog' | 'v1_catalog' }

const employees = ref<EmployeeRow[]>([])
const visibleEmployees = computed(() => employees.value.filter((e) => !hiddenPkgIds.value.has(e.id)))
const hasV1OnlyEmployees = computed(() => employees.value.some((e) => e.source === 'v1_catalog'))
const selectedId = ref('')
const messages = ref<{ role: 'user' | 'assistant'; text: string }[]>([])
const draft = ref('')
const loadingList = ref(false)
const sending = ref(false)
const listError = ref('')
const sendError = ref('')

function selectEmployee(id: string) {
  selectedId.value = id
  messages.value = []
  sendError.value = ''
}

function editEmployee(id: string) {
  router.push({ name: 'workbench-shell', params: { target: 'employee', id } })
}

async function confirmDeleteEmployee(e: EmployeeRow) {
  if (!isAdmin.value) return
  const label = e.name || e.id
  const ok = window.confirm(`确定删除员工包「${label}」（${e.id}）？将从目录与数据库移除，不可恢复。`)
  if (!ok) return
  deletingId.value = e.id
  listError.value = ''
  try {
    await api.adminDeleteEmployeePack(e.id)
    hiddenPkgIds.value.delete(e.id)
    persistHiddenPkgIds()
    if (selectedId.value === e.id) {
      selectedId.value = ''
      messages.value = []
    }
    await loadEmployees()
  } catch (err: unknown) {
    listError.value = err instanceof Error ? err.message : String(err)
  } finally {
    deletingId.value = ''
  }
}

function extractAssistantText(res: unknown): string {
  const r = res as Record<string, unknown> | null
  const result = r?.result as Record<string, unknown> | undefined
  const outs = result?.outputs as unknown[] | undefined
  if (!Array.isArray(outs)) return JSON.stringify(res, null, 2)
  const echo = outs.find((o) => (o as Record<string, unknown>).handler === 'echo') as Record<string, unknown> | undefined
  if (echo && typeof echo.output === 'string') return echo.output
  return JSON.stringify(outs, null, 2)
}

async function loadEmployees() {
  listError.value = ''
  loadingList.value = true
  try {
    const rows = await api.listEmployees()
    if (!Array.isArray(rows)) {
      employees.value = []
      return
    }
    employees.value = (rows as Record<string, unknown>[]).map((e) => {
      const id = String(e.id ?? '').trim()
      const rawSrc = e.source
      const source: EmployeeRow['source'] = rawSrc === 'v1_catalog' ? 'v1_catalog' : 'catalog'
      return {
        id,
        name: typeof e.name === 'string' ? e.name : undefined,
        source,
      }
    })
  } catch (e: unknown) {
    listError.value = e instanceof Error ? e.message : String(e)
    employees.value = []
  } finally {
    loadingList.value = false
  }
}

async function send() {
  const text = draft.value.trim()
  if (!text || !selectedId.value) return
  sendError.value = ''
  sending.value = true
  messages.value.push({ role: 'user', text })
  draft.value = ''
  try {
    const tail = messages.value
      .filter((m) => m.role === 'user')
      .slice(-5)
      .map((m) => m.text)
    const res = await api.executeEmployeeTask(selectedId.value, text, {
      chat_history: tail,
    })
    messages.value.push({ role: 'assistant', text: extractAssistantText(res) })
  } catch (e: unknown) {
    sendError.value = e instanceof Error ? e.message : String(e)
    messages.value.push({
      role: 'assistant',
      text: `（执行失败）${sendError.value}`,
    })
  } finally {
    sending.value = false
  }
}

function onKeydown(ev: KeyboardEvent) {
  if (ev.key === 'Enter' && (ev.ctrlKey || ev.metaKey)) {
    ev.preventDefault()
    send()
  }
}

onMounted(() => {
  loadEmployees()
})
</script>

<style scoped>
.emp-chat {
  max-width: var(--layout-max, min(1200px, calc(100vw - 48px)));
  margin: 0 auto;
  padding: 1.25rem var(--layout-pad-x, 16px) 2rem;
  color: rgba(255, 255, 255, 0.88);
}
.emp-chat--embedded {
  max-width: none;
  margin: 0;
  padding: 0.5rem 0.65rem 0.75rem;
  flex: 1 1 auto;
  min-height: 0;
  display: flex;
  flex-direction: column;
}
.emp-chat__toolbar {
  display: flex;
  justify-content: flex-end;
  margin-bottom: 0.5rem;
}
.emp-chat--embedded .emp-chat__layout {
  flex: 1 1 auto;
  min-height: 0;
  margin-top: 0;
}
.emp-chat__head h1 {
  margin: 0 0 0.35rem;
  font-size: 1.35rem;
}
.emp-chat__sub {
  margin: 0 0 0.75rem;
  font-size: 0.88rem;
  color: rgba(255, 255, 255, 0.55);
  line-height: 1.45;
}
.emp-mono {
  font-family: ui-monospace, monospace;
  font-size: 0.85em;
}
.emp-chat__layout {
  display: grid;
  grid-template-columns: min(280px, 32vw) 1fr;
  gap: 1rem;
  margin-top: 1rem;
  min-height: 420px;
}
@media (max-width: 720px) {
  .emp-chat__layout {
    grid-template-columns: 1fr;
  }
}
.emp-chat__side,
.emp-chat__main {
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.03);
  padding: 0.75rem 1rem;
  min-width: 0;
}
.emp-chat__side h2 {
  margin: 0 0 0.5rem;
  font-size: 1rem;
}
.emp-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}
.emp-list__row {
  display: flex;
  align-items: stretch;
  gap: 0.35rem;
  min-width: 0;
}
.emp-list__btn {
  flex: 1 1 auto;
  min-width: 0;
  text-align: left;
  padding: 0.5rem 0.6rem;
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  background: rgba(0, 0, 0, 0.25);
  color: inherit;
  cursor: pointer;
}
.emp-list__action {
  flex: 0 0 auto;
  align-self: center;
  padding: 0.35rem 0.45rem;
  font-size: 0.72rem;
  line-height: 1.2;
  border-radius: 6px;
  border: 1px solid rgba(255, 255, 255, 0.14);
  background: rgba(255, 255, 255, 0.06);
  color: rgba(255, 255, 255, 0.72);
  cursor: pointer;
}
.emp-list__action:hover:not(:disabled) {
  background: rgba(255, 255, 255, 0.1);
}
.emp-list__action:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}
.emp-list__action--edit {
  border-color: rgba(99, 102, 241, 0.35);
  color: #a5b4fc;
}
.emp-list__action--edit:hover {
  background: rgba(99, 102, 241, 0.15);
}
.emp-list__action--danger {
  border-color: rgba(248, 113, 113, 0.35);
  color: #fca5a5;
}
.emp-list__action--danger:hover:not(:disabled) {
  background: rgba(248, 113, 113, 0.15);
}
.emp-list__btn--active {
  border-color: rgba(99, 102, 241, 0.65);
  background: rgba(99, 102, 241, 0.12);
}
.emp-list__name {
  display: block;
  font-weight: 600;
}
.emp-list__id {
  font-size: 0.78rem;
  color: rgba(255, 255, 255, 0.45);
  word-break: break-all;
}
.emp-msgs {
  min-height: 240px;
  max-height: min(52vh, 520px);
  overflow: auto;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  margin-bottom: 0.75rem;
}
.emp-msg {
  display: flex;
}
.emp-msg--user {
  justify-content: flex-end;
}
.emp-msg--bot {
  justify-content: flex-start;
}
.emp-msg__bubble {
  max-width: min(92%, 640px);
  padding: 0.55rem 0.75rem;
  border-radius: 10px;
  font-size: 0.9rem;
  line-height: 1.45;
  white-space: pre-wrap;
  word-break: break-word;
}
.emp-msg--user .emp-msg__bubble {
  background: rgba(99, 102, 241, 0.35);
}
.emp-msg--bot .emp-msg__bubble {
  background: rgba(255, 255, 255, 0.08);
}
.emp-composer textarea {
  width: 100%;
  box-sizing: border-box;
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.14);
  background: rgba(0, 0, 0, 0.35);
  color: inherit;
  padding: 0.5rem 0.65rem;
  resize: vertical;
  font: inherit;
}
.emp-composer__foot {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 0.5rem;
  gap: 0.75rem;
}
.emp-btn {
  padding: 0.45rem 0.9rem;
  border-radius: 8px;
  border: none;
  background: rgba(99, 102, 241, 0.9);
  color: #fff;
  font-weight: 600;
  cursor: pointer;
}
.emp-btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}
.emp-btn--ghost {
  background: rgba(255, 255, 255, 0.08);
  color: rgba(255, 255, 255, 0.88);
}
.emp-btn--inline {
  margin-left: 0.35rem;
  padding: 0.25rem 0.55rem;
  font-size: 0.82rem;
  vertical-align: baseline;
}
.emp-muted {
  color: rgba(255, 255, 255, 0.45);
  font-size: 0.85rem;
}
.emp-muted--hint {
  margin-bottom: 0.5rem;
  font-size: 0.8rem;
  line-height: 1.4;
}
.emp-chat__err {
  color: #f87171;
  font-size: 0.88rem;
  margin: 0.25rem 0;
}
.emp-chat__empty {
  color: rgba(255, 255, 255, 0.45);
  padding: 2rem 1rem;
  text-align: center;
}
</style>
