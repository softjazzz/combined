<template>
  <aside class="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm space-y-4">
    <div>
      <div class="text-[12px] font-semibold text-slate-700">
        规则类型
      </div>
      <a-radio-group
        class="mt-2 flex flex-col gap-1"
        :value="ruleType"
        @update:value="emit('update:ruleType', $event)"
      >
        <a-radio value="all">
          全部
        </a-radio>
        <a-radio value="main_diagnosis">
          主诊断
        </a-radio>
        <a-radio value="other_diagnosis">
          其他诊断
        </a-radio>
        <a-radio value="main_procedure">
          主手术
        </a-radio>
        <a-radio value="other_procedure">
          其他手术
        </a-radio>
      </a-radio-group>
    </div>

    <div>
      <div class="text-[12px] font-semibold text-slate-700">
        状态
      </div>
      <a-checkbox-group
        class="mt-2 flex flex-col gap-1"
        :value="statusSet"
        :options="statusOptions"
        @change="emit('update:statusSet', $event as string[])"
      />
    </div>

    <div>
      <div class="text-[12px] font-semibold text-slate-700">
        风险等级
      </div>
      <a-checkbox-group
        class="mt-2 flex flex-col gap-1"
        :value="riskSet"
        :options="riskOptions"
        @change="emit('update:riskSet', $event as string[])"
      />
    </div>

    <div>
      <div class="text-[12px] font-semibold text-slate-700">
        最近修改人
      </div>
      <a-select
        class="mt-2 w-full"
        allow-clear
        :value="ownerId"
        :options="ownerOptions"
        @update:value="emit('update:ownerId', $event)"
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

defineProps<{
  ruleType: RuleTypeValue
  statusSet: string[]
  riskSet: string[]
  ownerId?: string
  ownerOptions: Array<{ label: string; value: string }>
  savedViews: Array<{ id: string; name: string }>
  readonly: boolean
}>()

const emit = defineEmits<{
  'update:ruleType': [value: RuleTypeValue]
  'update:statusSet': [value: string[]]
  'update:riskSet': [value: string[]]
  'update:ownerId': [value?: string]
  'reset-filters': []
  'save-view': [payload: { name: string }]
  'apply-view': [payload: { id: string }]
}>()

const statusOptions = [
  { label: '已发布', value: 'published' },
  { label: '草稿', value: 'draft' },
  { label: '停用', value: 'disabled' },
]
const riskOptions = [
  { label: '高', value: 'high' },
  { label: '中', value: 'medium' },
  { label: '低', value: 'low' },
]
</script>
