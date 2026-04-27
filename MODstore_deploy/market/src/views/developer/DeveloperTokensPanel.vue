<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { api } from '../../api'

interface DeveloperToken {
  id: number
  name: string
  prefix: string
  scopes: string[]
  created_at: string | null
  last_used_at: string | null
  expires_at: string | null
  revoked_at: string | null
  is_active: boolean
}

const tokens = ref<DeveloperToken[]>([])
const loading = ref(false)
const errMsg = ref('')

const showDialog = ref(false)
const submitBusy = ref(false)
const draft = reactive({ name: '', scopesCsv: 'workflow:read,workflow:execute', expiresDays: '90' })

const justCreated = ref<{ token: string; meta: DeveloperToken } | null>(null)
const copied = ref(false)

const SCOPE_HINTS = [
  'workflow:read',
  'workflow:execute',
  'employee:execute',
  'catalog:read',
  'webhook:manage',
]

async function refresh() {
  loading.value = true
  errMsg.value = ''
  try {
    const list: any = await api.developerListTokens()
    tokens.value = Array.isArray(list) ? list : []
  } catch (e: any) {
    errMsg.value = e?.detail || e?.message || '加载失败'
  } finally {
    loading.value = false
  }
}

onMounted(refresh)

function openCreate() {
  draft.name = ''
  draft.scopesCsv = 'workflow:read,workflow:execute'
  draft.expiresDays = '90'
  showDialog.value = true
}

function closeCreate() {
  if (submitBusy.value) return
  showDialog.value = false
}

async function submitCreate() {
  if (!draft.name.trim()) {
    errMsg.value = '请填写 Token 名称'
    return
  }
  submitBusy.value = true
  errMsg.value = ''
  try {
    const scopes = draft.scopesCsv
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean)
    const days = draft.expiresDays.trim() ? Number(draft.expiresDays) : null
    const resp: any = await api.developerCreateToken(
      draft.name.trim(),
      scopes,
      Number.isFinite(days as number) && (days as number) > 0 ? (days as number) : null,
    )
    showDialog.value = false
    if (resp?.token) {
      const { token, ...meta } = resp
      justCreated.value = { token, meta: meta as DeveloperToken }
      copied.value = false
    }
    await refresh()
  } catch (e: any) {
    errMsg.value = e?.detail || e?.message || '创建失败'
  } finally {
    submitBusy.value = false
  }
}

async function copyJustCreated() {
  if (!justCreated.value) return
  try {
    await navigator.clipboard.writeText(justCreated.value.token)
    copied.value = true
  } catch {
    const ta = document.createElement('textarea')
    ta.value = justCreated.value.token
    document.body.appendChild(ta)
    ta.select()
    try {
      document.execCommand('copy')
      copied.value = true
    } finally {
      document.body.removeChild(ta)
    }
  }
}

function dismissJustCreated() {
  if (!copied.value && !confirm('确定关闭？关闭后将无法再次查看明文，请确认已经复制并妥善保管。')) return
  justCreated.value = null
}

async function revoke(row: DeveloperToken) {
  if (!confirm(`确认吊销 "${row.name}"？已分发的客户端将立即失效。`)) return
  try {
    await api.developerRevokeToken(row.id)
    await refresh()
  } catch (e: any) {
    errMsg.value = e?.detail || e?.message || '吊销失败'
  }
}

function formatTime(iso: string | null): string {
  if (!iso) return '—'
  try {
    return new Date(iso).toLocaleString()
  } catch {
    return iso
  }
}

function statusOf(row: DeveloperToken): { text: string; cls: string } {
  if (row.revoked_at) return { text: '已吊销', cls: 'st-revoked' }
  if (row.expires_at && new Date(row.expires_at).getTime() < Date.now())
    return { text: '已过期', cls: 'st-expired' }
  return { text: '可用', cls: 'st-active' }
}
</script>

<template>
  <div class="dt">
    <header class="dt__head">
      <div>
        <h2 class="dt__title">Personal Access Token</h2>
        <p class="dt__hint">
          用 <code>Authorization: Bearer pat_xxx</code> 调用 MODstore REST API。明文仅在创建时显示一次。
        </p>
      </div>
      <button class="dt__btn dt__btn--primary" type="button" @click="openCreate">
        创建新 Token
      </button>
    </header>

    <p v-if="errMsg" class="dt__err">{{ errMsg }}</p>

    <div v-if="loading" class="dt__placeholder">加载中…</div>
    <div v-else-if="!tokens.length" class="dt__placeholder">
      还没有 Token，点击「创建新 Token」开始接入第三方应用。
    </div>
    <table v-else class="dt__table">
      <thead>
        <tr>
          <th>名称</th>
          <th>前缀</th>
          <th>权限范围</th>
          <th>创建时间</th>
          <th>最近使用</th>
          <th>过期</th>
          <th>状态</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="t in tokens" :key="t.id" :class="{ 'dt__row--inactive': !t.is_active }">
          <td>{{ t.name || '—' }}</td>
          <td><code>{{ t.prefix }}…</code></td>
          <td>
            <span v-if="!t.scopes.length" class="dt__scope-empty">全部</span>
            <span v-for="s in t.scopes" :key="s" class="dt__scope">{{ s }}</span>
          </td>
          <td>{{ formatTime(t.created_at) }}</td>
          <td>{{ formatTime(t.last_used_at) }}</td>
          <td>{{ t.expires_at ? formatTime(t.expires_at) : '永不' }}</td>
          <td>
            <span class="dt__status" :class="statusOf(t).cls">{{ statusOf(t).text }}</span>
          </td>
          <td>
            <button
              v-if="t.is_active"
              class="dt__btn dt__btn--danger"
              type="button"
              @click="revoke(t)"
            >
              吊销
            </button>
          </td>
        </tr>
      </tbody>
    </table>

    <transition name="dt-fade">
      <div v-if="showDialog" class="dt-modal" @click.self="closeCreate">
        <div class="dt-modal__card">
          <header class="dt-modal__head">
            <h3>创建新 Token</h3>
            <button class="dt__btn" type="button" :disabled="submitBusy" @click="closeCreate">关闭</button>
          </header>
          <div class="dt-modal__body">
            <label class="dt-field">
              <span>名称</span>
              <input v-model="draft.name" type="text" placeholder="例如：本地脚本 / CI Pipeline" />
            </label>
            <label class="dt-field">
              <span>权限范围（逗号分隔；为空 = 全部）</span>
              <input v-model="draft.scopesCsv" type="text" placeholder="workflow:read,workflow:execute" />
              <small class="dt-field__hint">
                可选：
                <button
                  v-for="s in SCOPE_HINTS"
                  :key="s"
                  type="button"
                  class="dt-field__chip"
                  @click="draft.scopesCsv = draft.scopesCsv.split(',').filter(Boolean).concat(s).join(',')"
                >
                  {{ s }}
                </button>
              </small>
            </label>
            <label class="dt-field">
              <span>有效期（天，留空 = 永不过期）</span>
              <input v-model="draft.expiresDays" type="number" min="1" max="365" placeholder="90" />
            </label>
          </div>
          <footer class="dt-modal__foot">
            <button class="dt__btn" type="button" :disabled="submitBusy" @click="closeCreate">取消</button>
            <button class="dt__btn dt__btn--primary" type="button" :disabled="submitBusy" @click="submitCreate">
              {{ submitBusy ? '提交中…' : '生成 Token' }}
            </button>
          </footer>
        </div>
      </div>
    </transition>

    <transition name="dt-fade">
      <div v-if="justCreated" class="dt-modal">
        <div class="dt-modal__card dt-modal__card--ok">
          <header class="dt-modal__head">
            <h3>Token 已生成 — 仅显示一次</h3>
          </header>
          <div class="dt-modal__body">
            <p class="dt-just__warn">
              这是 <strong>{{ justCreated.meta.name }}</strong> 的明文 Token。请立即复制并妥善保管，关闭后将无法再次查看。
            </p>
            <pre class="dt-just__token">{{ justCreated.token }}</pre>
            <p class="dt-just__sample">使用示例：</p>
            <pre class="dt-just__sample-code"
><code>curl https://&lt;your-domain&gt;/api/employees/ \
  -H "Authorization: Bearer {{ justCreated.token }}"</code></pre>
          </div>
          <footer class="dt-modal__foot">
            <button class="dt__btn" type="button" @click="copyJustCreated">
              {{ copied ? '已复制 ✓' : '复制到剪贴板' }}
            </button>
            <button class="dt__btn dt__btn--primary" type="button" @click="dismissJustCreated">
              我已保存
            </button>
          </footer>
        </div>
      </div>
    </transition>
  </div>
</template>

<style scoped>
.dt__head {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  gap: 16px;
  margin-bottom: 14px;
}

.dt__title {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
}

.dt__hint {
  margin: 4px 0 0;
  font-size: 12px;
  color: #64748b;
}

.dt__hint code {
  background: #f1f5f9;
  padding: 1px 4px;
  border-radius: 4px;
  font-size: 11px;
}

.dt__err {
  margin: 0 0 12px;
  padding: 8px 12px;
  background: #fee2e2;
  color: #991b1b;
  border-radius: 6px;
  font-size: 13px;
}

.dt__placeholder {
  padding: 28px;
  background: #f8fafc;
  border: 1px dashed #cbd5e1;
  border-radius: 8px;
  text-align: center;
  color: #64748b;
  font-size: 13px;
}

.dt__table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.dt__table th,
.dt__table td {
  padding: 10px 12px;
  border-bottom: 1px solid #e2e8f0;
  text-align: left;
}

.dt__table th {
  font-size: 11px;
  font-weight: 600;
  color: #64748b;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  background: #f8fafc;
}

.dt__row--inactive {
  color: #94a3b8;
}

.dt__row--inactive code {
  color: #94a3b8;
}

.dt__scope {
  display: inline-block;
  font-size: 11px;
  background: #eef2ff;
  color: #3730a3;
  padding: 1px 6px;
  border-radius: 999px;
  margin-right: 4px;
  margin-bottom: 2px;
}

.dt__scope-empty {
  font-size: 11px;
  color: #94a3b8;
}

.dt__status {
  font-size: 11px;
  padding: 1px 8px;
  border-radius: 999px;
}

.st-active {
  background: #dcfce7;
  color: #166534;
}

.st-revoked {
  background: #fee2e2;
  color: #991b1b;
}

.st-expired {
  background: #fef3c7;
  color: #92400e;
}

.dt__btn {
  font-size: 13px;
  border: 1px solid #cbd5e1;
  background: #fff;
  color: #334155;
  padding: 6px 12px;
  border-radius: 6px;
  cursor: pointer;
}

.dt__btn:hover:not(:disabled) {
  background: #f1f5f9;
}

.dt__btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.dt__btn--primary {
  background: #4f46e5;
  border-color: #4f46e5;
  color: #fff;
}

.dt__btn--primary:hover:not(:disabled) {
  background: #4338ca;
}

.dt__btn--danger {
  border-color: #fecaca;
  color: #b91c1c;
  background: #fff;
}

.dt__btn--danger:hover {
  background: #fef2f2;
}

.dt-modal {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.42);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
  padding: 16px;
}

.dt-modal__card {
  width: min(560px, 100%);
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 24px 48px -16px rgba(15, 23, 42, 0.4);
  display: flex;
  flex-direction: column;
}

.dt-modal__card--ok {
  border-top: 4px solid #22c55e;
}

.dt-modal__head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 18px;
  border-bottom: 1px solid #e2e8f0;
}

.dt-modal__head h3 {
  margin: 0;
  font-size: 15px;
}

.dt-modal__body {
  padding: 16px 18px;
}

.dt-modal__foot {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding: 12px 18px;
  border-top: 1px solid #e2e8f0;
}

.dt-field {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-bottom: 14px;
}

.dt-field span {
  font-size: 12px;
  color: #334155;
  font-weight: 500;
}

.dt-field input {
  width: 100%;
  border: 1px solid #cbd5e1;
  border-radius: 6px;
  padding: 7px 9px;
  font-size: 13px;
}

.dt-field input:focus {
  outline: none;
  border-color: #6366f1;
  box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.18);
}

.dt-field__hint {
  font-size: 11px;
  color: #64748b;
  margin-top: 2px;
}

.dt-field__chip {
  background: #eef2ff;
  color: #3730a3;
  border: 0;
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 999px;
  margin-left: 4px;
  cursor: pointer;
}

.dt-field__chip:hover {
  background: #c7d2fe;
}

.dt-just__warn {
  margin: 0 0 10px;
  font-size: 13px;
  color: #b45309;
  background: #fef3c7;
  padding: 8px 12px;
  border-radius: 6px;
}

.dt-just__token {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 13px;
  background: #0f172a;
  color: #e2e8f0;
  padding: 12px;
  border-radius: 6px;
  word-break: break-all;
  white-space: pre-wrap;
  margin: 0 0 14px;
}

.dt-just__sample {
  margin: 0 0 4px;
  font-size: 12px;
  color: #475569;
}

.dt-just__sample-code {
  margin: 0;
  font-size: 12px;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  padding: 10px 12px;
  white-space: pre-wrap;
  word-break: break-all;
  color: #0f172a;
}

.dt-fade-enter-active,
.dt-fade-leave-active {
  transition: opacity 0.18s ease;
}

.dt-fade-enter-from,
.dt-fade-leave-to {
  opacity: 0;
}
</style>
