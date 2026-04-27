<script setup lang="ts">
import { ref } from 'vue'
import { listByCategory, type NodeKind } from '../composables/useNodeRegistry'

defineEmits<{
  (e: 'add', kind: NodeKind): void
}>()

const groups = listByCategory()
const collapsed = ref<Record<string, boolean>>({})

function toggle(cat: string) {
  collapsed.value[cat] = !collapsed.value[cat]
}

function onDragStart(ev: DragEvent, kind: NodeKind) {
  if (!ev.dataTransfer) return
  ev.dataTransfer.setData('application/wf2-node-kind', kind)
  ev.dataTransfer.effectAllowed = 'move'
}
</script>

<template>
  <aside class="wf2-library">
    <h3 class="wf2-library__title">节点库</h3>
    <p class="wf2-library__hint">点击或拖入画布</p>
    <div v-for="g in groups" :key="g.category" class="wf2-library__group">
      <button class="wf2-library__group-head" type="button" @click="toggle(g.category)">
        <span>{{ g.label }}</span>
        <span class="wf2-library__group-count">{{ g.items.length }}</span>
      </button>
      <ul v-show="!collapsed[g.category]" class="wf2-library__list">
        <li
          v-for="m in g.items"
          :key="m.kind"
          class="wf2-library__item"
          :draggable="true"
          @dragstart="onDragStart($event, m.kind)"
          @click="$emit('add', m.kind)"
        >
          <span class="wf2-library__item-icon" :style="{ background: m.accent }">{{ m.icon }}</span>
          <div class="wf2-library__item-text">
            <span class="wf2-library__item-label">{{ m.label }}</span>
            <span class="wf2-library__item-desc">{{ m.description }}</span>
          </div>
        </li>
      </ul>
    </div>
  </aside>
</template>

<style scoped>
.wf2-library {
  width: 248px;
  flex-shrink: 0;
  border-right: 1px solid #e2e8f0;
  background: #f8fafc;
  padding: 16px 12px;
  overflow-y: auto;
  height: 100%;
}

.wf2-library__title {
  margin: 0 0 4px;
  font-size: 14px;
  font-weight: 600;
  color: #0f172a;
}

.wf2-library__hint {
  margin: 0 0 12px;
  font-size: 12px;
  color: #94a3b8;
}

.wf2-library__group {
  margin-bottom: 8px;
}

.wf2-library__group-head {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 8px;
  background: transparent;
  border: 0;
  cursor: pointer;
  font-size: 12px;
  font-weight: 600;
  color: #475569;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  border-radius: 6px;
}

.wf2-library__group-head:hover {
  background: #e2e8f0;
}

.wf2-library__group-count {
  font-size: 10px;
  color: #94a3b8;
  background: #e2e8f0;
  padding: 1px 6px;
  border-radius: 999px;
}

.wf2-library__list {
  list-style: none;
  margin: 4px 0 0;
  padding: 0;
}

.wf2-library__item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 8px;
  border-radius: 8px;
  cursor: grab;
  transition: background 0.15s ease;
}

.wf2-library__item:hover {
  background: #fff;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.05);
}

.wf2-library__item:active {
  cursor: grabbing;
}

.wf2-library__item-icon {
  width: 28px;
  height: 28px;
  border-radius: 7px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 14px;
  flex-shrink: 0;
}

.wf2-library__item-text {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.wf2-library__item-label {
  font-size: 13px;
  color: #0f172a;
  font-weight: 500;
}

.wf2-library__item-desc {
  font-size: 11px;
  color: #94a3b8;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
</style>
