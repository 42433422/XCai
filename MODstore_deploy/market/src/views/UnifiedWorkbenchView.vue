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
    </header>

    <section class="focus-layout">
      <EmployeePanel v-if="viewMode === 'employee'" class="focus-embed" />
      <WorkflowPanel v-else-if="viewMode === 'workflow'" />
      <OpenApiConnectorsPanel v-else-if="viewMode === 'integrations'" />
      <VibeCodeSkillPanel v-else-if="viewMode === 'code_skill'" />
      <RepositoryPanel v-else />
    </section>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import EmployeePanel from '../components/workbench/EmployeePanel.vue'
import OpenApiConnectorsPanel from '../components/workbench/OpenApiConnectorsPanel.vue'
import RepositoryPanel from '../components/workbench/RepositoryPanel.vue'
import WorkflowPanel from '../components/workbench/WorkflowPanel.vue'
import VibeCodeSkillPanel from '../components/workbench/VibeCodeSkillPanel.vue'

const route = useRoute()
const router = useRouter()

const allowed = new Set(['employee', 'workflow', 'skill', 'repository', 'integrations', 'code_skill'])

const modeTabs = [
  { mode: 'employee' as const, label: '专注员工制作' },
  { mode: 'workflow' as const, label: '专注 Skill 组' },
  { mode: 'code_skill' as const, label: 'AI 代码技能 (vibe)' },
  { mode: 'repository' as const, label: '专注 Mod 库' },
  { mode: 'integrations' as const, label: 'API 连接器' },
]

const routeFocus = computed(() => {
  const raw = String(route.query.focus || '').trim().toLowerCase()
  if (raw === 'hybrid') return 'employee'
  if (raw === 'skill') return 'workflow'
  return allowed.has(raw) ? raw : 'repository'
})

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
</style>
