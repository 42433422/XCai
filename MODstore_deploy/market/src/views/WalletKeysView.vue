<template>
  <div class="wallet-keys">
    <h1 class="page-title">API 密钥</h1>
    <p class="wallet-keys__lead">
      在此创建、吊销 Personal Access Token，或将多条密钥<strong>加密下发到桌面</strong>（免逐条复制）。调用接口时使用
      <code>Authorization: Bearer pat_…</code>。
    </p>
    <div class="wallet-keys__embed">
      <DeveloperTokensPanel />
    </div>
    <p class="wallet-keys__more">
      <router-link :to="{ name: 'developer-portal' }" class="inline-link">Webhook 订阅与完整开发者门户 →</router-link>
    </p>
  </div>
</template>

<script setup lang="ts">
import DeveloperTokensPanel from './developer/DeveloperTokensPanel.vue'
</script>

<style scoped>
.wallet-keys__lead {
  margin: 0 0 18px;
  font-size: 14px;
  color: rgba(255, 255, 255, 0.65);
  line-height: 1.55;
  max-width: 52rem;
}

.wallet-keys__lead code {
  font-size: 12px;
  padding: 2px 6px;
  border-radius: 4px;
  background: rgba(15, 23, 42, 0.55);
  color: #e2e8f0;
}

.wallet-keys__embed {
  border-radius: 12px;
  overflow: hidden;
  border: 1px solid rgba(255, 255, 255, 0.1);
  background: #f8fafc;
}

.wallet-keys__more {
  margin: 16px 0 0;
  font-size: 13px;
}

.inline-link {
  color: #a5b4fc;
  text-decoration: none;
}

.inline-link:hover {
  text-decoration: underline;
}
</style>
