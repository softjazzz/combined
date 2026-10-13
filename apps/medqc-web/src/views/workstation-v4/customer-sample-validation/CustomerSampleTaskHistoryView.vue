<template>
  <div class="customer-task-history-page mq-page">
    <section class="customer-task-history-hero mq-page-head">
      <div>
        <button
          type="button"
          class="customer-task-history-back"
          @click="router.push({ name: 'WorkstationV4CustomerSampleValidation' })"
        >
          ← 返回客户样本验证
        </button>
        <h1 class="mq-page-title">质控记录</h1>
        <p>
          集中查看客户样本验证历史任务，支持按状态、病历或质控点检索，并可直接查看结果和导出 HTML
          明细。
        </p>
      </div>
      <div class="customer-task-history-hero-actions mq-page-head__actions">
        <a-button :loading="loading" @click="loadJobs"> 刷新 </a-button>
      </div>
    </section>

    <section class="customer-task-history-filters mq-card">
      <input
        v-model.trim="query.keyword"
        class="customer-task-history-search mq-input"
        placeholder="搜索任务、病历号、质控点"
        @keyup.enter="handleSearch"
      />
      <select
        v-model="query.status"
        class="customer-task-history-select mq-input"
        @change="handleSearch"
      >
        <option value="">全部状态</option>
        <option value="running">执行中</option>
        <option value="queued">排队中</option>
        <option value="completed">已完成</option>
        <option value="failed">失败</option>
        <option value="canceled">已取消</option>
      </select>
      <a-button type="primary" :loading="loading" @click="handleSearch"> 查询 </a-button>
      <a-button @click="resetFilters"> 重置 </a-button>
      <span class="customer-task-history-total">共 {{ total }} 条任务</span>
    </section>

    <section class="customer-task-history-table mq-card">
      <div class="customer-task-history-head-row">
        <span>发起时间</span>
        <span>任务与范围</span>
        <span>病历</span>
        <span>结果摘要</span>
        <span>操作</span>
      </div>

      <a-spin :spinning="loading">
        <div v-if="!jobs.length && loaded" class="customer-task-history-empty">
          暂无符合条件的质控记录。
        </div>

        <article v-for="job in jobs" :key="job.id" class="customer-task-history-row">
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
            <a-button size="small" @click="openJob(job)"> 查看结果 </a-button>
            <a-button
              v-if="job.status === 'completed'"
              size="small"
              :loading="reviewingJobId === job.id"
              @click="reviewJob(job)"
            >
              复核
            </a-button>
            <a-button v-if="job.status === 'completed'" size="small" @click="exportJob(job)">
              导出HTML
            </a-button>
          </div>
        </article>
      </a-spin>
    </section>

    <section class="customer-task-history-pagination">
      <a-button :disabled="query.page <= 1 || loading" @click="goPage(query.page - 1)">
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

<style scoped src="../styles/task-history.css"></style>
