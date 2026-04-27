<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { api } from '../../../../api'
import { getNodeMeta } from '../composables/useNodeRegistry'
import type { WorkflowFlowNode } from '../composables/useWorkflowGraph'

const props = defineProps<{
  selected: WorkflowFlowNode | null
}>()

const emit = defineEmits<{
  (e: 'patch', payload: { id: string; label?: string; config?: Record<string, unknown> }): void
  (e: 'delete', id: string): void
}>()

const employees = ref<Array<{ id: string; name?: string }>>([])
const employeesLoaded = ref(false)

const meta = computed(() => (props.selected ? getNodeMeta(props.selected.data!.kind) : null))

const labelDraft = ref('')
const configDraft = ref<Record<string, unknown>>({})

watch(
  () => props.selected?.id,
  () => {
    if (props.selected) {
      labelDraft.value = props.selected.data!.label || ''
      configDraft.value = { ...(props.selected.data!.config || {}) }
    } else {
      labelDraft.value = ''
      configDraft.value = {}
    }
  },
  { immediate: true },
)

function commitLabel() {
  if (!props.selected) return
  emit('patch', { id: props.selected.id, label: labelDraft.value })
}

function setField(key: string, value: unknown) {
  configDraft.value = { ...configDraft.value, [key]: value }
  if (!props.selected) return
  emit('patch', { id: props.selected.id, config: configDraft.value })
}

async function ensureEmployees() {
  if (employeesLoaded.value) return
  try {
    const list: any = await api.listEmployees()
    employees.value = Array.isArray(list) ? list : list?.employees || []
  } catch {
    employees.value = []
  } finally {
    employeesLoaded.value = true
  }
}

onMounted(ensureEmployees)

function jsonToString(v: unknown): string {
  if (typeof v === 'string') return v
  try {
    return JSON.stringify(v ?? {}, null, 2)
  } catch {
    return ''
  }
}

function tryParseJson(raw: string): { ok: true; value: unknown } | { ok: false; error: string } {
  if (!raw.trim()) return { ok: true, value: {} }
  try {
    return { ok: true, value: JSON.parse(raw) }
  } catch (e) {
    return { ok: false, error: (e as Error).message }
  }
}

function onJsonInput(key: string, raw: string) {
  const r = tryParseJson(raw)
  if (r.ok) setField(key, r.value)
}

function onSwitchInput(key: string, ev: Event) {
  const target = ev.target as HTMLInputElement | null
  setField(key, !!target?.checked)
}

function onNumberInput(key: string, ev: Event) {
  const target = ev.target as HTMLInputElement | null
  const val = Number(target?.value || 0)
  setField(key, Number.isFinite(val) ? val : 0)
}
</script>

<template>
  <aside class="wf2-properties">
    <header class="wf2-properties__head">
      <h3 class="wf2-properties__title">属性</h3>
      <button v-if="selected" class="wf2-properties__del" type="button" @click="emit('delete', selected.id)">
        删除节点
      </button>
    </header>

    <div v-if="!selected" class="wf2-properties__empty">
      <p>选中一个节点以编辑属性</p>
      <p class="wf2-properties__empty-sub">画布空白处单击可取消选中</p>
    </div>

    <div v-else class="wf2-properties__body">
      <div class="wf2-properties__meta">
        <span class="wf2-properties__chip" :style="{ '--accent': meta!.accent }">
          {{ meta!.label }}
        </span>
        <span class="wf2-properties__id">#{{ selected.data!.backendId || '新建' }}</span>
      </div>
      <p class="wf2-properties__desc">{{ meta!.description }}</p>

      <label class="wf2-field">
        <span class="wf2-field__label">名称</span>
        <input
          v-model="labelDraft"
          class="wf2-input"
          type="text"
          @blur="commitLabel"
          @keydown.enter.prevent="commitLabel"
        />
      </label>

      <template v-for="f in meta!.fields" :key="f.key">
        <label class="wf2-field">
          <span class="wf2-field__label">
            {{ f.label }}<span v-if="f.required" class="wf2-field__required">*</span>
          </span>

          <textarea
            v-if="f.type === 'textarea'"
            class="wf2-input wf2-input--ta"
            :value="String(configDraft[f.key] ?? '')"
            :placeholder="f.placeholder"
            rows="3"
            @input="setField(f.key, ($event.target as HTMLTextAreaElement).value)"
          />

          <input
            v-else-if="f.type === 'number'"
            class="wf2-input"
            type="number"
            :value="Number(configDraft[f.key] ?? 0)"
            :placeholder="f.placeholder"
            @input="onNumberInput(f.key, $event)"
          />

          <label v-else-if="f.type === 'switch'" class="wf2-switch">
            <input
              type="checkbox"
              :checked="Boolean(configDraft[f.key])"
              @change="onSwitchInput(f.key, $event)"
            />
            <span>{{ Boolean(configDraft[f.key]) ? '启用' : '关闭' }}</span>
          </label>

          <select
            v-else-if="f.type === 'select'"
            class="wf2-input"
            :value="String(configDraft[f.key] ?? '')"
            @change="setField(f.key, ($event.target as HTMLSelectElement).value)"
          >
            <option v-for="o in f.options || []" :key="String(o.value)" :value="String(o.value)">
              {{ o.label }}
            </option>
          </select>

          <select
            v-else-if="f.type === 'employee-picker'"
            class="wf2-input"
            :value="String(configDraft[f.key] ?? '')"
            @change="setField(f.key, ($event.target as HTMLSelectElement).value)"
          >
            <option value="">— 选择员工 —</option>
            <option v-for="e in employees" :key="String(e.id)" :value="String(e.id)">
              {{ e.name || e.id }}
            </option>
          </select>

          <textarea
            v-else-if="f.type === 'json'"
            class="wf2-input wf2-input--ta wf2-input--mono"
            :value="jsonToString(configDraft[f.key])"
            :placeholder="f.placeholder"
            rows="5"
            @input="onJsonInput(f.key, ($event.target as HTMLTextAreaElement).value)"
          />

          <input
            v-else
            class="wf2-input"
            type="text"
            :value="String(configDraft[f.key] ?? '')"
            :placeholder="f.placeholder"
            @input="setField(f.key, ($event.target as HTMLInputElement).value)"
          />

          <small v-if="f.helper" class="wf2-field__helper">{{ f.helper }}</small>
        </label>
      </template>
    </div>
  </aside>
</template>

<style scoped>
.wf2-properties {
  width: 320px;
  flex-shrink: 0;
  border-left: 1px solid #e2e8f0;
  background: #ffffff;
  height: 100%;
  overflow-y: auto;
}

.wf2-properties__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px;
  border-bottom: 1px solid #e2e8f0;
}

.wf2-properties__title {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
}

.wf2-properties__del {
  font-size: 12px;
  background: transparent;
  border: 1px solid #fecaca;
  color: #b91c1c;
  padding: 4px 10px;
  border-radius: 6px;
  cursor: pointer;
}

.wf2-properties__del:hover {
  background: #fef2f2;
}

.wf2-properties__empty {
  padding: 32px 16px;
  text-align: center;
  color: #64748b;
}

.wf2-properties__empty-sub {
  font-size: 12px;
  color: #94a3b8;
}

.wf2-properties__body {
  padding: 14px 16px 24px;
}

.wf2-properties__meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 4px;
}

.wf2-properties__chip {
  --accent: #6366f1;
  display: inline-block;
  font-size: 11px;
  font-weight: 600;
  padding: 3px 8px;
  border-radius: 999px;
  background: color-mix(in srgb, var(--accent) 15%, transparent);
  color: var(--accent);
}

.wf2-properties__id {
  font-size: 11px;
  color: #94a3b8;
}

.wf2-properties__desc {
  font-size: 12px;
  color: #64748b;
  margin: 4px 0 14px;
}

.wf2-field {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-bottom: 14px;
}

.wf2-field__label {
  font-size: 12px;
  color: #334155;
  font-weight: 500;
}

.wf2-field__required {
  color: #ef4444;
  margin-left: 2px;
}

.wf2-field__helper {
  font-size: 11px;
  color: #94a3b8;
  line-height: 1.4;
}

.wf2-input {
  width: 100%;
  border: 1px solid #cbd5e1;
  border-radius: 6px;
  padding: 7px 9px;
  font-size: 13px;
  font-family: inherit;
  color: #0f172a;
  background: #fff;
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}

.wf2-input:focus {
  outline: none;
  border-color: #6366f1;
  box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.18);
}

.wf2-input--ta {
  resize: vertical;
  line-height: 1.5;
}

.wf2-input--mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 12px;
}

.wf2-switch {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: #334155;
}
</style>
