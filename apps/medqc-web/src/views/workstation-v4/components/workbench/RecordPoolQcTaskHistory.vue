<template>
  <a-button
    size="small"
    class="record-pool-task-history__entry"
    data-testid="record-pool-qc-task-history-entry"
    @click="openHistory"
  >
    <History
      :size="15"
      aria-hidden="true"
    />
    最近质控任务
  </a-button>

  <a-drawer
    :open="historyOpen"
    placement="right"
    :width="560"
    class="record-pool-task-history"
    root-class-name="record-pool-task-history-root"
    @close="closeHistory"
  >
    <template #title>
      <div class="record-pool-task-history__title">
        <span class="record-pool-task-history__title-icon"><History :size="18" /></span>
        <span>
          <strong>最近质控任务</strong>
          <small>病历池最近 10 次质控执行记录</small>
        </span>
      </div>
    </template>

    <div class="record-pool-task-history__toolbar">
      <span>{{
        confirmedResultsOnly
          ? '可查看最近质控任务的执行状态与结果汇总'
          : '可查看执行统计、调试快照并下载诊断包'
      }}</span>
      <a-button
        size="small"
        :loading="loading"
        @click="loadJobs"
      >
        <RefreshCw :size="14" />刷新
      </a-button>
    </div>

    <a-spin :spinning="loading">
      <a-empty
        v-if="!loading && !jobs.length"
        description="暂无病历池质控任务"
        class="record-pool-task-history__empty"
      />
      <div
        v-else
        class="record-pool-task-history__list"
      >
        <button
          v-for="job in jobs"
          :key="job.id"
          type="button"
          class="record-pool-task-history__item"
          :data-status="job.status"
          @click="openJob(job.id)"
        >
          <span class="record-pool-task-history__item-main">
            <span class="record-pool-task-history__item-heading">
              <strong>{{ job.rule_set_name || job.rule_name || '病历池质控任务' }}</strong>
              <em>{{ getBatchJobStatusText(job.status) }}</em>
            </span>
            <span class="record-pool-task-history__item-meta">
              <span>{{ scopeLabel(job.scope) }}</span>
              <span>{{ recordCount(job) }} 份病历</span>
              <span>{{ formatPaddedQcTaskDateTime(job.created_at) }}</span>
            </span>
            <span
              v-if="!confirmedResultsOnly"
              class="record-pool-task-history__item-metrics"
            >
              <span>墙钟耗时 {{ durationLabel(job) }}</span>
              <span>LLM {{ job.summary?.executor_breakdown?.llm || 0 }}</span>
              <span>缓存命中 {{ job.summary?.cache_breakdown?.hit || 0 }}</span>
            </span>
          </span>
          <ChevronRight
            :size="17"
            aria-hidden="true"
          />
        </button>
      </div>
    </a-spin>
  </a-drawer>

  <SemanticRulesBatchResultDrawer
    :open="detailOpen"
    :batch-job-detail="batchJobDetail"
    :batch-job-detail-loading="detailLoading"
    :batch-job-debug-snapshot="debugSnapshot"
    :batch-job-debug-loading="debugLoading"
    :fetch-batch-job-debug-snapshot="fetchDebugSnapshot"
    :close="closeDetail"
    :export-batch-job-report="exportReport"
    :review-batch-job-result="confirmedResultsOnly ? undefined : reviewBatchJob"
    :review-batch-job-loading="reviewLoading"
    :cancel-batch-job="cancelBatchJob"
    :cancel-batch-job-loading="cancelLoading"
    :get-batch-job-status-tag-class="getBatchJobStatusTagClass"
    :get-batch-job-status-text="getBatchJobStatusText"
    :format-date-time="formatPaddedQcTaskDateTime"
    back-label="返回病历池"
  />
</template>

<script setup lang="ts">
import { message } from 'ant-design-vue'
import { ChevronRight, History, RefreshCw } from 'lucide-vue-next'
import { onBeforeUnmount, ref } from 'vue'
import { useQcResultVisibility } from '@/composables/useQcResultVisibility'
import {
  cancelSichuanWorkspaceBatchJob,
  exportSichuanWorkspaceBatchJob,
  getSichuanWorkspaceBatchJob,
  getSichuanWorkspaceBatchJobDebugSnapshot,
  listSichuanWorkspaceBatchJobs,
  reviewSichuanWorkspaceBatchJob,
} from '@/services/sichuan-rule-workspace-service'
import { formatPaddedQcTaskDateTime } from '../../utils/qcTaskTime'
import SemanticRulesBatchResultDrawer from '../../semantic-rules/components/SemanticRulesBatchResultDrawer.vue'
import type { SichuanBatchJob, SichuanBatchJobDebugSnapshot } from '../../semantic-rules/types'
import {
  getBatchJobStatusTagClass,
  getBatchJobStatusText,
} from '../../customer-sample-validation/customerSampleValidationPresentation'
import {
  downloadBlob,
  normalizeBatchExportBlob,
} from '../../customer-sample-validation/batchExport'

const RECORD_POOL_RULE_SET_KEY = 'luxian_0609_qc_v1'
const { confirmedResultsOnly } = useQcResultVisibility()

const historyOpen = ref(false)
const detailOpen = ref(false)
const loading = ref(false)
const detailLoading = ref(false)
const debugLoading = ref(false)
const reviewLoading = ref(false)
const cancelLoading = ref(false)
const jobs = ref<SichuanBatchJob[]>([])
const batchJobDetail = ref<SichuanBatchJob | null>(null)
const debugSnapshot = ref<SichuanBatchJobDebugSnapshot | null>(null)
let loadJobsSequence = 0
let openJobSequence = 0
let debugSnapshotSequence = 0

const SAMPLE_VALIDATION_FILTER_SOURCES = new Set([
  'manual_problem_sample_pool',
  'manual_sample_formal_fast_screen_full',
])

function isSampleValidationJob(job: SichuanBatchJob): boolean {
  if (job.is_sample_validation === true) return true
  const taskOrigin = String(job.task_origin || '')
    .trim()
    .toLowerCase()
  if (taskOrigin === 'sample_validation') return true
  const filters = job.filters && typeof job.filters === 'object' ? job.filters : null
  if (filters) {
    if (String(filters.sample_pool_id || '').trim()) return true
    const source = String(filters.source || '')
      .trim()
      .toLowerCase()
    if (SAMPLE_VALIDATION_FILTER_SOURCES.has(source) || source.includes('sample_pool')) return true
  }
  return false
}

function isRecordPoolJob(job: SichuanBatchJob): boolean {
  if (isSampleValidationJob(job)) return false
  const ruleSetKey = String(job.rule_set_key || job.summary?.rule_set_key || '').trim()
  return ruleSetKey === RECORD_POOL_RULE_SET_KEY
}

async function loadJobs() {
  const requestSequence = ++loadJobsSequence
  loading.value = true
  try {
    const response = await listSichuanWorkspaceBatchJobs({
      page: 1,
      page_size: 30,
      exclude_validation: true,
    })
    if (requestSequence !== loadJobsSequence) return
    if (!response.success || !response.data) {
      throw new Error(response.message || '获取最近质控任务失败')
    }
    jobs.value = response.data.items.filter(isRecordPoolJob).slice(0, 10)
  } catch (error) {
    if (requestSequence !== loadJobsSequence) return
    jobs.value = []
    message.error(error instanceof Error ? error.message : '获取最近质控任务失败')
  } finally {
    if (requestSequence === loadJobsSequence) {
      loading.value = false
    }
  }
}

function openHistory() {
  historyOpen.value = true
  void loadJobs()
}

function closeHistory() {
  ++loadJobsSequence
  historyOpen.value = false
  loading.value = false
}

async function openJob(jobId: string) {
  const requestSequence = ++openJobSequence
  ++debugSnapshotSequence
  detailOpen.value = true
  detailLoading.value = true
  debugLoading.value = false
  batchJobDetail.value = null
  debugSnapshot.value = null
  try {
    const response = await getSichuanWorkspaceBatchJob(jobId)
    if (requestSequence !== openJobSequence || !detailOpen.value) return
    if (!response.success || !response.data) {
      throw new Error(response.message || '获取任务详情失败')
    }
    batchJobDetail.value = response.data
    if (!confirmedResultsOnly.value) {
      await fetchDebugSnapshot(jobId)
    }
  } catch (error) {
    if (requestSequence !== openJobSequence || !detailOpen.value) return
    batchJobDetail.value = null
    message.error(error instanceof Error ? error.message : '获取任务详情失败')
  } finally {
    if (requestSequence === openJobSequence) {
      detailLoading.value = false
    }
  }
}

async function fetchDebugSnapshot(
  jobId: string,
  options?: { ruleJobId?: string; itemLimit?: number },
): Promise<SichuanBatchJobDebugSnapshot | null> {
  if (confirmedResultsOnly.value) return null
  const requestSequence = ++debugSnapshotSequence
  debugLoading.value = true
  try {
    const response = await getSichuanWorkspaceBatchJobDebugSnapshot(jobId, {
      rule_job_id: options?.ruleJobId,
      item_limit: options?.itemLimit,
    })
    if (requestSequence !== debugSnapshotSequence || !detailOpen.value) return null
    if (!response.success || !response.data) return null
    debugSnapshot.value = response.data
    return response.data
  } finally {
    if (requestSequence === debugSnapshotSequence) {
      debugLoading.value = false
    }
  }
}

function closeDetail() {
  ++openJobSequence
  ++debugSnapshotSequence
  detailOpen.value = false
  detailLoading.value = false
  debugLoading.value = false
  batchJobDetail.value = null
  debugSnapshot.value = null
}

onBeforeUnmount(() => {
  ++loadJobsSequence
  ++openJobSequence
  ++debugSnapshotSequence
})

async function exportReport(format: 'xlsx' | 'csv' | 'html' = 'html') {
  const job = batchJobDetail.value
  if (!job) return
  try {
    const response = await exportSichuanWorkspaceBatchJob({ job_id: job.id, format })
    if (!response.success || !response.data) {
      throw new Error(response.message || '导出任务报告失败')
    }
    const blob = await normalizeBatchExportBlob(response.data, format)
    downloadBlob(blob, `病历池质控任务_${job.id}.${format}`)
  } catch (error) {
    message.error(error instanceof Error ? error.message : '导出任务报告失败')
  }
}

async function reviewBatchJob() {
  const job = batchJobDetail.value
  if (!job?.id || reviewLoading.value) return
  reviewLoading.value = true
  try {
    const response = await reviewSichuanWorkspaceBatchJob(job.id)
    if (!response.success || !response.data?.job) {
      message.error(response.message || '复核本次结果失败')
      return
    }
    const updatedJob = response.data.job
    if (batchJobDetail.value?.id === updatedJob.id) {
      batchJobDetail.value = updatedJob
    }
    jobs.value = jobs.value.map((item) =>
      item.id === updatedJob.id ? { ...item, ...updatedJob } : item,
    )
    const count = Number(response.data.review_report?.summary?.total_findings || 0)
    message.success(count > 0 ? `复核完成，发现 ${count} 条复核建议` : '复核完成，暂无高风险建议')
  } catch (error) {
    message.error(error instanceof Error ? error.message : '复核本次结果失败')
  } finally {
    reviewLoading.value = false
  }
}

async function cancelBatchJob(jobId: string) {
  if (!jobId || cancelLoading.value) return
  cancelLoading.value = true
  try {
    const response = await cancelSichuanWorkspaceBatchJob(jobId)
    if (!response.success || !response.data) {
      throw new Error(response.message || '停止批量任务失败')
    }
    if (batchJobDetail.value?.id === response.data.id) {
      batchJobDetail.value = {
        ...batchJobDetail.value,
        ...response.data,
      }
    }
    await loadJobs()
    if (detailOpen.value && batchJobDetail.value?.id === jobId) {
      const detailResponse = await getSichuanWorkspaceBatchJob(jobId)
      if (detailOpen.value && detailResponse.success && detailResponse.data?.id === jobId) {
        batchJobDetail.value = detailResponse.data
      }
    }
    message.success('批量任务已停止')
  } catch (error) {
    message.error(error instanceof Error ? error.message : '停止批量任务失败')
  } finally {
    cancelLoading.value = false
  }
}

function scopeLabel(scope: SichuanBatchJob['scope']): string {
  if (scope === 'running') return '运行病历'
  if (scope === 'final') return '终末病历'
  return '全部病历'
}

function recordCount(job: SichuanBatchJob): number {
  return Math.max(0, Number(job.total_records ?? job.summary?.total_records ?? 0) || 0)
}

function durationLabel(job: SichuanBatchJob): string {
  const seconds = Number(job.wall_clock_time ?? job.summary?.wall_clock_time ?? 0)
  if (!Number.isFinite(seconds) || seconds <= 0) return '—'
  if (seconds < 60) return `${seconds.toFixed(1)} 秒`
  return `${Math.floor(seconds / 60)} 分 ${Math.round(seconds % 60)} 秒`
}
</script>

<style scoped>
.record-pool-task-history__entry {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 32px;
  border-color: rgba(0, 0, 0, 0.08);
  border-radius: 8px;
  color: rgba(29, 29, 31, 0.68);
  font-size: 14px;
  font-weight: 400;
}
.record-pool-task-history__entry:hover {
  border-color: rgba(10, 108, 255, 0.24);
  color: #0a6cff;
}
.record-pool-task-history__title {
  display: flex;
  align-items: center;
  gap: 10px;
}
.record-pool-task-history__title-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  border-radius: 10px;
  color: #0a6cff;
  background: rgba(10, 108, 255, 0.09);
}
.record-pool-task-history__title span:last-child {
  display: grid;
  gap: 2px;
}
.record-pool-task-history__title strong {
  color: #1d1d1f;
  font-size: 17px;
  font-weight: 600;
}
.record-pool-task-history__title small {
  color: rgba(29, 29, 31, 0.48);
  font-size: 12px;
  font-weight: 400;
}
.record-pool-task-history__toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
  padding: 10px 12px;
  border: 1px solid rgba(0, 0, 0, 0.06);
  border-radius: 10px;
  background: rgba(245, 247, 250, 0.82);
  color: rgba(29, 29, 31, 0.52);
  font-size: 13px;
}
.record-pool-task-history__toolbar :deep(.ant-btn) {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  border-radius: 8px;
}
.record-pool-task-history__list {
  display: grid;
  gap: 10px;
}
.record-pool-task-history__item {
  display: flex;
  width: 100%;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  padding: 14px 15px;
  border: 1px solid rgba(0, 0, 0, 0.07);
  border-radius: 12px;
  background: #fff;
  color: #1d1d1f;
  text-align: left;
  cursor: pointer;
  transition: 180ms ease;
}
.record-pool-task-history__item:hover {
  border-color: rgba(10, 108, 255, 0.22);
  background: rgba(10, 108, 255, 0.025);
}
.record-pool-task-history__item > svg {
  flex: none;
  color: rgba(29, 29, 31, 0.32);
}
.record-pool-task-history__item-main {
  display: grid;
  min-width: 0;
  flex: 1;
  gap: 8px;
}
.record-pool-task-history__item-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}
.record-pool-task-history__item-heading strong {
  overflow: hidden;
  color: #283548;
  font-size: 14px;
  font-weight: 600;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.record-pool-task-history__item-heading em {
  flex: none;
  padding: 2px 7px;
  border-radius: 999px;
  background: rgba(10, 108, 255, 0.08);
  color: #0a6cff;
  font-size: 12px;
  font-style: normal;
  font-weight: 500;
}
.record-pool-task-history__item[data-status='failed'] .record-pool-task-history__item-heading em {
  color: #c62828;
  background: rgba(239, 68, 68, 0.08);
}
.record-pool-task-history__item-meta,
.record-pool-task-history__item-metrics {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 12px;
  color: rgba(29, 29, 31, 0.52);
  font-size: 12px;
  font-weight: 400;
}
.record-pool-task-history__item-metrics {
  color: rgba(29, 29, 31, 0.66);
}
.record-pool-task-history__empty {
  padding: 72px 0;
}
</style>

<style>
.record-pool-task-history-root .ant-drawer-content {
  background: rgba(248, 250, 252, 0.96);
  backdrop-filter: blur(20px) saturate(125%);
  -webkit-backdrop-filter: blur(20px) saturate(125%);
}
.record-pool-task-history-root .ant-drawer-header {
  border-bottom-color: rgba(0, 0, 0, 0.06);
}
</style>
