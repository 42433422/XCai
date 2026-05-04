# MODstore 轻量级 FHD/XCAGI 在线沙箱页面计划

## 一、核心思路

**不是做新 UI，而是直接嵌入 FHD 前端界面**——在 MODstore 中打开一个页面，里面就是 FHD 的前端（侧栏 + 内容区），只是砍掉不必要的路由，只保留测试相关的核心页面。

用户在 MODstore 里做完 Mod/员工包 → 点「在线测试」→ 直接看到 FHD 的界面 → 在真实环境中测试功能。

## 二、实现方案

### 方案：iframe 嵌入 + FHD 沙箱模式

```
┌─────────────────────────────────────────────────────────────────┐
│  MODstore 市场前端                                               │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  沙箱工具栏（宿主URL / 连接状态 / 快捷操作）                │  │
│  ├───────────────────────────────────────────────────────────┤  │
│  │                                                           │  │
│  │  <iframe src="{fhd_url}/?sandbox=1">                      │  │
│  │    ┌──────────┬──────────────────────────────────────┐    │  │
│  │    │ FHD 侧栏  │  FHD 内容区                           │    │  │
│  │    │ (精简版)  │  (Chat / 员工空间 / 工作流等)          │    │  │
│  │    │          │                                      │    │  │
│  │    │ • AI助手  │                                      │    │  │
│  │    │ • 员工空间│                                      │    │  │
│  │    │ • 工作流  │                                      │    │  │
│  │    │ • Mod详情│                                      │    │  │
│  │    └──────────┴──────────────────────────────────────┘    │  │
│  │  </iframe>                                                │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### 2.1 FHD 侧改动：新增 `sandbox` 查询参数模式

在 FHD 前端路由中增加沙箱模式支持。当 URL 带 `?sandbox=1` 时：

**保留的路由（测试核心）**：
| 路由 | 视图 | 用途 |
|------|------|------|
| `/` | ChatView | AI 对话测试 |
| `/workflow-employee-space` | EmployeeWorkspaceView | 员工空间测试 |
| `/workflow-employee-space/stitch-full` | YuangongStitchFullView | 员工工作流全景 |
| `/workflow-visualization` | WorkflowVisualizationView | 工作流可视化 |
| `/mod/:modId` | ModLandingView | Mod 详情测试 |
| `/chat-debug` | ChatDebugView | 聊天调试 |
| `/tools` | ToolsView | 工具测试 |

**隐藏的路由（非测试必需）**：
| 路由 | 原因 |
|------|------|
| `/products`, `/materials`, `/orders` 等 | 业务 CRUD，与测试无关 |
| `/print`, `/printer-list` | 硬件依赖，沙箱无法使用 |
| `/settings`, `/desktop-runtime` | 系统配置，非测试场景 |
| `/wechat-contacts` | 需要微信环境 |
| `/approval-hub` | 审批流程，非测试核心 |
| `/business-docking` | 业务对接，非测试核心 |
| `/model-payment`, `/kitten-finance` | 支付/财务，非测试核心 |
| `/ai-ecosystem`, `/brain` | 展示页，非测试核心 |
| `/traditional-mode` | 传统模式，非测试核心 |
| `/lan-gate` | 局域网授权，非测试核心 |

**实现方式**：在 FHD 前端 `router/index.ts` 中，根据 `?sandbox=1` 参数过滤路由：

```typescript
const isSandbox = new URLSearchParams(window.location.search).has('sandbox')

const allRoutes: RouteRecordRaw[] = [ /* 现有全部路由 */ ]

const SANDBOX_ALLOWED = new Set(['chat', 'workflow-employee-space', ...])

const routes = isSandbox
  ? allRoutes.filter(r => SANDBOX_ALLOWED.has(r.name as string))
  : allRoutes
```

同时在 `Sidebar.vue` 中，沙箱模式下隐藏非测试菜单项。

### 2.2 MODstore 侧改动：新增沙箱页面

**新增文件**：

```
market/src/
├── views/
│   └── SandboxView.vue              # 沙箱页面（工具栏 + iframe）
├── composables/
│   └── useHostConnection.ts         # 宿主连接状态管理
└── application/
    └── sandboxApi.ts                # 沙箱 API 客户端
```

**SandboxView.vue 核心结构**：

```vue
<template>
  <div class="sandbox-page">
    <!-- 工具栏 -->
    <div class="sandbox-toolbar">
      <div class="host-config">
        <input v-model="hostUrl" placeholder="宿主地址 (如 http://127.0.0.1:8000)" />
        <button @click="connect">连接</button>
        <span :class="statusClass">{{ statusText }}</span>
      </div>
      <div class="quick-actions">
        <button @click="pushAndTest">推送当前Mod并测试</button>
        <button @click="openFullscreen">全屏</button>
      </div>
    </div>
    <!-- FHD 前端 iframe -->
    <iframe
      v-if="connected"
      :src="iframeSrc"
      class="sandbox-iframe"
      allow="clipboard-read; clipboard-write"
    />
    <div v-else class="sandbox-placeholder">
      请输入 FHD/XCAGI 宿主地址并连接
    </div>
  </div>
</template>
```

**后端新增**：

```
modstore_server/
└── sandbox_api.py                   # 沙箱 API（连接测试 + 推送并测试）
```

新增 API：
- `POST /api/sandbox/connect` — 测试宿主连通性（调用 `{host}/api/health`）
- `POST /api/sandbox/push-and-test` — 将指定 Mod push 到宿主 + 返回 iframe URL
- `GET /api/sandbox/host-status` — 代理查询宿主状态（复用现有 `api/xcagi/loading-status`）

### 2.3 iframe 通信（可选增强）

如果需要 MODstore 工具栏与 FHD iframe 之间通信（如自动跳转到指定 Mod 页面）：

```typescript
// MODstore 侧发送
iframe.contentWindow.postMessage({ type: 'sandbox:navigate', path: '/mod/my-mod' }, '*')

// FHD 侧接收
window.addEventListener('message', (e) => {
  if (e.data?.type === 'sandbox:navigate') {
    router.push(e.data.path)
  }
})
```

---

## 三、实施步骤

### 步骤 1：FHD 前端增加沙箱模式（路由过滤 + 侧栏精简）

1. 修改 `frontend/src/router/index.ts`：根据 `?sandbox=1` 过滤路由
2. 修改 `frontend/src/components/Sidebar.vue`：沙箱模式下隐藏非测试菜单
3. 修改 `frontend/src/App.vue`：沙箱模式下跳过开机动画（直接显示主界面）
4. 修改 `frontend/src/components/MainLayout.vue`：沙箱模式下隐藏顶栏非必要元素
5. 确保 FHD 的 CORS 配置允许 MODstore 域名嵌入 iframe

### 步骤 2：MODstore 新增沙箱页面

6. 创建 `market/src/views/SandboxView.vue`：工具栏 + iframe
7. 创建 `market/src/composables/useHostConnection.ts`：宿主连接管理
8. 创建 `market/src/application/sandboxApi.ts`：API 客户端
9. 在 `market/src/router/index.ts` 中添加 `/sandbox` 路由
10. 在侧栏菜单中添加「沙箱测试」入口

### 步骤 3：后端沙箱 API

11. 创建 `modstore_server/sandbox_api.py`：连接测试 + 推送并测试
12. 在 `modstore_server/app.py` 中挂载 sandbox_api router

### 步骤 4：集成入口

13. 在工作台首页添加「在线测试」快捷入口
14. 在 Mod 详情页添加「推送并测试」按钮
15. 在员工制作 Step8Testing 添加「宿主沙箱」选项卡

### 步骤 5：iframe 通信增强（可选）

16. FHD 侧添加 `message` 事件监听
17. MODstore 侧添加 `postMessage` 发送逻辑
18. 支持：自动导航到指定 Mod / 自动执行员工 / 自动运行工作流

---

## 四、关键技术细节

### 4.1 iframe 嵌入的 CORS 和 CSP

FHD 后端需要配置：
- `CORS_ORIGINS` 添加 MODstore 域名
- `Content-Security-Policy` 的 `frame-ancestors` 允许 MODstore 域名
- FHD 的 `SecurityHeadersMiddleware` 中 `x-frame-options` 需在沙箱模式下改为 `ALLOW-FROM` 或移除

### 4.2 宿主 URL 配置

复用现有 MODstore 配置中的 `xcagi_backend_url`，用户在「路径与同步」页面已配置过的可直接使用。

### 4.3 沙箱模式下的 FHD 行为差异

| 行为 | 正常模式 | 沙箱模式 |
|------|---------|---------|
| 开机动画 | 完整动画 | 跳过，直接显示 |
| 侧栏菜单 | 全部显示 | 仅测试相关 |
| 路由 | 全部注册 | 仅测试路由 |
| 顶栏角标 | 普通/专业 | 显示「沙箱」标记 |
| 退出按钮 | 无 | 右上角「返回 MODstore」 |

---

## 五、预期效果

1. 用户在 MODstore 做完 Mod → 点「在线测试」
2. 输入宿主 URL → 点连接 → 工具栏显示「已连接」
3. iframe 中加载 FHD 前端（精简版），侧栏只显示 AI 助手 / 员工空间 / 工作流 / Mod 详情
4. 点「推送并测试」→ Mod 自动 push 到宿主 → iframe 自动跳转到该 Mod 页面
5. 在真实 FHD 界面中测试 AI 对话、员工执行、工作流运行
6. 测试完毕点「返回 MODstore」回到制作流程

**核心优势**：零学习成本——用户看到的就是 FHD 的界面，只是少了无关路由。
