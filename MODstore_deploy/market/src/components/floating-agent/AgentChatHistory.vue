<template>
  <div ref="scrollEl" class="chat-history" role="log" aria-label="对话历史" aria-live="polite">
    <div v-if="!messages.length" class="chat-empty">
      <p class="chat-empty-title">需要我做什么？</p>
      <p class="chat-empty-desc">我可以理解当前页面，并帮你跳转、搜索或执行常用操作。</p>
      <p class="chat-empty-sub">
        <button class="quick-tip" @click="$emit('quick', '这个页面有什么功能？')">这页有什么？</button>
        <button class="quick-tip" @click="$emit('quick', '去会员页面')">去会员页</button>
        <button class="quick-tip" @click="$emit('quick', '帮我搜索 AI 员工')">搜索员工</button>
      </p>
    </div>
    <AgentMessageBubble
      v-for="msg in messages"
      :key="msg.id"
      :msg="msg"
    />
    <!-- 操作确认区 -->
    <AgentActionPreview
      v-if="pendingAction"
      :action="pendingAction"
      @confirm="pendingAction?.resolve(true)"
      @cancel="pendingAction?.resolve(false)"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, watch, nextTick } from 'vue'
import { storeToRefs } from 'pinia'
import { useAgentStore } from '../../stores/agent'
import AgentMessageBubble from './AgentMessageBubble.vue'
import AgentActionPreview from './AgentActionPreview.vue'

defineEmits<{ (e: 'quick', text: string): void }>()

const agentStore = useAgentStore()
const { messages, pendingAction } = storeToRefs(agentStore)

const scrollEl = ref<HTMLDivElement | null>(null)

watch(
  messages,
  () => {
    nextTick(() => {
      if (scrollEl.value) {
        scrollEl.value.scrollTop = scrollEl.value.scrollHeight
      }
    })
  },
  { deep: true },
)
</script>

<style scoped>
.chat-history {
  flex: 1 1 0%;
  overflow-y: auto;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 0;
  min-height: 0;
  scroll-behavior: smooth;
}

.chat-empty {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  justify-content: center;
  gap: 6px;
  color: rgba(255, 255, 255, 0.55);
  font-size: 0.88rem;
  text-align: left;
  padding: 18px;
  border: 1px dashed rgba(255, 255, 255, 0.08);
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.025);
}

.chat-empty-title {
  margin: 0;
  color: rgba(255, 255, 255, 0.82);
  font-weight: 750;
}

.chat-empty-desc {
  margin: 0 0 6px;
  color: rgba(255, 255, 255, 0.42);
  font-size: 0.78rem;
  line-height: 1.5;
}

.chat-empty-sub {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  justify-content: flex-start;
  margin: 0;
}

.quick-tip {
  padding: 4px 9px;
  border-radius: 7px;
  font-size: 0.78rem;
  background: rgba(255, 255, 255, 0.045);
  border: 1px solid rgba(255, 255, 255, 0.09);
  color: rgba(226, 232, 240, 0.82);
  cursor: pointer;
  transition: all 0.15s;
}

.quick-tip:hover {
  background: rgba(255, 255, 255, 0.08);
  color: #fff;
}
</style>
