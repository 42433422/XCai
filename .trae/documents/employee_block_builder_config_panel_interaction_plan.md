# 配置面板交互优化计划

## 需求
将 `EmployeeBlockBuilder.vue` 的配置面板（右侧 `div.config.right-drawer`）改成：点击哪个画布节点，就只弹出哪个节点对应的配置卡片 `div`，而不是默认展开全部。

## 当前行为分析
- `showAllConfigs` 默认值为 `true`（第 411 行）
- 每个 `cfg-card` 的显示条件是 `v-if="showAllConfigs || selectedModule === 'xxx'"`
- 由于 `showAllConfigs` 默认为 true，所以所有卡片始终显示
- 点击画布节点会设置 `selectedModule = key`，但这对卡片显示没有影响（因为 showAllConfigs 为 true）

## 修改方案

### 步骤 1：修改 `showAllConfigs` 默认值为 `false`
- 文件：`MODstore_deploy/market/src/views/employee-steps/EmployeeBlockBuilder.vue`
- 第 411 行：`const showAllConfigs = ref(true)` 改为 `const showAllConfigs = ref(false)`
- 效果：默认只显示当前选中的模块卡片

### 步骤 2：调整"同时展开全部模块卡片"复选框的交互
- 第 131 行：保持现有复选框逻辑不变
- 当用户勾选时，仍然可以展开全部卡片
- 当用户取消勾选时，恢复只显示选中卡片的模式

### 步骤 3：确保点击画布节点时自动展开对应卡片
- 第 93 行：`@click.stop="selectedModule = key"`
- 这个逻辑已经存在，当 `showAllConfigs` 为 false 时，设置 `selectedModule` 后，对应的 `cfg-card` 会自动显示（因为 `v-if="showAllConfigs || selectedModule === 'xxx'"`）
- 同时需要确保对应的卡片不是折叠状态：在点击节点时，自动展开对应卡片的 `collapsed` 状态
- 修改 `selectedModule` 的赋值逻辑，或者添加 watch，当 `selectedModule` 变化时，将对应模块的 `collapsed` 设为 false

### 步骤 4：添加 `selectedModule` 的 watch 以自动展开对应卡片
- 在 script 中添加 watch：
```javascript
watch(selectedModule, (key) => {
  if (key) {
    collapsed.value = { ...collapsed.value, [key]: false }
  }
})
```
- 这样当点击不同节点时，对应卡片会自动展开

## 修改文件清单
| 文件 | 修改内容 |
|------|----------|
| `MODstore_deploy/market/src/views/employee-steps/EmployeeBlockBuilder.vue` | 1. `showAllConfigs` 默认值改为 `false`<br>2. 添加 `selectedModule` watch 自动展开卡片 |

## 预期效果
1. 页面加载后，配置面板默认只显示当前 `selectedModule`（默认为 `'collaboration'`）对应的卡片
2. 点击画布上的任意节点，右侧配置面板只显示该节点对应的配置卡片，其他卡片隐藏
3. 勾选"同时展开全部模块卡片"后，恢复显示所有卡片
4. 取消勾选后，恢复只显示当前选中卡片的模式
