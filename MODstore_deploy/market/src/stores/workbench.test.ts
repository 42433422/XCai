import { describe, it, expect, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useWorkbenchStore } from './workbench'
import { createEmptyEmployeeConfigV2 } from '../employeeConfigV2'

describe('useWorkbenchStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('initialises with employee target kind and empty manifest', () => {
    const store = useWorkbenchStore()
    expect(store.target.kind).toBe('employee')
    expect(store.target.id).toBeNull()
    expect(store.target.manifest).toBeDefined()
  })

  it('setTarget updates kind, id, manifest and resets selection', () => {
    const store = useWorkbenchStore()
    const manifest = createEmptyEmployeeConfigV2() as Record<string, unknown>
    store.setTarget('workflow', '42', manifest, '测试工作流')
    expect(store.target.kind).toBe('workflow')
    expect(store.target.id).toBe('42')
    expect(store.target.name).toBe('测试工作流')
    expect(store.selectedNodeId).toBeNull()
    expect(store.dirty).toBe(false)
  })

  it('patchManifest writes deeply nested value and marks dirty', () => {
    const store = useWorkbenchStore()
    store.patchManifest('identity.name', '客服助手')
    expect((store.target.manifest.identity as Record<string, unknown>).name).toBe('客服助手')
    expect(store.dirty).toBe(true)
  })

  it('patchManifest creates intermediate objects when missing', () => {
    const store = useWorkbenchStore()
    store.setTarget('employee', null, {}, '测试')
    store.patchManifest('cognition.agent.system_prompt', '你好')
    const cog = store.target.manifest.cognition as Record<string, unknown>
    const agent = cog.agent as Record<string, unknown>
    expect(agent.system_prompt).toBe('你好')
  })

  it('selectNode sets selectedNodeId and switches inspector to node mode', () => {
    const store = useWorkbenchStore()
    store.selectNode('emp-identity')
    expect(store.selectedNodeId).toBe('emp-identity')
    expect(store.inspectorMode).toBe('node')
  })

  it('selectNode(null) switches inspector to library mode', () => {
    const store = useWorkbenchStore()
    store.selectNode('emp-identity')
    store.selectNode(null)
    expect(store.selectedNodeId).toBeNull()
    expect(store.inspectorMode).toBe('library')
  })

  it('chat message push and chunk append', () => {
    const store = useWorkbenchStore()
    store.pushChatMessage({ id: 'msg-1', role: 'user', content: 'hello', ts: Date.now() })
    store.pushChatMessage({ id: 'msg-2', role: 'assistant', content: '', ts: Date.now() })
    store.appendChatChunk('msg-2', '你好')
    store.appendChatChunk('msg-2', '！')
    expect(store.chatMessages[1].content).toBe('你好！')
  })

  it('agent run lifecycle: start → pushEvent → finish', () => {
    const store = useWorkbenchStore()
    const run = {
      id: 'run-1',
      source: 'employee-draft' as const,
      brief: '测试员工',
      status: 'running' as const,
      events: [],
      manifest: null,
      startedAt: Date.now(),
      endedAt: null,
    }
    store.startRun(run)
    expect(store.currentRunId).toBe('run-1')
    expect(store.inspectorMode).toBe('run')

    store.pushRunEvent('run-1', { id: 'ev-1', stage: 'parse_intent', label: '解析意图', payload: null, status: 'done', ts: Date.now() })
    expect(store.agentRuns[0].events[0].stage).toBe('parse_intent')

    const manifest = { identity: { id: 'x', name: '测试' } }
    store.finishRun('run-1', 'done', manifest as Record<string, unknown>)
    expect(store.agentRuns[0].status).toBe('done')
    expect(store.agentRuns[0].manifest).toEqual(manifest)
    // manifest auto-applied to target
    expect(store.target.manifest).toEqual(manifest)
    expect(store.dirty).toBe(true)
  })
})
