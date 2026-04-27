<template>
  <section>
    <h3 class="ttl">Step6 协作层（心脏必选）</h3>
    <input
      class="input"
      type="number"
      min="1"
      :value="workflowId"
      placeholder="workflow_id"
      @input="$emit('change', Number($event.target.value || 0))"
    />
    <p :class="['tip', workflowId > 0 ? 'ok' : 'err']">
      {{ workflowId > 0 ? '心脏已配置' : '请填写有效 workflow_id' }}
    </p>
  </section>
</template>
<script setup>
defineProps({ workflowId: { type: Number, required: true } })
defineEmits(['change'])
</script>
<style scoped>.ttl{margin:.2rem 0 .5rem;color:#fff}.tip{margin:.5rem 0 0;font-size:12px}.ok{color:#4ade80}.err{color:#f87171}</style>
