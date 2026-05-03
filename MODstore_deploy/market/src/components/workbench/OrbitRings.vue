<template>
  <div
    class="orbit-rings"
    :class="[`orbit-rings--${modeClass}`]"
    aria-hidden="true"
  >
    <div class="orbit-rings__inner"></div>
    <div class="orbit-rings__outer"></div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  /** Matches workbench voiceState: idle | listening | thinking | summary */
  mode: {
    type: String,
    default: 'idle',
  },
})

const modeClass = computed(() => {
  const m = props.mode
  if (m === 'thinking' || m === 'summary') return m
  return 'cyan'
})
</script>

<style scoped>
.orbit-rings {
  position: absolute;
  inset: 0;
  z-index: 0;
  pointer-events: none;
  display: grid;
  place-items: center;
}

.orbit-rings__inner,
.orbit-rings__outer {
  position: absolute;
  top: 50%;
  left: 50%;
  border-radius: 50%;
  border: 1px solid var(--orbit-border, rgba(0, 255, 255, 0.35));
  box-shadow: 0 0 10px var(--orbit-glow, rgba(0, 255, 255, 0.22));
  transition:
    border-color 0.35s cubic-bezier(0.4, 0, 0.2, 1),
    box-shadow 0.35s cubic-bezier(0.4, 0, 0.2, 1);
}

.orbit-rings__inner {
  width: 88%;
  height: 88%;
  animation: orbitSpin 30s linear infinite;
}

.orbit-rings__outer {
  width: 100%;
  height: 100%;
  animation: orbitSpinReverse 25s linear infinite;
}

.orbit-rings--cyan {
  --orbit-border: rgba(0, 255, 255, 0.35);
  --orbit-glow: rgba(0, 255, 255, 0.22);
}

.orbit-rings--thinking {
  --orbit-border: rgba(255, 80, 80, 0.42);
  --orbit-glow: rgba(255, 80, 80, 0.25);
}

.orbit-rings--summary {
  --orbit-border: rgba(255, 215, 0, 0.45);
  --orbit-glow: rgba(255, 215, 0, 0.28);
}

@keyframes orbitSpin {
  from {
    transform: translate(-50%, -50%) rotateZ(0deg);
  }
  to {
    transform: translate(-50%, -50%) rotateZ(360deg);
  }
}

@keyframes orbitSpinReverse {
  from {
    transform: translate(-50%, -50%) rotateZ(360deg);
  }
  to {
    transform: translate(-50%, -50%) rotateZ(0deg);
  }
}

@media (prefers-reduced-motion: reduce) {
  .orbit-rings__inner,
  .orbit-rings__outer {
    animation: none;
  }
}
</style>
