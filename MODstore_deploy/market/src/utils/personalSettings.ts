/**
 * 个性化设置（主题 / 字号 / 长期记忆 / 推荐 prompt）持久化与默认值。
 */

export interface PersonalSettings {
  theme: 'dark' | 'light' | 'auto'
  fontPx: number
  memory: string
  suggestions: string[]
}

const KEY = 'workbench_personal_settings_v1'

const DEFAULT_SUGGESTIONS = [
  '帮我把今天的工作拆成步骤',
  '帮我分析一个自动化流程',
  '帮我写一段客户沟通话术',
]

export function defaultPersonalSettings(): PersonalSettings {
  return {
    theme: 'dark',
    fontPx: 15,
    memory: '',
    suggestions: DEFAULT_SUGGESTIONS.slice(),
  }
}

export function loadPersonalSettings(): PersonalSettings {
  try {
    const raw = localStorage.getItem(KEY)
    if (!raw) return defaultPersonalSettings()
    const obj = JSON.parse(raw) || {}
    const def = defaultPersonalSettings()
    return {
      theme: obj.theme === 'light' || obj.theme === 'auto' ? obj.theme : 'dark',
      fontPx: Number.isFinite(Number(obj.fontPx)) ? Math.max(13, Math.min(20, Number(obj.fontPx))) : def.fontPx,
      memory: typeof obj.memory === 'string' ? obj.memory.slice(0, 600) : '',
      suggestions: Array.isArray(obj.suggestions) && obj.suggestions.length
        ? obj.suggestions.filter((x: unknown) => typeof x === 'string' && (x as string).trim()).slice(0, 6)
        : def.suggestions,
    }
  } catch {
    return defaultPersonalSettings()
  }
}

export function savePersonalSettings(v: PersonalSettings): void {
  try {
    localStorage.setItem(KEY, JSON.stringify(v))
  } catch {
    /* ignore */
  }
}

export function applyThemeToDocument(theme: 'dark' | 'light' | 'auto'): void {
  if (typeof document === 'undefined') return
  const html = document.documentElement
  if (!html) return
  if (theme === 'auto') {
    const prefersLight = typeof window !== 'undefined' && window.matchMedia?.('(prefers-color-scheme: light)').matches
    html.dataset.workbenchTheme = prefersLight ? 'light' : 'dark'
  } else {
    html.dataset.workbenchTheme = theme
  }
}
