# MODstore 用户登录与个性化MOD管理计划

## 需求分析

为 MODstore 添加用户登录/注册功能，实现以下目标：
1. 用户可以通过注册/登录访问系统
2. 登录后用户只能看到自己的 MOD
3. 支持标准的 Web 注册登录流程
4. 服务器端管理用户与 MOD 的关联关系

## 当前状态

- **后端**：已有完整的认证系统（`auth_service.py`），包含 JWT 认证、用户注册/登录 API（`market_api.py`）
- **数据库**：已有 User、Wallet 等模型（`models.py`），使用 SQLite
- **市场前端**（`market/`）：已有登录注册页面和 API 调用
- **主前端**（`web/`）：目前没有登录功能，所有 MOD 对所有用户可见

## 实施步骤

### 第一阶段：数据库扩展

**步骤 1：修改数据模型**
- 文件：`modstore_server/models.py`
- 在 `CatalogItem` 或新建模型中添加 `owner_id` 字段关联用户
- 创建用户与 MOD 的关联表 `UserMod`
- 添加数据库迁移支持

**步骤 2：修改 MOD 列表 API**
- 文件：`modstore_server/app.py`
- 修改 `/api/mods` 接口，添加认证依赖
- 根据当前用户过滤返回的 MOD 列表
- 修改 `/api/mods/create` 接口，创建 MOD 时自动关联当前用户

### 第二阶段：前端认证集成

**步骤 3：创建认证 API 模块**
- 文件：`web/src/auth.js`（新建）
- 实现登录、注册、获取用户信息 API
- 实现 token 存储和管理
- 实现请求拦截器自动添加认证头

**步骤 4：创建登录页面**
- 文件：`web/src/views/LoginView.vue`（新建）
- 登录表单：用户名、密码
- 注册表单切换
- 错误处理和成功提示

**步骤 5：修改路由配置**
- 文件：`web/src/router/index.js`
- 添加登录路由
- 添加路由守卫，未登录用户重定向到登录页
- 允许未登录访问特定页面（如公开 MOD 列表）

### 第三阶段：用户界面集成

**步骤 6：修改主应用布局**
- 文件：`web/src/App.vue`
- 添加用户信息栏
- 添加登录/登出按钮
- 显示当前用户名

**步骤 7：修改主页**
- 文件：`web/src/views/HomeView.vue`
- 修改 MOD 列表加载逻辑，传递用户认证
- 添加"我的 MOD"过滤选项
- 更新 API 调用添加认证头

### 第四阶段：后端权限控制

**步骤 8：完善权限验证**
- 文件：`modstore_server/app.py`
- 添加 `require_auth` 依赖函数
- 修改所有 MOD 操作接口（读、写、删除）添加权限检查
- 确保用户只能操作自己的 MOD

**步骤 9：管理员功能**
- 为管理员用户添加查看所有 MOD 的权限
- 添加用户管理接口（可选）

### 第五阶段：测试与优化

**步骤 10：功能测试**
- 测试注册流程
- 测试登录流程
- 测试 MOD 创建和查看的权限隔离
- 测试未登录用户的访问限制

**步骤 11：错误处理**
- 完善 API 错误响应
- 添加前端友好的错误提示
- 处理 token 过期情况

## 技术要点

### 认证流程
1. 用户注册 → 创建用户记录 → 返回 JWT token
2. 用户登录 → 验证密码 → 返回 JWT token
3. 前端存储 token 到 localStorage
4. 每次请求自动携带 `Authorization: Bearer <token>` 头
5. 后端验证 token，获取当前用户

### 数据隔离
- MOD 列表按 `owner_id` 过滤
- 创建 MOD 时自动设置 `owner_id`
- 修改/删除 MOD 时验证 `owner_id` 匹配

### 安全考虑
- 密码使用 bcrypt 加密存储
- JWT token 设置合理过期时间
- 防止越权访问
- 输入验证和 SQL 注入防护

## 文件变更清单

### 新建文件
- `web/src/auth.js` - 认证相关 API 和工具
- `web/src/views/LoginView.vue` - 登录注册页面

### 修改文件
- `modstore_server/models.py` - 添加用户-MOD 关联
- `modstore_server/app.py` - 添加认证依赖和权限控制
- `web/src/api.js` - 添加认证相关 API 调用
- `web/src/router/index.js` - 添加路由和守卫
- `web/src/App.vue` - 添加用户信息展示
- `web/src/views/HomeView.vue` - 集成认证和用户隔离

## 预期结果

完成后，MODstore 将具备：
- 完整的用户注册/登录功能
- 基于用户的 MOD 数据隔离
- 友好的登录界面和用户体验
- 安全的认证和授权机制
- 管理员可查看/管理所有用户 MOD
