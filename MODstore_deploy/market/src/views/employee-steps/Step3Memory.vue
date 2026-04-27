<template>
  <section>
    <h3 class="ttl">Step3 记忆层（可选）</h3>
    <label><input type="checkbox" :checked="enabled" @change="$emit('toggle', $event.target.checked)" /> 启用记忆层</label>
  </section>
</template>
<script setup>
defineProps({ enabled: { type: Boolean, required: true } })
defineEmits(['toggle'])
</script>
<style scoped>.ttl{margin:.2rem 0 .5rem;color:#fff}</style>
