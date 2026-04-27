<template>
  <section>
    <h3 class="ttl">Step1 身份层</h3>
    <div class="g">
      <input class="input" :value="config.identity.id" placeholder="identity.id" @input="$emit('patch', { identity: { ...config.identity, id: $event.target.value } })" />
      <input class="input" :value="config.identity.version" placeholder="identity.version" @input="$emit('patch', { identity: { ...config.identity, version: $event.target.value } })" />
      <input class="input" :value="form.name" placeholder="员工名称" @input="$emit('form', { name: $event.target.value })" />
      <textarea class="input" :value="form.description" placeholder="员工描述" @input="$emit('form', { description: $event.target.value })" />
    </div>
  </section>
</template>
<script setup>
defineProps({ config: { type: Object, required: true }, form: { type: Object, required: true } })
defineEmits(['patch', 'form'])
</script>
<style scoped>.ttl{margin:.2rem 0 .5rem;color:#fff}.g{display:grid;gap:.5rem}</style>
