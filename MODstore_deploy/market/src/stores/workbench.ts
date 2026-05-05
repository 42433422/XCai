import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { createEmptyEmployeeConfigV2 } from '../employeeConfigV2'
import { api } from '../api'

// Use generic shapes to avoid @vue-flow/core deep-generic TS2589 errors
// eslint-disable-next-line @typescript-eslint/no-explicit-any
type FlowNode = any
// eslint-disable-next-line @typescript-eslint/no-explicit-any
type FlowEdge = any

// ─── Target kinds ───────────────────────────────────────────────────────────

export type TargetKind = 'employee' | 'workflow' | 'mod' | 'skill'

export interface WorkbenchTarget {
  kind: TargetKind
  id: string | null
  manifest: Record<string, unknown>
  name: string
}

// ─── Chat ────────────────────────────────────────────────────────────────────

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  ts: number
}

// ─── Agent loop runs ─────────────────────────────────────────────────────────

export type AgentEventStatus = 'running' | 'done' | 'error' | 'idle'

export interface AgentEvent {
  id: string
  stage: string
  label: string
  payload: unknown
  status: AgentEventStatus
  ts: number
}

export type AgentRunSource = 'employee-draft' | 'script-workflow' | 'vibe-code' | 'mod-session'

export interface AgentRun {
  id: string
  source: AgentRunSource
  brief: string
  status: AgentEventStatus
  events: AgentEvent[]
  manifest: Record<string, unknown> | null
  startedAt: number
  endedAt: number | null
}

// ─── Inspector ───────────────────────────────────────────────────────────────

export type InspectorMode = 'node' | 'library' | 'run' | 'diff'

// ─── Store ───────────────────────────────────────────────────────────────────

export const useWorkbenchStore = defineStore('workbench', () => {
  // Current editing target
  const target = ref<WorkbenchTarget>({
    kind: 'employee',
    id: null,
    manifest: createEmptyEmployeeConfigV2() as Record<string, unknown>,
    name: '新员工',
  })

  // Vue Flow canvas state (source of truth driven by manifest via useWorkbenchManifest)
  const canvasNodes = ref<FlowNode[]>([])
  const canvasEdges = ref<FlowEdge[]>([])
  const selectedNodeId = ref<string | null>(null)

  // Chat (left rail)
  const chatMessages = ref<ChatMessage[]>([])
  const chatStreaming = ref(false)
  let chatAborter: AbortController | null = null

  // Agent runs (left rail timeline)
  const agentRuns = ref<AgentRun[]>([])
  const currentRunId = ref<string | null>(null)

  // Inspector (right rail)
  const inspectorMode = ref<InspectorMode>('library')

  // Research context cache
  const researchContext = ref<string>('')
  const researchSources = ref<string[]>([])

  // Unsaved state
  const dirty = ref(false)
  const lastSavedAt = ref<number | null>(null)

  // Workflow gate (for employee canvas: selected workflow sandbox status)
  const eligibleWorkflows = ref<unknown[]>([])
  const allWorkflowOptions = ref<unknown[]>([])
  const workflowGateLoading = ref(false)

  // ── Computed ──────────────────────────────────────────────────────────────

  function getSelectedNode() {
    return canvasNodes.value.find((n) => n.id === selectedNodeId.value) ?? null
  }
  const selectedNode = computed(getSelectedNode)

  const currentRun = computed<AgentRun | null>(() =>
    agentRuns.value.find((r) => r.id === currentRunId.value) ?? null,
  )

  // ── Actions ───────────────────────────────────────────────────────────────

  function setTarget(kind: TargetKind, id: string | null, manifest?: Record<string, unknown>, name?: string) {
    target.value = {
      kind,
      id: id ?? null,
      manifest: manifest ?? (createEmptyEmployeeConfigV2() as Record<string, unknown>),
      name: name ?? '新员工',
    }
    selectedNodeId.value = null
    inspectorMode.value = 'library'
    dirty.value = false
  }

  function patchManifest(path: string, value: unknown) {
    const keys = path.split('.')
    let obj: Record<string, unknown> = target.value.manifest
    for (let i = 0; i < keys.length - 1; i++) {
      const k = keys[i]
      if (obj[k] == null || typeof obj[k] !== 'object') {
        obj[k] = {}
      }
      obj = obj[k] as Record<string, unknown>
    }
    obj[keys[keys.length - 1]] = value
    dirty.value = true
  }

  function selectNode(id: string | null) {
    selectedNodeId.value = id
    inspectorMode.value = id ? 'node' : 'library'
  }

  function setCanvasGraph(nodes: FlowNode[], edges: FlowEdge[]) {
    canvasNodes.value = nodes
    canvasEdges.value = edges
  }

  // Chat helpers
  function pushChatMessage(msg: ChatMessage) {
    chatMessages.value.push(msg)
  }

  function appendChatChunk(id: string, chunk: string) {
    const msg = chatMessages.value.find((m) => m.id === id)
    if (msg) msg.content += chunk
  }

  function setChatStreaming(v: boolean, ctrl?: AbortController | null) {
    chatStreaming.value = v
    if (ctrl !== undefined) chatAborter = ctrl
  }

  function abortChat() {
    chatAborter?.abort()
    chatAborter = null
    chatStreaming.value = false
  }

  // Agent run helpers
  function startRun(run: AgentRun) {
    agentRuns.value.unshift(run)
    currentRunId.value = run.id
    inspectorMode.value = 'run'
  }

  function pushRunEvent(runId: string, ev: AgentEvent) {
    const run = agentRuns.value.find((r) => r.id === runId)
    if (!run) return
    const existing = run.events.findIndex((e) => e.stage === ev.stage)
    if (existing >= 0) {
      run.events[existing] = ev
    } else {
      run.events.push(ev)
    }
  }

  function finishRun(runId: string, status: AgentEventStatus, manifest?: Record<string, unknown> | null) {
    const run = agentRuns.value.find((r) => r.id === runId)
    if (!run) return
    run.status = status
    run.endedAt = Date.now()
    if (manifest) {
      run.manifest = manifest
      // Auto-apply manifest to current target when run is done
      if (status === 'done') {
        target.value.manifest = manifest
        dirty.value = true
      }
    }
  }

  // Research context
  function setResearch(context: string, sources: string[]) {
    researchContext.value = context
    researchSources.value = sources
  }

  // Workflow gate
  async function loadEligibleWorkflows() {
    workflowGateLoading.value = true
    try {
      const res = (await api.listEmployeeEligibleWorkflows()) as { workflows?: unknown[]; all_workflows?: unknown[] }
      eligibleWorkflows.value = Array.isArray(res?.workflows) ? res.workflows : []
      allWorkflowOptions.value = Array.isArray(res?.all_workflows)
        ? res.all_workflows
        : eligibleWorkflows.value
    } catch {
      eligibleWorkflows.value = []
      allWorkflowOptions.value = []
    } finally {
      workflowGateLoading.value = false
    }
  }

  return {
    // State
    target,
    canvasNodes,
    canvasEdges,
    selectedNodeId,
    chatMessages,
    chatStreaming,
    agentRuns,
    currentRunId,
    inspectorMode,
    researchContext,
    researchSources,
    dirty,
    lastSavedAt,
    eligibleWorkflows,
    allWorkflowOptions,
    workflowGateLoading,
    // Computed
    selectedNode,
    currentRun,
    // Actions
    setTarget,
    patchManifest,
    selectNode,
    setCanvasGraph,
    pushChatMessage,
    appendChatChunk,
    setChatStreaming,
    abortChat,
    startRun,
    pushRunEvent,
    finishRun,
    setResearch,
    loadEligibleWorkflows,
  }
})
