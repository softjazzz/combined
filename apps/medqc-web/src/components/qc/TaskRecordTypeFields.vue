<template>
  <section class="task-type-fields" :inert="disabled">
    <a-checkbox
      :checked="!!modelValue"
      :disabled="required && !!modelValue"
      @update:checked="toggle"
      >配置源病历类型标志</a-checkbox
    >
    <p v-if="required && !modelValue" role="alert">按类型抽样或分配必须明确填写类型字典</p>
    <template v-if="modelValue">
      <div v-for="(institute, index) in modelValue.institutes" :key="index" class="type-institute">
        <label>机构ID</label
        ><a-input
          :value="institute.institute_id"
          @update:value="(value) => changeInstitute(index, value)"
        />
        <template v-for="flag in flags" :key="flag.key">
          <label>{{ flag.label }}阳性码</label
          ><a-select
            mode="tags"
            :value="institute[flag.key].positive_codes"
            @update:value="(values) => changeCodes(index, flag.key, 'positive_codes', values)"
          />
          <label>{{ flag.label }}阴性码</label
          ><a-select
            mode="tags"
            :value="institute[flag.key].negative_codes"
            @update:value="(values) => changeCodes(index, flag.key, 'negative_codes', values)"
          />
        </template>
        <a-button :disabled="modelValue.institutes.length === 1" @click="removeInstitute(index)"
          ><Trash2 :size="14" />移除机构</a-button
        >
      </div>
      <a-button @click="addInstitute"><Plus :size="14" />添加机构字典</a-button>
      <label>双阳性病历策略</label>
      <a-radio-group :value="modelValue.overlap_policy" @update:value="changePolicy">
        <a-radio value="separate">独立双阳性桶</a-radio
        ><a-radio value="priority">显式优先级</a-radio>
      </a-radio-group>
      <a-select
        v-if="modelValue.overlap_policy === 'priority'"
        :value="modelValue.priority?.[0]"
        :options="[
          { value: 'critical', label: '危重优先于疑难' },
          { value: 'difficult', label: '疑难优先于危重' },
        ]"
        @update:value="changePriority"
      />
      <p class="type-source">
        来源：cdm.mr_customize
        危重/疑难标志；NULL、未知码与缺少机构字典保持未知。普通桶仅包含双阴性病例。
      </p>
    </template>
  </section>
</template>
<script setup lang="ts">
import { Plus, Trash2 } from 'lucide-vue-next'
import type { TaskRecordTypeConfig } from '@/api/tasks'
const props = defineProps<{
  modelValue?: TaskRecordTypeConfig
  required?: boolean
  disabled?: boolean
}>()
const emit = defineEmits<{ 'update:modelValue': [TaskRecordTypeConfig | undefined] }>()
const flags = [
  { key: 'critical' as const, label: '危重' },
  { key: 'difficult' as const, label: '疑难' },
]
const blank = () => ({
  institute_id: '',
  critical: { positive_codes: [] as string[], negative_codes: [] as string[] },
  difficult: { positive_codes: [] as string[], negative_codes: [] as string[] },
})
function copy() {
  return JSON.parse(
    JSON.stringify(props.modelValue ?? { institutes: [blank()] }),
  ) as TaskRecordTypeConfig
}
function toggle(enabled: boolean) {
  emit('update:modelValue', enabled ? copy() : undefined)
}
function changeInstitute(index: number, value: string) {
  const next = copy()
  next.institutes[index].institute_id = value
  emit('update:modelValue', next)
}
function changeCodes(
  index: number,
  flag: 'critical' | 'difficult',
  key: 'positive_codes' | 'negative_codes',
  values: string[],
) {
  const next = copy()
  next.institutes[index][flag][key] = values
  emit('update:modelValue', next)
}
function changePolicy(value: 'separate' | 'priority') {
  const next = copy()
  next.overlap_policy = value
  delete next.priority
  emit('update:modelValue', next)
}
function changePriority(value: 'critical' | 'difficult') {
  const next = copy()
  next.priority = value === 'critical' ? ['critical', 'difficult'] : ['difficult', 'critical']
  emit('update:modelValue', next)
}
function addInstitute() {
  const next = copy()
  next.institutes.push(blank())
  emit('update:modelValue', next)
}
function removeInstitute(index: number) {
  const next = copy()
  next.institutes.splice(index, 1)
  emit('update:modelValue', next)
}
</script>
<style scoped>
.task-type-fields {
  display: grid;
  gap: 10px;
  margin: 12px 0;
}
.type-institute {
  display: grid;
  grid-template-columns: 110px minmax(0, 1fr);
  gap: 8px;
  padding: 12px 0;
  border-bottom: 1px solid #e8e8ed;
}
.type-source {
  color: #666;
  margin: 0;
  font-size: 13px;
}
@media (max-width: 600px) {
  .type-institute {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
