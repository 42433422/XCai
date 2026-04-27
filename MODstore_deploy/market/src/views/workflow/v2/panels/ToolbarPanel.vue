<script setup lang="ts">
defineProps<{
  workflowName: string
  saving: boolean
  isActive: boolean
}>()

defineEmits<{
  (e: 'back'): void
  (e: 'rename'): void
  (e: 'auto-layout'): void
  (e: 'sandbox'): void
  (e: 'execute'): void
  (e: 'toggle-active'): void
  (e: 'publish'): void
  (e: 'versions'): void
  (e: 'save-as-template'): void
}>()
</script>

<template>
  <header class="wf2-toolbar">
    <div class="wf2-toolbar__left">
      <button class="wf2-tb-btn wf2-tb-btn--ghost" type="button" @click="$emit('back')">
        ← 返回列表
      </button>
      <h2 class="wf2-toolbar__title" @click="$emit('rename')" :title="'点击修改'">
        {{ workflowName || '未命名工作流' }}
      </h2>
      <span
        class="wf2-toolbar__status"
        :class="{ 'wf2-toolbar__status--ok': isActive }"
      >
        {{ isActive ? '已激活' : '未激活' }}
      </span>
      <span v-if="saving" class="wf2-toolbar__saving">保存中…</span>
      <span v-else class="wf2-toolbar__saved">已保存</span>
    </div>
    <div class="wf2-toolbar__right">
      <button class="wf2-tb-btn" type="button" @click="$emit('toggle-active')">
        {{ isActive ? '停用' : '激活' }}
      </button>
      <button class="wf2-tb-btn" type="button" @click="$emit('auto-layout')">自动布局</button>
      <button class="wf2-tb-btn" type="button" @click="$emit('versions')">版本历史</button>
      <button class="wf2-tb-btn" type="button" @click="$emit('publish')">发布版本</button>
      <button class="wf2-tb-btn" type="button" @click="$emit('save-as-template')">另存为模板</button>
      <button class="wf2-tb-btn" type="button" @click="$emit('sandbox')">沙盒测试</button>
      <button class="wf2-tb-btn wf2-tb-btn--primary" type="button" @click="$emit('execute')">
        立即执行
      </button>
    </div>
  </header>
</template>

<style scoped>
.wf2-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 10px 16px;
  border-bottom: 1px solid #e2e8f0;
  background: #ffffff;
}

.wf2-toolbar__left,
.wf2-toolbar__right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.wf2-toolbar__title {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: #0f172a;
  cursor: pointer;
}

.wf2-toolbar__title:hover {
  color: #4f46e5;
}

.wf2-toolbar__status {
  font-size: 11px;
  color: #94a3b8;
  background: #f1f5f9;
  padding: 2px 8px;
  border-radius: 999px;
}

.wf2-toolbar__status--ok {
  background: #dcfce7;
  color: #166534;
}

.wf2-toolbar__saving {
  font-size: 12px;
  color: #f59e0b;
}

.wf2-toolbar__saved {
  font-size: 12px;
  color: #94a3b8;
}

.wf2-tb-btn {
  font-size: 13px;
  border: 1px solid #cbd5e1;
  background: #fff;
  color: #334155;
  padding: 6px 12px;
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.15s ease, color 0.15s ease, border-color 0.15s ease;
}

.wf2-tb-btn:hover {
  background: #f1f5f9;
}

.wf2-tb-btn--ghost {
  background: transparent;
  border-color: transparent;
  color: #64748b;
}

.wf2-tb-btn--primary {
  background: #4f46e5;
  border-color: #4f46e5;
  color: #fff;
}

.wf2-tb-btn--primary:hover {
  background: #4338ca;
  border-color: #4338ca;
}
</style>
