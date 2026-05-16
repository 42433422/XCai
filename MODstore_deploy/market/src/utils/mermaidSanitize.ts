/**
 * 把"模型生成的"宽容 Mermaid 源码尽量挽救成 Mermaid 词法器可以接受的形式。
 *
 * 设计取舍：
 * - 这里只做最小、保守的字符级转换，**不重写图结构**。命中条件越苛刻越好，
 *   避免破坏已经合法的图。
 * - 主要修复：节点标签 `id[label]` / `id(label)` / `id{label}` 中包含 Mermaid
 *   词法器不喜欢的字符（圆括号、方括号、冒号、分号、尖括号、引号、井号、管道、
 *   反引号、和号）时，给 label 加上 `"..."` 引号包裹；引号内部出现的 `"` 用
 *   `#quot;` 转义，Mermaid 接受 HTML 实体形式。
 * - 不处理双层括号形状（`[[ ]]` / `(( ))` / `{{ }}` / `([ ])` / `[( )]`），
 *   它们的语义不同，错误改写会更糟。
 * - 不动诸如 `style A fill:#fff,stroke:#000`、`click A "tip"`、子图声明
 *   `subgraph "标题"`、连边管道标签 `A -->|提示| B` 等其他语法位置——它们
 *   不会被本函数的正则匹配。
 *
 * 这个函数仅在第一次原样调用 `mermaid.run` 失败后作为重试源使用，因此即使
 * 偶尔"无所改动"或"改不到位"，也不会影响原本就能成功渲染的图。
 */
export function sanitizeMermaidSource(input: string): string {
  let s = String(input ?? '').replace(/\r\n?/g, '\n')

  // 偶发：模型把围栏一起塞进来；先剥掉首尾的 ``` 行
  s = s.replace(/^\s*```[\w+-]*\n/, '').replace(/\n```\s*$/, '')

  const PROBLEMATIC = /[:;<>"'`#|&]|\(|\)|\[|\]|\{|\}/

  const quoteIfNeeded = (
    id: string,
    open: string,
    label: string,
    close: string,
  ) => {
    const trimmed = label.trim()
    if (!trimmed) return null
    if (/^".*"$/.test(trimmed)) return null
    if (!PROBLEMATIC.test(trimmed)) return null
    const escaped = trimmed.replace(/"/g, '#quot;')
    return `${id}${open}"${escaped}"${close}`
  }

  // 方括号节点：A[label]。label 内允许圆括号/花括号，但不允许方括号或换行；
  // 这样自然跳过 `[[ ... ]]` / `([ ... ])` 这类双层形状（首字符就是另一个 `[`，
  // 落在排除集中无法匹配）。
  s = s.replace(
    /([A-Za-z0-9_\-]+)(\[)([^\[\]\n]*?)(\])/g,
    (match, id: string, open: string, label: string, close: string) =>
      quoteIfNeeded(id, open, label, close) ?? match,
  )

  // 圆括号节点：A(label)。label 内允许方括号/花括号，但不允许圆括号或换行。
  s = s.replace(
    /([A-Za-z0-9_\-]+)(\()([^()\n]*?)(\))/g,
    (match, id: string, open: string, label: string, close: string) =>
      quoteIfNeeded(id, open, label, close) ?? match,
  )

  // 花括号节点：A{label}。label 内允许圆括号/方括号，但不允许花括号或换行；
  // `A{{label}}` 形状会被自然跳过（内部首字符是另一个 `{`）。
  s = s.replace(
    /([A-Za-z0-9_\-]+)(\{)([^{}\n]*?)(\})/g,
    (match, id: string, open: string, label: string, close: string) =>
      quoteIfNeeded(id, open, label, close) ?? match,
  )

  return s
}
