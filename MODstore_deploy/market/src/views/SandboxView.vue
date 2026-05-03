<template>
  <div class="sandbox-page">
    <div class="sandbox-toolbar">
      <div class="toolbar-left">
        <span class="toolbar-label">宿主地址</span>
        <input
          v-model="hostUrl"
          class="toolbar-input"
          placeholder="http://127.0.0.1:8000"
          @keydown.enter="connect"
        />
        <button class="btn btn-connect" :disabled="connecting" @click="connect">
          {{ connecting ? '连接中...' : connected ? '已连接' : '连接' }}
        </button>
        <span v-if="statusText" class="status-chip" :class="statusClass">{{ statusText }}</span>
      </div>
      <div class="toolbar-right">
        <button class="btn btn-action" :disabled="!connected || pushing" @click="pushAndTest">
          {{ pushing ? '推送中...' : '推送当前 Mod 并测试' }}
        </button>
        <button class="btn btn-action" :disabled="!connected" @click="openFullscreen">全屏</button>
      </div>
    </div>

    <div v-if="connected" class="sandbox-iframe-wrap">
      <iframe
        ref="iframeRef"
        :src="iframeSrc"
        class="sandbox-iframe"
        allow="clipboard-read; clipboard-write"
      />
    </div>
    <div v-else class="sandbox-placeholder">
      <div class="placeholder-icon">
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
          <rect x="2" y="3" width="20" height="14" rx="2" ry="2" />
          <line x1="8" y1="21" x2="16" y2="21" />
          <line x1="12" y1="17" x2="12" y2="21" />
        </svg>
      </div>
      <p class="placeholder-text">输入 FHD/XCAGI 宿主地址并点击「连接」</p>
      <p class="placeholder-hint">宿主需要处于运行状态，如 http://127.0.0.1:8000</p>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useRoute } from 'vue-router'
import { sandboxApi } from '../application/sandboxApi'

const route = useRoute()

const hostUrl = ref('http://127.0.0.1:8000')
const connected = ref(false)
const connecting = ref(false)
const pushing = ref(false)
const hostInfo = ref(null)
const iframeRef = ref(null)

const statusText = computed(() => {
  if (connected.value) return '已连接'
  if (connecting.value) return '连接中'
  return ''
})

const statusClass = computed(() => {
  return connected.value ? 'status-ok' : 'status-pending'
})

const iframeSrc = computed(() => {
  if (!connected.value || !hostUrl.value) return ''
  const base = hostUrl.value.replace(/\/+$/, '')
  return `${base}/?sandbox=1`
})

async function connect() {
  if (connecting.value) return
  connecting.value = true
  connected.value = false
  hostInfo.value = null
  try {
    const result = await sandboxApi.connectHost(hostUrl.value)
    if (result.ok) {
      connected.value = true
      hostInfo.value = result
    }
  } catch (e) {
    console.warn('[Sandbox] 连接失败:', e)
  } finally {
    connecting.value = false
  }
}

async function pushAndTest() {
  if (!connected.value || pushing.value) return
  const modId = route.query.modId || route.params.modId
  if (!modId) {
    console.warn('[Sandbox] 未指定 modId，跳过推送')
    return
  }
  pushing.value = true
  try {
    const result = await sandboxApi.pushAndTest(hostUrl.value, String(modId))
    if (result.ok && iframeRef.value) {
      iframeRef.value.contentWindow?.postMessage(
        { type: 'sandbox:navigate', path: `/mod/${modId}` },
        '*'
      )
    }
  } catch (e) {
    console.warn('[Sandbox] 推送失败:', e)
  } finally {
    pushing.value = false
  }
}

function openFullscreen() {
  if (!iframeRef.value) return
  const el = iframeRef.value
  if (el.requestFullscreen) el.requestFullscreen()
  else if (el.webkitRequestFullscreen) el.webkitRequestFullscreen()
}

let messageHandler = null

onMounted(() => {
  const queryHost = route.query.host
  if (queryHost) {
    hostUrl.value = String(queryHost)
  }
  messageHandler = (e) => {
    if (e.data?.type === 'sandbox:ready') {
      console.log('[Sandbox] FHD 宿主已就绪')
    }
  }
  window.addEventListener('message', messageHandler)

  if (hostUrl.value) {
    void connect()
  }
})

onBeforeUnmount(() => {
  if (messageHandler) {
    window.removeEventListener('message', messageHandler)
    messageHandler = null
  }
})
</script>

<style scoped>
.sandbox-page {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
}

.sandbox-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 8px 16px;
  background: var(--color-bg-elevated, #1a1a1a);
  border-bottom: 0.5px solid var(--color-border-subtle, rgba(255, 255, 255, 0.1));
  flex-shrink: 0;
  flex-wrap: wrap;
}

.toolbar-left,
.toolbar-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.toolbar-label {
  font-size: 0.85rem;
  color: var(--color-text-muted, rgba(255, 255, 255, 0.55));
  white-space: nowrap;
}

.toolbar-input {
  width: 260px;
  padding: 6px 10px;
  border: 0.5px solid var(--color-border-subtle, rgba(255, 255, 255, 0.15));
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.03);
  color: var(--color-text-primary, #fff);
  font-size: 0.85rem;
  outline: none;
  transition: border-color 0.2s;
}

.toolbar-input:focus {
  border-color: rgba(255, 255, 255, 0.3);
}

.toolbar-input::placeholder {
  color: rgba(255, 255, 255, 0.3);
}

.btn {
  padding: 6px 14px;
  border-radius: 6px;
  font-size: 0.85rem;
  cursor: pointer;
  border: 0.5px solid rgba(255, 255, 255, 0.15);
  background: rgba(255, 255, 255, 0.06);
  color: var(--color-text-primary, #fff);
  transition: all 0.2s;
  white-space: nowrap;
}

.btn:hover:not(:disabled) {
  background: rgba(255, 255, 255, 0.1);
}

.btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.btn-connect {
  background: rgba(96, 165, 250, 0.15);
  color: #60a5fa;
  border-color: rgba(96, 165, 250, 0.3);
}

.btn-connect:hover:not(:disabled) {
  background: rgba(96, 165, 250, 0.25);
}

.btn-action {
  background: rgba(74, 222, 128, 0.12);
  color: #4ade80;
  border-color: rgba(74, 222, 128, 0.25);
}

.btn-action:hover:not(:disabled) {
  background: rgba(74, 222, 128, 0.2);
}

.status-chip {
  font-size: 0.75rem;
  padding: 2px 8px;
  border-radius: 999px;
  font-weight: 600;
}

.status-ok {
  color: #4ade80;
  background: rgba(74, 222, 128, 0.1);
}

.status-pending {
  color: #fbbf24;
  background: rgba(251, 191, 36, 0.1);
}

.sandbox-iframe-wrap {
  flex: 1 1 0%;
  min-height: 0;
  position: relative;
}

.sandbox-iframe {
  width: 100%;
  height: 100%;
  border: none;
  display: block;
}

.sandbox-placeholder {
  flex: 1 1 0%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
  color: var(--color-text-muted, rgba(255, 255, 255, 0.4));
}

.placeholder-icon {
  opacity: 0.4;
}

.placeholder-text {
  font-size: 1rem;
  font-weight: 500;
}

.placeholder-hint {
  font-size: 0.85rem;
  opacity: 0.6;
}

@media (max-width: 768px) {
  .sandbox-toolbar {
    flex-direction: column;
    align-items: stretch;
    gap: 8px;
  }
  .toolbar-left,
  .toolbar-right {
    flex-wrap: wrap;
  }
  .toolbar-input {
    width: 100%;
  }
}
</style>
