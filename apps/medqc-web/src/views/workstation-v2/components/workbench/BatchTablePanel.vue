<template>
  <section class="rounded-2xl border border-slate-200/70 bg-white shadow-[0_10px_28px_rgba(15,23,42,0.05)] overflow-hidden">
    <div class="border-b border-slate-100 bg-slate-50/80 px-4 py-3">
      <div class="flex flex-wrap items-center justify-between gap-2">
        <div class="text-[14px] font-semibold text-slate-800">
          批量工作台
        </div>
        <a-space size="small">
          <a-button
            size="small"
            @click="emit('clear-filters')"
          >
            清空筛选
          </a-button>
        </a-space>
      </div>
      <div class="mt-1 text-[12px] text-slate-500">
        {{ summaryText }}
      </div>
    </div>

    <div class="border-b border-slate-100 px-4 py-2.5 bg-white">
      <div class="flex flex-wrap items-center gap-2">
        <span class="text-[12px] text-slate-600">已选 {{ selectedRowKeys.length }} 条</span>
        <a-button
          size="small"
          type="primary"
          :disabled="selectedRowKeys.length === 0 || readonly"
          @click="emit('batch-extract', selectedRowKeys)"
        >
          批量进入抽取
        </a-button>
        <a-button
          size="small"
          :disabled="selectedRowKeys.length === 0 || readonly"
          @click="emit('batch-defer', selectedRowKeys)"
        >
          批量标记稍后
        </a-button>
        <a-button
          size="small"
          :disabled="selectedRowKeys.length === 0 || readonly"
          @click="emit('batch-assign', selectedRowKeys)"
        >
          批量分派
        </a-button>
      </div>
    </div>

    <a-table
      :columns="columns"
      :data-source="rows"
      :loading="loading"
      row-key="id"
      :pagination="false"
      :row-selection="rowSelection"
      :scroll="{ x: 980 }"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'patient'">
          <div class="font-semibold text-slate-900">
            {{ record.patientName }}
          </div>
          <div class="mt-1 flex items-center gap-2 text-[12px] text-slate-500">
            <span class="font-mono">{{ record.visitId }}</span>
            <a-tag
              v-if="record.isDemo"
              color="blue"
            >
              Demo
            </a-tag>
          </div>
        </template>
        <template v-else-if="column.key === 'risk'">
          <span class="text-amber-700">{{ record.riskReason }}</span>
        </template>
        <template v-else-if="column.key === 'action'">
          <a-button
            type="link"
            size="small"
            @click="emit('open-record', record.id)"
          >
            查看详情 →
          </a-button>
        </template>
      </template>
    </a-table>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'

export interface WorkbenchRow {
  id: string
  patientName: string
  visitId: string
  department: string
  stageStatus: string
  riskReason: string
  updatedAt: string
  isDemo: boolean
}

const props = defineProps<{
  rows: WorkbenchRow[]
  selectedRowKeys: string[]
  summaryText: string
  loading?: boolean
  readonly?: boolean
}>()

const emit = defineEmits<{
  'update:selectedRowKeys': [keys: string[]]
  'open-record': [id: string]
  'batch-extract': [keys: string[]]
  'batch-defer': [keys: string[]]
  'batch-assign': [keys: string[]]
  'clear-filters': []
}>()

const rowSelection = computed(() => ({
  selectedRowKeys: props.selectedRowKeys,
  onChange: (keys: (string | number)[]) => emit('update:selectedRowKeys', keys.map((k) => String(k))),
}))

const columns = [
  { title: '患者信息', key: 'patient', dataIndex: 'patient', width: 260 },
  { title: '科室', key: 'department', dataIndex: 'department', width: 180 },
  { title: '阶段状态', key: 'stageStatus', dataIndex: 'stageStatus', width: 140 },
  { title: '风险原因', key: 'risk', dataIndex: 'riskReason', width: 260 },
  { title: '更新时间', key: 'updatedAt', dataIndex: 'updatedAt', width: 140 },
  { title: '操作', key: 'action', dataIndex: 'action', width: 120 },
]
</script>
