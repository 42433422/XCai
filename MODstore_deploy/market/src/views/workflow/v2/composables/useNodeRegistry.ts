/**
 * 工作流节点类型注册表。
 *
 * 与后端 `WorkflowNode.node_type`（modstore_server/models.py）对齐：
 * start, end, employee, condition, openapi_operation, knowledge_search,
 * webhook_trigger, cron_trigger, variable_set。
 *
 * 任何新增节点类型都应在此处登记 metadata + 属性字段 schema，
 * 编辑器不需要为每种节点单独写 Vue 组件。
 */

export type NodeKind =
  | 'start'
  | 'end'
  | 'employee'
  | 'condition'
  | 'openapi_operation'
  | 'knowledge_search'
  | 'webhook_trigger'
  | 'cron_trigger'
  | 'variable_set'

export type NodeCategory = 'flow' | 'employee' | 'logic' | 'integration' | 'trigger' | 'data'

export interface FieldSchema {
  key: string
  label: string
  type: 'text' | 'textarea' | 'number' | 'switch' | 'select' | 'json' | 'employee-picker'
  placeholder?: string
  helper?: string
  options?: { label: string; value: string | number | boolean }[]
  required?: boolean
}

export interface NodeMeta {
  kind: NodeKind
  label: string
  category: NodeCategory
  description: string
  accent: string
  icon: string
  hasInput: boolean
  hasOutput: boolean
  /** condition 节点用 true/false 两个出 handle，其它默认单出 */
  branchOutputs?: boolean
  defaultConfig: Record<string, unknown>
  fields: FieldSchema[]
}

const REGISTRY: Record<NodeKind, NodeMeta> = {
  start: {
    kind: 'start',
    label: '开始',
    category: 'flow',
    description: '工作流入口，接收 input_data',
    accent: '#22c55e',
    icon: '▶',
    hasInput: false,
    hasOutput: true,
    defaultConfig: {},
    fields: [],
  },
  end: {
    kind: 'end',
    label: '结束',
    category: 'flow',
    description: '工作流终点，输出当前变量上下文',
    accent: '#64748b',
    icon: '■',
    hasInput: true,
    hasOutput: false,
    defaultConfig: {},
    fields: [
      {
        key: 'output_template',
        label: '输出模板',
        type: 'textarea',
        placeholder: '可用 {{ var }} 引用变量；为空时返回完整上下文',
        helper: '留空时返回执行上下文 JSON',
      },
    ],
  },
  employee: {
    kind: 'employee',
    label: 'AI 员工',
    category: 'employee',
    description: '调用一个 AI 员工执行任务',
    accent: '#6366f1',
    icon: '🤖',
    hasInput: true,
    hasOutput: true,
    defaultConfig: { employee_id: '', task: '', input_mapping: {} },
    fields: [
      {
        key: 'employee_id',
        label: '员工 ID',
        type: 'employee-picker',
        required: true,
        helper: '从已购/自有员工中选择，或手动填写 employee_id',
      },
      { key: 'task', label: '任务描述', type: 'textarea', placeholder: '该员工要完成的任务，可使用 {{ input.field }}' },
      { key: 'output_var', label: '输出变量名', type: 'text', placeholder: '默认写入 last_output' },
    ],
  },
  condition: {
    kind: 'condition',
    label: '条件分支',
    category: 'logic',
    description: '基于表达式选择 true/false 出边',
    accent: '#f59e0b',
    icon: '◇',
    hasInput: true,
    hasOutput: true,
    branchOutputs: true,
    defaultConfig: { expression: '' },
    fields: [
      {
        key: 'expression',
        label: '判断表达式',
        type: 'textarea',
        required: true,
        placeholder: '例：{{ score }} > 0.6  或  {{ status }} == "ok"',
        helper: '与 workflow_engine 中的条件求值器对齐',
      },
    ],
  },
  openapi_operation: {
    kind: 'openapi_operation',
    label: 'OpenAPI 调用',
    category: 'integration',
    description: '调用第三方 OpenAPI 连接器中的 operation',
    accent: '#0ea5e9',
    icon: '🔌',
    hasInput: true,
    hasOutput: true,
    defaultConfig: { connector_id: 0, operation_id: '', params: {}, output_var: 'api_result' },
    fields: [
      { key: 'connector_id', label: '连接器 ID', type: 'number', required: true, helper: '从 /api/openapi-connectors 中选取' },
      { key: 'operation_id', label: 'Operation ID', type: 'text', required: true },
      { key: 'params', label: '入参 (JSON)', type: 'json', placeholder: '{"key":"{{ var }}"}' },
      { key: 'output_var', label: '输出变量名', type: 'text' },
    ],
  },
  knowledge_search: {
    kind: 'knowledge_search',
    label: '知识检索',
    category: 'integration',
    description: '在知识库 V2 中检索 top-k 片段',
    accent: '#10b981',
    icon: '📚',
    hasInput: true,
    hasOutput: true,
    defaultConfig: { kb_id: '', query: '', top_k: 5, output_var: 'kb_chunks' },
    fields: [
      { key: 'kb_id', label: '知识库 ID', type: 'text', required: true },
      { key: 'query', label: '查询语句', type: 'textarea', placeholder: '可使用 {{ var }} 模板' },
      { key: 'top_k', label: 'Top-K', type: 'number' },
      { key: 'output_var', label: '输出变量名', type: 'text' },
    ],
  },
  webhook_trigger: {
    kind: 'webhook_trigger',
    label: 'Webhook 触发器',
    category: 'trigger',
    description: '通过外部 HTTP 调用启动该工作流',
    accent: '#ec4899',
    icon: '🪝',
    hasInput: false,
    hasOutput: true,
    defaultConfig: { secret: '', payload_var: 'webhook_payload' },
    fields: [
      { key: 'secret', label: 'HMAC 共享密钥', type: 'text', helper: '留空则使用全局默认密钥；建议每个工作流独立设置' },
      { key: 'payload_var', label: '负载写入变量名', type: 'text' },
    ],
  },
  cron_trigger: {
    kind: 'cron_trigger',
    label: '定时触发器',
    category: 'trigger',
    description: '按 cron 表达式自动执行',
    accent: '#a855f7',
    icon: '⏰',
    hasInput: false,
    hasOutput: true,
    defaultConfig: { cron: '0 * * * *', timezone: 'Asia/Shanghai' },
    fields: [
      { key: 'cron', label: 'Cron 表达式', type: 'text', required: true, placeholder: '0 * * * *' },
      {
        key: 'timezone',
        label: '时区',
        type: 'select',
        options: [
          { label: 'Asia/Shanghai', value: 'Asia/Shanghai' },
          { label: 'UTC', value: 'UTC' },
        ],
      },
    ],
  },
  variable_set: {
    kind: 'variable_set',
    label: '变量赋值',
    category: 'data',
    description: '向上下文写入或覆盖一个变量',
    accent: '#14b8a6',
    icon: '✎',
    hasInput: true,
    hasOutput: true,
    defaultConfig: { name: '', value: '' },
    fields: [
      { key: 'name', label: '变量名', type: 'text', required: true },
      { key: 'value', label: '值（支持 {{ var }} 模板）', type: 'textarea' },
    ],
  },
}

export const KNOWN_KINDS = Object.keys(REGISTRY) as NodeKind[]

export function getNodeMeta(kind: string): NodeMeta {
  if ((KNOWN_KINDS as string[]).includes(kind)) {
    return REGISTRY[kind as NodeKind]
  }
  return {
    kind: kind as NodeKind,
    label: kind || '未知节点',
    category: 'logic',
    description: '未注册的节点类型',
    accent: '#94a3b8',
    icon: '?',
    hasInput: true,
    hasOutput: true,
    defaultConfig: {},
    fields: [],
  }
}

export function listByCategory(): { category: NodeCategory; label: string; items: NodeMeta[] }[] {
  const groups: { category: NodeCategory; label: string }[] = [
    { category: 'flow', label: '基础流程' },
    { category: 'trigger', label: '触发器' },
    { category: 'employee', label: 'AI 员工' },
    { category: 'logic', label: '逻辑' },
    { category: 'integration', label: '集成' },
    { category: 'data', label: '数据' },
  ]
  return groups.map((g) => ({
    ...g,
    items: KNOWN_KINDS.map((k) => REGISTRY[k]).filter((m) => m.category === g.category),
  }))
}
