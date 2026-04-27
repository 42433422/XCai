<template>
  <div class="step-nav">
    <button
      v-for="s in steps"
      :key="s.id"
      type="button"
      class="step-chip"
      :class="{ active: s.id === currentStep }"
      @click="$emit('go', s.id)"
    >
      {{ s.label }}
    </button>
  </div>
</template>

<script setup>
defineProps({
  steps: { type: Array, required: true },
  currentStep: { type: Number, required: true },
})
defineEmits(['go'])
</script>

<style scoped>
.step-nav { display:flex; flex-wrap:wrap; gap:.45rem; margin-bottom:1rem; }
.step-chip { padding:.35rem .6rem; border:1px solid rgba(255,255,255,.15); border-radius:6px; background:transparent; color:rgba(255,255,255,.65); cursor:pointer; font-size:12px; }
.step-chip.active { background:rgba(56,189,248,.22); border-color:rgba(56,189,248,.5); color:#fff; }
</style>
