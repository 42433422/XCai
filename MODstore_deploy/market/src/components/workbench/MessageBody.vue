<template>
  <div ref="hostRef" class="msg-body" v-html="rendered" />
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { renderMarkdown } from '../../utils/lightMarkdown'

const props = defineProps<{
  content: string
  /** 是否在生成中（生成中末尾会附加光标） */
  streaming?: boolean
}>()

const hostRef = ref<HTMLDivElement | null>(null)

const rendered = computed(() => {
  const html = renderMarkdown(props.content || '')
  if (props.streaming) {
    return `${html}<span class="msg-body__cursor" aria-hidden="true">▍</span>`
  }
  return html
})

let mermaidApi: any = null
let mermaidInit = false

async function getMermaid() {
  if (!mermaidApi) {
    const mod = await import('mermaid')
    mermaidApi = mod.default
  }
  if (!mermaidInit) {
    mermaidApi.initialize({
      startOnLoad: false,
      securityLevel: 'strict',
      theme: 'dark',
      fontFamily: 'ui-sans-serif, system-ui, sans-serif',
    })
    mermaidInit = true
  }
  return mermaidApi
}

async function flushMermaid() {
  const host = hostRef.value
  if (!host) return
  const els = Array.from(host.querySelectorAll('.md-mermaid')) as HTMLElement[]
  if (!els.length) return
  let mer
  try {
    mer = await getMermaid()
  } catch {
    for (const el of els) el.textContent = '[流程图加载失败]'
    return
  }
  for (const el of els) {
    if (el.dataset.rendered === '1') continue
    const src = el.dataset.source || ''
    if (!src) {
      el.dataset.rendered = '1'
      continue
    }
    const slot = document.createElement('div')
    slot.className = 'mermaid'
    slot.textContent = src
    el.innerHTML = ''
    el.appendChild(slot)
    try {
      await mer.run({ nodes: [slot] })
      el.dataset.rendered = '1'
    } catch (e) {
      el.innerHTML = `<pre class="md-code"><code class="md-code__body">[流程图解析失败：${(e as Error)?.message || e}]\n\n${src.replace(/[<>&]/g, (c) => ({ '<': '&lt;', '>': '&gt;', '&': '&amp;' } as any)[c])}</code></pre>`
      el.dataset.rendered = '1'
    }
  }
}

function bindCopyButtons() {
  const host = hostRef.value
  if (!host) return
  const btns = Array.from(host.querySelectorAll('.md-code__copy')) as HTMLButtonElement[]
  for (const btn of btns) {
    if (btn.dataset.bound === '1') continue
    btn.dataset.bound = '1'
    btn.addEventListener('click', async () => {
      const code = btn.parentElement?.parentElement?.querySelector('.md-code__body')?.textContent || ''
      try {
        await navigator.clipboard.writeText(code)
        const orig = btn.textContent
        btn.textContent = '已复制'
        window.setTimeout(() => {
          btn.textContent = orig || '复制'
        }, 1400)
      } catch {
        btn.textContent = '复制失败'
      }
    })
  }
}

async function flushAll() {
  await nextTick()
  bindCopyButtons()
  await flushMermaid()
}

onMounted(() => {
  void flushAll()
})

watch(
  () => props.content,
  () => {
    void flushAll()
  },
)
</script>

<style scoped>
.msg-body {
  display: block;
  color: rgba(248, 250, 252, 0.94);
  line-height: 1.6;
  font-size: 0.95rem;
  word-break: break-word;
}

.msg-body :deep(.md-p) {
  margin: 0.4rem 0;
}

.msg-body :deep(.md-h) {
  margin: 0.85rem 0 0.5rem;
  font-weight: 700;
  line-height: 1.3;
}

.msg-body :deep(.md-h1) { font-size: 1.45rem; }
.msg-body :deep(.md-h2) { font-size: 1.25rem; }
.msg-body :deep(.md-h3) { font-size: 1.08rem; }
.msg-body :deep(.md-h4) { font-size: 1rem; color: rgba(226, 232, 240, 0.92); }
.msg-body :deep(.md-h5),
.msg-body :deep(.md-h6) { font-size: 0.94rem; color: rgba(203, 213, 225, 0.9); }

.msg-body :deep(.md-list) {
  padding-left: 1.4rem;
  margin: 0.4rem 0;
}

.msg-body :deep(.md-li) {
  margin: 0.18rem 0;
}

.msg-body :deep(.md-quote) {
  margin: 0.6rem 0;
  padding: 0.4rem 0.85rem;
  border-left: 3px solid rgba(129, 140, 248, 0.55);
  background: rgba(129, 140, 248, 0.08);
  color: rgba(226, 232, 240, 0.88);
  border-radius: 0 0.4rem 0.4rem 0;
}

.msg-body :deep(.md-link) {
  color: #93c5fd;
  text-decoration: underline;
  text-underline-offset: 2px;
}
.msg-body :deep(.md-link:hover) { color: #bfdbfe; }

.msg-body :deep(.md-img) {
  max-width: 100%;
  border-radius: 0.5rem;
  margin: 0.4rem 0;
}

.msg-body :deep(.md-hr) {
  border: 0;
  height: 1px;
  background: rgba(255, 255, 255, 0.1);
  margin: 0.85rem 0;
}

.msg-body :deep(.md-code-inline) {
  padding: 0.08em 0.35em;
  border-radius: 0.32em;
  background: rgba(15, 23, 42, 0.6);
  border: 1px solid rgba(255, 255, 255, 0.08);
  font-family: ui-monospace, 'SFMono-Regular', Menlo, Consolas, monospace;
  font-size: 0.88em;
  color: #fbbf24;
}

.msg-body :deep(.md-code) {
  margin: 0.5rem 0;
  border-radius: 0.6rem;
  background: rgba(2, 6, 23, 0.7);
  border: 1px solid rgba(255, 255, 255, 0.08);
  overflow: hidden;
}

.msg-body :deep(.md-code__head) {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.35rem 0.75rem;
  background: rgba(15, 23, 42, 0.85);
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  font-size: 0.72rem;
  color: rgba(226, 232, 240, 0.7);
  letter-spacing: 0.04em;
  text-transform: uppercase;
}

.msg-body :deep(.md-code__copy) {
  background: transparent;
  color: rgba(226, 232, 240, 0.78);
  border: 1px solid rgba(255, 255, 255, 0.12);
  padding: 0.18rem 0.55rem;
  font-size: 0.7rem;
  border-radius: 0.4rem;
  cursor: pointer;
  text-transform: none;
  letter-spacing: 0;
}
.msg-body :deep(.md-code__copy:hover) {
  background: rgba(99, 102, 241, 0.18);
  color: #fff;
}

.msg-body :deep(.md-code__body) {
  display: block;
  padding: 0.7rem 0.95rem;
  font-family: ui-monospace, 'SFMono-Regular', Menlo, Consolas, monospace;
  font-size: 0.86rem;
  line-height: 1.55;
  color: #e2e8f0;
  overflow-x: auto;
  white-space: pre;
}

.msg-body :deep(.md-table-wrap) {
  margin: 0.55rem 0;
  overflow-x: auto;
  border-radius: 0.55rem;
  border: 1px solid rgba(255, 255, 255, 0.08);
}

.msg-body :deep(.md-table) {
  border-collapse: collapse;
  width: 100%;
  font-size: 0.88rem;
}

.msg-body :deep(.md-table th),
.msg-body :deep(.md-table td) {
  padding: 0.45rem 0.7rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  border-right: 1px solid rgba(255, 255, 255, 0.06);
  text-align: left;
  vertical-align: top;
}

.msg-body :deep(.md-table th:last-child),
.msg-body :deep(.md-table td:last-child) {
  border-right: none;
}

.msg-body :deep(.md-table th) {
  background: rgba(99, 102, 241, 0.12);
  color: rgba(226, 232, 240, 0.95);
  font-weight: 600;
}

.msg-body :deep(.md-table tbody tr:hover) {
  background: rgba(255, 255, 255, 0.04);
}

.msg-body :deep(.md-math) {
  font-family: 'Cambria Math', 'Times New Roman', serif;
  color: #fbbf24;
  font-style: italic;
}

.msg-body :deep(.md-math-block) {
  display: block;
  margin: 0.6rem 0;
  padding: 0.5rem 0.9rem;
  border: 1px dashed rgba(251, 191, 36, 0.4);
  border-radius: 0.45rem;
  text-align: center;
  background: rgba(251, 191, 36, 0.05);
}

.msg-body :deep(.md-mermaid) {
  display: block;
  margin: 0.55rem 0;
  padding: 0.6rem;
  background: rgba(15, 23, 42, 0.6);
  border-radius: 0.6rem;
  border: 1px solid rgba(255, 255, 255, 0.06);
  text-align: center;
}

.msg-body :deep(.md-mermaid svg) {
  max-width: 100%;
  height: auto;
}

.msg-body :deep(.msg-body__cursor) {
  display: inline-block;
  width: 0.55ch;
  margin-left: 0.1ch;
  color: rgba(165, 180, 252, 0.9);
  animation: msgBodyCursorBlink 1s steps(2, start) infinite;
}

@keyframes msgBodyCursorBlink {
  to {
    visibility: hidden;
  }
}
</style>
