<template>
  <div class="unified-workbench">
    <header class="unified-toolbar">
      <div class="mode-tabs" role="tablist" aria-label="统一工作台视图">
        <button
          v-for="tab in modeTabs"
          :key="tab.mode"
          type="button"
          role="tab"
          class="mode-tab"
          :class="{ 'mode-tab--active': viewMode === tab.mode }"
          :aria-selected="viewMode === tab.mode"
          @click="setViewMode(tab.mode)"
        >
          {{ tab.label }}
        </button>
      </div>
      <div
        v-if="viewMode === 'employee'"
        class="employee-subtabs"
        role="tablist"
        aria-label="员工制作子视图"
      >
        <button
          type="button"
          role="tab"
          class="employee-subtab"
          :class="{ 'employee-subtab--active': employeeSubview === 'wizard' }"
          :aria-selected="employeeSubview === 'wizard'"
          @click="setEmployeeSubview('wizard')"
        >
          制作向导
        </button>
        <button
          type="button"
          role="tab"
          class="employee-subtab"
          :class="{ 'employee-subtab--active': employeeSubview === 'list' }"
          :aria-selected="employeeSubview === 'list'"
          @click="setEmployeeSubview('list')"
        >
          我的员工
        </button>
      </div>
    </header>

    <section class="focus-layout">
      <template v-if="viewMode === 'employee'">
        <MyEmployeesChatView v-if="employeeSubview === 'list'" embedded class="focus-embed" />
        <EmployeePanel v-else />
      </template>
      <WorkflowPanel v-else-if="viewMode === 'workflow'" />
      <OpenApiConnectorsPanel v-else-if="viewMode === 'integrations'" />
      <RepositoryPanel v-else />
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import EmployeePanel from '../components/workbench/EmployeePanel.vue'
import OpenApiConnectorsPanel from '../components/workbench/OpenApiConnectorsPanel.vue'
import RepositoryPanel from '../components/workbench/RepositoryPanel.vue'
import WorkflowPanel from '../components/workbench/WorkflowPanel.vue'
import MyEmployeesChatView from './MyEmployeesChatView.vue'

const route = useRoute()
const router = useRouter()

const allowed = new Set(['employee', 'workflow', 'skill', 'repository', 'integrations'])

const modeTabs = [
  { mode: 'employee' as const, label: '专注员工制作' },
  { mode: 'workflow' as const, label: '专注 Skill 组' },
  { mode: 'repository' as const, label: '专注 Mod 库' },
  { mode: 'integrations' as const, label: 'API 连接器' },
]

const routeFocus = computed(() => {
  const raw = String(route.query.focus || '').trim().toLowerCase()
  if (raw === 'hybrid') return 'employee'
  if (raw === 'skill') return 'workflow'
  return allowed.has(raw) ? raw : 'employee'
})

const employeeSubview = computed(() =>
  routeFocus.value === 'employee' && String(route.query.employeeView || '').trim().toLowerCase() === 'list'
    ? 'list'
    : 'wizard',
)

const viewMode = ref(routeFocus.value)

watch(
  () => route.query.focus,
  (focus) => {
    const f = String(focus || '').trim().toLowerCase()
    if (f === 'hybrid') {
      void router.replace({ name: 'workbench-unified', query: { ...route.query, focus: 'employee' } })
      return
    }
    if (f === 'workflow') {
      void router.replace({ name: 'workbench-unified', query: { ...route.query, focus: 'skill' } })
    }
  },
  { immediate: true },
)

watch(routeFocus, (v) => {
  viewMode.value = v
})

function setViewMode(mode: string) {
  if (!allowed.has(mode)) return
  const query: Record<string, string | string[]> = { ...route.query } as Record<string, string | string[]>
  query.focus = mode === 'workflow' ? 'skill' : mode
  if (mode !== 'employee') {
    delete query.employeeView
  }
  void router.replace({ name: 'workbench-unified', query })
}

function setEmployeeSubview(sub: 'wizard' | 'list') {
  const query: Record<string, string | string[]> = { ...route.query } as Record<string, string | string[]>
  query.focus = 'employee'
  if (sub === 'list') {
    query.employeeView = 'list'
  } else {
    delete query.employeeView
  }
  void router.replace({ name: 'workbench-unified', query })
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
  gap: 0.6rem 1rem;
  padding: 0.65rem 0.8rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(8, 8, 8, 0.95);
}

.mode-tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
}

.mode-tab {
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.03);
  color: rgba(255, 255, 255, 0.72);
  padding: 0.35rem 0.7rem;
  font-size: 0.86rem;
  cursor: pointer;
}

.mode-tab--active {
  color: #c7e5ff;
  border-color: #2ba8ff;
  box-shadow: 0 0 0 1px rgba(43, 168, 255, 0.2) inset;
}

.focus-layout {
  flex: 1 1 auto;
  min-height: 0;
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.focus-embed {
  flex: 1 1 auto;
  min-height: 0;
  min-width: 0;
  overflow: auto;
}

.employee-subtabs {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
  align-items: center;
}

.employee-subtab {
  border: 1px solid rgba(255, 255, 255, 0.14);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.02);
  color: rgba(255, 255, 255, 0.65);
  padding: 0.28rem 0.65rem;
  font-size: 0.82rem;
  cursor: pointer;
}

.employee-subtab--active {
  color: #e8d4ff;
  border-color: rgba(167, 139, 250, 0.55);
  box-shadow: 0 0 0 1px rgba(167, 139, 250, 0.15) inset;
}
</style>
