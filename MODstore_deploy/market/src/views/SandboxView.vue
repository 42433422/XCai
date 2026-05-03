<template>
  <div class="sandbox-page">
    <div class="sandbox-toolbar">
      <div class="toolbar-left">
        <span class="toolbar-label">自动匹配</span>
        <input
          v-model="hostUrl"
          class="toolbar-input"
          placeholder="可留空；将扫本机常见 API 端口"
          @keydown.enter="discoverAndConnect"
        />
        <button class="btn btn-connect" :disabled="connecting" @click="discoverAndConnect">
          {{ connecting ? '扫端口中…' : '重新扫描' }}
        </button>
        <span v-if="statusText" class="status-chip" :class="statusClass">{{ statusText }}</span>
        <span v-if="connectError" class="status-chip status-err" role="alert">{{ connectError }}</span>
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
      <p class="placeholder-text">正在本机与局域网自动扫描常见 API 端口并匹配 XCAGI / FHD</p>
      <p class="placeholder-hint">
        依次探测多端口（如 5000–5002、5173–5176、8000 等）；命中后写入上方；也可手动填根地址后回车或点「重新扫描」
      </p>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useRoute } from 'vue-router'
import { sandboxApi } from '../application/sandboxApi'
import { ApiError } from '../infrastructure/http/client'

const route = useRoute()

/** 上次成功连上的宿主 API 根，供下次优先探测 */
const SANDBOX_HOST_STORAGE = 'modstore_sandbox_last_host'

const hostUrl = ref('')
const connected = ref(false)
const connecting = ref(false)
const connectError = ref('')
const probeProgress = ref('')
const pushing = ref(false)
const hostInfo = ref(null)
const iframeRef = ref(null)

const statusText = computed(() => {
  if (connected.value) return '已匹配'
  if (connecting.value) {
    return probeProgress.value ? `扫端口 (${probeProgress.value})` : '扫端口中'
  }
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

function formatConnectFailure(e) {
  if (e instanceof ApiError) return e.message || `请求失败（${e.status}）`
  if (e && typeof e === 'object' && 'message' in e && typeof e.message === 'string') return e.message
  return String(e)
}

/** 规范为「协议 + host」，供 /api/health 探测 */
function normalizeHostOrigin(raw) {
  const t = String(raw || '').trim()
  if (!t) return ''
  try {
    const withProto = /^\w+:\/\//.test(t) ? t : `http://${t}`
    const u = new URL(withProto)
    return `${u.protocol}//${u.host}`
  } catch {
    return t.replace(/\/+$/, '')
  }
}

/**
 * 本机 / 局域网常见 XCAGI FastAPI 与联调端口（含 Vite 同机多实例）；顺序大致为默认 API 优先再 dev。
 * 每项为端口号，将拼成 http://127.0.0.1:{port} 与 http://localhost:{port}，并对当前页 hostname 复用。
 */
const LOCAL_PROBE_PORTS = [
  5000, 5001, 5002, 5003,
  5173, 5174, 5175, 5176, 5177,
  4173, 3000, 8080, 8888,
  8000, 8001,
]

function addHostPortVariants(add, hostname, ports, includeHttps) {
  const h = String(hostname || '').trim()
  if (!h) return
  for (const p of ports) {
    add(`http://${h}:${p}`)
    if (includeHttps) add(`https://${h}:${p}`)
  }
}

/** 合并去重：URL 参数 → 输入框 → 上次成功 → 当前页同机多端口扫描 → 127.0.0.1/localhost 端口表 */
function buildDiscoveryCandidates() {
  const seen = new Set()
  const out = []
  const add = (raw) => {
    const n = normalizeHostOrigin(raw)
    if (!n || seen.has(n)) return
    seen.add(n)
    out.push(n)
  }

  const q = route.query.host
  if (q) add(String(q))

  add(hostUrl.value)

  try {
    const s = localStorage.getItem(SANDBOX_HOST_STORAGE)
    if (s) add(s)
  } catch (_) {
    /* ignore */
  }

  /** 若 API 与当前页同端口（少见），优先尝试 */
  try {
    const p = String(window.location.port || '').trim()
    if (p && /^\d+$/.test(p) && p !== '80' && p !== '443') {
      add(`${window.location.protocol}//${window.location.hostname}:${p}`)
    }
  } catch (_) {
    /* ignore */
  }

  try {
    const { hostname, protocol } = window.location
    if (hostname && hostname !== 'localhost' && hostname !== '127.0.0.1') {
      addHostPortVariants(add, hostname, LOCAL_PROBE_PORTS, protocol === 'https:')
    }
  } catch (_) {
    /* ignore */
  }

  addHostPortVariants(add, '127.0.0.1', LOCAL_PROBE_PORTS, false)
  addHostPortVariants(add, 'localhost', LOCAL_PROBE_PORTS, false)

  return out
}

/** 依次尝试候选地址，成功则写入输入框并记住 */
async function discoverAndConnect() {
  if (connecting.value) return
  connecting.value = true
  connected.value = false
  hostInfo.value = null
  connectError.value = ''
  probeProgress.value = ''

  const list = buildDiscoveryCandidates()
  if (!list.length) {
    connectError.value = '请填写宿主 API 根地址（例如 http://127.0.0.1:5000）'
    connecting.value = false
    return
  }

  let lastApiError = null

  for (let i = 0; i < list.length; i++) {
    const url = list[i]
    hostUrl.value = url
    probeProgress.value = `${i + 1}/${list.length}`
    try {
      const result = await sandboxApi.connectHost(url)
      if (result && result.ok === true) {
        connected.value = true
        hostInfo.value = result
        try {
          localStorage.setItem(SANDBOX_HOST_STORAGE, url)
        } catch (_) {
          /* ignore */
        }
        probeProgress.value = ''
        connecting.value = false
        return
      }
    } catch (e) {
      lastApiError = e
    }
  }

  probeProgress.value = ''
  if (lastApiError) {
    connectError.value = formatConnectFailure(lastApiError)
  } else {
    connectError.value =
      '未发现可连宿主（已试常用地址与当前页同机）。请确认 XCAGI 已启动后点「重新探测」，或手动填写 API 根地址。'
  }
  console.warn('[Sandbox] 探测结束，未找到可用宿主')
  connecting.value = false
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
  messageHandler = (e) => {
    if (e.data?.type === 'sandbox:ready') {
      console.log('[Sandbox] FHD 宿主已就绪')
    }
  }
  window.addEventListener('message', messageHandler)

  void discoverAndConnect()
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

.status-err {
  color: #f87171;
  background: rgba(248, 113, 113, 0.12);
  max-width: min(520px, 100%);
  white-space: normal;
  line-height: 1.35;
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
