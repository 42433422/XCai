<template>
  <section>
    <h3 class="ttl">Step9 上架发布</h3>
    <p class="muted">以下为系统根据包内 manifest 给出的参考，可自行调整后再确认。</p>
    <button type="button" class="btn" @click="$emit('back')">返回测试与审核</button>
    <div class="muted box">
      <p v-if="listingHints.industryRaw">包内参考行业：{{ listingHints.industryRaw }}</p>
      <p v-else>包内未声明行业，默认通用。</p>
      <p v-if="listingHints.priceFromManifest != null">包内参考价格：¥{{ Number(listingHints.priceFromManifest).toFixed(2) }}</p>
    </div>
    <form @submit.prevent="$emit('submit')">
      <div class="row">
        <select class="input" :value="industry" @change="$emit('update:industry', $event.target.value)" required>
          <option value="" disabled>选择行业</option>
          <option v-for="opt in normalizedIndustryOptions" :key="opt" :value="opt">{{ opt }}</option>
        </select>
        <input class="input" type="number" min="0" step="0.01" :value="price" @input="$emit('update:price', Number($event.target.value || 0))" />
      </div>
      <input
        class="input industry-custom"
        type="text"
        :value="industry"
        list="employee-listing-industries"
        placeholder="自定义行业，或直接使用 AI / manifest 识别出的行业"
        @input="$emit('update:industry', $event.target.value)"
      />
      <datalist id="employee-listing-industries">
        <option v-for="opt in normalizedIndustryOptions" :key="'dl-' + opt" :value="opt" />
      </datalist>
      <div v-if="error" class="flash flash-err">{{ error }}</div>
      <div v-if="success" class="flash flash-success">{{ success }}</div>
      <button type="submit" class="btn btn-primary" :disabled="uploading || !canConfirm">
        {{ uploading ? '上传中...' : (isCatalogEdit ? '保存测试版' : '确认上架') }}
      </button>
    </form>
  </section>
</template>
<script setup>
import { computed } from 'vue'

const props = defineProps({
  listingHints: { type: Object, required: true },
  industry: { type: String, required: true },
  industryOptions: { type: Array, default: () => [] },
  price: { type: Number, required: true },
  error: { type: String, required: true },
  success: { type: String, required: true },
  uploading: { type: Boolean, required: true },
  canConfirm: { type: Boolean, required: true },
  isCatalogEdit: { type: Boolean, required: true },
})
defineEmits(['update:industry', 'update:price', 'submit', 'back'])

const normalizedIndustryOptions = computed(() => {
  const seen = new Set()
  const out = []
  for (const raw of [props.industry, ...(props.industryOptions || []), '通用']) {
    const text = typeof raw === 'string' ? raw.trim() : ''
    if (!text || seen.has(text)) continue
    seen.add(text)
    out.push(text)
  }
  return out
})
</script>
<style scoped>
.ttl{margin:.1rem 0 .45rem;color:#fff;font-size:18px}
.row{display:grid;grid-template-columns:1fr 1fr;gap:.5rem}
.box{margin:.5rem 0;border:1px solid rgba(255,255,255,.12);border-radius:10px;padding:.55rem .65rem;background:rgba(255,255,255,.02)}
.muted{font-size:12px;color:rgba(255,255,255,.62)}
.input{background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.12);border-radius:10px;color:#fff;padding:.55rem .65rem}
.industry-custom{width:100%;margin:.5rem 0 0}
.btn{border:1px solid rgba(255,255,255,.16);background:rgba(255,255,255,.04);color:#fff}
.btn-primary{background:#1f4f8e;border-color:#3563a5;color:#fff}
@media (max-width:720px){.row{grid-template-columns:1fr}}
</style>
