import { requestJson, fetchZipBlob, requestBlob } from './infrastructure/http/client'
import { clearAuthTokens, getAccessToken, setAuthTokens } from './infrastructure/storage/tokenStore'
import type {
  PaymentCheckoutBody,
  PaymentCheckoutInput,
  PaymentCheckoutResponse,
  PaymentSignResponse,
  RefundApplyResponse,
  WorkflowSandboxRequest,
  WorkflowSandboxResponse,
} from './types/api'

const req = requestJson

export function setTokensFromAuthResponse(res: { access_token?: string; refresh_token?: string } | null | undefined) {
  setAuthTokens(res)
}

function catalogWriteHeaders(): Record<string, string> | undefined {
  const token = (import.meta.env?.VITE_MODSTORE_CATALOG_UPLOAD_TOKEN ?? '').toString().trim()
  return token ? { Authorization: `Bearer ${token}` } : undefined
}

function authHeaders(): Record<string, string> | undefined {
  const token = getAccessToken()
  return token ? { Authorization: `Bearer ${token}` } : undefined
}

async function authRequest(path: string, init: RequestInit = {}) {
  return req(path, init)
}

export const api = {
  register: async (username: string, password: string, email: string, verificationCode = '') => {
    const res = await authRequest('/api/auth/register', {
      method: 'POST',
      body: JSON.stringify({ username, password, email, verification_code: verificationCode }),
    })
    setTokensFromAuthResponse(res as any)
    return res
  },
  login: async (username: string, password: string) => {
    const res = await authRequest('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    })
    setTokensFromAuthResponse(res as any)
    return res
  },
  loginWithCode: async (email: string, code: string) => {
    const res = await authRequest('/api/auth/login-with-code', {
      method: 'POST',
      body: JSON.stringify({ email, code }),
    })
    setTokensFromAuthResponse(res as any)
    return res
  },
  sendPhoneCode: (phone: string) => req('/api/auth/send-phone-code', { method: 'POST', body: JSON.stringify({ phone }) }),
  loginWithPhoneCode: async (phone: string, code: string) => {
    const res = await authRequest('/api/auth/login-with-phone-code', {
      method: 'POST',
      body: JSON.stringify({ phone, code }),
    })
    setTokensFromAuthResponse(res as any)
    return res
  },
  me: () => req('/api/auth/me'),
  sendVerificationCode: (email: string) => req('/api/auth/send-code', { method: 'POST', body: JSON.stringify({ email }) }),
  sendRegisterVerificationCode: (email: string) => req('/api/auth/send-register-code', { method: 'POST', body: JSON.stringify({ email }) }),
  sendResetPasswordCode: (email: string) => req('/api/auth/send-reset-password-code', { method: 'POST', body: JSON.stringify({ email }) }),
  resetPassword: (email: string, code: string, newPassword: string) =>
    req('/api/auth/reset-password', { method: 'POST', body: JSON.stringify({ email, code, new_password: newPassword }) }),
  /** 落地页联系表单（匿名），写入 ``landing_contact_submissions`` */
  submitLandingContact: (data: {
    name: string
    email: string
    phone?: string
    company?: string
    message?: string
    source?: string
  }) =>
    req('/api/public/contact', {
      method: 'POST',
      body: JSON.stringify({
        name: data.name,
        email: data.email,
        phone: data.phone ?? '',
        company: data.company ?? '',
        message: data.message ?? '',
        source: data.source ?? 'home',
      }),
    }),
  updateProfile: (username: string) => req('/api/auth/profile', { method: 'PUT', body: JSON.stringify({ username }) }),
  changePassword: (currentPassword: string, newPassword: string) =>
    req('/api/auth/change-password', { method: 'POST', body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }) }),

  balance: () => req('/api/wallet/balance'),
  walletOverview: (limit = 20, offset = 0) => req(`/api/wallet/overview?limit=${limit}&offset=${offset}`),
  /** 管理员为本人钱包加款（仅 JWT，不依赖 MODSTORE_ADMIN_RECHARGE_TOKEN） */
  walletAdminSelfCredit: (amount: number, description = '') =>
    req('/api/wallet/admin-self-credit', { method: 'POST', body: JSON.stringify({ amount, description }) }),
  recharge: (amount: number, description = '') => req('/api/wallet/recharge', { method: 'POST', body: JSON.stringify({ amount, description }) }),
  transactions: (limit = 50, offset = 0) => req(`/api/wallet/transactions?limit=${limit}&offset=${offset}`),

  paymentPlans: () => req('/api/payment/plans'),
  paymentMyPlan: () => req('/api/payment/my-plan'),
  /** reconcile=true 时由后端主动调支付宝「交易查询」对账，补发异步通知未达时的权益 */
  paymentQuery: (orderId: string, options?: { reconcile?: boolean }) => {
    const r = options?.reconcile ? '?reconcile=true' : ''
    return req(`/api/payment/query/${encodeURIComponent(orderId)}${r}`)
  },
  paymentOrders: (status = '', limit = 50, offset = 0) => {
    const q = new URLSearchParams({ limit: String(limit), offset: String(offset) })
    if (status) q.set('status', status)
    return req(`/api/payment/orders?${q}`)
  },
  /** 从订单列表中隐藏已关闭/失败/已退款等，仅保留可继续处理或已支付/退款中 */
  paymentDismissNonActiveOrders: () =>
    req('/api/payment/orders/dismiss-non-active', { method: 'POST', body: '{}' }),
  paymentCancelOrder: (orderNo: string) => req(`/api/payment/cancel/${encodeURIComponent(orderNo)}`, { method: 'POST', body: '{}' }),
  paymentDiagnostics: () => req('/api/payment/diagnostics'),
  paymentEntitlements: () => req('/api/payment/entitlements'),
  paymentCheckout: async (data: PaymentCheckoutInput): Promise<PaymentCheckoutResponse> => {
    const sign = (await req('/api/payment/sign-checkout', {
      method: 'POST',
      body: JSON.stringify({
        plan_id: data?.plan_id ?? '',
        item_id: Number(data?.item_id ?? 0) || 0,
        total_amount: Number(data?.total_amount ?? 0) || 0,
        subject: data?.subject ?? '',
        wallet_recharge: Boolean(data?.wallet_recharge),
      }),
    })) as PaymentSignResponse
    const checkoutBody: PaymentCheckoutBody = {
      plan_id: sign.plan_id ?? '',
      item_id: sign.item_id ?? 0,
      total_amount: sign.total_amount ?? 0,
      subject: sign.subject ?? '',
      wallet_recharge: Boolean(sign.wallet_recharge),
      request_id: sign.request_id,
      timestamp: sign.timestamp,
      signature: sign.signature,
    }
    if (data?.pay_channel) checkoutBody.pay_channel = data.pay_channel
    if (data?.pay_type) checkoutBody.pay_type = data.pay_type
    const checkout = (await req('/api/payment/checkout', {
      method: 'POST',
      body: JSON.stringify(checkoutBody),
    })) as PaymentCheckoutResponse
    if (checkout?.ok === false) {
      return checkout
    }
    if (checkout?.ok !== true) {
      throw new Error('支付下单返回异常：缺少成功标识')
    }
    const payType = String(checkout.type || '').trim()
    if (!payType) {
      throw new Error('支付下单返回异常：缺少支付类型')
    }
    if (payType === 'page' || payType === 'wap') {
      const u = checkout.redirect_url
      if (!u || String(u).trim() === '') {
        throw new Error('支付下单返回异常：缺少跳转地址')
      }
    }
    if (payType === 'precreate' || payType === 'wechat_native') {
      const oid = checkout.order_id
      if (!oid || String(oid).trim() === '') {
        throw new Error('支付下单返回异常：缺少订单号')
      }
    }
    return checkout
  },

  refundsApply: async (orderNo: string, reason: string): Promise<RefundApplyResponse> => {
    const res = (await req('/api/refunds/apply', { method: 'POST', body: JSON.stringify({ order_no: orderNo, reason }) })) as RefundApplyResponse
    if (res?.ok === false) throw new Error(res.message || '退款申请失败')
    return res
  },
  refundsMy: () => req('/api/refunds/my'),
  refundsAdminPending: () => req('/api/refunds/admin/pending'),
  refundsAdminReview: (refundId: number, action: string, adminNote = '') =>
    req(`/api/refunds/admin/${encodeURIComponent(String(refundId))}/review`, {
      method: 'POST',
      body: JSON.stringify({ action, admin_note: adminNote }),
    }),

  catalog: (q = '', artifact = '', limit = 50, offset = 0, industry = '', securityLevel = '', materialCategory = '', licenseScope = '') => {
    const p = new URLSearchParams({ limit: String(limit), offset: String(offset) })
    if (q) p.set('q', q)
    if (artifact) p.set('artifact', artifact)
    if (industry) p.set('industry', industry)
    if (securityLevel) p.set('security_level', securityLevel)
    if (materialCategory) p.set('material_category', materialCategory)
    if (licenseScope) p.set('license_scope', licenseScope)
    return req(`/api/market/catalog?${p}`)
  },
  catalogFacets: () => req('/api/market/facets'),
  catalogDetail: (id: string | number) => req(`/api/market/catalog/${encodeURIComponent(String(id))}`),
  catalogReviews: (id: string | number) => req(`/api/market/catalog/${encodeURIComponent(String(id))}/reviews`),
  catalogSubmitReview: (id: string | number, rating: number, content = '') =>
    req(`/api/market/catalog/${encodeURIComponent(String(id))}/review`, { method: 'POST', body: JSON.stringify({ rating, content }) }),
  catalogSubmitComplaint: (id: string | number, complaintType: string, reason: string, evidence: Record<string, unknown> = {}) =>
    req(`/api/market/catalog/${encodeURIComponent(String(id))}/complaints`, {
      method: 'POST',
      body: JSON.stringify({ complaint_type: complaintType, reason, evidence }),
    }),
  catalogToggleFavorite: (id: string | number) => req(`/api/market/catalog/${encodeURIComponent(String(id))}/favorite`, { method: 'POST', body: '{}' }),
  buyItem: (id: string | number) => req(`/api/market/catalog/${encodeURIComponent(String(id))}/buy`, { method: 'POST' }),
  downloadItem: async (id: string | number) => {
    const blob = await fetchZipBlob(`/api/market/catalog/${encodeURIComponent(String(id))}/download`, authHeaders())
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `mod-${id}.zip`
    a.click()
    URL.revokeObjectURL(url)
  },
  myStore: (limit = 50, offset = 0) => req(`/api/my-store?limit=${limit}&offset=${offset}`),

  adminStatus: () => req('/api/admin/status'),
  adminResearchSettings: () => req('/api/admin/research-settings'),
  adminSaveResearchSettings: (data: Record<string, unknown>) =>
    req('/api/admin/research-settings', { method: 'PUT', body: JSON.stringify(data || {}) }),
  adminVectorSettings: () => req('/api/admin/vector-settings'),
  adminSaveVectorSettings: (data: Record<string, unknown>) =>
    req('/api/admin/vector-settings', { method: 'PUT', body: JSON.stringify(data || {}) }),
  adminUpload: (formData: FormData) => req('/api/admin/catalog', { method: 'POST', body: formData }),
  adminListCatalog: (limit = 200, offset = 0) => req(`/api/admin/catalog?limit=${limit}&offset=${offset}`),
  adminDeleteCatalog: (id: string | number) => req(`/api/admin/catalog/${encodeURIComponent(String(id))}`, { method: 'DELETE' }),
  adminDeleteEmployeePack: (pkgId: string) =>
    req(`/api/admin/employee-packs/${encodeURIComponent(pkgId)}`, { method: 'DELETE' }),
  /** 管理员一键清空：原子地把 packages.json + catalog_items 中所有 employee_pack 行清掉，
   * 替代前端循环逐条删；用于解决「员工仓库老是删不完」（两边数据源 pkg_id 不重合时单条对账会遗漏）。 */
  adminPurgeAllEmployeePacks: () =>
    req('/api/admin/employee-packs/purge-all', { method: 'POST' }),
  /** 管理员一键清空 mod 源码库：删 library/ 下所有 mod 目录 + 截断 user_mods 关联表，
   * 作为「重置仓库」的原子操作，避免前端循环单条 DELETE 因 list 缓存/关联残留导致「删不完」。 */
  adminPurgeAllMods: () => req('/api/admin/mods/purge-all', { method: 'POST' }),
  adminListCatalogComplaints: (status = '', limit = 50, offset = 0) => {
    const p = new URLSearchParams({ limit: String(limit), offset: String(offset) })
    if (status) p.set('status', status)
    return req(`/api/admin/catalog/complaints?${p}`)
  },
  adminReviewCatalogComplaint: (id: string | number, action: string, adminNote = '', extra: Record<string, unknown> = {}) =>
    req(`/api/admin/catalog/complaints/${encodeURIComponent(String(id))}/review`, {
      method: 'POST',
      body: JSON.stringify({ action, admin_note: adminNote, ...extra }),
    }),
  adminListUsers: (limit = 200, offset = 0) => req(`/api/admin/users?limit=${limit}&offset=${offset}`),
  adminSetUserAdmin: (userId: string | number, isAdmin: boolean) => req(`/api/admin/users/${userId}/admin?is_admin=${isAdmin}`, { method: 'PUT' }),
  adminListWallets: (limit = 200, offset = 0) => req(`/api/admin/wallets?limit=${limit}&offset=${offset}`),
  adminListTransactions: (limit = 200, offset = 0) => req(`/api/admin/transactions?limit=${limit}&offset=${offset}`),

  /** 传 true 时追加查询参数，避免 CDN/浏览器对 GET /api/mods 的缓存导致「删了仍显示」 */
  listMods: (cacheBust = false) => req(`/api/mods${cacheBust ? `?_=${Date.now()}` : ''}`),
  deleteMod: (modId: string) => req(`/api/mods/${encodeURIComponent(modId)}`, { method: 'DELETE' }),
  createMod: (mod_id: string, display_name: string) => req('/api/mods/create', { method: 'POST', body: JSON.stringify({ mod_id, display_name }) }),
  importZIP: (file: File, replace = true) => {
    const fd = new FormData()
    fd.append('file', file)
    return req(`/api/mods/import?replace=${replace}`, { method: 'POST', body: fd })
  },
  modAiScaffold: (brief: string, suggestedId = '', replace = true, provider?: string, model?: string) =>
    req('/api/mods/ai-scaffold', { method: 'POST', body: JSON.stringify({ brief, suggested_id: suggestedId || undefined, replace, provider, model }) }),
  push: (mod_ids: unknown = null) => req('/api/sync/push', { method: 'POST', body: JSON.stringify({ mod_ids }) }),
  pull: (mod_ids: unknown = null) => req('/api/sync/pull', { method: 'POST', body: JSON.stringify({ mod_ids }) }),
  /** 库路径、XCAGI 根目录、宿主后端 URL（与 modstore_server GET/PUT /api/config 对齐） */
  getRepoConfig: () => req('/api/config'),
  putRepoConfig: (body: { library_root?: string; xcagi_root?: string; xcagi_backend_url?: string }) =>
    req('/api/config', { method: 'PUT', body: JSON.stringify(body || {}) }),
  getMod: (modId: string) => req(`/api/mods/${encodeURIComponent(modId)}`),
  putModManifest: (modId: string, manifest: unknown) => req(`/api/mods/${encodeURIComponent(modId)}/manifest`, { method: 'PUT', body: JSON.stringify({ manifest }) }),
  getModFile: (modId: string, path: string) => req(`/api/mods/${encodeURIComponent(modId)}/file?path=${encodeURIComponent(path)}`),
  putModFile: (modId: string, path: string, content: string) => req(`/api/mods/${encodeURIComponent(modId)}/file`, { method: 'PUT', body: JSON.stringify({ path, content }) }),
  regenerateModFrontend: (modId: string, brief = '') =>
    req(`/api/mods/${encodeURIComponent(modId)}/frontend/regenerate`, { method: 'POST', body: JSON.stringify({ brief }) }),
  listModSnapshots: (modId: string) => req(`/api/mods/${encodeURIComponent(modId)}/snapshots`),
  captureModSnapshot: (modId: string, label = '') => req(`/api/mods/${encodeURIComponent(modId)}/snapshots`, { method: 'POST', body: JSON.stringify({ label }) }),
  restoreModSnapshot: (modId: string, snapId: string) => req(`/api/mods/${encodeURIComponent(modId)}/snapshots/${encodeURIComponent(snapId)}/restore`, { method: 'POST', body: '{}' }),
  bumpModManifestPatchVersion: (modId: string) => req(`/api/mods/${encodeURIComponent(modId)}/manifest/bump-patch-version`, { method: 'POST', body: '{}' }),
  modWorkflowLink: (modId: string, body: unknown) => req(`/api/mods/${encodeURIComponent(modId)}/workflow-link`, { method: 'POST', body: JSON.stringify(body) }),
  scaffoldWorkflowEmployee: (modId: string, body: unknown) => req(`/api/mods/${encodeURIComponent(modId)}/workflow-employees/scaffold`, { method: 'POST', body: JSON.stringify(body) }),
  getModAuthoringSummary: (modId: string) => req(`/api/mods/${encodeURIComponent(modId)}/authoring-summary`),
  /** Mod 内蓝图路由（供编辑器渲染节点列表 / 路由树） */
  getModBlueprintRoutes: (modId: string) => req(`/api/mods/${encodeURIComponent(modId)}/blueprint-routes`),
  /** 当前作者可用的扩展面（components / triggers / actions），可选合并宿主提供项 */
  getAuthoringExtensionSurface: (mergeHost = false) =>
    req(`/api/authoring/extension-surface?merge_host=${mergeHost ? 'true' : 'false'}`),
  /**
   * 从 Mod 的 workflow_employees[index] 生成 employee_pack 最小 zip。
   * 兼容旧路由 /export_employee_pack（下划线版本）：若新路由 404，则回退尝试一次。
   */
  exportEmployeePackZip: async (modId: string, workflowIndex = 0): Promise<Blob> => {
    const mid = String(modId || '').trim()
    const n = Number.parseInt(String(workflowIndex ?? 0), 10)
    const idx = Number.isFinite(n) && n >= 0 ? n : 0
    const q = `workflow_index=${idx}`
    const headers = authHeaders()
    const urls = [
      `/api/mods/${encodeURIComponent(mid)}/export-employee-pack?${q}`,
      `/api/mods/${encodeURIComponent(mid)}/export_employee_pack?${q}`,
    ]
    const staleHint =
      '8765 上的 API 进程里若没有该路由，会返回 Not Found。请完全退出旧进程后重启：在 MODstore_deploy 目录执行 start-modstore.bat / restart.bat，或手动运行 python -m modstore_server。自检：打开 http://127.0.0.1:8765/docs 搜索「export-employee-pack」，搜不到即仍是旧代码。'
    const looksLikeMissingRoute = (raw: string): boolean => {
      const m = String(raw || '').trim()
      if (/mod\s*不存在|Mod 不存在/i.test(m)) return false
      if (/^not found$/i.test(m)) return true
      if (m === '{"detail":"Not Found"}') return true
      try {
        const j = JSON.parse(m)
        const d = j?.detail
        if (d === 'Not Found') return true
        if (Array.isArray(d) && d.some((x: any) => String(x?.msg || '').toLowerCase() === 'not found')) return true
      } catch {
        /* ignore */
      }
      return false
    }
    let lastErr: unknown
    for (let i = 0; i < urls.length; i++) {
      try {
        return await fetchZipBlob(urls[i], headers)
      } catch (e) {
        lastErr = e
        const msg = String((e as any)?.message || '').trim()
        if (looksLikeMissingRoute(msg) && i === 0) continue
        break
      }
    }
    const base = String((lastErr as any)?.message || '导出失败').trim()
    if (looksLikeMissingRoute(base)) {
      throw new Error(`${base} — ${staleHint}`)
    }
    throw lastErr instanceof Error ? lastErr : new Error(base)
  },
  exportModZip: (modId: string) => fetchZipBlob(`/api/mods/${encodeURIComponent(modId)}/export`, authHeaders()),
  /** 沙盒审核：multipart file（.zip/.xcemp），可选 metadata JSON 含 artifact */
  auditPackage: (file: File, metadata: unknown = null) => {
    const fd = new FormData()
    fd.append('file', file)
    if (metadata != null) fd.append('metadata', JSON.stringify(metadata))
    return req('/api/package-audit', { method: 'POST', body: fd })
  },

  listV1Packages: (artifact = '', q = '', limit = 50, offset = 0, cacheBust = false) => {
    const p = new URLSearchParams({ limit: String(limit), offset: String(offset) })
    if (artifact) p.set('artifact', artifact)
    if (q) p.set('q', q)
    if (cacheBust) p.set('_', String(Date.now()))
    return req(`/v1/packages?${p}`)
  },
  listCatalogPackageVersions: (pkgId: string) => req(`/v1/packages/by-id/${encodeURIComponent(pkgId)}/versions`),
  promoteCatalogPackage: (pkgId: string, fromVersion: string) =>
    req(`/v1/packages/${encodeURIComponent(pkgId)}/promote`, { method: 'POST', body: JSON.stringify({ from_version: fromVersion }), headers: catalogWriteHeaders() }),
  downloadCatalogPackageBlob: (pkgId: string, version: string) => fetchZipBlob(`/v1/packages/${encodeURIComponent(pkgId)}/${encodeURIComponent(version)}/download`),
  uploadPackage: (metadata: unknown, file: File) => {
    const fd = new FormData()
    fd.append('metadata', JSON.stringify(metadata))
    fd.append('file', file)
    return req('/v1/packages', { method: 'POST', body: fd, headers: catalogWriteHeaders() })
  },
  registerWorkflowEmployeeCatalog: (modId: string, workflowIndex = 0, opts: { industry?: string; price?: number; release_channel?: string } = {}) =>
    req(`/api/mods/${encodeURIComponent(modId)}/register-workflow-employee-catalog`, {
      method: 'POST',
      body: JSON.stringify({ workflow_index: workflowIndex, industry: opts.industry || '通用', price: opts.price ?? 0, release_channel: opts.release_channel || 'stable' }),
    }),
  /** 再次对齐画布 employee 节点与 manifest 推导的 pack id（可补 start/end 骨架） */
  patchModWorkflowEmployeeNodes: (modId: string) =>
    req(`/api/mods/${encodeURIComponent(modId)}/patch-workflow-employee-nodes`, { method: 'POST' }),

  /** 员工上架：LLM 生成 1-5 级测试任务 → 执行 → 量化打分 → 五维审核 */
  employeeBenchTest: (employeeId: string, provider?: string, model?: string) =>
    req('/api/workbench/employee-bench-test', {
      method: 'POST',
      body: JSON.stringify({ employee_id: employeeId, provider: provider || null, model: model || null }),
    }),

  /** 员工上架：bench 通过后写入 catalog_store + catalog_items */
  employeePublish: (employeeId: string, opts?: { price?: number; industry?: string; release_channel?: string }) =>
    req('/api/workbench/employee-publish', {
      method: 'POST',
      body: JSON.stringify({ employee_id: employeeId, ...(opts || {}) }),
    }),

  /**
   * 员工同步测试：bench → 发布到 catalog → 推送到宿主 fhd-sandbox-runtime /api/mod-store/install
   * 成功后员工出现在宿主「一键托管」面板
   */
  employeeSyncTest: (employeeId: string, fhdBaseUrl?: string, provider?: string, model?: string) =>
    req('/api/workbench/employee-sync-test', {
      method: 'POST',
      body: JSON.stringify({
        employee_id: employeeId,
        fhd_base_url: fhdBaseUrl || null,
        provider: provider || null,
        model: model || null,
      }),
    }),

  // ----- 脚本即工作流（替代节点图）-----
  listScriptWorkflows: (status: string = '') =>
    req(`/api/script-workflows${status ? `?status=${encodeURIComponent(status)}` : ''}`),
  getScriptWorkflow: (id: number | string) => req(`/api/script-workflows/${id}`),
  updateScriptWorkflow: (id: number | string, body: Record<string, unknown>) =>
    req(`/api/script-workflows/${id}`, { method: 'PUT', body: JSON.stringify(body) }),
  deleteScriptWorkflow: (id: number | string) =>
    req(`/api/script-workflows/${id}`, { method: 'DELETE' }),
  sandboxRunScriptWorkflow: (id: number | string, files: File[]) => {
    const fd = new FormData()
    files.forEach((f) => fd.append('files', f))
    return req(`/api/script-workflows/${id}/sandbox-run`, { method: 'POST', body: fd })
  },
  runScriptWorkflow: (id: number | string, files: File[]) => {
    const fd = new FormData()
    files.forEach((f) => fd.append('files', f))
    return req(`/api/script-workflows/${id}/run`, { method: 'POST', body: fd })
  },
  activateScriptWorkflow: (id: number | string) =>
    req(`/api/script-workflows/${id}/activate`, { method: 'POST' }),
  deactivateScriptWorkflow: (id: number | string) =>
    req(`/api/script-workflows/${id}/deactivate`, { method: 'POST' }),
  listScriptWorkflowRuns: (id: number | string, mode: string = '') =>
    req(`/api/script-workflows/${id}/runs${mode ? `?mode=${encodeURIComponent(mode)}` : ''}`),
  downloadScriptWorkflowRunFile: async (id: number | string, runId: number | string, filename: string) => {
    const res = await fetch(
      `/api/script-workflows/${encodeURIComponent(String(id))}/runs/${encodeURIComponent(String(runId))}/files/${encodeURIComponent(filename)}`,
      { headers: authHeaders() },
    )
    if (!res.ok) {
      throw new Error(res.statusText || '下载失败')
    }
    return res.blob()
  },
  listScriptWorkflowVersions: (id: number | string) =>
    req(`/api/script-workflows/${id}/versions`),
  commitScriptWorkflowSession: (sid: string, body: { name: string; schema_in?: Record<string, unknown> }) =>
    req(`/api/script-workflows/sessions/${encodeURIComponent(sid)}/commit`, {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  getScriptWorkflowSession: (sid: string) =>
    req(`/api/script-workflows/sessions/${encodeURIComponent(sid)}`),

  listWorkflows: () => req('/api/workflow/'),
  listESkills: () => req('/api/eskills'),
  createESkill: (body: unknown) => req('/api/eskills', { method: 'POST', body: JSON.stringify(body || {}) }),
  runESkill: (id: string | number, body: unknown) => req(`/api/eskills/${id}/run`, { method: 'POST', body: JSON.stringify(body || {}) }),
  listEmployeeEligibleWorkflows: () => req('/api/workflow/employee-eligible'),
  listWorkflowsByEmployee: (employeeId: string) => req(`/api/workflow/by-employee?employee_id=${encodeURIComponent(employeeId)}`),
  getWorkflow: (id: string | number) => req(`/api/workflow/${id}`),
  createWorkflow: (name: string, description: string) => req('/api/workflow/', { method: 'POST', body: JSON.stringify({ name, description }) }),
  updateWorkflow: (id: string | number, name: string | null, description: string | null, isActive: boolean) => req(`/api/workflow/${id}`, { method: 'PUT', body: JSON.stringify({ name, description, is_active: isActive }) }),
  deleteWorkflow: (id: string | number) => req(`/api/workflow/${id}`, { method: 'DELETE' }),
  addWorkflowNode: (workflowId: string | number, nodeType: string, name: string, config: unknown, positionX: number, positionY: number) =>
    req(`/api/workflow/${workflowId}/nodes`, { method: 'POST', body: JSON.stringify({ node_type: nodeType, name, config, position_x: positionX, position_y: positionY }) }),
  updateWorkflowNode: (nodeId: string | number, name: string, config: unknown, positionX: number, positionY: number) =>
    req(`/api/workflow/nodes/${nodeId}`, { method: 'PUT', body: JSON.stringify({ name, config, position_x: positionX, position_y: positionY }) }),
  deleteWorkflowNode: (nodeId: string | number) => req(`/api/workflow/nodes/${nodeId}`, { method: 'DELETE' }),
  addWorkflowEdge: (workflowId: string | number, sourceNodeId: unknown, targetNodeId: unknown, condition = '') =>
    req(`/api/workflow/${workflowId}/edges`, { method: 'POST', body: JSON.stringify({ source_node_id: sourceNodeId, target_node_id: targetNodeId, condition }) }),
  deleteWorkflowEdge: (edgeId: string | number) => req(`/api/workflow/edges/${edgeId}`, { method: 'DELETE' }),
  executeWorkflow: (workflowId: string | number, inputData = {}) => req(`/api/workflow/${workflowId}/execute`, { method: 'POST', body: JSON.stringify({ input_data: inputData }) }),
  workflowValidate: (workflowId: string | number) => req(`/api/workflow/${workflowId}/validate`),
  workflowSandboxRun: (workflowId: string | number, payload: WorkflowSandboxRequest): Promise<WorkflowSandboxResponse> => req(`/api/workflow/${workflowId}/sandbox-run`, { method: 'POST', body: JSON.stringify(payload || {}) }),
  listWorkflowExecutions: (workflowId: string | number, limit = 50, offset = 0) => req(`/api/workflow/${workflowId}/executions?limit=${limit}&offset=${offset}`),
  listWorkflowTriggers: (workflowId: string | number) => req(`/api/workflow/${workflowId}/triggers`),
  createWorkflowTrigger: (workflowId: string | number, payload: unknown) => req(`/api/workflow/${workflowId}/triggers`, { method: 'POST', body: JSON.stringify(payload || {}) }),
  deleteWorkflowTrigger: (workflowId: string | number, triggerId: string | number) => req(`/api/workflow/${workflowId}/triggers/${triggerId}`, { method: 'DELETE' }),
  workflowWebhookRun: (workflowId: string | number, payload = {}) => req(`/api/workflow/${workflowId}/webhook-run`, { method: 'POST', body: JSON.stringify(payload) }),
  publishWorkflowVersion: (workflowId: string | number, note = '') =>
    req(`/api/workflow/${workflowId}/versions/publish`, { method: 'POST', body: JSON.stringify({ note }) }),
  listWorkflowVersions: (workflowId: string | number, limit = 50, offset = 0) =>
    req(`/api/workflow/${workflowId}/versions?limit=${limit}&offset=${offset}`),
  getWorkflowVersion: (workflowId: string | number, versionId: string | number) =>
    req(`/api/workflow/${workflowId}/versions/${versionId}`),
  rollbackWorkflowVersion: (workflowId: string | number, versionId: string | number) =>
    req(`/api/workflow/${workflowId}/versions/${versionId}/rollback`, { method: 'POST' }),
  getExecution: (executionId: string | number) => req(`/api/workflow/executions/${executionId}`),

  // 开发者门户：Personal Access Token
  developerListTokens: () => req('/api/developer/tokens'),
  developerCreateToken: (name: string, scopes: string[] = [], expiresDays: number | null = null) =>
    req('/api/developer/tokens', {
      method: 'POST',
      body: JSON.stringify({ name, scopes, expires_days: expiresDays }),
    }),
  developerRevokeToken: (tokenId: string | number) =>
    req(`/api/developer/tokens/${tokenId}`, { method: 'DELETE' }),

  developerExportKeyBundle: (payload: {
    recipient_public_key_spki_b64: string
    current_password: string
    token_ids: number[]
    rotate_source_tokens?: boolean
  }) =>
    req('/api/developer/key-export/bundle', {
      method: 'POST',
      body: JSON.stringify({
        recipient_public_key_spki_b64: payload.recipient_public_key_spki_b64,
        current_password: payload.current_password,
        token_ids: payload.token_ids,
        rotate_source_tokens: payload.rotate_source_tokens !== false,
      }),
    }),
  developerListKeyExportAudit: (limit = 50) =>
    req(`/api/developer/key-export/audit?limit=${encodeURIComponent(String(limit))}`),

  // 开发者门户：Webhook 订阅
  developerWebhookEventCatalog: () => req('/api/developer/webhooks/event-catalog'),
  developerListWebhooks: () => req('/api/developer/webhooks'),
  developerCreateWebhook: (payload: {
    name: string
    target_url: string
    secret?: string
    enabled_events?: string[]
    description?: string
    is_active?: boolean
  }) => req('/api/developer/webhooks', { method: 'POST', body: JSON.stringify(payload) }),
  developerUpdateWebhook: (
    id: string | number,
    payload: {
      name?: string
      target_url?: string
      secret?: string
      enabled_events?: string[]
      description?: string
      is_active?: boolean
    },
  ) => req(`/api/developer/webhooks/${id}`, { method: 'PUT', body: JSON.stringify(payload) }),
  developerDeleteWebhook: (id: string | number) =>
    req(`/api/developer/webhooks/${id}`, { method: 'DELETE' }),
  developerListWebhookDeliveries: (
    id: string | number,
    opts: { limit?: number; offset?: number; status?: string } = {},
  ) => {
    const p = new URLSearchParams()
    if (opts.limit) p.set('limit', String(opts.limit))
    if (opts.offset) p.set('offset', String(opts.offset))
    if (opts.status) p.set('status', opts.status)
    const qs = p.toString()
    return req(`/api/developer/webhooks/${id}/deliveries${qs ? `?${qs}` : ''}`)
  },
  developerRetryWebhookDelivery: (deliveryId: string | number) =>
    req(`/api/developer/webhooks/deliveries/${deliveryId}/retry`, { method: 'POST' }),
  developerTestWebhook: (id: string | number) =>
    req(`/api/developer/webhooks/${id}/test`, { method: 'POST' }),

  // 模板市场
  templatesList: (
    opts: { q?: string; category?: string; difficulty?: string; sort?: string; limit?: number; offset?: number } = {},
  ) => {
    const p = new URLSearchParams()
    if (opts.q) p.set('q', opts.q)
    if (opts.category) p.set('category', opts.category)
    if (opts.difficulty) p.set('difficulty', opts.difficulty)
    if (opts.sort) p.set('sort', opts.sort)
    if (opts.limit) p.set('limit', String(opts.limit))
    if (opts.offset) p.set('offset', String(opts.offset))
    return req(`/api/templates${p.toString() ? '?' + p.toString() : ''}`)
  },
  templatesCategories: () => req('/api/templates/categories'),
  templateDetail: (id: string | number) => req(`/api/templates/${encodeURIComponent(String(id))}`),
  templateInstall: (id: string | number) =>
    req(`/api/templates/${encodeURIComponent(String(id))}/install`, { method: 'POST' }),
  saveWorkflowAsTemplate: (
    workflowId: string | number,
    payload: {
      name: string
      description?: string
      template_category?: string
      template_difficulty?: string
      price?: number
      is_public?: boolean
      industry?: string
    },
  ) =>
    req(`/api/templates/from-workflow/${workflowId}`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  notificationsList: (unreadOnly = false, limit = 50, kind = '') => {
    const p = new URLSearchParams({ unread_only: unreadOnly ? 'true' : 'false', limit: String(limit) })
    if (kind) p.set('kind', kind)
    return req(`/api/notifications/?${p}`)
  },
  notificationMarkRead: (id: string | number) => req(`/api/notifications/${id}/read`, { method: 'POST' }),
  notificationsMarkAllRead: () => req('/api/notifications/read-all', { method: 'POST' }),
  analyticsDashboard: () => req('/api/analytics/dashboard'),

  listEmployees: () => req('/api/employees/'),
  getEmployeeStatus: (employeeId: string) => req(`/api/employees/${encodeURIComponent(employeeId)}/status`),
  getEmployeeManifest: (employeeId: string) => req(`/api/employees/${encodeURIComponent(employeeId)}/manifest`),
  executeEmployeeTask: (employeeId: string, task: string, inputData: unknown) =>
    req(`/api/employees/${employeeId}/execute`, { method: 'POST', body: JSON.stringify({ task, input_data: inputData }) }),

  llmStatus: () => req('/api/llm/status'),
  llmResolveChatDefault: () => req('/api/llm/resolve-chat-default'),
  llmCatalog: (refresh = false) => req(`/api/llm/catalog?refresh=${refresh ? 1 : 0}`),
  llmSaveCredentials: (provider: string, apiKey: string, baseUrl?: string | null) => req(`/api/llm/credentials/${encodeURIComponent(provider)}`, { method: 'PUT', body: JSON.stringify({ api_key: apiKey, base_url: baseUrl ?? null }) }),
  llmDeleteCredentials: (provider: string) => req(`/api/llm/credentials/${encodeURIComponent(provider)}`, { method: 'DELETE' }),
  llmSavePreferences: (provider: string, model: string) => req('/api/llm/preferences', { method: 'PUT', body: JSON.stringify({ provider, model }) }),
  llmPricing: () => req('/api/llm/pricing'),
  llmUsage: (limit = 50, offset = 0) => req(`/api/llm/usage?limit=${limit}&offset=${offset}`),
  llmConversations: (limit = 30, offset = 0) => req(`/api/llm/conversations?limit=${limit}&offset=${offset}`),
  llmConversationDetail: (id: string | number) => req(`/api/llm/conversations/${encodeURIComponent(String(id))}`),
  llmAdminSavePrice: (data: Record<string, unknown>) => req('/api/llm/admin/pricing', { method: 'PUT', body: JSON.stringify(data || {}) }),
  llmAdminModelCapabilities: (opts?: { provider?: string; q?: string; limit?: number }) => {
    const p = new URLSearchParams()
    if (opts?.provider) p.set('provider', opts.provider)
    if (opts?.q) p.set('q', opts.q)
    if (opts?.limit != null) p.set('limit', String(opts.limit))
    const qs = p.toString()
    return req(`/api/llm/admin/model-capabilities${qs ? `?${qs}` : ''}`)
  },
  llmAdminModelCapabilityReview: (body: { provider: string; model: string; l3_status: string; notes?: string }) =>
    req('/api/llm/admin/model-capabilities/review', { method: 'PUT', body: JSON.stringify(body) }),
  llmChat: async (
    provider: string,
    model: string,
    messages: unknown[],
    maxTokens: number | null = null,
    conversationId: number | null = null,
  ) => {
    const res = (await req('/api/llm/chat', {
      method: 'POST',
      body: JSON.stringify({ provider, model, messages, max_tokens: maxTokens, conversation_id: conversationId }),
    })) as { billed?: boolean; charge_amount?: number }
    if (res && (res.billed === true || (Number(res.charge_amount) || 0) > 0)) {
      void import('./utils/llmBillingRefresh').then((m) => m.refreshLevelAndWalletAfterLlm())
    }
    return res
  },
  llmChatStream: (provider: string, model: string, messages: unknown[], maxTokens: number | null = null, conversationId: number | null = null, signal?: AbortSignal) => {
    const headers = new Headers(authHeaders())
    headers.set('Content-Type', 'application/json')
    headers.set('Accept', 'text/event-stream')
    return fetch('/api/llm/chat/stream', {
      method: 'POST',
      headers,
      signal,
      body: JSON.stringify({ provider, model, messages, max_tokens: maxTokens, conversation_id: conversationId }),
    })
  },
  llmGenerateImage: (provider: string, model: string, prompt: string, opts: { size?: string; count?: number; n?: number } = {}) =>
    req('/api/llm/image', {
      method: 'POST',
      body: JSON.stringify({
        provider,
        model,
        prompt,
        size: opts.size || '1024x1024',
        n: opts.count || opts.n || 1,
      }),
    }),
  llmGeneratePptxBlob: async (title: string, markdown: string, filename = 'ai-presentation.pptx') => {
    const headers = new Headers(authHeaders())
    headers.set('Content-Type', 'application/json')
    const res = await fetch('/api/llm/pptx', {
      method: 'POST',
      headers,
      body: JSON.stringify({ title, markdown, filename }),
    })
    const buf = await res.arrayBuffer()
    if (!res.ok) {
      let message = res.statusText || '生成 PPT 失败'
      try {
        const text = new TextDecoder().decode(buf)
        const data = JSON.parse(text)
        message = data?.detail || data?.message || message
      } catch {
        /* ignore */
      }
      throw new Error(message)
    }
    return new Blob([buf], { type: 'application/vnd.openxmlformats-officedocument.presentationml.presentation' })
  },
  workbenchResearchContext: (body: unknown) => req('/api/workbench/research-context', { method: 'POST', body: JSON.stringify(body) }),
  workbenchStartSession: (body: unknown) => req('/api/workbench/sessions', { method: 'POST', body: JSON.stringify(body) }),
  /**
   * 工作台三档对话中的即席文件处理（Canvas Skill 模式）。
   * 轮询方式，结果通过 workbenchGetSession 查询，不持久化到数据库。
   *
   * ⚠️ 与 /api/script-workflows/sessions（SSE）是两条独立产品线：
   *   - workbenchStartScriptSession → 即席、一次性、在工作台内完成
   *   - /api/script-workflows/sessions → ScriptWorkflowComposerView 中创建可复用的命名工作流，结果持久化到 script_workflows 表
   */
  workbenchStartScriptSession: (metadata: unknown, files: File[]) => {
    const fd = new FormData()
    fd.append('metadata', JSON.stringify(metadata || {}))
    for (const f of files || []) fd.append('files', f)
    return req('/api/workbench/script-sessions', { method: 'POST', body: fd })
  },
  workbenchGetSession: (sessionId: string) => req(`/api/workbench/sessions/${encodeURIComponent(sessionId)}`),

  /**
   * 启动 6 阶段 AI 员工生成流水线（SSE）。
   * 返回原生 Response 对象，调用方通过 `useEmployeeAiDraft` composable 消费。
   * 与 workbenchStartSession/workbenchGetSession（轮询）完全独立，不互相干扰。
   */
  streamEmployeeAiDraft: (
    brief: string,
    opts?: { provider?: string; model?: string; suggestedId?: string },
  ): Promise<Response> =>
    fetch('/api/workbench/employee-ai/draft', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        brief,
        provider: opts?.provider || undefined,
        model: opts?.model || undefined,
        suggested_id: opts?.suggestedId || undefined,
      }),
    }),

  /** LLM 优化 system prompt，返回 {improved_prompt, diff_explanation}。 */
  refineSystemPrompt: (body: {
    current_prompt: string
    instruction: string
    role_context?: string
    provider?: string
    model?: string
  }) =>
    req('/api/workbench/employee-ai/refine-prompt', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  /** 微软在线神经 TTS（服务端 edge-tts），返回 MP3 Blob */
  workbenchEdgeTts: (text: string, voice?: string, rate?: number) =>
    requestBlob('/api/workbench/tts/edge', {
      method: 'POST',
      body: JSON.stringify({
        text,
        ...(voice ? { voice } : {}),
        ...(rate != null && Number.isFinite(rate) ? { rate } : {}),
      }),
    }),

  knowledgeStatus: () => req('/api/knowledge/status'),
  knowledgeListDocuments: () => req('/api/knowledge/documents'),
  knowledgeUploadDocument: (file: File, opts?: { embeddingProvider?: string; embeddingModel?: string }) => {
    const form = new FormData()
    form.append('file', file)
    if (opts?.embeddingProvider) form.append('embedding_provider', opts.embeddingProvider)
    if (opts?.embeddingModel) form.append('embedding_model', opts.embeddingModel)
    return req('/api/knowledge/documents', { method: 'POST', body: form })
  },
  knowledgeDeleteDocument: (docId: string) => req(`/api/knowledge/documents/${encodeURIComponent(docId)}`, { method: 'DELETE' }),
  knowledgeExtractText: (file: File) => {
    const form = new FormData()
    form.append('file', file)
    return req('/api/knowledge/extract-text', { method: 'POST', body: form })
  },
  knowledgeSearch: (query: string, limit = 6, opts?: { embeddingProvider?: string; embeddingModel?: string }) =>
    req('/api/knowledge/search', {
      method: 'POST',
      body: JSON.stringify({
        query,
        limit,
        embedding_provider: opts?.embeddingProvider,
        embedding_model: opts?.embeddingModel,
      }),
    }),

  // v2: 集合 + 共享 + 跨上下文检索
  knowledgeV2Status: () => req('/api/knowledge/v2/status'),
  knowledgeV2ListCollections: (params?: { ownerKind?: string; ownerId?: string }) => {
    const qs: string[] = []
    if (params?.ownerKind) qs.push(`owner_kind=${encodeURIComponent(params.ownerKind)}`)
    if (params?.ownerId !== undefined && params?.ownerId !== null)
      qs.push(`owner_id=${encodeURIComponent(String(params.ownerId))}`)
    const suffix = qs.length ? `?${qs.join('&')}` : ''
    return req(`/api/knowledge/v2/collections${suffix}`)
  },
  knowledgeV2CreateCollection: (body: {
    owner_kind?: string
    owner_id?: string
    name: string
    description?: string
    visibility?: string
    embedding_model?: string
    embedding_dim?: number
  }) => req('/api/knowledge/v2/collections', { method: 'POST', body: JSON.stringify(body) }),
  knowledgeV2UpdateCollection: (
    id: number,
    body: { name?: string; description?: string; visibility?: string },
  ) =>
    req(`/api/knowledge/v2/collections/${encodeURIComponent(String(id))}`, {
      method: 'PATCH',
      body: JSON.stringify(body),
    }),
  knowledgeV2DeleteCollection: (id: number) =>
    req(`/api/knowledge/v2/collections/${encodeURIComponent(String(id))}`, { method: 'DELETE' }),
  knowledgeV2ListDocuments: (id: number) =>
    req(`/api/knowledge/v2/collections/${encodeURIComponent(String(id))}/documents`),
  knowledgeV2UploadDocument: (id: number, file: File, opts?: { embeddingProvider?: string; embeddingModel?: string }) => {
    const form = new FormData()
    form.append('file', file)
    if (opts?.embeddingProvider) form.append('embedding_provider', opts.embeddingProvider)
    if (opts?.embeddingModel) form.append('embedding_model', opts.embeddingModel)
    return req(
      `/api/knowledge/v2/collections/${encodeURIComponent(String(id))}/documents`,
      { method: 'POST', body: form },
    )
  },
  knowledgeV2DeleteDocument: (id: number, docId: string) =>
    req(
      `/api/knowledge/v2/collections/${encodeURIComponent(String(id))}/documents/${encodeURIComponent(docId)}`,
      { method: 'DELETE' },
    ),
  knowledgeV2ShareCollection: (
    id: number,
    body: { grantee_kind: string; grantee_id: string; permission?: string },
  ) =>
    req(`/api/knowledge/v2/collections/${encodeURIComponent(String(id))}/share`, {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  knowledgeV2Unshare: (id: number, membershipId: number) =>
    req(
      `/api/knowledge/v2/collections/${encodeURIComponent(String(id))}/share/${encodeURIComponent(String(membershipId))}`,
      { method: 'DELETE' },
    ),
  knowledgeV2Retrieve: (body: {
    query: string
    top_k?: number
    min_score?: number
    employee_id?: string | null
    workflow_id?: number | null
    org_id?: string | null
    collection_ids?: number[]
    embedding_provider?: string | null
    embedding_model?: string | null
  }) => req('/api/knowledge/v2/retrieve', { method: 'POST', body: JSON.stringify(body) }),

  openApiListConnectors: () => req('/api/openapi-connectors/'),
  openApiGetConnector: (id: number | string) => req(`/api/openapi-connectors/${encodeURIComponent(String(id))}`),
  openApiImportConnector: (payload: unknown) =>
    req('/api/openapi-connectors/import', { method: 'POST', body: JSON.stringify(payload) }),
  openApiDeleteConnector: (id: number | string) =>
    req(`/api/openapi-connectors/${encodeURIComponent(String(id))}`, { method: 'DELETE' }),
  openApiSaveCredentials: (id: number | string, authType: string, config: unknown) =>
    req(`/api/openapi-connectors/${encodeURIComponent(String(id))}/credentials`, {
      method: 'PUT',
      body: JSON.stringify({ auth_type: authType, config }),
    }),
  openApiDeleteCredentials: (id: number | string) =>
    req(`/api/openapi-connectors/${encodeURIComponent(String(id))}/credentials`, { method: 'DELETE' }),
  openApiToggleOperation: (id: number | string, operationId: string, enabled: boolean) =>
    req(
      `/api/openapi-connectors/${encodeURIComponent(String(id))}/operations/${encodeURIComponent(operationId)}`,
      { method: 'PATCH', body: JSON.stringify({ enabled }) },
    ),
  openApiTestOperation: (id: number | string, operationId: string, payload: unknown) =>
    req(
      `/api/openapi-connectors/${encodeURIComponent(String(id))}/operations/${encodeURIComponent(operationId)}/test`,
      { method: 'POST', body: JSON.stringify(payload || {}) },
    ),
  openApiPublishWorkflowNode: (id: number | string, payload: unknown) =>
    req(`/api/openapi-connectors/${encodeURIComponent(String(id))}/publish-workflow-node`, {
      method: 'POST',
      body: JSON.stringify(payload || {}),
    }),
  openApiListLogs: (id: number | string, limit = 50, offset = 0) =>
    req(`/api/openapi-connectors/${encodeURIComponent(String(id))}/logs?limit=${limit}&offset=${offset}`),

  customerServiceChat: (payload: { message: string; session_id?: number | null; context?: Record<string, unknown> }) =>
    req('/api/customer-service/chat', { method: 'POST', body: JSON.stringify(payload) }),
  customerServiceSessions: () => req('/api/customer-service/sessions'),
  customerServiceSessionDetail: (id: number | string) =>
    req(`/api/customer-service/sessions/${encodeURIComponent(String(id))}`),
  customerServiceTickets: (status = '') =>
    req(`/api/customer-service/tickets${status ? `?status=${encodeURIComponent(status)}` : ''}`),
  customerServiceTicketDetail: (id: number | string) =>
    req(`/api/customer-service/tickets/${encodeURIComponent(String(id))}`),
  customerServiceActions: (ticketId?: number | string) =>
    req(`/api/customer-service/actions${ticketId ? `?ticket_id=${encodeURIComponent(String(ticketId))}` : ''}`),
  customerServiceStandards: () => req('/api/customer-service/standards'),
  customerServiceCreateStandard: (payload: unknown) =>
    req('/api/customer-service/standards', { method: 'POST', body: JSON.stringify(payload || {}) }),
  customerServiceUpdateStandard: (id: number | string, payload: unknown) =>
    req(`/api/customer-service/standards/${encodeURIComponent(String(id))}`, {
      method: 'PUT',
      body: JSON.stringify(payload || {}),
    }),
  customerServiceIntegrations: () => req('/api/customer-service/integrations'),
  customerServiceCreateIntegration: (payload: unknown) =>
    req('/api/customer-service/integrations', { method: 'POST', body: JSON.stringify(payload || {}) }),
  customerServiceUpdateIntegration: (id: number | string, payload: unknown) =>
    req(`/api/customer-service/integrations/${encodeURIComponent(String(id))}`, {
      method: 'PUT',
      body: JSON.stringify(payload || {}),
    }),

  // ─── AI 数字管家 Butler ─────────────────────────────────────────────
  /** POST /api/agent/butler/chat — 发送对话（非流式） */
  agentButlerChat: (payload: {
    messages: unknown[]
    conversation_id?: number | null
    page_context?: string
  }) =>
    req('/api/agent/butler/chat', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  /** POST /api/agent/butler/chat/stream — SSE 流式对话 */
  agentButlerChatStream: (
    payload: {
      messages: unknown[]
      conversation_id?: number | null
      page_context?: string
    },
    signal?: AbortSignal,
  ) => {
    const headers = new Headers(authHeaders())
    headers.set('Content-Type', 'application/json')
    headers.set('Accept', 'text/event-stream')
    return fetch('/api/agent/butler/chat/stream', {
      method: 'POST',
      headers,
      signal,
      body: JSON.stringify(payload),
    })
  },

  /** GET /api/agent/butler/skills — 获取 butler 类型的技能列表 */
  listButlerSkills: () => req('/api/agent/butler/skills'),

  /** POST /api/agent/butler/actions — 记录操作审计 */
  recordButlerAction: (payload: {
    route: string
    action: string
    args?: Record<string, unknown>
    risk: string
    status: 'success' | 'failed' | 'cancelled'
  }) =>
    req('/api/agent/butler/actions', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  /** PATCH /api/agent/butler/skills/:id — 更新技能激活状态 */
  updateButlerSkillActive: (id: number | string, isActive: boolean) =>
    req(`/api/agent/butler/skills/${encodeURIComponent(String(id))}`, {
      method: 'PATCH',
      body: JSON.stringify({ is_active: isActive }),
    }),

  /**
   * POST /api/agent/butler/orchestrate — 启动 vibe-coding 改写管线。
   * 返回 { session_id, status }，进度通过 workbenchGetSession 轮询。
   */
  butlerOrchestrateStart: (payload: {
    target_type: 'mod' | 'workflow' | 'employee'
    target_id: string
    brief: string
    scope?: string
    focus_paths?: string[]
    with_snapshot?: boolean
    provider?: string
    model?: string
  }) =>
    req('/api/agent/butler/orchestrate', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
}

export { clearAuthTokens }
export * from './application'
