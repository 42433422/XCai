/**
 * 解析粘贴的 .env 片段，映射到 LLM provider（与 modstore_server.llm_key_resolver 环境变量名对齐）。
 *
 * 无 KEY= 或 provider= 的裸密钥行不再直接丢弃，而是收集进 `bareKeys` 返回给调用方，
 * 由调用方提交到后端 `/api/llm/credentials/detect-bare`，依次拉取各厂商 /models 自动命中归属。
 */

/** 与后端 KNOWN_PROVIDERS 顺序一致，用于 openai=... 行校验 */
export const BYOK_ALLOWED_PROVIDERS = [
  'openai',
  'deepseek',
  'anthropic',
  'google',
  'siliconflow',
  'dashscope',
  'moonshot',
  'minimax',
  'doubao',
  'wenxin',
  'hunyuan',
  'zhipu',
  'xunfei',
  'yi',
  'stepfun',
  'baichuan',
  'sensetime',
  'groq',
  'together',
  'openrouter',
]

const _allowed = new Set(BYOK_ALLOWED_PROVIDERS)

/** @type {Record<string, { provider: string, field: 'api_key' | 'base_url' }>} */
const ENV_MAP = {
  OPENAI_API_KEY: { provider: 'openai', field: 'api_key' },
  OPENAI_BASE_URL: { provider: 'openai', field: 'base_url' },
  DEEPSEEK_API_KEY: { provider: 'deepseek', field: 'api_key' },
  DEEPSEEK_BASE_URL: { provider: 'deepseek', field: 'base_url' },
  ANTHROPIC_API_KEY: { provider: 'anthropic', field: 'api_key' },
  GEMINI_API_KEY: { provider: 'google', field: 'api_key' },
  GOOGLE_API_KEY: { provider: 'google', field: 'api_key' },
  SILICONFLOW_API_KEY: { provider: 'siliconflow', field: 'api_key' },
  SILICONFLOW_BASE_URL: { provider: 'siliconflow', field: 'base_url' },
  DASHSCOPE_API_KEY: { provider: 'dashscope', field: 'api_key' },
  DASHSCOPE_BASE_URL: { provider: 'dashscope', field: 'base_url' },
  MOONSHOT_API_KEY: { provider: 'moonshot', field: 'api_key' },
  MOONSHOT_BASE_URL: { provider: 'moonshot', field: 'base_url' },
  MINIMAX_API_KEY: { provider: 'minimax', field: 'api_key' },
  MINIMAX_BASE_URL: { provider: 'minimax', field: 'base_url' },
  DOUBAO_API_KEY: { provider: 'doubao', field: 'api_key' },
  ARK_API_KEY: { provider: 'doubao', field: 'api_key' },
  DOUBAO_BASE_URL: { provider: 'doubao', field: 'base_url' },
  WENXIN_API_KEY: { provider: 'wenxin', field: 'api_key' },
  QIANFAN_API_KEY: { provider: 'wenxin', field: 'api_key' },
  BAIDU_QIANFAN_API_KEY: { provider: 'wenxin', field: 'api_key' },
  WENXIN_BASE_URL: { provider: 'wenxin', field: 'base_url' },
  QIANFAN_BASE_URL: { provider: 'wenxin', field: 'base_url' },
  HUNYUAN_API_KEY: { provider: 'hunyuan', field: 'api_key' },
  TENCENT_HUNYUAN_API_KEY: { provider: 'hunyuan', field: 'api_key' },
  HUNYUAN_BASE_URL: { provider: 'hunyuan', field: 'base_url' },
  TENCENT_HUNYUAN_BASE_URL: { provider: 'hunyuan', field: 'base_url' },
  ZHIPU_API_KEY: { provider: 'zhipu', field: 'api_key' },
  BIGMODEL_API_KEY: { provider: 'zhipu', field: 'api_key' },
  ZHIPU_BASE_URL: { provider: 'zhipu', field: 'base_url' },
  BIGMODEL_BASE_URL: { provider: 'zhipu', field: 'base_url' },
  XUNFEI_API_KEY: { provider: 'xunfei', field: 'api_key' },
  SPARK_API_KEY: { provider: 'xunfei', field: 'api_key' },
  XUNFEI_BASE_URL: { provider: 'xunfei', field: 'base_url' },
  SPARK_BASE_URL: { provider: 'xunfei', field: 'base_url' },
  YI_API_KEY: { provider: 'yi', field: 'api_key' },
  LINGYIWANWU_API_KEY: { provider: 'yi', field: 'api_key' },
  YI_BASE_URL: { provider: 'yi', field: 'base_url' },
  LINGYIWANWU_BASE_URL: { provider: 'yi', field: 'base_url' },
  STEPFUN_API_KEY: { provider: 'stepfun', field: 'api_key' },
  STEPFUN_BASE_URL: { provider: 'stepfun', field: 'base_url' },
  BAICHUAN_API_KEY: { provider: 'baichuan', field: 'api_key' },
  BAICHUAN_BASE_URL: { provider: 'baichuan', field: 'base_url' },
  SENSETIME_API_KEY: { provider: 'sensetime', field: 'api_key' },
  SENSENOVA_API_KEY: { provider: 'sensetime', field: 'api_key' },
  SENSETIME_BASE_URL: { provider: 'sensetime', field: 'base_url' },
  SENSENOVA_BASE_URL: { provider: 'sensetime', field: 'base_url' },
  GROQ_API_KEY: { provider: 'groq', field: 'api_key' },
  GROQ_BASE_URL: { provider: 'groq', field: 'base_url' },
  TOGETHER_API_KEY: { provider: 'together', field: 'api_key' },
  TOGETHER_BASE_URL: { provider: 'together', field: 'base_url' },
  OPENROUTER_API_KEY: { provider: 'openrouter', field: 'api_key' },
  OPENROUTER_BASE_URL: { provider: 'openrouter', field: 'base_url' },
}

function stripQuotes(s) {
  const t = s.trim()
  if ((t.startsWith('"') && t.endsWith('"')) || (t.startsWith("'") && t.endsWith("'"))) {
    return t.slice(1, -1).trim()
  }
  return t
}

/** 看起来像 API Key 的裸字符串：不含空格/等号、长度 ≥ 8（与后端 detect-bare 的最小长度对齐） */
function looksLikeBareKey(s) {
  const t = s.trim()
  if (!t) return false
  if (t.length < 8) return false
  if (/\s/.test(t)) return false
  if (t.includes('=')) return false
  return /^[A-Za-z0-9._\-+/:]+$/.test(t)
}

/**
 * @param {string} text
 * @returns {{
 *   entries: { provider: string, api_key: string, base_url?: string|null }[],
 *   bareKeys: string[],
 *   warnings: string[],
 * }}
 */
export function parseByokPaste(text) {
  const warnings = []
  /** @type {Record<string, { api_key?: string, base_url?: string }>} */
  const acc = {}
  /** @type {string[]} */
  const bareKeys = []
  const bareSeen = new Set()
  let unrecognizedLines = 0

  const rawLines = (text || '').split(/\r?\n/)

  for (let line of rawLines) {
    line = line.trim()
    if (!line || line.startsWith('#')) continue

    if (/^export\s+/i.test(line)) {
      line = line.replace(/^export\s+/i, '').trim()
    }

    const eq = line.indexOf('=')
    if (eq <= 0) {
      if (looksLikeBareKey(line) && !bareSeen.has(line)) {
        bareSeen.add(line)
        bareKeys.push(line)
      } else {
        unrecognizedLines += 1
      }
      continue
    }

    const key = line.slice(0, eq).trim()
    const value = stripQuotes(line.slice(eq + 1))
    if (!key) continue

    const upper = key.toUpperCase()
    const mapped = ENV_MAP[upper]
    if (mapped) {
      const { provider, field } = mapped
      if (!acc[provider]) acc[provider] = {}
      if (field === 'api_key') {
        if (value) acc[provider].api_key = value
      } else if (value) {
        acc[provider].base_url = value
      }
      continue
    }

    const lower = key.toLowerCase()
    if (_allowed.has(lower)) {
      if (value) {
        if (!acc[lower]) acc[lower] = {}
        acc[lower].api_key = value
      }
      continue
    }

    unrecognizedLines += 1
  }

  if (unrecognizedLines > 0) {
    warnings.push(
      `已跳过 ${unrecognizedLines} 行无法识别的内容（既不是 NAME=VALUE，也不像 API Key）。`,
    )
  }

  const entries = []
  for (const provider of BYOK_ALLOWED_PROVIDERS) {
    const row = acc[provider]
    if (row && row.api_key && String(row.api_key).trim().length < 4) {
      warnings.push(`密钥过短（至少 4 字符）已忽略：${provider}`)
    }
    if (!row || !row.api_key || String(row.api_key).trim().length < 4) {
      if (row && row.base_url && !row.api_key) {
        warnings.push(`已忽略仅含 Base URL、无 API Key 的项：${provider}`)
      }
      continue
    }
    entries.push({
      provider,
      api_key: String(row.api_key).trim(),
      base_url: row.base_url ? String(row.base_url).trim() : null,
    })
  }

  if (!entries.length && !bareKeys.length) {
    const hasKeyLikeLine = rawLines.some((ln) => {
      const t = ln.trim()
      return t && !t.startsWith('#') && t.includes('=')
    })
    if (!hasKeyLikeLine && !warnings.length) {
      warnings.push('请粘贴 .env 片段（例如 OPENAI_API_KEY=sk-…）或直接粘贴一段 sk-… 裸密钥。')
    } else if (!warnings.some((w) => w.includes('跳过'))) {
      warnings.push('未解析到任何可保存的 API Key（需至少 4 字符的密钥）。')
    }
  }

  return { entries, bareKeys, warnings }
}
