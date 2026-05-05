<template>
  <div class="voice-bar">
    <button
      v-if="isSupported"
      type="button"
      class="voice-btn"
      :class="{ 'voice-btn--active': isListening }"
      :aria-label="isListening ? '停止录音' : '按住说话'"
      :title="isSupported ? (isListening ? '点击停止录音' : '点击开始语音输入') : '浏览器不支持语音识别'"
      @click="toggle"
    >
      <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <rect x="9" y="2" width="6" height="12" rx="3" stroke="currentColor" stroke-width="1.8" />
        <path d="M5 11a7 7 0 0 0 14 0" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" />
        <line x1="12" y1="18" x2="12" y2="22" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" />
      </svg>
    </button>
    <span v-if="error" class="voice-err">{{ error }}</span>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { VoiceState } from '../../composables/agent/useVoiceInput'

const props = defineProps<{
  voiceState: VoiceState
  isSupported: boolean
  error: string
}>()

const emit = defineEmits<{
  (e: 'toggle'): void
}>()

const isListening = computed(() => props.voiceState === 'listening')

function toggle() {
  emit('toggle')
}
</script>

<style scoped>
.voice-bar {
  display: flex;
  align-items: center;
  gap: 6px;
}

.voice-btn {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px solid rgba(255, 255, 255, 0.15);
  background: rgba(255, 255, 255, 0.04);
  color: rgba(255, 255, 255, 0.55);
  cursor: pointer;
  transition: all 0.15s;
  flex-shrink: 0;
}

.voice-btn svg {
  width: 18px;
  height: 18px;
}

.voice-btn:hover {
  background: rgba(255, 255, 255, 0.09);
  color: rgba(255, 255, 255, 0.85);
}

.voice-btn--active {
  background: rgba(0, 220, 255, 0.15);
  border-color: rgba(0, 220, 255, 0.45);
  color: #00dcff;
  animation: voice-pulse 1.2s ease-in-out infinite;
}

.voice-err {
  font-size: 0.72rem;
  color: #f87171;
  flex: 1;
}

@keyframes voice-pulse {
  0%, 100% { box-shadow: 0 0 0 0 rgba(0, 220, 255, 0.3); }
  50% { box-shadow: 0 0 0 5px rgba(0, 220, 255, 0); }
}
</style>
