# MODstore 前端

这是 MODstore 项目的前端代码仓库，基于 Vue 3 + Vite 构建。

## 项目结构

```
├── src/
│   ├── router/         # 路由配置
│   │   └── index.js    # 路由定义
│   ├── views/          # 页面组件
│   │   ├── HomeView.vue         # 首页
│   │   ├── RepositoryView.vue   # 仓库管理页面
│   │   ├── LoginByEmailView.vue # 邮箱验证码登录
│   │   └── ...                 # 其他页面
│   ├── App.vue         # 主应用组件
│   ├── api.js          # API 配置
│   ├── main.js         # 应用入口
│   └── style.css       # 全局样式
├── index.html          # HTML 模板
├── package.json        # 项目配置
├── package-lock.json   # 依赖锁定
└── vite.config.js      # Vite 配置
```

## 主要功能

- **现代化首页**：包含视频演示、功能介绍和统计数据
- **仓库管理**：MOD 列表和操作管理
- **邮箱验证码登录**：安全的登录方式
- **管理员/客户端视图分离**：不同角色的界面
- **SPA 路由**：单页应用路由系统

## 技术栈

- Vue 3
- Vite
- Vue Router
- JavaScript
- CSS3

## 开发命令

```bash
# 安装依赖
npm install

# 启动开发服务器
npm run dev

# 构建生产版本
npm run build

# 预览生产构建
npm run preview
```

## 部署

构建后的文件将输出到 `dist` 目录，可直接部署到任何静态文件服务器。

## 相关链接

- 后端 API：MODstore 后端服务
- 生产环境：https://www.xiu-ci.com/new/