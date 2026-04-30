# 工作流编辑器 UI 风格重塑计划

## 问题概述

当前 `workflow/v2` 可视化编辑器存在以下视觉问题：
1. **整体风格偏素**：大量灰色背景（#f8fafc、#f1f5f9），缺乏品牌感和层次感
2. **节点卡片简陋**：白色方块+细边框，缺乏质感，hover/selected 状态不够醒目
3. **面板风格不统一**：左侧节点库、右侧属性面板、顶部工具栏各自为政
4. **缺乏视觉层级**：画布、面板、节点之间没有明显的主次关系
5. **细节粗糙**：阴影过浅、圆角不统一、字体层级混乱

## 目标

将工作流编辑器从「简陋的灰白风格」升级为「现代深色/玻璃拟态风格」，提升专业感和品牌辨识度。

---

## 阶段 1：全局主题变量与画布背景

### 1.1 定义统一 CSS 变量

在 `WorkflowFlowEditor.vue` 的 `<style>` 中引入 CSS 变量体系：

```css
:root {
  /* 画布 */
  --wf-canvas-bg: #0f172a;
  --wf-canvas-grid: rgba(148, 163, 184, 0.08);
  
  /* 面板 */
  --wf-panel-bg: rgba(15, 23, 42, 0.85);
  --wf-panel-border: rgba(148, 163, 184, 0.12);
  --wf-panel-backdrop: blur(12px);
  
  /* 节点 */
  --wf-node-bg: rgba(30, 41, 59, 0.95);
  --wf-node-border: rgba(148, 163, 184, 0.15);
  --wf-node-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.3), 0 2px 4px -2px rgba(0, 0, 0, 0.2);
  --wf-node-shadow-hover: 0 20px 25px -5px rgba(0, 0, 0, 0.4), 0 8px 10px -6px rgba(0, 0, 0, 0.3);
  --wf-node-shadow-selected: 0 0 0 2px var(--accent), 0 20px 25px -5px rgba(0, 0, 0, 0.4);
  
  /* 文字 */
  --wf-text-primary: #f1f5f9;
  --wf-text-secondary: #94a3b8;
  --wf-text-muted: #64748b;
  
  /* 工具栏 */
  --wf-toolbar-bg: rgba(15, 23, 42, 0.9);
  --wf-toolbar-border: rgba(148, 163, 184, 0.1);
}
```

### 1.2 画布背景改造

修改 `WorkflowFlowEditor.vue`：
- `.wf2` 背景从 `#f8fafc` → `#0f172a`（深色）
- `.wf2-canvas-wrap` 背景从 `#f1f5f9` → `#0f172a`
- `<Background>` 的 `pattern-color` 从 `#cbd5e1` → `rgba(148, 163, 184, 0.08)`
- 添加 subtle grid 效果（可考虑自定义 CSS 背景图案替代默认 Background）

---

## 阶段 2：节点卡片重塑（GenericNode.vue）

### 2.1 节点外观升级

```css
.wf2-node {
  --accent: #6366f1;
  position: relative;
  width: 240px;                    /* 加宽 */
  min-height: 100px;
  background: rgba(30, 41, 59, 0.95);
  border: 1px solid rgba(148, 163, 184, 0.15);
  border-left: 3px solid var(--accent);
  border-radius: 14px;             /* 更大圆角 */
  box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.3),
              0 2px 4px -2px rgba(0, 0, 0, 0.2);
  padding: 14px 16px 16px;
  backdrop-filter: blur(8px);      /* 玻璃感 */
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
}

.wf2-node:hover {
  box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.4),
              0 8px 10px -6px rgba(0, 0, 0, 0.3);
  border-color: rgba(148, 163, 184, 0.25);
  transform: translateY(-2px);
}

.wf2-node--selected {
  border-color: var(--accent);
  box-shadow: 0 0 0 2px color-mix(in srgb, var(--accent) 40%, transparent),
              0 20px 25px -5px rgba(0, 0, 0, 0.4);
}
```

### 2.2 节点内部元素

- **图标**：增大到 32x32，添加发光效果 `box-shadow: 0 0 12px color-mix(in srgb, var(--accent) 30%, transparent)`
- **类型标签**：改为深色背景 chip 样式，而非纯文字
- **名称**：白色 `#f1f5f9`，font-weight 700
- **摘要**：`#94a3b8`，添加图标前缀表示状态
- **Handle**：增大到 12x12，添加 glow 效果

### 2.3 条件分支标签

- `true`/`false` 标签改为 pill 形状，带背景色
- true: 绿色背景 + 白色文字
- false: 红色背景 + 白色文字

---

## 阶段 3：工具栏重塑（ToolbarPanel.vue）

### 3.1 玻璃拟态工具栏

```css
.wf2-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 12px 20px;
  background: rgba(15, 23, 42, 0.85);
  backdrop-filter: blur(12px);
  border-bottom: 1px solid rgba(148, 163, 184, 0.1);
  position: relative;
  z-index: 10;
}
```

### 3.2 按钮样式统一

- 普通按钮：透明背景 + 边框 `rgba(148, 163, 184, 0.2)` + `#e2e8f0` 文字
- Hover：背景 `rgba(148, 163, 184, 0.1)`
- Primary（立即执行）：渐变背景 `linear-gradient(135deg, #6366f1, #8b5cf6)` + 白色文字 + glow
- 状态标签：绿色/灰色 pill 形状，带发光

### 3.3 标题区域

- 工作流名称：更大字号（18px），白色，hover 时显示编辑图标
- 添加面包屑或路径指示

---

## 阶段 4：左侧面板重塑（NodeLibraryPanel.vue）

### 4.1 玻璃拟态侧边栏

```css
.wf2-library {
  width: 260px;
  flex-shrink: 0;
  background: rgba(15, 23, 42, 0.8);
  backdrop-filter: blur(12px);
  border-right: 1px solid rgba(148, 163, 184, 0.1);
  padding: 20px 14px;
}
```

### 4.2 分组头部

- 添加左侧彩色竖条指示器（与节点 accent 色对应）
- 展开/折叠动画
- 计数 badge 改为深色背景

### 4.3 节点项

- 悬停效果：背景 `rgba(255,255,255,0.05)` + 左侧 accent 色竖条
- 图标：32x32，带 subtle glow
- 标签：白色，描述：灰色
- 添加拖拽时的 ghost 效果

---

## 阶段 5：右侧面板重塑（PropertiesPanel.vue）

### 5.1 玻璃拟态属性面板

```css
.wf2-properties {
  width: 340px;                    /* 加宽 */
  flex-shrink: 0;
  background: rgba(15, 23, 42, 0.8);
  backdrop-filter: blur(12px);
  border-left: 1px solid rgba(148, 163, 184, 0.1);
}
```

### 5.2 表单元素

- 输入框：深色背景 `rgba(30, 41, 59, 0.8)` + 浅色边框 + 白色文字
- Focus：accent 色边框 + glow
- 标签：灰色，加粗
- 必填标记：红色
- Helper 文字：更暗的灰色

### 5.3 空状态

- 添加插画或图标
- 文字：灰色，居中

---

## 阶段 6：连线与交互效果

### 6.1 连线样式

- 默认：灰色 `rgba(148, 163, 184, 0.3)`，2px
- Hover：accent 色，3px，带 glow
- 选中：accent 色，3px，animated dash

### 6.2 添加/删除动画

- 节点添加：scale(0.8) → scale(1) + fade in
- 节点删除：scale(1) → scale(0.8) + fade out
- 连线添加：stroke-dasharray 动画

---

## 阶段 7：辅助元素优化

### 7.1 Flash 提示

- 改为顶部居中 slide-down 动画
- 成功：绿色背景 + 白色文字 + check 图标
- 错误：红色背景 + 白色文字 + error 图标

### 7.2 沙盒结果面板

- 玻璃拟态背景
- 代码块：深色背景 + 语法高亮（可考虑 simple-highlight）

### 7.3 版本历史面板

- 玻璃拟态
- 当前版本：带发光边框
- 时间线样式：左侧竖线 + 圆点

### 7.4 空画布提示

- 中央大图标 + 文字
- 添加「快速开始」快捷按钮（如：添加开始节点）

---

## 阶段 8：空状态与加载状态

### 8.1 加载动画

- 骨架屏或 spinner
- 深色主题适配

### 8.2 空画布

```
[大图标：流程图示意]
从左侧拖入节点开始编排
[按钮：添加开始节点] [按钮：从模板导入]
```

---

## 实施顺序

| 优先级 | 阶段 | 文件 | 预计影响 |
|--------|------|------|----------|
| P0 | 画布背景 + 主题变量 | WorkflowFlowEditor.vue | 全局底色 |
| P0 | 节点卡片重塑 | GenericNode.vue | 最核心视觉 |
| P1 | 工具栏 | ToolbarPanel.vue | 顶部视觉 |
| P1 | 左侧面板 | NodeLibraryPanel.vue | 侧边视觉 |
| P1 | 右侧面板 | PropertiesPanel.vue | 表单视觉 |
| P2 | 连线效果 | WorkflowFlowEditor.vue (edge options) | 交互质感 |
| P2 | 辅助元素 | VersionsPanel.vue, Flash, Sandbox | 细节完善 |
| P3 | 动画与过渡 | 多个文件 | 流畅感 |

---

## 注意事项

1. **保持 Vue Flow 兼容性**：不要覆盖 Vue Flow 核心样式，只调整自定义节点和容器
2. **响应式**：确保深色主题下所有文字可读
3. **性能**：backdrop-filter 不宜过多，关键面板使用即可
4. **一致性**：所有颜色从 CSS 变量获取，不要硬编码
5. **可维护性**：将变量提取到独立文件 `workflow-theme.css`
