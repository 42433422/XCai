<template>
  <div v-if="open" class="ps-mask" role="dialog" aria-modal="true" aria-labelledby="ps-title" @click.self="$emit('close')">
    <div class="ps-card">
      <header class="ps-head">
        <h2 id="ps-title" class="ps-title">个性化设置</h2>
        <button type="button" class="ps-close" aria-label="关闭" @click="$emit('close')">×</button>
      </header>

      <section class="ps-section">
        <h3 class="ps-section-title">主题</h3>
        <div class="ps-row">
          <label v-for="t in themes" :key="t.id" class="ps-radio" :class="{ 'ps-radio--on': model.theme === t.id }">
            <input
              v-model="model.theme"
              type="radio"
              :value="t.id"
              class="ps-radio__input"
              @change="emitChange"
            />
            <span class="ps-radio__dot" aria-hidden="true">{{ t.icon }}</span>
            <span>{{ t.label }}</span>
          </label>
        </div>
      </section>

      <section class="ps-section">
        <h3 class="ps-section-title">字号 ({{ model.fontPx }}px)</h3>
        <input
          v-model.number="model.fontPx"
          type="range"
          min="13"
          max="20"
          step="1"
          class="ps-range"
          @change="emitChange"
        />
        <p class="ps-section-tip">仅作用于聊天消息体；过大会影响代码块换行。</p>
      </section>

      <section class="ps-section">
        <h3 class="ps-section-title">长期记忆（&ldquo;记住我的事实&rdquo;）</h3>
        <p class="ps-section-tip">这里写下的内容会以 system 提示形式注入每一次对话；不要写敏感信息。</p>
        <textarea
          v-model="model.memory"
          class="ps-textarea"
          rows="5"
          placeholder="例如：我叫张三，在成都做电商运营；周报偏数据驱动；尽量用结构化清单回答；输出代码默认 TypeScript。"
          spellcheck="false"
          @blur="emitChange"
        />
        <div class="ps-row">
          <button type="button" class="ps-btn ps-btn--ghost" @click="resetMemory">清空记忆</button>
          <span class="ps-section-tip">字数 {{ model.memory.length }}/600</span>
        </div>
      </section>

      <section class="ps-section">
        <h3 class="ps-section-title">推荐问题模板</h3>
        <p class="ps-section-tip">首页 hero 下方会展示这里的快捷提问；每行一个，最多 6 条。</p>
        <textarea
          v-model="suggestionsRaw"
          class="ps-textarea"
          rows="5"
          placeholder="帮我把今天的工作拆成步骤&#10;帮我分析一个自动化流程&#10;帮我写一段客户沟通话术"
          spellcheck="false"
          @blur="onSuggestionsBlur"
        />
      </section>

      <footer class="ps-foot">
        <button type="button" class="ps-btn ps-btn--ghost" @click="$emit('close')">关闭</button>
        <button type="button" class="ps-btn ps-btn--primary" @click="onSave">保存</button>
      </footer>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref, watch } from 'vue'
import type { PersonalSettings } from '../../utils/personalSettings'

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

const model = reactive<PersonalSettings>({
  theme: 'dark',
  fontPx: 15,
  memory: '',
  suggestions: [],
})

const suggestionsRaw = ref('')

function syncFromProps() {
  const v = props.modelValue || ({} as PersonalSettings)
  model.theme = (v.theme || 'dark') as 'dark' | 'light' | 'auto'
  model.fontPx = Number.isFinite(Number(v.fontPx)) ? Number(v.fontPx) : 15
  model.memory = String(v.memory || '').slice(0, 600)
  model.suggestions = Array.isArray(v.suggestions) ? v.suggestions.slice(0, 6) : []
  suggestionsRaw.value = model.suggestions.join('\n')
}

watch(
  () => props.modelValue,
  () => syncFromProps(),
  { immediate: true, deep: true },
)

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
  emit('update:modelValue', { ...model, memory: model.memory.slice(0, 600) })
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
.ps-mask {
  position: fixed;
  inset: 0;
  z-index: 80;
  background: rgba(2, 6, 23, 0.7);
  display: grid;
  place-items: center;
  padding: 1rem;
  backdrop-filter: blur(6px);
}

.ps-card {
  width: min(40rem, 100%);
  max-height: 90vh;
  overflow-y: auto;
  padding: 1.25rem 1.4rem;
  background: rgba(15, 23, 42, 0.96);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 0.85rem;
  color: #e2e8f0;
}

.ps-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 0.85rem;
}

.ps-title {
  font-size: 1.1rem;
  margin: 0;
  font-weight: 700;
}

.ps-close {
  width: 2rem;
  height: 2rem;
  border-radius: 0.45rem;
  background: rgba(255, 255, 255, 0.05);
  color: rgba(226, 232, 240, 0.78);
  border: 1px solid rgba(255, 255, 255, 0.08);
  cursor: pointer;
  font-size: 1.1rem;
}

.ps-section {
  margin-top: 1rem;
  padding-top: 1rem;
  border-top: 1px dashed rgba(255, 255, 255, 0.08);
}

.ps-section:first-of-type {
  margin-top: 0.5rem;
  padding-top: 0;
  border-top: none;
}

.ps-section-title {
  font-size: 0.92rem;
  font-weight: 600;
  margin: 0 0 0.5rem;
  color: rgba(165, 180, 252, 0.95);
}

.ps-section-tip {
  margin: 0.35rem 0 0;
  font-size: 0.75rem;
  color: rgba(203, 213, 225, 0.6);
}

.ps-row {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  flex-wrap: wrap;
}

.ps-radio {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.35rem 0.65rem;
  border-radius: 999px;
  background: rgba(15, 23, 42, 0.6);
  border: 1px solid rgba(255, 255, 255, 0.1);
  cursor: pointer;
  font-size: 0.82rem;
}

.ps-radio--on {
  background: rgba(99, 102, 241, 0.32);
  border-color: rgba(165, 180, 252, 0.6);
}

.ps-radio__input {
  display: none;
}

.ps-range {
  width: 100%;
}

.ps-textarea {
  width: 100%;
  padding: 0.6rem 0.75rem;
  border-radius: 0.5rem;
  background: rgba(2, 6, 23, 0.7);
  border: 1px solid rgba(255, 255, 255, 0.1);
  color: #e2e8f0;
  font-family: inherit;
  font-size: 0.86rem;
  resize: vertical;
}

.ps-textarea:focus {
  outline: none;
  border-color: rgba(129, 140, 248, 0.55);
}

.ps-foot {
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
  margin-top: 1.2rem;
}

.ps-btn {
  padding: 0.45rem 0.95rem;
  border-radius: 0.5rem;
  cursor: pointer;
  font-size: 0.84rem;
  border: 1px solid transparent;
}

.ps-btn--ghost {
  background: rgba(255, 255, 255, 0.05);
  color: rgba(226, 232, 240, 0.85);
  border-color: rgba(255, 255, 255, 0.1);
}

.ps-btn--primary {
  background: linear-gradient(135deg, rgba(129, 140, 248, 0.5), rgba(99, 102, 241, 0.7));
  color: #fff;
  border-color: rgba(165, 180, 252, 0.6);
}

.ps-btn--ghost:hover {
  background: rgba(255, 255, 255, 0.1);
}

.ps-btn--primary:hover {
  filter: brightness(1.1);
}
</style>
