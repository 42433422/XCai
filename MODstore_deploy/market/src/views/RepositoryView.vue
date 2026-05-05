<template>
  <div class="repo-page">
    <div class="page-header">
      <h1 class="page-title">Mod 源码库</h1>
      <p class="page-desc">
        维护 <strong>manifest.json</strong>、backend、frontend 与 AI 生成配置。同步到 XCAGI 不再要求在网页里填写服务器绝对路径：
        用含 <code class="mono">mod:sync</code> 权限的 Developer Token 拉取即可。支持导入标准 <strong>.xcmod</strong>（与 .zip 相同容器），在卡片上点「制作 / 编辑」打开制作页。
      </p>
      <div class="header-actions">
        <button
          type="button"
          class="btn btn-sm btn-danger"
          :disabled="purgeLibraryBusy"
          title="删除当前账号 Mod 源码库中的全部包（需登录），并清除本页提示与「带入员工制作」预填缓存；不可恢复"
          @click="purgeRepoLibraryAndLocalState"
        >
          {{ purgeLibraryBusy ? '清空中…' : '一键清理' }}
        </button>
        <button class="btn btn-primary" @click="showCreate = true">新建 Mod</button>
        <label class="btn">
          导入包（.zip / .xcmod）
          <input type="file" accept=".zip,.xcmod,.xcemp" class="hidden-input" @change="onImport" />
        </label>
        <button
          type="button"
          class="btn btn-secondary"
          title="使用已配置的默认大模型生成 manifest + 脚手架并导入（见 LLM 设置）"
          @click="showScaffold = true"
        >
          AI 生成脚手架
        </button>
      </div>
    </div>

    <div v-if="message" :class="['flash', messageOk ? 'flash-ok' : 'flash-err']">{{ message }}</div>

    <div v-if="loading" class="loading">加载中...</div>
    <div v-else-if="mods.length" class="mods-grid">
      <div v-for="m in mods" :key="m.id" class="mod-card">
        <div class="mod-card-badges">
          <span class="badge badge-artifact" :class="'badge-artifact--' + (m.artifact || 'mod')">{{ artifactLabel(m.artifact) }}</span>
          <span class="badge" :class="m.ok ? 'badge-ok' : 'badge-warn'">{{ m.ok ? '通过' : '待修正' }}</span>
          <span v-if="m.primary" class="badge badge-primary">主扩展</span>
        </div>
        <p v-if="isBundle(m)" class="bundle-hint">组合包：子项见 manifest.bundle</p>
        <h3 class="mod-card-name">{{ m.name || m.id }}</h3>
        <p v-if="getBlurb(m)" class="mod-card-blurb">{{ getBlurb(m) }}</p>
        <div class="mod-card-id">{{ m.id }} · v{{ m.version || '?' }}</div>
        <div v-if="m.warnings?.length" class="mod-card-warn">{{ m.warnings[0] }}{{ m.warnings.length > 1 ? ' …' : '' }}</div>
        <div v-if="m.error" class="mod-card-warn">{{ m.error }}</div>
        <div v-if="m.workflow_employees?.length" class="wf-emp-block">
          <div class="wf-emp-title">manifest 中的工作流声明（workflow_employees）</div>
          <div class="wf-emp-actions">
            <div
              v-for="(e, idx) in m.workflow_employees"
              :key="(e.id || '') + '-' + idx"
              class="wf-emp-line"
            >
              <button
                type="button"
                class="btn btn-sm btn-ghost"
                title="打开员工制作页并预填该条声明（不会自动写入本地包目录）。也可点右侧「一键登记」直接写入 /v1/packages；或完成向导后手动上传登记。"
                @click="goEmployeePrefill(m.id, e, Number(idx))"
              >
                带入员工制作：{{ e.label || e.id || '未命名' }}
              </button>
              <button
                type="button"
                class="btn btn-sm btn-primary"
                :disabled="registerBusy === registerKey(m.id, idx)"
                title="从该条声明生成最小 employee_pack 并通过沙盒审核后写入本地 /v1/packages（需已登录）。与「带入员工制作」二选一或组合使用；同包 id+version 再次登记会覆盖。"
                @click="registerWorkflowToCatalog(m.id, idx)"
              >
                {{ registerBusy === registerKey(m.id, idx) ? '登记中…' : '一键登记' }}
              </button>
            </div>
          </div>
        </div>
        <div class="mod-card-actions">
          <button class="btn btn-sm" @click="viewMod(m.id)">制作 / 编辑</button>
          <button
            type="button"
            class="btn btn-sm btn-secondary"
            title="把该 Mod ID 自动带入沙箱页，并指向线上 FHD 沙盒宿主"
            @click="testModInSandbox(m.id)"
          >
            沙箱测试
          </button>
          <button
            type="button"
            class="btn btn-sm btn-danger"
          :disabled="deleteModBusy === modIdForDeleteApi(m)"
          title="从当前账号的 Mod 库中整包删除（需已登录）；不可恢复"
          @click="deleteModFromLibrary(m)"
        >
          {{ deleteModBusy === modIdForDeleteApi(m) ? '删除中…' : '删除 Mod' }}
          </button>
        </div>
      </div>
    </div>
    <div v-else class="empty-state">
      <p>库中暂无扩展包</p>
      <p class="empty-hint">点击「新建 Mod」或「导入包（.zip / .xcmod）」开始；制作页「指南」Tab 可对照 MOD_AUTHORING_GUIDE.md 自查清单。</p>
    </div>

    <!-- AI 脚手架 -->
    <div v-if="showScaffold" class="modal-overlay" @click.self="showScaffold = false">
      <div class="modal modal-wide">
        <h2 class="modal-title">AI 生成 Mod 脚手架</h2>
        <p class="modal-hint">
          使用你在 LLM 设置中的默认模型与 Key；服务端返回 JSON manifest 后写入模板文件并调用现有导入逻辑。生成后请到制作页核对并补全业务代码。
        </p>
        <div class="form-group">
          <label class="label">自然语言描述</label>
          <textarea
            v-model="scaffoldBrief"
            class="input textarea"
            rows="5"
            placeholder="例如：一个帮助整理会议纪要的小扩展，带一个工作流员工卡片用于摘要"
          />
        </div>
        <div class="form-group">
          <label class="label">希望的 manifest.id（可选）</label>
          <input v-model="scaffoldIdHint" class="input" placeholder="如 my-notes-helper" />
        </div>
        <label class="checkbox-line">
          <input v-model="scaffoldReplace" type="checkbox" />
          若 id 已存在则覆盖导入
        </label>
        <div class="modal-actions">
          <button class="btn" type="button" :disabled="scaffoldBusy" @click="showScaffold = false">取消</button>
          <button class="btn btn-primary" type="button" :disabled="scaffoldBusy" @click="submitScaffold">
            {{ scaffoldBusy ? '生成中…' : '生成并导入' }}
          </button>
        </div>
      </div>
    </div>

    <!-- 新建 Mod 弹窗 -->
    <div v-if="showCreate" class="modal-overlay" @click.self="showCreate = false">
      <div class="modal">
        <h2 class="modal-title">新建 Mod</h2>
        <div class="form-group">
          <label class="label">名称</label>
          <input v-model="createName" class="input" placeholder="用作显示名；目录 id 将自动生成" />
        </div>
        <div class="modal-actions">
          <button class="btn" @click="showCreate = false">取消</button>
          <button class="btn btn-primary" @click="submitCreate">创建</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api'

const router = useRouter()
const mods = ref([])
const loading = ref(true)
const message = ref('')
const messageOk = ref(true)
const showCreate = ref(false)
const createName = ref('')
const showScaffold = ref(false)
const scaffoldBrief = ref('')
const scaffoldIdHint = ref('')
const scaffoldReplace = ref(true)
const scaffoldBusy = ref(false)
/** `${modId}:${workflowIndex}` 登记中 */
const registerBusy = ref('')
/** 正在删除的 manifest.id */
const deleteModBusy = ref('')
/** 一键清理：批量删库进行中 */
const purgeLibraryBusy = ref(false)

const PREFILL_KEY = 'modstore_employee_prefill'

/** 由显示名生成 manifest / 目录 id（与后端 create_mod 约定一致） */
function modIdFromDisplayName(name: string): string {
  const raw = String(name || '')
    .trim()
    .toLowerCase()
  let x = raw.replace(/[^a-z0-9]+/g, '-').replace(/-+/g, '-').replace(/^-|-$/g, '')
  if (!x) {
    x = `mod-${Date.now().toString(36)}`
  }
  if (!/^[a-z]/.test(x)) {
    x = `m-${x.replace(/[^a-z0-9-]/g, '')}`.replace(/-+/g, '-').replace(/^-|-$/g, '')
  }
  if (!x || !/^[a-z]/.test(x)) {
    x = `mod-${Date.now().toString(36)}`
  }
  return x.slice(0, 128)
}

function isCreateModConflictError(e: unknown): boolean {
  const msg = (e as { message?: string })?.message || String(e)
  return msg.includes('已存在') || msg.includes('409') || /FileExistsError/i.test(msg)
}

function flash(msg, ok = true) {
  message.value = msg
  messageOk.value = ok
  setTimeout(() => { message.value = '' }, 5000)
}

/** 磁盘目录末段名（仅用于提示文案；删除 API 须用 manifest id） */
function libraryFolderForDeleteApi(m) {
  if (!m || typeof m !== 'object') return ''
  const rawPath = typeof m.path === 'string' ? m.path.trim() : ''
  if (rawPath) {
    const norm = rawPath.replace(/\\/g, '/').replace(/\/+$/, '')
    const seg = norm.split('/').filter(Boolean).pop()
    if (seg) return seg
  }
  return String(m.id || '').trim()
}

/** DELETE /api/mods/:id 须传 manifest.id（与账号 user_mod 一致）；服务端再解析真实目录 */
function modIdForDeleteApi(m) {
  if (!m || typeof m !== 'object') return ''
  const mid = String(m.id || '').trim()
  if (mid) return mid
  return libraryFolderForDeleteApi(m)
}

function clearRepoPageLocalOnly() {
  message.value = ''
  try {
    sessionStorage.removeItem(PREFILL_KEY)
  } catch {
    /* ignore */
  }
  showCreate.value = false
  createName.value = ''
  showScaffold.value = false
  scaffoldBrief.value = ''
  scaffoldIdHint.value = ''
}

/** 清空源码库：删账号下全部 Mod 包 + 清本页本地状态（与「repo-page 全删」语义一致） */
async function purgeRepoLibraryAndLocalState() {
  if (purgeLibraryBusy.value) return
  if (!localStorage.getItem('modstore_token')) {
    flash('请先登录后再使用一键清理（将删除账号下全部 Mod）', false)
    return
  }

  const list = Array.isArray(mods.value) ? mods.value : []
  const folderKeys = [...new Set(list.map((m) => modIdForDeleteApi(m)).filter(Boolean))]
  const primaryCount = list.filter((m) => m && m.primary).length
  const primaryHint =
    primaryCount > 0
      ? `\n\n其中有 ${primaryCount} 个包在 manifest 中标记为主扩展（primary），删除后请确认 XCAGI / 宿主侧不再依赖对应 id。`
      : ''

  if (folderKeys.length === 0) {
    if (
      !window.confirm(
        '库中当前没有 Mod。将仅清除：本页提示、新建/脚手架弹窗未提交内容、以及「带入员工制作」预填缓存。是否继续？',
      )
    ) {
      return
    }
    clearRepoPageLocalOnly()
    flash('已清理本页本地状态', true)
    void load()
    return
  }

  if (
    !window.confirm(
      `确定删除当前账号 Mod 源码库中的全部 ${folderKeys.length} 个包？\n本地库目录将整包删除且从账号关联中移除，不可恢复。${primaryHint}\n\n同时将清除本页提示与员工制作预填缓存。`,
    )
  ) {
    return
  }

  purgeLibraryBusy.value = true
  clearRepoPageLocalOnly()
  const failed = []
  try {
    for (const folder of folderKeys) {
      try {
        await api.deleteMod(folder)
      } catch (e) {
        failed.push({ id: folder, err: e?.message || String(e) })
      }
    }
    if (failed.length) {
      flash(
        `已删除 ${folderKeys.length - failed.length} 个，失败 ${failed.length} 个：${failed.map((f) => f.id).join(', ')}`,
        false,
      )
    } else {
      flash(`已清空源码库（共删除 ${folderKeys.length} 个包）`, true)
    }
  } finally {
    purgeLibraryBusy.value = false
    await load({ cacheBust: true })
    if (failed.length === 0 && Array.isArray(mods.value) && mods.value.length > 0) {
      flash(
        `删除请求已返回成功，但列表仍显示 ${mods.value.length} 个包；请强制刷新页面或检查网关/浏览器是否缓存了「GET /api/mods」。`,
        false,
      )
    }
  }
}

async function deleteModFromLibrary(m) {
  const folder = m && typeof m === 'object' ? modIdForDeleteApi(m) : ''
  const folderSeg = m && typeof m === 'object' ? libraryFolderForDeleteApi(m) : ''
  const displayId = m && typeof m === 'object' ? String(m.id || '').trim() : ''
  if (!folder) return
  if (!localStorage.getItem('modstore_token')) {
    flash('请先登录后再删除 Mod', false)
    return
  }
  const label = (m.name && String(m.name).trim()) || displayId || folder
  const prim = m.primary
    ? '\n\n注意：该包在 manifest 中标记为主扩展（primary），删除后请确认 XCAGI / 宿主侧不再依赖该 id。'
    : ''
  const idNote =
    displayId && folderSeg && displayId !== folderSeg
      ? `（manifest id：${displayId}；目录名：${folderSeg}）`
      : `（${folder}）`
  if (
    !window.confirm(
      `确定从 Mod 源码库删除「${label}」${idNote}？\n本地库目录将整包删除，且会从你的账号关联中移除。此操作不可恢复。${prim}`,
    )
  ) {
    return
  }
  deleteModBusy.value = folder
  try {
    await api.deleteMod(folder)
    flash(`已删除 Mod 目录：${folder}`, true)
    await load({ cacheBust: true })
    if (Array.isArray(mods.value) && mods.value.some((row) => modIdForDeleteApi(row) === folder)) {
      flash(`删除已返回成功，但列表仍包含「${folder}」；请强制刷新或检查 GET /api/mods 是否被缓存。`, false)
    }
  } catch (e) {
    flash(e?.message || String(e), false)
  } finally {
    deleteModBusy.value = ''
  }
}

function getBlurb(m) {
  if (!m || typeof m !== 'object') return ''
  const b = typeof m.library_blurb === 'string' ? m.library_blurb.trim() : ''
  if (b) return b
  const d = typeof m.description === 'string' ? m.description.trim() : ''
  if (!d) return ''
  const one = d.replace(/\s+/g, ' ')
  return one.length > 120 ? `${one.slice(0, 117)}…` : one
}

function artifactLabel(a) {
  const x = (a || 'mod').toLowerCase()
  if (x === 'employee_pack') return '员工包'
  if (x === 'bundle') return '组合包'
  return 'Mod'
}

function isBundle(m) {
  return (m?.artifact || 'mod').toLowerCase() === 'bundle'
}

function viewMod(id) {
  router.push({ name: 'mod-authoring', params: { modId: id } })
}

function testModInSandbox(id) {
  const modId = String(id || '').trim()
  if (!modId) {
    flash('该 Mod 缺少 id，无法带入沙箱测试', false)
    return
  }
  router.push({ name: 'sandbox', query: { modId, host: '/sandbox', autoPush: '1' } })
}

function registerKey(modId, workflowIndex) {
  return `${modId}:${workflowIndex}`
}

async function registerWorkflowToCatalog(modId, workflowIndex) {
  if (!localStorage.getItem('modstore_token')) {
    flash('请先登录工作台后再一键登记到本地仓库', false)
    return
  }
  const k = registerKey(modId, workflowIndex)
  registerBusy.value = k
  try {
    const res = await api.registerWorkflowEmployeeCatalog(modId, workflowIndex)
    const pkg = res?.package
    const pid = pkg?.id || ''
    const ver = pkg?.version || ''
    flash(
      pid && ver
        ? `已登记到本地仓库：${pid} @ ${ver}（员工制作页「已登记员工包」可见）`
        : '已登记到本地仓库（/v1/packages）',
      true,
    )
  } catch (err) {
    flash(err?.message || String(err), false)
  } finally {
    registerBusy.value = ''
  }
}

function goEmployeePrefill(modId, emp, workflowIndex = 0) {
  const label = (emp && (emp.label || emp.id)) || '员工'
  const sum = typeof emp?.panel_summary === 'string' ? emp.panel_summary.trim() : ''
  const desc = sum
    ? `声明摘要：${sum}\n来源 Mod：${modId}（manifest.workflow_employees[${workflowIndex}]）。已带入员工制作页预填；也可在 Mod 源码库对该条点「一键登记」直接写入 /v1/packages，或完成向导后手动登记。`
    : `来自 Mod「${modId}」的 workflow_employees[${workflowIndex}] 声明。已带入员工制作页预填；也可在源码库「一键登记」或完成向导后登记到 /v1/packages。`
  try {
    sessionStorage.setItem(
      PREFILL_KEY,
      JSON.stringify({
        modId,
        workflowIndex,
        workflowEmployee: emp && typeof emp === 'object' ? emp : {},
        name: String(label).slice(0, 200),
        description: desc.slice(0, 4000),
      }),
    )
  } catch {
    /* ignore */
  }
  router.push({ name: 'workbench-unified', query: { focus: 'employee' } })
}

async function submitScaffold() {
  const brief = scaffoldBrief.value.trim()
  if (brief.length < 3) {
    flash('请至少写几句描述', false)
    return
  }
  scaffoldBusy.value = true
  try {
    const res = await api.modAiScaffold(brief, scaffoldIdHint.value.trim(), scaffoldReplace.value)
    flash(`已生成并导入 ${res.id}`)
    showScaffold.value = false
    scaffoldBrief.value = ''
    scaffoldIdHint.value = ''
    await load()
    router.push({ name: 'mod-authoring', params: { modId: res.id } })
  } catch (e) {
    flash(e.message || String(e), false)
  } finally {
    scaffoldBusy.value = false
  }
}

async function load(opts?: { cacheBust?: boolean }) {
  loading.value = true
  try {
    const res = await api.listMods(!!opts?.cacheBust)
    mods.value = Array.isArray(res?.data) ? res.data : []
  } catch (e) {
    flash('加载 Mod 库失败: ' + (e.message || String(e)), false)
    mods.value = []
  } finally {
    loading.value = false
  }
}

async function submitCreate() {
  const displayName = createName.value.trim()
  if (!displayName) {
    flash('请填写名称', false)
    return
  }
  const baseId = modIdFromDisplayName(displayName)
  for (let i = 0; i < 30; i++) {
    const candidate = i === 0 ? baseId : `${baseId}-${i + 1}`.slice(0, 128)
    try {
      const res = await api.createMod(candidate, displayName)
      const newId = res.id
      showCreate.value = false
      createName.value = ''
      flash(`已创建 ${newId}`)
      await load()
      router.push({ name: 'mod-authoring', params: { modId: newId } })
      return
    } catch (e: unknown) {
      if (isCreateModConflictError(e)) continue
      flash((e as Error)?.message || String(e), false)
      return
    }
  }
  flash('无法生成可用目录名（重试次数过多）', false)
}

async function onImport(ev) {
  const f = ev.target.files?.[0]
  ev.target.value = ''
  if (!f) return
  try {
    const res = await api.importZIP(f, true)
    flash(`已导入 ${res.id}`)
    await load()
  } catch (e) {
    flash(e.message || String(e), false)
  }
}

onMounted(() => {
  void load()
})
</script>

<style scoped>
.repo-page {
  width: 100%;
  max-width: var(--layout-max);
  margin: 0 auto;
  padding: var(--page-pad-y) var(--layout-pad-x);
  box-sizing: border-box;
}

.page-header {
  margin-bottom: 2rem;
}

.page-title {
  font-size: 1.75rem;
  margin: 0 0 0.5rem;
  color: #ffffff;
}

.page-desc {
  font-size: 0.9rem;
  color: rgba(255,255,255,0.4);
  margin: 0 0 1.25rem;
  line-height: 1.55;
}

.page-desc .mono {
  font-size: 0.8125rem;
  background: rgba(255,255,255,0.06);
  padding: 0.1em 0.35em;
  border-radius: 4px;
  color: rgba(255,255,255,0.75);
}

.bundle-hint {
  font-size: 0.75rem;
  color: rgba(251, 191, 36, 0.9);
  margin: 0 0 0.5rem;
}

.badge-artifact {
  font-weight: 600;
}

.badge-artifact--mod {
  background: rgba(96, 165, 250, 0.12);
  color: #93c5fd;
}

.badge-artifact--employee_pack {
  background: rgba(129, 140, 248, 0.15);
  color: #a5b4fc;
}

.badge-artifact--bundle {
  background: rgba(251, 191, 36, 0.12);
  color: #fbbf24;
}

.header-actions {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.hidden-input {
  display: none;
}

.flash {
  padding: 10px 16px;
  border-radius: 8px;
  margin-bottom: 16px;
  font-size: 14px;
}

.flash-ok {
  background: rgba(74,222,128,0.1);
  color: #4ade80;
}

.flash-err {
  background: rgba(255,80,80,0.1);
  color: #ff6b6b;
}

.loading {
  text-align: center;
  padding: 3rem;
  color: rgba(255,255,255,0.3);
}

.mods-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(min(100%, 17rem), 1fr));
  gap: 1rem;
}

.mod-card {
  background: #111111;
  border: 0.5px solid rgba(255,255,255,0.1);
  border-radius: 12px;
  padding: 1.25rem;
  transition: all 0.2s;
}

.mod-card:hover {
  border-color: rgba(255,255,255,0.2);
  transform: translateY(-2px);
}

.mod-card-badges {
  display: flex;
  gap: 0.375rem;
  margin-bottom: 0.75rem;
}

.mod-card-name {
  font-size: 1rem;
  font-weight: 600;
  color: #ffffff;
  margin: 0 0 0.375rem;
}

.mod-card-blurb {
  font-size: 0.8125rem;
  color: rgba(255,255,255,0.5);
  line-height: 1.5;
  margin: 0 0 0.625rem;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.mod-card-id {
  font-size: 0.75rem;
  color: rgba(255,255,255,0.3);
  font-family: monospace;
  margin-bottom: 0.5rem;
}

.mod-card-warn {
  font-size: 0.75rem;
  color: #fbbf24;
}

.mod-card-actions {
  margin-top: 1rem;
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  align-items: center;
}

.empty-state {
  text-align: center;
  padding: 4rem 1rem;
  color: rgba(255,255,255,0.3);
}

.empty-state p {
  margin: 0 0 0.5rem;
  font-size: 1.1rem;
}

.empty-hint {
  font-size: 0.85rem;
  color: rgba(255,255,255,0.2);
}

.btn {
  padding: 0.5rem 1rem;
  border: 0.5px solid rgba(255,255,255,0.15);
  border-radius: 6px;
  background: transparent;
  color: rgba(255,255,255,0.7);
  font-size: 0.875rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}

.btn:hover {
  background: rgba(255,255,255,0.06);
  color: #ffffff;
}

.btn-primary {
  background: #ffffff;
  color: #0a0a0a;
  border: none;
}

.btn-primary:hover {
  opacity: 0.9;
}

.btn-sm {
  padding: 0.35rem 0.75rem;
  font-size: 0.8rem;
}

.badge {
  display: inline-flex;
  align-items: center;
  padding: 0.1875rem 0.5rem;
  border-radius: 4px;
  font-size: 0.6875rem;
  font-weight: 500;
}

.badge-ok {
  background: rgba(74,222,128,0.1);
  color: #4ade80;
}

.badge-warn {
  background: rgba(251,191,36,0.1);
  color: #fbbf24;
}

.badge-primary {
  background: rgba(255,255,255,0.06);
  color: rgba(255,255,255,0.5);
}

.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.6);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
  padding: 1rem;
}

.modal {
  width: 100%;
  max-width: 420px;
  background: #111111;
  border: 0.5px solid rgba(255,255,255,0.1);
  border-radius: 16px;
  padding: 1.5rem;
}

.modal-title {
  font-size: 1.125rem;
  font-weight: 600;
  margin: 0 0 1.25rem;
  color: #ffffff;
}

.form-group {
  margin-bottom: 1rem;
}

.label {
  display: block;
  font-size: 0.8rem;
  color: rgba(255,255,255,0.5);
  margin-bottom: 0.4rem;
}

.input {
  width: 100%;
  padding: 0.6rem 0.75rem;
  border: 0.5px solid rgba(255,255,255,0.15);
  border-radius: 6px;
  background: rgba(255,255,255,0.03);
  color: #ffffff;
  font-size: 0.9rem;
  outline: none;
}

.input:focus {
  border-color: rgba(255,255,255,0.3);
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
  margin-top: 1.5rem;
}

.modal-wide {
  max-width: 520px;
}

.modal-hint {
  font-size: 0.8rem;
  color: rgba(255, 255, 255, 0.45);
  line-height: 1.45;
  margin: -0.5rem 0 1rem;
}

.textarea {
  resize: vertical;
  min-height: 6rem;
  font-family: inherit;
}

.checkbox-line {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.85rem;
  color: rgba(255, 255, 255, 0.55);
  margin-top: 0.5rem;
}

.btn-secondary {
  border-color: rgba(147, 197, 253, 0.35);
  color: #93c5fd;
}

.btn-secondary:hover {
  background: rgba(96, 165, 250, 0.12);
  color: #bfdbfe;
}

.btn-ghost {
  border-style: dashed;
  border-color: rgba(255, 255, 255, 0.12);
  color: rgba(255, 255, 255, 0.55);
}

.btn-ghost:hover {
  border-color: rgba(165, 180, 252, 0.4);
  color: #c7d2fe;
}

.wf-emp-block {
  margin-top: 0.75rem;
  padding-top: 0.75rem;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
}

.wf-emp-title {
  font-size: 0.7rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: rgba(255, 255, 255, 0.35);
  margin-bottom: 0.35rem;
}

.wf-emp-actions {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

.wf-emp-line {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.35rem 0.5rem;
}
</style>
