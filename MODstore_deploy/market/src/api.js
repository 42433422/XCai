const BASE = ''

const REFRESH_KEY = 'modstore_refresh_token'

function getToken() {
  return localStorage.getItem('modstore_token') || ''
}

export function setTokensFromAuthResponse(res) {
  if (res?.access_token) localStorage.setItem('modstore_token', res.access_token)
  if (res?.refresh_token) localStorage.setItem(REFRESH_KEY, res.refresh_token)
}

export function clearAuthTokens() {
  localStorage.removeItem('modstore_token')
  localStorage.removeItem(REFRESH_KEY)
}

let _refreshInFlight = null

async function doRefreshAccessToken() {
  const rt = localStorage.getItem(REFRESH_KEY)
  if (!rt) return null
  const r = await fetch(`${BASE}/api/auth/refresh`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh_token: rt }),
  })
  const text = await r.text()
  let data = null
  try {
    data = text ? JSON.parse(text) : null
  } catch {
    data = { detail: text || r.statusText }
  }
  if (!r.ok) {
    clearAuthTokens()
    return null
  }
  setTokensFromAuthResponse(data)
  return data?.access_token || null
}

function refreshAccessTokenOnce() {
  if (!_refreshInFlight) {
    _refreshInFlight = doRefreshAccessToken().finally(() => {
      _refreshInFlight = null
    })
  }
  return _refreshInFlight
}

/** 成功响应须为 zip（PK）；否则从 JSON/HTML 正文解析可读错误（常见于 401 或代理误配）。 */
function assertZipBufferOrThrow(buf, httpStatusText) {
  const u8 = new Uint8Array(buf)
  if (buf.byteLength >= 4 && u8[0] === 0x50 && u8[1] === 0x4b) return
  let msg = '响应不是 zip 文件（请确认已登录且当前页与接口同源；部署在子路径时需正确代理 /api）'
  try {
    const text = new TextDecoder('utf-8', { fatal: false }).decode(buf.slice(0, 8000))
    const j = JSON.parse(text)
    if (j?.detail) msg = typeof j.detail === 'string' ? j.detail : JSON.stringify(j.detail)
    else if (text.trim()) msg = text.trim().slice(0, 600)
  } catch {
    try {
      const text = new TextDecoder('utf-8', { fatal: false }).decode(buf.slice(0, 600))
      if (text.trim()) msg = text.trim().slice(0, 600)
    } catch {
      /* keep default */
    }
  }
  throw new Error(msg || httpStatusText || '无效的 zip 响应')
}

async function fetchOkZipBlob(url, headers = {}) {
  const r = await fetch(url, { headers })
  const buf = await r.arrayBuffer()
  if (!r.ok) {
    let msg = r.statusText || '请求失败'
    try {
      const text = new TextDecoder('utf-8', { fatal: false }).decode(buf.slice(0, 8000))
      const j = JSON.parse(text)
      if (j?.detail) msg = typeof j.detail === 'string' ? j.detail : JSON.stringify(j.detail)
      else if (text.trim()) msg = text.trim().slice(0, 600)
    } catch {
      /* keep msg */
    }
    throw new Error(msg)
  }
  assertZipBufferOrThrow(buf, r.statusText)
  return new Blob([buf], { type: 'application/zip' })
}

/** Catalog 写入（上传 / promote）优先使用环境变量中的专用 Bearer，与 MODSTORE_CATALOG_UPLOAD_TOKEN 一致 */
function catalogWriteHeaders() {
  const t = (import.meta.env?.VITE_MODSTORE_CATALOG_UPLOAD_TOKEN ?? '').toString().trim()
  if (t) return { Authorization: `Bearer ${t}` }
  return {}
}

async function req(path, opts = {}, authAttempt = 0) {
  const method = (opts.method || 'GET').toUpperCase()
  const headers = { ...(opts.headers || {}) }
  const token = getToken()
  if (token && !headers['Authorization']) {
    headers['Authorization'] = `Bearer ${token}`
  }
  const body = opts.body
  if (!(body instanceof FormData) && method !== 'GET' && method !== 'HEAD' && body !== undefined) {
    if (!headers['Content-Type'] && !headers['content-type']) {
      headers['Content-Type'] = 'application/json'
    }
  }
  const skipRefresh =
    path.includes('/api/auth/login') ||
    path.includes('/api/auth/register') ||
    path.includes('/api/auth/login-with-code') ||
    path.includes('/api/auth/refresh') ||
    path.includes('/api/auth/send-')

  let r = await fetch(`${BASE}${path}`, { ...opts, method, headers, body })
  let text = await r.text()
  if (
    r.status === 401 &&
    authAttempt === 0 &&
    getToken() &&
    !skipRefresh &&
    !headers['X-Skip-Auth-Refresh']
  ) {
    const newTok = await refreshAccessTokenOnce()
    if (newTok) return req(path, opts, 1)
  }
  let data = null
  try {
    data = text ? JSON.parse(text) : null
  } catch {
    data = { detail: text || r.statusText }
  }
  if (!r.ok) {
    const d = data?.detail
    let msg
    if (Array.isArray(d)) msg = d.map((x) => x.msg || JSON.stringify(x)).join('; ')
    else if (typeof d === 'string') msg = d
    else if (d && typeof d === 'object') msg = JSON.stringify(d)
    else msg = r.statusText
    throw new Error(msg)
  }
  return data
}

export const api = {
  register: async (username, password, email, verificationCode = '') => {
    const res = await req('/api/auth/register', {
      method: 'POST',
      body: JSON.stringify({
        username,
        password,
        email,
        verification_code: verificationCode,
      }),
    })
    setTokensFromAuthResponse(res)
    return res
  },
  login: async (username, password) => {
    const res = await req('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    })
    setTokensFromAuthResponse(res)
    return res
  },
  me: () => req('/api/auth/me'),

  sendVerificationCode: (email) =>
    req('/api/auth/send-code', { method: 'POST', body: JSON.stringify({ email }) }),
  sendRegisterVerificationCode: (email) =>
    req('/api/auth/send-register-code', { method: 'POST', body: JSON.stringify({ email }) }),
  sendResetPasswordCode: (email) =>
    req('/api/auth/send-reset-password-code', { method: 'POST', body: JSON.stringify({ email }) }),
  resetPassword: (email, code, newPassword) =>
    req('/api/auth/reset-password', {
      method: 'POST',
      body: JSON.stringify({ email, code, new_password: newPassword }),
    }),
  loginWithCode: async (email, code) => {
    const res = await req('/api/auth/login-with-code', {
      method: 'POST',
      body: JSON.stringify({ email, code }),
    })
    setTokensFromAuthResponse(res)
    return res
  },
  updateProfile: (username) =>
    req('/api/auth/profile', { method: 'PUT', body: JSON.stringify({ username }) }),
  changePassword: (currentPassword, newPassword) =>
    req('/api/auth/change-password', {
      method: 'POST',
      body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
    }),

  balance: () => req('/api/wallet/balance'),
  recharge: (amount, description) =>
    req('/api/wallet/recharge', { method: 'POST', body: JSON.stringify({ amount, description }) }),
  transactions: (limit = 50, offset = 0) =>
    req(`/api/wallet/transactions?limit=${limit}&offset=${offset}`),

  catalog: (q = '', artifact = '', limit = 50, offset = 0, industry = '', securityLevel = '') => {
    let url = `/api/market/catalog?limit=${limit}&offset=${offset}`
    if (q) url += `&q=${encodeURIComponent(q)}`
    if (artifact) url += `&artifact=${encodeURIComponent(artifact)}`
    if (industry) url += `&industry=${encodeURIComponent(industry)}`
    if (securityLevel) url += `&security_level=${encodeURIComponent(securityLevel)}`
    return req(url)
  },
  catalogFacets: () => req('/api/market/facets'),
  catalogDetail: (id) => req(`/api/market/catalog/${id}`),
  catalogReviews: (id) => req(`/api/market/catalog/${id}/reviews`),
  catalogSubmitReview: (id, rating, content) =>
    req(`/api/market/catalog/${id}/review`, {
      method: 'POST',
      body: JSON.stringify({ rating, content: content || '' }),
    }),
  catalogToggleFavorite: (id) => req(`/api/market/catalog/${id}/favorite`, { method: 'POST', body: '{}' }),
  buyItem: (id) => req(`/api/market/catalog/${id}/buy`, { method: 'POST' }),
  downloadItem: (id) => {
    const token = getToken()
    return fetch(`${BASE}/api/market/catalog/${id}/download`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    }).then(async (r) => {
      if (!r.ok) {
        const text = await r.text()
        throw new Error(text || r.statusText)
      }
      const blob = await r.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `mod-${id}.zip`
      a.click()
      URL.revokeObjectURL(url)
    })
  },

  myStore: (limit = 50, offset = 0) =>
    req(`/api/my-store?limit=${limit}&offset=${offset}`),

  adminStatus: () => req('/api/admin/status'),
  adminUpload: (formData) => req('/api/admin/catalog', { method: 'POST', body: formData }),
  adminListCatalog: (limit = 200, offset = 0) =>
    req(`/api/admin/catalog?limit=${limit}&offset=${offset}`),
  adminDeleteCatalog: (id) =>
    req(`/api/admin/catalog/${id}`, { method: 'DELETE' }),
  adminListUsers: (limit = 200, offset = 0) =>
    req(`/api/admin/users?limit=${limit}&offset=${offset}`),
  adminSetUserAdmin: (userId, isAdmin) =>
    req(`/api/admin/users/${userId}/admin?is_admin=${isAdmin}`, { method: 'PUT' }),
  adminListWallets: (limit = 200, offset = 0) =>
    req(`/api/admin/wallets?limit=${limit}&offset=${offset}`),
  adminListTransactions: (limit = 200, offset = 0) =>
    req(`/api/admin/transactions?limit=${limit}&offset=${offset}`),

  paymentPlans: () => req('/api/payment/plans'),
  paymentMyPlan: () => req('/api/payment/my-plan'),
  paymentCheckout: async (data) => {
    const sign = await req('/api/payment/sign-checkout', {
      method: 'POST',
      body: JSON.stringify({
        plan_id: data.plan_id ?? '',
        item_id: Number(data.item_id ?? 0) || 0,
        total_amount: Number(data.total_amount ?? 0) || 0,
        subject: data.subject ?? '',
        wallet_recharge: Boolean(data.wallet_recharge),
      }),
    })
    const finalData = {
      plan_id: sign.plan_id ?? '',
      item_id: sign.item_id ?? 0,
      total_amount: sign.total_amount ?? 0,
      subject: sign.subject ?? '',
      wallet_recharge: Boolean(sign.wallet_recharge),
      request_id: sign.request_id,
      timestamp: sign.timestamp,
      signature: sign.signature,
    }
    return req('/api/payment/checkout', { method: 'POST', body: JSON.stringify(finalData) })
  },
  paymentQuery: (orderId) => req(`/api/payment/query/${orderId}`),
  paymentOrders: (status = '', limit = 50, offset = 0) => {
    let url = `/api/payment/orders?limit=${limit}&offset=${offset}`
    if (status) url += `&status=${encodeURIComponent(status)}`
    return req(url)
  },
  paymentCancelOrder: (orderNo) =>
    req(`/api/payment/cancel/${encodeURIComponent(orderNo)}`, { method: 'POST', body: '{}' }),
  paymentDiagnostics: () => req('/api/payment/diagnostics'),
  paymentEntitlements: () => req('/api/payment/entitlements'),

  // Repository APIs
  listMods: () => req('/api/mods'),
  createMod: (mod_id, display_name) =>
    req('/api/mods/create', { method: 'POST', body: JSON.stringify({ mod_id, display_name }) }),
  importZIP: async (file, replace = true) => {
    const fd = new FormData()
    fd.append('file', file)
    const r = await fetch(`${BASE}/api/mods/import?replace=${replace}`, {
      method: 'POST',
      headers: getToken() ? { Authorization: `Bearer ${getToken()}` } : {},
      body: fd,
    })
    const data = await r.json().catch(() => ({}))
    if (!r.ok) throw new Error(data.detail || r.statusText)
    return data
  },
  /** 服务端按默认或指定 LLM 生成 manifest + 脚手架 zip 并导入库 */
  modAiScaffold: (brief, suggestedId = '', replace = true, provider = undefined, model = undefined) => {
    const body = {
      brief,
      suggested_id: suggestedId || undefined,
      replace,
    }
    if (provider && model) {
      body.provider = provider
      body.model = model
    }
    return req('/api/mods/ai-scaffold', { method: 'POST', body: JSON.stringify(body) })
  },
  push: (mod_ids) =>
    req('/api/sync/push', { method: 'POST', body: JSON.stringify({ mod_ids: mod_ids || null }) }),
  pull: (mod_ids) =>
    req('/api/sync/pull', { method: 'POST', body: JSON.stringify({ mod_ids: mod_ids || null }) }),

  getMod: (modId) => req(`/api/mods/${encodeURIComponent(modId)}`),
  putModManifest: (modId, manifest) =>
    req(`/api/mods/${encodeURIComponent(modId)}/manifest`, {
      method: 'PUT',
      body: JSON.stringify({ manifest }),
    }),
  listModSnapshots: (modId) => req(`/api/mods/${encodeURIComponent(modId)}/snapshots`),
  captureModSnapshot: (modId, label = '') =>
    req(`/api/mods/${encodeURIComponent(modId)}/snapshots`, {
      method: 'POST',
      body: JSON.stringify({ label }),
    }),
  restoreModSnapshot: (modId, snapId) =>
    req(`/api/mods/${encodeURIComponent(modId)}/snapshots/${encodeURIComponent(snapId)}/restore`, {
      method: 'POST',
      body: JSON.stringify({}),
    }),
  bumpModManifestPatchVersion: (modId) =>
    req(`/api/mods/${encodeURIComponent(modId)}/manifest/bump-patch-version`, {
      method: 'POST',
      body: JSON.stringify({}),
    }),
  /** 向 manifest.workflow_employees 写入 workflow_id：追加新项，或 body.workflow_index 指定时合并到已有条目 */
  modWorkflowLink: (modId, body) =>
    req(`/api/mods/${encodeURIComponent(modId)}/workflow-link`, {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  /** 追加 workflow_employee + 生成 employee_stubs 占位路由（骨架 Mod 可自动合并 blueprints） */
  scaffoldWorkflowEmployee: (modId, body) =>
    req(`/api/mods/${encodeURIComponent(modId)}/workflow-employees/scaffold`, {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  getModFile: (modId, path) =>
    req(`/api/mods/${encodeURIComponent(modId)}/file?path=${encodeURIComponent(path)}`),
  putModFile: (modId, path, content) =>
    req(`/api/mods/${encodeURIComponent(modId)}/file`, {
      method: 'PUT',
      body: JSON.stringify({ path, content }),
    }),
  getModAuthoringSummary: (modId) =>
    req(`/api/mods/${encodeURIComponent(modId)}/authoring-summary`),

  /** 本地 Catalog（/v1/packages）：无需登录即可列出；与 SQL 市场目录是两套存储 */
  listV1Packages: (artifact = '', q = '', limit = 50, offset = 0) => {
    let u = `/v1/packages?limit=${limit}&offset=${offset}`
    if (artifact) u += `&artifact=${encodeURIComponent(artifact)}`
    if (q) u += `&q=${encodeURIComponent(q)}`
    return req(u)
  },

  /** 同 pkg id 下所有 Catalog 版本（含 release_channel） */
  listCatalogPackageVersions: (pkgId) =>
    req(`/v1/packages/by-id/${encodeURIComponent(pkgId)}/versions`),

  /** 将 draft 记录晋升为新的 stable 版本（需 Catalog 上传 token） */
  promoteCatalogPackage: (pkgId, fromVersion) =>
    req(`/v1/packages/${encodeURIComponent(pkgId)}/promote`, {
      method: 'POST',
      body: JSON.stringify({ from_version: fromVersion }),
      headers: { ...catalogWriteHeaders() },
    }),

  /** 下载已登记包（公开 GET，返回 Blob） */
  downloadCatalogPackageBlob: async (pkgId, version) => {
    const r = await fetch(
      `${BASE}/v1/packages/${encodeURIComponent(pkgId)}/${encodeURIComponent(version)}/download`,
    )
    if (!r.ok) {
      const t = await r.text()
      let msg = t || r.statusText
      try {
        const j = JSON.parse(t)
        if (j?.detail) msg = typeof j.detail === 'string' ? j.detail : JSON.stringify(j.detail)
      } catch {
        /* keep */
      }
      throw new Error(msg)
    }
    return r.blob()
  },

  /** 从 Mod 的 workflow_employees[index] 生成 employee_pack 最小 zip（Bearer JWT） */
  exportEmployeePackZip: async (modId, workflowIndex = 0) => {
    const token = getToken()
    const n = Number.parseInt(String(workflowIndex ?? 0), 10)
    const idx = Number.isFinite(n) && n >= 0 ? n : 0
    const q = new URLSearchParams({ workflow_index: String(idx) })
    const headers = token ? { Authorization: `Bearer ${token}` } : {}
    const mid = String(modId || '').trim()
    const urls = [
      `${BASE}/api/mods/${encodeURIComponent(mid)}/export-employee-pack?${q}`,
      `${BASE}/api/mods/${encodeURIComponent(mid)}/export_employee_pack?${q}`,
    ]
    const staleHint =
      '8765 上的 API 进程里若没有该路由，会返回 Not Found。请完全退出旧进程后重启：在 MODstore_deploy 目录执行 start-modstore.bat / restart.bat，或手动运行 python -m modstore_server。自检：打开 http://127.0.0.1:8765/docs 搜索「export-employee-pack」，搜不到即仍是旧代码。'
    const looksLikeMissingRoute = (raw) => {
      const m = String(raw || '').trim()
      if (/mod\s*不存在|Mod 不存在/i.test(m)) return false
      if (/^not found$/i.test(m)) return true
      if (m === '{"detail":"Not Found"}') return true
      if (m.startsWith('[{') && /not found/i.test(m)) return true
      try {
        const j = JSON.parse(m)
        const d = j?.detail
        if (d === 'Not Found') return true
        if (Array.isArray(d) && d.some((x) => String(x?.msg || '').toLowerCase() === 'not found')) return true
      } catch {
        /* ignore */
      }
      return false
    }
    let lastErr
    for (let i = 0; i < urls.length; i++) {
      try {
        return await fetchOkZipBlob(urls[i], headers)
      } catch (e) {
        lastErr = e
        const msg = String((e && e.message) || '').trim()
        if (looksLikeMissingRoute(msg) && i === 0) continue
        break
      }
    }
    const base = String((lastErr && lastErr.message) || '导出失败').trim()
    if (looksLikeMissingRoute(base)) {
      throw new Error(`${base} — ${staleHint}`)
    }
    throw lastErr instanceof Error ? lastErr : new Error(base)
  },

  /**
   * 从 workflow_employees[index] 一键生成 employee_pack 并登记到本地 /v1/packages（Bearer 用户 JWT，无需 Catalog 上传 Token）。
   * @param {string} modId
   * @param {number} [workflowIndex=0]
   * @param {{ industry?: string, price?: number, release_channel?: 'stable'|'draft' }} [opts]
   */
  registerWorkflowEmployeeCatalog: async (modId, workflowIndex = 0, opts = {}) => {
    const mid = String(modId || '').trim()
    const n = Number.parseInt(String(workflowIndex ?? 0), 10)
    const idx = Number.isFinite(n) && n >= 0 ? n : 0
    const body = {
      workflow_index: idx,
      industry: typeof opts.industry === 'string' && opts.industry.trim() ? opts.industry.trim() : '通用',
      price: typeof opts.price === 'number' && Number.isFinite(opts.price) ? opts.price : 0,
      release_channel:
        opts.release_channel === 'draft' || opts.release_channel === 'stable'
          ? opts.release_channel
          : 'stable',
    }
    return req(`/api/mods/${encodeURIComponent(mid)}/register-workflow-employee-catalog`, {
      method: 'POST',
      body: JSON.stringify(body),
    })
  },

  /** 将库中 Mod 目录打包为 zip（Bearer 用户 JWT） */
  exportModZip: async (modId) => {
    const token = getToken()
    const headers = token ? { Authorization: `Bearer ${token}` } : {}
    return fetchOkZipBlob(`${BASE}/api/mods/${encodeURIComponent(modId)}/export`, headers)
  },
  getModBlueprintRoutes: (modId) =>
    req(`/api/mods/${encodeURIComponent(modId)}/blueprint-routes`),
  getAuthoringExtensionSurface: (mergeHost = false) =>
    req(`/api/authoring/extension-surface?merge_host=${mergeHost ? 'true' : 'false'}`),

  /** 沙盒审核：multipart file（.zip/.xcemp），可选 metadata JSON 含 artifact */
  auditPackage: async (file, metadata = null) => {
    const fd = new FormData()
    fd.append('file', file)
    if (metadata != null) fd.append('metadata', JSON.stringify(metadata))
    return req('/api/package-audit', { method: 'POST', body: fd })
  },

  // 上传员工包
  uploadPackage: async (metadata, file) => {
    const fd = new FormData()
    fd.append('metadata', JSON.stringify(metadata))
    fd.append('file', file)
    return req('/v1/packages', {
      method: 'POST',
      body: fd,
      headers: { ...catalogWriteHeaders() },
    })
  },

  // 工作流相关API
  listWorkflows: () => req('/api/workflow'),
  listWorkflowsByEmployee: (employeeId) =>
    req(`/api/workflow/by-employee?employee_id=${encodeURIComponent(String(employeeId || '').trim())}`),
  getWorkflow: (id) => req(`/api/workflow/${id}`),
  createWorkflow: (name, description) =>
    req('/api/workflow', {
      method: 'POST',
      body: JSON.stringify({ name, description })
    }),
  updateWorkflow: (id, name, description, isActive) =>
    req(`/api/workflow/${id}`, {
      method: 'PUT',
      body: JSON.stringify({ name, description, is_active: isActive })
    }),
  deleteWorkflow: (id) =>
    req(`/api/workflow/${id}`, {
      method: 'DELETE'
    }),
  addWorkflowNode: (workflowId, nodeType, name, config, positionX, positionY) =>
    req(`/api/workflow/${workflowId}/nodes`, {
      method: 'POST',
      body: JSON.stringify({ node_type: nodeType, name, config, position_x: positionX, position_y: positionY })
    }),
  updateWorkflowNode: (nodeId, name, config, positionX, positionY) =>
    req(`/api/workflow/nodes/${nodeId}`, {
      method: 'PUT',
      body: JSON.stringify({ name, config, position_x: positionX, position_y: positionY })
    }),
  deleteWorkflowNode: (nodeId) =>
    req(`/api/workflow/nodes/${nodeId}`, {
      method: 'DELETE'
    }),
  addWorkflowEdge: (workflowId, sourceNodeId, targetNodeId, condition) =>
    req(`/api/workflow/${workflowId}/edges`, {
      method: 'POST',
      body: JSON.stringify({ source_node_id: sourceNodeId, target_node_id: targetNodeId, condition })
    }),
  deleteWorkflowEdge: (edgeId) =>
    req(`/api/workflow/edges/${edgeId}`, {
      method: 'DELETE'
    }),
  executeWorkflow: (workflowId, inputData = {}) =>
    req(`/api/workflow/${workflowId}/execute`, {
      method: 'POST',
      body: JSON.stringify({ input_data: inputData ?? {} }),
    }),
  /** 静态校验 + 拓扑可达性提示（不执行节点副作用） */
  workflowValidate: (workflowId) => req(`/api/workflow/${workflowId}/validate`),
  /** 沙盒运行：全链路变量快照、条件分支、可选 Mock 员工 */
  workflowSandboxRun: (workflowId, payload) =>
    req(`/api/workflow/${workflowId}/sandbox-run`, {
      method: 'POST',
      body: JSON.stringify({
        input_data: payload?.input_data ?? {},
        mock_employees: payload?.mock_employees !== false,
        validate_only: Boolean(payload?.validate_only),
      }),
    }),
  listWorkflowExecutions: (workflowId, limit = 50, offset = 0) =>
    req(`/api/workflow/${workflowId}/executions?limit=${limit}&offset=${offset}`),
  listWorkflowTriggers: (workflowId) => req(`/api/workflow/${workflowId}/triggers`),
  createWorkflowTrigger: (workflowId, payload) =>
    req(`/api/workflow/${workflowId}/triggers`, {
      method: 'POST',
      body: JSON.stringify(payload || {}),
    }),
  deleteWorkflowTrigger: (workflowId, triggerId) =>
    req(`/api/workflow/${workflowId}/triggers/${triggerId}`, { method: 'DELETE' }),
  workflowWebhookRun: (workflowId, payload = {}) =>
    req(`/api/workflow/${workflowId}/webhook-run`, {
      method: 'POST',
      body: JSON.stringify(payload ?? {}),
    }),
  getExecution: (executionId) =>
    req(`/api/workflow/executions/${executionId}`),

  notificationsList: (unreadOnly = false, limit = 50, kind = '') => {
    const q = new URLSearchParams({
      unread_only: unreadOnly ? 'true' : 'false',
      limit: String(limit),
    })
    if (kind) q.set('kind', kind)
    return req(`/api/notifications?${q}`)
  },
  notificationMarkRead: (id) => req(`/api/notifications/${id}/read`, { method: 'POST' }),
  notificationsMarkAllRead: () => req('/api/notifications/read-all', { method: 'POST' }),

  analyticsDashboard: () => req('/api/analytics/dashboard'),
  refundsApply: (orderNo, reason) =>
    req('/api/refunds/apply', {
      method: 'POST',
      body: JSON.stringify({ order_no: orderNo, reason }),
    }),
  refundsMy: () => req('/api/refunds/my'),
  
  // 员工相关API
  listEmployees: () => req('/api/employees'),
  getEmployeeStatus: (employeeId) => req(`/api/employees/${employeeId}/status`),
  executeEmployeeTask: (employeeId, task, inputData) =>
    req(`/api/employees/${employeeId}/execute`, {
      method: 'POST',
      body: JSON.stringify({ task, input_data: inputData })
    }),

  llmStatus: () => req('/api/llm/status'),
  /** 自动模式：服务端按密钥与目录解析可用 provider/model（与 /chat 一致） */
  llmResolveChatDefault: () => req('/api/llm/resolve-chat-default'),
  llmCatalog: (refresh = false) => req(`/api/llm/catalog?refresh=${refresh ? 1 : 0}`),
  llmSaveCredentials: (provider, apiKey, baseUrl = undefined) =>
    req(`/api/llm/credentials/${encodeURIComponent(provider)}`, {
      method: 'PUT',
      body: JSON.stringify({ api_key: apiKey, base_url: baseUrl ?? null }),
    }),
  llmDeleteCredentials: (provider) =>
    req(`/api/llm/credentials/${encodeURIComponent(provider)}`, { method: 'DELETE' }),
  llmSavePreferences: (provider, model) =>
    req('/api/llm/preferences', {
      method: 'PUT',
      body: JSON.stringify({ provider, model }),
    }),
  llmChat: (provider, model, messages, maxTokens = null) =>
    req('/api/llm/chat', {
      method: 'POST',
      body: JSON.stringify({
        provider,
        model,
        messages,
        max_tokens: maxTokens,
      }),
    }),

  /** 工作台：联网搜索 GitHub 公开资料摘要（供需求规划首轮拼接） */
  workbenchResearchContext: (body) =>
    req('/api/workbench/research-context', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  /** 工作台 AI 编排（Mod / 员工 / 工作流） */
  workbenchStartSession: (body) =>
    req('/api/workbench/sessions', {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  workbenchGetSession: (sessionId) =>
    req(`/api/workbench/sessions/${encodeURIComponent(sessionId)}`),
}
