/**
 * 厂商 SVG 图标地址（jsDelivr + simple-icons 固定版本）。
 * Simple Icons 未收录的 slug 返回 null，由 UI 用字首色块展示。
 */
import { llmUiMeta } from './llmModels'

const SIMPLE_ICONS_VER = '15.22.0'
const SIMPLE_ICONS_CDN = `https://cdn.jsdelivr.net/npm/simple-icons@${SIMPLE_ICONS_VER}/icons`

/**
 * 在 SIMPLE_ICONS_VER 下不存在对应 svg 的 slug（cdn.jsdelivr.net 返回 404）。
 * 见 simple-icons 仓库：DeepSeek 等因品牌条款未收录；Groq / Together 等部分版本缺失。
 */
const SI_MISSING_SLUGS = new Set(['deepseek', 'groq', 'togethercomputer'])

/**
 * @param {string} providerId
 * @returns {string|null} 可放入 <img src> 的 URL；null 表示使用字首回退
 */
export function llmProviderIconImgSrc(providerId) {
  const { iconSlug } = llmUiMeta(providerId)
  if (SI_MISSING_SLUGS.has(iconSlug)) return null
  return `${SIMPLE_ICONS_CDN}/${iconSlug}.svg`
}
