<template>
  <section>
    <h3 class="ttl">Step4 认知层</h3>
    <textarea
      class="input"
      :value="config?.cognition?.agent?.system_prompt || ''"
      placeholder="system_prompt"
      @input="$emit('prompt', $event.target.value)"
    />
  </section>
</template>
<script setup>
defineProps({ config: { type: Object, required: true } })
defineEmits(['prompt'])
</script>
<style scoped>.ttl{margin:.2rem 0 .5rem;color:#fff}</style>
