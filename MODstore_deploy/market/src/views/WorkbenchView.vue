<template>
  <div class="workbench">
    <header v-if="!isEmployeeRoute" class="workbench-bar">
      <div class="workbench-bar-inner">
        <router-link :to="{ name: 'workbench-home' }" class="workbench-title-link">
          <h1 class="workbench-title">工作台</h1>
        </router-link>
        <details class="workbench-help">
          <summary class="workbench-help-summary">各入口一句话说明（展开）</summary>
          <div class="workbench-help-body">
            <p><strong>Mod 库</strong>：维护扩展包与 manifest；其中的「工作流员工」多为占位声明，不等于已上架的完整员工包。</p>
            <p><strong>员工制作</strong>：用向导做可安装员工包，并走打包、测试、上架；工作流是必选核心。</p>
            <p><strong>工作流</strong>：<strong>脚本工作流</strong>是可运行的 Python 任务；统一工作台里可切到<strong>专注工作流</strong>做画布编排。要「能跑的任务」优先用脚本工作流。</p>
            <p class="workbench-help-foot muted">字段与格式详见仓库内 <strong>MOD_AUTHORING_GUIDE.md</strong>。</p>
          </div>
        </details>
        <nav class="workbench-tabs" aria-label="工作台主导航">
          <router-link
            :to="{ name: 'workbench-home' }"
            class="workbench-tab"
            active-class="workbench-tab--active"
          >
            首页
          </router-link>
          <router-link
            :to="{ name: 'workbench-unified', query: { focus: 'employee' } }"
            class="workbench-tab"
            active-class="workbench-tab--active"
          >
            统一工作台
          </router-link>
          <router-link
            :to="{ name: 'script-workflows' }"
            class="workbench-tab"
            :class="{ 'workbench-tab--active': scriptWorkflowsNavActive }"
          >
            脚本工作流
          </router-link>
          <router-link
            :to="{ name: 'workbench-unified', query: { focus: 'employee', employeeView: 'list' } }"
            class="workbench-tab"
            :class="{ 'workbench-tab--active': myEmployeesNavActive }"
          >
            我的员工
          </router-link>
        </nav>
      </div>
    </header>
    <main class="workbench-main">
      <router-view v-slot="{ Component, route: childRoute }">
        <!-- 首页 / 统一工作台 / Mod 制作等切换时保留各自状态，避免 fullPath 当 key 导致整页重挂 -->
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
import { useRoute } from 'vue-router'

const route = useRoute()
const isEmployeeRoute = computed(() => String(route.name || '') === 'workbench-employee')
const scriptWorkflowsNavActive = computed(() => String(route.path || '').startsWith('/script-workflows'))
const myEmployeesNavActive = computed(() => {
  if (String(route.name || '') !== 'workbench-unified') return false
  const f = String(route.query.focus || '').trim().toLowerCase()
  const v = String(route.query.employeeView || '').trim().toLowerCase()
  return f === 'employee' && v === 'list'
})
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

.workbench-bar {
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(0, 0, 0, 0.45);
}

.workbench-bar-inner {
  width: 100%;
  max-width: var(--layout-max, min(1600px, calc(100vw - 48px)));
  margin: 0 auto;
  padding: 0.75rem var(--layout-pad-x, 16px) 0.65rem;
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  gap: 0.65rem 1rem;
  min-width: 0;
}

.workbench-help {
  flex: 1 1 220px;
  min-width: 0;
  max-width: min(420px, 100%);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 8px;
  padding: 0.35rem 0.65rem;
  background: rgba(255, 255, 255, 0.03);
  color: rgba(255, 255, 255, 0.72);
  font-size: 0.85rem;
  line-height: 1.45;
}

.workbench-help-summary {
  cursor: pointer;
  font-weight: 500;
  color: rgba(255, 255, 255, 0.88);
  list-style: none;
}

.workbench-help summary::-webkit-details-marker {
  display: none;
}

.workbench-help-body {
  margin-top: 0.5rem;
  padding-top: 0.5rem;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
}

.workbench-help-body p {
  margin: 0 0 0.5rem;
}

.workbench-help-body p:last-child {
  margin-bottom: 0;
}

.workbench-help .mono {
  font-family: ui-monospace, monospace;
  font-size: 0.82em;
  color: rgba(200, 220, 255, 0.95);
}

.workbench-help-foot {
  font-size: 0.8rem;
  margin-top: 0.35rem !important;
}

.workbench-title-link {
  text-decoration: none;
  color: inherit;
}

.workbench-title-link:hover .workbench-title {
  color: rgba(255, 255, 255, 0.88);
}

.workbench-title {
  margin: 0;
  font-size: clamp(1.1rem, 1rem + 0.35vw, 1.3rem);
  font-weight: 600;
  color: #ffffff;
}

.workbench-tabs {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.25rem;
}

.workbench-tab {
  padding: 0.45rem 0.95rem;
  border-radius: 6px;
  font-size: clamp(0.9rem, 0.85rem + 0.2vw, 1rem);
  color: rgba(255, 255, 255, 0.45);
  text-decoration: none;
}

.workbench-tab:hover {
  color: rgba(255, 255, 255, 0.85);
  background: rgba(255, 255, 255, 0.06);
}

.workbench-tab--active {
  color: #ffffff;
  background: rgba(255, 255, 255, 0.1);
}

.workbench-main {
  flex: 1 1 auto;
  min-width: 0;
  min-height: 0;
}
</style>
