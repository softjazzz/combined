<template>
  <section class="condition-editor" aria-labelledby="visual-condition-title">
    <div class="editor-heading">
      <div>
        <h2 id="visual-condition-title">缺陷触发条件</h2>
        <p>条件结果为真时触发缺陷；事实无法确认时返回数据不足。</p>
      </div>
      <label class="compact-field">
        <span>条件组关系</span>
        <select v-model="draft.root_operator" :disabled="disabled">
          <option v-for="item in groupOperatorOptions" :key="item.value" :value="item.value">{{ item.label }}</option>
        </select>
      </label>
    </div>

    <div v-if="error" class="condition-error" role="alert">{{ error }}</div>

    <div class="group-list">
      <article v-for="(group, groupIndex) in draft.groups" :key="group.id" class="condition-group">
        <header>
          <strong>条件组 {{ groupIndex + 1 }}</strong>
          <label class="compact-field">
            <span>组内关系</span>
            <select v-model="group.operator" :disabled="disabled">
              <option v-for="item in groupOperatorOptions" :key="item.value" :value="item.value">{{ item.label }}</option>
            </select>
          </label>
          <button type="button" class="text-button danger" :disabled="disabled || draft.groups.length <= 1" @click="removeGroup(groupIndex)">删除组</button>
        </header>

        <div class="condition-list">
          <div v-for="(condition, conditionIndex) in group.conditions" :key="condition.id" class="condition-row">
            <select :value="condition.kind" :disabled="disabled" aria-label="条件类型" @change="changeKind(groupIndex, conditionIndex, $event)">
              <option value="field">字段条件</option>
              <option value="document_presence">文书存在性</option>
              <option value="timeliness">时效条件</option>
            </select>

            <template v-if="condition.kind === 'field'">
              <select :value="condition.fact_key" :disabled="disabled" aria-label="字段" @change="changeField(condition, $event)">
                <option value="" disabled>选择字段</option>
                <option v-for="field in options.fields" :key="field.key" :value="field.key">{{ field.label }}</option>
              </select>
              <select v-model="condition.operator" :disabled="disabled || !condition.fact_key" aria-label="操作符" @change="clearUnusedFieldValue(condition)">
                <option value="" disabled>选择操作符</option>
                <option v-for="operator in fieldOperators(condition.fact_key)" :key="operator.value" :value="operator.value">{{ operator.label }}</option>
              </select>
              <template v-if="fieldOperator(condition)?.value_required">
                <select v-if="isMultipleValueOperator(condition) && fieldOperator(condition)?.value_options" v-model="condition.value" multiple :disabled="disabled" aria-label="比较值">
                  <option v-for="item in fieldOperator(condition)?.value_options" :key="item.value" :value="item.value">{{ item.label }}</option>
                </select>
                <div v-else-if="isMultipleValueOperator(condition)" class="array-value-editor">
                  <div v-for="(_item, valueIndex) in arrayValues(condition)" :key="valueIndex" class="array-value-row">
                    <input :value="arrayValues(condition)[valueIndex]" :disabled="disabled" aria-label="比较值项" placeholder="输入一个精确值" @input="changeArrayValue(condition, valueIndex, $event)" />
                    <button type="button" title="删除比较值" :disabled="disabled || arrayValues(condition).length <= 1" @click="removeArrayValue(condition, valueIndex)">×</button>
                  </div>
                  <button type="button" class="add-value-button" :disabled="disabled || arrayValues(condition).length >= 50" @click="addArrayValue(condition)">添加值</button>
                </div>
                <select v-else-if="fieldOperator(condition)?.value_options" v-model="condition.value" :disabled="disabled" aria-label="比较值">
                  <option value="" disabled>选择值</option>
                  <option v-for="item in fieldOperator(condition)?.value_options" :key="item.value" :value="item.value">{{ item.label }}</option>
                </select>
                <input v-else :value="condition.value" :type="fieldInputType(condition.fact_key)" :disabled="disabled" aria-label="比较值" placeholder="输入比较值" @input="changeFieldValue(condition, $event)" />
              </template>
              <span v-else class="value-placeholder">无需比较值</span>
            </template>

            <template v-else-if="condition.kind === 'document_presence'">
              <select v-model="condition.document_type" :disabled="disabled" aria-label="文书类型">
                <option value="" disabled>选择文书</option>
                <option v-for="item in options.document_types" :key="item.value" :value="item.value">{{ item.label }}</option>
              </select>
              <select v-model="condition.operator" :disabled="disabled" aria-label="存在性">
                <option value="exists">存在</option>
                <option value="not_exists">不存在</option>
              </select>
              <span class="value-placeholder">由服务端核实文书加载状态</span>
            </template>

            <template v-else>
              <select :value="condition.start_fact" :disabled="disabled" aria-label="起点时间" @change="changeStartFact(condition, $event)">
                <option value="" disabled>选择起点</option>
                <option v-for="item in options.timeliness.start_fields" :key="item.value" :value="item.value">{{ item.label }}</option>
              </select>
              <select v-model="condition.end_fact" :disabled="disabled || !condition.start_fact" aria-label="终点时间">
                <option value="" disabled>选择终点</option>
                <option v-for="item in allowedEndFields(condition.start_fact)" :key="item.value" :value="item.value">{{ item.label }}</option>
              </select>
              <select v-model="condition.operator" :disabled="disabled" aria-label="时效比较符">
                <option v-for="item in options.timeliness.operators" :key="item.value" :value="item.value">{{ item.label }}</option>
              </select>
              <div class="threshold-control">
                <input v-model.number="condition.threshold.value" type="number" min="1" step="1" :disabled="disabled" aria-label="时效阈值" />
                <select v-model="condition.threshold.unit" :disabled="disabled" aria-label="时效单位">
                  <option v-for="item in options.timeliness.units" :key="item.value" :value="item.value">{{ item.label }}</option>
                </select>
              </div>
            </template>

            <button type="button" class="icon-button" title="删除条件" :disabled="disabled" @click="removeCondition(groupIndex, conditionIndex)">×</button>
          </div>
        </div>

        <div class="group-actions">
          <button type="button" :disabled="disabled || group.conditions.length >= options.limits.max_conditions_per_group" @click="addCondition(groupIndex, 'field')">添加字段条件</button>
          <button type="button" :disabled="disabled || group.conditions.length >= options.limits.max_conditions_per_group" @click="addCondition(groupIndex, 'document_presence')">添加文书条件</button>
          <button type="button" :disabled="disabled || group.conditions.length >= options.limits.max_conditions_per_group" @click="addCondition(groupIndex, 'timeliness')">添加时效条件</button>
        </div>
      </article>
    </div>

    <footer class="editor-actions">
      <button type="button" class="secondary-button" :disabled="disabled || draft.groups.length >= options.limits.max_groups" @click="addGroup">添加条件组</button>
      <button type="button" class="primary-button" :disabled="disabled" data-testid="save-visual-condition" @click="submit">保存条件配置</button>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import type {
  VisualCondition, VisualConditionFieldOperator, VisualConditionOptions,
  VisualConditionTree,
} from '@/types/custom-rule-workspace'

const props = defineProps<{
  modelValue: VisualConditionTree
  options: VisualConditionOptions
  disabled?: boolean
}>()
const emit = defineEmits<{
  save: [value: VisualConditionTree]
  dirty: [value: boolean]
}>()

let sequence = 0
const createId = (prefix: string) => `${prefix}-${Date.now()}-${++sequence}`
const cloneTree = (value: VisualConditionTree): VisualConditionTree => JSON.parse(JSON.stringify(value)) as VisualConditionTree
const draft = reactive<VisualConditionTree>(cloneTree(props.modelValue))
const error = ref('')

watch(() => props.modelValue, (value) => {
  Object.assign(draft, cloneTree(value))
  error.value = ''
}, { deep: true })
watch(draft, () => {
  emit('dirty', JSON.stringify(draft) !== JSON.stringify(props.modelValue))
}, { deep: true })

const groupOperatorOptions = computed(() => props.options.group_operators.map((value) => ({
  value, label: value === 'all' ? '全部满足' : '任一满足',
})))

function fieldOperators(factKey: string) {
  return props.options.fields.find((item) => item.key === factKey)?.operators ?? []
}
function fieldOperator(condition: Extract<VisualCondition, { kind: 'field' }>): VisualConditionFieldOperator | undefined {
  return fieldOperators(condition.fact_key).find((item) => item.value === condition.operator)
}
function fieldInputType(factKey: string) {
  return props.options.fields.find((item) => item.key === factKey)?.value_type === 'number' ? 'number' : 'text'
}
function changeFieldValue(condition: Extract<VisualCondition, { kind: 'field' }>, event: Event) {
  const raw = (event.target as HTMLInputElement).value
  const valueType = props.options.fields.find((item) => item.key === condition.fact_key)?.value_type
  condition.value = valueType === 'number' && raw !== '' ? Number(raw) : raw
}
function isMultipleValueOperator(condition: Extract<VisualCondition, { kind: 'field' }>) {
  return condition.operator === 'in' || condition.operator === 'not_in'
}
function arrayValues(condition: Extract<VisualCondition, { kind: 'field' }>) {
  return Array.isArray(condition.value) ? condition.value : []
}
function addArrayValue(condition: Extract<VisualCondition, { kind: 'field' }>) {
  condition.value = [...arrayValues(condition), '']
}
function changeArrayValue(condition: Extract<VisualCondition, { kind: 'field' }>, index: number, event: Event) {
  const values = [...arrayValues(condition)]
  values[index] = (event.target as HTMLInputElement).value
  condition.value = values
}
function removeArrayValue(condition: Extract<VisualCondition, { kind: 'field' }>, index: number) {
  condition.value = arrayValues(condition).filter((_item, valueIndex) => valueIndex !== index)
}
function allowedEndFields(startFact: string) {
  const allowed = new Set(props.options.timeliness.allowed_pairs
    .filter((item) => item.start_fact === startFact).map((item) => item.end_fact))
  return props.options.timeliness.end_fields.filter((item) => allowed.has(item.value))
}
function addGroup() {
  if (draft.groups.length >= props.options.limits.max_groups) return
  draft.groups.push({ id: createId('group'), operator: 'all', conditions: [] })
}
function removeGroup(index: number) { draft.groups.splice(index, 1) }
function newCondition(kind: VisualCondition['kind']): VisualCondition {
  if (kind === 'document_presence') return { id: createId('condition'), kind, document_type: '', operator: 'exists' }
  if (kind === 'timeliness') return {
    id: createId('condition'), kind, start_fact: '', end_fact: '', operator: props.options.timeliness.operators[0]?.value ?? 'lte',
    threshold: { value: 0, unit: props.options.timeliness.units[0]?.value ?? 'hours' },
  }
  return { id: createId('condition'), kind, fact_key: '', operator: '', value: '' }
}
function addCondition(groupIndex: number, kind: VisualCondition['kind']) {
  const group = draft.groups[groupIndex]
  if (!group || group.conditions.length >= props.options.limits.max_conditions_per_group) return
  group.conditions.push(newCondition(kind))
}
function removeCondition(groupIndex: number, conditionIndex: number) { draft.groups[groupIndex]?.conditions.splice(conditionIndex, 1) }
function changeKind(groupIndex: number, conditionIndex: number, event: Event) {
  const kind = (event.target as HTMLSelectElement).value as VisualCondition['kind']
  const group = draft.groups[groupIndex]
  if (group) group.conditions.splice(conditionIndex, 1, newCondition(kind))
}
function changeField(condition: Extract<VisualCondition, { kind: 'field' }>, event: Event) {
  condition.fact_key = (event.target as HTMLSelectElement).value
  condition.operator = ''
  condition.value = ''
}
function clearUnusedFieldValue(condition: Extract<VisualCondition, { kind: 'field' }>) {
  if (!fieldOperator(condition)?.value_required) delete condition.value
  else condition.value = isMultipleValueOperator(condition) ? [] : ''
}
function changeStartFact(condition: Extract<VisualCondition, { kind: 'timeliness' }>, event: Event) {
  condition.start_fact = (event.target as HTMLSelectElement).value
  if (!allowedEndFields(condition.start_fact).some((item) => item.value === condition.end_fact)) condition.end_fact = ''
}
function validate(): string {
  if (draft.groups.length === 0 || draft.groups.length > props.options.limits.max_groups) return '请至少配置一个条件组'
  for (const group of draft.groups) {
    if (group.conditions.length === 0) return '条件组不能为空'
    if (group.conditions.length > props.options.limits.max_conditions_per_group) return '条件数量超过服务端限制'
    for (const condition of group.conditions) {
      if (condition.kind === 'field') {
        const operator = fieldOperator(condition)
        if (!props.options.fields.some((item) => item.key === condition.fact_key) || !operator) return '请选择有效的字段和操作符'
        if (operator.value_required && (condition.value === undefined || condition.value === ''
          || (Array.isArray(condition.value) && condition.value.length === 0))) return '请填写字段比较值'
        if (isMultipleValueOperator(condition)) {
          const allowed = operator.value_options ? new Set(operator.value_options.map((item) => item.value)) : null
          if (!Array.isArray(condition.value) || condition.value.length === 0
            || condition.value.some((item) => !item.trim() || (allowed !== null && !allowed.has(item)))) return '请选择有效的字段比较值'
        } else if (Array.isArray(condition.value)) return '字段比较值格式无效'
      } else if (condition.kind === 'document_presence') {
        if (!props.options.document_types.some((item) => item.value === condition.document_type)) return '请选择有效的文书类型'
      } else {
        const pairAllowed = props.options.timeliness.allowed_pairs.some((item) => item.start_fact === condition.start_fact && item.end_fact === condition.end_fact)
        if (!pairAllowed || !Number.isInteger(condition.threshold.value) || condition.threshold.value < 1) return '请完整填写有效的时效条件'
      }
    }
  }
  return ''
}
function submit() {
  error.value = validate()
  if (!error.value) emit('save', cloneTree(draft))
}
</script>

<style scoped>
.condition-editor { padding:22px; border:1px solid rgba(0,0,0,.08); border-radius:8px; background:#fff; box-shadow:0 4px 18px rgba(38,58,86,.04); }
.editor-heading,.condition-group>header,.editor-actions,.group-actions { display:flex; align-items:center; justify-content:space-between; gap:12px; }
.editor-heading h2 { margin:0; font-size:17px; line-height:22px; font-weight:600; }.editor-heading p { margin:4px 0 0; color:rgba(29,29,31,.6); font-size:13px; }
.compact-field { display:flex; align-items:center; gap:8px; font-size:13px; white-space:nowrap; }.compact-field select { min-width:112px; }
.condition-error { margin:14px 0; padding:9px 11px; border-left:3px solid #ef4444; background:#fff5f5; color:#b42318; font-size:13px; }
.group-list { display:grid; gap:14px; margin-top:18px; }.condition-group { padding:16px; border:1px solid rgba(0,0,0,.09); border-radius:8px; background:#fafbfc; }.condition-group>header { justify-content:flex-start; }.condition-group>header strong { margin-right:auto; }
.condition-list { display:grid; gap:10px; margin:14px 0; }.condition-row { display:grid; grid-template-columns:130px repeat(3,minmax(120px,1fr)) 34px; gap:8px; align-items:center; min-width:0; }
select,input { width:100%; min-width:0; min-height:36px; padding:0 9px; border:1px solid rgba(0,0,0,.14); border-radius:8px; background:#fff; color:#1d1d1f; font:inherit; }select:focus,input:focus { border-color:#007aff; outline:0; box-shadow:0 0 0 3px rgba(0,122,255,.08); }
.threshold-control { display:grid; grid-template-columns:minmax(70px,1fr) minmax(76px,1fr); gap:6px; }.value-placeholder { color:rgba(29,29,31,.45); font-size:12px; }
.array-value-editor { display:grid; gap:6px; }.array-value-row { display:grid; grid-template-columns:minmax(0,1fr) 30px; gap:4px; }.array-value-row button,.add-value-button { min-height:30px; border:1px solid rgba(0,0,0,.1); background:#fff; }.add-value-button { color:#007aff; }
button { min-height:34px; border-radius:8px; font:inherit; cursor:pointer; }button:disabled { cursor:not-allowed; opacity:.55; }.group-actions { justify-content:flex-start; }.group-actions button,.secondary-button { padding:0 12px; border:1px solid rgba(0,0,0,.12); background:#fff; }.primary-button { padding:0 16px; border:1px solid #007aff; background:#007aff; color:#fff; }.text-button,.icon-button { border:0; background:transparent; }.text-button.danger,.icon-button { color:#b42318; }.editor-actions { margin-top:16px; }
@media (max-width:980px) { .condition-row { grid-template-columns:1fr 1fr; }.icon-button { justify-self:end; }.editor-heading { align-items:flex-start; flex-direction:column; } }
</style>
