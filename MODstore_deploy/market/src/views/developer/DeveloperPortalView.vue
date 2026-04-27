<script setup lang="ts">
import { computed, ref } from 'vue'
import DeveloperTokensPanel from './DeveloperTokensPanel.vue'
import DeveloperWebhooksPanel from './DeveloperWebhooksPanel.vue'
import DeveloperDocsPanel from './DeveloperDocsPanel.vue'

type TabKey = 'tokens' | 'webhooks' | 'docs'

const activeTab = ref<TabKey>('tokens')

interface TabDef {
  key: TabKey
  label: string
  description: string
  ready: boolean
}

const tabs = computed<TabDef[]>(() => [
  {
    key: 'tokens',
    label: 'API Token',
    description: '管理可调用 MODstore REST API 的 Personal Access Token',
    ready: true,
  },
  {
    key: 'webhooks',
    label: 'Webhook 订阅',
    description: '接收事件回调（员工执行、工作流执行、支付变化）',
    ready: true,
  },
  {
    key: 'docs',
    label: 'API 文档',
    description: 'OpenAPI 在线文档、开发者手册与机器可读契约',
    ready: true,
  },
])

const activeMeta = computed(() => tabs.value.find((t) => t.key === activeTab.value)!)
</script>

<template>
  <main class="dev-portal">
    <header class="dev-portal__head">
      <div>
        <h1 class="dev-portal__title">开发者门户</h1>
        <p class="dev-portal__subtitle">
          {{ activeMeta.description }}
        </p>
      </div>
      <a class="dev-portal__doc-link" href="/docs" target="_blank" rel="noreferrer">
        Swagger UI ↗
      </a>
    </header>

    <nav class="dev-portal__tabs" aria-label="Developer sections">
      <button
        v-for="t in tabs"
        :key="t.key"
        type="button"
        class="dev-portal__tab"
        :class="{
          'dev-portal__tab--active': activeTab === t.key,
          'dev-portal__tab--coming': !t.ready,
        }"
        @click="activeTab = t.key"
      >
        <span>{{ t.label }}</span>
        <span v-if="!t.ready" class="dev-portal__chip">即将上线</span>
      </button>
    </nav>

    <section class="dev-portal__body">
      <DeveloperTokensPanel v-if="activeTab === 'tokens'" />

      <DeveloperWebhooksPanel v-else-if="activeTab === 'webhooks'" />

      <DeveloperDocsPanel v-else-if="activeTab === 'docs'" />
    </section>
  </main>
</template>

<style scoped>
.dev-portal {
  max-width: 980px;
  margin: 0 auto;
  padding: 32px 24px 48px;
  color: #0f172a;
}

.dev-portal__head {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  gap: 16px;
  margin-bottom: 18px;
}

.dev-portal__title {
  margin: 0;
  font-size: 26px;
  font-weight: 700;
}

.dev-portal__subtitle {
  margin: 4px 0 0;
  font-size: 13px;
  color: #64748b;
}

.dev-portal__doc-link {
  font-size: 13px;
  color: #4f46e5;
  text-decoration: none;
  border: 1px solid #c7d2fe;
  padding: 6px 12px;
  border-radius: 6px;
  background: #f5f3ff;
}

.dev-portal__doc-link:hover {
  background: #ede9fe;
}

.dev-portal__tabs {
  display: flex;
  gap: 4px;
  border-bottom: 1px solid #e2e8f0;
  margin-bottom: 24px;
}

.dev-portal__tab {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  background: transparent;
  border: 0;
  padding: 10px 16px;
  font-size: 14px;
  color: #64748b;
  cursor: pointer;
  border-bottom: 2px solid transparent;
  margin-bottom: -1px;
}

.dev-portal__tab:hover {
  color: #0f172a;
}

.dev-portal__tab--active {
  color: #4f46e5;
  border-bottom-color: #4f46e5;
  font-weight: 600;
}

.dev-portal__tab--coming {
  color: #94a3b8;
}

.dev-portal__chip {
  font-size: 10px;
  background: #fef3c7;
  color: #92400e;
  padding: 1px 6px;
  border-radius: 999px;
  letter-spacing: 0.04em;
}

.dev-portal__body {
  min-height: 60vh;
}

.dev-portal__placeholder {
  background: #f8fafc;
  border: 1px dashed #cbd5e1;
  padding: 32px;
  border-radius: 10px;
  color: #475569;
  text-align: center;
}

.dev-portal__placeholder h2 {
  margin: 0 0 6px;
  font-size: 18px;
  color: #0f172a;
}

.dev-portal__placeholder p {
  margin: 0;
  font-size: 13px;
  line-height: 1.5;
}
</style>
