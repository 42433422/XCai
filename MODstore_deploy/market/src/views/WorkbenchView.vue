<template>
  <div class="workbench">
    <header v-if="!isEmployeeRoute" class="workbench-bar">
      <div class="workbench-bar-inner">
        <router-link :to="{ name: 'workbench-home' }" class="workbench-title-link">
          <h1 class="workbench-title">工作台</h1>
        </router-link>
        <details class="workbench-help">
          <summary class="workbench-help-summary">Mod 库、员工制作、工作流，分别是干什么的？</summary>
          <div class="workbench-help-body">
            <p>
              <strong>Mod 库</strong>：给系统加功能的「扩展包」，可以带界面、带后台逻辑。你在里面写的「工作流里要用的 AI 员工」，
              相当于先写好<strong>说明书/占位</strong>，方便以后在流程里挂上名字；<strong>还不等于</strong>已经有一个能上传、能上架的完整员工包。
            </p>
            <p>
              <strong>员工制作</strong>：把<strong>zip / .xcemp</strong>登记到本地包目录（<code class="mono">/v1/packages</code>），并可在从 Mod 库同步后<strong>查看、编辑</strong>
              对应条目的 <code class="mono">workflow_employees</code> JSON、写回 manifest，或<strong>一键导出该 Mod 为 zip</strong>填入上传区。现在员工制作基于 V2 架构向导：
              <strong>工作流是员工心脏且必选</strong>，其它能力层（感知/记忆/行动/管理）可按需开启。
              公开「商店」列表仍来自后台数据库；管理员上架与本地包目录是两条可见数据源，本页「我的员工」会合并展示。
            </p>
            <p>
              <strong>工作流管理</strong>：像画一张<strong>流程图</strong>，把多个步骤（不同员工、条件判断等）连成一条自动流水线。
              它是员工运行时的<strong>心脏总调度</strong>，不是塞在某个员工包里面的子文件夹。
            </p>
            <p class="workbench-help-foot muted">
              需要字段、格式等技术细节时，可看项目里的 <strong>MOD_AUTHORING_GUIDE.md</strong>。
            </p>
          </div>
        </details>
        <nav class="workbench-tabs" aria-label="工作台导航：首页、统一工作台">
          <router-link
            :to="{ name: 'workbench-home' }"
            class="workbench-tab"
            active-class="workbench-tab--active"
          >
            首页
          </router-link>
          <router-link
            :to="{ name: 'workbench-unified' }"
            class="workbench-tab"
            active-class="workbench-tab--active"
          >
            统一工作台
          </router-link>
        </nav>
      </div>
    </header>
    <main class="workbench-main">
      <router-view v-slot="{ Component, route }">
        <transition name="page-fade" mode="out-in">
          <component :is="Component" :key="route.fullPath" />
        </transition>
      </router-view>
    </main>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const isEmployeeRoute = computed(() => String(route.name || '') === 'workbench-employee')
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
  padding: 1rem var(--layout-pad-x, 16px) 0.75rem;
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  gap: 1rem 1.5rem;
  min-width: 0;
}

.workbench-help {
  flex: 1 1 280px;
  min-width: 0;
  max-width: min(560px, 100%);
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
