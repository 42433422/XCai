# MODstore 公网部署完整规划

## 当前状态

| 项目 | 状态 | 说明 |
|---|---|---|
| 注册/登录 | ✅ 完成 | 用户认证、JWT、数据库 |
| MOD 市场 | ✅ 完成 | 商品浏览、购买、下载 |
| 钱包系统 | ✅ 完成 | 余额、交易记录 |
| 支付宝支付 | ✅ 完成 | 下单、回调、二维码 |
| 管理员后台 | ✅ 完成 | 上传商品、用户管理 |
| 深色主题 | ✅ 完成 | 所有页面统一 |
| CORS 配置 | ⚠️ 需配置 | 已通过环境变量支持 |
| JWT 密钥 | ⚠️ 需配置 | 开发密钥不安全 |
| HTTPS | ❌ 未配置 | 支付宝回调必须 |
| 域名解析 | ❌ 未配置 | 需要公网域名 |

## 待完成任务

### 1. 生成生产环境密钥（5 分钟）
- [ ] 生成 JWT 密钥（32 位随机字符串）
- [ ] 生成管理员充值 Token
- [ ] 写入 `.env` 文件

### 2. 域名和服务器配置（30 分钟）
- [ ] 购买/配置域名（如 `modstore.yourdomain.com`）
- [ ] 购买云服务器（阿里云/腾讯云，最低 2 核 2G 即可）
- [ ] 域名解析到服务器 IP
- [ ] 服务器安装 Python 3.11+、Node.js 18+

### 3. HTTPS 证书配置（15 分钟）
- [ ] 申请免费 SSL 证书（Let's Encrypt / 阿里云免费证书）
- [ ] 配置 Nginx 反向代理 + HTTPS
- [ ] 支付宝回调 URL 设置为 `https://你的域名/api/payment/notify/alipay`

### 4. 后端部署（15 分钟）
- [ ] 上传代码到服务器（git clone 或 scp）
- [ ] 安装 Python 依赖：`pip install -r requirements.txt`
- [ ] 创建 `.env` 文件，填写生产配置
- [ ] 使用 `uvicorn` + `gunicorn` 或 `systemd` 启动服务
- [ ] 配置进程守护（systemd 或 supervisor）

### 5. 前端构建和部署（10 分钟）
- [ ] 构建 market 前端：`cd market && npm run build`
- [ ] 构建 web 前端：`cd web && npm run build`
- [ ] 将 dist 文件部署到服务器
- [ ] 配置 Nginx 静态文件服务 + API 反向代理

### 6. Nginx 配置（核心，20 分钟）

完整 Nginx 配置模板：
```nginx
server {
    listen 80;
    server_name your-domain.com;
    # 强制 HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com;
    
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    
    # 前端静态文件（market）
    location / {
        root /path/to/market/dist;
        try_files $uri $uri/ /index.html;
    }
    
    # web 工作台前端
    location /workspace {
        alias /path/to/web/dist;
        try_files $uri $uri/ /workspace/index.html;
    }
    
    # 后端 API 反向代理
    location /api/ {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    # WebSocket 支持（如果需要）
    location /ws/ {
        proxy_pass http://127.0.0.1:8080;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

### 7. 支付宝配置（如果需要支付，20 分钟）
- [ ] 支付宝开放平台创建应用
- [ ] 配置应用网关地址：`https://你的域名`
- [ ] 生成 RSA2 密钥对
- [ ] 上传应用公钥到支付宝
- [ ] 设置授权回调地址
- [ ] 在 `.env` 中填写支付宝配置
- [ ] `ALIPAY_NOTIFY_URL=https://你的域名/api/payment/notify/alipay`
- [ ] `ALIPAY_DEBUG=0`（关闭沙箱）

### 8. 安全加固（重要，30 分钟）
- [ ] 服务器防火墙配置（只开放 80/443 端口）
- [ ] 禁用 Python 调试模式
- [ ] 设置 CORS_ORIGINS 为实际域名
- [ ] 配置数据库备份（SQLite 文件定期备份）
- [ ] 日志配置和监控

## 部署顺序建议

```
生成密钥 → 购买服务器 → 域名解析 → 部署代码 → 配置 Nginx → 配置 HTTPS → 
配置支付宝 → 测试全流程 → 上线
```

## 最低服务器配置

| 项目 | 最低配置 | 推荐配置 |
|---|---|---|
| CPU | 2 核 | 4 核 |
| 内存 | 2GB | 4GB |
| 硬盘 | 20GB SSD | 50GB SSD |
| 带宽 | 1Mbps | 5Mbps |
| 月费预估 | ¥30-50 | ¥80-120 |

## 本地开发测试检查清单

在部署到公网之前，本地确认以下内容都正常：
- [ ] 注册新用户，登录成功，token 保存
- [ ] 登录后能看到用户信息
- [ ] 浏览市场商品
- [ ] 购买商品（免费商品直接获取，付费商品走支付）
- [ ] 钱包余额变动记录
- [ ] 管理员上传商品
- [ ] 支付宝支付流程（沙箱模式）
- [ ] 页面刷新后登录状态保持

## 部署后验证

- [ ] 通过 HTTPS 访问正常
- [ ] 注册/登录功能正常
- [ ] CORS 不报错（前端能正常调用 API）
- [ ] 支付宝回调能收到通知
- [ ] 支付成功后自动发放权益
- [ ] 页面加载速度可接受

## 后续优化（可选）
- [ ] 数据库从 SQLite 迁移到 PostgreSQL
- [ ] 接入 CDN 加速静态资源
- [ ] 配置自动备份脚本
- [ ] 添加监控告警（如 Sentry）
- [ ] 支持更多支付方式（微信）
