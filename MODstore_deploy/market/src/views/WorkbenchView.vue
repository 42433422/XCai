<template>
  <div class="workbench">
    <nav class="wb-scene-nav">
      <a href="/workbench/home" class="wb-scene-nav-item" :class="{ 'wb-scene-nav-item--active': isWorkbenchHome }" @click.prevent="navigateTo({ name: 'workbench-home' })">
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"><path d="M2 2h5v5H2zM9 2h5v5H9zM2 9h5v5H2zM9 9h5v5H9z"/></svg>
        <span>首页</span>
      </a>
      <a href="/workbench/unified?focus=repository" class="wb-scene-nav-item" :class="{ 'wb-scene-nav-item--active': isUnifiedRepo }" @click.prevent="navigateTo({ name: 'workbench-unified', query: { focus: 'repository' } })">
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"><rect x="1.5" y="1.5" width="13" height="13" rx="2"/><path d="M5 8h6M8 5v6"/></svg>
        <span>统一工作台</span>
      </a>
      <a href="/workbench/script-workflows" class="wb-scene-nav-item" :class="{ 'wb-scene-nav-item--active': scriptWorkflowsNavActive }" @click.prevent="navigateTo({ name: 'workbench-script-workflows' })">
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"><path d="M2 4h12M2 8h8M2 12h5"/></svg>
        <span>脚本工作流</span>
      </a>
      <a href="/workbench/employees" class="wb-scene-nav-item" :class="{ 'wb-scene-nav-item--active': myEmployeesNavActive }" @click.prevent="navigateTo({ name: 'workbench-employees' })">
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"><circle cx="8" cy="5" r="2.5"/><path d="M3 14c0-2.76 2.24-5 5-5s5 2.24 5 5"/></svg>
        <span>我的员工</span>
      </a>
      <a href="/workbench/materials" class="wb-scene-nav-item" :class="{ 'wb-scene-nav-item--active': isMaterialsPage }" @click.prevent="navigateTo({ name: 'workbench-materials' })">
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"><path d="M2 2h4v4H2zM6 2h4v4H6zM10 2h4v4h-4zM2 6h4v4H2zM6 6h4v4H6z"/></svg>
        <span>我的素材</span>
      </a>
      <span class="wb-scene-nav-brand" aria-hidden="true">XC</span>
    </nav>
    <main class="workbench-main">
      <router-view v-slot="{ Component, route: childRoute }">
        <keep-alive :max="12">
          <component
            v-if="Component"
            :is="Component"
            :key="
              childRoute.name === 'mod-authoring'
                ? `mod-${String(childRoute.params?.modId || '')}`
                : String(childRoute.name || childRoute.fullPath)
            "
          />
        </keep-alive>
      </router-view>
    </main>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'

const router = useRouter()
const route = useRoute()

const isWorkbenchHome = computed(() => String(route.name || '') === 'workbench-home')
const isUnifiedRepo = computed(() => {
  if (String(route.name || '') !== 'workbench-unified') return false
  const f = String(route.query.focus || '').trim().toLowerCase()
  return f === 'repository' || f === ''
})
const scriptWorkflowsNavActive = computed(() => String(route.path || '').includes('/script-workflows'))
const myEmployeesNavActive = computed(() => String(route.name || '') === 'workbench-employees')
const isMaterialsPage = computed(() => String(route.name || '') === 'workbench-materials')

function navigateTo(routeLocation: Parameters<typeof router.push>[0]) {
  requestAnimationFrame(() => {
    router.push(routeLocation)
  })
}
</script>

<style scoped>
.workbench {
  display: flex;
  flex-direction: column;
  min-height: 0;
  width: 100%;
  min-width: 0;
  background: #0a0a0a;
}

.wb-scene-nav {
  display: flex;
  flex-direction: row;
  gap: 2px;
  padding: 0.5rem;
}

.wb-scene-nav-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  border-radius: 8px;
  color: rgba(240, 240, 245, 0.4);
  text-decoration: none;
  font-size: 12px;
  font-weight: 500;
  transition: all 180ms cubic-bezier(0.4, 0, 0.2, 1);
  white-space: nowrap;
}

.wb-scene-nav-item:hover {
  background: rgba(129, 140, 248, 0.08);
  color: rgba(240, 240, 245, 0.7);
}

.wb-scene-nav-item--active {
  background: rgba(129, 140, 248, 0.12);
  color: rgba(240, 240, 245, 0.95);
}

.wb-scene-nav-brand {
  margin-left: auto;
  font-size: 14px;
  font-weight: 800;
  letter-spacing: -0.5px;
  background: linear-gradient(135deg, #1e3a5f 0%, #6366f1 50%, #0a0a0a 100%);
  color: transparent;
  background-clip: text;
  -webkit-background-clip: text;
  user-select: none;
  pointer-events: none;
}

.workbench-main {
  flex: 1 1 auto;
  min-width: 0;
  min-height: 0;
}
</style>
