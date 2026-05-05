<template>
  <div class="butler-float-root">
    <!-- 隐私同意弹窗 -->
    <AgentPermissionDialog
      v-if="showPermissionDialog"
      @agree="agentStore.grantConsent()"
      @dismiss="agentStore.dismissLater()"
    />

    <!-- 主动建议气泡 -->
    <AgentSuggestionToast
      :suggestion="currentSuggestion"
      @dismiss="dismiss"
      @open-panel="agentStore.openPanel()"
    />

    <!-- 悬浮球 -->
    <FloatingAgentBall :is-speaking="isSpeaking" />

    <!-- 对话面板 -->
    <Transition name="panel-pop">
      <FloatingAgentPanel v-if="isOpen" />
    </Transition>

    <!-- vibe-coding 改写进度全屏遮罩 -->
    <ButlerProgressOverlay
      v-if="orchestrationSession"
      @done="onOrchestratesDone"
      @rollback="onOrchestrationRollback"
      @close="agentStore.clearOrchestration()"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { storeToRefs } from 'pinia'
import { useRouter } from 'vue-router'
import { useAgentStore } from '../../stores/agent'
import { useAgentSuggestions } from '../../composables/agent/useAgentSuggestions'
import { useESkillRuntime } from '../../composables/agent/useESkillRuntime'
import { useButlerOrchestrator } from '../../composables/agent/useButlerOrchestrator'
import { registerBuiltinSkills } from '../../composables/agent/skills/index'
import AgentPermissionDialog from './AgentPermissionDialog.vue'
import AgentSuggestionToast from './AgentSuggestionToast.vue'
import FloatingAgentBall from './FloatingAgentBall.vue'
import FloatingAgentPanel from './FloatingAgentPanel.vue'
import ButlerProgressOverlay from './ButlerProgressOverlay.vue'

const agentStore = useAgentStore()
const { isOpen, showPermissionDialog, orchestrationSession } = storeToRefs(agentStore)
const isSpeaking = ref(false)

const router = useRouter()
const orchestrator = useButlerOrchestrator()

// 注册内置技能
onMounted(() => {
  registerBuiltinSkills(router)
})

// E-Skill 运行时（Phase 4）
useESkillRuntime()

// 主动建议
const { currentSuggestion, dismiss } = useAgentSuggestions()

function onOrchestratesDone() {
  agentStore.clearOrchestration()
  orchestrator.refreshAfterDone()
}

function onOrchestrationRollback() {
  agentStore.clearOrchestration()
}
</script>

<style>
/* panel 弹出动画 */
.panel-pop-enter-active {
  transition: all 0.22s cubic-bezier(0.34, 1.56, 0.64, 1);
}

.panel-pop-leave-active {
  transition: all 0.18s ease;
}

.panel-pop-enter-from,
.panel-pop-leave-to {
  opacity: 0;
  transform: scale(0.92) translateY(8px);
}
</style>
