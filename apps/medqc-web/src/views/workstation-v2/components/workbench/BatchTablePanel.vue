<template>
  <section
    class="batch-table-panel overflow-hidden rounded-[28px] border border-white/80 bg-[linear-gradient(180deg,rgba(255,255,255,0.98),rgba(246,249,252,0.96))] shadow-[0_24px_60px_rgba(15,23,42,0.08)]"
  >
    <div class="border-b border-slate-200/70 px-5 py-4">
      <div class="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
        <div class="min-w-0">
          <div class="text-[11px] font-bold uppercase tracking-[0.22em] text-slate-400">
            Batch Workspace
          </div>
          <div class="mt-2 flex flex-wrap items-end gap-3">
            <div class="text-[24px] font-black tracking-[-0.04em] text-slate-950">
              批量工作台
            </div>
            <span class="inline-flex items-center rounded-full border border-slate-200/80 bg-white/90 px-3 py-1 text-[12px] font-semibold text-slate-500">
              当前 {{ rows.length }} 条候选病历
            </span>
            <span class="inline-flex items-center rounded-full border border-slate-200/80 bg-slate-50/90 px-3 py-1 text-[12px] font-semibold text-slate-500">
              已选 {{ selectedRowKeys.length }} 条
            </span>
          </div>
          <div class="mt-2 text-[13px] leading-6 text-slate-500">
            {{ summaryText }}
          </div>
        </div>

        <div class="flex flex-wrap items-center gap-2">
          <a-button
            size="small"
            type="primary"
            class="!h-9 !rounded-full !border-0 !bg-slate-950 !px-4 !font-semibold !shadow-[0_12px_20px_rgba(15,23,42,0.18)]"
            :disabled="selectedRowKeys.length === 0 || readonly"
            @click="emit('batch-extract', selectedRowKeys)"
          >
            批量进入抽取
          </a-button>
          <a-button
            size="small"
            class="!h-9 !rounded-full !border-slate-200/90 !px-4 !font-semibold !text-slate-600"
            :disabled="selectedRowKeys.length === 0 || readonly"
            @click="emit('batch-defer', selectedRowKeys)"
          >
            批量标记稍后
          </a-button>
          <a-button
            size="small"
            class="!h-9 !rounded-full !border-slate-200/90 !px-4 !font-semibold !text-slate-600"
            :disabled="selectedRowKeys.length === 0 || readonly"
            @click="emit('batch-assign', selectedRowKeys)"
          >
            批量分派
          </a-button>
          <a-button
            size="small"
            class="!h-9 !rounded-full !border-slate-200/90 !px-4 !font-semibold !text-slate-500"
            @click="emit('clear-filters')"
          >
            清空筛选
          </a-button>
        </div>
      </div>
    </div>

    <a-table
      class="batch-table-panel__table"
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
          <div class="text-[15px] font-bold tracking-tight text-slate-900">
            {{ record.patientName }}
          </div>
          <div class="mt-2 flex items-center gap-2 text-[12px] text-slate-500">
            <span class="inline-flex items-center rounded-full bg-slate-100/90 px-2.5 py-1 font-mono text-[11px] text-slate-600">
              {{ record.visitId }}
            </span>
            <span
              v-if="record.isDemo"
              class="inline-flex items-center rounded-full border border-blue-200/80 bg-blue-50/90 px-2.5 py-1 text-[11px] font-semibold text-blue-700"
            >
              Demo
            </span>
          </div>
        </template>
        <template v-else-if="column.key === 'department'">
          <span class="text-[13px] font-medium text-slate-600">{{ record.department }}</span>
        </template>
        <template v-else-if="column.key === 'stageStatus'">
          <span class="inline-flex items-center rounded-full border border-sky-200/80 bg-sky-50/90 px-2.5 py-1 text-[11px] font-semibold text-sky-700">
            {{ record.stageStatus }}
          </span>
        </template>
        <template v-else-if="column.key === 'risk'">
          <span class="text-[13px] leading-6 text-slate-600">{{ record.riskReason }}</span>
        </template>
        <template v-else-if="column.key === 'updatedAt'">
          <span class="text-[12px] font-medium text-slate-500">{{ record.updatedAt }}</span>
        </template>
        <template v-else-if="column.key === 'action'">
          <a-button
            type="default"
            size="small"
            class="!h-8 !rounded-full !border-slate-200/90 !bg-white !px-3 !font-semibold !text-slate-700 !shadow-none"
            @click="emit('open-record', record.id)"
          >
            查看详情
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
  onChange: (keys: (string | number)[]) =>
    emit(
      'update:selectedRowKeys',
      keys.map((k) => String(k)),
    ),
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

<style scoped>
.batch-table-panel :deep(.ant-table) {
  background: transparent;
}

.batch-table-panel :deep(.ant-table-container) {
  border-top: 1px solid rgba(226, 232, 240, 0.9);
}

.batch-table-panel :deep(.ant-table-thead > tr > th) {
  background: rgba(248, 250, 252, 0.9);
  color: rgb(100 116 139);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  border-bottom: 1px solid rgba(226, 232, 240, 0.9);
}

.batch-table-panel :deep(.ant-table-tbody > tr > td) {
  background: transparent;
  border-bottom: 1px solid rgba(241, 245, 249, 0.9);
  padding-top: 18px;
  padding-bottom: 18px;
}

.batch-table-panel :deep(.ant-table-tbody > tr:hover > td) {
  background: rgba(248, 250, 252, 0.82);
}

.batch-table-panel :deep(.ant-table-tbody > tr.ant-table-row-selected > td) {
  background: rgba(239, 246, 255, 0.88);
}

.batch-table-panel :deep(.ant-checkbox-wrapper) {
  color: rgb(71 85 105);
}
</style>
