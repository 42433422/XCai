<template>
  <button
    ref="ballRef"
    type="button"
    class="butler-ball"
    :class="{
      'butler-ball--consent-pending': !consentGiven,
      'butler-ball--open': isOpen,
    }"
    :style="{ transform: `translate(${pos.x}px, ${pos.y}px)` }"
    :aria-label="consentGiven ? (isOpen ? '关闭 AI 管家' : '打开 AI 管家') : '启用 AI 数字管家'"
    @click.stop="handleClick"
    @pointerdown="onPointerDown"
  >
    <JarvisCore
      :is-speaking="isSpeaking"
      :is-work-mode="mode === 'operating'"
      :is-monitor-mode="mode === 'thinking' || mode === 'listening'"
      :reduce-effects="mode === 'idle'"
    />
    <!-- 未读红点 -->
    <span v-if="unreadCount > 0 && !isOpen" class="butler-ball__badge">
      {{ unreadCount > 9 ? '9+' : unreadCount }}
    </span>
    <!-- 未同意时显示半透明提示 -->
    <span v-if="!consentGiven" class="butler-ball__hint">点我</span>
  </button>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { storeToRefs } from 'pinia'
import { useAgentStore } from '../../stores/agent'
import JarvisCore from '../workbench/JarvisCore.vue'

const agentStore = useAgentStore()
const { isOpen, mode, consentGiven, unreadCount } = storeToRefs(agentStore)

const props = defineProps<{ isSpeaking?: boolean }>()

const ballRef = ref<HTMLButtonElement | null>(null)

// 拖拽逻辑
let isDragging = false
let dragStartX = 0
let dragStartY = 0
let pointerMoved = false

const pos = computed(() => agentStore.position)

function onPointerDown(e: PointerEvent) {
  if (e.button !== 0) return
  isDragging = true
  pointerMoved = false
  dragStartX = e.clientX - agentStore.position.x
  dragStartY = e.clientY - agentStore.position.y
  ballRef.value?.setPointerCapture(e.pointerId)
  window.addEventListener('pointermove', onPointerMove)
  window.addEventListener('pointerup', onPointerUp)
}

function onPointerMove(e: PointerEvent) {
  if (!isDragging) return
  pointerMoved = true
  const nx = e.clientX - dragStartX
  const ny = e.clientY - dragStartY
  // 边界约束
  const maxX = window.innerWidth - 70
  const maxY = window.innerHeight - 70
  agentStore.savePosition(Math.max(4, Math.min(maxX, nx)), Math.max(4, Math.min(maxY, ny)))
}

function onPointerUp() {
  isDragging = false
  window.removeEventListener('pointermove', onPointerMove)
  window.removeEventListener('pointerup', onPointerUp)
}

function handleClick() {
  if (pointerMoved) return
  if (!agentStore.consentGiven) {
    agentStore.showPermissionDialog = true
    return
  }
  if (agentStore.isOpen) {
    agentStore.closePanel()
  } else {
    agentStore.openPanel()
  }
}

onBeforeUnmount(() => {
  window.removeEventListener('pointermove', onPointerMove)
  window.removeEventListener('pointerup', onPointerUp)
})
</script>

<style scoped>
.butler-ball {
  position: fixed;
  /* position is controlled by transform */
  top: 0;
  left: 0;
  width: 64px;
  height: 64px;
  border-radius: 50%;
  border: none;
  background: transparent;
  cursor: pointer;
  z-index: 11000;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: visible;
  transition: filter 0.2s;
  /* ensure JarvisCore fits */
  padding: 0;
}

/* Scale down JarvisCore (160×160) to fit 64px ball */
.butler-ball :deep(.jarvis-core) {
  width: 64px;
  height: 64px;
  transform: scale(0.4) !important;
  transform-origin: center center;
}

.butler-ball:hover {
  filter: brightness(1.1);
}

.butler-ball--consent-pending {
  opacity: 0.65;
}

.butler-ball--open {
  filter: drop-shadow(0 0 12px rgba(0, 220, 255, 0.6));
}

.butler-ball__badge {
  position: absolute;
  top: 0px;
  right: 0px;
  min-width: 18px;
  height: 18px;
  padding: 0 4px;
  border-radius: 999px;
  background: #f87171;
  color: #fff;
  font-size: 0.65rem;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 0 0 2px #0a0a0a;
  pointer-events: none;
  z-index: 1;
}

.butler-ball__hint {
  position: absolute;
  bottom: -22px;
  left: 50%;
  transform: translateX(-50%);
  font-size: 0.65rem;
  color: rgba(255, 255, 255, 0.5);
  white-space: nowrap;
  pointer-events: none;
  background: rgba(0, 0, 0, 0.6);
  padding: 2px 6px;
  border-radius: 4px;
}
</style>
