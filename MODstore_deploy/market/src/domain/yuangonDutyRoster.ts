/**
 * 与 modstore_server/duty_roster.py、AdminDutyEmployeeGraph 编制矩阵一致。
 * 用于工作台等场景判断「MODstore 在岗」编制内员工包，以便 UI 标记与删除保护。
 */
export const YUANGON_AREAS: Record<string, { label: string; ids: string[] }> = {
  'site-and-marketing': {
    label: '对外网站与 SEO',
    ids: ['site-content-editor', 'seo-sitemap-curator', 'flask-entry-keeper'],
  },
  'server-and-ops': {
    label: '服务器与运维',
    ids: [
      'nginx-config-engineer',
      'push-update-context-officer',
      'deploy-release-officer',
      'security-secrets-guard',
      'log-monitor-incident',
      'retention-officer',
      'dbops-engineer',
    ],
  },
  'modstore-backend': {
    label: 'MODstore 后端',
    ids: ['modstore-backend-api', 'employee-pack-curator', 'payment-billing-reconciler'],
  },
  'modstore-frontend': {
    label: 'MODstore 前端',
    ids: ['market-frontend-dev', 'workbench-ux-stylist'],
  },
  'platform-core': {
    label: '平台核心',
    ids: [
      'vibe-coding-maintainer',
      'mods-and-eskill-curator',
      'change-request-auditor',
      'daily-orchestrator',
      'intake-dispatcher',
      'task-router-officer',
    ],
  },
  'quality-and-docs': {
    label: '质量与文档',
    ids: [
      'test-qa-runner',
      'doc-knowledge-curator',
      'employee-interview-assistant',
      'employee-pack-quality-interviewer',
    ],
  },
}

/** 编制内全部 pkg_id（与后端 duty_roster.all_planned_employee_ids 对齐） */
export const ALL_PLANNED_YUANGON_PKG_IDS: ReadonlySet<string> = new Set(
  Object.values(YUANGON_AREAS).flatMap((a) => a.ids),
)

/**
 * 管理端值班图固定展示名（与 docs/routing-table.md 索引列中文名一致），
 * 不依赖 catalog 数据库里的 name 字段。
 */
export const YUANGON_PKG_ROLE_LABELS: Record<string, string> = {
  'site-content-editor': '静态站内容编辑员',
  'seo-sitemap-curator': 'SEO 站点地图管理员',
  'flask-entry-keeper': 'Flask 入口维护员',
  'nginx-config-engineer': 'Nginx 配置工程师',
  'push-update-context-officer': '推送更新员工',
  'deploy-release-officer': '发布部署主管',
  'security-secrets-guard': '安全密钥守卫',
  'log-monitor-incident': '日志监控与事故响应员',
  'retention-officer': '档案清理员',
  'dbops-engineer': '数据库运维工程师',
  'modstore-backend-api': 'MODstore 后端 API 员',
  'employee-pack-curator': '员工包策展员',
  'payment-billing-reconciler': '支付账单对账员',
  'market-frontend-dev': '市场前端开发员',
  'workbench-ux-stylist': '工作台 UX 设计员',
  'vibe-coding-maintainer': 'Vibe-Coding 维护员',
  'mods-and-eskill-curator': 'Mods/ESkill 策展员',
  'change-request-auditor': '变更评审员',
  'daily-orchestrator': '每日编排员',
  'intake-dispatcher': '需求接入员',
  'task-router-officer': '任务派发员',
  'test-qa-runner': '测试质量运行员',
  'doc-knowledge-curator': '文档知识管理员',
  'employee-interview-assistant': '员工信息访谈员',
  'employee-pack-quality-interviewer': '员工包质询员',
}
