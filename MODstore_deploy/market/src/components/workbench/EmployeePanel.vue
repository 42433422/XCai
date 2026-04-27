<template>
  <section class="workbench-panel">
    <EmployeeAuthoringView />
  </section>
</template>

<script setup lang="ts">
import EmployeeAuthoringView from '../../views/EmployeeAuthoringView.vue'
</script>

<style scoped>
.workbench-panel {
  min-height: 0;
}
</style>
