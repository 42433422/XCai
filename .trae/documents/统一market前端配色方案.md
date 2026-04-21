# 统一 market 前端配色方案

## 问题
market 前端现有页面使用了两种完全不同的配色方案，视觉上严重不统一：

| 页面组 | 背景色 | 文字色 | 卡片色 | 风格 |
|---|---|---|---|---|
| HomeView / CatalogDetail / Login / Register / MyStore / Wallet | `#f8f9fa` / `#fff` | `#1a1a2e` | `#fff` | 浅色 |
| PaymentPlansView / PaymentCheckoutView / OrderDetailView | `#0a0a0a` | `#ffffff` | `rgba(255,255,255,0.02)` | 深色 |

## 方案选择

### 方案 A：全部统一为深色主题（推荐）
- 符合 Krea.ai 的设计语言
- 现代感更强
- 支付页面已经做好深色，改动较少
- 需要修改：HomeView、CatalogDetailView、LoginView、RegisterView、MyStoreView、WalletView、AdminView、App.vue

### 方案 B：全部统一为浅色主题
- 传统风格
- 市场页面已经做好，改动较少
- 需要修改：PaymentPlansView、PaymentCheckoutView、OrderDetailView、App.vue

## 实施步骤

### 选择方案 A（深色主题）

#### 1. 修改 `market/src/App.vue`
- 背景色改为 `#0a0a0a`
- 文字色改为 `#ffffff`
- 导航栏边框 `rgba(255,255,255,0.1)`
- 按钮颜色适配深色主题

#### 2. 修改 `market/src/views/HomeView.vue`
- 页面背景：`#0a0a0a`
- 卡片背景：`#111111`，边框 `rgba(255,255,255,0.1)`
- 标题文字：`#ffffff`
- 副标题/描述：`rgba(255,255,255,0.5)`
- 标签背景：`rgba(255,255,255,0.06)`
- 按钮：白色背景 + 黑色文字（btn-primary-solid 改为反向）

#### 3. 修改 `market/src/views/CatalogDetailView.vue`
- 文字颜色适配深色主题
- 价格、徽章等元素颜色适配

#### 4. 修改 `market/src/views/LoginView.vue`
- 卡片背景改为 `#111111`，边框 `rgba(255,255,255,0.1)`
- 输入框边框改为 `rgba(255,255,255,0.15)`
- 文字颜色适配

#### 5. 修改 `market/src/views/RegisterView.vue`
- 同上

#### 6. 修改 `market/src/views/MyStoreView.vue`
- 同上

#### 7. 修改 `market/src/views/WalletView.vue`
- 同上

#### 8. 修改 `market/src/views/AdminView.vue`
- 适配深色主题

#### 9. 检查全局 CSS（如有 style.css 或 index.html 中的全局样式）
- 确保 body 背景为 `#0a0a0a`

### 深色主题设计变量
```
--bg:        #0a0a0a
--bg-card:   #111111
--border:    rgba(255, 255, 255, 0.1)
--text:      #ffffff
--text-sec:  rgba(255, 255, 255, 0.5)
--muted:     rgba(255, 255, 255, 0.3)
--accent:    #ffffff（按钮等）
```

## 影响范围
- 只修改 market 前端的样式文件
- 不影响 web 前端（工作台）
- 不影响后端服务
- 不涉及功能逻辑变更
