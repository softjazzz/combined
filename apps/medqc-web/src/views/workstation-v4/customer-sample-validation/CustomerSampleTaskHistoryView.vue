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
        <a-button :loading="loading" @click="loadJobs"> 刷新 </a-button>
      </div>
    </section>

    <section class="customer-task-history-filters">
      <input
        v-model.trim="query.keyword"
        class="customer-task-history-search"
        placeholder="搜索任务、病历号、质控点"
        @keyup.enter="handleSearch"
      />
      <select v-model="query.status" class="customer-task-history-select" @change="handleSearch">
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

    <section class="customer-task-history-table">
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
            <strong>{{ formatDateTime(job.created_at) || '未返回时间' }}</strong>
            <span>{{ getBatchJobStatusText(job.status) }}</span>
          </div>

          <div class="customer-task-history-scope">
            <strong>{{ taskRuleSetText(job) }}</strong>
            <span>{{ taskScopeText(job) }}</span>
            <span>{{ compactRuleIds(job) }}</span>
          </div>

          <div class="customer-task-history-records">
            <strong>{{ taskRecordText(job) }}</strong>
            <span>{{ taskResultCountText(job) }}</span>
          </div>

          <div class="customer-task-history-result">
            <strong>{{ taskOverviewText(job) }}</strong>
            <span v-if="taskIssueSummaryText(job)">
              {{ taskIssueSummaryText(job) }}
            </span>
            <div v-if="statusChips(job).length" class="customer-task-history-chips">
              <em v-for="chip in statusChips(job)" :key="chip.key" :class="chip.className">
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
      :batch-job-debug-snapshot="null"
      :batch-job-debug-loading="false"
      :close="closeResult"
      :export-batch-job-report="exportCurrentJob"
      :review-batch-job-result="reviewCurrentJob"
      :review-batch-job-loading="reviewingJobId === jobDetail?.id"
      :get-batch-job-status-tag-class="getBatchJobStatusTagClass"
      :get-batch-job-status-text="getBatchJobStatusText"
      :format-date-time="formatDateTime"
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
  listSichuanWorkspaceBatchJobs,
  reviewSichuanWorkspaceBatchJob,
} from '@/services/sichuan-rule-workspace-service'
import SemanticRulesBatchResultDrawer from '@/views/workstation-v4/semantic-rules/components/SemanticRulesBatchResultDrawer.vue'
import type {
  SichuanBatchJob,
  SichuanBatchJobStatus,
} from '@/views/workstation-v4/semantic-rules/types'
import { downloadBlob, normalizeBatchExportBlob } from './batchExport'

type StatusChip = {
  key: string
  label: string
  value: number
  className: string
}

const router = useRouter()
const loading = ref(false)
const loaded = ref(false)
const jobs = ref<SichuanBatchJob[]>([])
const total = ref(0)
const jobDetail = ref<SichuanBatchJob | null>(null)
const jobDetailLoading = ref(false)
const resultOpen = ref(false)
const reviewingJobId = ref('')

const query = reactive({
  keyword: '',
  status: '' as '' | SichuanBatchJobStatus,
  page: 1,
  pageSize: 20,
})

const attentionStatuses = new Set([
  'non_compliant',
  'ai_suggested_non_compliant',
  'data_gap',
  'uncertain',
  'not_executed',
  'technical_error',
])

const statusMeta: Record<string, { label: string; className: string }> = {
  non_compliant: { label: '不合规', className: 'is-danger' },
  ai_suggested_non_compliant: { label: 'AI判断', className: 'is-review' },
  ai_suggested_compliant: { label: 'AI未见问题', className: 'is-muted' },
  compliant: { label: '合规', className: 'is-success' },
  not_applicable: { label: '不适用', className: 'is-muted' },
  data_gap: { label: '数据不足', className: 'is-warning' },
  uncertain: { label: 'AI判断', className: 'is-review' },
  not_executed: { label: '未执行', className: 'is-muted' },
  technical_error: { label: '技术异常', className: 'is-danger' },
}

const briefByRuleId: Record<string, string> = {
  'LX0609-001': '入院记录未在24小时内完成',
  'LX0609-002': '首次病程记录时间超过8小时',
  'LX0609-003': '手术记录未在术后24小时内完成',
  'LX0609-005': '入院48小时内无主治医师首次查房记录',
  'LX0609-007': '病情稳定患者3天内无查房病程记录',
  'LX0609-008': '病重患者2天内无查房病程记录',
  'LX0609-009': '病危患者未每天记录查房病程',
  'LX0609-016': '首次病程与入院记录存在复制风险',
  'LX0609-017': '多次病程记录高度重复',
  'LX0609-018': '主诉不能导出第一诊断',
  'LX0609-020': '会诊后未记录会诊意见执行情况',
  'LX0609-021': '会诊申请目的不明确',
  'LX0609-022': '会诊意见不明确',
  'LX0609-023': '会诊执行记录不规范',
  'LX0609-041': '缺少输血知情同意书',
  'LX0609-049': '输血医嘱与收费不一致',
}

const currentJobId = computed(() => String(jobDetail.value?.id || '').trim())

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

function getBatchJobStatusText(status?: string): string {
  const normalized = String(status || '').toLowerCase()
  if (normalized === 'completed') return '已完成'
  if (normalized === 'running') return '执行中'
  if (normalized === 'queued') return '排队中'
  if (normalized === 'failed') return '失败'
  if (normalized === 'canceled') return '已取消'
  return '未知'
}

function getBatchJobStatusTagClass(status?: string): string {
  const normalized = String(status || '').toLowerCase()
  if (normalized === 'completed') return 'is-success'
  if (normalized === 'failed') return 'is-danger'
  if (normalized === 'canceled') return 'is-muted'
  if (normalized === 'running' || normalized === 'queued') return 'is-running'
  return 'is-muted'
}

function formatDateTime(value?: string | Date | null): string {
  if (!value) return ''
  const date = value instanceof Date ? value : new Date(value)
  if (Number.isNaN(date.getTime())) return String(value)
  const pad = (num: number) => String(num).padStart(2, '0')
  return `${date.getFullYear()}/${pad(date.getMonth() + 1)}/${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`
}

function taskRuleSetText(job: SichuanBatchJob): string {
  return String(job.rule_set_name || job.summary?.rule_set_name || job.rule_name || '质控任务')
}

function normalizeRuleIds(value: unknown): string[] {
  return Array.isArray(value)
    ? value.map((item) => String(item).trim()).filter((item) => /^LX0609-\d+/u.test(item))
    : []
}

function selectedRuleIds(job: SichuanBatchJob): string[] {
  const filters = job.filters && typeof job.filters === 'object' ? job.filters : {}
  const fromFilters = normalizeRuleIds(
    filters.scoped_customer_rule_ids || filters.selected_rule_ids || filters.rule_ids,
  )
  if (fromFilters.length) return fromFilters
  return normalizeRuleIds(job.draft_ids || job.draft_id)
}

function compactRuleIds(job: SichuanBatchJob): string {
  const ids = selectedRuleIds(job)
  const count = Number(
    job.customer_rule_count || job.summary?.customer_rule_count || ids.length || 0,
  )
  if (!ids.length) return count > 0 ? `${count} 个客户质控点` : '未返回质控点范围'
  const head = ids.slice(0, 3).join('、')
  const suffix = ids.length > 3 ? ` +${ids.length - 3}` : ''
  return `${count || ids.length} 个 LX0609 质控点：${head}${suffix}`
}

function taskScopeText(job: SichuanBatchJob): string {
  const ids = selectedRuleIds(job)
  if (ids.length) return '泸县0609 scoped run'
  const count = Number(job.customer_rule_count || job.summary?.customer_rule_count || 0)
  return count >= 49 ? '全量 0609 规则集' : '质控范围未完整返回'
}

function taskRecordText(job: SichuanBatchJob): string {
  const count = Number(
    job.summary?.total_records || job.total_records || job.record_ids?.length || 0,
  )
  return `${count || 0} 份病历`
}

function mergeStatusCounts(
  target: Record<string, number>,
  source: unknown,
): Record<string, number> {
  if (!source || typeof source !== 'object' || Array.isArray(source)) return target
  Object.entries(source as Record<string, unknown>).forEach(([key, value]) => {
    const count = Number(value || 0)
    if (Number.isFinite(count) && count > 0) {
      target[key] = count
    }
  })
  return target
}

function displayCounts(job: SichuanBatchJob): Record<string, number> {
  const summary = job.summary
  const counts: Record<string, number> = {}
  mergeStatusCounts(counts, summary?.display_status_counts)
  mergeStatusCounts(counts, summary?.status_breakdown)
  mergeStatusCounts(counts, summary?.result_aggregation?.status_breakdown)
  return counts
}

function statusChips(job: SichuanBatchJob): StatusChip[] {
  const counts = displayCounts(job)
  return Object.entries(statusMeta)
    .map(([key, meta]) => ({
      key,
      label: meta.label,
      value: Number(counts[key] || 0),
      className: meta.className,
    }))
    .filter((chip) => chip.value > 0)
}

function taskResultCount(job: SichuanBatchJob): number {
  const countSum = Object.values(displayCounts(job)).reduce(
    (sum, value) => sum + Number(value || 0),
    0,
  )
  if (countSum > 0) return countSum
  return Number(job.summary?.total_records || 0) * Number(job.customer_rule_count || 0)
}

function taskResultCountText(job: SichuanBatchJob): string {
  const count = taskResultCount(job)
  return count > 0 ? `${count} 条结果` : '结果数待返回'
}

function taskOverviewText(job: SichuanBatchJob): string {
  if (job.status === 'failed') return job.error_message || '任务失败'
  const chips = statusChips(job).filter((chip) => chip.key !== 'compliant')
  if (chips.length) {
    return `发现需关注结果：${chips.map((chip) => `${chip.label} ${chip.value}`).join('，')}`
  }
  const compliant = Number(displayCounts(job).compliant || 0)
  return compliant > 0 ? `合规 ${compliant}` : '暂无结果摘要'
}

function taskIssueSummaryText(job: SichuanBatchJob): string {
  const summaries = Array.isArray(job.summary?.history_issue_summaries)
    ? job.summary.history_issue_summaries
    : []
  const lines = summaries
    .slice(0, 4)
    .map((item) => {
      const ruleId = String(item.rule_id || '').trim()
      const text = String(item.text || briefByRuleId[ruleId] || '').trim()
      return ruleId && text ? `${ruleId} ${text}` : text
    })
    .filter(Boolean)
  if (lines.length) return `问题点：${lines.join('；')}`

  const items = (job.items || []).filter((item) => {
    const status = String(item.status || '').toLowerCase()
    return attentionStatuses.has(status)
  })
  const itemLines = items
    .slice(0, 4)
    .map((item) => {
      const ruleId = String(item.rule_code || item.rule_id || '').trim()
      const text = String(item.findings || item.rule_name || briefByRuleId[ruleId] || '').trim()
      return ruleId && text ? `${ruleId} ${text}` : text
    })
    .filter(Boolean)
  return itemLines.length ? `问题点：${itemLines.join('；')}` : ''
}

async function openJob(job: SichuanBatchJob) {
  resultOpen.value = true
  jobDetailLoading.value = true
  try {
    const result = await getSichuanWorkspaceBatchJob(job.id)
    if (!result.success || !result.data) {
      message.error(result.message || '获取任务详情失败')
      return
    }
    jobDetail.value = result.data
  } finally {
    jobDetailLoading.value = false
  }
}

function closeResult() {
  resultOpen.value = false
  jobDetail.value = null
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
  color: #0066cc;
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
  background: rgba(0, 102, 204, 0.025);
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
