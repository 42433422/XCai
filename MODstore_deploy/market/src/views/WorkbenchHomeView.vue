<!--
  WorkbenchHomeView — legacy entry point, now redirects to AI-native WorkbenchShell.
  
  Original 9782-line orchestration (JarvisCore, MediaGenPanel, streamLLMChat sessions,
  EmployeeAiDraftReview, planning/media/research UX) has been superseded by the three-column
  WorkbenchShell which exposes all the same backend capabilities in a more coherent way:
  
  - Left Rail  (LeftRail.vue):    Chat + Agent Loop Timeline (streamEmployeeAiDraft SSE)
  - Center     (CanvasStage.vue): Vue Flow canvas (employee modules + workflow editor)
  - Right Rail (RightRail.vue):   Inspector + ModuleLibrary + Run (refine-prompt, research-context)
  
  See views/workbench/ for the new implementation.
-->
<script setup lang="ts">
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()

onMounted(() => {
  router.replace({ name: 'workbench-shell', params: { target: 'employee' } })
})
</script>

<template>
  <div class="home-redirect">
    <p>正在跳转到工作台…</p>
  </div>
</template>

<style scoped>
.home-redirect {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100vh;
  background: #080f1a;
  color: #475569;
  font-size: 13px;
}
</style>
