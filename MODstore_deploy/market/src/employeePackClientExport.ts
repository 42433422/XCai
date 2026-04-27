/**
 * 浏览器端从 Mod manifest 快照 + workflow_employees 单条 JSON 生成 employee_pack zip，
 * 与 modstore_server.employee_pack_export 行为对齐，供 API 不可用时兜底。
 */
import { strToU8, zipSync } from 'fflate'

const ID_RE = /^[a-z0-9][a-z0-9._-]*$/

export function normalizeModId(s) {
  const x = String(s || '')
    .trim()
    .toLowerCase()
  if (!x || !ID_RE.test(x)) return null
  return x
}

function slugId(raw, fallback) {
  let x = String(raw || '')
    .trim()
    .toLowerCase()
  x = x.replace(/[^a-z0-9._-]+/g, '-')
  x = x.replace(/-+/g, '-').replace(/^-|-$/g, '')
  if (!x) x = fallback
  if (x && !/^[a-z0-9]/i.test(x)) x = `x${x}`
  if (!ID_RE.test(x)) x = fallback
  return x.slice(0, 48)
}

function validateEmployeePackManifest(data) {
  const errors = []
  const mid = data?.id
  if (!mid || typeof mid !== 'string' || !mid.trim()) errors.push('缺少非空字符串字段 id')
  else if (!ID_RE.test(mid.trim())) errors.push('id 建议使用小写字母、数字、点、下划线、连字符，且不以连字符开头')
  for (const key of ['name', 'version']) {
    const v = data[key]
    if (v == null || (typeof v === 'string' && !v.trim())) errors.push(`建议填写非空 ${key}`)
  }
  const art = String(data.artifact || 'mod').toLowerCase()
  if (art !== 'employee_pack') errors.push('artifact 须为 employee_pack')
  const emp = data.employee
  if (!emp || typeof emp !== 'object') errors.push('employee_pack 须包含 employee 对象')
  else if (!String(emp.id || '').trim()) errors.push('employee.id 不能为空')
  const scope = String(data.scope || 'global')
    .trim()
    .toLowerCase()
  if (!['global', 'host'].includes(scope)) errors.push('scope 仅支持 global 或 host（host 为二期预留）')
  return errors
}

export function buildEmployeePackManifestFromWorkflow(modId, modManifest, wfEntry, workflowIndex = 0) {
  const mid = normalizeModId(modId)
  if (!mid) return { manifest: null, error: 'Mod id 无效' }

  const wf = wfEntry && typeof wfEntry === 'object' && !Array.isArray(wfEntry) ? wfEntry : {}
  const wfRawId = String(wf.id || '').trim()
  const wfSlug = normalizeModId(wfRawId) || slugId(wfRawId, `emp${workflowIndex}`)
  let packId = wfSlug === mid ? mid : `${mid}-${wfSlug}`
  if (packId.length > 48) packId = packId.slice(0, 48)
  if (!ID_RE.test(packId)) packId = mid

  const nameSrc = String(
    wf.label || wf.panel_title || modManifest?.name || packId,
  ).trim()
  const name = (nameSrc.slice(0, 200) || packId).trim() || packId
  const ver = String(modManifest?.version != null ? modManifest.version : '1.0.0')
    .trim() || '1.0.0'
  const desc = String(
    wf.panel_summary || wf.description || modManifest?.description || '',
  )
    .trim()
    .slice(0, 4000)

  const empId = normalizeModId(String(wf.id || '').trim()) || wfSlug
  const label = (String(wf.label || name).trim() || empId).slice(0, 200)
  const capsIn = wf.capabilities
  const caps = []
  if (Array.isArray(capsIn)) {
    for (const x of capsIn) {
      if (typeof x === 'string' && x.trim()) caps.push(x.trim().slice(0, 128))
    }
  }

  const manifest = {
    id: packId,
    name,
    version: ver,
    author: String(modManifest?.author || '').trim(),
    description: desc,
    artifact: 'employee_pack',
    scope: 'global',
    dependencies:
      modManifest?.dependencies && typeof modManifest.dependencies === 'object'
        ? modManifest.dependencies
        : { xcagi: '>=1.0.0' },
    employee: {
      id: empId,
      label,
      capabilities: caps,
    },
  }

  const ve = validateEmployeePackManifest(manifest)
  if (ve.length) return { manifest: null, error: `manifest 校验: ${ve.join('; ')}` }
  return { manifest, error: '' }
}

/**
 * @returns {{ blob: Blob, packId: string }}
 */
export function buildEmployeePackZipFromPanel({ modId, workflowIndex, modManifest, workflowJsonText }) {
  if (!String(modId || '').trim()) throw new Error('缺少 Mod id')
  let wfEntry
  try {
    wfEntry = JSON.parse(workflowJsonText || '{}')
  } catch {
    throw new Error('workflow_employees JSON 无法解析')
  }
  if (!wfEntry || typeof wfEntry !== 'object' || Array.isArray(wfEntry)) {
    throw new Error('workflow 条目须为 JSON 对象（非数组）')
  }
  const mod = modManifest && typeof modManifest === 'object' ? modManifest : {}
  const { manifest, error } = buildEmployeePackManifestFromWorkflow(
    modId.trim(),
    mod,
    wfEntry,
    Number(workflowIndex) || 0,
  )
  if (error || !manifest) throw new Error(error || '无法生成 manifest')

  const packId = String(manifest.id || '').trim()
  const body = `${JSON.stringify(manifest, null, 2)}\n`
  const zipBytes = zipSync({ [`${packId}/manifest.json`]: strToU8(body) }, { level: 6 })
  const blob = new Blob([zipBytes as unknown as BlobPart], { type: 'application/zip' })
  return { blob, packId }
}

function sanitizePackId(raw = '') {
  const norm = normalizeModId(String(raw || '').trim())
  if (norm) return norm
  return slugId(String(raw || '').trim(), 'employee-pack')
}

/**
 * V2 配置转 employee_pack manifest（浏览器端兜底导出专用）
 */
export function buildEmployeePackManifestFromV2({
  config,
  packId = '',
  industry = '',
  price = 0,
  author = '',
}) {
  const c = config && typeof config === 'object' ? config : {}
  const identity = c.identity && typeof c.identity === 'object' ? c.identity : {}
  const collaboration = c.collaboration && typeof c.collaboration === 'object' ? c.collaboration : {}
  const wf = collaboration.workflow && typeof collaboration.workflow === 'object' ? collaboration.workflow : {}
  const wfEmployees = Array.isArray(c.workflow_employees) ? c.workflow_employees : []
  const idFromConfig = sanitizePackId(identity.id || '')
  const finalPackId = sanitizePackId(packId || idFromConfig || identity.name || 'employee-pack')

  const workflowId = Number.parseInt(String(wf.workflow_id || 0), 10)
  const capabilities = []
  if (c.perception) capabilities.push('perception')
  if (c.memory) capabilities.push('memory')
  if (c.cognition) capabilities.push('cognition')
  if (c.actions) capabilities.push('actions')
  if (c.management) capabilities.push('management')
  capabilities.push('collaboration')

  const manifest = {
    id: finalPackId,
    name: String(identity.name || finalPackId).trim() || finalPackId,
    version: String(identity.version || '1.0.0').trim() || '1.0.0',
    author: String(author || identity.author || '').trim(),
    description: String(identity.description || '').trim(),
    artifact: 'employee_pack',
    scope: 'global',
    employee: {
      id: String(identity.id || finalPackId).trim() || finalPackId,
      label: String(identity.name || finalPackId).trim() || finalPackId,
      capabilities,
      workflow_id: Number.isFinite(workflowId) ? workflowId : 0,
    },
    workflow_employees: wfEmployees,
    employee_config_v2: c,
    commerce: {
      industry: String(industry || c?.commerce?.industry || '通用').trim() || '通用',
      price: Number.isFinite(Number(price)) ? Number(price) : Number(c?.commerce?.price || 0) || 0,
    },
    metadata: {
      exported_by: 'employee_pack_client_export_v2',
      exported_at: new Date().toISOString(),
    },
  }
  return { manifest, packId: finalPackId }
}

/**
 * 用 V2 配置在浏览器内构建 employee_pack zip
 * files 支持额外携带代码/资源，键为 zip 内相对路径。
 */
export function buildEmployeePackZipFromV2({
  config,
  packId = '',
  industry = '',
  price = 0,
  author = '',
  files = {},
}) {
  const { manifest, packId: finalPackId } = buildEmployeePackManifestFromV2({
    config,
    packId,
    industry,
    price,
    author,
  })
  const errors = validateEmployeePackManifest(manifest)
  if (errors.length) throw new Error(`V2 manifest 校验失败: ${errors.join('; ')}`)

  /** @type {Record<string, Uint8Array>} */
  const zipEntries = {
    [`${finalPackId}/manifest.json`]: strToU8(`${JSON.stringify(manifest, null, 2)}\n`),
  }

  const inputFiles = files && typeof files === 'object' ? files : {}
  for (const [rel, body] of Object.entries(inputFiles)) {
    const clean = String(rel || '').replace(/^\/+/, '').trim()
    if (!clean) continue
    if (body instanceof Uint8Array) zipEntries[`${finalPackId}/${clean}`] = body
    else zipEntries[`${finalPackId}/${clean}`] = strToU8(String(body ?? ''))
  }

  const zipBytes = zipSync(zipEntries, { level: 6 })
  const blob = new Blob([zipBytes as unknown as BlobPart], { type: 'application/zip' })
  return { blob, packId: finalPackId, manifest }
}
