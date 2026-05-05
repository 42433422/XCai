<!--
  EmployeeAuthoringView — thin wrapper.
  Redirects to the AI-native WorkbenchShell with target=employee.
  All authoring logic now lives in WorkbenchShell + LeftRail + CanvasStage + RightRail.
-->
<script setup lang="ts">
import { onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'

const router = useRouter()
const route = useRoute()

onMounted(() => {
  const id = route.params.id ?? route.query.id ?? null
  router.replace({
    name: 'workbench-shell',
    params: { target: 'employee', ...(id ? { id: String(id) } : {}) },
  })
})
</script>

<template>
  <div class="authoring-redirect">
    <p>正在跳转到工作台…</p>
  </div>
</template>

<style scoped>
.authoring-redirect {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: #64748b;
  font-size: 13px;
}
</style>
