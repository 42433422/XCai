/**
 * 会话本地持久化（localStorage 优先，失败时退回内存）。
 * - 仅做一档「直接对话」的会话；二档/三档独立。
 * - 数据结构与豆包 / ChatGPT 类似：conversations[]（含 messages[]）+ activeId。
 * - 不做云端同步；后续接 /api/llm/conversations 时只需替换 io 层即可。
 */

export interface ChatAttachmentMeta {
  name: string
  size: number
  status: 'ready' | 'error' | 'skipped' | 'uploading'
  docId?: string
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  createdAt: number
  reasoning?: string
  attachments?: ChatAttachmentMeta[]
  citations?: Array<{ title: string; url?: string; snippet?: string }>
  imageUrls?: string[]
  feedback?: 'up' | 'down' | null
  pending?: boolean
  error?: string
  skills?: string[]
  agentId?: string
  agentLabel?: string
}

export interface Conversation {
  id: string
  title: string
  createdAt: number
  updatedAt: number
  pinned: boolean
  messages: ChatMessage[]
  agentId?: string
  agentLabel?: string
}

const STORAGE_KEY = 'workbench_direct_conversations_v1'
const ACTIVE_KEY = 'workbench_direct_active_v1'
const MAX_CONVS = 100
const MAX_MSGS_PER_CONV = 400

function newId(prefix = 'c'): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    try {
      return `${prefix}_${crypto.randomUUID()}`
    } catch {
      /* fallthrough */
    }
  }
  return `${prefix}_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 10)}`
}

function safeRead<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key)
    if (!raw) return fallback
    return JSON.parse(raw) as T
  } catch {
    return fallback
  }
}

function safeWrite(key: string, value: unknown): void {
  try {
    localStorage.setItem(key, JSON.stringify(value))
  } catch {
    /* 配额超限时静默吞掉 */
  }
}

export function loadConversations(): Conversation[] {
  const raw = safeRead<Conversation[]>(STORAGE_KEY, [])
  if (!Array.isArray(raw)) return []
  return raw
    .filter((c) => c && typeof c.id === 'string' && Array.isArray(c.messages))
    .map((c) => ({
      id: c.id,
      title: String(c.title || '新对话'),
      createdAt: Number(c.createdAt) || Date.now(),
      updatedAt: Number(c.updatedAt) || Date.now(),
      pinned: Boolean(c.pinned),
      messages: c.messages.slice(0, MAX_MSGS_PER_CONV),
      agentId: c.agentId,
      agentLabel: c.agentLabel,
    }))
    .sort((a, b) => {
      if (a.pinned !== b.pinned) return a.pinned ? -1 : 1
      return b.updatedAt - a.updatedAt
    })
    .slice(0, MAX_CONVS)
}

export function saveConversations(list: Conversation[]): void {
  const trimmed = list
    .slice()
    .sort((a, b) => {
      if (a.pinned !== b.pinned) return a.pinned ? -1 : 1
      return b.updatedAt - a.updatedAt
    })
    .slice(0, MAX_CONVS)
    .map((c) => ({ ...c, messages: c.messages.slice(-MAX_MSGS_PER_CONV) }))
  safeWrite(STORAGE_KEY, trimmed)
}

export function loadActiveId(): string {
  return safeRead<string>(ACTIVE_KEY, '')
}

export function saveActiveId(id: string): void {
  safeWrite(ACTIVE_KEY, id || '')
}

export function createConversation(opts?: { title?: string; agentId?: string; agentLabel?: string }): Conversation {
  const now = Date.now()
  return {
    id: newId('conv'),
    title: opts?.title || '新对话',
    createdAt: now,
    updatedAt: now,
    pinned: false,
    messages: [],
    agentId: opts?.agentId,
    agentLabel: opts?.agentLabel,
  }
}

export function makeMessage(role: ChatMessage['role'], content: string, extra: Partial<ChatMessage> = {}): ChatMessage {
  return {
    id: newId('msg'),
    role,
    content,
    createdAt: Date.now(),
    ...extra,
  }
}

export function summarizeForTitle(text: string): string {
  const s = String(text || '').replace(/\s+/g, ' ').trim()
  if (!s) return '新对话'
  return s.slice(0, 24)
}

export function exportConversationAsMarkdown(c: Conversation): string {
  const head = `# ${c.title}\n\n_导出时间：${new Date().toLocaleString()}_\n\n---\n\n`
  const body = c.messages
    .map((m) => {
      const role = m.role === 'user' ? '**你**' : m.role === 'assistant' ? '**AI**' : '**系统**'
      return `${role}\n\n${m.content}\n`
    })
    .join('\n---\n\n')
  return head + body
}

export function searchConversations(list: Conversation[], q: string): Conversation[] {
  const kw = String(q || '').trim().toLowerCase()
  if (!kw) return list
  return list.filter((c) => {
    if (c.title.toLowerCase().includes(kw)) return true
    return c.messages.some((m) => m.content.toLowerCase().includes(kw))
  })
}
