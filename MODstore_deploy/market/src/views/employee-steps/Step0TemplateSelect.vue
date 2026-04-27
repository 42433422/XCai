<template>
  <section class="tpl">
    <h3 class="ttl">Step0 选择模板</h3>
    <div class="grid">
      <button
        v-for="item in templates"
        :key="item.id"
        type="button"
        class="card"
        :class="{ active: selectedId === item.id }"
        @click="selectedId = item.id"
      >
        <div class="row">
          <div class="icon">{{ item.icon }}</div>
          <div class="meta">
            <div class="name">{{ item.name }}</div>
            <div class="desc">{{ item.desc }}</div>
          </div>
        </div>
      </button>
    </div>
    <div class="ops">
      <button type="button" class="btn btn-sm btn-primary" @click="$emit('change', selectedId)">确认选择</button>
    </div>
  </section>
</template>
<script setup>
import { ref, watch } from 'vue'
const props = defineProps({ templateId: { type: String, required: true } })
defineEmits(['change'])
const selectedId = ref(props.templateId || 'workflow')
watch(() => props.templateId, (v) => { selectedId.value = v || 'workflow' })
const templates = [
  { id: 'workflow', icon: '🔧', name: '简单工作流员工', desc: '自动化任务编排' },
  { id: 'dialog', icon: '💬', name: '对话型 Agent', desc: '客服和问答助手' },
  { id: 'phone', icon: '📞', name: '电话客服员工', desc: '语音交互 + 知识库' },
  { id: 'data', icon: '📊', name: '数据处理员工', desc: '清洗与报表生成' },
  { id: 'full', icon: '🚀', name: '全能型员工', desc: '全模块组合' },
  { id: 'blank', icon: '📝', name: '空白模板', desc: '从零开始' },
]
</script>
<style scoped>
.ttl{margin:.15rem 0 .45rem;color:rgba(255,255,255,.84);font-size:14px;font-weight:600}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:.45rem}
.card{
  border:1px solid rgba(255,255,255,.1);
  background:rgba(255,255,255,.015);
  border-radius:10px;
  padding:.48rem .55rem;
  text-align:left;
  color:#fff;
}
.card:hover{border-color:rgba(255,255,255,.2);background:rgba(255,255,255,.03)}
.card.active{
  border-color:rgba(255,255,255,.32);
  background:rgba(255,255,255,.05);
  box-shadow:inset 0 0 0 1px rgba(255,255,255,.08);
}
.row{display:flex;align-items:center;gap:.5rem}
.meta{min-width:0}
.icon{
  width:26px;
  height:26px;
  border-radius:7px;
  display:flex;
  align-items:center;
  justify-content:center;
  font-size:14px;
  background:rgba(255,255,255,.08);
  flex:0 0 26px;
}
.name{font-size:13px;font-weight:600;line-height:1.2;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.desc{font-size:11px;color:rgba(255,255,255,.55);margin-top:.15rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.ops{margin-top:.6rem}
.ops .btn.btn-sm.btn-primary{
  color:#000000;
  font-family:Helvetica, Arial, sans-serif;
  background-color:#f2f2f2;
}
</style>
