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
import { InboxOutlined } from '@ant-design/icons-vue'
import type { TableColumnsType } from 'ant-design-vue'
import type { ManualSamplePool, ManualSamplePoolRecord } from './customer-sample-validation/types'
import {
  getManualSamplePoolRecords,
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
const selectedRowKeys = ref<string[]>([])

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

const poolOptions = computed(() =>
  pools.value.map((item) => ({
    label: `${item.name}（${item.total_items}）`,
    value: item.id,
  })),
)

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

const selectedRunnableCount = computed(() => selectedRowKeys.value.length)

const runButtonText = computed(() =>
  selectedRunnableCount.value > 0
    ? `发起选中病历验证（${selectedRunnableCount.value}）`
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
  getCheckboxProps: (record) => ({
    disabled: !isRunnableRecord(record),
  }),
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
    records.value.some((item) => item.id === key && isRunnableRecord(item)),
  )
}

async function handlePoolChange() {
  pagination.value.page = 1
  selectedRowKeys.value = []
  selectedPool.value = pools.value.find((item) => item.id === selectedPoolId.value)
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
  message.success(
    `同步完成：可抽取 ${result.data.eligible_visits} 份病历，拉取 ${result.data.total_rows_pulled} 行，写入 ${result.data.total_rows_upserted} 行`,
  )
  await loadPools()
  await loadRecords()
}

async function handleRunPool() {
  if (!selectedPoolId.value) return
  runLoading.value = true
  const result = await runManualSamplePool(selectedPoolId.value, {
    record_ids: selectedRowKeys.value,
  })
  runLoading.value = false
  if (!result.success || !result.data) {
    message.error(result.message || '创建样本验证任务失败')
    return
  }
  message.success(
    `已创建验证任务，覆盖 ${result.data.sample_item_count} 条样本 / ${result.data.record_count} 份病历 / ${result.data.rule_count} 条规则`,
  )
  selectedRowKeys.value = []
  await loadPools()
  await openBatchJob(result.data.job_id)
}

async function openLatestJob() {
  if (!selectedPool.value?.latest_job_id) return
  await openBatchJob(selectedPool.value.latest_job_id)
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
