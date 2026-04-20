<template>
  <div class="min-h-screen bg-slate-50 p-6">
    <div class="mx-auto max-w-7xl space-y-6">
      <a-card
        :bordered="false"
        class="rounded-3xl shadow-sm"
      >
        <div class="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <div class="mb-3 flex flex-wrap items-center gap-2">
              <a-tag color="blue">
                运行病历
              </a-tag>
              <a-tag color="processing">
                客户样本验证
              </a-tag>
            </div>
            <h1 class="text-3xl font-semibold text-slate-900">
              客户样本验证
            </h1>
            <p class="mt-3 max-w-3xl text-sm leading-7 text-slate-600">
              基于客户人工核查样本，核对系统病历同步情况，并对首批内涵问题执行 LLM
              验证。页面重点展示人工问题、样本匹配状态和批量质控结果，不混入程序化时效问题。
            </p>
          </div>
          <div class="flex flex-wrap gap-2">
            <a-button
              class="!rounded-xl"
              :loading="poolLoading"
              @click="loadPools()"
            >
              刷新样本池
            </a-button>
            <a-button
              type="primary"
              class="!rounded-xl"
              :disabled="!selectedPoolId"
              :loading="matchLoading"
              @click="handleMatchPool"
            >
              执行病历匹配
            </a-button>
            <a-button
              type="primary"
              ghost
              class="!rounded-xl"
              :disabled="!selectedPoolId || !selectedPool?.llm_intrinsic_items"
              :loading="runLoading"
              @click="handleRunPool"
            >
              发起内涵验证
            </a-button>
            <a-button
              class="!rounded-xl"
              :disabled="!selectedPool?.latest_job_id"
              @click="openLatestJob"
            >
              查看最近任务
            </a-button>
          </div>
        </div>
      </a-card>

      <div class="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
        <a-card
          v-for="item in summaryCards"
          :key="item.label"
          :bordered="false"
          class="rounded-2xl shadow-sm"
        >
          <div class="text-sm text-slate-500">
            {{ item.label }}
          </div>
          <div class="mt-3 text-3xl font-semibold text-slate-900">
            {{ item.value }}
          </div>
          <div
            v-if="item.help"
            class="mt-2 text-xs text-slate-400"
          >
            {{ item.help }}
          </div>
        </a-card>
      </div>

      <a-card
        :bordered="false"
        class="rounded-3xl shadow-sm"
      >
        <div class="grid gap-4 xl:grid-cols-[320px_minmax(0,1fr)]">
          <div class="space-y-4">
            <div>
              <div class="mb-2 text-sm font-medium text-slate-700">
                样本池
              </div>
              <a-select
                v-model:value="selectedPoolId"
                class="w-full"
                size="large"
                :loading="poolLoading"
                :options="poolOptions"
                placeholder="请选择样本池"
                @change="handlePoolChange"
              />
            </div>
            <div class="rounded-2xl border border-slate-200 bg-slate-50 p-4">
              <div class="text-sm font-medium text-slate-700">
                当前样本池
              </div>
              <div
                v-if="selectedPool"
                class="mt-3 space-y-2 text-sm text-slate-600"
              >
                <div><span class="text-slate-400">名称：</span>{{ selectedPool.name }}</div>
                <div><span class="text-slate-400">来源：</span>{{ selectedPool.source_sheet }}</div>
                <div><span class="text-slate-400">文件：</span>{{ selectedPool.source_file }}</div>
                <div>
                  <span class="text-slate-400">最近任务：</span>{{ selectedPool.latest_job_id || '暂无' }}
                </div>
              </div>
              <div
                v-else
                class="mt-3 text-sm text-slate-400"
              >
                暂无样本池，请先导入 Sheet2。
              </div>
            </div>
            <div class="rounded-2xl border border-slate-200 bg-white p-4">
              <div class="text-sm font-medium text-slate-700">
                筛选条件
              </div>
              <div class="mt-3 space-y-3">
                <a-input
                  v-model:value="filters.query"
                  size="large"
                  placeholder="搜索患者/住院号/人工问题"
                  @press-enter="loadItems()"
                />
                <a-select
                  v-model:value="filters.coverageType"
                  size="large"
                  allow-clear
                  placeholder="覆盖类型"
                  :options="coverageOptions"
                />
                <a-select
                  v-model:value="filters.matchStatus"
                  size="large"
                  allow-clear
                  placeholder="匹配状态"
                  :options="matchStatusOptions"
                />
                <a-switch
                  v-model:checked="filters.includeInBatch"
                  checked-children="仅首批"
                  un-checked-children="全部"
                />
                <div class="flex gap-2">
                  <a-button
                    type="primary"
                    class="!rounded-xl"
                    @click="loadItems()"
                  >
                    查询
                  </a-button>
                  <a-button
                    class="!rounded-xl"
                    @click="resetFilters"
                  >
                    重置
                  </a-button>
                </div>
              </div>
            </div>
          </div>

          <div class="space-y-4">
            <div
              class="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600"
            >
              首批只验证内涵问题，优先覆盖入院记录、首次病程、日常病程、会诊执行和上级查房内容质量。程序化/时效类问题保留在样本池中，但不进入本轮
              LLM 批量验证。
            </div>
            <a-table
              row-key="id"
              size="middle"
              :loading="itemLoading"
              :columns="itemColumns"
              :data-source="items"
              :pagination="paginationConfig"
              :scroll="{ x: 1280 }"
            />
          </div>
        </div>
      </a-card>
    </div>

    <a-drawer
      :open="detailOpen"
      width="720"
      title="样本详情"
      @close="detailOpen = false"
    >
      <div
        v-if="activeItem"
        class="space-y-5"
      >
        <a-card
          size="small"
          class="rounded-2xl"
        >
          <template #title>
            人工问题
          </template>
          <div class="space-y-2 text-sm leading-7 text-slate-700">
            <div>
              <span class="font-medium text-slate-500">科室：</span>{{ activeItem.department || '-' }}
            </div>
            <div>
              <span class="font-medium text-slate-500">患者：</span>{{ activeItem.patient_name || '-' }}
            </div>
            <div>
              <span class="font-medium text-slate-500">住院号：</span>{{ activeItem.mr_no || '-' }}
            </div>
            <div>
              <span class="font-medium text-slate-500">问题：</span>{{ activeItem.manual_issue_text }}
            </div>
          </div>
        </a-card>

        <a-card
          size="small"
          class="rounded-2xl"
        >
          <template #title>
            内涵分类
          </template>
          <div class="space-y-2 text-sm leading-7 text-slate-700">
            <div>
              <span class="font-medium text-slate-500">覆盖类型：</span>{{ coverageLabel(activeItem.coverage_type) }}
            </div>
            <div>
              <span class="font-medium text-slate-500">问题分类：</span>{{ activeItem.issue_category || '-' }}
            </div>
            <div>
              <span class="font-medium text-slate-500">首批纳入：</span>{{ activeItem.include_in_batch_1 ? '是' : '否' }}
            </div>
            <div>
              <span class="font-medium text-slate-500">候选规则：</span>{{ activeItem.candidate_rule_ids.join(', ') || '-' }}
            </div>
            <div v-if="activeItem.exclude_reason">
              <span class="font-medium text-slate-500">排除原因：</span>{{ activeItem.exclude_reason }}
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
              <span class="font-medium text-slate-500">匹配状态：</span>{{ matchStatusLabel(activeItem.match_status) }}
            </div>
            <div>
              <span class="font-medium text-slate-500">visit_id：</span>{{ activeItem.matched_visit_id || '-' }}
            </div>
            <div>
              <span class="font-medium text-slate-500">patient_id：</span>{{ activeItem.matched_patient_id || '-' }}
            </div>
            <div>
              <span class="font-medium text-slate-500">institute_id：</span>{{ activeItem.matched_institute_id || '-' }}
            </div>
            <div>
              <span class="font-medium text-slate-500">同步状态：</span>{{ activeItem.sync_status || '-' }}
            </div>
            <div>
              <span class="font-medium text-slate-500">bundle 状态：</span>{{ activeItem.bundle_status || '-' }}
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
  </div>
</template>

<script setup lang="ts">
import { computed, h, onMounted, ref } from 'vue'
import { message } from 'ant-design-vue'
import type { TableColumnsType } from 'ant-design-vue'
import type { ManualSamplePool, ManualSamplePoolItem } from './customer-sample-validation/types'
import {
  getManualSamplePoolItems,
  listManualSamplePools,
  matchManualSamplePool,
  runManualSamplePool,
} from '@/services/manual-case-sample-service'
import {
  exportSichuanWorkspaceBatchJob,
  getSichuanWorkspaceBatchJob,
} from '@/services/sichuan-rule-workspace-service'
import SemanticRulesBatchResultDrawer from '@/views/workstation-v4/semantic-rules/components/SemanticRulesBatchResultDrawer.vue'
import type { SichuanBatchJob } from '@/views/workstation-v4/semantic-rules/types'

const poolLoading = ref(false)
const itemLoading = ref(false)
const matchLoading = ref(false)
const runLoading = ref(false)

const pools = ref<ManualSamplePool[]>([])
const selectedPoolId = ref<string>()
const selectedPool = ref<ManualSamplePool>()
const items = ref<ManualSamplePoolItem[]>([])

const detailOpen = ref(false)
const activeItem = ref<ManualSamplePoolItem>()

const batchResultOpen = ref(false)
const batchJobDetail = ref<SichuanBatchJob>()
const batchJobLoading = ref(false)

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
    { label: '样本总数', value: pool?.total_items ?? 0 },
    { label: '内涵样本', value: pool?.llm_intrinsic_items ?? 0 },
    { label: '已匹配病历', value: pool?.matched_items ?? 0 },
    { label: '可运行样本', value: pool?.ready_items ?? 0, help: 'running bundle 就绪' },
    {
      label: '最近任务',
      value: pool?.latest_job_id ? '已创建' : '暂无',
      help: pool?.latest_job_id || '',
    },
  ]
})

const paginationConfig = computed(() => ({
  current: pagination.value.page,
  pageSize: pagination.value.pageSize,
  total: pagination.value.total,
  showSizeChanger: true,
  showTotal: (total: number) => `共 ${total} 条`,
  onChange: (page: number, pageSize: number) => {
    pagination.value.page = page
    pagination.value.pageSize = pageSize
    loadItems()
  },
}))

const itemColumns: TableColumnsType<ManualSamplePoolItem> = [
  {
    title: '行号',
    dataIndex: 'row_no',
    width: 80,
  },
  {
    title: '患者 / 住院号',
    key: 'patient',
    width: 180,
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
    title: '人工问题',
    dataIndex: 'manual_issue_text',
    ellipsis: true,
  },
  {
    title: '覆盖类型',
    dataIndex: 'coverage_type',
    width: 120,
    customRender: ({ value }) => coverageLabel(String(value || '')),
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
    width: 110,
    customRender: ({ value }) => matchStatusLabel(String(value || '')),
  },
  {
    title: 'bundle',
    dataIndex: 'bundle_status',
    width: 100,
  },
  {
    title: '操作',
    key: 'actions',
    width: 180,
    fixed: 'right',
    customRender: ({ record }) =>
      h('div', { class: 'flex gap-2' }, [
        h(
          'a',
          {
            class: 'text-[#1677ff]',
            onClick: () => openItemDetail(record),
          },
          '查看详情',
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

function coverageLabel(value: string): string {
  if (value === 'llm_intrinsic') return '内涵问题'
  if (value === 'programmatic') return '程序化'
  if (value === 'unsupported') return '暂不支持'
  return value || '-'
}

function matchStatusLabel(value: string): string {
  if (value === 'matched') return '已匹配'
  if (value === 'ambiguous') return '匹配歧义'
  if (value === 'unmatched') return '未匹配'
  return value || '-'
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
    await loadItems()
  }
}

async function loadItems() {
  if (!selectedPoolId.value) {
    items.value = []
    return
  }
  itemLoading.value = true
  const result = await getManualSamplePoolItems(selectedPoolId.value, {
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
  items.value = result.data.items
  pagination.value.total = result.data.total
}

async function handlePoolChange() {
  pagination.value.page = 1
  selectedPool.value = pools.value.find((item) => item.id === selectedPoolId.value)
  await loadItems()
}

function resetFilters() {
  filters.value = {
    query: '',
    coverageType: undefined,
    matchStatus: undefined,
    includeInBatch: true,
  }
  pagination.value.page = 1
  loadItems()
}

function openItemDetail(record: ManualSamplePoolItem) {
  activeItem.value = record
  detailOpen.value = true
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

async function handleRunPool() {
  if (!selectedPoolId.value) return
  runLoading.value = true
  const result = await runManualSamplePool(selectedPoolId.value)
  runLoading.value = false
  if (!result.success || !result.data) {
    message.error(result.message || '创建样本验证任务失败')
    return
  }
  message.success(
    `已创建验证任务，覆盖 ${result.data.record_count} 份病历 / ${result.data.rule_count} 条规则`,
  )
  await loadPools()
  await openBatchJob(result.data.job_id)
}

async function openLatestJob() {
  if (!selectedPool.value?.latest_job_id) return
  await openBatchJob(selectedPool.value.latest_job_id)
}

async function openBatchJob(jobId: string) {
  batchJobLoading.value = true
  batchResultOpen.value = true
  const result = await getSichuanWorkspaceBatchJob(jobId)
  batchJobLoading.value = false
  if (!result.success || !result.data) {
    message.error(result.message || '获取任务详情失败')
    return
  }
  batchJobDetail.value = result.data
}

function closeBatchDrawer() {
  batchResultOpen.value = false
  batchJobDetail.value = undefined
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
</script>
