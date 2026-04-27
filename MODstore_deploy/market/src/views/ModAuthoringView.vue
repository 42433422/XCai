<template>
  <div class="authoring-page">
    <div v-if="loading" class="loading">加载中...</div>
    <div v-else-if="loadError" class="panel panel-err">
      <p>{{ loadError }}</p>
      <button type="button" class="btn" @click="goRepo">返回 Mod 仓库</button>
    </div>
    <template v-else-if="modData">
      <header class="page-header">
        <div class="header-top">
          <button type="button" class="btn btn-ghost" @click="goRepo">← Mod 仓库</button>
          <span
            class="badge"
            :class="modData.validation_ok ? 'badge-ok' : 'badge-warn'"
          >
            {{ modData.validation_ok ? 'manifest 校验通过' : 'manifest 待修正' }}
          </span>
        </div>
        <h1 class="page-title">{{ modData.manifest?.name || modData.id }}</h1>
        <p class="page-sub">
          <code class="mono">{{ modData.id }}</code>
          <span v-if="modData.manifest?.version" class="muted"> · v{{ modData.manifest.version }}</span>
        </p>
      </header>

      <div v-if="message" :class="['flash', messageOk ? 'flash-ok' : 'flash-err']">{{ message }}</div>

      <nav class="tabs">
        <button
          v-for="t in tabs"
          :key="t.id"
          type="button"
          class="tab"
          :class="{ active: tab === t.id }"
          @click="tab = t.id"
        >
          {{ t.label }}
        </button>
      </nav>

      <!-- 概览与清单 -->
      <section v-show="tab === 'guide'" class="panel">
        <h2 class="panel-title">这份扩展是做什么的？</h2>
        <p class="overview-lead">
          <strong>{{ modData.manifest?.name || modData.id }}</strong>
          <span v-if="modData.manifest?.version" class="muted small"> · 版本 {{ modData.manifest.version }}</span>
        </p>
        <p v-if="modDescriptionLine" class="overview-desc">{{ modDescriptionLine }}</p>
        <p v-else class="overview-desc muted small">
          还没有一句话介绍。可以打开「配置 (JSON)」填写 <code class="mono">description</code>，让同事一眼看懂用途。
        </p>

        <h3 class="sub-title">工作流里会用到的「AI 员工名片」</h3>
        <p class="emp-intro">
          这里的每一条，相当于给自动化流程起的一个<strong>角色名片</strong>：名字、说明会出现在工作台和流程配置里。
          <strong>接微信、打电话等真实能力</strong>取决于本 Mod 里是否已有对应程序代码；改名片不会自动变出程序，需要时在
          <button type="button" class="linkish" @click="tab = 'files'">「编辑文件」</button>里改 Python，或请开发者协助。
        </p>
        <p v-if="scaffoldEnvHint" class="muted small emp-env-hint">{{ scaffoldEnvHint }}</p>
        <div class="emp-toolbar">
          <button type="button" class="btn btn-primary btn-sm" @click="openEmployeeModal('add')">添加员工名片</button>
        </div>
        <p v-if="!workflowEmployeesRows.length" class="muted small emp-empty">
          还没有声明任何员工。点「添加员工名片」即可从零增加；也可在「配置 (JSON)」里批量编辑 <code class="mono">workflow_employees</code>。
        </p>
        <div v-else class="emp-table-wrap">
          <table class="emp-table">
            <thead>
              <tr>
                <th>显示名</th>
                <th>内部 ID</th>
                <th>一句话</th>
                <th>给用户看的说明</th>
                <th class="emp-th-link">MODstore 图</th>
                <th class="emp-th-actions">操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in workflowEmployeesRows" :key="'emp-' + row.index">
                <td>{{ row.label || '—' }}</td>
                <td class="mono">{{ row.id || '—' }}</td>
                <td>{{ row.panelTitle || '—' }}</td>
                <td class="emp-summary-cell">
                  <span :title="row.bodyFull">{{ row.isEmpty ? '（待完善）' : row.bodyShort }}</span>
                </td>
                <td class="emp-link-cell">
                  <template v-if="row.linkedWorkflowId">
                    <span class="muted small">#{{ row.linkedWorkflowId }}</span>
                  </template>
                  <div v-else class="wf-link-inline">
                    <select
                      class="input input-sm wf-link-select"
                      :value="linkPick[row.index] ?? 0"
                      :disabled="linkWorkflowBusy || !linkableWorkflows.length"
                      @change="(ev) => { linkPick[row.index] = Number((ev.target as HTMLSelectElement).value) }"
                    >
                      <option :value="0">选择工作流…</option>
                      <option v-for="w in linkableWorkflows" :key="w.id" :value="w.id">
                        {{ w.name }} (id={{ w.id }})
                      </option>
                    </select>
                    <button
                      type="button"
                      class="btn btn-sm btn-primary"
                      :disabled="linkWorkflowBusy || !linkPick[row.index]"
                      @click="applyWorkflowLinkToRow(row)"
                    >写入关联</button>
                  </div>
                </td>
                <td class="emp-actions-cell">
                  <button type="button" class="btn btn-sm btn-ghost" @click="openEmployeeModal('edit', row.index)">编辑</button>
                  <button type="button" class="btn btn-sm btn-ghost" @click="goEmployeePrefill(row)">带入员工制作</button>
                  <button
                    type="button"
                    class="btn btn-sm btn-primary"
                    :disabled="registerCatalogBusy === row.index"
                    title="从该条声明生成最小 employee_pack 并写入本地 /v1/packages（需已登录）。依赖 Mod 内 Python 电话路由时请走员工制作页导出完整包。"
                    @click="registerWorkflowEmployeeCatalog(row)"
                  >
                    {{ registerCatalogBusy === row.index ? '登记中…' : '一键登记' }}
                  </button>
                  <button
                    v-if="row.linkedWorkflowId"
                    type="button"
                    class="btn btn-sm btn-primary"
                    @click="openWorkflowSandboxDecompose(row)"
                  >拆解与沙盒测试</button>
                  <button type="button" class="btn btn-sm btn-ghost danger" @click="confirmDeleteEmployee(row.index)">删除</button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <details class="dev-details">
          <summary class="dev-details-summary">给开发者：XCAGI 契约摘要</summary>
          <p class="muted small dev-details-lead">
            完整字段与契约请以宿主仓库中的
            <strong>MOD_AUTHORING_GUIDE.md</strong>（XCAGI MOD 作者指南）为准；以下为制作时常用摘要。
          </p>
          <ul class="guide-list">
            <li>物理路径 <code class="mono">mods/&lt;mod_id&gt;/</code>，目录名须与 <code class="mono">manifest.id</code> 一致。</li>
            <li>根目录必须有 <code class="mono">manifest.json</code>；<code class="mono">backend/__init__.py</code> 必须存在（可为空）。</li>
            <li>
              <code class="mono">backend.entry</code> 指向 <code class="mono">backend/&lt;entry&gt;.py</code>，推荐导出
              <code class="mono">register_fastapi_routes(app, mod_id)</code>；禁止新 Mod 使用 Flask
              <code class="mono">register_blueprints</code>。
            </li>
            <li>前端约定：<code class="mono">frontend/routes.js</code> 导出路由与菜单；见指南 §8。</li>
            <li><code class="mono">hooks</code> / <code class="mono">comms.exports</code> / <code class="mono">workflow_employees</code> / <code class="mono">bundle</code> 见指南 §9–§11、§14。</li>
          </ul>
        </details>

        <h3 class="sub-title">本包结构检查</h3>
        <ul class="checklist">
          <li v-for="row in checklist" :key="row.key" :class="{ ok: row.ok, warn: !row.ok }">
            <span class="mark">{{ row.ok ? '✓' : '○' }}</span>
            {{ row.label }}
            <span v-if="row.hint" class="hint">{{ row.hint }}</span>
          </li>
        </ul>

        <div v-if="artifactNote" class="artifact-note">{{ artifactNote }}</div>
      </section>

      <!-- manifest -->
      <section v-show="tab === 'manifest'" class="panel">
        <div class="panel-actions">
          <button type="button" class="btn btn-primary" :disabled="savingManifest" @click="saveManifest">
            {{ savingManifest ? '保存中…' : '保存 manifest' }}
          </button>
          <button type="button" class="btn" :disabled="loading" @click="reload">重新加载</button>
        </div>
        <p v-if="manifestSaveWarnings.length" class="warn-block">
          保存后提示：<span v-for="(w, i) in manifestSaveWarnings" :key="i">{{ w }}<br v-if="i < manifestSaveWarnings.length - 1" /></span>
        </p>
        <textarea v-model="manifestText" class="code-area" spellcheck="false" />
      </section>

      <!-- 文件 -->
      <section v-show="tab === 'files'" class="panel">
        <div class="file-toolbar">
          <label class="label-inline">文件</label>
          <select v-model="selectedPath" class="select" @change="onPathSelect">
            <option value="">选择路径…</option>
            <option v-for="p in sortedFiles" :key="p" :value="p">{{ p }}</option>
          </select>
          <button type="button" class="btn" :disabled="!selectedPath || loadingFile" @click="loadSelectedFile">
            读取
          </button>
          <button type="button" class="btn btn-primary" :disabled="!selectedPath || savingFile" @click="saveFile">
            {{ savingFile ? '保存中…' : '保存文件' }}
          </button>
        </div>
        <p v-if="fileWarnings.length" class="warn-block">
          manifest 相关提示：<span v-for="(w, i) in fileWarnings" :key="i">{{ w }}<br v-if="i < fileWarnings.length - 1" /></span>
        </p>
        <textarea
          v-model="fileContent"
          class="code-area"
          spellcheck="false"
          :placeholder="selectedPath ? '' : '请选择文件并点击「读取」'"
        />
      </section>

      <!-- manifest 快照与 semver -->
      <section v-show="tab === 'snapshots'" class="panel">
        <p class="muted small snap-lead">
          每次<strong>保存 manifest</strong>前会自动写入一条「保存前」快照（可在此恢复）。也可手动创建快照；「patch +1」会按 semver 递增
          <code class="mono">manifest.version</code> 并写回磁盘。
        </p>
        <div class="snap-toolbar">
          <input
            v-model="snapshotLabelDraft"
            type="text"
            class="input snap-label-input"
            maxlength="240"
            placeholder="快照说明（可选）"
          >
          <button type="button" class="btn btn-primary" :disabled="snapshotBusy" @click="() => void captureSnapshotManual()">
            {{ snapshotBusy ? '处理中…' : '创建快照' }}
          </button>
          <button type="button" class="btn" :disabled="snapshotBusy" @click="() => void refreshSnapshots()">
            刷新列表
          </button>
          <button type="button" class="btn" :disabled="snapshotBusy" @click="() => void bumpManifestPatch()">
            {{ snapshotBusy ? '处理中…' : 'manifest 版本 patch+1' }}
          </button>
        </div>
        <p v-if="snapshotsLoadErr" class="flash flash-err">{{ snapshotsLoadErr }}</p>
        <ul v-if="snapshotsRows.length" class="snap-list">
          <li v-for="s in snapshotsRows" :key="s.snap_id" class="snap-li">
            <code class="mono">{{ s.snap_id }}</code>
            <span class="muted small">{{ formatSnapTime(s.created_at) }}</span>
            <span v-if="s.label" class="snap-label">{{ s.label }}</span>
            <button type="button" class="btn btn-sm btn-ghost" :disabled="snapshotBusy" @click="() => void restoreSnapshot(s.snap_id)">
              恢复
            </button>
          </li>
        </ul>
        <p v-else class="muted small">暂无快照；保存 manifest 或点「创建快照」后会出现列表。</p>
      </section>

      <!-- 扫描与诊断 -->
      <section v-show="tab === 'scan'" class="panel">
        <div class="panel-actions">
          <button type="button" class="btn" :disabled="loadingSummary" @click="refreshSummary">
            {{ loadingSummary ? '刷新中…' : '刷新扫描' }}
          </button>
        </div>
        <template v-if="summary">
          <p class="small">
            蓝图文件：
            <code v-if="summary.blueprint_file" class="mono">{{ summary.blueprint_file }}</code>
            <span v-else class="muted">未找到 backend/blueprints.py 或根目录 blueprints.py</span>
          </p>
          <p v-if="summary.validation_ok === false && summary.warnings?.length" class="warn-block">
            <span v-for="(w, i) in summary.warnings" :key="i">{{ w }}<br /></span>
          </p>
          <p v-else-if="summary.validation_ok" class="ok-line">当前 manifest 校验无警告。</p>

          <div v-if="summary.blueprint_routes?.length" class="table-wrap">
            <table class="routes-table">
              <thead>
                <tr>
                  <th>方法</th>
                  <th>路径</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(r, idx) in summary.blueprint_routes" :key="idx">
                  <td class="mono">{{ (r.methods || []).join(', ') }}</td>
                  <td class="mono">{{ r.path }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <p v-else class="muted small">未扫描到 FastAPI APIRouter 路由装饰器，或蓝图文件不存在。</p>
        </template>
      </section>
    </template>

    <!-- 员工名片 添加/编辑 -->
    <div v-if="empModalOpen" class="modal-overlay" @click.self="closeEmployeeModal">
      <div class="modal modal-wide">
        <h2 class="modal-title">
          {{ empScaffoldDone ? '已生成占位文件' : empModalMode === 'add' ? '添加员工名片' : '编辑员工名片' }}
        </h2>
        <p v-if="empModalMode === 'add' && !empScaffoldDone" class="modal-hint">
          内部 ID 创建后如需与代码对应，请使用小写字母开头，仅含字母、数字、下划线、连字符。
        </p>
        <div v-if="!empScaffoldDone" class="form-grid">
          <div class="form-group">
            <label class="label">显示名（label）</label>
            <input v-model="empDraft.label" class="input" maxlength="256" placeholder="例如：微信电话业务员" />
          </div>
          <div class="form-group">
            <label class="label">内部 ID（id）{{ empModalMode === 'edit' ? '（保存后勿随意改，以免与代码不一致）' : '' }}</label>
            <input
              v-model="empDraft.id"
              class="input mono"
              maxlength="64"
              :disabled="empModalMode === 'edit'"
              placeholder="例如：wechat_phone"
            />
          </div>
          <div class="form-group full-width">
            <label class="label">一句话介绍（panel_title）</label>
            <input v-model="empDraft.panel_title" class="input" maxlength="256" placeholder="可选，列表副标题" />
          </div>
          <div class="form-group full-width">
            <label class="label">给用户看的说明（panel_summary）</label>
            <textarea v-model="empDraft.panel_summary" class="input textarea" rows="5" maxlength="8000" placeholder="用白话写清楚能做什么、不能做什么" />
          </div>
          <label v-if="empModalMode === 'add'" class="checkbox-line full-width">
            <input v-model="empScaffoldRouter" type="checkbox" />
            同时生成后端占位接口（仅适合<strong>标准骨架</strong> Mod；复杂 Mod 会提示手动合并 blueprints）
          </label>
        </div>
        <p v-if="empModalError" class="flash flash-err">{{ empModalError }}</p>
        <div v-if="empModalMergeHint" class="merge-hint-block">
          <span class="merge-hint-label">合并说明</span>
          <pre class="merge-hint-pre">{{ empModalMergeHint }}</pre>
          <button type="button" class="btn btn-sm" @click="copyMergeHint">复制合并说明</button>
        </div>
        <div class="modal-actions">
          <button type="button" class="btn" @click="closeEmployeeModal">{{ empScaffoldDone ? '关闭' : '取消' }}</button>
          <button
            v-if="!empScaffoldDone"
            type="button"
            class="btn btn-primary"
            :disabled="empModalSaving"
            @click="submitEmployeeModal"
          >
            {{ empModalSaving ? '保存中…' : '保存' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, reactive } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '../api'

const route = useRoute()
const router = useRouter()

const tabs = [
  { id: 'guide', label: '概览与清单' },
  { id: 'manifest', label: '配置 (JSON)' },
  { id: 'files', label: '编辑文件' },
  { id: 'snapshots', label: '版本与快照' },
  { id: 'scan', label: '路由扫描' },
]

const WORKFLOW_SUMMARY_MAX = 280

function truncatePlain(s, max) {
  const t = String(s || '')
    .replace(/\s+/g, ' ')
    .trim()
  if (t.length <= max) return t
  return `${t.slice(0, max)}…`
}

const modDescriptionLine = computed(() => {
  const d = modData.value?.manifest?.description
  return typeof d === 'string' && d.trim() ? d.trim() : ''
})

const workflowEmployeesRows = computed(() => {
  const raw = modData.value?.manifest?.workflow_employees
  if (!Array.isArray(raw)) return []
  return raw.map((item, index) => {
    const o = item && typeof item === 'object' ? item : {}
    const id = typeof o.id === 'string' ? o.id.trim() : ''
    const label = typeof o.label === 'string' ? o.label.trim() : ''
    const panelTitle = typeof o.panel_title === 'string' ? o.panel_title.trim() : ''
    const summary = typeof o.panel_summary === 'string' ? o.panel_summary.trim() : ''
    const title = label || panelTitle || id || `员工 ${index + 1}`
    const bodyFull = summary
    const bodyShort = bodyFull ? truncatePlain(bodyFull, WORKFLOW_SUMMARY_MAX) : ''
    const widRaw = o.workflow_id ?? o.workflowId
    const linkedWorkflowId =
      widRaw == null || widRaw === ''
        ? 0
        : (() => {
            const n = parseInt(String(widRaw), 10)
            return Number.isFinite(n) && n > 0 ? n : 0
          })()
    return {
      index,
      raw: { ...o },
      id,
      label,
      panelTitle,
      title,
      bodyFull,
      bodyShort,
      isEmpty: !id && !label && !panelTitle,
      linkedWorkflowId,
    }
  })
})

const tab = ref('guide')
const loading = ref(true)
const loadError = ref('')
const modData = ref(null)
const summary = ref(null)
const manifestText = ref('')
const manifestSaveWarnings = ref([])
const message = ref('')
const messageOk = ref(true)
const savingManifest = ref(false)
const selectedPath = ref('')
const fileContent = ref('')
const loadingFile = ref(false)
const savingFile = ref(false)
const fileWarnings = ref([])
const loadingSummary = ref(false)

const snapshotsRows = ref([])
const snapshotsLoadErr = ref('')
const snapshotBusy = ref(false)
const snapshotLabelDraft = ref('')

const modId = computed(() => String(route.params.modId || ''))

const PREFILL_KEY = 'modstore_employee_prefill'

const linkableWorkflows = ref([])
const linkPick = reactive({})
const linkWorkflowBusy = ref(false)
/** workflow_employees 行 index，一键登记 API 进行中 */
const registerCatalogBusy = ref(-1)

const empModalOpen = ref(false)
const empModalMode = ref('add')
const empEditIndex = ref(-1)
const empDraft = ref({ id: '', label: '', panel_title: '', panel_summary: '' })
const empScaffoldRouter = ref(false)
const empModalSaving = ref(false)
const empModalError = ref('')
const empModalMergeHint = ref('')
const empScaffoldDone = ref(false)

const EMP_ID_RE = /^[a-z][a-z0-9_-]{0,63}$/

async function registerWorkflowEmployeeCatalog(row) {
  if (!localStorage.getItem('modstore_token')) {
    flash('请先登录工作台后再一键登记', false)
    return
  }
  registerCatalogBusy.value = row.index
  try {
    const res = await api.registerWorkflowEmployeeCatalog(modId.value, row.index)
    const pkg = res?.package
    const pid = pkg?.id || ''
    const ver = pkg?.version || ''
    flash(
      pid && ver ? `已登记到本地仓库：${pid} @ ${ver}` : '已登记到本地仓库（/v1/packages）',
      true,
    )
  } catch (e) {
    flash(e?.message || String(e), false)
  } finally {
    registerCatalogBusy.value = -1
  }
}

function goEmployeePrefill(row) {
  const mid = modId.value
  const wi = row.index
  const desc = row.bodyFull
    ? `声明摘要：${row.bodyFull}\n来源 Mod：${mid}（workflow_employees[${wi}]）。已带入员工制作页预填；也可在本页点「一键登记」写入 /v1/packages，或完成向导后手动登记。`
    : `来自 Mod「${mid}」的 workflow_employees[${wi}]（ID：${row.id || '—'}）。已带入员工制作页预填；也可点「一键登记」或完成向导后登记。`
  try {
    sessionStorage.setItem(
      PREFILL_KEY,
      JSON.stringify({
        modId: mid,
        workflowIndex: wi,
        workflowEmployee: row.raw && typeof row.raw === 'object' ? row.raw : {},
        name: String(row.title || '员工').slice(0, 200),
        description: desc.slice(0, 4000),
      }),
    )
  } catch {
    /* ignore */
  }
  router.push({ name: 'workbench-employee' })
}

function getWorkflowEmployeesArray() {
  const m = modData.value?.manifest
  const raw = m?.workflow_employees
  if (!Array.isArray(raw)) return []
  return raw.map((x) => (x && typeof x === 'object' ? { ...x } : {}))
}

function openEmployeeModal(mode, index = -1) {
  empModalMode.value = mode
  empModalError.value = ''
  empModalMergeHint.value = ''
  empScaffoldDone.value = false
  empScaffoldRouter.value = false
  if (mode === 'add') {
    empEditIndex.value = -1
    empDraft.value = { id: '', label: '', panel_title: '', panel_summary: '' }
  } else {
    empEditIndex.value = index
    const row = workflowEmployeesRows.value.find((r) => r.index === index)
    const o = row?.raw || {}
    empDraft.value = {
      id: typeof o.id === 'string' ? o.id : '',
      label: typeof o.label === 'string' ? o.label : '',
      panel_title: typeof o.panel_title === 'string' ? o.panel_title : '',
      panel_summary: typeof o.panel_summary === 'string' ? o.panel_summary : '',
    }
  }
  empModalOpen.value = true
}

function closeEmployeeModal() {
  empModalOpen.value = false
  empModalError.value = ''
  empModalMergeHint.value = ''
  empScaffoldDone.value = false
}

async function persistWorkflowEmployees(nextList) {
  const parsed = JSON.parse(JSON.stringify(modData.value.manifest || {}))
  parsed.workflow_employees = nextList
  await api.putModManifest(modId.value, parsed)
  manifestSaveWarnings.value = []
  flash('员工名片已保存')
  await reload()
}

function copyMergeHint() {
  if (!empModalMergeHint.value) return
  navigator.clipboard?.writeText(empModalMergeHint.value).then(
    () => flash('已复制到剪贴板', true),
    () => flash('复制失败', false),
  )
}

async function submitEmployeeModal() {
  empModalError.value = ''
  empModalMergeHint.value = ''
  const id = empDraft.value.id.trim()
  const label = empDraft.value.label.trim()
  const panel_title = empDraft.value.panel_title.trim()
  const panel_summary = empDraft.value.panel_summary.trim()
  if (!label) {
    empModalError.value = '请填写显示名（label）'
    return
  }
  if (empModalMode.value === 'add' && !id) {
    empModalError.value = '请填写内部 ID（id）'
    return
  }
  if (empModalMode.value === 'add' && !EMP_ID_RE.test(id)) {
    empModalError.value = '内部 ID 须小写字母开头，仅含小写字母、数字、下划线、连字符（1–64 字符）'
    return
  }
  const wf = getWorkflowEmployeesArray()
  if (empModalMode.value === 'add') {
    if (wf.some((x) => String(x.id || '').trim() === id)) {
      empModalError.value = '该内部 ID 已存在'
      return
    }
  }
  empModalSaving.value = true
  try {
    if (empModalMode.value === 'add' && empScaffoldRouter.value) {
      const res = await api.scaffoldWorkflowEmployee(modId.value, {
        id,
        label,
        panel_title,
        panel_summary,
        template: 'skeleton_router',
        force_auto_merge: false,
      })
      await reload()
      if (res.merge_hint) {
        empModalMergeHint.value = String(res.merge_hint)
        empScaffoldDone.value = true
        flash(
          res.merged_blueprint
            ? '已添加员工；已尝试合并 blueprints。请查看下方合并说明，可复制给开发者。'
            : '已添加员工与占位文件；请按下方说明手动合并 blueprints。',
          true,
        )
      } else {
        flash('已添加员工并生成占位路由', true)
        closeEmployeeModal()
      }
      return
    }
    const entry = { id, label, panel_title, panel_summary }
    if (empModalMode.value === 'add') {
      wf.push(entry)
    } else {
      const idx = empEditIndex.value
      if (idx < 0 || idx >= wf.length) {
        empModalError.value = '索引无效'
        return
      }
      const prev = wf[idx] || {}
      wf[idx] = { ...prev, ...entry, id: typeof prev.id === 'string' && prev.id ? prev.id : id }
    }
    await persistWorkflowEmployees(wf)
    closeEmployeeModal()
  } catch (e) {
    empModalError.value = e.message || String(e)
  } finally {
    empModalSaving.value = false
  }
}

async function confirmDeleteEmployee(index) {
  const wf = getWorkflowEmployeesArray()
  if (index < 0 || index >= wf.length) return
  const row = wf[index]
  const name = (row && row.label) || row?.id || `第 ${index + 1} 条`
  if (!window.confirm(`确定从 manifest 中删除员工「${name}」？（不会删除已生成的 Python 文件）`)) return
  wf.splice(index, 1)
  empModalSaving.value = true
  try {
    await persistWorkflowEmployees(wf)
  } catch (e) {
    flash(e.message || String(e), false)
  } finally {
    empModalSaving.value = false
  }
}

function normPath(p) {
  return String(p || '').replace(/\\/g, '/').replace(/^\//, '')
}

const fileSet = computed(() => {
  const files = modData.value?.files
  if (!Array.isArray(files)) return new Set()
  return new Set(files.map((f) => normPath(f)))
})

const scaffoldEnvHint = computed(() => {
  if (!fileSet.value.has('backend/blueprints.py')) return ''
  return '提示：若本 Mod 的 blueprints 含大量自定义逻辑，「自动生成占位接口」只会写入文件并给出合并说明，不会强行改你的代码。'
})

const sortedFiles = computed(() => {
  const files = modData.value?.files
  if (!Array.isArray(files)) return []
  return [...files].map(normPath).sort((a, b) => a.localeCompare(b))
})

const backendEntryRel = computed(() => {
  const m = modData.value?.manifest
  const entry = typeof m?.backend?.entry === 'string' ? m.backend.entry : 'blueprints'
  const stem = entry.replace(/\.py$/i, '')
  return `backend/${stem}.py`
})

const checklist = computed(() => {
  const fs = fileSet.value
  const entryPath = backendEntryRel.value
  const rows = [
    {
      key: 'manifest',
      label: '扩展说明文件 manifest.json 已就绪',
      ok: fs.has('manifest.json'),
    },
    {
      key: 'init',
      label: '后端 Python 包已初始化',
      ok: fs.has('backend/__init__.py'),
      hint: '缺少 backend/__init__.py 时，同包内相对 import 可能失败',
    },
    {
      key: 'entry',
      label: '后端入口文件已就位',
      ok: fs.has(entryPath),
      hint: `须存在 ${entryPath}（由 manifest.backend.entry 决定）`,
    },
    {
      key: 'routes',
      label: '前端路由表已就位',
      ok: fs.has('frontend/routes.js'),
      hint: '通常为 frontend/routes.js',
    },
  ]
  return rows
})

const artifactNote = computed(() => {
  const art = modData.value?.manifest?.artifact || modData.value?.manifest?.kind
  if (art === 'employee_pack') {
    return '当前 artifact 为 employee_pack：通常仅声明 workflow_employee，不带路由与前端菜单。'
  }
  if (art === 'bundle') {
    return '当前 artifact 为 bundle：元包组合安装，本体多为 manifest + bundle 字段，一般不含业务代码。'
  }
  return ''
})

function flash(msg, ok = true) {
  message.value = msg
  messageOk.value = ok
  setTimeout(() => {
    message.value = ''
  }, 5000)
}

function openWorkflowSandboxDecompose(row) {
  const wid = row.linkedWorkflowId
  if (!wid) {
    flash('当前员工条目未声明 workflow_id，请先在 manifest 中关联 MODstore 工作流', false)
    return
  }
  router.push({ name: 'workbench-workflow', query: { edit: String(wid), tab: 'sandbox' } })
}

async function loadLinkableWorkflows() {
  try {
    linkableWorkflows.value = (await api.listWorkflows()) || []
  } catch {
    linkableWorkflows.value = []
  }
}

async function applyWorkflowLinkToRow(row) {
  const wid = Number(linkPick[row.index])
  if (!modId.value || !Number.isFinite(wid) || wid <= 0) {
    flash('请在下拉框中选择一个工作流', false)
    return
  }
  linkWorkflowBusy.value = true
  try {
    const res = await api.modWorkflowLink(modId.value, {
      workflow_id: wid,
      workflow_index: row.index,
    })
    const mw = Array.isArray(res?.manifest_warnings) ? res.manifest_warnings : []
    if (mw.length) manifestSaveWarnings.value = mw
    flash('已写入 workflow_id，可点「拆解与沙盒测试」', true)
    await reload()
  } catch (e) {
    flash(e.message || String(e), false)
  } finally {
    linkWorkflowBusy.value = false
  }
}

function formatSnapTime(ts) {
  const n = Number(ts)
  if (!Number.isFinite(n) || n <= 0) return '—'
  try {
    return new Date(n * 1000).toLocaleString()
  } catch {
    return String(ts)
  }
}

async function refreshSnapshots() {
  if (!modId.value) return
  snapshotsLoadErr.value = ''
  try {
    const res = await api.listModSnapshots(modId.value)
    const rows = Array.isArray(res?.snapshots) ? res.snapshots : Array.isArray(res) ? res : []
    snapshotsRows.value = rows
  } catch (e) {
    snapshotsRows.value = []
    snapshotsLoadErr.value = e.message || String(e)
  }
}

async function captureSnapshotManual() {
  if (!modId.value) return
  snapshotBusy.value = true
  try {
    await api.captureModSnapshot(modId.value, snapshotLabelDraft.value.trim())
    snapshotLabelDraft.value = ''
    flash('已创建快照', true)
    await refreshSnapshots()
  } catch (e) {
    flash(e.message || String(e), false)
  } finally {
    snapshotBusy.value = false
  }
}

async function restoreSnapshot(snapId) {
  if (!modId.value || !snapId) return
  if (!window.confirm('将用该快照覆盖当前 manifest.json，确定继续？')) return
  snapshotBusy.value = true
  try {
    await api.restoreModSnapshot(modId.value, snapId)
    flash('已从快照恢复 manifest', true)
    await reload()
    await refreshSnapshots()
  } catch (e) {
    flash(e.message || String(e), false)
  } finally {
    snapshotBusy.value = false
  }
}

async function bumpManifestPatch() {
  if (!modId.value) return
  snapshotBusy.value = true
  try {
    const res = await api.bumpModManifestPatchVersion(modId.value)
    const w = Array.isArray(res?.warnings) ? res.warnings : []
    if (w.length) manifestSaveWarnings.value = w
    flash(`manifest 版本已更新为 ${res?.manifest?.version || '新版本'}`, true)
    await reload()
    await refreshSnapshots()
  } catch (e) {
    flash(e.message || String(e), false)
  } finally {
    snapshotBusy.value = false
  }
}

function goRepo() {
  router.push({ name: 'workbench-repository' })
}

async function refreshSummary() {
  if (!modId.value) return
  loadingSummary.value = true
  try {
    summary.value = await api.getModAuthoringSummary(modId.value)
  } catch (e) {
    flash(e.message || String(e), false)
  } finally {
    loadingSummary.value = false
  }
}

async function reload() {
  loadError.value = ''
  loading.value = true
  manifestSaveWarnings.value = []
  fileWarnings.value = []
  try {
    const [detail, sum] = await Promise.all([
      api.getMod(modId.value),
      api.getModAuthoringSummary(modId.value).catch(() => null),
    ])
    modData.value = detail
    summary.value = sum
    manifestText.value = JSON.stringify(detail.manifest || {}, null, 2)
    void loadLinkableWorkflows()
    void refreshSnapshots()
    if (!selectedPath.value || !fileSet.value.has(normPath(selectedPath.value))) {
      selectedPath.value = ''
      fileContent.value = ''
    }
  } catch (e) {
    modData.value = null
    summary.value = null
    loadError.value = e.message || String(e)
  } finally {
    loading.value = false
  }
}

async function saveManifest() {
  let parsed
  try {
    parsed = JSON.parse(manifestText.value)
  } catch (e) {
    flash('JSON 解析失败: ' + (e.message || String(e)), false)
    return
  }
  savingManifest.value = true
  manifestSaveWarnings.value = []
  try {
    try {
      await api.captureModSnapshot(modId.value, `保存前 ${new Date().toISOString().slice(0, 19)}`)
    } catch {
      /* 快照失败不阻断保存 */
    }
    const res = await api.putModManifest(modId.value, parsed)
    manifestSaveWarnings.value = Array.isArray(res.warnings) ? res.warnings : []
    flash('manifest 已保存')
    await reload()
  } catch (e) {
    flash(e.message || String(e), false)
  } finally {
    savingManifest.value = false
  }
}

async function loadSelectedFile() {
  const p = normPath(selectedPath.value)
  if (!p) return
  loadingFile.value = true
  fileWarnings.value = []
  try {
    const res = await api.getModFile(modId.value, p)
    fileContent.value = res.content ?? ''
  } catch (e) {
    flash(e.message || String(e), false)
  } finally {
    loadingFile.value = false
  }
}

function onPathSelect() {
  fileContent.value = ''
  fileWarnings.value = []
}

async function saveFile() {
  const p = normPath(selectedPath.value)
  if (!p) return
  savingFile.value = true
  fileWarnings.value = []
  try {
    const res = await api.putModFile(modId.value, p, fileContent.value)
    fileWarnings.value = Array.isArray(res.manifest_warnings) ? res.manifest_warnings : []
    flash('文件已保存')
    await reload()
  } catch (e) {
    flash(e.message || String(e), false)
  } finally {
    savingFile.value = false
  }
}

watch(
  modId,
  (id) => {
    if (!id) {
      loadError.value = '缺少 modId'
      loading.value = false
      modData.value = null
      return
    }
    reload()
  },
  { immediate: true },
)

watch(
  () => [String(route.query.mode || '').toLowerCase(), modId.value],
  ([mode]) => {
    if (mode === 'edit' && modId.value) tab.value = 'snapshots'
  },
  { immediate: true },
)
</script>

<style scoped>
.authoring-page {
  width: 100%;
  max-width: var(--layout-max);
  margin: 0 auto;
  padding: var(--page-pad-y) var(--layout-pad-x);
  box-sizing: border-box;
}

.loading {
  text-align: center;
  padding: 3rem;
  color: rgba(255, 255, 255, 0.35);
}

.page-header {
  margin-bottom: 1.25rem;
}

.header-top {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-bottom: 0.75rem;
}

.page-title {
  font-size: 1.5rem;
  margin: 0 0 0.25rem;
  color: #fff;
}

.page-sub {
  margin: 0;
  font-size: 0.875rem;
  color: rgba(255, 255, 255, 0.45);
}

.mono {
  font-family: ui-monospace, monospace;
  font-size: 0.85em;
}

.muted {
  color: rgba(255, 255, 255, 0.4);
}

.small {
  font-size: 0.8125rem;
}

.flash {
  padding: 10px 16px;
  border-radius: 8px;
  margin-bottom: 16px;
  font-size: 14px;
}

.flash-ok {
  background: rgba(74, 222, 128, 0.1);
  color: #4ade80;
}

.flash-err {
  background: rgba(255, 80, 80, 0.1);
  color: #ff6b6b;
}

.tabs {
  display: flex;
  gap: 0.25rem;
  flex-wrap: wrap;
  margin-bottom: 1rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  padding-bottom: 0.5rem;
}

.tab {
  padding: 0.45rem 0.85rem;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: rgba(255, 255, 255, 0.45);
  font-size: 0.875rem;
  cursor: pointer;
}

.tab:hover {
  color: rgba(255, 255, 255, 0.75);
  background: rgba(255, 255, 255, 0.05);
}

.tab.active {
  color: #fff;
  background: rgba(255, 255, 255, 0.08);
}

.panel {
  background: #111;
  border: 0.5px solid rgba(255, 255, 255, 0.1);
  border-radius: 12px;
  padding: 1.25rem;
}

.panel-err {
  color: #ff6b6b;
}

.panel-title {
  font-size: 1.05rem;
  margin: 0 0 0.5rem;
  color: #fff;
}

.overview-lead {
  margin: 0.35rem 0 0;
  font-size: 0.9rem;
  color: rgba(255, 255, 255, 0.82);
}

.overview-desc {
  margin: 0.5rem 0 0;
  line-height: 1.55;
  color: rgba(255, 255, 255, 0.72);
  font-size: 0.9rem;
}

.emp-empty {
  margin: 0.35rem 0 0;
}

.emp-cards {
  display: grid;
  gap: 0.65rem;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  margin: 0.5rem 0 0;
}

.emp-card {
  padding: 0.85rem 1rem;
  border-radius: 10px;
  border: 0.5px solid rgba(255, 255, 255, 0.1);
  background: rgba(255, 255, 255, 0.04);
}

.emp-card-title {
  margin: 0 0 0.35rem;
  font-size: 0.95rem;
  font-weight: 600;
  color: #f4f4f5;
}

.emp-card-id {
  margin: 0 0 0.45rem;
  font-size: 0.75rem;
  color: rgba(255, 255, 255, 0.45);
}

.emp-card-body {
  margin: 0;
  font-size: 0.82rem;
  line-height: 1.45;
  color: rgba(255, 255, 255, 0.68);
  white-space: pre-wrap;
  word-break: break-word;
}

.emp-sync-btn {
  margin-top: 0.65rem;
}

.dev-details {
  margin-top: 1.35rem;
  padding: 0.65rem 0.85rem;
  border-radius: 10px;
  border: 0.5px solid rgba(255, 255, 255, 0.08);
  background: rgba(0, 0, 0, 0.2);
}

.dev-details-summary {
  cursor: pointer;
  font-size: 0.88rem;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.75);
  user-select: none;
}

.dev-details-summary:hover {
  color: #fff;
}

.dev-details-lead {
  margin: 0.65rem 0 0.35rem;
}

.dev-details .guide-list {
  margin-top: 0.35rem;
}

.sub-title {
  font-size: 0.95rem;
  margin: 1.25rem 0 0.5rem;
  color: rgba(255, 255, 255, 0.85);
}

.panel-actions {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
  margin-bottom: 0.75rem;
}

.snap-lead {
  margin: 0 0 1rem;
  line-height: 1.55;
}

.snap-toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 1rem;
}

.snap-label-input {
  flex: 1 1 12rem;
  min-width: 10rem;
}

.snap-list {
  list-style: none;
  padding: 0;
  margin: 0.5rem 0 0;
}

.snap-li {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.5rem 0.75rem;
  padding: 0.5rem 0;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  font-size: 0.875rem;
}

.snap-li:last-child {
  border-bottom: none;
}

.snap-label {
  color: rgba(255, 255, 255, 0.55);
  font-size: 0.8125rem;
}

.guide-list {
  margin: 0.75rem 0 0;
  padding-left: 1.2rem;
  color: rgba(255, 255, 255, 0.65);
  line-height: 1.6;
  font-size: 0.875rem;
}

.guide-list li {
  margin-bottom: 0.35rem;
}

.checklist {
  list-style: none;
  padding: 0;
  margin: 0.5rem 0 0;
}

.checklist li {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 0.35rem;
  padding: 0.35rem 0;
  font-size: 0.875rem;
  color: rgba(255, 255, 255, 0.55);
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

.checklist li.ok {
  color: rgba(74, 222, 128, 0.85);
}

.checklist li.warn {
  color: rgba(251, 191, 36, 0.9);
}

.mark {
  width: 1.25rem;
  flex-shrink: 0;
}

.hint {
  width: 100%;
  font-size: 0.75rem;
  color: rgba(255, 255, 255, 0.35);
}

.artifact-note {
  margin-top: 1rem;
  padding: 0.75rem;
  border-radius: 8px;
  background: rgba(96, 165, 250, 0.08);
  color: rgba(147, 197, 253, 0.95);
  font-size: 0.8125rem;
  line-height: 1.5;
}

.warn-block {
  font-size: 0.8125rem;
  color: #fbbf24;
  margin: 0 0 0.75rem;
}

.ok-line {
  font-size: 0.875rem;
  color: #4ade80;
  margin: 0 0 0.75rem;
}

.code-area {
  width: 100%;
  min-height: 420px;
  box-sizing: border-box;
  padding: 0.75rem;
  border: 0.5px solid rgba(255, 255, 255, 0.12);
  border-radius: 8px;
  background: rgba(0, 0, 0, 0.35);
  color: rgba(255, 255, 255, 0.88);
  font-family: ui-monospace, monospace;
  font-size: 0.8rem;
  line-height: 1.45;
  resize: vertical;
  outline: none;
}

.code-area:focus {
  border-color: rgba(255, 255, 255, 0.25);
}

.file-toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.75rem;
}

.label-inline {
  font-size: 0.8rem;
  color: rgba(255, 255, 255, 0.45);
}

.select {
  flex: 1;
  min-width: 200px;
  max-width: 100%;
  padding: 0.45rem 0.6rem;
  border-radius: 6px;
  border: 0.5px solid rgba(255, 255, 255, 0.15);
  background: rgba(255, 255, 255, 0.04);
  color: #fff;
  font-size: 0.85rem;
}

.table-wrap {
  overflow-x: auto;
  margin-top: 0.75rem;
}

.routes-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.8125rem;
}

.routes-table th,
.routes-table td {
  text-align: left;
  padding: 0.4rem 0.5rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.routes-table th {
  color: rgba(255, 255, 255, 0.45);
  font-weight: 500;
}

.badge {
  display: inline-flex;
  align-items: center;
  padding: 0.2rem 0.5rem;
  border-radius: 4px;
  font-size: 0.6875rem;
  font-weight: 500;
}

.badge-ok {
  background: rgba(74, 222, 128, 0.12);
  color: #4ade80;
}

.badge-warn {
  background: rgba(251, 191, 36, 0.12);
  color: #fbbf24;
}

.btn {
  padding: 0.45rem 0.9rem;
  border: 0.5px solid rgba(255, 255, 255, 0.15);
  border-radius: 6px;
  background: transparent;
  color: rgba(255, 255, 255, 0.75);
  font-size: 0.8125rem;
  cursor: pointer;
}

.btn:hover:not(:disabled) {
  background: rgba(255, 255, 255, 0.06);
  color: #fff;
}

.btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.btn-primary {
  background: #fff;
  color: #0a0a0a;
  border-color: transparent;
}

.btn-ghost {
  border-color: transparent;
  padding-left: 0;
}

.btn-sm {
  padding: 0.3rem 0.55rem;
  font-size: 0.78rem;
}

.btn-ghost.danger {
  color: #f87171;
}

.btn-ghost.danger:hover {
  color: #fca5a5;
}

.emp-intro {
  margin: 0.35rem 0 0.5rem;
  font-size: 0.84rem;
  line-height: 1.55;
  color: rgba(255, 255, 255, 0.62);
}

.emp-env-hint {
  margin: 0 0 0.5rem;
}

.emp-toolbar {
  margin: 0.5rem 0 0.75rem;
}

.linkish {
  border: none;
  background: none;
  color: #93c5fd;
  cursor: pointer;
  text-decoration: underline;
  padding: 0;
  font: inherit;
}

.linkish:hover {
  color: #bfdbfe;
}

.emp-table-wrap {
  overflow-x: auto;
  margin-top: 0.35rem;
  border-radius: 10px;
  border: 0.5px solid rgba(255, 255, 255, 0.1);
}

.emp-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.82rem;
}

.emp-table th,
.emp-table td {
  padding: 0.55rem 0.65rem;
  text-align: left;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  vertical-align: top;
  color: rgba(255, 255, 255, 0.78);
}

.emp-table th {
  color: rgba(255, 255, 255, 0.45);
  font-weight: 600;
  font-size: 0.75rem;
}

.emp-th-actions {
  width: 1%;
  white-space: nowrap;
}

.emp-th-link {
  min-width: 11rem;
  font-size: 0.75rem;
}

.emp-link-cell {
  min-width: 10rem;
}

.wf-link-inline {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  align-items: stretch;
}

.wf-link-select {
  max-width: 16rem;
  font-size: 0.78rem;
}

.emp-summary-cell {
  max-width: 22rem;
}

.emp-actions-cell {
  white-space: nowrap;
}

.emp-actions-cell .btn {
  margin-right: 0.25rem;
}

.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.55);
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding: 2rem 1rem;
  z-index: 80;
  overflow-y: auto;
}

.modal {
  background: #141414;
  border: 0.5px solid rgba(255, 255, 255, 0.12);
  border-radius: 12px;
  padding: 1.25rem 1.35rem;
  max-width: 36rem;
  width: 100%;
  margin-top: 2vh;
}

.modal-wide {
  max-width: 40rem;
}

.modal-title {
  margin: 0 0 0.5rem;
  font-size: 1.1rem;
  color: #fff;
}

.modal-hint {
  font-size: 0.8rem;
  color: rgba(255, 255, 255, 0.45);
  margin: 0 0 1rem;
  line-height: 1.45;
}

.form-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.75rem 1rem;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.form-group.full-width {
  grid-column: 1 / -1;
}

.label {
  font-size: 0.78rem;
  color: rgba(255, 255, 255, 0.55);
}

.input {
  padding: 0.45rem 0.65rem;
  border-radius: 8px;
  border: 0.5px solid rgba(255, 255, 255, 0.12);
  background: rgba(255, 255, 255, 0.04);
  color: #fff;
  font-size: 0.875rem;
}

.input.textarea {
  resize: vertical;
  min-height: 6rem;
  font-family: inherit;
}

.checkbox-line {
  display: flex;
  align-items: flex-start;
  gap: 0.5rem;
  font-size: 0.8rem;
  color: rgba(255, 255, 255, 0.65);
  line-height: 1.45;
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
  margin-top: 1rem;
  padding-top: 0.75rem;
  border-top: 0.5px solid rgba(255, 255, 255, 0.08);
}

.merge-hint-block {
  margin-top: 0.75rem;
  padding: 0.65rem 0.75rem;
  border-radius: 8px;
  background: rgba(251, 191, 36, 0.08);
  border: 0.5px solid rgba(251, 191, 36, 0.25);
}

.merge-hint-label {
  display: block;
  font-size: 0.75rem;
  font-weight: 600;
  color: #fbbf24;
  margin-bottom: 0.35rem;
}

.merge-hint-pre {
  margin: 0 0 0.5rem;
  font-size: 0.72rem;
  line-height: 1.45;
  color: rgba(255, 255, 255, 0.75);
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 14rem;
  overflow: auto;
}

@media (max-width: 720px) {
  .form-grid {
    grid-template-columns: 1fr;
  }

  .emp-actions-cell {
    white-space: normal;
  }
}
</style>
