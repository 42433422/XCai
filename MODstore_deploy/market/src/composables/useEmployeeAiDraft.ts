/**
 * SSE 消费层：连接 POST /api/workbench/employee-ai/draft
 * 并把 6 阶段事件映射为响应式状态，供 EmployeeAiDraftReview 组件消费。
 */

import { reactive, ref, readonly } from 'vue'

export type StageStatus = 'idle' | 'running' | 'done' | 'error'

export interface StageState<T = unknown> {
  status: StageStatus
  data: T | null
  error: string
  warnings?: string[]
}

export interface IntentData {
  id: string
  name: string
  role: string
  scenario: string
  industry: string
  complexity: string
}

export interface WorkflowData {
  workflow_id: number | null
  workflow_name: string
  match_score: number
  generated: boolean
  sandbox_passed?: boolean
}

export interface V2Data {
  perception: Record<string, unknown>
  memory: Record<string, unknown>
  cognition: Record<string, unknown>
  actions: Record<string, unknown>
}

export interface SkillData {
  name: string
  brief: string
  unverified: boolean
}

export interface PricingData {
  tier: string
  cny: number
  period: string
  reasoning: string
}

export interface PipelineStages {
  parse_intent: StageState<IntentData>
  resolve_workflow: StageState<WorkflowData>
  design_v2: StageState<V2Data>
  suggest_skills: StageState<SkillData[]>
  suggest_pricing: StageState<PricingData>
  assemble: StageState<Record<string, unknown>>
}

export interface PipelineStatus {
  phase: 'idle' | 'running' | 'done' | 'error'
  current: string
  manifest: Record<string, unknown> | null
  fatalError: string
}

function makeStageState<T = unknown>(): StageState<T> {
  return { status: 'idle', data: null, error: '', warnings: [] }
}

function makeStages(): PipelineStages {
  return {
    parse_intent: makeStageState<IntentData>(),
    resolve_workflow: makeStageState<WorkflowData>(),
    design_v2: makeStageState<V2Data>(),
    suggest_skills: makeStageState<SkillData[]>(),
    suggest_pricing: makeStageState<PricingData>(),
    assemble: makeStageState<Record<string, unknown>>(),
  }
}

export function useEmployeeAiDraft() {
  const stages = reactive<PipelineStages>(makeStages())
  const status = reactive<PipelineStatus>({
    phase: 'idle',
    current: '',
    manifest: null,
    fatalError: '',
  })
  const progressMessages = ref<string[]>([])

  let _controller: AbortController | null = null

  function reset() {
    Object.assign(stages, makeStages())
    status.phase = 'idle'
    status.current = ''
    status.manifest = null
    status.fatalError = ''
    progressMessages.value = []
  }

  function abort() {
    _controller?.abort()
    _controller = null
    if (status.phase === 'running') {
      status.phase = 'error'
      status.fatalError = '已取消'
    }
  }

  function _applyEvent(ev: Record<string, unknown>) {
    const event = ev.event as string
    const stage = ev.stage as string

    if (event === 'stage_start') {
      status.current = stage
      if (stage in stages) {
        ;(stages as Record<string, StageState>)[stage].status = 'running'
      }
      return
    }

    if (event === 'stage_progress') {
      if (typeof ev.message === 'string') {
        progressMessages.value.push(ev.message)
      }
      return
    }

    if (event === 'stage_done') {
      if (stage in stages) {
        const s = (stages as Record<string, StageState>)[stage]
        s.status = 'done'
        s.data = (ev.data ?? null) as unknown
        s.warnings = Array.isArray(ev.warnings) ? (ev.warnings as string[]) : []
      }
      return
    }

    if (event === 'stage_error') {
      if (stage in stages) {
        const s = (stages as Record<string, StageState>)[stage]
        s.status = 'error'
        s.error = String(ev.error ?? '')
      }
      // Fatal stages: parse_intent, resolve_workflow, design_v2, assemble
      const retryable = ev.retryable === true
      if (!retryable && stage !== 'suggest_skills' && stage !== 'suggest_pricing') {
        status.phase = 'error'
        status.fatalError = String(ev.error ?? '流水线失败')
      }
      return
    }

    if (event === 'pipeline_done') {
      status.phase = 'done'
      status.manifest = (ev.manifest as Record<string, unknown>) ?? null
      return
    }

    if (event === 'pipeline_error') {
      status.phase = 'error'
      status.fatalError = String(ev.error ?? '初始化失败')
    }
  }

  async function start(
    brief: string,
    options: {
      provider?: string
      model?: string
      suggestedId?: string
      token?: string
    } = {},
  ) {
    abort()
    reset()
    status.phase = 'running'

    _controller = new AbortController()
    const { signal } = _controller

    const headers: Record<string, string> = { 'Content-Type': 'application/json' }
    if (options.token) headers['Authorization'] = `Bearer ${options.token}`

    let response: Response
    try {
      response = await fetch('/api/workbench/employee-ai/draft', {
        method: 'POST',
        headers,
        body: JSON.stringify({
          brief,
          provider: options.provider || undefined,
          model: options.model || undefined,
          suggested_id: options.suggestedId || undefined,
        }),
        signal,
      })
    } catch (e: unknown) {
      if ((e as Error)?.name === 'AbortError') return
      status.phase = 'error'
      status.fatalError = `请求失败: ${(e as Error)?.message || String(e)}`
      return
    }

    if (!response.ok) {
      let msg = `HTTP ${response.status}`
      try {
        const body = await response.json()
        msg = body?.detail || body?.error || msg
      } catch {
        /* ignore */
      }
      status.phase = 'error'
      status.fatalError = msg
      return
    }

    const reader = response.body?.getReader()
    if (!reader) {
      status.phase = 'error'
      status.fatalError = '无法读取 SSE 流'
      return
    }

    const decoder = new TextDecoder()
    let buffer = ''
    try {
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() ?? ''
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const ev = JSON.parse(line.slice(6))
              _applyEvent(ev)
            } catch {
              /* ignore malformed line */
            }
          }
        }
      }
    } catch (e: unknown) {
      if ((e as Error)?.name === 'AbortError') return
      if (status.phase === 'running') {
        status.phase = 'error'
        status.fatalError = `流中断: ${(e as Error)?.message || String(e)}`
      }
    } finally {
      reader.releaseLock()
    }

    if (status.phase === 'running') {
      status.phase = 'error'
      status.fatalError = '流意外结束'
    }
  }

  /**
   * 重新触发单个阶段（用于"重生成此模块"按钮）。
   * 简单实现：用当前 manifest 里的数据作为 brief 重启整个流水线，
   * 但仅把对应 stage 的状态标记为 running，让父组件决定如何合并结果。
   *
   * 注意：真正的单 stage 重试需要后端支持独立端点（v2 roadmap），
   * 此处仅重置该 stage 的显示状态供 UI 反馈使用，实际重新运行需调用 start()。
   */
  function markStageForRetry(stageId: keyof PipelineStages) {
    const s = stages[stageId] as StageState
    s.status = 'idle'
    s.error = ''
    s.data = null
  }

  return {
    stages: readonly(stages) as PipelineStages,
    status: readonly(status) as PipelineStatus,
    progressMessages: readonly(progressMessages),
    start,
    abort,
    reset,
    markStageForRetry,
  }
}
