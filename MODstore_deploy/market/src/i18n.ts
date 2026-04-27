import { inject, reactive } from 'vue'
import zhCN from './locales/zh-CN'
import enUS from './locales/en-US'

export const I18N_KEY = Symbol('modstore-i18n')

const messages = {
  'zh-CN': zhCN,
  'en-US': enUS,
}

function readPath(source, path) {
  return String(path)
    .split('.')
    .reduce((cur, key) => (cur && Object.prototype.hasOwnProperty.call(cur, key) ? cur[key] : undefined), source)
}

function storedLocale() {
  try {
    return localStorage.getItem('modstore_locale') || 'zh-CN'
  } catch {
    return 'zh-CN'
  }
}

export function createModstoreI18n(defaultLocale = storedLocale()) {
  const state = reactive({
    locale: messages[defaultLocale] ? defaultLocale : 'zh-CN',
  })

  function setLocale(locale) {
    if (!messages[locale]) return
    state.locale = locale
    try {
      localStorage.setItem('modstore_locale', locale)
    } catch {
      /* ignore storage errors */
    }
  }

  function t(path, params = {}) {
    const value = readPath(messages[state.locale], path) ?? readPath(messages['zh-CN'], path) ?? path
    return String(value).replace(/\{(\w+)\}/g, (_, key) =>
      params[key] === undefined ? `{${key}}` : String(params[key]),
    )
  }

  return {
    install(app) {
      app.provide(I18N_KEY, { state, t, setLocale, messages })
      app.config.globalProperties.$t = t
    },
    state,
    t,
    setLocale,
    messages,
  }
}

export function useI18n() {
  return inject(I18N_KEY, createModstoreI18n())
}
