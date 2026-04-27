<template>
  <div class="msg-act" role="group" aria-label="消息操作">
    <button v-if="role === 'assistant'" type="button" class="msg-act__btn" :title="speakLabel" @click="$emit('speak')">
      <span aria-hidden="true">{{ speakIcon }}</span> {{ speakLabel }}
    </button>
    <button type="button" class="msg-act__btn" title="复制原文" @click="onCopy">
      <span aria-hidden="true">📋</span> {{ copied ? '已复制' : '复制' }}
    </button>
    <button v-if="role === 'user'" type="button" class="msg-act__btn" title="编辑后重发" @click="$emit('edit')">
      <span aria-hidden="true">✎</span> 编辑
    </button>
    <button v-if="role === 'assistant' && canRegenerate" type="button" class="msg-act__btn" title="重新生成" @click="$emit('regenerate')">
      <span aria-hidden="true">↻</span> 重答
    </button>
    <button
      v-if="role === 'assistant'"
      type="button"
      class="msg-act__btn"
      :class="{ 'msg-act__btn--up': feedback === 'up' }"
      title="赞"
      @click="$emit('feedback', feedback === 'up' ? null : 'up')"
    >👍</button>
    <button
      v-if="role === 'assistant'"
      type="button"
      class="msg-act__btn"
      :class="{ 'msg-act__btn--down': feedback === 'down' }"
      title="踩"
      @click="$emit('feedback', feedback === 'down' ? null : 'down')"
    >👎</button>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'

const props = defineProps<{
  role: 'user' | 'assistant' | 'system'
  content: string
  feedback?: 'up' | 'down' | null
  canRegenerate?: boolean
  speaking?: boolean
}>()

defineEmits<{
  (e: 'edit'): void
  (e: 'regenerate'): void
  (e: 'speak'): void
  (e: 'feedback', v: 'up' | 'down' | null): void
}>()

const copied = ref(false)
const speakIcon = computed(() => (props.speaking ? '⏹' : '🔊'))
const speakLabel = computed(() => (props.speaking ? '停止' : '朗读'))

async function onCopy() {
  try {
    await navigator.clipboard.writeText(props.content || '')
    copied.value = true
    window.setTimeout(() => {
      copied.value = false
    }, 1500)
  } catch {
    copied.value = false
  }
}
</script>

<style scoped>
.msg-act {
  display: flex;
  flex-wrap: wrap;
  gap: 0.3rem;
  margin-top: 0.4rem;
}

.msg-act__btn {
  display: inline-flex;
  align-items: center;
  gap: 0.2rem;
  padding: 0.2rem 0.55rem;
  border-radius: 0.42rem;
  background: rgba(15, 23, 42, 0.45);
  border: 1px solid rgba(255, 255, 255, 0.06);
  color: rgba(203, 213, 225, 0.8);
  font-size: 0.72rem;
  cursor: pointer;
  transition: background 120ms ease, color 120ms ease, border-color 120ms ease;
}

.msg-act__btn:hover {
  background: rgba(99, 102, 241, 0.18);
  color: #fff;
  border-color: rgba(165, 180, 252, 0.32);
}

.msg-act__btn--up {
  background: rgba(45, 212, 191, 0.22);
  color: #5eead4;
  border-color: rgba(45, 212, 191, 0.35);
}

.msg-act__btn--down {
  background: rgba(248, 113, 113, 0.22);
  color: #fca5a5;
  border-color: rgba(248, 113, 113, 0.32);
}
</style>
