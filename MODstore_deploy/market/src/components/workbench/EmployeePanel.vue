<template>
  <section class="workbench-panel employee-entry-panel">
    <div class="employee-entry-card">
      <p class="entry-kicker">AI-native Employee Builder</p>
      <h2>员工制作已升级为三栏 AI 工作台</h2>
      <p class="entry-copy">
        左侧对话与 Agent 流式生成，中间 Vue Flow 画布，右侧属性面板与模块库。
        原统一工作台的首页与 Mod / 工作流 / 连接器保持不变。
      </p>
      <div class="entry-actions">
        <router-link class="entry-primary" :to="{ name: 'workbench-shell', params: { target: 'employee' } }">
          进入员工制作
        </router-link>
        <router-link class="entry-secondary" :to="{ name: 'workbench-my-employees' }">
          查看我的员工
        </router-link>
      </div>
    </div>
  </section>
</template>

<style scoped>
.workbench-panel {
  min-height: 0;
}

.employee-entry-panel {
  display: grid;
  place-items: center;
  min-height: 420px;
  padding: 24px;
}

.employee-entry-card {
  width: min(720px, 100%);
  padding: 28px;
  border: 1px solid rgba(148, 163, 184, 0.18);
  border-radius: 18px;
  background:
    radial-gradient(circle at 10% 10%, rgba(99, 102, 241, 0.22), transparent 32%),
    rgba(15, 23, 42, 0.78);
  color: #e2e8f0;
  box-shadow: 0 24px 70px rgba(0, 0, 0, 0.35);
}

.entry-kicker {
  margin: 0 0 8px;
  color: #a5b4fc;
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.employee-entry-card h2 {
  margin: 0 0 10px;
  font-size: clamp(24px, 3vw, 34px);
}

.entry-copy {
  margin: 0;
  color: #94a3b8;
  line-height: 1.7;
}

.entry-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 22px;
}

.entry-primary,
.entry-secondary {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 38px;
  padding: 0 16px;
  border-radius: 10px;
  font-weight: 800;
  text-decoration: none;
}

.entry-primary {
  color: #fff;
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
}

.entry-secondary {
  color: #cbd5e1;
  border: 1px solid rgba(148, 163, 184, 0.22);
  background: rgba(15, 23, 42, 0.62);
}
</style>
