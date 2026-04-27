<template>
  <div class="unified-workbench">
    <header class="unified-toolbar">
      <div class="mode-tabs" role="tablist" aria-label="统一工作台视图">
        <button type="button" class="mode-tab" :class="{ 'mode-tab--active': viewMode === 'hybrid' }" @click="setViewMode('hybrid')">
          同屏工作台
        </button>
        <button type="button" class="mode-tab" :class="{ 'mode-tab--active': viewMode === 'employee' }" @click="setViewMode('employee')">
          专注员工制作
        </button>
        <button type="button" class="mode-tab" :class="{ 'mode-tab--active': viewMode === 'workflow' }" @click="setViewMode('workflow')">
          专注工作流
        </button>
        <button type="button" class="mode-tab" :class="{ 'mode-tab--active': viewMode === 'repository' }" @click="setViewMode('repository')">
          专注Mod库
        </button>
      </div>
      <div v-if="viewMode === 'hybrid'" class="panel-tabs" role="tablist" aria-label="同屏面板切换">
        <button type="button" class="panel-tab" :class="{ 'panel-tab--active': hybridPanel === 'workflow' && hybridSideVisible }" @click="toggleHybridPanel('workflow')">
          工作流管理
        </button>
        <button type="button" class="panel-tab" :class="{ 'panel-tab--active': hybridPanel === 'repository' && hybridSideVisible }" @click="toggleHybridPanel('repository')">
          Mod 库
        </button>
      </div>
    </header>

    <section v-if="viewMode === 'hybrid'" class="hybrid-layout">
      <div class="hybrid-main">
        <EmployeePanel />
      </div>
      <aside v-if="hybridSideVisible" class="hybrid-side">
        <WorkflowPanel v-if="hybridPanel === 'workflow'" />
        <RepositoryPanel v-else />
      </aside>
    </section>

    <section v-else class="focus-layout">
      <EmployeePanel v-if="viewMode === 'employee'" />
      <WorkflowPanel v-else-if="viewMode === 'workflow'" />
      <RepositoryPanel v-else />
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import EmployeePanel from '../components/workbench/EmployeePanel.vue'
import RepositoryPanel from '../components/workbench/RepositoryPanel.vue'
import WorkflowPanel from '../components/workbench/WorkflowPanel.vue'

const route = useRoute()
const router = useRouter()

const allowed = new Set(['hybrid', 'employee', 'workflow', 'repository'])
const routeFocus = computed(() => {
  const raw = String(route.query.focus || '').trim().toLowerCase()
  return allowed.has(raw) ? raw : 'hybrid'
})

const viewMode = ref(routeFocus.value)
const hybridPanel = ref(routeFocus.value === 'repository' ? 'repository' : 'workflow')
const hybridSideVisible = ref(true)

watch(routeFocus, (v) => {
  viewMode.value = v
  if (v === 'repository' || v === 'workflow') hybridPanel.value = v
})

function setViewMode(mode) {
  if (!allowed.has(mode)) return
  if (mode === 'repository' || mode === 'workflow') hybridPanel.value = mode
  hybridSideVisible.value = true
  const query = { ...route.query, focus: mode }
  void router.replace({ name: 'workbench-unified', query })
}

function toggleHybridPanel(panel) {
  if (hybridPanel.value === panel) {
    hybridSideVisible.value = !hybridSideVisible.value
  } else {
    hybridPanel.value = panel
    hybridSideVisible.value = true
  }
}
</script>

<style scoped>
.unified-workbench {
  display: flex;
  flex-direction: column;
  min-height: 0;
  height: 100%;
  background: #050505;
}

.unified-toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 0.6rem 1rem;
  padding: 0.65rem 0.8rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(8, 8, 8, 0.95);
}

.mode-tabs,
.panel-tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
}

.mode-tab,
.panel-tab {
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.03);
  color: rgba(255, 255, 255, 0.72);
  padding: 0.35rem 0.7rem;
  font-size: 0.86rem;
  cursor: pointer;
}

.mode-tab--active,
.panel-tab--active {
  color: #c7e5ff;
  border-color: #2ba8ff;
  box-shadow: 0 0 0 1px rgba(43, 168, 255, 0.2) inset;
}

.hybrid-layout,
.focus-layout {
  flex: 1 1 auto;
  min-height: 0;
}

.hybrid-layout {
  display: grid;
}

.hybrid-layout:has(.hybrid-side) {
  grid-template-columns: minmax(0, 1fr) minmax(380px, 44vw);
}

.hybrid-layout:not(:has(.hybrid-side)) {
  grid-template-columns: 1fr;
}

.hybrid-main,
.hybrid-side {
  min-height: 0;
  overflow: auto;
}

.hybrid-side {
  border-left: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(4, 4, 4, 0.9);
}

@media (max-width: 1200px) {
  .hybrid-layout {
    grid-template-columns: 1fr;
  }
  .hybrid-side {
    border-left: none;
    border-top: 1px solid rgba(255, 255, 255, 0.08);
    max-height: 46vh;
  }
}
</style>
