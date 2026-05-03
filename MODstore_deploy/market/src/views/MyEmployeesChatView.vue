<template>
  <div class="emp-chat">
    <header class="emp-chat__head">
      <h1>我的员工</h1>
      <p class="emp-chat__sub">从已登记的员工包中选择一名，通过服务端执行管道对话（调用 <code class="emp-mono">/api/employees</code>）。</p>
      <button type="button" class="emp-btn emp-btn--ghost" :disabled="loadingList" @click="loadEmployees">
        {{ loadingList ? '加载中…' : '刷新列表' }}
      </button>
    </header>

    <div class="emp-chat__layout">
      <aside class="emp-chat__side">
        <h2>员工列表</h2>
        <p v-if="listError" class="emp-chat__err">{{ listError }}</p>
        <p v-else-if="!employees.length && !loadingList" class="emp-muted">暂无可用员工包。请先在 Mod 制作或员工制作中登记 employee_pack。</p>
        <ul v-else class="emp-list">
          <li v-for="e in employees" :key="e.id">
            <button
              type="button"
              class="emp-list__btn"
              :class="{ 'emp-list__btn--active': e.id === selectedId }"
              @click="selectEmployee(e.id)"
            >
              <span class="emp-list__name">{{ e.name || e.id }}</span>
              <span class="emp-list__id">{{ e.id }}</span>
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
import { ref, onMounted } from 'vue'
import { api } from '../api'

type EmployeeRow = { id: string; name?: string }

const employees = ref<EmployeeRow[]>([])
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
    employees.value = Array.isArray(rows) ? (rows as EmployeeRow[]) : []
  } catch (e: unknown) {
    listError.value = e instanceof Error ? e.message : String(e)
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
.emp-list__btn {
  width: 100%;
  text-align: left;
  padding: 0.5rem 0.6rem;
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  background: rgba(0, 0, 0, 0.25);
  color: inherit;
  cursor: pointer;
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
.emp-muted {
  color: rgba(255, 255, 255, 0.45);
  font-size: 0.85rem;
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
