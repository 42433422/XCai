<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useWorkbenchStore } from '../../../stores/workbench'
import { useFieldAi } from '../../../composables/useFieldAi'
import { useManifestDiff } from '../../../composables/useManifestDiff'
import {
  MODULE_META,
  DEFAULT_MODULE_ORDER,
  addModuleToManifest,
  type EmployeeModuleKind,
} from '../../../composables/useWorkbenchManifest'
import type { EmployeeNodeData } from '../../../composables/useWorkbenchManifest'
import { api } from '../../../api'

const store = useWorkbenchStore()
const fieldAi = useFieldAi()
const manifestDiff = useManifestDiff()

// ── Inspector mode computed ─────────────────────────────────────────────────

const mode = computed(() => store.inspectorMode)

const selectedNodeData = computed<EmployeeNodeData | null>(() => {
  const node = store.selectedNode
  if (!node) return null
  return node.data as EmployeeNodeData
})

// ── Local field edits (bound to manifest slice) ─────────────────────────────

const manifest = computed(() => store.target.manifest as Record<string, unknown>)

function getPath(path: string): unknown {
  return path.split('.').reduce<unknown>((cur, key) => {
    if (cur == null || typeof cur !== 'object') return undefined
    return (cur as Record<string, unknown>)[key]
  }, manifest.value)
}

function setPath(path: string, value: unknown) {
  store.patchManifest(path, value)
}

// ── Identity fields ─────────────────────────────────────────────────────────

const identityName = computed({
  get: () => String(getPath('identity.name') ?? ''),
  set: (v) => setPath('identity.name', v),
})

const identityId = computed({
  get: () => String(getPath('identity.id') ?? ''),
  set: (v) => setPath('identity.id', v),
})

const identityVersion = computed({
  get: () => String(getPath('identity.version') ?? '1.0.0'),
  set: (v) => setPath('identity.version', v),
})

const identityDesc = computed({
  get: () => String(getPath('identity.description') ?? ''),
  set: (v) => setPath('identity.description', v),
})

// ── Prompt / cognition fields ───────────────────────────────────────────────

const systemPrompt = computed({
  get: () => String(getPath('cognition.agent.system_prompt') ?? ''),
  set: (v) => setPath('cognition.agent.system_prompt', v),
})

const roleName = computed({
  get: () => String(getPath('cognition.agent.role.name') ?? ''),
  set: (v) => setPath('cognition.agent.role.name', v),
})

const rolePersona = computed({
  get: () => String(getPath('cognition.agent.role.persona') ?? ''),
  set: (v) => setPath('cognition.agent.role.persona', v),
})

const roleTone = computed({
  get: () => String(getPath('cognition.agent.role.tone') ?? 'professional'),
  set: (v) => setPath('cognition.agent.role.tone', v),
})

const modelProvider = computed({
  get: () => String(getPath('cognition.agent.model.provider') ?? 'deepseek'),
  set: (v) => setPath('cognition.agent.model.provider', v),
})

const modelName = computed({
  get: () => String(getPath('cognition.agent.model.model_name') ?? 'deepseek-chat'),
  set: (v) => setPath('cognition.agent.model.model_name', v),
})

const temperature = computed({
  get: () => Number(getPath('cognition.agent.model.temperature') ?? 0.7),
  set: (v) => setPath('cognition.agent.model.temperature', Number(v)),
})

// ── Workflow heart field ────────────────────────────────────────────────────

const workflowId = computed({
  get: () => Number(getPath('collaboration.workflow.workflow_id') ?? 0),
  set: (v) => setPath('collaboration.workflow.workflow_id', Number(v)),
})

// ── Skills ─────────────────────────────────────────────────────────────────

const skills = computed(() => {
  const arr = getPath('cognition.skills')
  return Array.isArray(arr) ? arr as Array<Record<string, unknown>> : []
})

// ── Refine prompt with AI ───────────────────────────────────────────────────

const refineInstruction = ref('请使提示词更专业、更清晰、更具引导性')
const refineResult = ref('')
const refineExplanation = ref('')
const refineLoading = ref(false)

async function refinePrompt() {
  if (!systemPrompt.value.trim()) return
  refineLoading.value = true
  const result = await fieldAi.assist('refine-prompt', systemPrompt.value, {
    roleContext: roleName.value,
    instruction: refineInstruction.value,
  })
  refineLoading.value = false
  if (result) {
    refineResult.value = result.value
    refineExplanation.value = result.explanation ?? ''
  }
}

function applyRefine() {
  if (!refineResult.value) return
  systemPrompt.value = refineResult.value
  refineResult.value = ''
  refineExplanation.value = ''
}

// ── Research context for workflow selection ─────────────────────────────────

const researchBrief = ref('')
const researchLoading = ref(false)

async function fetchResearch() {
  const brief = researchBrief.value.trim() || store.target.name
  if (!brief) return
  researchLoading.value = true
  try {
    const res = await api.workbenchResearchContext?.(brief) as Record<string, unknown> | undefined
    if (res) {
      store.setResearch(String(res.context ?? ''), Array.isArray(res.sources) ? res.sources as string[] : [])
    }
  } catch { /* ignore */ }
  finally { researchLoading.value = false }
}

// ── Run (execute) section ─────────────────────────────────────────────────

const runInput = ref('')
const runResult = ref<string | null>(null)
const runLoading = ref(false)

async function runEmployee() {
  const eid = store.target.id
  if (!eid) {
    runResult.value = '请先保存员工（需要 ID）'
    return
  }
  runLoading.value = true
  runResult.value = null
  try {
    const res = await api.executeEmployeeTask(eid, runInput.value, {}) as Record<string, unknown>
    runResult.value = JSON.stringify(res, null, 2)
  } catch (e: unknown) {
    runResult.value = `错误: ${(e as Error)?.message || String(e)}`
  } finally {
    runLoading.value = false
  }
}

// ── TTS preview ────────────────────────────────────────────────────────────

const ttsText = ref('')
const ttsLoading = ref(false)

async function previewTts() {
  const text = ttsText.value.trim() || '你好，我是您的 AI 助理'
  ttsLoading.value = true
  try {
    const blob = await api.workbenchEdgeTts(text)
    const url = URL.createObjectURL(blob as Blob)
    const audio = new Audio(url)
    audio.play()
    audio.onended = () => URL.revokeObjectURL(url)
  } catch { /* ignore */ }
  finally { ttsLoading.value = false }
}

// ── Module library ─────────────────────────────────────────────────────────

const presentModuleKinds = computed(() => {
  const m = manifest.value
  return new Set(
    DEFAULT_MODULE_ORDER.filter((kind) => {
      if (MODULE_META[kind].required) return true
      const meta = MODULE_META[kind]
      return meta.paths.some((p) => {
        const val = getPath(p)
        return val != null
      })
    }),
  )
})

function addModule(kind: EmployeeModuleKind) {
  store.target.manifest = addModuleToManifest(
    manifest.value,
    kind,
  ) as Record<string, unknown>
  store.dirty = true
}

function dragModuleStart(kind: EmployeeModuleKind, event: DragEvent) {
  event.dataTransfer?.setData('application/emp-module-kind', kind)
}

// Watch for run mode from store
watch(() => store.inspectorMode, (m) => {
  if (m === 'run') runResult.value = null
})

function formatDiffVal(val: unknown): string {
  if (val === undefined || val === null || val === '') return '(空)'
  if (typeof val === 'string') {
    return val.length > 120 ? val.slice(0, 120) + '…' : val
  }
  return JSON.stringify(val)
}
</script>

<template>
  <div class="right-rail">
    <!-- Mode tabs -->
    <div class="rr-tabs">
      <button
        class="rr-tab"
        :class="{ 'rr-tab--active': mode === 'node' }"
        :disabled="!store.selectedNode"
        @click="store.inspectorMode = 'node'"
      >
        属性
      </button>
      <button
        class="rr-tab"
        :class="{ 'rr-tab--active': mode === 'library' }"
        @click="store.inspectorMode = 'library'"
      >
        模块库
      </button>
      <button
        class="rr-tab"
        :class="{ 'rr-tab--active': mode === 'run' }"
        @click="store.inspectorMode = 'run'"
      >
        运行
      </button>
      <button
        v-if="manifestDiff.hasBaseline.value"
        class="rr-tab rr-tab--diff"
        :class="{ 'rr-tab--active': mode === 'diff' }"
        @click="store.inspectorMode = 'diff'"
      >
        变更
        <span v-if="manifestDiff.diffCount.value > 0" class="rr-diff-badge">
          {{ manifestDiff.diffCount.value }}
        </span>
      </button>
    </div>

    <!-- ── Inspector (node selected) ─────────────────────────────── -->
    <div v-if="mode === 'node' && selectedNodeData" class="rr-pane inspector-pane">
      <div class="inspector-header">
        <span class="inspector-icon" :style="{ background: selectedNodeData.meta.accent }">
          {{ selectedNodeData.meta.icon }}
        </span>
        <div>
          <div class="inspector-title">{{ selectedNodeData.label }}</div>
          <div class="inspector-sub">{{ selectedNodeData.meta.required ? '必填模块' : '可选模块' }}</div>
        </div>
      </div>

      <!-- Identity fields -->
      <div v-if="selectedNodeData.moduleKind === 'identity'" class="field-group">
        <label class="field-label">员工名称 *</label>
        <input v-model="identityName" class="field-input" placeholder="例如：客服助手" />

        <label class="field-label">员工 ID *</label>
        <input v-model="identityId" class="field-input" placeholder="例如：cs-agent-v1" />

        <label class="field-label">版本</label>
        <input v-model="identityVersion" class="field-input" placeholder="1.0.0" />

        <label class="field-label">描述</label>
        <textarea v-model="identityDesc" class="field-textarea" rows="3" placeholder="一句话描述员工的作用…" />
      </div>

      <!-- Prompt / cognition fields -->
      <div v-else-if="selectedNodeData.moduleKind === 'prompt'" class="field-group">
        <label class="field-label">角色名</label>
        <input v-model="roleName" class="field-input" placeholder="例如：小智" />

        <label class="field-label">人设描述</label>
        <input v-model="rolePersona" class="field-input" placeholder="例如：专业、高效、亲切" />

        <label class="field-label">语气风格</label>
        <select v-model="roleTone" class="field-select">
          <option value="professional">专业</option>
          <option value="formal">正式</option>
          <option value="friendly">友好</option>
          <option value="casual">随意</option>
        </select>

        <label class="field-label">
          System Prompt
          <button class="field-ai-btn" :disabled="refineLoading" @click="refinePrompt">
            {{ refineLoading ? '优化中…' : '✨ AI 优化' }}
          </button>
        </label>
        <textarea v-model="systemPrompt" class="field-textarea" rows="8" placeholder="描述员工的角色、职责、行为准则…" />

        <!-- Refine result preview -->
        <div v-if="refineResult" class="refine-result">
          <p class="refine-result__title">AI 建议（点击应用）</p>
          <p class="refine-result__exp">{{ refineExplanation }}</p>
          <textarea class="field-textarea" rows="5" readonly :value="refineResult" />
          <div class="refine-actions">
            <button class="btn-apply" @click="applyRefine">应用</button>
            <button class="btn-discard" @click="refineResult = ''">放弃</button>
          </div>
        </div>

        <label class="field-label">优化指令</label>
        <input v-model="refineInstruction" class="field-input" placeholder="例如：让语气更友好" />

        <label class="field-label">模型</label>
        <div class="field-row">
          <select v-model="modelProvider" class="field-select" style="flex:1">
            <option value="deepseek">DeepSeek</option>
            <option value="openai">OpenAI</option>
            <option value="anthropic">Anthropic</option>
            <option value="local">Local</option>
          </select>
          <input v-model="modelName" class="field-input" style="flex:2" placeholder="model_name" />
        </div>

        <label class="field-label">温度 ({{ temperature }})</label>
        <input v-model="temperature" type="range" min="0" max="1" step="0.05" class="field-range" />
      </div>

      <!-- Workflow heart -->
      <div v-else-if="selectedNodeData.moduleKind === 'workflow_heart'" class="field-group">
        <label class="field-label">工作流 ID *</label>
        <select v-model="workflowId" class="field-select">
          <option :value="0">— 请选择 —</option>
          <option
            v-for="wf in store.allWorkflowOptions"
            :key="(wf as Record<string, unknown>).id as number"
            :value="(wf as Record<string, unknown>).id"
          >
            #{{ (wf as Record<string, unknown>).id }} {{ (wf as Record<string, unknown>).name }}
          </option>
        </select>
        <p class="field-hint">
          仅显示已通过沙箱测试的工作流。若列表为空，请先在脚本工作流页面完成测试。
        </p>

        <!-- Research context helper -->
        <div class="research-section">
          <label class="field-label">研究上下文（可选）</label>
          <div class="field-row">
            <input v-model="researchBrief" class="field-input" placeholder="关键词，补充网络资料" style="flex:1" />
            <button class="field-btn" :disabled="researchLoading" @click="fetchResearch">
              {{ researchLoading ? '…' : '获取' }}
            </button>
          </div>
          <p v-if="store.researchContext" class="field-hint research-context">
            {{ store.researchContext.slice(0, 300) }}{{ store.researchContext.length > 300 ? '…' : '' }}
          </p>
        </div>
      </div>

      <!-- Skills -->
      <div v-else-if="selectedNodeData.moduleKind === 'skills'" class="field-group">
        <p class="field-hint">当前已配置 {{ skills.length }} 个技能</p>
        <div v-for="(sk, i) in skills" :key="i" class="skill-item">
          <span class="skill-name">{{ (sk as Record<string, unknown>).name ?? `技能 ${i+1}` }}</span>
        </div>
        <p v-if="!skills.length" class="field-hint">在 Agent 面板输入"推荐技能"指令，AI 会自动填充。</p>
      </div>

      <!-- Memory -->
      <div v-else-if="selectedNodeData.moduleKind === 'memory'" class="field-group">
        <p class="field-hint">已启用记忆模块。可在 manifest 中详细配置 short_term / long_term 参数。</p>
      </div>

      <!-- Voice -->
      <div v-else-if="selectedNodeData.moduleKind === 'voice'" class="field-group">
        <label class="field-label">TTS 试听</label>
        <div class="field-row">
          <input v-model="ttsText" class="field-input" placeholder="输入测试文字…" style="flex:1" />
          <button class="field-btn" :disabled="ttsLoading" @click="previewTts">
            {{ ttsLoading ? '…' : '▶ 试听' }}
          </button>
        </div>
      </div>

      <!-- Fallback for other modules -->
      <div v-else class="field-group">
        <p class="field-hint">{{ selectedNodeData.meta.label }} 模块已启用。JSON 编辑请展开高级配置。</p>
        <details class="field-advanced">
          <summary class="field-advanced-toggle">高级 JSON 配置</summary>
          <textarea
            class="field-textarea field-json"
            rows="10"
            :value="JSON.stringify(selectedNodeData.slice, null, 2)"
            @change="(e) => {
              try {
                const val = JSON.parse((e.target as HTMLTextAreaElement).value)
                const path = MODULE_META[selectedNodeData!.moduleKind].paths[0]
                setPath(path, val)
              } catch { /* ignore parse error */ }
            }"
          />
        </details>
      </div>
    </div>

    <!-- ── No node selected + library ────────────────────────────── -->
    <div v-else-if="mode === 'library'" class="rr-pane library-pane">
      <p class="library-title">模块库</p>
      <p class="library-sub">拖放模块到画布，或点击添加</p>
      <div class="library-grid">
        <div
          v-for="kind in DEFAULT_MODULE_ORDER"
          :key="kind"
          class="library-item"
          :class="{ 'library-item--present': presentModuleKinds.has(kind) }"
          :draggable="!presentModuleKinds.has(kind)"
          @dragstart="(e) => dragModuleStart(kind, e)"
          @click="() => !presentModuleKinds.has(kind) && addModule(kind)"
        >
          <span class="library-item__icon" :style="{ background: MODULE_META[kind].accent }">
            {{ MODULE_META[kind].icon }}
          </span>
          <div class="library-item__info">
            <span class="library-item__name">{{ MODULE_META[kind].label }}</span>
            <span class="library-item__state">
              {{ presentModuleKinds.has(kind) ? '已添加' : MODULE_META[kind].required ? '必填' : '可拖入' }}
            </span>
          </div>
        </div>
      </div>

      <!-- Dirty indicator -->
      <div v-if="store.dirty" class="dirty-hint">
        ● 有未保存的修改
      </div>
    </div>

    <!-- ── Run panel ─────────────────────────────────────────────── -->
    <div v-else-if="mode === 'run'" class="rr-pane run-pane">
      <p class="run-title">试运行员工</p>
      <p class="run-sub">需要先保存员工并获得 ID</p>

      <label class="field-label">任务描述</label>
      <textarea v-model="runInput" class="field-textarea" rows="4" placeholder="描述你想让员工执行的任务…" />

      <button
        class="run-btn"
        :disabled="runLoading || !store.target.id"
        @click="runEmployee"
      >
        {{ runLoading ? '运行中…' : '▶ 执行' }}
      </button>

      <div v-if="!store.target.id" class="run-hint">
        当前员工尚未保存，请先通过「上传打包」或「发布上架」获得员工 ID
      </div>

      <pre v-if="runResult" class="run-result">{{ runResult }}</pre>

      <!-- Current agent run status if present -->
      <div v-if="store.currentRun" class="current-run-summary">
        <p class="field-label">最近一次 Agent 运行</p>
        <span class="agent-run__status" :class="`agent-run__status--${store.currentRun.status}`">
          {{ store.currentRun.status === 'running' ? '运行中' : store.currentRun.status === 'done' ? '完成' : '失败' }}
        </span>
        <p class="run-brief">{{ store.currentRun.brief }}</p>
      </div>
    </div>

    <!-- Empty state when no node selected in node mode -->
    <div v-else-if="mode === 'node' && !selectedNodeData" class="rr-pane empty-pane">
      <p class="empty-hint">点击画布中的模块节点以编辑属性</p>
    </div>

    <!-- ── Diff panel ─────────────────────────────────────────────── -->
    <div v-else-if="mode === 'diff'" class="rr-pane diff-pane">
      <p class="diff-title">变更对比</p>
      <p class="diff-sub">当前配置与加载时的快照对比</p>

      <div v-if="!manifestDiff.hasDiff.value" class="diff-empty">
        <span class="diff-empty__icon">✓</span>
        <p>与基准版本无差异</p>
      </div>

      <div v-else class="diff-list">
        <div
          v-for="entry in manifestDiff.diffs.value"
          :key="entry.path"
          class="diff-entry"
        >
          <div class="diff-entry__label">{{ entry.label }}</div>
          <div class="diff-entry__row">
            <div class="diff-entry__side diff-entry__side--before">
              <span class="diff-entry__side-tag">原</span>
              <span class="diff-entry__val">{{ formatDiffVal(entry.before) }}</span>
            </div>
            <span class="diff-entry__arrow">→</span>
            <div class="diff-entry__side diff-entry__side--after">
              <span class="diff-entry__side-tag">现</span>
              <span class="diff-entry__val">{{ formatDiffVal(entry.after) }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.right-rail {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
  background: rgba(8, 15, 26, 0.98);
}

/* Tabs */
.rr-tabs {
  display: flex;
  border-bottom: 1px solid rgba(148, 163, 184, 0.1);
  flex-shrink: 0;
}

.rr-tab {
  flex: 1;
  padding: 10px 6px;
  background: transparent;
  border: none;
  color: #64748b;
  font-size: 11px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s ease;
  text-transform: uppercase;
  letter-spacing: 0.06em;
}

.rr-tab:hover:not(:disabled) { color: #94a3b8; }
.rr-tab--active { color: #a5b4fc; border-bottom: 2px solid #6366f1; }
.rr-tab:disabled { opacity: 0.35; cursor: not-allowed; }

/* Pane */
.rr-pane {
  flex: 1;
  overflow-y: auto;
  padding: 12px;
  scrollbar-width: thin;
  scrollbar-color: rgba(99, 102, 241, 0.25) transparent;
}

/* Inspector */
.inspector-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 14px;
  padding-bottom: 12px;
  border-bottom: 1px solid rgba(148, 163, 184, 0.08);
}

.inspector-icon {
  width: 34px;
  height: 34px;
  border-radius: 10px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
  flex-shrink: 0;
}

.inspector-title {
  font-size: 15px;
  font-weight: 700;
  color: #f1f5f9;
}

.inspector-sub {
  font-size: 10px;
  color: #64748b;
  text-transform: uppercase;
  letter-spacing: 0.06em;
}

/* Fields */
.field-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.field-label {
  font-size: 11px;
  font-weight: 600;
  color: #94a3b8;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
  margin-top: 2px;
}

.field-input, .field-select, .field-textarea {
  background: rgba(15, 23, 42, 0.8);
  border: 1px solid rgba(148, 163, 184, 0.12);
  border-radius: 8px;
  color: #e2e8f0;
  font-size: 12px;
  padding: 7px 10px;
  outline: none;
  width: 100%;
  box-sizing: border-box;
  font-family: inherit;
  transition: border-color 0.15s ease;
}

.field-input:focus, .field-select:focus, .field-textarea:focus {
  border-color: rgba(99, 102, 241, 0.4);
}

.field-select option { background: #0f172a; }

.field-textarea { resize: vertical; line-height: 1.5; }

.field-json { font-family: monospace; font-size: 11px; }

.field-range {
  width: 100%;
  accent-color: #6366f1;
}

.field-hint {
  font-size: 11px;
  color: #475569;
  margin: 0;
  line-height: 1.5;
}

.field-row {
  display: flex;
  gap: 6px;
}

.field-btn {
  background: rgba(99, 102, 241, 0.12);
  border: 1px solid rgba(99, 102, 241, 0.25);
  color: #a5b4fc;
  font-size: 11px;
  font-weight: 700;
  padding: 6px 12px;
  border-radius: 8px;
  cursor: pointer;
  white-space: nowrap;
  flex-shrink: 0;
  transition: all 0.15s ease;
}

.field-btn:hover:not(:disabled) {
  background: rgba(99, 102, 241, 0.2);
  border-color: rgba(99, 102, 241, 0.4);
}

.field-btn:disabled { opacity: 0.35; cursor: not-allowed; }

.field-ai-btn {
  background: linear-gradient(135deg, rgba(99, 102, 241, 0.15), rgba(139, 92, 246, 0.15));
  border: 1px solid rgba(99, 102, 241, 0.25);
  color: #a5b4fc;
  font-size: 9px;
  font-weight: 700;
  padding: 3px 9px;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.15s ease;
  letter-spacing: 0.02em;
}

.field-ai-btn:hover:not(:disabled) {
  background: linear-gradient(135deg, rgba(99, 102, 241, 0.25), rgba(139, 92, 246, 0.25));
}

.field-ai-btn:disabled { opacity: 0.35; cursor: not-allowed; }

.field-advanced { margin-top: 4px; }

.field-advanced-toggle {
  font-size: 11px;
  color: #64748b;
  cursor: pointer;
  padding: 4px 0;
  user-select: none;
}

/* Refine result */
.refine-result {
  background: rgba(99, 102, 241, 0.06);
  border: 1px solid rgba(99, 102, 241, 0.2);
  border-radius: 10px;
  padding: 10px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.refine-result__title {
  font-size: 11px;
  font-weight: 700;
  color: #a5b4fc;
  margin: 0;
}

.refine-result__exp {
  font-size: 11px;
  color: #94a3b8;
  margin: 0;
  font-style: italic;
}

.refine-actions {
  display: flex;
  gap: 6px;
  justify-content: flex-end;
}

.btn-apply {
  background: rgba(16, 185, 129, 0.15);
  border: 1px solid rgba(16, 185, 129, 0.3);
  color: #6ee7b7;
  font-size: 11px;
  font-weight: 700;
  padding: 5px 14px;
  border-radius: 7px;
  cursor: pointer;
}

.btn-discard {
  background: transparent;
  border: 1px solid rgba(148, 163, 184, 0.15);
  color: #64748b;
  font-size: 11px;
  font-weight: 700;
  padding: 5px 14px;
  border-radius: 7px;
  cursor: pointer;
}

/* Research */
.research-section { margin-top: 6px; }
.research-context { color: #94a3b8; font-size: 11px; }

/* Skill item */
.skill-item {
  background: rgba(245, 158, 11, 0.08);
  border: 1px solid rgba(245, 158, 11, 0.15);
  border-radius: 7px;
  padding: 6px 10px;
}

.skill-name { font-size: 12px; color: #fde68a; }

/* Library */
.library-title {
  font-size: 13px;
  font-weight: 700;
  color: #e2e8f0;
  margin: 0 0 4px;
}

.library-sub {
  font-size: 11px;
  color: #475569;
  margin: 0 0 12px;
}

.library-grid {
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.library-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 10px;
  background: rgba(15, 23, 42, 0.6);
  border: 1px solid rgba(148, 163, 184, 0.1);
  border-radius: 10px;
  cursor: grab;
  transition: all 0.15s ease;
}

.library-item:hover:not(.library-item--present) {
  background: rgba(99, 102, 241, 0.08);
  border-color: rgba(99, 102, 241, 0.2);
  transform: translateX(2px);
}

.library-item--present {
  opacity: 0.45;
  cursor: default;
}

.library-item__icon {
  width: 28px;
  height: 28px;
  border-radius: 8px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  flex-shrink: 0;
}

.library-item__info {
  display: flex;
  flex-direction: column;
  gap: 1px;
}

.library-item__name {
  font-size: 12px;
  font-weight: 600;
  color: #e2e8f0;
}

.library-item__state {
  font-size: 9px;
  color: #64748b;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.library-item--present .library-item__state { color: #10b981; }

.dirty-hint {
  margin-top: 14px;
  font-size: 11px;
  color: #f59e0b;
  text-align: center;
}

/* Run */
.run-title {
  font-size: 14px;
  font-weight: 700;
  color: #f1f5f9;
  margin: 0 0 4px;
}

.run-sub {
  font-size: 11px;
  color: #64748b;
  margin: 0 0 12px;
}

.run-btn {
  background: rgba(99, 102, 241, 0.15);
  border: 1px solid rgba(99, 102, 241, 0.3);
  color: #a5b4fc;
  font-size: 12px;
  font-weight: 700;
  padding: 9px 16px;
  border-radius: 9px;
  cursor: pointer;
  width: 100%;
  margin-top: 6px;
  transition: all 0.15s ease;
}

.run-btn:hover:not(:disabled) {
  background: rgba(99, 102, 241, 0.25);
}

.run-btn:disabled { opacity: 0.35; cursor: not-allowed; }

.run-hint {
  font-size: 11px;
  color: #f59e0b;
  margin-top: 8px;
  padding: 8px 10px;
  background: rgba(245, 158, 11, 0.08);
  border: 1px solid rgba(245, 158, 11, 0.15);
  border-radius: 8px;
  line-height: 1.5;
}

.run-result {
  background: rgba(15, 23, 42, 0.8);
  border: 1px solid rgba(148, 163, 184, 0.12);
  border-radius: 9px;
  padding: 10px;
  font-size: 11px;
  color: #94a3b8;
  overflow-x: auto;
  margin-top: 10px;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 300px;
  overflow-y: auto;
}

.current-run-summary {
  margin-top: 14px;
  padding-top: 12px;
  border-top: 1px solid rgba(148, 163, 184, 0.08);
}

.run-brief { font-size: 12px; color: #94a3b8; margin: 4px 0 0; }

/* Agent run status (reuse from LeftRail) */
.agent-run__status {
  font-size: 9px;
  font-weight: 700;
  padding: 2px 7px;
  border-radius: 999px;
  display: inline-block;
}

.agent-run__status--running {
  background: rgba(99, 102, 241, 0.15);
  color: #a5b4fc;
  border: 1px solid rgba(99, 102, 241, 0.25);
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

/* Empty */
.empty-pane {
  display: flex;
  align-items: center;
  justify-content: center;
}

.empty-hint {
  font-size: 12px;
  color: #475569;
  text-align: center;
  padding: 20px;
  line-height: 1.6;
}

/* Diff tab */
.rr-tab--diff { position: relative; }

.rr-diff-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: #6366f1;
  color: #fff;
  font-size: 9px;
  font-weight: 800;
  min-width: 14px;
  height: 14px;
  border-radius: 7px;
  padding: 0 3px;
  margin-left: 4px;
  vertical-align: middle;
}

/* Diff pane */
.diff-title {
  font-size: 13px;
  font-weight: 700;
  color: #e2e8f0;
  margin: 0 0 4px;
}

.diff-sub {
  font-size: 11px;
  color: #475569;
  margin: 0 0 14px;
}

.diff-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 30px 10px;
  color: #475569;
  font-size: 12px;
  text-align: center;
}

.diff-empty__icon {
  font-size: 22px;
  color: #10b981;
}

.diff-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.diff-entry {
  background: rgba(15, 23, 42, 0.6);
  border: 1px solid rgba(148, 163, 184, 0.1);
  border-radius: 10px;
  padding: 10px 12px;
}

.diff-entry__label {
  font-size: 10px;
  font-weight: 700;
  color: #94a3b8;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: 6px;
}

.diff-entry__row {
  display: flex;
  align-items: flex-start;
  gap: 6px;
}

.diff-entry__side {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 3px;
  min-width: 0;
}

.diff-entry__side-tag {
  font-size: 9px;
  font-weight: 700;
  padding: 1px 5px;
  border-radius: 4px;
  align-self: flex-start;
}

.diff-entry__side--before .diff-entry__side-tag {
  background: rgba(239, 68, 68, 0.12);
  color: #fca5a5;
}

.diff-entry__side--after .diff-entry__side-tag {
  background: rgba(16, 185, 129, 0.12);
  color: #6ee7b7;
}

.diff-entry__val {
  font-size: 11px;
  color: #cbd5e1;
  word-break: break-all;
  line-height: 1.4;
  font-family: monospace;
}

.diff-entry__arrow {
  font-size: 12px;
  color: #475569;
  flex-shrink: 0;
  margin-top: 16px;
}
</style>
