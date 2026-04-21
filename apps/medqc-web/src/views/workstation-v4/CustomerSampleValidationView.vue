<template>
  <main class="relative z-10 flex min-w-0 flex-1 flex-col overflow-hidden">
    <div class="custom-scrollbar flex-1 overflow-y-auto px-4 pb-5 pt-4 xl:px-5">
      <div class="mx-auto w-full max-w-[1440px] space-y-4">
        <section
          class="rounded-[24px] border border-slate-200/80 bg-[linear-gradient(135deg,rgba(239,246,255,0.95),rgba(255,255,255,0.98))] p-5 shadow-[0_14px_34px_rgba(148,163,184,0.16)]"
        >
          <div class="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
            <div class="min-w-0 space-y-3">
              <div class="flex flex-wrap items-center gap-2">
                <a-tag color="blue">
                  运行病历
                </a-tag>
                <a-tag color="processing">
                  客户样本验证
                </a-tag>
                <a-tag v-if="selectedPool?.latest_job_status">
                  {{ getBatchJobStatusText(selectedPool.latest_job_status) }}
                </a-tag>
              </div>
              <div>
                <h1 class="text-[28px] font-bold leading-tight text-slate-900">
                  客户样本验证
                </h1>
                <p class="mt-2 max-w-4xl text-[14px] leading-7 text-slate-600">
                  先核对人工问题样本与系统病历的匹配关系，再对首批内涵问题执行 LLM
                  验证。页面只展示可直接用于客户演示的样本状态、验证任务和命中结果。
                </p>
              </div>
              <div class="flex flex-wrap items-center gap-2 text-[13px] text-slate-500">
                <span class="rounded-full border border-slate-200 bg-white px-3 py-1">
                  当前样本池：{{ selectedPool?.name || '未选择' }}
                </span>
                <span
                  v-if="selectedPool?.source_sheet"
                  class="rounded-full border border-slate-200 bg-white px-3 py-1"
                >
                  来源：{{ selectedPool.source_sheet }}
                </span>
                <span
                  v-if="selectedPool?.latest_job_id"
                  class="rounded-full border border-slate-200 bg-white px-3 py-1"
                >
                  最近任务：{{ selectedPool.latest_job_id }}
                </span>
              </div>
            </div>

            <div class="flex shrink-0 flex-wrap gap-2 xl:justify-end">
              <a-button
                type="primary"
                ghost
                class="!rounded-full"
                @click="importModalOpen = true"
              >
                导入模板
              </a-button>
              <a-button
                class="!rounded-full"
                :loading="poolLoading"
                @click="loadPools()"
              >
                刷新样本池
              </a-button>
              <a-button
                class="!rounded-full"
                :disabled="!selectedPoolId"
                :loading="syncLoading"
                @click="handleSyncPoolRecords"
              >
                同步样本病历
              </a-button>
              <a-button
                type="primary"
                class="!rounded-full"
                :disabled="!selectedPoolId"
                :loading="matchLoading"
                @click="handleMatchPool"
              >
                执行病历匹配
              </a-button>
              <a-button
                type="primary"
                ghost
                class="!rounded-full"
                :disabled="!selectedPoolId || !selectedPool?.llm_intrinsic_items"
                :loading="runLoading"
                @click="handleRunPool"
              >
                {{ runButtonText }}
              </a-button>
              <a-button
                class="!rounded-full"
                :disabled="!selectedPool?.latest_job_id"
                @click="openLatestJob"
              >
                查看最近任务
              </a-button>
            </div>
          </div>
        </section>

        <section class="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <a-card
            v-for="item in summaryCards"
            :key="item.label"
            :bordered="false"
            class="rounded-[18px] border border-slate-200/80 shadow-[0_10px_24px_rgba(148,163,184,0.12)]"
          >
            <div class="text-[13px] font-medium text-slate-500">
              {{ item.label }}
            </div>
            <div class="mt-3 text-[34px] font-bold leading-none text-slate-900">
              {{ item.value }}
            </div>
            <div
              v-if="item.help"
              class="mt-3 text-[12px] leading-5 text-slate-400"
            >
              {{ item.help }}
            </div>
          </a-card>
        </section>

        <section
          v-if="syncJobDetail"
          class="rounded-[24px] border border-slate-200/80 bg-white shadow-[0_14px_34px_rgba(148,163,184,0.12)]"
        >
          <div class="border-b border-slate-200/80 px-5 py-4">
            <div class="flex flex-col gap-3 xl:flex-row xl:items-start xl:justify-between">
              <div class="min-w-0">
                <div class="text-[17px] font-semibold text-slate-900">
                  样本病历同步进度
                </div>
                <div class="mt-1 text-[13px] leading-6 text-slate-500">
                  按样本池定向从源库拉取真实病历到本地 PG，并刷新 running bundle。
                </div>
              </div>
              <a-tag :color="syncJobStatusColor(syncJobDetail.status)">
                {{ syncJobStatusText(syncJobDetail.status) }}
              </a-tag>
            </div>
          </div>
          <div class="grid gap-4 px-5 py-4 md:grid-cols-2 xl:grid-cols-5">
            <div class="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
              <div class="text-[12px] text-slate-400">
                样本病历
              </div>
              <div class="mt-2 text-[28px] font-semibold leading-none text-slate-900">
                {{ syncProgress.total_candidates ?? 0 }}
              </div>
            </div>
            <div class="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
              <div class="text-[12px] text-slate-400">
                可同步病历
              </div>
              <div class="mt-2 text-[28px] font-semibold leading-none text-slate-900">
                {{ syncProgress.eligible_visits ?? 0 }}
              </div>
            </div>
            <div class="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
              <div class="text-[12px] text-slate-400">
                已完成表数
              </div>
              <div class="mt-2 text-[28px] font-semibold leading-none text-slate-900">
                {{ syncProgress.processed_tables ?? 0 }}/{{ syncProgress.total_tables ?? 0 }}
              </div>
            </div>
            <div class="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
              <div class="text-[12px] text-slate-400">
                已拉取行数
              </div>
              <div class="mt-2 text-[28px] font-semibold leading-none text-slate-900">
                {{ syncProgress.total_rows_pulled ?? 0 }}
              </div>
            </div>
            <div class="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
              <div class="text-[12px] text-slate-400">
                已写入行数
              </div>
              <div class="mt-2 text-[28px] font-semibold leading-none text-slate-900">
                {{ syncProgress.total_rows_upserted ?? 0 }}
              </div>
            </div>
          </div>
          <div class="space-y-3 px-5 pb-5">
            <div
              class="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-[13px] leading-6 text-slate-600"
            >
              <div class="font-medium text-slate-700">
                {{ syncProgress.step_label || '等待同步开始' }}
              </div>
              <div class="mt-1">
                当前表：{{ syncProgress.current_table || '—' }}；剩余表数：{{
                  syncProgress.remaining_tables ?? 0
                }}
              </div>
              <div
                v-if="syncJobDetail.error_message"
                class="mt-2 text-rose-600"
              >
                {{ syncJobDetail.error_message }}
              </div>
            </div>
          </div>
        </section>

        <section
          class="rounded-[24px] border border-slate-200/80 bg-white shadow-[0_14px_34px_rgba(148,163,184,0.12)]"
        >
          <div class="border-b border-slate-200/80 px-5 py-4">
            <div class="flex flex-col gap-3 xl:flex-row xl:items-start xl:justify-between">
              <div class="min-w-0">
                <div class="text-[17px] font-semibold text-slate-900">
                  病历池
                </div>
                <div class="mt-1 text-[13px] leading-6 text-slate-500">
                  列表按真实病历聚合展示，人工问题样本作为病历详情里的关联问题保留。客户操作对象是病历，不是
                  Excel 样本行。
                </div>
              </div>
              <div class="grid gap-2 text-[13px] text-slate-500 sm:grid-cols-2 xl:min-w-[420px]">
                <div class="rounded-2xl border border-slate-200 bg-slate-50 px-3 py-2">
                  <div class="text-[12px] text-slate-400">
                    当前样本池
                  </div>
                  <div class="mt-1 font-medium text-slate-700">
                    {{ selectedPool?.name || '未选择' }}
                  </div>
                </div>
                <div class="rounded-2xl border border-slate-200 bg-slate-50 px-3 py-2">
                  <div class="text-[12px] text-slate-400">
                    当前任务
                  </div>
                  <div class="mt-1 font-medium text-slate-700">
                    {{ selectedPool?.latest_job_id ? '已创建' : '暂无任务' }}
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div class="space-y-4 px-5 py-4">
            <div class="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
              <div class="flex flex-1 flex-col gap-3 xl:flex-row xl:items-center">
                <a-select
                  v-model:value="selectedPoolId"
                  class="w-full xl:max-w-[280px] customer-sample-toolbar-select"
                  size="middle"
                  :loading="poolLoading"
                  :options="poolOptions"
                  placeholder="请选择样本池"
                  @change="handlePoolChange"
                />
                <a-input
                  v-model:value="filters.query"
                  class="w-full xl:min-w-[320px] xl:flex-1 customer-sample-toolbar-input"
                  size="middle"
                  placeholder="搜索患者/住院号/人工问题"
                  @press-enter="loadRecords()"
                />
              </div>

              <div class="flex flex-wrap gap-2 xl:justify-end">
                <a-select
                  v-model:value="filters.coverageType"
                  class="min-w-[140px] customer-sample-toolbar-select"
                  size="middle"
                  allow-clear
                  placeholder="覆盖类型"
                  :options="coverageOptions"
                />
                <a-select
                  v-model:value="filters.matchStatus"
                  class="min-w-[140px] customer-sample-toolbar-select"
                  size="middle"
                  allow-clear
                  placeholder="匹配状态"
                  :options="matchStatusOptions"
                />
                <div
                  class="flex items-center rounded-full border border-slate-200 bg-slate-50 px-3 text-[13px] text-slate-600"
                >
                  <span class="mr-2">仅首批</span>
                  <a-switch v-model:checked="filters.includeInBatch" />
                </div>
                <div
                  class="flex items-center gap-2 rounded-full border border-slate-200 bg-slate-50 px-3 text-[13px] text-slate-600"
                >
                  <span>并发病历数</span>
                  <a-select
                    v-model:value="runOptions.maxParallelRecords"
                    class="w-[88px] customer-sample-toolbar-select"
                    size="middle"
                    :options="parallelOptions"
                  />
                </div>
                <a-button
                  type="primary"
                  class="!rounded-full"
                  @click="loadRecords()"
                >
                  查询
                </a-button>
                <a-button
                  class="!rounded-full"
                  @click="resetFilters"
                >
                  重置
                </a-button>
              </div>
            </div>

            <div
              class="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-[13px] leading-6 text-slate-600"
            >
              <div class="font-medium text-slate-700">
                当前口径
              </div>
              <div class="mt-1">
                首批只验证内涵问题。列表是去重后的真实病历池；每份病历下可查看关联人工问题。未匹配病历或
                running bundle 未就绪的病历不会进入批量验证。
              </div>
            </div>

            <a-table
              row-key="id"
              size="middle"
              :loading="itemLoading"
              :columns="itemColumns"
              :data-source="records"
              :row-selection="rowSelection"
              :pagination="paginationConfig"
              :scroll="{ x: 1280 }"
              :locale="{ emptyText: tableEmptyText }"
            />
          </div>
        </section>
      </div>
    </div>

    <a-modal
      v-model:open="importModalOpen"
      title="导入客户样本模板"
      :confirm-loading="importingPool"
      ok-text="开始导入"
      cancel-text="取消"
      @ok="handleImportPool"
      @cancel="resetImportForm"
    >
      <div class="space-y-4 pt-2">
        <div>
          <div class="mb-2 text-[13px] font-medium text-slate-700">
            样本池名称
          </div>
          <a-input
            v-model:value="importForm.poolName"
            placeholder="例如：手工问题样本池-第二轮"
            :maxlength="60"
          />
        </div>
        <div class="grid gap-4 md:grid-cols-2">
          <div>
            <div class="mb-2 text-[13px] font-medium text-slate-700">
              Sheet 名称
            </div>
            <a-input
              v-model:value="importForm.sourceSheet"
              placeholder="默认 Sheet2"
              :maxlength="40"
            />
          </div>
          <div>
            <div class="mb-2 text-[13px] font-medium text-slate-700">
              目标场景
            </div>
            <a-select
              v-model:value="importForm.scene"
              :options="sceneOptions"
            />
          </div>
        </div>
        <div>
          <div class="mb-2 text-[13px] font-medium text-slate-700">
            备注
          </div>
          <a-textarea
            v-model:value="importForm.description"
            :rows="3"
            placeholder="可选，记录这次导入的说明"
            :maxlength="200"
          />
        </div>
        <div>
          <div
            class="mb-2 flex items-center justify-between gap-3 text-[13px] font-medium text-slate-700"
          >
            <span>Excel 模板</span>
            <a-button
              type="link"
              class="!px-0"
              @click="handleDownloadTemplate"
            >
              下载模板
            </a-button>
          </div>
          <a-upload-dragger
            v-model:file-list="importFileList"
            :before-upload="handleImportFileSelect"
            :multiple="false"
            :max-count="1"
            accept=".xls,.xlsx"
          >
            <p class="ant-upload-drag-icon">
              <InboxOutlined />
            </p>
            <p class="ant-upload-text">
              点击或拖拽上传 Excel 模板
            </p>
            <p class="ant-upload-hint">
              支持 .xls / .xlsx，默认读取 Sheet2。
            </p>
            <p class="mt-2 text-[12px] text-slate-400">
              核心列：住院号 或 visit_id；存在问题为可选。其余字段可不填。
            </p>
          </a-upload-dragger>
        </div>
      </div>
    </a-modal>

    <a-drawer
      :open="detailOpen"
      width="720"
      title="病历关联问题"
      @close="detailOpen = false"
    >
      <div
        v-if="activeRecord"
        class="space-y-5"
      >
        <a-card
          size="small"
          class="rounded-2xl"
        >
          <template #title>
            病历概况
          </template>
          <div class="space-y-2 text-sm leading-7 text-slate-700">
            <div>
              <span class="font-medium text-slate-500">科室：</span>{{ activeRecord.department || '-' }}
            </div>
            <div>
              <span class="font-medium text-slate-500">患者：</span>{{ activeRecord.patient_name || '-' }}
            </div>
            <div>
              <span class="font-medium text-slate-500">住院号：</span>{{ activeRecord.mr_no || '-' }}
            </div>
            <div>
              <span class="font-medium text-slate-500">visit_id：</span>{{ activeRecord.matched_visit_id || '-' }}
            </div>
          </div>
        </a-card>

        <a-card
          size="small"
          class="rounded-2xl"
        >
          <template #title>
            验证范围
          </template>
          <div class="space-y-2 text-sm leading-7 text-slate-700">
            <div>
              <span class="font-medium text-slate-500">覆盖类型：</span>
              {{ activeRecord.coverage_types.map((item) => coverageLabel(item)).join('、') || '-' }}
            </div>
            <div>
              <span class="font-medium text-slate-500">关联问题数：</span>{{ activeRecord.issue_count }}
            </div>
            <div>
              <span class="font-medium text-slate-500">候选规则：</span>{{ activeRecord.candidate_rule_ids.join(', ') || '-' }}
            </div>
          </div>
        </a-card>

        <a-card
          size="small"
          class="rounded-2xl"
        >
          <template #title>
            病历匹配
          </template>
          <div class="space-y-2 text-sm leading-7 text-slate-700">
            <div>
              <span class="font-medium text-slate-500">匹配状态：</span>{{ matchStatusLabel(activeRecord.match_status) }}
            </div>
            <div>
              <span class="font-medium text-slate-500">visit_id：</span>{{ activeRecord.matched_visit_id || '-' }}
            </div>
            <div>
              <span class="font-medium text-slate-500">patient_id：</span>{{ activeRecord.matched_patient_id || '-' }}
            </div>
            <div>
              <span class="font-medium text-slate-500">institute_id：</span>{{ activeRecord.matched_institute_id || '-' }}
            </div>
            <div>
              <span class="font-medium text-slate-500">同步状态：</span>{{ activeRecord.sync_status || '-' }}
            </div>
            <div>
              <span class="font-medium text-slate-500">bundle 状态：</span>{{ activeRecord.bundle_status || '-' }}
            </div>
          </div>
        </a-card>

        <a-card
          size="small"
          class="rounded-2xl"
        >
          <template #title>
            关联人工问题
          </template>
          <div class="space-y-3">
            <div
              v-for="sample in activeRecord.sample_items"
              :key="sample.id"
              class="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm leading-7 text-slate-700"
            >
              <div class="font-medium text-slate-900">
                行号 {{ sample.row_no }} · {{ sample.issue_category || '未分类' }}
              </div>
              <div class="mt-1">
                {{ sample.manual_issue_text || '-' }}
              </div>
              <div class="mt-2 text-xs text-slate-500">
                候选规则：{{ sample.candidate_rule_ids.join(', ') || '-' }}
              </div>
            </div>
          </div>
        </a-card>
      </div>
    </a-drawer>

    <SemanticRulesBatchResultDrawer
      :open="batchResultOpen"
      :batch-job-detail="batchJobDetail"
      :batch-job-detail-loading="batchJobLoading"
      :batch-job-debug-snapshot="undefined"
      :batch-job-debug-loading="false"
      :fetch-batch-job-debug-snapshot="undefined"
      :close="closeBatchDrawer"
      :export-batch-job-report="handleExportBatchReport"
      :get-batch-job-status-tag-class="getBatchJobStatusTagClass"
      :get-batch-job-status-text="getBatchJobStatusText"
      :format-date-time="formatDateTime"
    />

    <QCReviewDrawer
      :visible="reviewDrawerVisible"
      :record="reviewDrawerRecord"
      @update:visible="reviewDrawerVisible = $event"
      @close="reviewDrawerVisible = false"
      @refresh="loadRecords"
    />
  </main>
</template>

<script setup lang="ts">
import { computed, h, onMounted, onUnmounted, ref } from 'vue'
import { message } from 'ant-design-vue'
import type { UploadFile, UploadProps } from 'ant-design-vue'
import { InboxOutlined } from '@ant-design/icons-vue'
import type { TableColumnsType } from 'ant-design-vue'
import type {
  ManualSamplePool,
  ManualSamplePoolRecord,
  ManualSamplePoolSyncJob,
} from './customer-sample-validation/types'
import {
  getLatestManualSamplePoolSyncJob,
  getManualSamplePoolSyncJob,
  getManualSamplePoolRecords,
  importManualSamplePoolByUpload,
  listManualSamplePools,
  matchManualSamplePool,
  runManualSamplePool,
  syncManualSamplePoolRecords,
} from '@/services/manual-case-sample-service'
import {
  exportSichuanWorkspaceBatchJob,
  getSichuanWorkspaceBatchJob,
} from '@/services/sichuan-rule-workspace-service'
import QCReviewDrawer from '@/components/qc/QCReviewDrawer.vue'
import SemanticRulesBatchResultDrawer from '@/views/workstation-v4/semantic-rules/components/SemanticRulesBatchResultDrawer.vue'
import type { SichuanBatchJob } from '@/views/workstation-v4/semantic-rules/types'

const poolLoading = ref(false)
const itemLoading = ref(false)
const matchLoading = ref(false)
const runLoading = ref(false)
const syncLoading = ref(false)
const importingPool = ref(false)
const selectedRowKeys = ref<string[]>([])
const importModalOpen = ref(false)
const importFileList = ref<UploadFile[]>([])

const pools = ref<ManualSamplePool[]>([])
const selectedPoolId = ref<string>()
const selectedPool = ref<ManualSamplePool>()
const records = ref<ManualSamplePoolRecord[]>([])

const detailOpen = ref(false)
const activeRecord = ref<ManualSamplePoolRecord>()
const reviewDrawerVisible = ref(false)
const reviewDrawerRecord = ref<{
  id: string
  record_id: string
  patient_name?: string
  department?: string
  discharge_date?: string
  score?: number
  defect_count?: number
  status?: string
} | null>(null)

const batchResultOpen = ref(false)
const batchJobDetail = ref<SichuanBatchJob>()
const batchJobLoading = ref(false)
let batchJobPollTimer: ReturnType<typeof setInterval> | null = null
let syncJobPollTimer: ReturnType<typeof setInterval> | null = null
const syncJobDetail = ref<ManualSamplePoolSyncJob>()

const pagination = ref({
  page: 1,
  pageSize: 20,
  total: 0,
})

const filters = ref({
  query: '',
  coverageType: undefined as string | undefined,
  matchStatus: undefined as string | undefined,
  includeInBatch: true,
})
const importForm = ref({
  poolName: '',
  sourceSheet: 'Sheet2',
  description: '',
  scene: 'running',
})
const runOptions = ref({
  maxParallelRecords: 4,
})

const poolOptions = computed(() =>
  pools.value.map((item) => ({
    label: `${item.name}（${item.total_items}）`,
    value: item.id,
  })),
)

const sceneOptions = [
  { label: '运行病历', value: 'running' },
  { label: '终末病历', value: 'final' },
]

const coverageOptions = [
  { label: '内涵问题', value: 'llm_intrinsic' },
  { label: '程序化问题', value: 'programmatic' },
  { label: '暂不支持', value: 'unsupported' },
]

const matchStatusOptions = [
  { label: '已匹配', value: 'matched' },
  { label: '匹配歧义', value: 'ambiguous' },
  { label: '未匹配', value: 'unmatched' },
]
const parallelOptions = [
  { label: '1', value: 1 },
  { label: '2', value: 2 },
  { label: '4', value: 4 },
]

const summaryCards = computed(() => {
  const pool = selectedPool.value
  return [
    { label: '样本总数', value: pool?.total_items ?? 0, help: 'Sheet2 导入后的样本总量' },
    {
      label: '内涵样本',
      value: pool?.llm_intrinsic_items ?? 0,
      help: '当前纳入 LLM 验证的问题样本',
    },
    { label: '已匹配病历', value: pool?.matched_items ?? 0, help: '已映射到系统病历主键的样本数' },
    {
      label: '可运行样本',
      value: pool?.ready_items ?? 0,
      help: 'running bundle 已就绪，可直接发起验证',
    },
  ]
})

const syncProgress = computed(() => syncJobDetail.value?.summary?.progress || {})

const selectedRecordStats = computed(() => {
  const selectedRecords = records.value.filter((record) =>
    selectedRowKeys.value.includes(record.id),
  )
  const runnableRecords = selectedRecords.filter((record) => isRunnableRecord(record))
  return {
    selectedCount: selectedRecords.length,
    runnableCount: runnableRecords.length,
    skippedCount: Math.max(0, selectedRecords.length - runnableRecords.length),
    runnableRecordIds: runnableRecords.map((record) => record.id),
  }
})

const runButtonText = computed(() =>
  selectedRecordStats.value.selectedCount > 0
    ? `发起选中病历验证（${selectedRecordStats.value.selectedCount}）`
    : '发起内涵验证',
)

const paginationConfig = computed(() => ({
  current: pagination.value.page,
  pageSize: pagination.value.pageSize,
  total: pagination.value.total,
  showSizeChanger: true,
  showTotal: (total: number) => `共 ${total} 条`,
  onChange: (page: number, pageSize: number) => {
    pagination.value.page = page
    pagination.value.pageSize = pageSize
    loadRecords()
  },
}))

const tableEmptyText = computed(() =>
  h(
    'div',
    {
      class: 'flex min-h-[220px] flex-col items-center justify-center px-6 py-10 text-center',
    },
    [
      h(InboxOutlined, {
        class: 'mb-3 text-[36px] text-slate-300',
      }),
      h('div', { class: 'text-[15px] font-semibold text-slate-700' }, emptyTitle.value),
      h(
        'div',
        { class: 'mt-2 max-w-[420px] text-[13px] leading-6 text-slate-500' },
        emptyDescription.value,
      ),
    ],
  ),
)

const emptyTitle = computed(() => {
  if (!selectedPoolId.value) return '请先选择样本池'
  if (!selectedPool.value?.matched_items) return '当前还没有匹配成功的病历'
  if (!pagination.value.total) return '当前筛选条件下没有样本'
  return '暂无样本数据'
})

const emptyDescription = computed(() => {
  if (!selectedPoolId.value) {
    return '先选择一个客户样本池，再查看内涵问题样本和匹配状态。'
  }
  if (!selectedPool.value?.matched_items) {
    return '请先执行病历匹配，并确认当前环境已经同步到客户真实病历数据。'
  }
  if (!pagination.value.total) {
    return '可以放宽覆盖类型、匹配状态或关闭“仅首批”后重新查询。'
  }
  return '当前没有可展示的样本。'
})

const itemColumns: TableColumnsType<ManualSamplePoolRecord> = [
  {
    title: '患者 / 住院号',
    key: 'patient',
    width: 200,
    customRender: ({ record }) =>
      h('div', { class: 'space-y-1' }, [
        h('div', { class: 'font-medium text-slate-900' }, record.patient_name || '-'),
        h('div', { class: 'text-xs text-slate-500' }, record.mr_no || '-'),
      ]),
  },
  {
    title: '科室',
    dataIndex: 'department',
    width: 120,
  },
  {
    title: '关联人工问题',
    dataIndex: 'issue_preview_text',
    ellipsis: true,
  },
  {
    title: '覆盖类型',
    dataIndex: 'coverage_types',
    width: 180,
    customRender: ({ record }) =>
      h(
        'span',
        {
          class: coverageTagClass(String(record.coverage_types?.[0] || '')),
        },
        record.coverage_types?.map((item) => coverageLabel(String(item || ''))).join(' / ') || '-',
      ),
  },
  {
    title: '候选规则',
    dataIndex: 'candidate_rule_ids',
    width: 220,
    customRender: ({ record }) => record.candidate_rule_ids.join(', ') || '-',
  },
  {
    title: '匹配状态',
    dataIndex: 'match_status',
    width: 120,
    customRender: ({ value }) =>
      h(
        'span',
        {
          class: matchStatusTagClass(String(value || '')),
        },
        matchStatusLabel(String(value || '')),
      ),
  },
  {
    title: '人工问题数',
    dataIndex: 'issue_count',
    width: 110,
  },
  {
    title: 'bundle',
    dataIndex: 'bundle_status',
    width: 120,
    customRender: ({ value }) => value || '-',
  },
  {
    title: '操作',
    key: 'actions',
    width: 240,
    fixed: 'right',
    customRender: ({ record }) =>
      h('div', { class: 'flex gap-2' }, [
        h(
          'a',
          {
            class: 'text-[#1677ff]',
            onClick: () => openRecordDetail(record),
          },
          '查看详情',
        ),
        record.matched_visit_id
          ? h(
              'a',
              {
                class: 'text-[#1677ff]',
                onClick: () => openReviewDrawer(record),
              },
              '查看病历',
            )
          : h(
              'span',
              {
                class: 'cursor-not-allowed text-slate-300',
                title: '需先完成病历匹配',
              },
              '查看病历',
            ),
        selectedPool.value?.latest_job_id
          ? h(
              'a',
              {
                class: 'text-[#1677ff]',
                onClick: () => openBatchJob(selectedPool.value?.latest_job_id || ''),
              },
              '查看结果',
            )
          : null,
      ]),
  },
]

const rowSelection = computed(() => ({
  selectedRowKeys: selectedRowKeys.value,
  onChange: (keys) => {
    selectedRowKeys.value = keys.map((key) => String(key))
  },
}))

function coverageLabel(value: string): string {
  if (value === 'llm_intrinsic') return '内涵问题'
  if (value === 'programmatic') return '程序化'
  if (value === 'unsupported') return '暂不支持'
  return value || '-'
}

function coverageTagClass(value: string): string {
  if (value === 'llm_intrinsic') {
    return 'inline-flex rounded-full border border-blue-200 bg-blue-50 px-2.5 py-1 text-xs font-medium text-blue-700'
  }
  if (value === 'programmatic') {
    return 'inline-flex rounded-full border border-amber-200 bg-amber-50 px-2.5 py-1 text-xs font-medium text-amber-700'
  }
  return 'inline-flex rounded-full border border-slate-200 bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-600'
}

function matchStatusLabel(value: string): string {
  if (value === 'matched') return '已匹配'
  if (value === 'ambiguous') return '匹配歧义'
  if (value === 'unmatched') return '未匹配'
  return value || '-'
}

function matchStatusTagClass(value: string): string {
  if (value === 'matched') {
    return 'inline-flex rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-1 text-xs font-medium text-emerald-700'
  }
  if (value === 'ambiguous') {
    return 'inline-flex rounded-full border border-amber-200 bg-amber-50 px-2.5 py-1 text-xs font-medium text-amber-700'
  }
  return 'inline-flex rounded-full border border-rose-200 bg-rose-50 px-2.5 py-1 text-xs font-medium text-rose-700'
}

function isRunnableRecord(record: ManualSamplePoolRecord): boolean {
  return (
    record.match_status === 'matched' &&
    record.sync_status === 'synced' &&
    record.bundle_status === 'ready' &&
    !!record.matched_visit_id
  )
}

async function loadPools() {
  poolLoading.value = true
  const result = await listManualSamplePools({ page: 1, page_size: 50 })
  poolLoading.value = false
  if (!result.success || !result.data) {
    message.error(result.message || '获取样本池失败')
    return
  }
  pools.value = result.data.items
  if (!selectedPoolId.value && pools.value.length > 0) {
    selectedPoolId.value = pools.value[0].id
  }
  selectedPool.value = pools.value.find((item) => item.id === selectedPoolId.value)
  if (selectedPoolId.value) {
    await loadLatestSyncJob()
    await loadRecords()
  }
}

async function loadRecords() {
  if (!selectedPoolId.value) {
    records.value = []
    pagination.value.total = 0
    return
  }
  itemLoading.value = true
  const result = await getManualSamplePoolRecords(selectedPoolId.value, {
    coverage_type: filters.value.coverageType,
    match_status: filters.value.matchStatus,
    include_in_batch_1: filters.value.includeInBatch,
    q: filters.value.query || undefined,
    page: pagination.value.page,
    page_size: pagination.value.pageSize,
  })
  itemLoading.value = false
  if (!result.success || !result.data) {
    message.error(result.message || '获取样本明细失败')
    return
  }
  selectedPool.value = result.data.pool
  records.value = result.data.items
  pagination.value.total = result.data.total
  selectedRowKeys.value = selectedRowKeys.value.filter((key) =>
    records.value.some((item) => item.id === key),
  )
}

async function handlePoolChange() {
  pagination.value.page = 1
  selectedRowKeys.value = []
  selectedPool.value = pools.value.find((item) => item.id === selectedPoolId.value)
  await loadLatestSyncJob()
  await loadRecords()
}

function resetFilters() {
  filters.value = {
    query: '',
    coverageType: undefined,
    matchStatus: undefined,
    includeInBatch: true,
  }
  pagination.value.page = 1
  selectedRowKeys.value = []
  loadRecords()
}

function resetImportForm() {
  importModalOpen.value = false
  importForm.value = {
    poolName: '',
    sourceSheet: 'Sheet2',
    description: '',
    scene: 'running',
  }
  importFileList.value = []
}

const handleImportFileSelect: UploadProps['beforeUpload'] = (file) => {
  importFileList.value = [
    {
      uid: file.uid,
      name: file.name,
      status: 'done',
      size: file.size,
      type: file.type,
      originFileObj: file,
    },
  ]
  return false
}

async function handleImportPool() {
  const poolName = importForm.value.poolName.trim()
  const file = importFileList.value[0]?.originFileObj
  if (!poolName) {
    message.warning('请先填写样本池名称')
    return
  }
  if (!file) {
    message.warning('请先上传 Excel 模板')
    return
  }
  importingPool.value = true
  const result = await importManualSamplePoolByUpload({
    pool_name: poolName,
    source_sheet: importForm.value.sourceSheet.trim() || 'Sheet2',
    description: importForm.value.description.trim(),
    scene: importForm.value.scene,
    file,
  })
  importingPool.value = false
  if (!result.success || !result.data) {
    message.error(result.message || '导入客户样本模板失败')
    return
  }
  selectedPoolId.value = result.data.id
  resetImportForm()
  message.success(`导入成功，共写入 ${result.data.imported_rows} 条样本`)
  await loadPools()
}

async function handleDownloadTemplate() {
  const XLSX = await import('xlsx')
  const workbook = XLSX.utils.book_new()
  const worksheet = XLSX.utils.aoa_to_sheet([
    ['住院号', 'visit_id', '存在问题'],
    ['2248248', '', ''],
    ['', 'VISIT-001', '首次病程记录鉴别诊断不全面'],
  ])
  worksheet['!cols'] = [{ wch: 16 }, { wch: 16 }, { wch: 48 }]
  XLSX.utils.book_append_sheet(workbook, worksheet, 'Sheet2')
  XLSX.writeFile(workbook, '客户样本导入模板.xlsx')
}

function openRecordDetail(record: ManualSamplePoolRecord) {
  activeRecord.value = record
  detailOpen.value = true
}

function openReviewDrawer(record: ManualSamplePoolRecord) {
  if (!record.matched_visit_id) {
    message.warning('当前样本尚未匹配到病历，无法查看原文')
    return
  }
  reviewDrawerRecord.value = {
    id: record.id,
    record_id: record.matched_visit_id,
    patient_name: record.patient_name,
    department: record.department,
    defect_count: 0,
    status: record.match_status || 'pending',
  }
  reviewDrawerVisible.value = true
}

async function handleMatchPool() {
  if (!selectedPoolId.value) return
  matchLoading.value = true
  const result = await matchManualSamplePool(selectedPoolId.value)
  matchLoading.value = false
  if (!result.success) {
    message.error(result.message || '执行病历匹配失败')
    return
  }
  message.success('病历匹配完成')
  await loadPools()
}

async function handleSyncPoolRecords() {
  if (!selectedPoolId.value) return
  syncLoading.value = true
  const result = await syncManualSamplePoolRecords(selectedPoolId.value, {
    only_intrinsic: true,
    include_in_batch_1: true,
  })
  syncLoading.value = false
  if (!result.success || !result.data) {
    message.error(result.message || '同步样本病历失败')
    return
  }
  message.success('样本病历同步任务已创建')
  await openSyncJob(result.data.job_id)
}

async function handleRunPool() {
  if (!selectedPoolId.value) return
  const { selectedCount, runnableCount, skippedCount, runnableRecordIds } =
    selectedRecordStats.value
  if (selectedCount > 0 && runnableCount === 0) {
    message.warning('当前选中的病历还未完成匹配、同步或 bundle 准备，暂时无法发起验证')
    return
  }
  if (selectedCount > 0 && skippedCount > 0) {
    message.info(
      `已选 ${selectedCount} 份病历，其中 ${runnableCount} 份可执行，${skippedCount} 份将自动跳过`,
    )
  }
  runLoading.value = true
  const result = await runManualSamplePool(selectedPoolId.value, {
    record_ids: runnableRecordIds,
    max_parallel_records: runOptions.value.maxParallelRecords,
  })
  runLoading.value = false
  if (!result.success || !result.data) {
    message.error(result.message || '创建样本验证任务失败')
    return
  }
  message.success(
    `已创建验证任务，覆盖 ${result.data.sample_item_count} 条样本 / ${result.data.record_count} 份病历 / ${result.data.rule_count} 条规则，并发 ${runOptions.value.maxParallelRecords} 份病历`,
  )
  selectedRowKeys.value = []
  await loadPools()
  await openBatchJob(result.data.job_id)
}

async function openLatestJob() {
  if (!selectedPool.value?.latest_job_id) return
  await openBatchJob(selectedPool.value.latest_job_id)
}

async function loadLatestSyncJob() {
  if (!selectedPoolId.value) {
    syncJobDetail.value = undefined
    stopSyncJobPolling()
    return
  }
  const result = await getLatestManualSamplePoolSyncJob(selectedPoolId.value)
  if (!result.success) return
  syncJobDetail.value = result.data || undefined
  if (syncJobDetail.value && isSyncJobRunning(syncJobDetail.value.status)) {
    startSyncJobPolling(syncJobDetail.value.id)
  } else {
    stopSyncJobPolling()
  }
}

async function openSyncJob(jobId: string) {
  stopSyncJobPolling()
  const result = await getManualSamplePoolSyncJob(jobId)
  if (!result.success || !result.data) {
    message.error(result.message || '获取样本同步任务失败')
    return
  }
  syncJobDetail.value = result.data
  if (isSyncJobRunning(result.data.status)) {
    startSyncJobPolling(jobId)
  } else {
    await loadPools()
    await loadRecords()
  }
}

async function openBatchJob(jobId: string) {
  stopBatchJobPolling()
  batchJobLoading.value = true
  batchResultOpen.value = true
  const result = await getSichuanWorkspaceBatchJob(jobId)
  batchJobLoading.value = false
  if (!result.success || !result.data) {
    message.error(result.message || '获取任务详情失败')
    return
  }
  batchJobDetail.value = result.data
  if (isBatchJobRunning(result.data.status)) {
    startBatchJobPolling(jobId)
  }
}

function closeBatchDrawer() {
  stopBatchJobPolling()
  batchResultOpen.value = false
  batchJobDetail.value = undefined
}

function isBatchJobRunning(status?: string) {
  const normalized = String(status || '').toLowerCase()
  return normalized === 'queued' || normalized === 'running'
}

function stopBatchJobPolling() {
  if (batchJobPollTimer) {
    clearInterval(batchJobPollTimer)
    batchJobPollTimer = null
  }
}

function isSyncJobRunning(status?: string) {
  const normalized = String(status || '').toLowerCase()
  return normalized === 'queued' || normalized === 'running'
}

function stopSyncJobPolling() {
  if (syncJobPollTimer) {
    clearInterval(syncJobPollTimer)
    syncJobPollTimer = null
  }
}

function startSyncJobPolling(jobId: string) {
  stopSyncJobPolling()
  syncJobPollTimer = setInterval(async () => {
    const result = await getManualSamplePoolSyncJob(jobId)
    if (!result.success || !result.data) return
    syncJobDetail.value = result.data
    if (!isSyncJobRunning(result.data.status)) {
      stopSyncJobPolling()
      await loadPools()
      await loadRecords()
    }
  }, 3000)
}

function startBatchJobPolling(jobId: string) {
  stopBatchJobPolling()
  batchJobPollTimer = setInterval(async () => {
    if (!batchResultOpen.value) {
      stopBatchJobPolling()
      return
    }
    const result = await getSichuanWorkspaceBatchJob(jobId)
    if (!result.success || !result.data) return
    batchJobDetail.value = result.data
    if (!isBatchJobRunning(result.data.status)) {
      stopBatchJobPolling()
      await loadPools()
      await loadRecords()
    }
  }, 3000)
}

async function handleExportBatchReport(jobId: string) {
  const result = await exportSichuanWorkspaceBatchJob({ job_id: jobId, format: 'xlsx' })
  if (!result.success || !result.data) {
    message.error(result.message || '导出验证任务失败')
    return
  }
  const blob = new Blob([result.data], {
    type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  })
  const url = window.URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `manual-sample-validation-${jobId}.xlsx`
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  window.URL.revokeObjectURL(url)
}

function getBatchJobStatusText(status?: string): string {
  const normalized = String(status || '').toLowerCase()
  if (normalized === 'completed') return '已完成'
  if (normalized === 'running') return '执行中'
  if (normalized === 'failed') return '失败'
  if (normalized === 'canceled') return '已取消'
  return '排队中'
}

function getBatchJobStatusTagClass(status?: string): string {
  const normalized = String(status || '').toLowerCase()
  if (normalized === 'completed') return 'border-emerald-200 bg-emerald-50 text-emerald-700'
  if (normalized === 'running') return 'border-blue-200 bg-blue-50 text-blue-700'
  if (normalized === 'failed') return 'border-rose-200 bg-rose-50 text-rose-700'
  if (normalized === 'canceled') return 'border-slate-200 bg-slate-100 text-slate-600'
  return 'border-amber-200 bg-amber-50 text-amber-700'
}

function syncJobStatusText(status?: string): string {
  const normalized = String(status || '').toLowerCase()
  if (normalized === 'completed') return '已完成'
  if (normalized === 'running') return '执行中'
  if (normalized === 'failed') return '失败'
  return '排队中'
}

function syncJobStatusColor(status?: string): string {
  const normalized = String(status || '').toLowerCase()
  if (normalized === 'completed') return 'success'
  if (normalized === 'running') return 'processing'
  if (normalized === 'failed') return 'error'
  return 'default'
}

function formatDateTime(value?: string) {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  }).format(date)
}

onMounted(() => {
  loadPools()
})

onUnmounted(() => {
  stopBatchJobPolling()
  stopSyncJobPolling()
})
</script>

<style scoped>
.customer-sample-toolbar-input {
  height: 40px;
  font-size: 14px;
  line-height: 22px;
}

.customer-sample-toolbar-input::placeholder {
  font-size: 14px;
}

:deep(.customer-sample-toolbar-select .ant-select-selector) {
  height: 40px !important;
  padding: 0 12px !important;
}

:deep(.customer-sample-toolbar-select .ant-select-selection-placeholder),
:deep(.customer-sample-toolbar-select .ant-select-selection-item) {
  font-size: 14px;
  line-height: 38px !important;
}

:deep(.customer-sample-toolbar-select .ant-select-selection-search-input) {
  height: 38px !important;
}
</style>
