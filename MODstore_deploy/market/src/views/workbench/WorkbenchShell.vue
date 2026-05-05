<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import LeftRail from './panels/LeftRail.vue'
import CanvasStage from './panels/CanvasStage.vue'
import RightRail from './panels/RightRail.vue'
import { useWorkbenchStore } from '../../stores/workbench'
import { useAuthStore } from '../../stores/auth'
import { api } from '../../api'
import type { TargetKind } from '../../stores/workbench'
import { createEmptyEmployeeConfigV2, upgradeLegacyToV2 } from '../../employeeConfigV2'

const store = useWorkbenchStore()
const auth = useAuthStore()
const route = useRoute()
const router = useRouter()

const props = withDefaults(defineProps<{
  embedded?: boolean
  initialTarget?: TargetKind
}>(), {
  embedded: false,
  initialTarget: 'employee',
})

const canvasRef = ref<InstanceType<typeof CanvasStage> | null>(null)

// ── Target kind from route ───────────────────────────────────────────────────

const VALID_KINDS: TargetKind[] = ['employee', 'workflow', 'mod', 'skill']

function resolveKind(): TargetKind {
  const k = String(route.params.target ?? route.query.focus ?? props.initialTarget)
  return (VALID_KINDS.includes(k as TargetKind) ? k : 'employee') as TargetKind
}

function resolveId(): string | null {
  // route.params.id – from /workbench/shell/employee/:id
  // route.query.id  – explicit ?id= query
  // route.query.packId – set by wb-home make-scene handoff (fromAi=1)
  const id = route.params.id ?? route.query.id ?? route.query.packId ?? null
  return id ? String(id) : null
}

// ── Load target manifest ──────────────────────────────────────────────────────

const loading = ref(false)
const loadError = ref('')

function _snapshotBaseline(id: string, manifest: Record<string, unknown>) {
  try {
    sessionStorage.setItem(`workbench_baseline_manifest_${id}`, JSON.stringify(manifest))
  } catch { /* quota exceeded – ignore */ }
}

async function loadTarget(kind: TargetKind, id: string | null) {
  loading.value = true
  loadError.value = ''

  try {
    if (kind === 'employee' && id) {
      // Check for an AI-draft prefill written by EmployeeAiDraftReview.openInAuthoring()
      const prefillRaw = sessionStorage.getItem('modstore_employee_prefill')
      if (prefillRaw) {
        try {
          const prefill = JSON.parse(prefillRaw) as Record<string, unknown>
          const prefillId = String(prefill.id ?? prefill['identity']?.['id'] ?? '')
          if (prefillId === id || !prefillId) {
            sessionStorage.removeItem('modstore_employee_prefill')
            const name = String(prefill.name ?? prefill['identity']?.['name'] ?? id)
            store.setTarget(kind, id, prefill, name)
            _snapshotBaseline(id, prefill)
            store.loadEligibleWorkflows()
            return
          }
        } catch { /* malformed prefill – fall through to API load */ }
      }

      // Load existing employee pack from API
      const res = await api.listEmployees() as Record<string, unknown>
      const packs = Array.isArray(res?.packages) ? res.packages : (Array.isArray(res) ? res : [])
      const pack = packs.find((p: Record<string, unknown>) => String(p.pack_id ?? p.id ?? '') === id)
      if (pack) {
        const rawManifest = (pack as Record<string, unknown>).manifest ?? pack
        const raw = rawManifest && typeof rawManifest === 'object' ? rawManifest as Record<string, unknown> : {}
        // Pack manifest can have three shapes:
        //   1. { employee_config_v2: { identity, cognition, ... } }  ← generated packs
        //   2. { identity, cognition, ... }                           ← already V2 at root
        //   3. { panel_summary, workflow_employees, ... }             ← legacy V1
        const manifest: Record<string, unknown> = (
          raw.employee_config_v2 && typeof raw.employee_config_v2 === 'object'
            ? raw.employee_config_v2
            : raw.identity && typeof raw.identity === 'object'
              ? raw
              : upgradeLegacyToV2(raw)
        ) as Record<string, unknown>
        const displayName = String(
          (manifest.identity as Record<string, unknown> | undefined)?.name
          ?? raw.name
          ?? (pack as Record<string, unknown>).name
          ?? id,
        )
        store.setTarget(kind, id, manifest, displayName)
        _snapshotBaseline(id, manifest)
      } else {
        const empty = createEmptyEmployeeConfigV2() as Record<string, unknown>
        store.setTarget(kind, id, empty, id)
        _snapshotBaseline(id, empty)
      }
    } else if (kind === 'employee') {
      // New employee
      store.setTarget('employee', null, createEmptyEmployeeConfigV2() as Record<string, unknown>, '新员工')
    } else {
      // workflow / mod / skill — placeholder targets
      store.setTarget(kind, id, {}, id ?? kind)
    }

    // Pre-load workflow list for the heart node dropdown
    if (kind === 'employee') {
      store.loadEligibleWorkflows()
    }
  } catch (e: unknown) {
    loadError.value = (e as Error)?.message || String(e)
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  await loadTarget(resolveKind(), resolveId())
  // If coming from wb-home generation and manifest has no workflow linked, apply the generated wfId
  const wfId = Number(route.query.wfId ?? 0)
  if (wfId > 0) {
    const curWfId = Number(
      (store.target.manifest as Record<string, unknown>)
        ?.collaboration?.workflow?.workflow_id ?? 0,
    )
    if (curWfId === 0) {
      store.patchManifest('collaboration.workflow.workflow_id', wfId)
    }
  }
  setTimeout(() => canvasRef.value?.fitView(), 200)
})

watch(() => route.params, async () => {
  await loadTarget(resolveKind(), resolveId())
  setTimeout(() => canvasRef.value?.fitView(), 200)
})

// ── Target switcher bar (top) ────────────────────────────────────────────────

const TARGET_TABS: { kind: TargetKind; label: string; icon: string }[] = [
  { kind: 'employee', label: '员工', icon: '🤖' },
  { kind: 'workflow', label: '工作流', icon: '⚡' },
  { kind: 'mod', label: 'Mod 库', icon: '📦' },
  { kind: 'skill', label: '技能', icon: '🔧' },
]

function switchTarget(kind: TargetKind) {
  if (props.embedded) {
    void loadTarget(kind, null)
    return
  }
  router.push({ name: 'workbench-shell', params: { target: kind } })
}

// ── Panels resize ─────────────────────────────────────────────────────────────

const leftWidth = ref(props.embedded ? 260 : 280)
const rightWidth = ref(props.embedded ? 280 : 300)

// ── Save / publish actions ────────────────────────────────────────────────────

const saving = ref(false)
const saveMsg = ref('')

async function saveEmployee() {
  if (saving.value) return
  saving.value = true
  saveMsg.value = ''
  try {
    // Use export endpoint to get zip blob and upload
    const manifest = store.target.manifest
    const identity = manifest.identity as Record<string, unknown> | undefined
    if (!identity?.id || !identity?.name) {
      saveMsg.value = '请先填写员工身份（ID 和名称）'
      return
    }
    // For now: show a success message until the full save flow is implemented
    saveMsg.value = '配置已暂存（本地会话）'
    store.dirty = false
    store.lastSavedAt = Date.now()
    setTimeout(() => { saveMsg.value = '' }, 3000)
  } catch (e: unknown) {
    saveMsg.value = '保存失败: ' + ((e as Error)?.message || String(e))
  } finally {
    saving.value = false
  }
}

// ── Select employee from LeftRail ─────────────────────────────────────────────

async function onSelectEmployee(id: string) {
  await loadTarget('employee', id)
  if (!props.embedded) {
    void router.replace({ name: 'workbench-shell', params: { target: 'employee', id } })
  }
  setTimeout(() => canvasRef.value?.fitView(), 200)
}

// ── Toolbar panel toggles ────────────────────────────────────────────────────

const showPackagePanel = ref(false)
const showTestPanel = ref(false)
const showPublishPanel = ref(false)
</script>

<template>
  <div class="wb-shell" :class="{ 'wb-shell--embedded': embedded }">
    <!-- Top bar -->
    <header v-if="!embedded" class="wb-topbar">
      <!-- Left: branding + target tabs -->
      <div class="wb-topbar-left">
        <span class="wb-logo">XCAGI <span class="wb-logo-badge">工作台</span></span>
        <nav class="wb-target-tabs">
          <button
            v-for="tab in TARGET_TABS"
            :key="tab.kind"
            class="wb-target-tab"
            :class="{ 'wb-target-tab--active': store.target.kind === tab.kind }"
            @click="switchTarget(tab.kind)"
          >
            <span>{{ tab.icon }}</span>
            <span>{{ tab.label }}</span>
          </button>
        </nav>
      </div>

      <!-- Center: current target name + dirty indicator -->
      <div class="wb-topbar-center">
        <span class="wb-target-name">{{ store.target.name || '未命名' }}</span>
        <span v-if="store.dirty" class="wb-dirty">● 未保存</span>
        <span v-if="store.target.id" class="wb-target-id">ID: {{ store.target.id }}</span>
      </div>

      <!-- Right: action buttons -->
      <div class="wb-topbar-right">
        <span v-if="saveMsg" class="wb-save-msg" :class="{ 'wb-save-msg--ok': saveMsg.startsWith('配置') }">
          {{ saveMsg }}
        </span>
        <button class="wb-btn" @click="showPackagePanel = !showPackagePanel">上传打包</button>
        <button class="wb-btn" @click="showTestPanel = !showTestPanel">测试审核</button>
        <button class="wb-btn wb-btn--primary" :disabled="saving" @click="saveEmployee">
          {{ saving ? '保存中…' : '保存' }}
        </button>
        <button class="wb-btn wb-btn--publish" @click="showPublishPanel = !showPublishPanel">
          发布上架
        </button>
        <span class="wb-user">{{ auth.username || '—' }}</span>
      </div>
    </header>

    <!-- Loading / Error overlay -->
    <div v-if="loading" class="wb-loading">
      <span class="wb-loading-spinner">●</span> 加载中…
    </div>
    <div v-else-if="loadError" class="wb-error">加载失败：{{ loadError }}</div>

    <!-- Three-column body -->
    <div v-else class="wb-body">
      <!-- Left rail -->
      <div class="wb-col wb-col--left" :style="{ width: leftWidth + 'px' }">
        <LeftRail @select-employee="onSelectEmployee" />
      </div>

      <!-- Resize handle left -->
      <div
        class="wb-resize"
        @mousedown="(e) => {
          const startX = e.clientX
          const startW = leftWidth
          const move = (ev: MouseEvent) => { leftWidth = Math.max(220, Math.min(480, startW + ev.clientX - startX)) }
          const up = () => { window.removeEventListener('mousemove', move); window.removeEventListener('mouseup', up) }
          window.addEventListener('mousemove', move)
          window.addEventListener('mouseup', up)
        }"
      />

      <!-- Center canvas -->
      <div class="wb-col wb-col--center">
        <CanvasStage ref="canvasRef" />
      </div>

      <!-- Resize handle right -->
      <div
        class="wb-resize"
        @mousedown="(e) => {
          const startX = e.clientX
          const startW = rightWidth
          const move = (ev: MouseEvent) => { rightWidth = Math.max(240, Math.min(520, startW - ev.clientX + startX)) }
          const up = () => { window.removeEventListener('mousemove', move); window.removeEventListener('mouseup', up) }
          window.addEventListener('mousemove', move)
          window.addEventListener('mouseup', up)
        }"
      />

      <!-- Right rail -->
      <div class="wb-col wb-col--right" :style="{ width: rightWidth + 'px' }">
        <RightRail />
      </div>
    </div>

    <!-- Package panel drawer -->
    <transition name="drawer">
      <div v-if="showPackagePanel" class="wb-drawer">
        <div class="wb-drawer-header">
          <span>上传打包</span>
          <button class="wb-drawer-close" @click="showPackagePanel = false">✕</button>
        </div>
        <div class="wb-drawer-body">
          <p class="drawer-hint">将当前 Manifest 打包为可安装的 employee_pack.zip。</p>
          <pre class="drawer-json">{{ JSON.stringify(store.target.manifest, null, 2) }}</pre>
        </div>
      </div>
    </transition>

    <!-- Test panel drawer -->
    <transition name="drawer">
      <div v-if="showTestPanel" class="wb-drawer">
        <div class="wb-drawer-header">
          <span>测试审核</span>
          <button class="wb-drawer-close" @click="showTestPanel = false">✕</button>
        </div>
        <div class="wb-drawer-body">
          <p class="drawer-hint">在沙箱中对绑定的工作流进行测试运行。</p>
          <p v-if="!store.target.id" class="drawer-warn">请先保存员工以获得 ID。</p>
        </div>
      </div>
    </transition>

    <!-- Publish panel drawer -->
    <transition name="drawer">
      <div v-if="showPublishPanel" class="wb-drawer">
        <div class="wb-drawer-header">
          <span>发布上架</span>
          <button class="wb-drawer-close" @click="showPublishPanel = false">✕</button>
        </div>
        <div class="wb-drawer-body">
          <p class="drawer-hint">将员工包发布到 AI 市场目录，供其他用户安装使用。</p>
          <p v-if="!store.target.id" class="drawer-warn">请先保存员工以获得 ID。</p>
        </div>
      </div>
    </transition>
  </div>
</template>

<style scoped>
.wb-shell {
  display: flex;
  flex-direction: column;
  height: 100vh;
  overflow: hidden;
  background: #080f1a;
  color: #e2e8f0;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
}

.wb-shell--embedded {
  height: 100%;
  min-height: 0;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 14px;
  background: #050505;
}

/* ── Top bar ── */
.wb-topbar {
  height: 48px;
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 0 16px;
  background: rgba(8, 15, 26, 0.98);
  border-bottom: 1px solid rgba(148, 163, 184, 0.1);
  flex-shrink: 0;
  z-index: 100;
}

.wb-topbar-left, .wb-topbar-right {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.wb-topbar-center {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  min-width: 0;
}

.wb-logo {
  font-size: 14px;
  font-weight: 900;
  color: #6366f1;
  letter-spacing: -0.02em;
  white-space: nowrap;
}

.wb-logo-badge {
  font-size: 9px;
  font-weight: 700;
  background: rgba(99, 102, 241, 0.15);
  color: #a5b4fc;
  padding: 2px 6px;
  border-radius: 5px;
  border: 1px solid rgba(99, 102, 241, 0.2);
  text-transform: uppercase;
  letter-spacing: 0.08em;
  vertical-align: middle;
  margin-left: 4px;
}

.wb-target-tabs {
  display: flex;
  gap: 2px;
}

.wb-target-tab {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  background: transparent;
  border: 1px solid transparent;
  border-radius: 7px;
  color: #64748b;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s ease;
}

.wb-target-tab:hover { color: #94a3b8; background: rgba(148, 163, 184, 0.06); }

.wb-target-tab--active {
  color: #a5b4fc;
  background: rgba(99, 102, 241, 0.12);
  border-color: rgba(99, 102, 241, 0.2);
}

.wb-target-name {
  font-size: 14px;
  font-weight: 700;
  color: #f1f5f9;
  max-width: 260px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.wb-dirty {
  font-size: 10px;
  color: #f59e0b;
  font-weight: 700;
}

.wb-target-id {
  font-size: 10px;
  color: #475569;
  font-variant-numeric: tabular-nums;
}

.wb-btn {
  background: rgba(15, 23, 42, 0.8);
  border: 1px solid rgba(148, 163, 184, 0.15);
  color: #94a3b8;
  font-size: 11px;
  font-weight: 600;
  padding: 5px 12px;
  border-radius: 7px;
  cursor: pointer;
  transition: all 0.15s ease;
  white-space: nowrap;
}

.wb-btn:hover:not(:disabled) {
  background: rgba(148, 163, 184, 0.08);
  color: #e2e8f0;
}

.wb-btn--primary {
  background: rgba(99, 102, 241, 0.15);
  border-color: rgba(99, 102, 241, 0.3);
  color: #a5b4fc;
}

.wb-btn--primary:hover:not(:disabled) {
  background: rgba(99, 102, 241, 0.25);
}

.wb-btn--publish {
  background: rgba(16, 185, 129, 0.1);
  border-color: rgba(16, 185, 129, 0.25);
  color: #6ee7b7;
}

.wb-btn--publish:hover {
  background: rgba(16, 185, 129, 0.18);
}

.wb-btn:disabled { opacity: 0.35; cursor: not-allowed; }

.wb-save-msg {
  font-size: 11px;
  color: #f59e0b;
  font-weight: 600;
}

.wb-save-msg--ok { color: #6ee7b7; }

.wb-user {
  font-size: 11px;
  color: #64748b;
  padding: 0 4px;
  border-left: 1px solid rgba(148, 163, 184, 0.1);
  margin-left: 4px;
}

/* ── Body ── */
.wb-body {
  flex: 1;
  display: flex;
  overflow: hidden;
  min-height: 0;
}

.wb-col {
  display: flex;
  flex-direction: column;
  overflow: hidden;
  flex-shrink: 0;
}

.wb-col--left {
  border-right: 1px solid rgba(148, 163, 184, 0.08);
}

.wb-col--center {
  flex: 1;
  min-width: 0;
}

.wb-col--right {
  border-left: 1px solid rgba(148, 163, 184, 0.08);
}

/* Resize handle */
.wb-resize {
  width: 4px;
  background: transparent;
  cursor: col-resize;
  flex-shrink: 0;
  transition: background 0.15s ease;
}

.wb-resize:hover { background: rgba(99, 102, 241, 0.3); }

/* Loading / error */
.wb-loading {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  color: #64748b;
  font-size: 13px;
}

.wb-loading-spinner {
  animation: spin 1.5s linear infinite;
  display: inline-block;
  color: #6366f1;
}

@keyframes spin {
  0% { opacity: 1; }
  33% { opacity: 0.3; }
  66% { opacity: 0.7; }
  100% { opacity: 1; }
}

.wb-error {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fca5a5;
  font-size: 13px;
}

/* ── Drawers ── */
.wb-drawer {
  position: fixed;
  bottom: 0;
  right: 0;
  width: 480px;
  max-height: 60vh;
  background: rgba(10, 18, 32, 0.98);
  border: 1px solid rgba(148, 163, 184, 0.12);
  border-bottom: none;
  border-radius: 14px 14px 0 0;
  box-shadow: 0 -8px 32px rgba(0, 0, 0, 0.5);
  z-index: 200;
  display: flex;
  flex-direction: column;
  backdrop-filter: blur(12px);
}

.wb-drawer-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 1px solid rgba(148, 163, 184, 0.08);
  font-size: 13px;
  font-weight: 700;
  color: #e2e8f0;
  flex-shrink: 0;
}

.wb-drawer-close {
  background: transparent;
  border: none;
  color: #64748b;
  font-size: 14px;
  cursor: pointer;
  padding: 2px 6px;
  border-radius: 5px;
  transition: color 0.15s ease;
}

.wb-drawer-close:hover { color: #e2e8f0; }

.wb-drawer-body {
  flex: 1;
  overflow-y: auto;
  padding: 14px 16px;
}

.drawer-hint {
  font-size: 12px;
  color: #94a3b8;
  margin: 0 0 10px;
  line-height: 1.6;
}

.drawer-warn {
  font-size: 12px;
  color: #f59e0b;
  margin: 0;
  padding: 8px 10px;
  background: rgba(245, 158, 11, 0.08);
  border: 1px solid rgba(245, 158, 11, 0.15);
  border-radius: 8px;
}

.drawer-json {
  font-size: 10px;
  color: #94a3b8;
  background: rgba(15, 23, 42, 0.6);
  border: 1px solid rgba(148, 163, 184, 0.1);
  border-radius: 8px;
  padding: 10px;
  overflow: auto;
  max-height: 300px;
  white-space: pre-wrap;
  word-break: break-all;
}

/* Drawer transition */
.drawer-enter-active, .drawer-leave-active {
  transition: transform 0.25s cubic-bezier(0.4, 0, 0.2, 1), opacity 0.25s ease;
}

.drawer-enter-from, .drawer-leave-to {
  transform: translateY(100%);
  opacity: 0;
}
</style>
