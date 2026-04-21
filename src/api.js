const BASE = 'http://127.0.0.1:8765'

function getToken() {
  return localStorage.getItem('modstore_token') || ''
}

async function req(path, opts = {}) {
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
  const r = await fetch(`${BASE}${path}`, { ...opts, method, headers, body })
  const text = await r.text()
  let data = null
  try { data = text ? JSON.parse(text) : null } catch { data = { detail: text || r.statusText } }
  if (!r.ok) {
    const d = data?.detail
    let msg
    if (Array.isArray(d)) msg = d.map(x => x.msg || JSON.stringify(x)).join('; ')
    else if (typeof d === 'string') msg = d
    else if (d && typeof d === 'object') msg = JSON.stringify(d)
    else msg = r.statusText
    throw new Error(msg)
  }
  return data
}

export const api = {
  register: (username, password, email, verificationCode = '') =>
    req('/api/auth/register', {
      method: 'POST',
      body: JSON.stringify({
        username,
        password,
        email,
        verification_code: verificationCode,
      }),
    }),
  login: (username, password) =>
    req('/api/auth/login', { method: 'POST', body: JSON.stringify({ username, password }) }),
  me: () => req('/api/auth/me'),

  sendVerificationCode: (email) =>
    req('/api/auth/send-code', { method: 'POST', body: JSON.stringify({ email }) }),
  sendRegisterVerificationCode: (email) =>
    req('/api/auth/send-register-code', { method: 'POST', body: JSON.stringify({ email }) }),
  loginWithCode: (email, code) =>
    req('/api/auth/login-with-code', { method: 'POST', body: JSON.stringify({ email, code }) }),

  balance: () => req('/api/wallet/balance'),
  recharge: (amount, description) =>
    req('/api/wallet/recharge', { method: 'POST', body: JSON.stringify({ amount, description }) }),
  transactions: (limit = 50, offset = 0) =>
    req(`/api/wallet/transactions?limit=${limit}&offset=${offset}`),

  catalog: (q = '', artifact = '', limit = 50, offset = 0, industry = '') => {
    let url = `/api/market/catalog?limit=${limit}&offset=${offset}`
    if (q) url += `&q=${encodeURIComponent(q)}`
    if (artifact) url += `&artifact=${encodeURIComponent(artifact)}`
    if (industry) url += `&industry=${encodeURIComponent(industry)}`
    return req(url)
  },
  catalogFacets: () => req('/api/market/facets'),
  catalogDetail: (id) => req(`/api/market/catalog/${id}`),
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
  paymentCheckout: (data) =>
    req('/api/payment/checkout', { method: 'POST', body: JSON.stringify(data) }),
  paymentQuery: (orderId) => req(`/api/payment/query/${orderId}`),
  paymentOrders: (status = '', limit = 50, offset = 0) => {
    let url = `/api/payment/orders?limit=${limit}&offset=${offset}`
    if (status) url += `&status=${encodeURIComponent(status)}`
    return req(url)
  },
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
  getModFile: (modId, path) =>
    req(`/api/mods/${encodeURIComponent(modId)}/file?path=${encodeURIComponent(path)}`),
  putModFile: (modId, path, content) =>
    req(`/api/mods/${encodeURIComponent(modId)}/file`, {
      method: 'PUT',
      body: JSON.stringify({ path, content }),
    }),
  getModAuthoringSummary: (modId) =>
    req(`/api/mods/${encodeURIComponent(modId)}/authoring-summary`),
  getModBlueprintRoutes: (modId) =>
    req(`/api/mods/${encodeURIComponent(modId)}/blueprint-routes`),
  getAuthoringExtensionSurface: (mergeHost = false) =>
    req(`/api/authoring/extension-surface?merge_host=${mergeHost ? 'true' : 'false'}`),
}
