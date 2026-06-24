<template>
  <aside class="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm space-y-4">
    <div>
      <div class="text-[12px] font-semibold text-slate-700">
        {{ ruleTypeTitle }}
      </div>
      <a-radio-group
        class="mt-2 flex flex-col gap-1"
        :value="ruleType"
        @update:value="emit('update:ruleType', $event)"
      >
        <a-radio
          v-for="item in resolvedRuleTypeOptions"
          :key="item.value"
          :value="item.value"
        >
          {{ item.label }}
        </a-radio>
      </a-radio-group>
    </div>

    <div>
      <div class="text-[12px] font-semibold text-slate-700">
        {{ statusTitle }}
      </div>
      <a-checkbox-group
        class="mt-2 flex flex-col gap-1"
        :value="statusSet"
        :options="resolvedStatusOptions"
        @change="emit('update:statusSet', $event as string[])"
      />
    </div>

    <div>
      <div class="text-[12px] font-semibold text-slate-700">
        {{ riskTitle }}
      </div>
      <a-checkbox-group
        class="mt-2 flex flex-col gap-1"
        :value="riskSet"
        :options="resolvedRiskOptions"
        @change="emit('update:riskSet', $event as string[])"
      />
    </div>

    <div v-if="showDocumentTypeFilter">
      <div class="text-[12px] font-semibold text-slate-700">
        {{ documentTypeTitle }}
      </div>
      <a-checkbox-group
        class="mt-2 flex flex-col gap-1"
        :value="documentTypeSet"
        :options="resolvedDocumentTypeOptions"
        @change="emit('update:documentTypeSet', $event as string[])"
      />
    </div>

    <div v-if="showOwnerFilter">
      <div class="text-[12px] font-semibold text-slate-700">
        {{ ownerTitle }}
      </div>
      <a-select
        class="mt-2 w-full"
        allow-clear
        :value="ownerId"
        :options="ownerOptions"
        @update:value="handleOwnerChange"
      />
    </div>

    <div class="pt-2 border-t border-slate-100">
      <a-space wrap>
        <a-button
          size="small"
          @click="emit('reset-filters')"
        >
          重置筛选
        </a-button>
        <a-button
          size="small"
          :disabled="readonly"
          @click="emit('save-view', { name: '我的筛选视图' })"
        >
          保存视图
        </a-button>
      </a-space>
    </div>
  </aside>
</template>

<script setup lang="ts">
import type { RuleTypeValue } from './types'
import { computed } from 'vue'

const props = withDefaults(
  defineProps<{
    ruleType: RuleTypeValue
    statusSet: string[]
    riskSet: string[]
    ownerId?: string
    ownerOptions: Array<{ label: string; value: string }>
    savedViews: Array<{ id: string; name: string }>
    readonly: boolean
    ruleTypeTitle?: string
    statusTitle?: string
    riskTitle?: string
    ownerTitle?: string
    showOwnerFilter?: boolean
    showDocumentTypeFilter?: boolean
    documentTypeTitle?: string
    documentTypeSet?: string[]
    documentTypeOptions?: Array<{ label: string; value: string }>
    ruleTypeOptions?: Array<{ label: string; value: string }>
    statusOptions?: Array<{ label: string; value: string }>
    riskOptions?: Array<{ label: string; value: string }>
  }>(),
  {
    ruleTypeTitle: '规则类型',
    statusTitle: '状态',
    riskTitle: '风险等级',
    ownerTitle: '最近修改人',
    showOwnerFilter: true,
    showDocumentTypeFilter: false,
    documentTypeTitle: '病历文书类型',
    documentTypeSet: () => [],
  },
)

const emit = defineEmits<{
  'update:ruleType': [value: RuleTypeValue]
  'update:statusSet': [value: string[]]
  'update:riskSet': [value: string[]]
  'update:ownerId': [value?: string]
  'update:documentTypeSet': [value: string[]]
  'reset-filters': []
  'save-view': [payload: { name: string }]
  'apply-view': [payload: { id: string }]
}>()

const defaultRuleTypeOptions = [
  { label: '全部', value: 'all' },
  { label: '主诊断', value: 'main_diagnosis' },
  { label: '其他诊断', value: 'other_diagnosis' },
  { label: '主手术', value: 'main_procedure' },
  { label: '其他手术', value: 'other_procedure' },
]
const defaultStatusOptions = [
  { label: '已发布', value: 'published' },
  { label: '草稿', value: 'draft' },
  { label: '停用', value: 'disabled' },
]
const defaultRiskOptions = [
  { label: '高', value: 'high' },
  { label: '中', value: 'medium' },
  { label: '低', value: 'low' },
]
const defaultDocumentTypeOptions = [
  { label: '入院记录', value: 'admission_record' },
  { label: '首次病程记录', value: 'first_course_record' },
  { label: '手术记录', value: 'operation_record' },
  { label: '会诊记录', value: 'consultation_record' },
  { label: '出院记录', value: 'discharge_record' },
  { label: '通用文书', value: 'general_record' },
]

const resolvedRuleTypeOptions = computed(() => props.ruleTypeOptions || defaultRuleTypeOptions)
const resolvedStatusOptions = computed(() => props.statusOptions || defaultStatusOptions)
const resolvedRiskOptions = computed(() => props.riskOptions || defaultRiskOptions)
const resolvedDocumentTypeOptions = computed(
  () => props.documentTypeOptions || defaultDocumentTypeOptions,
)

const handleOwnerChange = (value: string | number | undefined) => {
  if (value === undefined || value === null || value === '') {
    emit('update:ownerId', undefined)
    return
  }
  emit('update:ownerId', String(value))
}
</script>
