<script setup lang="ts">
import { computed } from 'vue'
import { Handle, Position } from '@vue-flow/core'
import { getNodeMeta } from '../composables/useNodeRegistry'
import type { WorkflowFlowNodeData } from '../composables/useWorkflowGraph'

const props = defineProps<{
  id: string
  data: WorkflowFlowNodeData
  selected: boolean
}>()

const meta = computed(() => getNodeMeta(props.data.kind))

const summary = computed(() => {
  const cfg = props.data.config || {}
  const m = meta.value
  switch (m.kind) {
    case 'employee':
      return cfg.employee_id ? `员工 ${cfg.employee_id}` : '未选择员工'
    case 'condition':
      return cfg.expression ? String(cfg.expression).slice(0, 48) : '未配置表达式'
    case 'openapi_operation':
      return cfg.connector_id && cfg.operation_id
        ? `${cfg.connector_id}#${cfg.operation_id}`
        : '未配置连接器'
    case 'knowledge_search':
      return cfg.kb_id ? `KB ${cfg.kb_id}` : '未选择知识库'
    case 'webhook_trigger':
      return cfg.secret ? '含独立密钥' : '使用全局密钥'
    case 'cron_trigger':
      return cfg.cron ? String(cfg.cron) : '未设置 Cron'
    case 'variable_set':
      return cfg.name ? `${cfg.name} =` : '未设置变量'
    default:
      return m.description
  }
})
</script>

<template>
  <div
    class="wf2-node"
    :class="{ 'wf2-node--selected': selected }"
    :style="{ '--accent': meta.accent }"
  >
    <Handle
      v-if="meta.hasInput"
      type="target"
      :position="Position.Left"
      class="wf2-handle wf2-handle--in"
    />

    <header class="wf2-node__head">
      <span class="wf2-node__icon" :style="{ background: meta.accent }">{{ meta.icon }}</span>
      <div class="wf2-node__titles">
        <span class="wf2-node__type">{{ meta.label }}</span>
        <span class="wf2-node__name" :title="data.label">{{ data.label }}</span>
      </div>
    </header>

    <p class="wf2-node__summary" :title="String(summary)">{{ summary }}</p>

    <template v-if="meta.branchOutputs">
      <Handle
        type="source"
        :position="Position.Right"
        id="true"
        class="wf2-handle wf2-handle--out wf2-handle--true"
      />
      <Handle
        type="source"
        :position="Position.Right"
        id="false"
        class="wf2-handle wf2-handle--out wf2-handle--false"
      />
      <span class="wf2-branch-label wf2-branch-label--true">true</span>
      <span class="wf2-branch-label wf2-branch-label--false">false</span>
    </template>
    <Handle
      v-else-if="meta.hasOutput"
      type="source"
      :position="Position.Right"
      class="wf2-handle wf2-handle--out"
    />
  </div>
</template>

<style scoped>
.wf2-node {
  --accent: #6366f1;
  position: relative;
  width: 220px;
  min-height: 92px;
  background: #ffffff;
  border: 1px solid color-mix(in srgb, var(--accent) 25%, #e2e8f0);
  border-left: 4px solid var(--accent);
  border-radius: 10px;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04), 0 8px 24px -16px rgba(15, 23, 42, 0.18);
  padding: 10px 12px 12px;
  font-family: inherit;
  cursor: grab;
  transition: box-shadow 0.18s ease, transform 0.18s ease, border-color 0.18s ease;
}

.wf2-node--selected {
  border-color: var(--accent);
  box-shadow: 0 0 0 2px color-mix(in srgb, var(--accent) 30%, transparent),
    0 12px 28px -16px rgba(15, 23, 42, 0.28);
}

.wf2-node:active {
  cursor: grabbing;
}

.wf2-node__head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}

.wf2-node__icon {
  width: 26px;
  height: 26px;
  border-radius: 7px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 14px;
  flex-shrink: 0;
}

.wf2-node__titles {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.wf2-node__type {
  font-size: 11px;
  letter-spacing: 0.04em;
  color: #64748b;
  text-transform: uppercase;
}

.wf2-node__name {
  font-size: 14px;
  font-weight: 600;
  color: #0f172a;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.wf2-node__summary {
  font-size: 12px;
  color: #475569;
  margin: 0;
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.wf2-handle {
  width: 10px;
  height: 10px;
  background: var(--accent);
  border: 2px solid #fff;
}

.wf2-handle--true {
  top: 38%;
  background: #22c55e;
}

.wf2-handle--false {
  top: 72%;
  background: #ef4444;
}

.wf2-branch-label {
  position: absolute;
  right: -42px;
  font-size: 10px;
  color: #94a3b8;
  pointer-events: none;
}

.wf2-branch-label--true {
  top: calc(38% - 6px);
}

.wf2-branch-label--false {
  top: calc(72% - 6px);
}
</style>
