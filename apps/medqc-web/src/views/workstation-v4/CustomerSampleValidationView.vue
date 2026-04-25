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
              <div class="flex flex-col gap-3 xl:flex-row xl:items-center">
                <div class="flex min-w-0 flex-col gap-1">
                  <div class="text-[12px] font-medium text-slate-500">
                    当前样本池
                  </div>
                  <a-select
                    v-model:value="selectedPoolId"
                    class="w-full min-w-[280px] max-w-[420px] customer-sample-toolbar-select"
                    size="middle"
                    :loading="poolLoading"
                    :options="poolOptions"
                    placeholder="请选择样本池"
                    show-search
                    option-filter-prop="label"
                    @change="handlePoolChange"
                  />
                </div>
                <div class="flex flex-wrap items-center gap-2 text-[13px] text-slate-500">
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
                  placeholder="快速切换样本池"
                  show-search
                  option-filter-prop="label"
                  @change="handlePoolChange"
                />
                <a-input
                  v-model:value="filters.query"
                  class="w-full xl:min-w-[320px] xl:flex-1 customer-sample-toolbar-input"
                  size="middle"
                  placeholder="搜索患者、住院号或问题摘要"
                  @press-enter="loadRecords()"
                />
              </div>

              <div class="flex flex-wrap gap-2 xl:justify-end">
                <a-select
                  v-model:value="filters.coverageType"
                  class="min-w-[140px] customer-sample-toolbar-select"
                  size="middle"
                  allow-clear
                  placeholder="样本范围"
                  :options="coverageOptions"
                />
                <a-select
                  v-model:value="filters.matchStatus"
                  class="min-w-[140px] customer-sample-toolbar-select"
                  size="middle"
                  allow-clear
                  placeholder="病历关联"
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
                {{ currentScopeDescription }}
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
            识别范围
          </template>
          <div class="space-y-2 text-sm leading-7 text-slate-700">
            <div>
              <span class="font-medium text-slate-500">文书范围：</span>
              {{ summarizeRecordScope(activeRecord) }}
            </div>
            <div>
              <span class="font-medium text-slate-500">验证说明：</span>
              {{ recordScopeHint(activeRecord) }}
            </div>
            <div>
              <span class="font-medium text-slate-500">样本范围：</span>
              {{ activeRecord.coverage_types.map((item) => coverageLabel(item)).join('、') || '-' }}
            </div>
          </div>
        </a-card>

        <a-card
          size="small"
          class="rounded-2xl"
        >
          <template #title>
            病历关联
          </template>
          <div class="space-y-2 text-sm leading-7 text-slate-700">
            <div>
              <span class="font-medium text-slate-500">关联结果：</span>{{ matchStatusLabel(activeRecord.match_status) }}
            </div>
            <div>
              <span class="font-medium text-slate-500">下一步：</span>{{ matchStatusHint(activeRecord.match_status) }}
            </div>
            <div>
              <span class="font-medium text-slate-500">visit_id：</span>{{ activeRecord.matched_visit_id || '-' }}
            </div>
            <div>
              <span class="font-medium text-slate-500">同步状态：</span>{{ activeRecord.sync_status || '-' }}
            </div>
            <div>
              <span class="font-medium text-slate-500">文书就绪：</span>{{ bundleStatusLabel(activeRecord.bundle_status) }}
            </div>
            <div>
              <span class="font-medium text-slate-500">处理建议：</span>{{ bundleStatusHint(activeRecord.bundle_status) }}
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
      :focus-visit-id="batchResultFocusRecord?.visitId"
      :focus-record-id="batchResultFocusRecord?.recordId"
      :focus-record-label="batchResultFocusRecord?.label"
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
const batchResultFocusRecord = ref<{
  visitId: string
  recordId: string
  label: string
} | null>(null)
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
  { label: '内涵验证', value: 'llm_intrinsic' },
  { label: '程序规则', value: 'programmatic' },
  { label: '未纳入', value: 'unsupported' },
]

const matchStatusOptions = [
  { label: '已关联病历', value: 'matched' },
  { label: '待人工确认', value: 'ambiguous' },
  { label: '未找到病历', value: 'unmatched' },
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

const currentScopeDescription = computed(() => {
  const total = pagination.value.total || 0
  const matched = records.value.filter((record) => record.match_status === 'matched').length
  const ready = records.value.filter((record) => record.bundle_status === 'ready').length
  const filterLabels = [
    filters.value.coverageType ? `样本范围：${coverageLabel(filters.value.coverageType)}` : '',
    filters.value.matchStatus ? `病历关联：${matchStatusLabel(filters.value.matchStatus)}` : '',
    filters.value.includeInBatch ? '仅看首批样本' : '',
  ].filter(Boolean)
  const base = `当前列表展示的是去重后的真实病历池，共 ${total} 份病历；其中已关联 ${matched} 份，文书已就绪 ${ready} 份。`
  if (!filterLabels.length) {
    return `${base} 未关联到真实病历或文书未就绪的病历不会进入批量验证。`
  }
  return `${base} 当前筛选：${filterLabels.join('，')}。`
})

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
        h('div', { class: 'font-medium text-slate-900' }, resolveRecordPatientName(record)),
        h('div', { class: 'text-xs text-slate-500' }, resolveRecordIdentifier(record)),
      ]),
  },
  {
    title: '科室',
    dataIndex: 'department',
    width: 120,
  },
  {
    title: '问题摘要',
    key: 'issue_summary',
    width: 280,
    customRender: ({ record }) =>
      h('div', { class: 'space-y-1.5' }, [
        ...(resolveIssueSummaryLines(record).length
          ? resolveIssueSummaryLines(record).map((line, index) =>
              h(
                'div',
                {
                  class:
                    index === 0
                      ? 'text-[13px] leading-6 text-slate-700'
                      : 'text-[13px] leading-6 text-slate-500',
                },
                line,
              ),
            )
          : [
              h(
                'div',
                {
                  class: 'text-[13px] leading-6 text-slate-400',
                },
                '当前没有人工问题摘要',
              ),
            ]),
        h(
          'div',
          {
            class: 'text-[12px] font-medium text-slate-400',
          },
          `共 ${record.issue_count || 0} 条问题`,
        ),
      ]),
  },
  {
    title: '文书范围',
    dataIndex: 'document_scope_labels',
    width: 180,
    customRender: ({ record }) =>
      h('div', { class: 'flex flex-wrap gap-2' }, buildScopeChips(record)),
  },
  {
    title: '病历关联',
    dataIndex: 'match_status',
    width: 170,
    customRender: ({ value }) =>
      h('div', { class: 'space-y-1.5' }, [
        h(
          'span',
          {
            class: matchStatusTagClass(String(value || '')),
          },
          matchStatusLabel(String(value || '')),
        ),
        h(
          'div',
          {
            class: 'text-[12px] leading-5 text-slate-400',
          },
          matchStatusHint(String(value || '')),
        ),
      ]),
  },
  {
    title: '文书就绪',
    dataIndex: 'bundle_status',
    width: 170,
    customRender: ({ value }) =>
      h('div', { class: 'space-y-1.5' }, [
        h(
          'span',
          {
            class: bundleStatusTagClass(String(value || '')),
          },
          bundleStatusLabel(String(value || '')),
        ),
        h(
          'div',
          {
            class: 'text-[12px] leading-5 text-slate-400',
          },
          bundleStatusHint(String(value || '')),
        ),
      ]),
  },
  {
    title: '操作',
    key: 'actions',
    width: 240,
    fixed: 'right',
    customRender: ({ record }) =>
      h('div', { class: 'space-y-2' }, [
        renderPrimaryAction(record),
        h(
          'div',
          { class: 'flex flex-wrap gap-x-3 gap-y-1 text-[12px] leading-5' },
          buildSecondaryActions(record),
        ),
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
  if (value === 'llm_intrinsic') return '内涵验证'
  if (value === 'programmatic') return '程序规则'
  if (value === 'unsupported') return '未纳入'
  return value || '-'
}

function matchStatusLabel(value: string): string {
  if (value === 'matched') return '已关联病历'
  if (value === 'ambiguous') return '待人工确认'
  if (value === 'unmatched') return '未找到病历'
  return value || '-'
}

function matchStatusHint(value: string): string {
  if (value === 'matched') return '已定位到真实病历，可继续同步文书。'
  if (value === 'ambiguous') return '同号命中多次住院，请先确认归属病历。'
  if (value === 'unmatched') return '请核对住院号、姓名或日期后重新匹配。'
  return '请先完成病历匹配。'
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

function bundleStatusLabel(value: string): string {
  if (value === 'ready') return '已就绪'
  if (value === 'missing') return '待同步'
  if (value === 'pending') return '准备中'
  return value || '-'
}

function bundleStatusHint(value: string): string {
  if (value === 'ready') return '可以查看病历并发起样本验证。'
  if (value === 'pending') return '正在刷新文书和 bundle，请稍后再看。'
  if (value === 'missing') return '下一步执行“同步样本病历”。'
  return '请先完成病历同步。'
}

function bundleStatusTagClass(value: string): string {
  if (value === 'ready') {
    return 'inline-flex rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-1 text-xs font-medium text-emerald-700'
  }
  if (value === 'pending') {
    return 'inline-flex rounded-full border border-amber-200 bg-amber-50 px-2.5 py-1 text-xs font-medium text-amber-700'
  }
  return 'inline-flex rounded-full border border-slate-200 bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-600'
}

function summarizeRuleScopes(ruleIds: string[]): string {
  const scopes: string[] = []
  const pushScope = (label: string) => {
    if (!scopes.includes(label)) scopes.push(label)
  }
  const rules = new Set((ruleIds || []).map((item) => String(item || '').trim()).filter(Boolean))
  for (const ruleId of rules) {
    const num = Number.parseInt(ruleId.replace('SC-', ''), 10)
    if (Number.isNaN(num)) continue
    if (num <= 20) {
      pushScope('入院记录')
    } else if (num <= 27) {
      pushScope('首次病程')
    } else if (
      num <= 49 ||
      num === 70 ||
      num === 73 ||
      num === 74 ||
      num === 79 ||
      num === 143 ||
      num === 146
    ) {
      pushScope('日常病程')
    } else if (num <= 60) {
      pushScope('查房讨论')
    } else if (num <= 76) {
      pushScope('交接会诊')
    } else if (num <= 115) {
      pushScope('手术麻醉')
    } else if (num <= 127) {
      pushScope('出院记录')
    } else if (num <= 136) {
      pushScope('知情同意')
    } else if (num <= 140) {
      pushScope('检查检验')
    }
  }
  return scopes.join(' / ') || '-'
}

function summarizeRecordScope(record: ManualSamplePoolRecord): string {
  const labels = (record.document_scope_labels || []).filter(Boolean)
  if (labels.length) {
    return labels.join(' / ')
  }
  return summarizeRuleScopes(record.candidate_rule_ids || [])
}

function recordScopeHint(record: ManualSamplePoolRecord): string {
  if ((record.document_scope_labels || []).length > 0) {
    return '已按当前病历实际同步到的文书类型识别验证范围。'
  }
  if ((record.candidate_rule_ids || []).length > 0) {
    return '当前仍按样本问题推断范围，待同步后会自动刷新。'
  }
  return '当前还没有可识别的文书范围。'
}

function resolveIssueSummaryLines(record: ManualSamplePoolRecord): string[] {
  const previews = (record.issue_preview || []).filter(Boolean)
  if (previews.length > 0) {
    return previews.slice(0, 2)
  }
  return record.issue_preview_text && record.issue_preview_text !== '-'
    ? [record.issue_preview_text]
    : []
}

function buildScopeChips(record: ManualSamplePoolRecord) {
  const labels = summarizeRecordScope(record)
    .split(' / ')
    .map((item) => item.trim())
    .filter(Boolean)
  if (!labels.length || (labels.length === 1 && labels[0] === '-')) {
    return [
      h(
        'span',
        {
          class:
            'inline-flex rounded-full border border-slate-200 bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-500',
        },
        '待识别',
      ),
    ]
  }
  return labels.map((label) =>
    h(
      'span',
      {
        class:
          'inline-flex rounded-full border border-cyan-200 bg-cyan-50 px-2.5 py-1 text-xs font-medium text-cyan-700',
      },
      label,
    ),
  )
}

function renderPrimaryAction(record: ManualSamplePoolRecord) {
  const primary = resolvePrimaryAction(record)
  return h(
    'button',
    {
      type: 'button',
      class:
        'inline-flex rounded-full border border-sky-200 bg-sky-50 px-3 py-1.5 text-[12px] font-medium text-sky-700 transition hover:border-sky-300 hover:bg-sky-100',
      onClick: primary.handler,
    },
    primary.label,
  )
}

function buildSecondaryActions(record: ManualSamplePoolRecord) {
  const actions = []
  const primary = resolvePrimaryAction(record).key
  if (primary !== 'detail') {
    actions.push(
      h(
        'a',
        {
          class: 'text-slate-500 hover:text-[#1677ff]',
          onClick: () => openRecordDetail(record),
        },
        '查看详情',
      ),
    )
  }
  if (record.matched_visit_id && primary !== 'review') {
    actions.push(
      h(
        'a',
        {
          class: 'text-slate-500 hover:text-[#1677ff]',
          onClick: () => openReviewDrawer(record),
        },
        '查看病历',
      ),
    )
  }
  if (selectedPool.value?.latest_job_id && record.matched_visit_id) {
    actions.push(
      h(
        'a',
        {
          class: 'text-slate-500 hover:text-[#1677ff]',
          onClick: () =>
            openBatchJob(selectedPool.value?.latest_job_id || '', {
              visitId: record.matched_visit_id || '',
              recordId: resolveRecordIdentifier(record),
              label: [
                resolveRecordPatientName(record) === '-' ? '' : resolveRecordPatientName(record),
                record.department || '',
                resolveRecordIdentifier(record),
              ]
                .filter(Boolean)
                .join(' · '),
            }),
        },
        '查看结果',
      ),
    )
  }
  return actions
}

function resolvePrimaryAction(record: ManualSamplePoolRecord): {
  key: 'detail' | 'review'
  label: string
  handler: () => void
} {
  if (record.matched_visit_id && record.bundle_status === 'ready') {
    return {
      key: 'review',
      label: '查看病历',
      handler: () => openReviewDrawer(record),
    }
  }
  return {
    key: 'detail',
    label: '查看详情',
    handler: () => openRecordDetail(record),
  }
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

function resolveRecordPatientName(record: ManualSamplePoolRecord): string {
  return String(record.patient_name || '').trim() || '-'
}

function resolveRecordIdentifier(record: ManualSamplePoolRecord): string {
  const rawVisitId = String(record.sample_items?.[0]?.visit_id || '').trim()
  return (
    String(record.mr_no || '').trim() ||
    rawVisitId ||
    String(record.matched_visit_id || '').trim() ||
    '-'
  )
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

async function openBatchJob(
  jobId: string,
  focusRecord?: { visitId?: string; recordId?: string; label?: string } | null,
) {
  stopBatchJobPolling()
  batchJobLoading.value = true
  batchResultOpen.value = true
  const focusVisitId = String(focusRecord?.visitId || '').trim()
  const focusRecordId = String(focusRecord?.recordId || '').trim()
  batchResultFocusRecord.value =
    focusVisitId || focusRecordId
      ? {
          visitId: focusVisitId,
          recordId: focusRecordId,
          label: String(focusRecord?.label || '').trim(),
        }
      : null
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
  batchResultFocusRecord.value = null
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

async function handleExportBatchReport(format: 'xlsx' | 'csv' = 'xlsx') {
  const jobId = String(batchJobDetail.value?.id || '').trim()
  if (!jobId) {
    message.warning('当前任务详情未加载完成，暂时无法导出报告')
    return
  }
  const result = await exportSichuanWorkspaceBatchJob({ job_id: jobId, format })
  if (!result.success || !result.data) {
    message.error(result.message || '导出验证任务失败')
    return
  }
  const blob = new Blob([result.data], {
    type:
      format === 'csv'
        ? 'text/csv;charset=utf-8'
        : 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  })
  const url = window.URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `manual-sample-validation-${jobId}.${format}`
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
