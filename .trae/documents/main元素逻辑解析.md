# `main` 元素逻辑解析

## 对应源文件

`src/views/AiStoreView.vue` — 这是一个 Vue 3 Composition API 组件，对应浏览器中 `<main class="main-content">` 区域的渲染内容。

## 整体结构

`main` 内部由 `.main-content-router` 包裹，实际内容来自 `<div class="store-page">`，分为四个区域：

| 区域 | CSS 类 | 作用 |
|------|--------|------|
| 头部横幅 | `.store-hero` | 展示页面标题和说明文案 |
| 工具栏 | `.store-toolbar` | 搜索框 + 行业筛选 + 类型筛选 |
| 状态提示 | `.flash` / `.state-msg` | 错误信息、加载中、空状态 |
| 商品网格 | `.store-grid` | 卡片列表展示商品 |

---

## 详细逻辑

### 1. 页面初始化 (`onMounted`)

组件挂载时依次执行：

```
onMounted()
  ├─ loadFacets()   // 获取筛选面数据（行业列表、类型列表）
  └─ loadItems()    // 获取初始商品列表
```

### 2. 数据获取

#### `loadFacets()` — 获取筛选面

- 调用 `api.catalogFacets()` 获取服务端返回的 `industries[]` 和 `artifacts[]`
- 失败时降级为空数组，不影响页面渲染

#### `loadItems()` — 获取商品列表

- 参数:
  - `appliedQ.value` — 搜索关键词
  - `filters.artifact` — 类型过滤
  - `80` — 每页最大条数
  - `0` — 偏移量
  - `filters.industry` — 行业过滤
- 赋值 `items.value`（商品列表）和 `total.value`（总数）
- 失败时设置 `err.value` 显示错误横幅

### 3. 筛选与搜索

#### 搜索流程

```
用户输入搜索文本 (v-model="searchQ")
  → 点击「搜索」按钮 / 按 Enter
    → applyFilters()
      → appliedQ.value = searchQ.value.trim()
      → loadItems()  // 用新关键词重新请求
```

#### 行业筛选

```
点击行业 chip 按钮
  → setIndustry(industryName)
    → filters.industry = industryName
      → watch 自动触发 loadItems()
```

#### 类型筛选

```
点击类型 chip 按钮
  → setArtifact(artifactType)
    → filters.artifact = artifactType
      → watch 自动触发 loadItems()
```

#### 重置

```
点击「重置」按钮
  → resetFilters()
    → 清空 searchQ、appliedQ、filters.industry、filters.artifact
    → loadItems()  // 重新加载全部数据
```

#### 自动触发机制

```javascript
watch(
  () => [filters.industry, filters.artifact],
  () => { loadItems() }
)
```

当行业或类型筛选条件变化时，自动重新请求数据，无需手动点击。

### 4. 商品卡片渲染

每个商品卡片展示：

```
.card-tags
  ├─ 行业标签 (tag-industry)    ← item.industry || '通用'
  ├─ 类型标签 (tag-type)        ← artifactLabel(item.artifact)
  └─ 已购标签 (tag-owned)       ← item.purchased ? 显示 : 隐藏

.card-title                     ← item.name
.card-desc                      ← truncate(item.description, 120)
.card-meta                      ← item.pkg_id · vitem.version

.card-footer
  ├─ 价格                       ← 免费(item.price<=0) 或 ¥item.price.toFixed(2)
  └─ 「详情」按钮               ← 路由跳转到 catalog-detail/:id
```

### 5. 状态展示

| 条件 | 展示内容 |
|------|----------|
| `err` 有值 | 红色错误横幅，显示错误信息 |
| `loading === true` | "加载中…" |
| `!items.length` (无数据) | "暂无符合的商品，试试调整筛选或搜索。" |
| 正常数据 | `.store-grid` 商品卡片列表 |
| `total > items.length` | 分页提示："共 N 条，当前展示前 M 条。" |

### 6. 类型映射

```javascript
const ARTIFACT_LABELS = {
  mod: 'MOD 插件',
  employee_pack: 'AI 员工包',
  bundle: '资源包',
  surface: '界面扩展',
}
```

### 7. 关键响应式变量

| 变量 | 类型 | 用途 |
|------|------|------|
| `loading` | `ref<boolean>` | 加载状态 |
| `err` | `ref<string>` | 错误信息 |
| `items` | `ref<Array>` | 商品列表 |
| `total` | `ref<number>` | 商品总数 |
| `searchQ` | `ref<string>` | 搜索框输入值 |
| `appliedQ` | `ref<string>` | 已应用的搜索关键词 |
| `facets` | `ref<Object>` | 筛选面原始数据 |
| `filters` | `reactive<Object>` | 当前筛选条件 `{ industry, artifact }` |

---

## 数据流总结

```
用户操作 (搜索/筛选/重置)
  ↓
更新响应式状态 (searchQ / filters)
  ↓
触发 loadItems()
  ↓
调用 api.catalog(query, artifact, limit, offset, industry)
  ↓
更新 items / total / err
  ↓
模板根据状态渲染不同视图
```
