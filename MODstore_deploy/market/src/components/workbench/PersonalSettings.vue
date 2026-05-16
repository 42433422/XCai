<template>
  <Transition name="ps-fade">
    <div v-if="open" class="ps-mask" role="dialog" aria-modal="true" aria-labelledby="ps-title" @click.self="$emit('close')">
      <div class="ps-card">
        <header class="ps-head">
          <div class="ps-head-left">
            <svg class="ps-head-icon" width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round">
              <circle cx="10" cy="5" r="3"/><path d="M3 18c0-3.87 3.13-7 7-7s7 3.13 7 7"/>
            </svg>
            <h2 id="ps-title" class="ps-title">个性化设置</h2>
          </div>
          <button type="button" class="ps-close" aria-label="关闭" @click="$emit('close')">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round">
              <line x1="3" y1="3" x2="13" y2="13"/><line x1="13" y1="3" x2="3" y2="13"/>
            </svg>
          </button>
        </header>

        <div class="ps-body">
          <section class="ps-section">
            <h3 class="ps-section-title">
              <svg class="ps-section-icon" width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round">
                <circle cx="8" cy="8" r="3.5"/><path d="M8 1v2M8 13v2M1 8h2M13 8h2M3.05 3.05l1.41 1.41M11.54 11.54l1.41 1.41M3.05 12.95l1.41-1.41M11.54 4.46l1.41-1.41"/>
              </svg>
              主题
            </h3>
            <div class="ps-row">
              <label v-for="t in themes" :key="t.id" class="ps-chip" :class="{ 'ps-chip--on': model.theme === t.id }">
                <input
                  v-model="model.theme"
                  type="radio"
                  :value="t.id"
                  class="ps-sr-only"
                  @change="emitChange"
                />
                <span class="ps-chip-icon">{{ t.icon }}</span>
                <span class="ps-chip-text">{{ t.label }}</span>
              </label>
            </div>
          </section>

          <section class="ps-section">
            <h3 class="ps-section-title">
              <svg class="ps-section-icon" width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round">
                <path d="M2 12h12M2 8h12M2 4h12"/>
              </svg>
              字号 <span class="ps-section-badge">{{ model.fontPx }}px</span>
            </h3>
            <div class="ps-range-wrap">
              <span class="ps-range-label">A</span>
              <input
                v-model.number="model.fontPx"
                type="range"
                min="13"
                max="20"
                step="1"
                class="ps-range"
                @change="emitChange"
              />
              <span class="ps-range-label ps-range-label--lg">A</span>
            </div>
            <p class="ps-section-tip">仅作用于聊天消息体；过大会影响代码块换行。</p>
          </section>

          <section class="ps-section">
            <h3 class="ps-section-title">
              <svg class="ps-section-icon" width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round">
                <path d="M8 1v6"/><path d="M5 4a3 3 0 016 0v2a3 3 0 01-6 0V4z"/><path d="M2 10v1a6 6 0 0012 0v-1"/>
              </svg>
              朗读
            </h3>
            <p class="ps-section-tip">作用于一档聊天里 AI 消息的「朗读」。默认使用微软在线神经语音（与 Edge「大声朗读」同源，经本服务端转发）。</p>
            <div class="ps-row">
              <label class="ps-chip" :class="{ 'ps-chip--on': model.ttsEngine === 'edge-online' }">
                <input v-model="model.ttsEngine" class="ps-sr-only" type="radio" value="edge-online" @change="emitChange" />
                <span class="ps-chip-text">☁️ 微软云端</span>
              </label>
              <label class="ps-chip" :class="{ 'ps-chip--on': model.ttsEngine === 'browser' }">
                <input v-model="model.ttsEngine" class="ps-sr-only" type="radio" value="browser" @change="emitChange" />
                <span class="ps-chip-text">💻 本机浏览器</span>
              </label>
            </div>
            <template v-if="model.ttsEngine === 'edge-online'">
              <label class="ps-field-label" for="ps-tts-edge-voice">云端音色</label>
              <select id="ps-tts-edge-voice" v-model="model.ttsEdgeVoice" class="ps-select" @change="emitChange">
                <option v-for="ev in edgeVoices" :key="ev.id" :value="ev.id">{{ ev.label }}</option>
              </select>
            </template>
            <template v-else>
              <label class="ps-field-label" for="ps-tts-voice">本机音色</label>
              <select id="ps-tts-voice" v-model="model.ttsVoiceName" class="ps-select" @change="emitChange">
                <option value="">自动（优先中文）</option>
                <option v-for="v in voiceList" :key="v.name" :value="v.name">{{ v.label }}</option>
              </select>
            </template>
            <label class="ps-field-label ps-field-label--spaced" for="ps-tts-rate">语速 <span class="ps-section-badge">{{ model.ttsRate.toFixed(1) }}×</span></label>
            <div class="ps-range-wrap">
              <span class="ps-range-label">0.6×</span>
              <input
                id="ps-tts-rate"
                v-model.number="model.ttsRate"
                type="range"
                min="0.6"
                max="1.6"
                step="0.1"
                class="ps-range"
                @change="emitChange"
              />
              <span class="ps-range-label">1.6×</span>
            </div>
          </section>

          <section class="ps-section">
            <h3 class="ps-section-title">
              <svg class="ps-section-icon" width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round">
                <path d="M8 2v2M8 12v2M2 8h2M12 8h2"/><circle cx="8" cy="8" r="2.5"/><path d="M4 4l1.5 1.5M10.5 10.5L12 12M4 12l1.5-1.5M10.5 4.5L12 3"/>
              </svg>
              长期记忆
            </h3>
            <p class="ps-section-tip">这里写下的内容会以 system 提示形式注入每一次对话；不要写敏感信息。</p>
            <textarea
              v-model="model.memory"
              class="ps-textarea"
              rows="4"
              placeholder="例如：我叫张三，在成都做电商运营；周报偏数据驱动；尽量用结构化清单回答；输出代码默认 TypeScript。"
              spellcheck="false"
              @blur="emitChange"
            />
            <div class="ps-row ps-row--between">
              <button type="button" class="ps-btn ps-btn--ghost" @click="resetMemory">
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"><path d="M2 4h10M5 4V2.5a.5.5 0 01.5-.5h3a.5.5 0 01.5.5V4M3.5 4v7.5a1 1 0 001 1h5a1 1 0 001-1V4"/></svg>
                清空记忆
              </button>
              <span class="ps-counter" :class="{ 'ps-counter--warn': model.memory.length > 500 }">{{ model.memory.length }}/600</span>
            </div>
          </section>

          <section class="ps-section">
            <h3 class="ps-section-title">
              <svg class="ps-section-icon" width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round">
                <path d="M6 2l6 6-6 6"/>
              </svg>
              推荐问题模板
            </h3>
            <p class="ps-section-tip">首页 hero 下方会展示这里的快捷提问；每行一个，最多 6 条。</p>
            <textarea
              v-model="suggestionsRaw"
              class="ps-textarea"
              rows="4"
              placeholder="帮我把今天的工作拆成步骤&#10;帮我分析一个自动化流程&#10;帮我写一段客户沟通话术"
              spellcheck="false"
              @blur="onSuggestionsBlur"
            />
          </section>
        </div>

        <footer class="ps-foot">
          <button type="button" class="ps-btn ps-btn--ghost" @click="$emit('close')">取消</button>
          <button type="button" class="ps-btn ps-btn--primary" @click="onSave">
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><path d="M2 8l3 3 7-7"/></svg>
            保存
          </button>
        </footer>
      </div>
    </div>
  </Transition>
</template>

<script setup lang="ts">
import { onBeforeUnmount, reactive, ref, watch } from 'vue'
import { defaultPersonalSettings, type PersonalSettings } from '../../utils/personalSettings'

const props = defineProps<{
  open: boolean
  modelValue: PersonalSettings
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'update:modelValue', v: PersonalSettings): void
}>()

const themes = [
  { id: 'dark', label: '深色', icon: '🌙' },
  { id: 'light', label: '浅色', icon: '☀️' },
  { id: 'auto', label: '跟随系统', icon: '🖥️' },
]

const model = reactive<PersonalSettings>({ ...defaultPersonalSettings() })

const suggestionsRaw = ref('')
const voiceList = ref<Array<{ name: string; label: string }>>([])

const edgeVoices = [
  { id: 'zh-CN-XiaoxiaoNeural', label: '晓晓（女声，通用）' },
  { id: 'zh-CN-YunxiNeural', label: '云希（男声）' },
  { id: 'zh-CN-XiaoyiNeural', label: '晓伊（女声）' },
  { id: 'zh-CN-YunjianNeural', label: '云健（男声，资讯风）' },
  { id: 'zh-CN-XiaochenNeural', label: '晓辰（女声）' },
  { id: 'zh-CN-XiaomengNeural', label: '晓梦（女声）' },
]

function loadVoices() {
  if (typeof window === 'undefined' || !('speechSynthesis' in window)) {
    voiceList.value = []
    return
  }
  const synth = window.speechSynthesis
  const all = synth.getVoices()
  const zh = all
    .filter((v) => /^zh|cmn|yue/i.test(v.lang))
    .map((v) => ({ name: v.name, label: `${v.name} (${v.lang})` }))
  const en = all.filter((v) => /^en/i.test(v.lang)).slice(0, 6).map((v) => ({ name: v.name, label: `${v.name} (${v.lang})` }))
  voiceList.value = [...zh, ...en]
}

function syncFromProps() {
  const v = props.modelValue || ({} as PersonalSettings)
  const def = defaultPersonalSettings()
  model.theme = (v.theme || 'dark') as 'dark' | 'light' | 'auto'
  model.fontPx = Number.isFinite(Number(v.fontPx)) ? Number(v.fontPx) : 15
  model.memory = String(v.memory || '').slice(0, 600)
  model.suggestions = Array.isArray(v.suggestions) ? v.suggestions.slice(0, 6) : []
  model.ttsEngine = v.ttsEngine === 'browser' || v.ttsEngine === 'edge-online' ? v.ttsEngine : def.ttsEngine
  model.ttsEdgeVoice =
    typeof v.ttsEdgeVoice === 'string' && v.ttsEdgeVoice.trim()
      ? v.ttsEdgeVoice.trim().slice(0, 120)
      : def.ttsEdgeVoice
  model.ttsVoiceName = typeof v.ttsVoiceName === 'string' ? v.ttsVoiceName.slice(0, 256) : def.ttsVoiceName
  const rr = Number(v.ttsRate)
  model.ttsRate = Number.isFinite(rr) ? Math.max(0.6, Math.min(1.6, rr)) : def.ttsRate
  suggestionsRaw.value = model.suggestions.join('\n')
}

watch(
  () => props.modelValue,
  () => syncFromProps(),
  { immediate: true, deep: true },
)

watch(
  () => props.open,
  (open) => {
    if (!open) return
    loadVoices()
    if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
      window.speechSynthesis.onvoiceschanged = loadVoices
    }
  },
)

onBeforeUnmount(() => {
  if (typeof window !== 'undefined' && 'speechSynthesis' in window && window.speechSynthesis.onvoiceschanged === loadVoices) {
    window.speechSynthesis.onvoiceschanged = null
  }
})

function onSuggestionsBlur() {
  const lines = String(suggestionsRaw.value || '')
    .split(/\r?\n/)
    .map((s) => s.trim())
    .filter(Boolean)
    .slice(0, 6)
  model.suggestions = lines
  suggestionsRaw.value = lines.join('\n')
  emitChange()
}

function emitChange() {
  const ttsRate = Math.max(0.6, Math.min(1.6, Number(model.ttsRate) || 1))
  model.ttsRate = ttsRate
  const ttsEngine = model.ttsEngine === 'browser' ? 'browser' : 'edge-online'
  const allowedEdge = new Set(edgeVoices.map((e) => e.id))
  const ttsEdgeVoice = allowedEdge.has(model.ttsEdgeVoice) ? model.ttsEdgeVoice : defaultPersonalSettings().ttsEdgeVoice
  emit('update:modelValue', {
    ...model,
    ttsEngine,
    ttsEdgeVoice,
    memory: model.memory.slice(0, 600),
    ttsVoiceName: String(model.ttsVoiceName || '').slice(0, 256),
    ttsRate,
  })
}

function resetMemory() {
  model.memory = ''
  emitChange()
}

function onSave() {
  emitChange()
  emit('close')
}
</script>

<style scoped>
.ps-fade-enter-active {
  transition: opacity 0.2s ease;
}
.ps-fade-leave-active {
  transition: opacity 0.15s ease;
}
.ps-fade-enter-from,
.ps-fade-leave-to {
  opacity: 0;
}

.ps-mask {
  position: fixed;
  inset: 0;
  z-index: 80;
  background: rgba(0, 0, 0, 0.6);
  display: grid;
  place-items: center;
  padding: 1rem;
  backdrop-filter: blur(8px);
}

.ps-card {
  width: min(38rem, 100%);
  max-height: 88vh;
  display: flex;
  flex-direction: column;
  background: #0c0c12;
  border: 1px solid rgba(240, 240, 245, 0.08);
  border-radius: 16px;
  color: rgba(240, 240, 245, 0.9);
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5), 0 0 0 1px rgba(255, 255, 255, 0.04);
  overflow: hidden;
  pointer-events: auto;
  position: relative;
  z-index: 1;
}

.ps-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  flex-shrink: 0;
}

.ps-head-left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.ps-head-icon {
  color: #818cf8;
  flex-shrink: 0;
}

.ps-title {
  font-size: 1rem;
  margin: 0;
  font-weight: 600;
  color: rgba(240, 240, 245, 0.9);
}

.ps-close {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: 8px;
  background: transparent;
  color: rgba(240, 240, 245, 0.45);
  border: none;
  cursor: pointer;
  transition: background 150ms ease, color 150ms ease;
}

.ps-close:hover {
  background: rgba(255, 255, 255, 0.08);
  color: rgba(240, 240, 245, 0.85);
}

.ps-body {
  overflow-y: auto;
  padding: 4px 20px 0;
  flex: 1 1 0%;
  scrollbar-width: thin;
  scrollbar-color: rgba(255, 255, 255, 0.1) transparent;
}

.ps-section {
  padding: 16px 0;
  border-bottom: 1px solid rgba(255, 255, 255, 0.04);
}

.ps-section:last-child {
  border-bottom: none;
}

.ps-section-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 0.88rem;
  font-weight: 600;
  margin: 0 0 10px;
  color: rgba(240, 240, 245, 0.9);
}

.ps-section-icon {
  color: #818cf8;
  flex-shrink: 0;
}

.ps-section-badge {
  display: inline-flex;
  align-items: center;
  padding: 1px 8px;
  border-radius: 6px;
  background: rgba(99, 102, 241, 0.15);
  color: #818cf8;
  font-size: 0.75rem;
  font-weight: 500;
}

.ps-section-tip {
  margin: 6px 0 0;
  font-size: 0.75rem;
  line-height: 1.45;
  color: rgba(148, 163, 184, 0.5);
}

.ps-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.ps-row--between {
  justify-content: space-between;
  margin-top: 8px;
}

.ps-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.08);
  cursor: pointer;
  font-size: 0.82rem;
  color: rgba(240, 240, 245, 0.55);
  transition: all 150ms ease;
}

.ps-chip:hover {
  background: rgba(255, 255, 255, 0.07);
  border-color: rgba(255, 255, 255, 0.14);
  color: rgba(240, 240, 245, 0.8);
}

.ps-chip--on {
  background: rgba(99, 102, 241, 0.15);
  border-color: rgba(99, 102, 241, 0.35);
  color: #818cf8;
}

.ps-chip-icon {
  font-size: 0.9rem;
  line-height: 1;
}

.ps-chip-text {
  line-height: 1;
}

.ps-sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  border: 0;
}

html[data-workbench-theme='light'] .ps-chip {
  background: rgba(0, 0, 0, 0.04);
  border-color: rgba(0, 0, 0, 0.08);
  color: #86868b;
}

html[data-workbench-theme='light'] .ps-chip:hover {
  background: rgba(0, 0, 0, 0.06);
  border-color: rgba(0, 0, 0, 0.12);
  color: #1d1d1f;
}

html[data-workbench-theme='light'] .ps-chip--on {
  background: rgba(0, 113, 227, 0.10);
  border-color: rgba(0, 113, 227, 0.30);
  color: #0071e3;
}

.ps-range-wrap {
  display: flex;
  align-items: center;
  gap: 10px;
}

.ps-range-label {
  font-size: 0.7rem;
  color: rgba(148, 163, 184, 0.4);
  flex-shrink: 0;
}

.ps-range-label--lg {
  font-size: 0.9rem;
  font-weight: 600;
}

.ps-range {
  flex: 1 1 0%;
  -webkit-appearance: none;
  appearance: none;
  height: 4px;
  border-radius: 2px;
  background: rgba(255, 255, 255, 0.1);
  outline: none;
}

.ps-range::-webkit-slider-thumb {
  -webkit-appearance: none;
  appearance: none;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: #818cf8;
  cursor: pointer;
  border: 2px solid #0c0c12;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.3);
  transition: transform 120ms ease;
}

.ps-range::-webkit-slider-thumb:hover {
  transform: scale(1.15);
}

.ps-range::-moz-range-thumb {
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: #818cf8;
  cursor: pointer;
  border: 2px solid #0c0c12;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.3);
}

.ps-field-label {
  display: block;
  margin: 12px 0 6px;
  font-size: 0.78rem;
  color: rgba(148, 163, 184, 0.6);
}

.ps-field-label--spaced {
  margin-top: 16px;
}

.ps-select {
  width: 100%;
  padding: 8px 12px;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.08);
  color: rgba(240, 240, 245, 0.9);
  font-family: inherit;
  font-size: 0.82rem;
  outline: none;
  transition: border-color 150ms ease;
}

.ps-select:focus {
  border-color: rgba(99, 102, 241, 0.4);
}

.ps-select option {
  background: #0c0c12;
  color: rgba(240, 240, 245, 0.9);
}

.ps-textarea {
  width: 100%;
  padding: 10px 14px;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.08);
  color: rgba(240, 240, 245, 0.9);
  font-family: inherit;
  font-size: 0.84rem;
  line-height: 1.5;
  resize: vertical;
  outline: none;
  transition: border-color 150ms ease;
}

.ps-textarea:focus {
  border-color: rgba(99, 102, 241, 0.4);
}

.ps-textarea::placeholder {
  color: rgba(148, 163, 184, 0.3);
}

.ps-counter {
  font-size: 0.72rem;
  color: rgba(148, 163, 184, 0.4);
  font-variant-numeric: tabular-nums;
}

.ps-counter--warn {
  color: #fbbf24;
}

.ps-foot {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding: 12px 20px 16px;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
  flex-shrink: 0;
}

.ps-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 18px;
  border-radius: 10px;
  cursor: pointer;
  font-size: 0.84rem;
  font-weight: 500;
  border: 1px solid transparent;
  transition: all 150ms ease;
}

.ps-btn--ghost {
  background: rgba(255, 255, 255, 0.04);
  color: rgba(240, 240, 245, 0.65);
  border-color: rgba(255, 255, 255, 0.08);
}

.ps-btn--ghost:hover {
  background: rgba(255, 255, 255, 0.08);
  color: rgba(240, 240, 245, 0.85);
}

.ps-btn--primary {
  background: linear-gradient(135deg, #6366f1, #818cf8);
  color: #fff;
  border-color: transparent;
  font-weight: 600;
}

.ps-btn--primary:hover {
  background: linear-gradient(135deg, #818cf8, #a5b4fc);
}
</style>
