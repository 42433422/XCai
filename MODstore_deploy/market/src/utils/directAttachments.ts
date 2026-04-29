export const DIRECT_KB_SUPPORTED_EXTENSIONS = ['txt', 'md', 'json', 'csv', 'pdf', 'docx', 'xlsx'] as const
export const DIRECT_KB_SUPPORTED_EXT = new Set<string>(DIRECT_KB_SUPPORTED_EXTENSIONS)
export const DIRECT_ATTACHMENT_ACCEPT = DIRECT_KB_SUPPORTED_EXTENSIONS.map((ext) => `.${ext}`).join(',')
export const DIRECT_KB_MAX_BYTES = 20 * 1024 * 1024

export type DirectAttachmentStatus = 'uploading' | 'ready' | 'inline' | 'error' | 'skipped'
export type DirectAttachmentKind = 'excel' | 'pdf' | 'word' | 'csv' | 'json' | 'text' | 'file'

export interface DirectAttachmentOutcome {
  status: 'ready' | 'inline' | 'error'
  canSend: boolean
  extractedText: string
  docId: string
  error: string
  ingestError: string
}

export function formatDirectFileSize(size: number): string {
  const n = Number(size || 0)
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(n < 10240 ? 1 : 0)} KB`
  return `${(n / (1024 * 1024)).toFixed(1)} MB`
}

export function directFileExt(filename: string): string {
  const s = String(filename || '')
  const i = s.lastIndexOf('.')
  if (i < 0 || i >= s.length - 1) return ''
  return s.slice(i + 1).toLowerCase()
}

export function directFileKind(filename: string, mime = ''): DirectAttachmentKind {
  const ext = directFileExt(filename)
  if (ext === 'xlsx') return 'excel'
  if (ext === 'pdf') return 'pdf'
  if (ext === 'docx') return 'word'
  if (ext === 'csv') return 'csv'
  if (ext === 'json') return 'json'
  if (ext === 'txt' || ext === 'md' || String(mime).startsWith('text/')) return 'text'
  return 'file'
}

export function directFileKindLabel(kind: DirectAttachmentKind): string {
  switch (kind) {
    case 'excel':
      return 'Excel'
    case 'pdf':
      return 'PDF'
    case 'word':
      return 'Word'
    case 'csv':
      return 'CSV'
    case 'json':
      return 'JSON'
    case 'text':
      return 'Text'
    default:
      return 'File'
  }
}

export function normalizeDirectAttachmentError(error: unknown, fallback = '上传失败'): string {
  const raw =
    typeof error === 'string'
      ? error
      : error && typeof error === 'object' && 'message' in error
        ? String((error as { message?: unknown }).message || '')
        : ''
  const text = raw.trim() || fallback
  if (/openpyxl/i.test(text)) return '服务器缺少 openpyxl，暂不能解析 Excel；请重新安装 knowledge 依赖后再试'
  if (/pypdf/i.test(text)) return '服务器缺少 pypdf，暂不能解析 PDF；请重新安装 knowledge 依赖后再试'
  if (/python-docx|docx/i.test(text)) return '服务器缺少 python-docx，暂不能解析 Word；请重新安装 knowledge 依赖后再试'
  if (/internal server error/i.test(text)) return '资料库入库失败，已直接读取附件内容'
  if (/MODSTORE_EMBEDDING_API_KEY|Embedding Key|无法构建向量库/i.test(text)) return '已读取文件内容，未写入向量库'
  if (/有效文本|empty|文本分块为空/i.test(text)) return '未能从文件中提取有效文本，请确认文件不是空表或扫描图片'
  return text
}

export function resolveDirectAttachmentOutcome(input: {
  extractedText?: unknown
  docId?: unknown
  extractError?: unknown
  uploadError?: unknown
}): DirectAttachmentOutcome {
  const extractedText = String(input.extractedText || '').trim()
  if (!extractedText) {
    return {
      status: 'error',
      canSend: false,
      extractedText: '',
      docId: '',
      error: normalizeDirectAttachmentError(input.extractError, '未能从文件中提取有效文本'),
      ingestError: '',
    }
  }

  const docId = String(input.docId || '').trim()
  if (docId) {
    return {
      status: 'ready',
      canSend: true,
      extractedText,
      docId,
      error: '',
      ingestError: '',
    }
  }

  return {
    status: 'inline',
    canSend: true,
    extractedText,
    docId: '',
    error: '',
    ingestError: input.uploadError
      ? normalizeDirectAttachmentError(input.uploadError, '资料库入库失败，已改为直接读取附件内容')
      : '',
  }
}
