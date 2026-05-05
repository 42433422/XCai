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
  if (m === 'publish') {
    // 切换到上架 tab 时重置动画状态
    auditAnimPhase.value = 'idle'
    auditAnimScores.value = {}
  }
})

// ── Publish / listing section ──────────────────────────────────────────────

type PublishState = 'idle' | 'testing' | 'done' | 'publishing' | 'published' | 'error'

const publishState = ref<PublishState>('idle')
const publishError = ref<string | null>(null)

interface BenchResult {
  tasks_result: Array<{
    level: number; task_id: string; task_desc: string
    ok: boolean; cost_tokens: number; duration_ms: number; score: number
  }>
  level_scores: Record<number, number>
  overall_score: number
  audit: {
    ok: boolean
    dimensions?: Record<string, { score: number; reasons: string[] }>
    summary?: { average: number; pass: boolean }
    error?: string
  }
  passed: boolean
}

const benchResult = ref<BenchResult | null>(null)

// 五维审核动画状态
type AuditAnimPhase = 'idle' | 'running' | 'done'
const auditAnimPhase = ref<AuditAnimPhase>('idle')
// 显示中的分数（从 0 动画滚动到真实分数）
const auditAnimScores = ref<Record<string, number>>({})

const DIM_LABELS: Record<string, string> = {
  manifest_compliance: '清单合规',
  declaration_completeness: '声明完整',
  api_testability_static: 'API 可测',
  security_and_size: '安全尺寸',
  metadata_quality: '元数据质量',
}

function _animateAuditScores(dims: Record<string, { score: number }>) {
  auditAnimPhase.value = 'running'
  const keys = Object.keys(dims)
  auditAnimScores.value = Object.fromEntries(keys.map((k) => [k, 0]))

  // 依次点亮每个维度，每个维度数字从 0 滚动到目标值
  const STEP_DELAY = 260   // 每个维度间隔 ms
  const COUNT_STEPS = 20   // 滚动帧数

  keys.forEach((key, i) => {
    const target = dims[key]?.score ?? 0
    const startAt = i * STEP_DELAY
    let step = 0
    const interval = setInterval(() => {
      step++
      auditAnimScores.value = {
        ...auditAnimScores.value,
        [key]: Math.round(target * Math.min(step / COUNT_STEPS, 1)),
      }
      if (step >= COUNT_STEPS) {
        clearInterval(interval)
        if (i === keys.length - 1) {
          // 最后一个维度完成 → 动画结束
          setTimeout(() => { auditAnimPhase.value = 'done' }, 300)
        }
      }
    }, (startAt + 50) / COUNT_STEPS)  // 每帧间隔
  })
}

async function startBenchTest() {
  const eid = store.target.id as string | undefined
  if (!eid) {
    publishError.value = '请先保存员工（需要 ID）'
    return
  }
  publishState.value = 'testing'
  publishError.value = null
  benchResult.value = null
  auditAnimPhase.value = 'idle'
  auditAnimScores.value = {}

  try {
    const res = await api.employeeBenchTest(eid) as BenchResult & { ok: boolean; error?: string }
    if (!res.ok) throw new Error(res.error || '测试失败')
    benchResult.value = res
    publishState.value = 'done'
    // 启动五维动画
    const dims = res.audit?.dimensions
    if (dims && Object.keys(dims).length > 0) {
      _animateAuditScores(dims)
    }
  } catch (e: unknown) {
    publishError.value = (e as Error)?.message || String(e)
    publishState.value = 'error'
  }
}

async function publishEmployee() {
  const eid = store.target.id as string | undefined
  if (!eid || !benchResult.value?.passed) return
  publishState.value = 'publishing'
  publishError.value = null
  try {
    const res = await api.employeePublish(eid) as { ok: boolean; error?: string; pkg_id?: string }
    if (!res.ok) throw new Error(res.error || '上架失败')
    publishState.value = 'published'
  } catch (e: unknown) {
    publishError.value = (e as Error)?.message || String(e)
    publishState.value = 'error'
  }
}

async function downloadPack() {
  const eid = store.target.id as string | undefined
  if (!eid) return
  // 先尝试从 mod context 导出，否则直接用 employee_id 当 mod_id
  const modId = (store.target as Record<string, unknown>).mod_id as string | undefined || eid
  try {
    const blob = await api.exportEmployeePackZip(modId, 0)
    const url = URL.createObjectURL(blob as Blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${eid}.xcemp`
    a.click()
    URL.revokeObjectURL(url)
  } catch {
    publishError.value = '下载失败，请确认员工已保存'
  }
}

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
        class="rr-tab rr-tab--publish"
        :class="{ 'rr-tab--active': mode === 'publish' }"
        @click="store.inspectorMode = 'publish'"
      >
        上架
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
          <!-- Fallback: manifest has a workflow_id that hasn't passed full sandbox yet -->
          <option
            v-if="workflowId > 0 && !store.allWorkflowOptions.some((wf: any) => Number((wf as any).id) === workflowId)"
            :value="workflowId"
          >
            #{{ workflowId }}（生成工作流，待沙箱验证）
          </option>
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

    <!-- ── Publish / listing panel ───────────────────────────────── -->
    <div v-else-if="mode === 'publish'" class="rr-pane publish-pane">

      <!-- ① 本地调试：下载员工包 -->
      <section class="pub-section">
        <h4 class="pub-section-title">本地调试</h4>
        <p class="pub-hint">下载员工包到本地，用 modman CLI 验证或集成到其它系统。</p>
        <button class="pub-btn pub-btn--secondary" :disabled="!store.target.id" @click="downloadPack">
          ↓ 下载员工包 (.xcemp)
        </button>
      </section>

      <!-- ② 上架测试区 -->
      <section class="pub-section">
        <h4 class="pub-section-title">上架测试</h4>
        <p class="pub-hint">大模型将生成 1–5 级共 15 项测试任务，根据完成率与消耗量量化打分，再进行五维审核。</p>

        <button
          class="pub-btn"
          :disabled="publishState === 'testing' || !store.target.id"
          @click="startBenchTest"
        >
          <span v-if="publishState === 'testing'" class="pub-spinner" />
          {{ publishState === 'testing' ? '测试中，请稍候…' : '开始测试' }}
        </button>

        <!-- 错误提示 -->
        <p v-if="publishState === 'error' && publishError" class="pub-error">{{ publishError }}</p>

        <!-- 任务完成后显示结果 -->
        <div v-if="benchResult" class="pub-result">

          <!-- 1-5 级得分条 -->
          <div class="pub-levels">
            <div v-for="lv in 5" :key="lv" class="pub-level">
              <span class="pub-level-label">Lv{{ lv }}</span>
              <div class="pub-level-bar">
                <div
                  class="pub-level-fill"
                  :style="{
                    width: (benchResult.level_scores[lv] ?? 0) + '%',
                    background: (benchResult.level_scores[lv] ?? 0) >= 60 ? '#22c55e' : '#f97316',
                  }"
                />
              </div>
              <span class="pub-level-score">{{ (benchResult.level_scores[lv] ?? 0).toFixed(0) }}</span>
            </div>
          </div>

          <!-- 五维审核动画 -->
          <div class="pub-audit">
            <p class="pub-audit-title">五维审核</p>

            <!-- 测试步骤流 -->
            <div class="pub-audit-stages">
              <div class="pub-stage" :class="{ 'pub-stage--done': auditAnimPhase !== 'idle' }">生成测试任务</div>
              <div class="pub-stage-arrow">→</div>
              <div class="pub-stage" :class="{ 'pub-stage--done': auditAnimPhase !== 'idle' }">执行任务</div>
              <div class="pub-stage-arrow">→</div>
              <div class="pub-stage" :class="{ 'pub-stage--done': auditAnimPhase !== 'idle' }">统计消耗</div>
              <div class="pub-stage-arrow">→</div>
              <div class="pub-stage" :class="{ 'pub-stage--done': auditAnimPhase !== 'idle' }">五维审核</div>
              <div class="pub-stage-arrow">→</div>
              <div class="pub-stage" :class="{ 'pub-stage--done': auditAnimPhase === 'done' }">
                {{ benchResult.passed ? '可上架' : '未通过' }}
              </div>
            </div>

            <!-- 五维卡片网格 -->
            <div v-if="benchResult.audit?.dimensions" class="pub-dim-grid">
              <div
                v-for="(dim, key, idx) in benchResult.audit.dimensions"
                :key="key"
                class="pub-dim-card"
                :class="{
                  'pub-dim-card--active': auditAnimPhase !== 'idle',
                  'pub-dim-card--pass': dim.score >= 60,
                  'pub-dim-card--fail': dim.score < 60,
                }"
                :style="{ animationDelay: `${(idx as number) * 260}ms` }"
              >
                <!-- 环形进度 SVG -->
                <svg class="pub-ring" viewBox="0 0 44 44">
                  <circle class="pub-ring-bg" cx="22" cy="22" r="18" />
                  <circle
                    class="pub-ring-fill"
                    cx="22" cy="22" r="18"
                    :stroke="dim.score >= 60 ? '#4ade80' : '#f87171'"
                    :stroke-dasharray="`${(auditAnimScores[key] ?? 0) * 1.131} 113.1`"
                  />
                </svg>
                <span class="pub-dim-score">{{ auditAnimScores[key] ?? 0 }}</span>
                <span class="pub-dim-label">{{ DIM_LABELS[key] ?? key }}</span>
                <!-- 第一条 reason 作为 tooltip -->
                <span v-if="dim.reasons?.[0]" class="pub-dim-reason">{{ dim.reasons[0] }}</span>
              </div>
            </div>

            <!-- 审核失败兜底文字 -->
            <p v-if="benchResult.audit?.error" class="pub-audit-err">
              审核异常：{{ benchResult.audit.error }}
            </p>
          </div>

          <!-- 综合得分总结 -->
          <div class="pub-overall" :class="benchResult.passed ? 'pub-overall--pass' : 'pub-overall--fail'">
            <span class="pub-overall-score">{{ benchResult.overall_score.toFixed(1) }}</span>
            <span class="pub-overall-label">
              {{ benchResult.passed ? '通过测试，可提交上架' : '未达标，请完善员工能力后重试' }}
            </span>
          </div>
        </div>
      </section>

      <!-- ③ 上架区（仅测试通过后显示） -->
      <section v-if="benchResult?.passed" class="pub-section pub-section--publish">
        <h4 class="pub-section-title">提交上架</h4>
        <button
          class="pub-btn pub-btn--primary"
          :disabled="publishState === 'publishing' || publishState === 'published'"
          @click="publishEmployee"
        >
          <span v-if="publishState === 'publishing'" class="pub-spinner" />
          {{ publishState === 'published' ? '✓ 已上架' : publishState === 'publishing' ? '上架中…' : '提交上架到目录' }}
        </button>
        <p v-if="publishState === 'published'" class="pub-ok">员工包已写入商店目录，可在「员工制作」页查看和分发。</p>
        <p v-if="publishState === 'error' && publishError" class="pub-error">{{ publishError }}</p>
      </section>

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

/* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   上架 Tab — publish pane
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */

/* Tab 按钮高亮色 —「上架」用绿色 */
.rr-tab.rr-tab--publish.rr-tab--active {
  color: #4ade80;
  border-bottom: 2px solid #22c55e;
}

.publish-pane {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

/* 卡片区块 */
.pub-section {
  border: 1px solid rgba(148, 163, 184, 0.1);
  border-radius: 10px;
  padding: 14px;
  background: rgba(15, 23, 42, 0.6);
}
.pub-section--publish {
  border-color: rgba(34, 197, 94, 0.25);
  background: rgba(34, 197, 94, 0.04);
}

.pub-section-title {
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: #64748b;
  margin: 0 0 8px;
}

.pub-hint {
  font-size: 11px;
  color: #475569;
  margin: 0 0 10px;
  line-height: 1.5;
}

/* 通用按钮 */
.pub-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 7px;
  width: 100%;
  padding: 9px 14px;
  border-radius: 8px;
  border: none;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.18s ease;
  background: rgba(99, 102, 241, 0.18);
  color: #a5b4fc;
}
.pub-btn:hover:not(:disabled) {
  background: rgba(99, 102, 241, 0.32);
  color: #c7d2fe;
}
.pub-btn:disabled {
  opacity: 0.38;
  cursor: not-allowed;
}
.pub-btn--secondary {
  background: transparent;
  border: 1px solid rgba(99, 102, 241, 0.3);
  color: #818cf8;
}
.pub-btn--secondary:hover:not(:disabled) {
  border-color: rgba(99, 102, 241, 0.6);
  background: rgba(99, 102, 241, 0.08);
}
.pub-btn--primary {
  background: rgba(34, 197, 94, 0.2);
  color: #4ade80;
  border: 1px solid rgba(34, 197, 94, 0.3);
}
.pub-btn--primary:hover:not(:disabled) {
  background: rgba(34, 197, 94, 0.32);
}

/* Loading spinner */
.pub-spinner {
  display: inline-block;
  width: 12px;
  height: 12px;
  border: 2px solid rgba(165, 180, 252, 0.3);
  border-top-color: #a5b4fc;
  border-radius: 50%;
  animation: pub-spin 0.7s linear infinite;
}
@keyframes pub-spin { to { transform: rotate(360deg); } }

/* 结果区 */
.pub-result { margin-top: 14px; display: flex; flex-direction: column; gap: 14px; }

/* 级别进度条 */
.pub-levels { display: flex; flex-direction: column; gap: 6px; }
.pub-level {
  display: flex;
  align-items: center;
  gap: 8px;
}
.pub-level-label {
  font-size: 10px;
  font-weight: 700;
  color: #64748b;
  width: 26px;
  flex-shrink: 0;
}
.pub-level-bar {
  flex: 1;
  height: 6px;
  border-radius: 3px;
  background: rgba(148, 163, 184, 0.1);
  overflow: hidden;
}
.pub-level-fill {
  height: 100%;
  border-radius: 3px;
  transition: width 0.6s cubic-bezier(0.4, 0, 0.2, 1);
}
.pub-level-score {
  font-size: 11px;
  font-weight: 700;
  color: #94a3b8;
  width: 26px;
  text-align: right;
  flex-shrink: 0;
}

/* ── 五维审核 ─────────────────────────────────────────── */
.pub-audit { display: flex; flex-direction: column; gap: 12px; }
.pub-audit-title {
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
  color: #64748b;
  letter-spacing: 0.07em;
}

/* 步骤流 */
.pub-audit-stages {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 4px;
}
.pub-stage {
  font-size: 10px;
  padding: 3px 8px;
  border-radius: 99px;
  background: rgba(148, 163, 184, 0.08);
  color: #475569;
  transition: all 0.4s ease;
  white-space: nowrap;
}
.pub-stage--done {
  background: rgba(99, 102, 241, 0.15);
  color: #a5b4fc;
  box-shadow: 0 0 0 1px rgba(99, 102, 241, 0.25);
}
.pub-stage-arrow { font-size: 10px; color: #334155; }

/* 五维卡片网格 */
.pub-dim-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
}

.pub-dim-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  padding: 10px 6px 8px;
  border-radius: 10px;
  border: 1px solid rgba(148, 163, 184, 0.08);
  background: rgba(15, 23, 42, 0.8);
  opacity: 0;
  transform: translateY(8px) scale(0.95);
  transition: opacity 0.35s ease, transform 0.35s ease;
}
.pub-dim-card--active {
  opacity: 1;
  transform: translateY(0) scale(1);
  animation: pub-card-in 0.38s ease both;
}
@keyframes pub-card-in {
  from { opacity: 0; transform: translateY(10px) scale(0.93); }
  to   { opacity: 1; transform: translateY(0) scale(1); }
}
.pub-dim-card--pass { border-color: rgba(74, 222, 128, 0.2); }
.pub-dim-card--fail { border-color: rgba(248, 113, 113, 0.2); }

/* 环形进度 */
.pub-ring {
  width: 40px;
  height: 40px;
  transform: rotate(-90deg);
}
.pub-ring-bg {
  fill: none;
  stroke: rgba(148, 163, 184, 0.1);
  stroke-width: 4;
}
.pub-ring-fill {
  fill: none;
  stroke-width: 4;
  stroke-linecap: round;
  transition: stroke-dasharray 0.5s cubic-bezier(0.4, 0, 0.2, 1);
}

.pub-dim-score {
  font-size: 14px;
  font-weight: 800;
  color: #f1f5f9;
  margin-top: -6px;  /* 叠在环形上 */
  line-height: 1;
}
.pub-dim-label {
  font-size: 9px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: #64748b;
  text-align: center;
  line-height: 1.3;
}
.pub-dim-reason {
  font-size: 9px;
  color: #475569;
  text-align: center;
  line-height: 1.3;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.pub-audit-err {
  font-size: 11px;
  color: #f87171;
  background: rgba(248, 113, 113, 0.08);
  border-radius: 6px;
  padding: 8px 10px;
}

/* 综合得分 */
.pub-overall {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 14px;
  border-radius: 10px;
}
.pub-overall--pass {
  background: rgba(34, 197, 94, 0.08);
  border: 1px solid rgba(34, 197, 94, 0.2);
}
.pub-overall--fail {
  background: rgba(248, 113, 113, 0.07);
  border: 1px solid rgba(248, 113, 113, 0.18);
}
.pub-overall-score {
  font-size: 28px;
  font-weight: 800;
  line-height: 1;
  flex-shrink: 0;
}
.pub-overall--pass .pub-overall-score { color: #4ade80; }
.pub-overall--fail .pub-overall-score { color: #f87171; }
.pub-overall-label {
  font-size: 12px;
  color: #94a3b8;
  line-height: 1.4;
}

/* 成功/失败文字 */
.pub-ok {
  margin-top: 8px;
  font-size: 11px;
  color: #4ade80;
  line-height: 1.4;
}
.pub-error {
  margin-top: 8px;
  font-size: 11px;
  color: #f87171;
  line-height: 1.4;
}
</style>
