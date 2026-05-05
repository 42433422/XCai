import { ref, onBeforeUnmount } from 'vue'

export type VoiceState = 'idle' | 'listening' | 'thinking' | 'speaking'

export function useVoiceInput(onFinalText: (text: string) => Promise<void>) {
  const state = ref<VoiceState>('idle')
  const error = ref('')
  const isSpeaking = ref(false)
  const muted = ref(false)
  const rate = ref(1.0)

  let rec: any = null
  let synth: SpeechSynthesis | null = null
  let interim = ''
  let currentUtterance: SpeechSynthesisUtterance | null = null

  if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
    synth = window.speechSynthesis
  }

  const isSupported = typeof window !== 'undefined' &&
    !!(((window as any).SpeechRecognition || (window as any).webkitSpeechRecognition))

  function createRec() {
    const w = window as any
    const Ctor = w.SpeechRecognition || w.webkitSpeechRecognition
    if (!Ctor) return null
    const r = new Ctor()
    r.lang = 'zh-CN'
    r.interimResults = true
    r.continuous = false
    return r
  }

  function speak(text: string): Promise<void> {
    if (muted.value || !text || !synth) return Promise.resolve()
    return new Promise<void>((resolve) => {
      const u = new SpeechSynthesisUtterance(text)
      const voices = synth!.getVoices()
      const zhVoice = voices.find((v) => /^zh/i.test(v.lang)) || voices[0]
      if (zhVoice) u.voice = zhVoice
      u.rate = Math.max(0.6, Math.min(1.6, rate.value))
      currentUtterance = u
      u.onend = () => { isSpeaking.value = false; resolve() }
      u.onerror = () => { isSpeaking.value = false; resolve() }
      state.value = 'speaking'
      isSpeaking.value = true
      synth!.cancel()
      synth!.speak(u)
    })
  }

  function startListening() {
    error.value = ''
    if (!rec) {
      rec = createRec()
      if (!rec) {
        error.value = '当前浏览器不支持语音识别（建议 Chrome / Edge）。'
        return
      }
    }
    interim = ''
    state.value = 'listening'

    rec.onresult = (e: any) => {
      let txt = ''
      for (let i = e.resultIndex; i < e.results.length; i++) {
        txt += e.results[i][0]?.transcript || ''
      }
      interim = txt.trim()
    }
    rec.onerror = (e: any) => {
      error.value = e?.error ? `语音识别失败：${e.error}` : '语音识别失败'
      state.value = 'idle'
    }
    rec.onend = async () => {
      if (interim && state.value === 'listening') {
        state.value = 'thinking'
        await onFinalText(interim)
        interim = ''
        if (state.value === 'thinking') state.value = 'idle'
      } else if (state.value === 'listening') {
        state.value = 'idle'
      }
    }

    try { rec.start() } catch (e: any) {
      error.value = e?.message || String(e)
      state.value = 'idle'
    }
  }

  function stopAll() {
    try { rec?.stop?.() } catch { /* ignore */ }
    try { synth?.cancel?.() } catch { /* ignore */ }
    isSpeaking.value = false
    currentUtterance = null
  }

  function toggleMute() {
    muted.value = !muted.value
    if (muted.value) { try { synth?.cancel?.() } catch { /* ignore */ }; isSpeaking.value = false }
  }

  onBeforeUnmount(() => { stopAll() })

  return {
    state,
    error,
    isSpeaking,
    muted,
    rate,
    isSupported,
    startListening,
    stopAll,
    speak,
    toggleMute,
  }
}
