<template>
  <div ref="scrollEl" class="chat-history" role="log" aria-label="对话历史" aria-live="polite">
    <div v-if="!messages.length" class="chat-empty">
      <div class="chat-empty-icon">🤖</div>
      <p>你好，我是你的 AI 数字管家</p>
      <p class="chat-empty-sub">可以问我：
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
  padding: 12px 14px;
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
  align-items: center;
  justify-content: center;
  gap: 8px;
  color: rgba(255, 255, 255, 0.45);
  font-size: 0.88rem;
  text-align: center;
  padding: 20px;
}

.chat-empty-icon {
  font-size: 2.2rem;
  margin-bottom: 4px;
}

.chat-empty-sub {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  justify-content: center;
  margin-top: 4px;
}

.quick-tip {
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 0.78rem;
  background: rgba(0, 180, 255, 0.1);
  border: 1px solid rgba(0, 180, 255, 0.25);
  color: #7dd3fc;
  cursor: pointer;
  transition: all 0.15s;
}

.quick-tip:hover {
  background: rgba(0, 180, 255, 0.18);
  color: #bae6fd;
}
</style>
