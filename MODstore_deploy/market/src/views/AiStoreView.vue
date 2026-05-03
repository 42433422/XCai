<template>
  <div class="store-page">
    <header class="store-hero">
      <div class="store-hero-inner">
        <p class="store-eyebrow">XC AGI · AI 市场</p>
        <h1 class="store-title">一站式选购 AI 员工与数字素材</h1>
        <p class="store-sub">
          AI 员工是其中一类；另有 Agent 提示词、Skill、TTS 声音、页面风格、个性化设计与 MOD 包素材等，可按类目与授权筛选。
        </p>
      </div>
    </header>

    <div class="store-toolbar">
      <section class="store-panel store-panel--search" aria-labelledby="store-search-heading">
        <div class="store-panel__hd">
          <h2 id="store-search-heading" class="store-panel__title">搜索</h2>
          <p class="store-panel__hint">按名称、包名或描述查找商品</p>
        </div>
        <div class="toolbar-row">
          <label class="sr-only" for="store-search">搜索</label>
          <input
            id="store-search"
            v-model="searchQ"
            class="input search-input"
            type="search"
            placeholder="搜索名称、包名、描述…"
            @keydown.enter.prevent="applyFilters"
          />
          <button type="button" class="btn btn-ghost" @click="applyFilters">搜索</button>
          <button type="button" class="btn btn-text" @click="resetFilters">重置全部筛选</button>
        </div>
      </section>

      <div class="store-facet-grid">
        <section class="store-panel store-panel--facet" aria-labelledby="store-facet-type-heading">
          <div class="store-panel__hd">
            <h2 id="store-facet-type-heading" class="store-panel__title">素材分类</h2>
            <p class="store-panel__hint">先选「类目」再选「工件类型」，缩小范围</p>
          </div>

          <div class="filter-block">
            <span class="filter-label">类目</span>
            <div class="chip-row">
              <button
                type="button"
                class="chip"
                :class="{ active: !filters.materialCategory }"
                @click="setMaterialCategory('')"
              >
                全部
              </button>
              <button
                v-for="cat in facetMaterialCategories"
                :key="'cat-' + cat"
                type="button"
                class="chip"
                :class="{ active: filters.materialCategory === cat }"
                @click="setMaterialCategory(cat)"
              >
                {{ materialCategoryLabel(cat) }}
              </button>
            </div>
          </div>

          <div class="filter-block">
            <span class="filter-label">工件类型</span>
            <div class="chip-row">
              <button
                type="button"
                class="chip"
                :class="{ active: !filters.artifact }"
                @click="setArtifact('')"
              >
                全部
              </button>
              <button
                v-for="art in facetArtifacts"
                :key="'art-' + art"
                type="button"
                class="chip"
                :class="{ active: filters.artifact === art }"
                @click="setArtifact(art)"
              >
                {{ artifactLabel(art) }}
              </button>
            </div>
          </div>
        </section>

        <section class="store-panel store-panel--facet" aria-labelledby="store-facet-policy-heading">
          <div class="store-panel__hd">
            <h2 id="store-facet-policy-heading" class="store-panel__title">行业与合规</h2>
            <p class="store-panel__hint">行业场景、授权范围与保密级</p>
          </div>

          <div class="filter-block">
            <span class="filter-label">行业</span>
            <div class="chip-row">
              <button
                type="button"
                class="chip"
                :class="{ active: !filters.industry }"
                @click="setIndustry('')"
              >
                全部
              </button>
              <button
                v-for="ind in facetIndustries"
                :key="'ind-' + ind"
                type="button"
                class="chip"
                :class="{ active: filters.industry === ind }"
                @click="setIndustry(ind)"
              >
                {{ ind }}
              </button>
            </div>
          </div>

          <div class="filter-block">
            <span class="filter-label">授权范围</span>
            <div class="chip-row">
              <button type="button" class="chip" :class="{ active: !filters.licenseScope }" @click="setLicenseScope('')">全部</button>
              <button
                v-for="scope in facetLicenseScopes"
                :key="'lic-' + scope"
                type="button"
                class="chip"
                :class="{ active: filters.licenseScope === scope }"
                @click="setLicenseScope(scope)"
              >
                {{ licenseScopeLabel(scope) }}
              </button>
            </div>
          </div>

          <div class="filter-block">
            <span class="filter-label">保密级</span>
            <div class="chip-row">
              <button type="button" class="chip" :class="{ active: !filters.securityLevel }" @click="setSecurityLevel('')">全部</button>
              <button type="button" class="chip" :class="{ active: filters.securityLevel === 'personal' }" @click="setSecurityLevel('personal')">个人级</button>
              <button type="button" class="chip" :class="{ active: filters.securityLevel === 'enterprise' }" @click="setSecurityLevel('enterprise')">企业级</button>
              <button type="button" class="chip" :class="{ active: filters.securityLevel === 'confidential' }" @click="setSecurityLevel('confidential')">保密级</button>
            </div>
          </div>
        </section>
      </div>
    </div>

    <div v-if="err" class="flash flash-err">{{ err }}</div>

    <section class="store-results" aria-labelledby="store-results-heading">
      <div class="store-results__hd">
        <h2 id="store-results-heading" class="store-results__title">商品列表</h2>
        <p v-if="!loading" class="store-results__meta">共 {{ total }} 条 · 当前展示 {{ items.length }} 条</p>
      </div>
      <div v-if="loading" class="state-msg">加载中…</div>
      <div v-else-if="!items.length" class="state-msg muted">暂无符合的商品，试试调整筛选或搜索。</div>
      <div v-else class="store-grid">
      <article v-for="item in items" :key="item.id" class="store-card">
        <div class="card-tags">
          <span class="tag tag-industry">{{ item.industry || '通用' }}</span>
          <span class="tag tag-category">{{ item.material_category_label || materialCategoryLabel(item.material_category) }}</span>
          <span class="tag tag-type">{{ artifactLabel(item.artifact) }}</span>
          <span class="tag tag-license">{{ item.license_scope_label || licenseScopeLabel(item.license_scope) }}</span>
          <span class="tag" :class="securityLevelClass(item.security_level)">{{ securityLabel(item.security_level) }}</span>
          <span v-if="item.compliance_status && item.compliance_status !== 'approved'" class="tag tag-review">{{ complianceStatusLabel(item.compliance_status) }}</span>
          <span v-if="item.purchased" class="tag tag-owned">已购</span>
        </div>
        <h2 class="card-title">{{ item.name }}</h2>
        <p class="card-desc">{{ truncate(item.description, 120) }}</p>
        <p class="card-meta">{{ item.pkg_id }} · v{{ item.version }}</p>
        <div class="card-footer">
          <span class="price" :class="{ free: item.price <= 0 }">
            {{ item.price <= 0 ? '免费' : '¥' + item.price.toFixed(2) }}
          </span>
          <div class="card-actions">
            <button
              v-if="authStore.isAdmin"
              type="button"
              class="btn btn-danger"
              :disabled="delistingId === item.id"
              @click="delistItem(item)"
            >
              {{ delistingId === item.id ? '下架中' : '下架' }}
            </button>
            <router-link :to="{ name: 'catalog-detail', params: { id: item.id } }" class="btn btn-detail">
              详情
            </router-link>
            <router-link :to="customerServiceLink(item, 'complaint')" class="btn btn-text">
              投诉/申诉
            </router-link>
          </div>
        </div>
      </article>
      </div>
    </section>

    <p v-if="!loading && total > items.length" class="pager-hint">共 {{ total }} 条，当前展示前 {{ items.length }} 条。</p>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { api } from '../api'
import { useAuthStore } from '../stores/auth'

const ARTIFACT_LABELS = {
  mod: 'MOD 插件',
  employee_pack: 'AI 员工包',
  bundle: '资源包',
  surface: '界面扩展',
  workflow_template: '工作流模板',
}

const MATERIAL_CATEGORY_LABELS = {
  ai_employee: 'AI 员工',
  agent_prompt: 'Agent 提示词',
  skill: 'Skill',
  tts_voice: 'TTS 声音模型',
  mod_asset: 'MOD 包素材',
  page_style: '页面风格',
  personal_design: '个性化设计',
  workflow_template: '工作流模板',
  other: '其他素材',
}

const LICENSE_SCOPE_LABELS = {
  personal: '个人使用',
  commercial: '商业授权',
  free_personal: '免费个人用',
}

const COMPLIANCE_STATUS_LABELS = {
  approved: '已审核',
  under_review: '投诉处理中',
  restricted: '已降权',
  delisted: '已下架',
}

const SECURITY_LABELS = {
  personal: '个人',
  enterprise: '企业',
  confidential: '保密',
}

const loading = ref(true)
const err = ref('')
const items = ref([])
const total = ref(0)
const delistingId = ref(null)
const searchQ = ref('')
const appliedQ = ref('')
const facets = ref({ industries: [], artifacts: [], material_categories: [], license_scopes: [], security_levels: [] })
const authStore = useAuthStore()

const filters = reactive({
  industry: '',
  artifact: '',
  materialCategory: '',
  licenseScope: '',
  securityLevel: '',
})

const facetIndustries = computed(() => facets.value.industries || [])
const facetArtifacts = computed(() => facets.value.artifacts || [])
const facetMaterialCategories = computed(() => facets.value.material_categories || [])
const facetLicenseScopes = computed(() => facets.value.license_scopes || [])
const facetSecurityLevels = computed(() => facets.value.security_levels || [])

function artifactLabel(art) {
  return ARTIFACT_LABELS[art] || art || '其他'
}

function materialCategoryLabel(cat) {
  return MATERIAL_CATEGORY_LABELS[cat] || cat || '其他素材'
}

function licenseScopeLabel(scope) {
  return LICENSE_SCOPE_LABELS[scope] || scope || '个人使用'
}

function complianceStatusLabel(status) {
  return COMPLIANCE_STATUS_LABELS[status] || status || '待处理'
}

function securityLabel(level) {
  return SECURITY_LABELS[level] || '个人'
}

function securityLevelClass(level) {
  if (level === 'confidential') return 'tag-confidential'
  if (level === 'enterprise') return 'tag-enterprise'
  return 'tag-personal'
}

function truncate(str, len) {
  if (!str) return ''
  return str.length > len ? str.slice(0, len) + '…' : str
}

async function loadFacets() {
  try {
    const res = await api.catalogFacets()
    facets.value = {
      industries: res.industries || [],
      artifacts: res.artifacts || [],
      material_categories: res.material_categories || [],
      license_scopes: res.license_scopes || [],
      security_levels: res.security_levels || [],
    }
  } catch {
    facets.value = { industries: [], artifacts: [], material_categories: [], license_scopes: [], security_levels: [] }
  }
}

async function loadItems() {
  loading.value = true
  err.value = ''
  try {
    const res = await api.catalog(
      appliedQ.value,
      filters.artifact,
      80,
      0,
      filters.industry,
      filters.securityLevel,
      filters.materialCategory,
      filters.licenseScope,
    )
    items.value = res.items || []
    total.value = res.total ?? items.value.length
  } catch (e) {
    err.value = e.message || String(e)
    items.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

function setIndustry(v) {
  filters.industry = v
}

function setArtifact(v) {
  filters.artifact = v
}

function setMaterialCategory(v) {
  filters.materialCategory = v
}

function setLicenseScope(v) {
  filters.licenseScope = v
}

function setSecurityLevel(v) {
  filters.securityLevel = v
}

function applyFilters() {
  appliedQ.value = searchQ.value.trim()
  loadItems()
}

function resetFilters() {
  searchQ.value = ''
  appliedQ.value = ''
  filters.industry = ''
  filters.artifact = ''
  filters.materialCategory = ''
  filters.licenseScope = ''
  filters.securityLevel = ''
  loadItems()
}

function customerServiceLink(item, scene = 'complaint') {
  return {
    name: 'customer-service',
    query: {
      scene,
      catalog_id: String(item?.id || ''),
      pkg_id: item?.pkg_id || '',
      item_name: item?.name || '',
      material_category: item?.material_category || '',
    },
  }
}

async function delistItem(item) {
  if (!item || delistingId.value) return
  const ok = window.confirm(`确定下架「${item.name}」吗？下架后 AI 市场将不再展示该商品。`)
  if (!ok) return
  delistingId.value = item.id
  err.value = ''
  try {
    await api.adminDeleteCatalog(item.id)
    await loadItems()
    await loadFacets()
  } catch (e) {
    err.value = e?.message || String(e)
  } finally {
    delistingId.value = null
  }
}

watch(
  () => [filters.industry, filters.artifact, filters.materialCategory, filters.licenseScope, filters.securityLevel],
  () => {
    loadItems()
  },
)

onMounted(async () => {
  await loadFacets()
  await loadItems()
})
</script>

<style scoped>
.store-page {
  min-height: 100vh;
  background: #0a0a0a;
  color: #fff;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  padding-bottom: 48px;
}

.store-hero {
  padding: clamp(2rem, 5vw, 3rem) var(--layout-pad-x) clamp(1.5rem, 4vw, 2rem);
  border-bottom: 0.5px solid rgba(255, 255, 255, 0.08);
  background: linear-gradient(180deg, rgba(96, 165, 250, 0.08) 0%, transparent 100%);
}

.store-hero-inner {
  width: 100%;
  max-width: var(--layout-max);
  margin: 0 auto;
  box-sizing: border-box;
}

.store-eyebrow {
  font-size: 13px;
  color: rgba(96, 165, 250, 0.9);
  letter-spacing: 0.08em;
  margin: 0 0 8px;
  text-transform: uppercase;
}

.store-title {
  font-size: clamp(26px, 4vw, 34px);
  font-weight: 600;
  margin: 0 0 10px;
  letter-spacing: -0.02em;
}

.store-sub {
  margin: 0;
  font-size: 15px;
  line-height: 1.6;
  color: rgba(255, 255, 255, 0.45);
  max-width: 640px;
}

.store-toolbar {
  width: 100%;
  max-width: var(--layout-max);
  margin: 0 auto;
  padding: 1.25rem var(--layout-pad-x) 0.5rem;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.store-panel {
  border: 0.5px solid rgba(255, 255, 255, 0.1);
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.025);
  padding: 1rem 1.1rem 1.05rem;
  box-sizing: border-box;
}

.store-panel--search {
  background: linear-gradient(145deg, rgba(96, 165, 250, 0.08), rgba(255, 255, 255, 0.02));
}

.store-panel__hd {
  margin-bottom: 0.75rem;
}

.store-panel__title {
  margin: 0 0 0.2rem;
  font-size: 0.95rem;
  font-weight: 600;
  letter-spacing: 0.02em;
  color: rgba(255, 255, 255, 0.92);
}

.store-panel__hint {
  margin: 0;
  font-size: 12px;
  line-height: 1.45;
  color: rgba(255, 255, 255, 0.38);
}

.store-facet-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: 1rem;
  align-items: start;
}

.toolbar-row {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
  margin-bottom: 0;
}

.search-input {
  flex: 1;
  min-width: 200px;
  max-width: 420px;
}

.filter-block {
  margin-bottom: 14px;
}

.filter-block:last-child {
  margin-bottom: 0;
}

.store-results {
  width: 100%;
  max-width: var(--layout-max);
  margin: 0 auto;
  padding: 0.75rem var(--layout-pad-x) 0;
  box-sizing: border-box;
}

.store-results__hd {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  justify-content: space-between;
  gap: 0.5rem 1rem;
  margin-bottom: 0.5rem;
}

.store-results__title {
  margin: 0;
  font-size: 0.95rem;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.88);
}

.store-results__meta {
  margin: 0;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.35);
}

.filter-label {
  display: block;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.35);
  margin-bottom: 8px;
  letter-spacing: 0.04em;
}

.chip-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.chip {
  border: 0.5px solid rgba(255, 255, 255, 0.12);
  background: rgba(255, 255, 255, 0.04);
  color: rgba(255, 255, 255, 0.75);
  font-size: 13px;
  padding: 6px 12px;
  border-radius: 999px;
  cursor: pointer;
  transition: background 0.15s, border-color 0.15s, color 0.15s;
}

.chip:hover {
  background: rgba(255, 255, 255, 0.08);
  color: #fff;
}

.chip.active {
  border-color: rgba(96, 165, 250, 0.5);
  background: rgba(96, 165, 250, 0.12);
  color: #fff;
}

.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 8px 14px;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  border: 0.5px solid rgba(255, 255, 255, 0.15);
  background: #141414;
  color: #fff;
}

.btn-ghost:hover {
  background: rgba(255, 255, 255, 0.06);
}

.btn-text {
  border-color: transparent;
  background: transparent;
  color: rgba(255, 255, 255, 0.45);
}

.btn-text:hover {
  color: #fff;
}

.input {
  padding: 10px 12px;
  border-radius: 8px;
  border: 0.5px solid rgba(255, 255, 255, 0.12);
  background: rgba(255, 255, 255, 0.04);
  color: #fff;
  font-size: 14px;
  outline: none;
}

.input::placeholder {
  color: rgba(255, 255, 255, 0.3);
}

.flash {
  width: 100%;
  max-width: var(--layout-max);
  margin: 0 auto 16px;
  padding: 10px 16px;
  border-radius: 8px;
  font-size: 14px;
  box-sizing: border-box;
}

.flash-err {
  background: rgba(255, 80, 80, 0.1);
  color: #ff8a8a;
}

.state-msg {
  text-align: center;
  padding: 40px 24px;
  font-size: 15px;
}

.state-msg.muted {
  color: rgba(255, 255, 255, 0.35);
}

.store-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(min(100%, 17.5rem), 1fr));
  gap: 16px;
  width: 100%;
  max-width: var(--layout-max);
  margin: 0 auto;
  padding: 8px var(--layout-pad-x) 0;
  box-sizing: border-box;
}

.store-card {
  border: 0.5px solid rgba(255, 255, 255, 0.1);
  border-radius: 14px;
  padding: 18px 16px;
  background: rgba(255, 255, 255, 0.02);
  display: flex;
  flex-direction: column;
  transition: border-color 0.2s, background 0.2s;
}

.store-card:hover {
  border-color: rgba(255, 255, 255, 0.16);
  background: rgba(255, 255, 255, 0.04);
}

.card-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 10px;
}

.tag {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 999px;
  font-weight: 500;
}

.tag-industry {
  background: rgba(96, 165, 250, 0.15);
  color: #93c5fd;
}

.tag-type {
  background: rgba(167, 139, 250, 0.12);
  color: #c4b5fd;
}

.tag-category {
  background: rgba(45, 212, 191, 0.12);
  color: #5eead4;
}

.tag-license {
  background: rgba(251, 146, 60, 0.12);
  color: #fdba74;
}

.tag-review {
  background: rgba(250, 204, 21, 0.13);
  color: #fde047;
}

.tag-owned {
  background: rgba(74, 222, 128, 0.12);
  color: #86efac;
}

.tag-personal { background: rgba(74, 222, 128, 0.12); color: #86efac; }
.tag-enterprise { background: rgba(251, 191, 36, 0.15); color: #fbbf24; }
.tag-confidential { background: rgba(248, 113, 113, 0.15); color: #f87171; }

.card-title {
  font-size: 16px;
  font-weight: 600;
  margin: 0 0 8px;
  line-height: 1.35;
}

.card-desc {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.5);
  margin: 0 0 10px;
  line-height: 1.5;
  flex: 1;
}

.card-meta {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.28);
  margin: 0 0 14px;
  word-break: break-all;
}

.card-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.card-actions {
  display: inline-flex;
  align-items: center;
  justify-content: flex-end;
  flex-wrap: wrap;
  gap: 8px;
}

.price {
  font-size: 18px;
  font-weight: 700;
}

.price.free {
  color: #86efac;
}

.btn-detail {
  text-decoration: none;
  border: 0.5px solid rgba(255, 255, 255, 0.2);
  background: rgba(255, 255, 255, 0.08);
  color: #fff;
  padding: 6px 12px;
  font-size: 13px;
  border-radius: 8px;
}

.btn-detail:hover {
  background: rgba(255, 255, 255, 0.12);
}

.btn-danger {
  color: #fca5a5;
  border-color: rgba(248, 113, 113, 0.35);
  background: rgba(127, 29, 29, 0.18);
}

.btn-danger:hover:not(:disabled) {
  color: #fecaca;
  background: rgba(127, 29, 29, 0.28);
}

.pager-hint {
  text-align: center;
  margin-top: 24px;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.3);
}

.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  border: 0;
}

@media (max-width: 900px) {
  .store-facet-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 640px) {
  .store-hero {
    padding: 32px 16px 24px;
  }
  .store-toolbar {
    padding-left: 16px;
    padding-right: 16px;
  }
  .store-grid {
    padding-left: 16px;
    padding-right: 16px;
  }
  .store-results {
    padding-left: 16px;
    padding-right: 16px;
  }
}
</style>
