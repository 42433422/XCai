<template>
  <div class="skill-selector">
    <div class="row head">
      <strong>Skill 选择器</strong>
      <button type="button" class="btn btn-sm" @click="showMarket = !showMarket">{{ showMarket ? '收起市场' : '添加技能' }}</button>
    </div>
    <div v-if="selected.length" class="selected-list">
      <div v-for="(item, idx) in selected" :key="`${item.skill_id}-${idx}`" class="skill-card">
        <div>
          <div class="title">{{ item.skill_name }} <span class="muted">v{{ item.version }}</span></div>
          <div class="muted">{{ item.description || item.type }}</div>
        </div>
        <button type="button" class="btn btn-sm" @click="removeSkill(idx)">移除</button>
      </div>
    </div>
    <p v-else class="muted">暂无已选技能</p>

    <div v-if="showMarket" class="market">
      <input v-model="keyword" class="input" placeholder="搜索技能名称" />
      <select v-model="typeFilter" class="input">
        <option value="">全部分类</option>
        <option v-for="t in typeOptions" :key="t.value" :value="t.value">{{ t.label }}</option>
      </select>
      <div v-for="item in filteredMarket" :key="item.skill_id" class="market-item">
        <div>
          <div class="title">{{ item.skill_name }} <span class="muted">v{{ item.version }}</span></div>
          <div class="muted">{{ item.description }}</div>
        </div>
        <button type="button" class="btn btn-sm" @click="addSkill(item)">添加</button>
      </div>
      <p v-if="dependencyWarnings.length" class="warn">依赖检查：{{ dependencyWarnings.join('；') }}</p>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'

const props = defineProps({
  modelValue: { type: Array, default: () => [] },
})
const emit = defineEmits(['update:modelValue'])

const showMarket = ref(false)
const keyword = ref('')
const typeFilter = ref('')
const selected = computed(() => (Array.isArray(props.modelValue) ? props.modelValue : []))

const typeOptions = [
  { value: 'document_processing', label: '文档处理' },
  { value: 'data_processing', label: '数据处理' },
  { value: 'image_recognition', label: '图像识别' },
  { value: 'audio_processing', label: '语音处理' },
  { value: 'network_request', label: '网络请求' },
  { value: 'business_logic', label: '业务逻辑' },
]

const skillMarket = [
  { skill_id: 'doc.extractor', skill_name: '文档抽取器', version: '1.0.0', type: 'document_processing', description: '提取 PDF/Docx 结构化信息', dependencies: [] },
  { skill_id: 'data.cleaner', skill_name: '数据清洗器', version: '1.0.0', type: 'data_processing', description: '缺失值处理与格式清洗', dependencies: [] },
  { skill_id: 'img.ocr', skill_name: 'OCR 识别', version: '1.0.0', type: 'image_recognition', description: '图片文字识别', dependencies: [] },
  { skill_id: 'voice.transcribe', skill_name: '语音转写', version: '1.0.0', type: 'audio_processing', description: '音频转文本', dependencies: [] },
  { skill_id: 'http.client', skill_name: 'HTTP 调用器', version: '1.0.0', type: 'network_request', description: '标准化外部 API 调用', dependencies: [] },
]

const filteredMarket = computed(() => skillMarket.filter((item) => {
  if (typeFilter.value && item.type !== typeFilter.value) return false
  if (!keyword.value.trim()) return true
  return item.skill_name.includes(keyword.value.trim()) || item.description.includes(keyword.value.trim())
}))

const dependencyWarnings = computed(() => {
  const ids = new Set(selected.value.map((x) => x.skill_id))
  const warns = []
  selected.value.forEach((item) => {
    const deps = Array.isArray(item.dependencies) ? item.dependencies : []
    deps.forEach((dep) => {
      if (!ids.has(dep)) warns.push(`${item.skill_name} 缺少依赖 ${dep}`)
    })
  })
  return warns
})

function addSkill(item) {
  const list = [...selected.value]
  if (list.some((x) => x.skill_id === item.skill_id)) return
  list.push({ ...item, config: {}, enabled: true })
  emit('update:modelValue', list)
}
function removeSkill(idx) {
  const list = [...selected.value]
  list.splice(idx, 1)
  emit('update:modelValue', list)
}
</script>

<style scoped>
.skill-selector{border:1px solid rgba(255,255,255,.12);border-radius:8px;padding:.5rem}
.head{display:flex;justify-content:space-between;align-items:center}
.selected-list,.market{display:flex;flex-direction:column;gap:.35rem;margin-top:.4rem}
.skill-card,.market-item{display:flex;justify-content:space-between;gap:.4rem;border:1px solid rgba(255,255,255,.08);border-radius:6px;padding:.35rem}
.title{font-size:12px;color:#fff}
.muted{font-size:11px;color:rgba(255,255,255,.6)}
.warn{font-size:11px;color:#facc15}
</style>
