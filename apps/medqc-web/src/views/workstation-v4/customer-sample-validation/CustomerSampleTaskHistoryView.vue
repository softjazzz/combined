<template>
  <div class="customer-task-history-page">
    <section class="customer-task-history-hero">
      <div>
        <button
          type="button"
          class="customer-task-history-back"
          @click="router.push({ name: 'WorkstationV4CustomerSampleValidation' })"
        >
          ← 返回客户样本验证
        </button>
        <h1>质控记录</h1>
        <p>
          集中查看客户样本验证历史任务，支持按状态、病历或质控点检索，并可直接查看结果和导出 HTML
          明细。
        </p>
      </div>
      <div class="customer-task-history-hero-actions">
        <a-button
          :loading="loading"
          @click="loadJobs"
        >
          刷新
        </a-button>
      </div>
    </section>

    <section class="customer-task-history-filters">
      <input
        v-model.trim="query.keyword"
        class="customer-task-history-search"
        placeholder="搜索任务、病历号、质控点"
        @keyup.enter="handleSearch"
      >
      <select
        v-model="query.status"
        class="customer-task-history-select"
        @change="handleSearch"
      >
        <option value="">
          全部状态
        </option>
        <option value="running">
          执行中
        </option>
        <option value="queued">
          排队中
        </option>
        <option value="completed">
          已完成
        </option>
        <option value="failed">
          失败
        </option>
        <option value="canceled">
          已取消
        </option>
      </select>
      <a-button
        type="primary"
        :loading="loading"
        @click="handleSearch"
      >
        查询
      </a-button>
      <a-button @click="resetFilters">
        重置
      </a-button>
      <span class="customer-task-history-total">共 {{ total }} 条任务</span>
    </section>

    <section class="customer-task-history-table">
      <div class="customer-task-history-head-row">
        <span>发起时间</span>
        <span>任务与范围</span>
        <span>病历</span>
        <span>结果摘要</span>
        <span>操作</span>
      </div>

      <a-spin :spinning="loading">
        <div
          v-if="!jobs.length && loaded"
          class="customer-task-history-empty"
        >
          暂无符合条件的质控记录。
        </div>

        <article
          v-for="job in jobs"
          :key="job.id"
          class="customer-task-history-row"
        >
          <div class="customer-task-history-time">
            <strong>{{ taskPresentation(job).createdText }}</strong>
            <span>{{ taskPresentation(job).statusLabel }}</span>
          </div>

          <div class="customer-task-history-scope">
            <strong>{{ taskPresentation(job).ruleSetText }}</strong>
            <span>{{ taskPresentation(job).scopeText }}</span>
            <span>{{ taskPresentation(job).compactRuleIdsText }}</span>
          </div>

          <div class="customer-task-history-records">
            <strong>{{ taskPresentation(job).recordText }}</strong>
            <span>{{ taskPresentation(job).resultCountText }}</span>
          </div>

          <div class="customer-task-history-result">
            <strong>{{ taskPresentation(job).overviewText }}</strong>
            <span v-if="taskPresentation(job).issueSummaryText">
              {{ taskPresentation(job).issueSummaryText }}
            </span>
            <div
              v-if="taskPresentation(job).statusChips.length"
              class="customer-task-history-chips"
            >
              <em
                v-for="chip in taskPresentation(job).statusChips"
                :key="chip.key"
                :class="chip.className"
              >
                {{ chip.label }} {{ chip.value }}
              </em>
            </div>
          </div>

          <div class="customer-task-history-actions">
            <a-button
              size="small"
              @click="openJob(job)"
            >
              查看结果
            </a-button>
            <a-button
              v-if="job.status === 'completed'"
              size="small"
              :loading="reviewingJobId === job.id"
              @click="reviewJob(job)"
            >
              复核
            </a-button>
            <a-button
              v-if="job.status === 'completed'"
              size="small"
              @click="exportJob(job)"
            >
              导出HTML
            </a-button>
          </div>
        </article>
      </a-spin>
    </section>

    <section class="customer-task-history-pagination">
      <a-button
        :disabled="query.page <= 1 || loading"
        @click="goPage(query.page - 1)"
      >
        上一页
      </a-button>
      <span>第 {{ query.page }} 页</span>
      <a-button
        :disabled="query.page * query.pageSize >= total || loading"
        @click="goPage(query.page + 1)"
      >
        下一页
      </a-button>
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
  buildBatchJobPresentation,
  formatBatchJobDateTime,
  getBatchJobStatusClass,
  getBatchJobStatusText,
} from './batchJobPresentation'

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

const currentJobId = computed(() => String(jobDetail.value?.id || '').trim())
const jobPresentations = computed(
  () => new Map(jobs.value.map((job) => [job.id, buildBatchJobPresentation(job)])),
)

function taskPresentation(job: SichuanBatchJob) {
  return jobPresentations.value.get(job.id) || buildBatchJobPresentation(job)
}

onMounted(() => {
  void loadJobs()
})

async function loadJobs() {
  loading.value = true
  try {
    const result = await listSichuanWorkspaceBatchJobs({
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

function resetFilters() {
  query.keyword = ''
  query.status = ''
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

<style scoped>
.customer-task-history-page {
  box-sizing: border-box;
  width: 100%;
  max-width: 100%;
  min-height: 100%;
  overflow-x: hidden;
  padding: 22px;
  color: #1d1d1f;
}

.customer-task-history-hero,
.customer-task-history-filters,
.customer-task-history-table {
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.88);
  box-shadow:
    0 1px 2px rgba(0, 0, 0, 0.04),
    0 10px 26px rgba(15, 23, 42, 0.06);
}

.customer-task-history-hero {
  display: flex;
  justify-content: space-between;
  gap: 18px;
  padding: 22px;
}

.customer-task-history-back {
  border: 0;
  background: transparent;
  color: #0a6cff;
  cursor: pointer;
  font-size: 13px;
  font-weight: 700;
  padding: 0;
}

.customer-task-history-hero h1 {
  margin: 12px 0 8px;
  font-size: 28px;
  font-weight: 750;
  line-height: 34px;
}

.customer-task-history-hero p {
  margin: 0;
  color: rgba(29, 29, 31, 0.58);
  font-size: 14px;
  line-height: 22px;
}

.customer-task-history-hero-actions {
  flex-shrink: 0;
}

.customer-task-history-filters {
  margin-top: 14px;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px;
}

.customer-task-history-search,
.customer-task-history-select {
  height: 36px;
  border: 1px solid rgba(0, 0, 0, 0.1);
  border-radius: 9px;
  background: #fff;
  color: #1d1d1f;
  font-size: 13px;
  outline: none;
  padding: 0 12px;
}

.customer-task-history-search {
  min-width: 280px;
  flex: 1;
}

.customer-task-history-select {
  min-width: 132px;
}

.customer-task-history-total {
  margin-left: auto;
  color: rgba(29, 29, 31, 0.54);
  font-size: 13px;
  font-weight: 650;
}

.customer-task-history-table {
  margin-top: 14px;
  overflow: hidden;
  width: 100%;
  max-width: 100%;
}

.customer-task-history-head-row,
.customer-task-history-row {
  display: grid;
  grid-template-columns:
    minmax(142px, 0.72fr)
    minmax(220px, 1.08fr)
    minmax(92px, 0.5fr)
    minmax(280px, 1.7fr)
    minmax(128px, 142px);
  gap: 12px;
  align-items: center;
  min-width: 0;
}

.customer-task-history-head-row {
  min-height: 48px;
  background: rgba(248, 250, 252, 0.92);
  padding: 0 18px;
  color: rgba(29, 29, 31, 0.42);
  font-size: 12px;
  font-weight: 700;
}

.customer-task-history-row {
  border-top: 1px solid rgba(0, 0, 0, 0.06);
  padding: 16px 18px;
  min-width: 0;
}

.customer-task-history-row:hover {
  background: rgba(10, 108, 255, 0.025);
}

.customer-task-history-time,
.customer-task-history-scope,
.customer-task-history-records,
.customer-task-history-result {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.customer-task-history-time strong,
.customer-task-history-scope strong,
.customer-task-history-records strong,
.customer-task-history-result strong {
  color: #1d1d1f;
  font-size: 14px;
  font-weight: 750;
  line-height: 20px;
}

.customer-task-history-time span,
.customer-task-history-scope span,
.customer-task-history-records span,
.customer-task-history-result span {
  color: rgba(29, 29, 31, 0.58);
  font-size: 12px;
  font-weight: 600;
  line-height: 18px;
  overflow-wrap: anywhere;
  word-break: break-word;
}

.customer-task-history-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.customer-task-history-chips em {
  border-radius: 999px;
  font-size: 12px;
  font-style: normal;
  font-weight: 700;
  line-height: 18px;
  padding: 3px 8px;
}

.customer-task-history-chips .is-danger {
  background: rgba(239, 68, 68, 0.08);
  color: #b91c1c;
}

.customer-task-history-chips .is-warning {
  background: rgba(245, 158, 11, 0.1);
  color: #b45309;
}

.customer-task-history-chips .is-review {
  background: rgba(124, 58, 237, 0.09);
  color: #6d28d9;
}

.customer-task-history-chips .is-success {
  background: rgba(16, 185, 129, 0.08);
  color: #047857;
}

.customer-task-history-chips .is-muted {
  background: rgba(0, 0, 0, 0.05);
  color: rgba(29, 29, 31, 0.58);
}

.customer-task-history-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: flex-end;
  min-width: 0;
}

.customer-task-history-actions :deep(.ant-btn) {
  border-radius: 8px;
  min-width: 62px;
  padding-inline: 10px;
}

.customer-task-history-empty {
  padding: 46px 20px;
  text-align: center;
  color: rgba(29, 29, 31, 0.5);
  font-size: 14px;
}

.customer-task-history-pagination {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 14px;
  color: rgba(29, 29, 31, 0.58);
  font-size: 13px;
}

@media (max-width: 1180px) {
  .customer-task-history-head-row {
    display: none;
  }

  .customer-task-history-row {
    grid-template-columns: 1fr;
  }

  .customer-task-history-actions {
    justify-content: flex-start;
  }

  .customer-task-history-filters {
    align-items: stretch;
    flex-direction: column;
  }

  .customer-task-history-total {
    margin-left: 0;
  }
}
</style>
