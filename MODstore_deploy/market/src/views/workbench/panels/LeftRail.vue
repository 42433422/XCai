<script setup lang="ts">
import { ref, nextTick } from 'vue'
import { useWorkbenchStore } from '../../../stores/workbench'
import { useAgentLoop } from '../../../composables/useAgentLoop'
import { getAccessToken } from '../../../infrastructure/storage/tokenStore'
import type { AgentRun } from '../../../stores/workbench'

const store = useWorkbenchStore()
const agentLoop = useAgentLoop()

// ── View toggle ────────────────────────────────────────────────────────────
type RailView = 'chat' | 'agent'
const view = ref<RailView>('chat')

// ── Chat ───────────────────────────────────────────────────────────────────
const chatInput = ref('')
const chatScrollRef = ref<HTMLElement | null>(null)

async function sendChat() {
  const text = chatInput.value.trim()
  if (!text || store.chatStreaming) return
  chatInput.value = ''

  const userId = 'u-' + Date.now()
  store.pushChatMessage({ id: userId, role: 'user', content: text, ts: Date.now() })

  const assistantId = 'a-' + Date.now()
  store.pushChatMessage({ id: assistantId, role: 'assistant', content: '', ts: Date.now() })
  await scrollToBottom()

  const ctrl = new AbortController()
  store.setChatStreaming(true, ctrl)

  try {
    const token = getAccessToken()
    const headers: Record<string, string> = { 'Content-Type': 'application/json' }
    if (token) headers['Authorization'] = `Bearer ${token}`

    const resp = await fetch('/api/llm/chat/stream', {
      method: 'POST',
      headers,
      body: JSON.stringify({
        messages: store.chatMessages
          .filter((m) => m.role !== 'system')
          .map((m) => ({ role: m.role, content: m.content })),
      }),
      signal: ctrl.signal,
    })

    if (!resp.ok || !resp.body) {
      store.appendChatChunk(assistantId, '\n\n*[请求失败]*')
      store.setChatStreaming(false, null)
      return
    }

    const reader = resp.body.getReader()
    const dec = new TextDecoder()
    let buf = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buf += dec.decode(value, { stream: true })
      const lines = buf.split('\n')
      buf = lines.pop() ?? ''
      for (const line of lines) {
        if (!line.startsWith('data: ')) continue
        const raw = line.slice(6).trim()
        if (raw === '[DONE]') continue
        try {
          const obj = JSON.parse(raw)
          const delta = obj?.choices?.[0]?.delta?.content
            ?? obj?.delta?.content
            ?? obj?.content
            ?? ''
          if (delta) {
            store.appendChatChunk(assistantId, delta)
            await scrollToBottom()
          }
        } catch { /* ignore */ }
      }
    }
  } catch (e: unknown) {
    if ((e as Error)?.name !== 'AbortError') {
      store.appendChatChunk(assistantId, '\n\n*[连接中断]*')
    }
  } finally {
    store.setChatStreaming(false, null)
  }
}

async function scrollToBottom() {
  await nextTick()
  if (chatScrollRef.value) {
    chatScrollRef.value.scrollTop = chatScrollRef.value.scrollHeight
  }
}

function onChatKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    sendChat()
  }
}

// ── Agent triggers ─────────────────────────────────────────────────────────

const agentInput = ref('')
const agentRunning = ref(false)
let currentAbort: (() => void) | null = null

async function runAgentDraft() {
  const brief = agentInput.value.trim()
  if (!brief || agentRunning.value) return
  agentRunning.value = true
  agentInput.value = ''
  view.value = 'agent'

  const { abort } = await agentLoop.runEmployeeDraft(brief)
  currentAbort = abort
  agentRunning.value = false
}

function abortCurrentRun() {
  currentAbort?.()
  currentAbort = null
  agentRunning.value = false
}

function applyRunManifest(run: AgentRun) {
  if (!run.manifest) return
  store.setTarget(store.target.kind, store.target.id, run.manifest as Record<string, unknown>, store.target.name)
}

function formatTs(ts: number) {
  return new Date(ts).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

// ── Suggested prompts ──────────────────────────────────────────────────────
const SUGGESTED = [
  '帮我创建一个电话客服员工，专注售后问题处理',
  '创建一个数据分析员工，能处理 CSV 并生成报表',
  '设计一个全能型 AI 助手，支持图文理解和对话',
]

function useSuggestion(s: string) {
  agentInput.value = s
}
</script>

<template>
  <div class="left-rail">
    <!-- Tab bar -->
    <div class="lr-tabs">
      <button class="lr-tab" :class="{ 'lr-tab--active': view === 'chat' }" @click="view = 'chat'">
        <span class="lr-tab-icon">💬</span> 对话
      </button>
      <button class="lr-tab" :class="{ 'lr-tab--active': view === 'agent' }" @click="view = 'agent'">
        <span class="lr-tab-icon">⚡</span> Agent
        <span v-if="store.agentRuns.length" class="lr-tab-badge">{{ store.agentRuns.length }}</span>
      </button>
    </div>

    <!-- ── Chat panel ─────────────────────────────────────────────────── -->
    <div v-if="view === 'chat'" class="lr-pane chat-pane">
      <div ref="chatScrollRef" class="chat-messages">
        <div v-if="!store.chatMessages.length" class="chat-empty">
          <p class="chat-empty-title">AI 工作台助手</p>
          <p class="chat-empty-sub">问我任何关于员工设计、模块配置、发布流程的问题</p>
          <div class="chat-suggestions">
            <button
              v-for="s in SUGGESTED"
              :key="s"
              class="chat-suggestion"
              @click="useSuggestion(s)"
            >
              {{ s }}
            </button>
          </div>
        </div>

        <div
          v-for="msg in store.chatMessages"
          :key="msg.id"
          class="chat-msg"
          :class="`chat-msg--${msg.role}`"
        >
          <span class="chat-msg__avatar">{{ msg.role === 'user' ? '你' : 'AI' }}</span>
          <div class="chat-msg__body">
            <span class="chat-msg__ts">{{ formatTs(msg.ts) }}</span>
            <p class="chat-msg__text" v-html="msg.content.replace(/\n/g, '<br>')"></p>
          </div>
        </div>
      </div>

      <form class="chat-input-row" @submit.prevent="sendChat">
        <textarea
          v-model="chatInput"
          class="chat-input"
          placeholder="输入问题，Shift+Enter 换行..."
          rows="2"
          :disabled="store.chatStreaming"
          @keydown="onChatKeydown"
        />
        <button type="submit" class="chat-send" :disabled="store.chatStreaming || !chatInput.trim()">
          {{ store.chatStreaming ? '…' : '发送' }}
        </button>
      </form>
    </div>

    <!-- ── Agent panel ────────────────────────────────────────────────── -->
    <div v-else class="lr-pane agent-pane">
      <!-- Agent input -->
      <div class="agent-input-area">
        <textarea
          v-model="agentInput"
          class="agent-input"
          placeholder="用一句话描述你想创建的员工，AI 将自动生成完整配置…"
          rows="3"
          :disabled="agentRunning"
        />
        <div class="agent-input-actions">
          <button
            v-if="!agentRunning"
            class="agent-run-btn"
            :disabled="!agentInput.trim()"
            @click="runAgentDraft"
          >
            ▶ 生成员工
          </button>
          <button v-else class="agent-abort-btn" @click="abortCurrentRun">
            ◼ 停止
          </button>
        </div>
        <div class="agent-suggestions">
          <button v-for="s in SUGGESTED" :key="s" class="agent-suggestion" @click="useSuggestion(s)">
            {{ s }}
          </button>
        </div>
      </div>

      <!-- Runs timeline -->
      <div class="agent-runs">
        <div v-if="!store.agentRuns.length" class="agent-empty">
          还没有 Agent 运行记录。填写描述后点击「生成员工」开始。
        </div>

        <div v-for="run in store.agentRuns" :key="run.id" class="agent-run">
          <div class="agent-run__header">
            <span class="agent-run__brief">{{ run.brief }}</span>
            <span class="agent-run__ts">{{ formatTs(run.startedAt) }}</span>
            <span class="agent-run__status" :class="`agent-run__status--${run.status}`">
              {{ run.status === 'running' ? '运行中' : run.status === 'done' ? '完成' : run.status === 'error' ? '失败' : '空闲' }}
            </span>
          </div>

          <!-- Events timeline -->
          <div class="agent-run__events">
            <div
              v-for="ev in run.events"
              :key="ev.id"
              class="agent-event"
              :class="`agent-event--${ev.status}`"
            >
              <span class="agent-event__dot"></span>
              <div class="agent-event__body">
                <span class="agent-event__label">{{ ev.label }}</span>
                <span v-if="ev.status === 'running'" class="agent-event__pulse">●</span>
                <span v-else-if="ev.status === 'done'" class="agent-event__check">✓</span>
                <span v-else-if="ev.status === 'error'" class="agent-event__err">✕</span>
              </div>
            </div>
          </div>

          <!-- Apply to canvas button -->
          <div v-if="run.manifest && run.status === 'done'" class="agent-run__apply">
            <button class="agent-apply-btn" @click="applyRunManifest(run)">
              ↗ 应用到画布
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.left-rail {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
  background: rgba(8, 15, 26, 0.98);
}

/* Tabs */
.lr-tabs {
  display: flex;
  border-bottom: 1px solid rgba(148, 163, 184, 0.1);
  flex-shrink: 0;
}

.lr-tab {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 5px;
  padding: 10px 8px;
  background: transparent;
  border: none;
  color: #64748b;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s ease;
  position: relative;
}

.lr-tab:hover { color: #94a3b8; }

.lr-tab--active {
  color: #a5b4fc;
  border-bottom: 2px solid #6366f1;
}

.lr-tab-icon { font-size: 13px; }

.lr-tab-badge {
  background: #6366f1;
  color: #fff;
  font-size: 9px;
  font-weight: 700;
  padding: 1px 5px;
  border-radius: 999px;
  min-width: 16px;
  text-align: center;
}

/* Pane */
.lr-pane {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* ── Chat ── */
.chat-pane { gap: 0; }

.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  scrollbar-width: thin;
  scrollbar-color: rgba(99, 102, 241, 0.3) transparent;
}

.chat-empty {
  margin: auto;
  text-align: center;
  padding: 16px;
}

.chat-empty-title {
  font-size: 15px;
  font-weight: 700;
  color: #e2e8f0;
  margin: 0 0 6px;
}

.chat-empty-sub {
  font-size: 12px;
  color: #64748b;
  margin: 0 0 14px;
}

.chat-suggestions {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.chat-suggestion {
  background: rgba(99, 102, 241, 0.08);
  border: 1px solid rgba(99, 102, 241, 0.2);
  color: #94a3b8;
  font-size: 11px;
  padding: 7px 10px;
  border-radius: 8px;
  cursor: pointer;
  text-align: left;
  transition: all 0.15s ease;
  line-height: 1.4;
}

.chat-suggestion:hover {
  background: rgba(99, 102, 241, 0.15);
  color: #c7d2fe;
  border-color: rgba(99, 102, 241, 0.35);
}

.chat-msg {
  display: flex;
  gap: 8px;
  align-items: flex-start;
}

.chat-msg--user { flex-direction: row-reverse; }

.chat-msg__avatar {
  width: 26px;
  height: 26px;
  border-radius: 50%;
  background: rgba(99, 102, 241, 0.2);
  border: 1px solid rgba(99, 102, 241, 0.3);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 10px;
  font-weight: 700;
  color: #a5b4fc;
  flex-shrink: 0;
}

.chat-msg--user .chat-msg__avatar {
  background: rgba(16, 185, 129, 0.15);
  border-color: rgba(16, 185, 129, 0.3);
  color: #6ee7b7;
}

.chat-msg__body {
  max-width: calc(100% - 36px);
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.chat-msg--user .chat-msg__body { align-items: flex-end; }

.chat-msg__ts {
  font-size: 9px;
  color: #475569;
  font-variant-numeric: tabular-nums;
}

.chat-msg__text {
  background: rgba(15, 23, 42, 0.8);
  border: 1px solid rgba(148, 163, 184, 0.1);
  border-radius: 10px;
  padding: 8px 11px;
  font-size: 13px;
  color: #e2e8f0;
  line-height: 1.55;
  margin: 0;
  word-break: break-word;
}

.chat-msg--user .chat-msg__text {
  background: rgba(99, 102, 241, 0.12);
  border-color: rgba(99, 102, 241, 0.2);
}

.chat-input-row {
  display: flex;
  gap: 6px;
  padding: 10px;
  border-top: 1px solid rgba(148, 163, 184, 0.08);
  flex-shrink: 0;
}

.chat-input {
  flex: 1;
  background: rgba(15, 23, 42, 0.8);
  border: 1px solid rgba(148, 163, 184, 0.12);
  border-radius: 10px;
  color: #e2e8f0;
  font-size: 13px;
  padding: 8px 10px;
  resize: none;
  outline: none;
  font-family: inherit;
  line-height: 1.5;
  transition: border-color 0.15s ease;
}

.chat-input:focus { border-color: rgba(99, 102, 241, 0.4); }

.chat-send {
  background: #6366f1;
  border: none;
  border-radius: 10px;
  color: #fff;
  font-size: 12px;
  font-weight: 700;
  padding: 0 14px;
  cursor: pointer;
  transition: all 0.15s ease;
  flex-shrink: 0;
}

.chat-send:hover:not(:disabled) { background: #818cf8; }

.chat-send:disabled { opacity: 0.4; cursor: not-allowed; }

/* ── Agent ── */
.agent-pane {
  overflow: hidden;
  gap: 0;
}

.agent-input-area {
  padding: 12px;
  border-bottom: 1px solid rgba(148, 163, 184, 0.08);
  flex-shrink: 0;
}

.agent-input {
  width: 100%;
  background: rgba(15, 23, 42, 0.8);
  border: 1px solid rgba(148, 163, 184, 0.12);
  border-radius: 10px;
  color: #e2e8f0;
  font-size: 13px;
  padding: 9px 11px;
  resize: none;
  outline: none;
  font-family: inherit;
  line-height: 1.5;
  box-sizing: border-box;
}

.agent-input:focus { border-color: rgba(99, 102, 241, 0.4); }

.agent-input-actions {
  display: flex;
  justify-content: flex-end;
  margin-top: 8px;
  gap: 6px;
}

.agent-run-btn {
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
  border: none;
  border-radius: 9px;
  color: #fff;
  font-size: 12px;
  font-weight: 700;
  padding: 7px 16px;
  cursor: pointer;
  transition: all 0.15s ease;
  letter-spacing: 0.02em;
}

.agent-run-btn:hover:not(:disabled) {
  background: linear-gradient(135deg, #818cf8, #a78bfa);
  transform: translateY(-1px);
}

.agent-run-btn:disabled { opacity: 0.4; cursor: not-allowed; }

.agent-abort-btn {
  background: rgba(239, 68, 68, 0.15);
  border: 1px solid rgba(239, 68, 68, 0.3);
  border-radius: 9px;
  color: #f87171;
  font-size: 12px;
  font-weight: 700;
  padding: 7px 16px;
  cursor: pointer;
  animation: pulse-red 1s ease infinite;
}

@keyframes pulse-red {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.65; }
}

.agent-suggestions {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-top: 8px;
}

.agent-suggestion {
  background: rgba(99, 102, 241, 0.06);
  border: 1px solid rgba(99, 102, 241, 0.15);
  color: #64748b;
  font-size: 10px;
  padding: 5px 9px;
  border-radius: 7px;
  cursor: pointer;
  text-align: left;
  transition: all 0.12s ease;
}

.agent-suggestion:hover {
  background: rgba(99, 102, 241, 0.12);
  color: #94a3b8;
}

.agent-runs {
  flex: 1;
  overflow-y: auto;
  padding: 10px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  scrollbar-width: thin;
  scrollbar-color: rgba(99, 102, 241, 0.3) transparent;
}

.agent-empty {
  color: #475569;
  font-size: 12px;
  text-align: center;
  margin: auto;
  padding: 20px;
  line-height: 1.6;
}

.agent-run {
  background: rgba(15, 23, 42, 0.7);
  border: 1px solid rgba(148, 163, 184, 0.1);
  border-radius: 12px;
  padding: 10px 12px;
}

.agent-run__header {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  margin-bottom: 8px;
  flex-wrap: wrap;
}

.agent-run__brief {
  flex: 1;
  font-size: 12px;
  color: #e2e8f0;
  font-weight: 500;
  line-height: 1.4;
  min-width: 0;
  word-break: break-word;
}

.agent-run__ts {
  font-size: 9px;
  color: #475569;
  flex-shrink: 0;
  font-variant-numeric: tabular-nums;
}

.agent-run__status {
  font-size: 9px;
  font-weight: 700;
  padding: 2px 7px;
  border-radius: 999px;
  flex-shrink: 0;
}

.agent-run__status--running {
  background: rgba(99, 102, 241, 0.15);
  color: #a5b4fc;
  border: 1px solid rgba(99, 102, 241, 0.25);
  animation: pulse-blue 1.2s ease infinite;
}

@keyframes pulse-blue {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.6; }
}

.agent-run__status--done {
  background: rgba(16, 185, 129, 0.12);
  color: #6ee7b7;
  border: 1px solid rgba(16, 185, 129, 0.2);
}

.agent-run__status--error {
  background: rgba(239, 68, 68, 0.12);
  color: #fca5a5;
  border: 1px solid rgba(239, 68, 68, 0.2);
}

.agent-run__events {
  display: flex;
  flex-direction: column;
  gap: 3px;
  margin-left: 4px;
  border-left: 1px solid rgba(148, 163, 184, 0.1);
  padding-left: 10px;
}

.agent-event {
  display: flex;
  align-items: center;
  gap: 7px;
  padding: 2px 0;
}

.agent-event__dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  flex-shrink: 0;
  margin-left: -13px;
  background: rgba(100, 116, 139, 0.4);
}

.agent-event--running .agent-event__dot { background: #6366f1; animation: pulse-blue 0.8s ease infinite; }
.agent-event--done .agent-event__dot { background: #10b981; }
.agent-event--error .agent-event__dot { background: #ef4444; }

.agent-event__body {
  display: flex;
  align-items: center;
  gap: 5px;
  flex: 1;
}

.agent-event__label {
  font-size: 11px;
  color: #94a3b8;
  flex: 1;
}

.agent-event--running .agent-event__label { color: #c7d2fe; }
.agent-event--done .agent-event__label { color: #6ee7b7; }
.agent-event--error .agent-event__label { color: #fca5a5; }

.agent-event__pulse {
  color: #6366f1;
  font-size: 8px;
  animation: pulse-blue 0.6s ease infinite;
}

.agent-event__check { color: #10b981; font-size: 11px; font-weight: 700; }
.agent-event__err { color: #ef4444; font-size: 11px; font-weight: 700; }

.agent-run__apply {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid rgba(148, 163, 184, 0.08);
}

.agent-apply-btn {
  width: 100%;
  background: rgba(16, 185, 129, 0.1);
  border: 1px solid rgba(16, 185, 129, 0.25);
  color: #6ee7b7;
  font-size: 12px;
  font-weight: 700;
  padding: 7px 12px;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.15s ease;
}

.agent-apply-btn:hover {
  background: rgba(16, 185, 129, 0.18);
  border-color: rgba(16, 185, 129, 0.4);
}
</style>
