<template>
  <div ref="hostRef" class="react-mount"></div>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { createRoot, type Root } from 'react-dom/client'
import { createElement, type ComponentType } from 'react'

const props = defineProps<{
  component: ComponentType<any>
  componentProps?: Record<string, unknown>
}>()

const hostRef = ref<HTMLElement | null>(null)
let root: Root | null = null

function renderReact() {
  if (!hostRef.value) return
  if (!root) root = createRoot(hostRef.value)
  root.render(createElement(props.component, props.componentProps || {}))
}

onMounted(renderReact)

watch(
  () => [props.component, props.componentProps] as const,
  () => renderReact(),
  { deep: true },
)

onBeforeUnmount(() => {
  root?.unmount()
  root = null
})
</script>

<style scoped>
.react-mount {
  width: 100%;
  min-height: 0;
  display: contents;
}
</style>
