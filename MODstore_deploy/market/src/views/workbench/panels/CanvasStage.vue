<script setup lang="ts">
import { watch, onMounted, computed } from 'vue'
import {
  VueFlow,
  useVueFlow,
  type NodeChange,
  type EdgeChange,
  type Connection,
} from '@vue-flow/core'
import { Background } from '@vue-flow/background'
import { Controls } from '@vue-flow/controls'
import { MiniMap } from '@vue-flow/minimap'
import EmployeeModuleNode from '../nodes/EmployeeModuleNode.vue'
import WorkflowFlowEditor from '../../workflow/v2/WorkflowFlowEditor.vue'
import { useWorkbenchStore } from '../../../stores/workbench'
import {
  manifestToNodes,
  manifestToEdges,
  addModuleToManifest,
  removeModuleFromManifest,
} from '../../../composables/useWorkbenchManifest'
import { computeAutoLayout } from '../../workflow/v2/composables/useAutoLayout'

import '@vue-flow/core/dist/style.css'
import '@vue-flow/core/dist/theme-default.css'
import '@vue-flow/controls/dist/style.css'
import '@vue-flow/minimap/dist/style.css'

const store = useWorkbenchStore()

const isWorkflowTarget = computed(() => store.target.kind === 'workflow')
const workflowId = computed(() => {
  const id = store.target.id
  const n = Number(id ?? 0)
  return Number.isFinite(n) && n > 0 ? n : 0
})

const flowInstance = useVueFlow({ id: 'workbench-canvas' })

const nodeTypes = { employeeModule: EmployeeModuleNode }

// ── Sync manifest → canvas nodes/edges ──────────────────────────────────────

function syncManifestToCanvas() {
  const manifest = store.target.manifest as Record<string, unknown>
  const nodes = manifestToNodes(manifest)
  const edges = manifestToEdges(nodes)

  // Apply auto-layout
  const posMap = computeAutoLayout(nodes, edges, {
    direction: 'LR',
    nodeWidth: 240,
    nodeHeight: 90,
    rankSep: 100,
    nodeSep: 60,
  })
  for (const n of nodes) {
    const pos = posMap.get(n.id)
    if (pos) n.position = pos
  }

  store.setCanvasGraph(nodes, edges)
}

onMounted(() => {
  syncManifestToCanvas()
})

watch(
  () => store.target.manifest,
  () => syncManifestToCanvas(),
  { deep: false },
)

// ── Vue Flow event handlers ──────────────────────────────────────────────────

function onNodesChange(changes: NodeChange[]) {
  for (const change of changes) {
    if (change.type === 'position' && change.position) {
      const node = store.canvasNodes.find((n) => n.id === change.id)
      if (node) node.position = change.position
    }
    if (change.type === 'remove') {
      const node = store.canvasNodes.find((n) => n.id === change.id)
      if (!node) continue
      const kind = node.data?.moduleKind
      if (kind) {
        store.target.manifest = removeModuleFromManifest(
          store.target.manifest as Record<string, unknown>,
          kind,
        ) as Record<string, unknown>
      }
    }
  }
}

function onEdgesChange(_changes: EdgeChange[]) {
  // Edge changes are informational for employee modules
}

function onConnect(conn: Connection) {
  store.canvasEdges.push({
    id: `e-${conn.source}-${conn.target}`,
    source: conn.source,
    target: conn.target,
    animated: true,
    style: { stroke: '#6366f1', strokeWidth: 2 },
  })
}

function onNodeClick(event: { node: { id: string } }) {
  store.selectNode(event.node.id)
}

function onPaneClick() {
  store.selectNode(null)
}

function fitView() {
  flowInstance.fitView({ padding: 0.15, duration: 400 })
}

function autoLayout() {
  syncManifestToCanvas()
  setTimeout(() => fitView(), 80)
}

// ── Module library drop ────────────────────────────────────────────────────

function onDragOver(event: DragEvent) {
  event.preventDefault()
  if (event.dataTransfer) event.dataTransfer.dropEffect = 'copy'
}

function onDrop(event: DragEvent) {
  const kind = event.dataTransfer?.getData('application/emp-module-kind')
  if (!kind) return
  store.target.manifest = addModuleToManifest(
    store.target.manifest as Record<string, unknown>,
    kind as import('../../../composables/useWorkbenchManifest').EmployeeModuleKind,
  ) as Record<string, unknown>
  store.dirty = true
  syncManifestToCanvas()
}

defineExpose({ fitView, autoLayout, syncManifestToCanvas })
</script>

<template>
  <div class="canvas-stage" @dragover.prevent="onDragOver" @drop="onDrop">
    <!-- Workflow target: embed the existing workflow editor -->
    <WorkflowFlowEditor
      v-if="isWorkflowTarget && workflowId > 0"
      :workflow-id="workflowId"
      @back="store.target.kind === 'workflow' && $router?.push({ name: 'workflow' })"
    />
    <div v-else-if="isWorkflowTarget && workflowId === 0" class="canvas-empty">
      <p>请先选择或创建一个工作流</p>
    </div>

    <!-- Employee / Mod / Skill target: custom module canvas -->
    <VueFlow v-else
      :nodes="store.canvasNodes"
      :edges="store.canvasEdges"
      :node-types="nodeTypes"
      fit-view-on-init
      :min-zoom="0.3"
      :max-zoom="2"
      class="canvas-flow"
      @nodes-change="onNodesChange"
      @edges-change="onEdgesChange"
      @connect="onConnect"
      @node-click="onNodeClick"
      @pane-click="onPaneClick"
    >
      <Background variant="dots" :gap="20" :size="1" pattern-color="rgba(148,163,184,0.08)" />
      <Controls class="canvas-controls" />
      <MiniMap class="canvas-minimap" node-color="#6366f1" mask-color="rgba(15,23,42,0.7)" />

      <template #node-employeeModule="nodeProps">
        <EmployeeModuleNode v-bind="nodeProps" />
      </template>
    </VueFlow>

    <!-- Canvas toolbar (only for employee/mod/skill canvas) -->
    <div v-if="!isWorkflowTarget" class="canvas-toolbar">
      <button class="canvas-btn" title="适配视图" @click="fitView">⊡ 适配</button>
      <button class="canvas-btn" title="自动布局" @click="autoLayout">⊞ 布局</button>
    </div>
  </div>
</template>

<style scoped>
.canvas-stage {
  flex: 1;
  position: relative;
  overflow: hidden;
  background: #080f1a;
  display: flex;
  flex-direction: column;
}

.canvas-empty {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #475569;
  font-size: 13px;
}

.canvas-flow {
  width: 100%;
  height: 100%;
}

.canvas-toolbar {
  position: absolute;
  top: 12px;
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  gap: 6px;
  z-index: 10;
}

.canvas-btn {
  background: rgba(15, 23, 42, 0.9);
  border: 1px solid rgba(148, 163, 184, 0.15);
  color: #94a3b8;
  font-size: 12px;
  font-weight: 600;
  padding: 5px 12px;
  border-radius: 8px;
  cursor: pointer;
  backdrop-filter: blur(8px);
  transition: all 0.15s ease;
  letter-spacing: 0.02em;
}

.canvas-btn:hover {
  background: rgba(99, 102, 241, 0.15);
  color: #a5b4fc;
  border-color: rgba(99, 102, 241, 0.3);
}

:deep(.canvas-controls) {
  background: rgba(15, 23, 42, 0.9) !important;
  border: 1px solid rgba(148, 163, 184, 0.12) !important;
  border-radius: 10px !important;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3) !important;
}

:deep(.canvas-controls button) {
  color: #94a3b8 !important;
  background: transparent !important;
}

:deep(.canvas-minimap) {
  background: rgba(8, 15, 26, 0.9) !important;
  border: 1px solid rgba(148, 163, 184, 0.1) !important;
  border-radius: 10px !important;
}

:deep(.vue-flow__edge-path) {
  stroke: #6366f1;
  stroke-width: 2;
}
</style>
