<template>
  <div class="task-history mq-page">
    <section class="task-history__head mq-page-head">
      <div>
        <button
          type="button"
          class="task-history__back"
          @click="router.push({ name: 'WorkstationV4CustomerSampleValidation' })"
        >
          ← 返回客户样本验证
        </button>
        <h1 class="mq-page-title">质控记录</h1>
        <p class="task-history__desc">每次发起的样本质控任务，点开查看结果或导出报告。</p>
      </div>
      <div class="mq-page-head__actions">
        <a-button :loading="loading" @click="loadJobs"> 刷新 </a-button>
      </div>
    </section>

    <section class="task-history__filters mq-card">
      <input
        v-model.trim="query.keyword"
        class="task-history__search mq-input"
        placeholder="搜索任务名称或质控点"
        data-testid="task-history-search"
        @keyup.enter="handleSearch"
      />
      <div class="mq-segmented mq-segmented--sm task-history__status" role="tablist">
        <button
          v-for="option in STATUS_OPTIONS"
          :key="option.value"
          type="button"
          role="tab"
          class="mq-segmented__item"
          :class="{ 'is-active': query.status === option.value }"
          :aria-selected="query.status === option.value"
          :data-testid="`task-history-status-${option.value || 'all'}`"
          @click="selectStatus(option.value)"
        >
          {{ option.label }}
        </button>
      </div>
      <span class="task-history__total">共 {{ total }} 条</span>
    </section>

    <section class="task-history__list mq-card">
      <a-spin :spinning="loading">
        <div v-if="!jobs.length && loaded" class="task-history__empty">
          {{
            query.keyword || query.status ? '没有符合条件的质控任务。' : '还没有发起过质控任务。'
          }}
        </div>

        <template v-for="group in rowGroups" :key="group.key">
          <div class="task-history__date">
            {{ group.label }}
          </div>
          <article
            v-for="row in group.rows"
            :key="row.id"
            class="task-history__row"
            :data-testid="`task-history-row-${row.id}`"
          >
            <div class="task-history__main">
              <div class="task-history__title-line">
                <span class="mq-status" :class="statusClass(row.statusTone)">{{
                  row.statusLabel
                }}</span>
                <strong class="task-history__title" :title="row.title">{{ row.title }}</strong>
              </div>
              <span class="task-history__meta">{{ row.metaText }}</span>
            </div>

            <div class="task-history__result">
              <template v-if="row.isRunning">
                <span class="task-history__bar">
                  <span class="is-info" :style="{ width: `${row.progressPercent}%` }" />
                </span>
                <span class="task-history__sub">{{ row.progressText }}</span>
              </template>
              <template v-else>
                <span
                  v-if="row.detailText"
                  class="task-history__sub"
                  :class="{ 'is-warning': row.detailTone === 'warning' }"
                  >{{ row.detailText }}</span
                >
              </template>
            </div>

            <div class="task-history__actions">
              <a-button
                :type="row.isRunning ? 'default' : 'primary'"
                size="small"
                data-testid="task-history-open"
                @click="openJob(jobById(row.id))"
              >
                {{ row.isRunning ? '查看进度' : '查看结果' }}
              </a-button>
              <a-dropdown v-if="row.canExport" :trigger="['click']">
                <a-button
                  size="small"
                  :loading="reviewingJobId === row.id"
                  data-testid="task-history-more"
                >
                  更多
                </a-button>
                <template #overlay>
                  <a-menu @click="handleRowMenu(row.id, $event)">
                    <a-menu-item key="export" data-menu-key="export"> 导出质控报告 </a-menu-item>
                    <a-menu-item key="review" data-menu-key="review"> 复核本次结果 </a-menu-item>
                  </a-menu>
                </template>
              </a-dropdown>
            </div>
          </article>
        </template>
      </a-spin>
    </section>

    <section v-if="total > query.pageSize" class="task-history__pagination">
      <a-pagination
        :current="query.page"
        :page-size="query.pageSize"
        :total="total"
        :show-size-changer="false"
        show-quick-jumper
        :disabled="loading"
        @change="goPage"
      />
    </section>

    <SemanticRulesBatchResultDrawer
      :open="resultOpen"
      :batch-job-detail="jobDetail"
      :batch-job-detail-loading="jobDetailLoading"
      :batch-job-debug-snapshot="jobDebugSnapshot"
      :batch-job-debug-loading="jobDebugLoading"
      :fetch-batch-job-debug-snapshot="fetchJobDebugSnapshot"
      :close="closeResult"
      :export-batch-job-report="exportCurrentJob"
      :review-batch-job-result="reviewCurrentJob"
      :review-batch-job-loading="reviewingJobId === jobDetail?.id"
      :get-batch-job-status-tag-class="getBatchJobStatusClass"
      :get-batch-job-status-text="getBatchJobStatusText"
      :format-date-time="formatBatchJobDateTime"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { message } from 'ant-design-vue'
import { useRouter } from 'vue-router'
import {
  exportSichuanWorkspaceBatchJob,
  getSichuanWorkspaceBatchJob,
  getSichuanWorkspaceBatchJobDebugSnapshot,
  listSichuanWorkspaceBatchJobs,
  reviewSichuanWorkspaceBatchJob,
} from '@/services/sichuan-rule-workspace-service'
import SemanticRulesBatchResultDrawer from '@/views/workstation-v4/semantic-rules/components/SemanticRulesBatchResultDrawer.vue'
import type {
  SichuanBatchJob,
  SichuanBatchJobDebugSnapshot,
  SichuanBatchJobStatus,
} from '@/views/workstation-v4/semantic-rules/types'
import { downloadBlob, normalizeBatchExportBlob } from './batchExport'
import {
  formatBatchJobDateTime,
  getBatchJobStatusClass,
  getBatchJobStatusText,
} from './batchJobPresentation'
import {
  buildTaskHistoryRow,
  groupTaskHistoryRows,
  type TaskHistoryTone,
} from './taskHistoryPresentation'

const router = useRouter()
const loading = ref(false)
const loaded = ref(false)
const jobs = ref<SichuanBatchJob[]>([])
const total = ref(0)
const jobDetail = ref<SichuanBatchJob | null>(null)
const jobDetailLoading = ref(false)
const jobDebugSnapshot = ref<SichuanBatchJobDebugSnapshot | null>(null)
const jobDebugLoading = ref(false)
const resultOpen = ref(false)
const reviewingJobId = ref('')
let jobDebugRequestId = 0

const query = reactive({
  keyword: '',
  status: '' as '' | SichuanBatchJobStatus,
  page: 1,
  pageSize: 20,
})

const STATUS_OPTIONS: Array<{ value: '' | SichuanBatchJobStatus; label: string }> = [
  { value: '', label: '全部' },
  { value: 'running', label: '执行中' },
  { value: 'completed', label: '已完成' },
  { value: 'failed', label: '有失败' },
  { value: 'canceled', label: '已取消' },
]

const currentJobId = computed(() => String(jobDetail.value?.id || '').trim())
const rowGroups = computed(() => groupTaskHistoryRows(jobs.value.map(buildTaskHistoryRow)))

function jobById(id: string) {
  return jobs.value.find((job) => job.id === id) as SichuanBatchJob
}

function statusClass(tone: TaskHistoryTone) {
  return tone === 'neutral' ? '' : `mq-status--${tone}`
}

// 状态切换即查询，不再需要单独的“查询/重置”。
function selectStatus(status: '' | SichuanBatchJobStatus) {
  if (query.status === status) return
  query.status = status
  handleSearch()
}

function handleRowMenu(id: string, event: { key: string | number }) {
  const job = jobById(id)
  if (!job) return
  if (event.key === 'export') void exportJob(job)
  if (event.key === 'review') void reviewJob(job)
}

onMounted(() => {
  void loadJobs()
})

async function loadJobs() {
  loading.value = true
  try {
    const result = await listSichuanWorkspaceBatchJobs({
      view: 'overview',
      page: query.page,
      page_size: query.pageSize,
      q: query.keyword || undefined,
      status: query.status || undefined,
    })
    if (!result.success || !result.data) {
      message.error(result.message || '获取质控记录失败')
      return
    }
    jobs.value = result.data.items || []
    total.value = Number(result.data.total || jobs.value.length || 0)
    loaded.value = true
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  query.page = 1
  void loadJobs()
}

function goPage(page: number) {
  query.page = Math.max(1, page)
  void loadJobs()
}

async function openJob(job: SichuanBatchJob) {
  resultOpen.value = true
  jobDebugRequestId += 1
  jobDebugLoading.value = false
  jobDebugSnapshot.value = null
  jobDetailLoading.value = true
  try {
    const result = await getSichuanWorkspaceBatchJob(job.id)
    if (!result.success || !result.data) {
      message.error(result.message || '获取任务详情失败')
      return
    }
    jobDetail.value = result.data
    void fetchJobDebugSnapshot(job.id)
  } finally {
    jobDetailLoading.value = false
  }
}

async function fetchJobDebugSnapshot(
  jobId: string,
  options?: { ruleJobId?: string; itemLimit?: number },
) {
  const normalizedJobId = String(jobId || '').trim()
  if (!normalizedJobId) return null
  const requestId = ++jobDebugRequestId
  jobDebugLoading.value = true
  try {
    const result = await getSichuanWorkspaceBatchJobDebugSnapshot(normalizedJobId, {
      rule_job_id: options?.ruleJobId,
      item_limit: options?.itemLimit,
    })
    if (requestId !== jobDebugRequestId) return null
    if (!result.success || !result.data) {
      message.warning(result.message || '调试信息暂不可用，质控结果仍可正常查看')
      return null
    }
    jobDebugSnapshot.value = result.data
    return result.data
  } catch (error: any) {
    if (requestId === jobDebugRequestId) {
      message.warning(error?.message || '调试信息暂不可用，质控结果仍可正常查看')
    }
    return null
  } finally {
    if (requestId === jobDebugRequestId) {
      jobDebugLoading.value = false
    }
  }
}

function closeResult() {
  jobDebugRequestId += 1
  resultOpen.value = false
  jobDetail.value = null
  jobDebugSnapshot.value = null
  jobDebugLoading.value = false
}

async function exportById(jobId: string, format: 'xlsx' | 'csv' | 'html' = 'html') {
  if (!jobId) {
    message.warning('当前任务未加载完成，暂时无法导出')
    return
  }
  const result = await exportSichuanWorkspaceBatchJob({ job_id: jobId, format })
  if (!result.success || !result.data) {
    message.error(result.message || '导出质控明细失败')
    return
  }
  try {
    const blob = await normalizeBatchExportBlob(result.data, format)
    downloadBlob(blob, `manual-sample-validation-${jobId}.${format}`)
    message.success(format === 'html' ? 'HTML 质控明细已开始下载' : '质控报告已开始下载')
  } catch (error: any) {
    message.error(error?.message || '导出质控明细失败')
  }
}

async function exportJob(job: SichuanBatchJob) {
  await exportById(job.id, 'html')
}

async function exportCurrentJob(format: 'xlsx' | 'csv' | 'html' = 'html') {
  await exportById(currentJobId.value, format)
}

async function reviewJob(job: SichuanBatchJob): Promise<SichuanBatchJob | null> {
  reviewingJobId.value = job.id
  try {
    const result = await reviewSichuanWorkspaceBatchJob(job.id)
    if (!result.success || !result.data?.job) {
      message.error(result.message || '复核本次结果失败')
      return null
    }
    const updatedJob = result.data.job
    const index = jobs.value.findIndex((item) => item.id === updatedJob.id)
    if (index >= 0) jobs.value.splice(index, 1, updatedJob)
    if (jobDetail.value?.id === updatedJob.id) jobDetail.value = updatedJob
    const count = Number(result.data.review_report?.summary?.total_findings || 0)
    message.success(count > 0 ? `复核完成，发现 ${count} 条复核建议` : '复核完成，暂无高风险建议')
    return updatedJob
  } finally {
    reviewingJobId.value = ''
  }
}

async function reviewCurrentJob() {
  if (!jobDetail.value) return
  await reviewJob(jobDetail.value)
}
</script>

<style scoped src="../styles/task-history.css"></style>
