<template>
  <div
    class="ctc"
    role="radiogroup"
    aria-labelledby="ctc-lbl"
    aria-describedby="ctc-hint"
  >
    <span id="ctc-hint" class="ctc__sr">{{ hint }}</span>
    <span id="ctc-lbl" class="ctc__label">消费档位（1–10）</span>
    <div class="ctc__row" role="presentation">
      <button
        v-for="n in 10"
        :key="n"
        type="button"
        role="radio"
        class="ctc__btn"
        :class="{ 'ctc__btn--on': modelValue === n }"
        :aria-checked="modelValue === n"
        :title="`${n} 档：${hint}`"
        @click="emit('update:modelValue', n)"
      >
        {{ n }}
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  modelValue: number
}>()

const emit = defineEmits<{
  'update:modelValue': [value: number]
}>()

const hint = '数值越高效果越好、花费越多；占位控件，后续可依据实时榜单自选'
</script>

<style scoped>
.ctc {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 0.35rem;
  text-align: right;
}

.ctc__label {
  font-size: 0.65rem;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: rgba(148, 163, 184, 0.72);
  user-select: none;
}

.ctc__row {
  display: flex;
  flex-wrap: nowrap;
  gap: 0.22rem;
  justify-content: flex-end;
  max-width: 100%;
  overflow-x: auto;
  overflow-y: hidden;
  padding-bottom: 0.15rem;
  scrollbar-width: thin;
  scrollbar-color: rgba(148, 163, 184, 0.28) transparent;
}

.ctc__btn {
  flex: 0 0 auto;
  min-width: 1.55rem;
  height: 1.55rem;
  padding: 0 0.2rem;
  border-radius: 999px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(255, 255, 255, 0.055);
  color: rgba(226, 232, 240, 0.72);
  font-size: 0.68rem;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  line-height: 1;
  cursor: pointer;
  transition:
    color 0.16s ease,
    background 0.16s ease,
    border-color 0.16s ease,
    box-shadow 0.16s ease;
}

.ctc__btn:hover {
  color: rgba(248, 250, 252, 0.95);
  background: rgba(255, 255, 255, 0.1);
  border-color: rgba(255, 255, 255, 0.14);
}

.ctc__btn--on {
  color: #f8fafc;
  border-color: rgba(165, 180, 252, 0.55);
  background:
    radial-gradient(circle at 35% 22%, rgba(255, 255, 255, 0.14), transparent 42%),
    rgba(55, 62, 101, 0.55);
  box-shadow:
    0 0 0 1px rgba(129, 140, 248, 0.12),
    0 6px 14px rgba(0, 0, 0, 0.22);
}

.ctc__btn:focus-visible {
  outline: 2px solid rgba(129, 140, 248, 0.65);
  outline-offset: 2px;
}

.ctc__sr {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}
</style>
