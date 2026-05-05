<template>
  <div
    ref="panelRef"
    class="butler-panel"
    :style="panelStyle"
    role="dialog"
    aria-label="AI 数字管家"
    aria-modal="false"
  >
    <!-- 顶栏（可拖拽）-->
    <header
      class="panel-head"
      @pointerdown="onHeaderPointerDown"
      @pointermove="onHeaderPointerMove"
      @pointerup="onHeaderPointerUp"
    >
      <div class="panel-head__left">
        <span class="panel-head__mark">AI</span>
        <div class="panel-head__titles">
          <span class="panel-head__title">数字管家</span>
          <span class="panel-head__sub">当前页面助手</span>
        </div>
      </div>
      <div class="panel-head__actions" @pointerdown.stop>
        <button
          type="button"
          class="panel-icon-btn"
          aria-label="查看操作日志"
          title="操作日志"
          @click.stop="showLog = !showLog"
        >
          <svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M9 12h6M9 8h6M9 16h4" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/><rect x="3" y="4" width="18" height="16" rx="3" stroke="currentColor" stroke-width="1.6"/></svg>
        </button>
        <button
          type="button"
          class="panel-icon-btn"
          aria-label="清空对话"
          title="清空对话"
          @click.stop="agentStore.clearMessages()"
        >
          <svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M3 6h18M8 6V4h8v2M19 6l-1 14H6L5 6" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>
        </button>
        <button
          type="button"
          class="panel-icon-btn"
          aria-label="关闭管家"
          title="关闭"
          @click.stop="agentStore.closePanel()"
        >
          <span aria-hidden="true">×</span>
        </button>
      </div>
    </header>

    <!-- 状态条 -->
    <AgentStatusBar :mode="mode" @stop="agentStore.setMode('idle')" />

    <!-- 操作日志抽屉 -->
    <div v-if="showLog" class="panel-log">
      <div class="panel-log__title">操作日志</div>
      <div v-if="!actionLog.length" class="panel-log__empty">暂无操作记录</div>
      <div v-for="(entry, i) in actionLog" :key="i" class="panel-log__entry">
        <span class="log-action">{{ entry.action }}</span>
        <span class="log-label">{{ entry.label }}</span>
        <span :class="['log-status', entry.success ? 'log-status--ok' : 'log-status--err']">
          {{ entry.success ? '成功' : '失败' }}
        </span>
      </div>
    </div>

    <!-- 对话区 -->
    <AgentChatHistory @quick="handleQuick" />

    <!-- 输入区 -->
    <footer class="panel-foot">
      <AgentVoiceInput
        :voice-state="voiceState"
        :is-supported="voiceIsSupported"
        :error="voiceError"
        @toggle="toggleVoice"
      />
      <div class="panel-composer">
        <textarea
          ref="textareaRef"
          v-model="draft"
          class="panel-input"
          placeholder="说点什么…"
          rows="1"
          aria-label="发送消息"
          @keydown.enter.exact.prevent="sendText"
          @input="autoResize"
        />
        <button
          type="button"
          class="panel-send"
          :disabled="!draft.trim() || agentStore.isLoading"
          aria-label="发送"
          @click="sendText"
        >
          <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <path d="M22 2L11 13M22 2L15 22l-4-9-9-4 20-7z" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
        </button>
      </div>
      <label class="panel-screenshot-toggle" title="是否附带截图发给 AI（需 vision 模型）">
        <input v-model="withScreenshot" type="checkbox" />
        <span>附带截图</span>
      </label>
    </footer>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, nextTick } from 'vue'
import { storeToRefs } from 'pinia'
import { useAgentStore } from '../../stores/agent'
import { useAgentEngine } from '../../composables/agent/useAgentEngine'
import { useVoiceInput } from '../../composables/agent/useVoiceInput'
import { getActionLog } from '../../composables/agent/useActionExecutor'
import AgentStatusBar from './AgentStatusBar.vue'
import AgentChatHistory from './AgentChatHistory.vue'
import AgentVoiceInput from './AgentVoiceInput.vue'

const agentStore = useAgentStore()
const { mode, position } = storeToRefs(agentStore)

const { handleInput } = useAgentEngine()

const draft = ref('')
const withScreenshot = ref(false)
const showLog = ref(false)
const textareaRef = ref<HTMLTextAreaElement | null>(null)
const panelRef = ref<HTMLDivElement | null>(null)

const actionLog = computed(() => getActionLog().slice().reverse())

// 面板定位：始终在球的上方
const panelStyle = computed(() => {
  const bx = position.value.x
  const by = position.value.y
  const panelW = 340
  const panelH = 460
  const margin = 12

  let left = bx + 32 - panelW / 2
  let top = by - panelH - margin

  // 边界保护
  left = Math.max(8, Math.min(window.innerWidth - panelW - 8, left))
  top = Math.max(8, Math.min(window.innerHeight - panelH - 8, top))

  return {
    left: `${left}px`,
    top: `${top}px`,
    width: `${panelW}px`,
    height: `${panelH}px`,
  }
})

// 面板拖拽
let panelDragStartX = 0
let panelDragStartY = 0
let isPanelDragging = false

function onHeaderPointerDown(e: PointerEvent) {
  if (e.button !== 0) return
  isPanelDragging = true
  panelDragStartX = e.clientX
  panelDragStartY = e.clientY
  ;(e.currentTarget as HTMLElement).setPointerCapture(e.pointerId)
}

function onHeaderPointerMove(e: PointerEvent) {
  if (!isPanelDragging) return
  const dx = e.clientX - panelDragStartX
  const dy = e.clientY - panelDragStartY
  panelDragStartX = e.clientX
  panelDragStartY = e.clientY
  agentStore.savePosition(position.value.x + dx, position.value.y + dy)
}

function onHeaderPointerUp() {
  isPanelDragging = false
}

// 语音输入
const { state: voiceState, error: voiceError, isSupported: voiceIsSupported, startListening, stopAll: stopVoice, speak } =
  useVoiceInput(async (text: string) => {
    await sendMessage(text)
    // 读取 last assistant message 朗读
    const msgs = agentStore.messages
    const last = msgs[msgs.length - 1]
    if (last && last.role === 'assistant' && !last.isLoading) {
      await speak(last.content)
    }
  })

function toggleVoice() {
  if (voiceState.value === 'listening') {
    stopVoice()
  } else {
    startListening()
  }
}

async function sendText() {
  const text = draft.value.trim()
  if (!text) return
  draft.value = ''
  await nextTick()
  autoResize()
  await sendMessage(text)
}

async function sendMessage(text: string) {
  await handleInput(text, { withScreenshot: withScreenshot.value })
}

async function handleQuick(text: string) {
  await sendMessage(text)
}

function autoResize() {
  const ta = textareaRef.value
  if (!ta) return
  ta.style.height = 'auto'
  ta.style.height = Math.min(ta.scrollHeight, 80) + 'px'
}
</script>

<style scoped>
.butler-panel {
  position: fixed;
  z-index: 11010;
  background: rgba(10, 11, 15, 0.98);
  border: 1px solid rgba(255, 255, 255, 0.10);
  border-radius: 14px;
  box-shadow:
    0 18px 54px rgba(0, 0, 0, 0.58),
    0 0 0 1px rgba(255, 255, 255, 0.03);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  backdrop-filter: blur(14px);
}

.panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-height: 46px;
  padding: 8px 10px 8px 12px;
  cursor: grab;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  user-select: none;
}

.panel-head:active { cursor: grabbing; }

.panel-head__left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.panel-head__mark {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.10);
  color: rgba(255, 255, 255, 0.78);
  font-size: 0.72rem;
  font-weight: 800;
  letter-spacing: 0.04em;
}

.panel-head__titles {
  display: flex;
  flex-direction: column;
  gap: 1px;
}

.panel-head__title {
  font-size: 0.86rem;
  font-weight: 700;
  color: rgba(255, 255, 255, 0.9);
  letter-spacing: 0.02em;
}

.panel-head__sub {
  font-size: 0.68rem;
  color: rgba(255, 255, 255, 0.36);
}

.panel-head__actions {
  display: flex;
  align-items: center;
  gap: 4px;
}

.panel-icon-btn {
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 6px;
  border: none;
  background: transparent;
  color: rgba(255, 255, 255, 0.36);
  cursor: pointer;
  font-size: 1.1rem;
  transition: all 0.15s;
}

.panel-icon-btn svg { width: 15px; height: 15px; }

.panel-icon-btn:hover {
  background: rgba(255, 255, 255, 0.06);
  color: rgba(255, 255, 255, 0.85);
}

/* 操作日志 */
.panel-log {
  padding: 8px 12px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  max-height: 120px;
  overflow-y: auto;
  background: rgba(255, 255, 255, 0.02);
}

.panel-log__title {
  font-size: 0.72rem;
  font-weight: 700;
  color: rgba(255, 255, 255, 0.4);
  margin-bottom: 4px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.panel-log__empty {
  font-size: 0.75rem;
  color: rgba(255, 255, 255, 0.25);
}

.panel-log__entry {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 0.73rem;
  color: rgba(255, 255, 255, 0.55);
  padding: 2px 0;
}

.log-action {
  color: #7dd3fc;
  font-weight: 600;
  flex-shrink: 0;
}

.log-label {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.log-status { flex-shrink: 0; font-weight: 600; }
.log-status--ok { color: #4ade80; }
.log-status--err { color: #f87171; }

/* 底部输入区 */
.panel-foot {
  padding: 8px 10px 10px;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.panel-composer {
  display: flex;
  align-items: flex-end;
  gap: 6px;
}

.panel-input {
  flex: 1;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 9px;
  padding: 8px 10px;
  font-size: 0.875rem;
  color: rgba(255, 255, 255, 0.88);
  resize: none;
  outline: none;
  line-height: 1.4;
  font-family: inherit;
  min-height: 36px;
  max-height: 80px;
  transition: border-color 0.15s;
}

.panel-input::placeholder { color: rgba(255, 255, 255, 0.25); }
.panel-input:focus { border-color: rgba(148, 163, 184, 0.38); }

.panel-send {
  width: 36px;
  height: 36px;
  border-radius: 9px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(59, 130, 246, 0.26);
  border: 1px solid rgba(96, 165, 250, 0.28);
  border: none;
  cursor: pointer;
  flex-shrink: 0;
  transition: all 0.15s;
}

.panel-send svg { width: 16px; height: 16px; color: #fff; }
.panel-send:hover:not(:disabled) { background: rgba(59, 130, 246, 0.38); }
.panel-send:disabled { opacity: 0.4; cursor: not-allowed; }

.panel-screenshot-toggle {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 0.72rem;
  color: rgba(255, 255, 255, 0.34);
  cursor: pointer;
  user-select: none;
  align-self: flex-end;
}

.panel-screenshot-toggle input { accent-color: #64748b; cursor: pointer; }
.panel-screenshot-toggle:hover { color: rgba(255, 255, 255, 0.55); }
</style>
