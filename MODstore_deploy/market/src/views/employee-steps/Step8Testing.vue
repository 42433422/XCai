<template>
  <section>
    <h3 class="ttl">Step8 测试审核</h3>
    <p class="muted">完成沙盒门槛后获取五维审核；通过后再填写行业与价格并确认上架。</p>
    <button type="button" class="btn" @click="$emit('back')">返回修改</button>

    <section v-if="selectedFile" class="sandbox-gate-panel">
      <h4 class="h4">1. 沙盒测试</h4>
      <template v-if="resolvedWorkflowId > 0">
        <p class="muted">当前关联工作流 ID <strong>{{ resolvedWorkflowId }}</strong>。</p>
        <textarea
          class="input ta"
          :value="wfSandboxInputJson"
          @input="$emit('update:wfSandboxInputJson', $event.target.value)"
        />
        <div class="row">
          <button type="button" class="btn btn-primary" :disabled="wfSandboxLoading" @click="$emit('sandbox')">
            {{ wfSandboxLoading ? '运行中…' : '运行沙盒测试' }}
          </button>
        </div>
        <p v-if="wfSandboxErr" class="flash flash-err">{{ wfSandboxErr }}</p>
      </template>
      <template v-else>
        <label class="muted">
          <input :checked="dockerLocalAck" type="checkbox" @change="$emit('update:dockerLocalAck', $event.target.checked)" />
          我已完成本地 / Docker 沙箱冒烟
        </label>
      </template>
    </section>

    <div v-if="selectedFile && !sandboxGateOk" class="flash flash-info">请先完成沙盒测试，再获取五维审核。</div>
    <div v-if="selectedFile && sandboxGateOk" class="row">
      <button type="button" class="btn btn-primary" :disabled="auditLoading" @click="$emit('audit')">
        {{ auditLoading ? '评分中…' : auditReport ? '重新获取五维审核' : '获取五维审核' }}
      </button>
    </div>

    <section v-if="auditLoading || auditErr || auditReport" class="audit-panel">
      <p v-if="auditLoading" class="muted">正在服务端评分…</p>
      <p v-else-if="auditErr" class="flash flash-err">{{ auditErr }}</p>
      <template v-else-if="auditReport">
        <div class="row muted">
          <span>综合分 <strong>{{ auditReport.summary?.average ?? '—' }}</strong></span>
          <span>{{ auditReport.summary?.pass ? '达到上架建议阈值' : '未达建议阈值' }}</span>
        </div>
        <ul v-if="auditReport.functional_tests?.length" class="lst">
          <li v-for="(t, ti) in auditReport.functional_tests" :key="ti">{{ t.name }} - {{ t.detail }}</li>
        </ul>
      </template>
    </section>

    <div v-if="auditReport?.summary?.pass" class="row">
      <button type="button" class="btn btn-primary" @click="$emit('next')">下一步：填写上架信息</button>
    </div>
  </section>
</template>
<script setup>
defineProps({
  selectedFile: { type: [Object, null], default: null },
  resolvedWorkflowId: { type: Number, required: true },
  wfSandboxInputJson: { type: String, required: true },
  wfSandboxLoading: { type: Boolean, required: true },
  wfSandboxErr: { type: String, required: true },
  dockerLocalAck: { type: Boolean, required: true },
  sandboxGateOk: { type: Boolean, required: true },
  auditLoading: { type: Boolean, required: true },
  auditErr: { type: String, required: true },
  auditReport: { type: [Object, null], default: null },
})
defineEmits(['update:wfSandboxInputJson', 'update:dockerLocalAck', 'sandbox', 'audit', 'next', 'back'])
</script>
<style scoped>
.ttl{margin:.1rem 0 .45rem;color:#fff;font-size:18px}
.h4{margin:.2rem 0 .5rem;color:#fff}
.muted{color:rgba(255,255,255,.62);font-size:12px}
.ta{min-height:110px;background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.12);border-radius:10px;color:#fff;padding:.55rem .65rem}
.row{display:flex;gap:.5rem;margin:.5rem 0;flex-wrap:wrap}
.lst{padding-left:1rem}
.sandbox-gate-panel,.audit-panel{border:1px solid rgba(255,255,255,.12);border-radius:10px;padding:.6rem .7rem;background:rgba(255,255,255,.02)}
.btn{border:1px solid rgba(255,255,255,.16);background:rgba(255,255,255,.04);color:#fff}
.btn-primary{background:#1f4f8e;border-color:#3563a5;color:#fff}
</style>
