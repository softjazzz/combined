<template>
  <a-drawer
    :open="open"
    placement="right"
    :width="640"
    :closable="false"
    :body-style="{ padding: 0 }"
    @close="close"
  >
    <div class="drawer-shell">
      <div class="drawer-head">
        <div>
          <p class="drawer-eyebrow">
            批量任务结果
          </p>
          <h2 class="drawer-title">
            任务详情
          </h2>
        </div>
        <div class="drawer-actions">
          <a-button
            v-if="batchJobDetail?.status === 'completed'"
            :loading="batchJobDetailLoading"
            @click="exportBatchJobReport('xlsx')"
          >
            导出报告
          </a-button>
          <a-button
            type="text"
            @click="close"
          >
            关闭
          </a-button>
        </div>
      </div>

      <div class="drawer-body">
        <div
          v-if="batchJobDetail"
          class="drawer-card"
        >
          <div class="drawer-card-top">
            <div>
              <div class="drawer-rule-name">
                {{ batchJobDetail.rule_name || batchJobDetail.rule_code }}
              </div>
              <div class="drawer-meta">
                {{ scopeLabelMap[batchJobDetail.scope] || batchJobDetail.scope }} ·
                {{ formatDateTime(batchJobDetail.created_at) }}
              </div>
            </div>
            <a-tag :class="getBatchJobStatusTagClass(batchJobDetail.status)">
              {{ getBatchJobStatusText(batchJobDetail.status) }}
            </a-tag>
          </div>
          <div
            v-if="batchJobDetail.error_message"
            class="drawer-error"
          >
            {{ batchJobDetail.error_message }}
          </div>
        </div>

        <div class="drawer-summary summary-grid-primary">
          <div
            v-for="item in primarySummaryCards"
            :key="item.key"
            class="summary-card"
          >
            <div class="summary-label">
              {{ item.label }}
            </div>
            <div class="summary-value">
              {{ item.value }}
            </div>
            <div
              v-if="item.desc"
              class="summary-desc"
            >
              {{ item.desc }}
            </div>
          </div>
        </div>

        <div
          v-if="executionSummary"
          class="drawer-summary summary-grid-secondary"
        >
          <div
            v-for="item in executionSummaryCards"
            :key="item.key"
            class="summary-card"
          >
            <div class="summary-label">
              {{ item.label }}
            </div>
            <div class="summary-value">
              {{ item.value }}
            </div>
          </div>
        </div>

        <div
          v-if="resultAggregation"
          class="drawer-card"
        >
          <div class="drawer-section-head">
            <div class="drawer-section-title">
              结果聚合
            </div>
            <div class="drawer-section-meta">
              簇数 {{ resultAggregation.cluster_count || 0 }} · 重复命中
              {{ resultAggregation.duplicate_hits || 0 }}
            </div>
          </div>
          <div
            v-if="aggregationBreakdownSections.length"
            class="aggregation-breakdown-grid"
          >
            <div
              v-for="section in aggregationBreakdownSections"
              :key="section.key"
              class="aggregation-breakdown-card"
            >
              <div class="aggregation-breakdown-head">
                <div class="aggregation-breakdown-title">
                  {{ section.title }}
                </div>
                <div class="aggregation-breakdown-count">
                  {{ section.total }}
                </div>
              </div>
              <div
                v-if="section.items.length"
                class="aggregation-breakdown-items"
              >
                <div
                  v-for="item in section.items"
                  :key="`${section.key}-${item.label}`"
                  class="aggregation-breakdown-item"
                >
                  <span class="aggregation-breakdown-item-label">{{ item.label }}</span>
                  <a-tag class="aggregation-breakdown-item-tag">
                    {{ item.count }}
                  </a-tag>
                </div>
              </div>
              <div
                v-else
                class="aggregation-breakdown-empty"
              >
                暂无分解数据
              </div>
            </div>
          </div>
          <div class="aggregation-list">
            <div
              v-for="cluster in topAggregationClusters"
              :key="cluster.cluster_key"
              class="aggregation-item"
              :class="{ active: selectedClusterKey === cluster.cluster_key }"
              @click="toggleClusterFilter(cluster.cluster_key)"
            >
              <div class="aggregation-item-head">
                <span class="aggregation-item-title">{{ cluster.cluster_key }}</span>
                <a-tag class="aggregation-count-tag">
                  {{ cluster.records || 0 }} 次
                </a-tag>
              </div>
              <div
                v-if="cluster.sample_evidence"
                class="aggregation-evidence"
              >
                {{ cluster.sample_evidence }}
              </div>
              <div class="aggregation-meta">
                病历 {{ cluster.records || 0 }} 条 · 规则 {{ cluster.rules?.length || 0 }} 条
              </div>
            </div>
          </div>
          <div
            v-if="selectedClusterKey"
            class="aggregation-active-tip"
          >
            已按聚合簇过滤：{{ selectedClusterKey }}
            <a-button
              type="link"
              size="small"
              @click.stop="clearClusterFilter"
            >
              清除
            </a-button>
          </div>
        </div>

        <div
          v-if="batchJobDebugSnapshot"
          class="drawer-card"
        >
          <div class="drawer-section-head">
            <div class="drawer-section-title">
              执行调试快照
            </div>
            <div class="debug-toolbar">
              <a-select
                :value="selectedDebugRuleJobId || undefined"
                allow-clear
                placeholder="按规则筛选调试快照"
                class="debug-rule-select"
                :options="debugRuleOptions"
                :loading="batchJobDebugLoading"
                @change="handleDebugRuleChange"
              />
              <div class="drawer-section-meta">
                {{ batchJobDebugSnapshot.status }} ·
                {{ batchJobDebugSnapshot.execution_mode || 'unknown' }}
              </div>
            </div>
          </div>
          <div class="debug-current-rule">
            <div class="debug-current-rule-main">
              <span class="debug-current-rule-label">当前规则</span>
              <span class="debug-current-rule-value">
                {{
                  batchJobDebugSnapshot.current_rule?.rule_code ||
                    currentDebugRule?.rule_code ||
                    '未定位'
                }}
              </span>
            </div>
            <div class="debug-current-rule-sub">
              {{
                batchJobDebugSnapshot.current_rule?.rule_name ||
                  currentDebugRule?.rule_name ||
                  '暂无规则名称'
              }}
            </div>
          </div>
          <div class="debug-meta-grid">
            <div class="debug-meta-item">
              <span class="debug-meta-label">规则总数</span>
              <span class="debug-meta-value">{{ batchJobDebugSnapshot.rule_count || 0 }}</span>
            </div>
            <div class="debug-meta-item">
              <span class="debug-meta-label">筛选规则</span>
              <span class="debug-meta-value">{{
                batchJobDebugSnapshot.filtered_rule_count || 0
              }}</span>
            </div>
            <div class="debug-meta-item">
              <span class="debug-meta-label">更新时间</span>
              <span class="debug-meta-value">{{
                formatDateTime(batchJobDebugSnapshot.updated_at)
              }}</span>
            </div>
            <div class="debug-meta-item">
              <span class="debug-meta-label">任务状态</span>
              <span class="debug-meta-value">{{ batchJobDebugSnapshot.status }}</span>
            </div>
          </div>
          <div
            v-if="debugProgressEntries.length"
            class="debug-pill-block"
          >
            <div class="debug-pill-title">
              current_rule.progress
            </div>
            <div class="debug-pill-list">
              <span
                v-for="item in debugProgressEntries"
                :key="`progress-${item.label}`"
                class="debug-pill"
              >
                {{ item.label }}: {{ item.value }}
              </span>
            </div>
          </div>
          <div
            v-if="debugDetailEntries.length"
            class="debug-pill-block"
          >
            <div class="debug-pill-title">
              current_rule.debug
            </div>
            <div class="debug-pill-list">
              <span
                v-for="item in debugDetailEntries"
                :key="`debug-${item.label}`"
                class="debug-pill debug-pill-muted"
              >
                {{ item.label }}: {{ item.value }}
              </span>
            </div>
          </div>
        </div>

        <div class="drawer-card">
          <div class="drawer-section-head">
            <div class="drawer-section-title">
              规则结果概览
            </div>
            <div
              v-if="activeRuleFilterLabel"
              class="drawer-section-meta"
            >
              已按规则过滤：{{ activeRuleFilterLabel }}
            </div>
          </div>
          <a-table
            :columns="ruleColumns"
            :data-source="displayRuleResults"
            row-key="id"
            size="small"
            :pagination="false"
          />
        </div>

        <div class="drawer-card">
          <div class="drawer-section-head">
            <div class="drawer-section-title">
              命中明细（含版本与证据来源）
            </div>
            <div
              v-if="activeRuleFilterLabel"
              class="drawer-section-meta"
            >
              已按规则过滤：{{ activeRuleFilterLabel }}
            </div>
          </div>
          <div
            v-if="selectedClusterKey || activeRuleFilterLabel"
            class="aggregation-active-tip"
          >
            <span v-if="selectedClusterKey">聚合簇：{{ selectedClusterKey }}</span>
            <span v-if="selectedClusterKey && activeRuleFilterLabel">·</span>
            <span v-if="activeRuleFilterLabel">规则：{{ activeRuleFilterLabel }}</span>
            <a-button
              v-if="selectedClusterKey"
              type="link"
              size="small"
              @click.stop="clearClusterFilter"
            >
              清除聚合过滤
            </a-button>
            <a-button
              v-if="activeRuleFilterLabel"
              type="link"
              size="small"
              @click.stop="handleDebugRuleChange(undefined)"
            >
              清除规则过滤
            </a-button>
          </div>
          <a-table
            :columns="issueColumns"
            class="batch-issue-table"
            :data-source="displayIssueItems"
            :row-key="resolveIssueStableKey"
            size="small"
            :scroll="{ x: 980 }"
            :pagination="issuePagination"
            :row-class-name="resolveIssueRowClassName"
            @change="handleIssueTableChange"
          />
        </div>
      </div>
    </div>
  </a-drawer>
</template>

<script setup lang="ts">
import { computed, nextTick, reactive, ref, watch } from 'vue'
import type {
  SichuanBatchIssueItem,
  SichuanBatchJobDebugSnapshot,
  SichuanBatchJob,
  SichuanBatchResultAggregation,
} from '@/views/workstation-v4/semantic-rules/types'

const props = defineProps<{
  open: boolean
  batchJobDetail: SichuanBatchJob | null
  batchJobDebugSnapshot?: SichuanBatchJobDebugSnapshot | null
  batchJobDebugLoading?: boolean
  fetchBatchJobDebugSnapshot?: (
    jobId: string,
    options?: { ruleJobId?: string; itemLimit?: number },
  ) => Promise<SichuanBatchJobDebugSnapshot | null>
  batchJobDetailLoading: boolean
  close: () => void
  exportBatchJobReport: (format?: 'xlsx' | 'csv') => void
  getBatchJobStatusTagClass: (status?: string) => string
  getBatchJobStatusText: (status?: string) => string
  formatDateTime: (value?: string | Date | null) => string
}>()

const scopeLabelMap: Record<string, string> = {
  running: '运行病历',
  final: '终末病历',
  all: '全量病历',
}

const ruleColumns = computed(() => [
  { title: '规则编码', dataIndex: 'rule_code', key: 'rule_code', width: 120 },
  { title: '规则名称', dataIndex: 'rule_name', key: 'rule_name', width: 220 },
  { title: '状态', dataIndex: 'status', key: 'status', width: 110 },
  { title: '命中问题', dataIndex: 'issue_records', key: 'issue_records', width: 100 },
  { title: '成功', dataIndex: 'success_count', key: 'success_count', width: 90 },
  { title: '失败', dataIndex: 'failed_count', key: 'failed_count', width: 90 },
])

const issueColumns = computed(() => [
  { title: '规则编码', dataIndex: 'rule_code', key: 'rule_code', width: 96 },
  { title: '病历号', dataIndex: 'record_id', key: 'record_id', width: 120 },
  { title: '执行器', dataIndex: 'executor_type', key: 'executor_type', width: 84 },
  { title: '规则版本', dataIndex: 'rule_version', key: 'rule_version', width: 112 },
  { title: 'Prompt版本', dataIndex: 'prompt_version', key: 'prompt_version', width: 120 },
  { title: '模型版本', dataIndex: 'model_version', key: 'model_version', width: 120 },
  { title: '证据来源', dataIndex: 'evidence_source', key: 'evidence_source', width: 110 },
])

const issueItems = computed<SichuanBatchIssueItem[]>(() => {
  const ruleResults = props.batchJobDetail?.rule_results || []
  const merged: SichuanBatchIssueItem[] = []
  ruleResults.forEach((ruleResult) => {
    ;(ruleResult.items || []).forEach((item) => {
      merged.push({
        ...item,
        rule_code: item.rule_code || ruleResult.rule_code,
        rule_name: item.rule_name || ruleResult.rule_name,
      })
    })
  })
  const recentItems = props.batchJobDebugSnapshot?.recent_items || []
  const source = merged.length > 0 ? merged : recentItems
  return source.slice(0, 200)
})

const selectedClusterKey = ref('')
const selectedDebugRuleJobId = ref('')
const issuePagination = reactive({
  current: 1,
  pageSize: 8,
  showSizeChanger: false,
})

watch(
  () => props.batchJobDetail?.id,
  () => {
    selectedClusterKey.value = ''
    selectedDebugRuleJobId.value = ''
  },
)

const resultAggregation = computed<SichuanBatchResultAggregation | null>(() => {
  return props.batchJobDetail?.summary?.result_aggregation || null
})

const topAggregationClusters = computed(() => {
  return (resultAggregation.value?.clusters || []).slice(0, 8)
})

const aggregationBreakdownSections = computed(() => {
  const aggregation = resultAggregation.value
  if (!aggregation) return []
  return [
    {
      key: 'rule',
      title: '按规则',
      total:
        aggregation.rule_breakdown?.reduce((sum, item) => sum + Number(item.hits || 0), 0) || 0,
      items: normalizeBreakdownItems(
        (aggregation.rule_breakdown || []).map((item) => ({
          label: item.rule_name || item.rule_id,
          count: Number(item.hits || 0),
        })),
      ),
    },
    {
      key: 'executor',
      title: '按执行器',
      total:
        aggregation.executor_breakdown?.reduce((sum, item) => sum + Number(item.count || 0), 0) ||
        0,
      items: normalizeBreakdownItems(
        (aggregation.executor_breakdown || []).map((item) => ({
          label: resolveBreakdownLabel('executor', item.key),
          count: Number(item.count || 0),
        })),
      ),
    },
    {
      key: 'document',
      title: '按文书',
      total:
        aggregation.document_breakdown?.reduce((sum, item) => sum + Number(item.count || 0), 0) ||
        0,
      items: normalizeBreakdownItems(
        (aggregation.document_breakdown || []).map((item) => ({
          label: resolveBreakdownLabel('document', item.key),
          count: Number(item.count || 0),
        })),
      ),
    },
    {
      key: 'defect',
      title: '按缺陷级别',
      total:
        aggregation.defect_level_breakdown?.reduce(
          (sum, item) => sum + Number(item.count || 0),
          0,
        ) || 0,
      items: normalizeBreakdownItems(
        (aggregation.defect_level_breakdown || []).map((item) => ({
          label: resolveBreakdownLabel('defect', item.key),
          count: Number(item.count || 0),
        })),
      ),
    },
  ]
})

const batchJobDebugSnapshot = computed(() => props.batchJobDebugSnapshot || null)
const debugRuleOptions = computed(() => {
  return (batchJobDebugSnapshot.value?.rules || []).map((rule) => ({
    label: `${rule.rule_code} · ${rule.rule_name}`,
    value: rule.rule_job_id,
  }))
})

const currentDebugRule = computed(() => {
  const snapshot = batchJobDebugSnapshot.value
  if (!snapshot) return null
  if (selectedDebugRuleJobId.value) {
    return (
      (snapshot.rules || []).find((rule) => rule.rule_job_id === selectedDebugRuleJobId.value) ||
      null
    )
  }
  const currentRuleJobId = String(snapshot.current_rule?.rule_job_id || '').trim()
  if (currentRuleJobId) {
    const matched = (snapshot.rules || []).find((rule) => rule.rule_job_id === currentRuleJobId)
    if (matched) return matched
  }
  return (
    (snapshot.rules || []).find((rule) => String(rule.status || '').toLowerCase() === 'running') ||
    snapshot.rules?.[0] ||
    null
  )
})

const debugProgressEntries = computed(() => {
  const progress =
    batchJobDebugSnapshot.value?.current_rule?.progress || currentDebugRule.value?.progress || {}
  return objectEntriesToCompactList(progress)
})

const debugDetailEntries = computed(() => {
  return objectEntriesToCompactList(currentDebugRule.value?.debug || {})
})

const activeRuleFilterLabel = computed(() => {
  if (!selectedDebugRuleJobId.value) return ''
  const matched = (batchJobDebugSnapshot.value?.rules || []).find(
    (rule) => rule.rule_job_id === selectedDebugRuleJobId.value,
  )
  if (!matched) return ''
  return `${matched.rule_code} · ${matched.rule_name}`
})

const selectedCluster = computed(() => {
  if (!selectedClusterKey.value) return null
  return (
    (resultAggregation.value?.clusters || []).find(
      (cluster) => cluster.cluster_key === selectedClusterKey.value,
    ) || null
  )
})

const displayIssueItems = computed<SichuanBatchIssueItem[]>(() => {
  const items = issueItems.value.filter((item) => {
    if (!selectedDebugRuleJobId.value) return true
    const itemRuleJobId = String(item.rule_job_id || '').trim()
    return itemRuleJobId === selectedDebugRuleJobId.value
  })
  const cluster = selectedCluster.value
  if (!cluster) return items
  return items.filter((item) => matchIssueItemWithCluster(item, cluster))
})

const linkedIssueRowKey = computed(() => {
  if (!selectedCluster.value) return ''
  return resolveIssueStableKey(displayIssueItems.value[0])
})

const displayRuleResults = computed(() => {
  const items = props.batchJobDetail?.rule_results || []
  if (!selectedDebugRuleJobId.value) return items
  return items.filter((item) => String(item.id || '').trim() === selectedDebugRuleJobId.value)
})

const executionSummary = computed(() => {
  const summary = props.batchJobDetail?.summary
  const fromSummary = summary?.executor_breakdown
  const cacheFromSummary = summary?.cache_breakdown
  if (fromSummary || cacheFromSummary) {
    return {
      programCount: Number(fromSummary?.program || 0),
      llmCount: Number(fromSummary?.llm || 0),
      cacheHit: Number(cacheFromSummary?.hit || 0),
      cacheMiss: Number(cacheFromSummary?.miss || 0),
    }
  }
  const items = issueItems.value
  if (!items.length) return null
  const programCount = items.filter(
    (item) => String(item.executor_type || '').toLowerCase() === 'program',
  ).length
  const llmCount = items.filter(
    (item) => String(item.executor_type || '').toLowerCase() !== 'program',
  ).length
  const cacheHit = items.filter((item) => item.cache_hit === true).length
  const cacheMiss = items.length - cacheHit
  return { programCount, llmCount, cacheHit, cacheMiss }
})

const primarySummaryCards = computed(() => {
  const summary = props.batchJobDetail?.summary
  const totalRecords = Number(summary?.total_records ?? props.batchJobDetail?.total_records ?? 0)
  const successCount = Number(summary?.success_count ?? props.batchJobDetail?.success_count ?? 0)
  const failedRecordCount = Number(
    summary?.failed_record_count ?? props.batchJobDetail?.failed_count ?? 0,
  )
  const failedAttemptCount = Number(
    summary?.failed_count ?? props.batchJobDetail?.failed_count ?? 0,
  )
  const issueRecords = Number(summary?.issue_records ?? props.batchJobDetail?.issue_records ?? 0)
  return [
    { key: 'total', label: '总病历', value: totalRecords, desc: '' },
    { key: 'success', label: '执行成功', value: successCount, desc: '' },
    { key: 'failed-records', label: '失败病历', value: failedRecordCount, desc: '去重后的病历数' },
    {
      key: 'failed-attempts',
      label: '失败次数',
      value: failedAttemptCount,
      desc: '规则执行失败总次数',
    },
    { key: 'issues', label: '命中问题', value: issueRecords, desc: '' },
  ]
})

const executionSummaryCards = computed(() => {
  if (!executionSummary.value) return []
  return [
    { key: 'program', label: 'Program执行', value: executionSummary.value.programCount },
    { key: 'llm', label: 'LLM执行', value: executionSummary.value.llmCount },
    { key: 'hit', label: '缓存命中', value: executionSummary.value.cacheHit },
    { key: 'miss', label: '缓存未命中', value: executionSummary.value.cacheMiss },
  ]
})

watch(
  () => [batchJobDebugSnapshot.value?.job_id, batchJobDebugSnapshot.value?.rules?.length],
  () => {
    if (!batchJobDebugSnapshot.value) {
      selectedDebugRuleJobId.value = ''
      return
    }
    if (!selectedDebugRuleJobId.value) return
    const hasSelected = (batchJobDebugSnapshot.value.rules || []).some(
      (rule) => rule.rule_job_id === selectedDebugRuleJobId.value,
    )
    if (!hasSelected) {
      selectedDebugRuleJobId.value = ''
    }
  },
  { immediate: true },
)

async function handleDebugRuleChange(value: string | undefined) {
  selectedDebugRuleJobId.value = value || ''
  const jobId = props.batchJobDetail?.id
  if (!jobId || !props.fetchBatchJobDebugSnapshot) return
  await props.fetchBatchJobDebugSnapshot(jobId, {
    ruleJobId: value || undefined,
  })
}

function toggleClusterFilter(clusterKey: string) {
  selectedClusterKey.value = selectedClusterKey.value === clusterKey ? '' : clusterKey
  issuePagination.current = 1
  void nextTick(() => scrollToLinkedIssueRow())
}

function clearClusterFilter() {
  selectedClusterKey.value = ''
  issuePagination.current = 1
}

function handleIssueTableChange(pagination: { current?: number; pageSize?: number }) {
  issuePagination.current = Number(pagination.current || 1)
  issuePagination.pageSize = Number(pagination.pageSize || 8)
}

function resolveIssueStableKey(item?: SichuanBatchIssueItem) {
  if (!item) return ''
  return [
    item.rule_job_id || '',
    item.rule_id || item.rule_code || '',
    item.record_id || '',
    item.visit_id || '',
    item.trace_id || '',
  ].join('|')
}

function scrollToLinkedIssueRow() {
  const linkedKey = linkedIssueRowKey.value
  if (!linkedKey) return
  const row = document.querySelector<HTMLElement>(
    `.batch-issue-table tbody tr[data-row-key="${linkedKey.replace(/"/g, '\\"')}"]`,
  )
  if (row) {
    row.scrollIntoView({ block: 'center', behavior: 'smooth' })
  }
}

function normalizeBreakdownItems(items: Array<{ label: string; count: number }>) {
  return items
    .filter((item) => item.label)
    .sort((left, right) => right.count - left.count)
    .slice(0, 4)
}

function resolveBreakdownLabel(kind: 'executor' | 'document' | 'defect', key: string) {
  const normalizedKey = String(key || '').trim()
  if (!normalizedKey) return '未命名'
  if (kind === 'executor') {
    const map: Record<string, string> = {
      program: '程序规则',
      llm: 'LLM 规则',
    }
    return map[normalizedKey.toLowerCase()] || normalizedKey
  }
  if (kind === 'defect') {
    const map: Record<string, string> = {
      critical: '严重缺陷',
      major: '重大缺陷',
      moderate: '中度缺陷',
      minor: '轻微缺陷',
      high: '高风险',
      medium: '中风险',
      low: '低风险',
    }
    return map[normalizedKey.toLowerCase()] || normalizedKey
  }
  return normalizedKey
}

function objectEntriesToCompactList(input: Record<string, unknown> | unknown) {
  if (!input || typeof input !== 'object') return []
  return Object.entries(input)
    .map(([label, value]) => ({
      label,
      value: formatCompactValue(value),
    }))
    .filter((item) => item.label && item.value)
    .slice(0, 8)
}

function formatCompactValue(value: unknown) {
  if (value === null || value === undefined) return ''
  if (typeof value === 'string') return value.trim()
  if (typeof value === 'number' || typeof value === 'boolean') return String(value)
  if (Array.isArray(value)) {
    const list = value
      .slice(0, 3)
      .map((item) => formatCompactValue(item))
      .filter(Boolean)
    const suffix = value.length > 3 ? '…' : ''
    return list.join('、') + suffix
  }
  if (value instanceof Date) {
    return value.toISOString()
  }
  try {
    const json = JSON.stringify(value)
    return json.length > 72 ? `${json.slice(0, 72)}…` : json
  } catch {
    return String(value)
  }
}

function resolveIssueRowClassName(record: SichuanBatchIssueItem) {
  const linkedKey = linkedIssueRowKey.value
  const currentKey = resolveIssueStableKey(record)
  if (linkedKey && currentKey === linkedKey) return 'issue-row-highlight issue-row-linked'
  if (!selectedCluster.value) return ''
  return matchIssueItemWithCluster(record, selectedCluster.value) ? 'issue-row-highlight' : ''
}

// 聚合簇命中判定：优先规则ID/编码匹配，其次回退到证据文本匹配。
function matchIssueItemWithCluster(
  item: SichuanBatchIssueItem,
  cluster: SichuanBatchResultAggregation['clusters'][number],
) {
  const clusterRuleIdSet = new Set(
    (cluster.rules || []).map((rule) => String(rule.rule_id || '').toLowerCase()).filter(Boolean),
  )
  const itemRuleCode = String(item.rule_code || '').toLowerCase()
  const itemRuleId = String(item.rule_id || '').toLowerCase()
  const byRule =
    (itemRuleId && clusterRuleIdSet.has(itemRuleId)) ||
    (itemRuleCode && clusterRuleIdSet.has(itemRuleCode))
  if (byRule) return true
  const finding = String(item.findings || '')
  const evidence = String(item.evidence || '')
  const sampleEvidence = String(cluster.sample_evidence || '').trim()
  if (sampleEvidence && (finding.includes(sampleEvidence) || evidence.includes(sampleEvidence))) {
    return true
  }
  const clusterKey = String(cluster.cluster_key || '').trim()
  if (clusterKey && (finding.includes(clusterKey) || evidence.includes(clusterKey))) {
    return true
  }
  return false
}

watch(
  () => [selectedClusterKey.value, displayIssueItems.value.length],
  async () => {
    if (!selectedClusterKey.value) return
    issuePagination.current = 1
    await nextTick()
    scrollToLinkedIssueRow()
  },
)
</script>

<style scoped>
.drawer-shell {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: #f8fafc;
}

.drawer-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  padding: 18px 22px;
  border-bottom: 1px solid #e2e8f0;
  background: #fff;
}

.drawer-eyebrow {
  margin: 0;
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: #94a3b8;
  font-weight: 600;
}

.drawer-title {
  margin: 4px 0 0;
  font-size: 20px;
  font-weight: 700;
  color: #0f172a;
}

.drawer-actions {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.drawer-body {
  flex: 1;
  overflow: auto;
  padding: 16px 20px 24px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.drawer-card {
  border-radius: 16px;
  border: 1px solid #e2e8f0;
  background: #fff;
  padding: 14px 16px;
}

.drawer-card-top {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
}

.drawer-rule-name {
  font-size: 14px;
  font-weight: 600;
  color: #0f172a;
}

.drawer-meta {
  font-size: 12px;
  color: #64748b;
  margin-top: 4px;
}

.drawer-error {
  margin-top: 10px;
  border-radius: 12px;
  border: 1px solid #fecaca;
  background: #fff1f2;
  color: #b91c1c;
  padding: 10px 12px;
  font-size: 12px;
}

.drawer-summary {
  display: grid;
  gap: 12px;
}

.summary-grid-primary {
  grid-template-columns: repeat(5, minmax(0, 1fr));
}

.summary-grid-secondary {
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.drawer-summary .summary-card {
  border-radius: 16px;
  border: 1px solid #e2e8f0;
  background: #fff;
  padding: 12px 14px;
}

.summary-label {
  font-size: 11px;
  color: #94a3b8;
}

.summary-value {
  margin-top: 4px;
  font-size: 18px;
  font-weight: 700;
  color: #0f172a;
}

.summary-desc {
  margin-top: 4px;
  font-size: 11px;
  color: #94a3b8;
}

.drawer-section-title {
  font-size: 14px;
  font-weight: 600;
  color: #0f172a;
  margin-bottom: 10px;
}

.drawer-section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 10px;
}

.drawer-section-head .drawer-section-title {
  margin-bottom: 0;
}

.drawer-section-meta {
  font-size: 12px;
  color: #64748b;
}

.debug-toolbar {
  display: inline-flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.debug-rule-select {
  min-width: 240px;
}

.aggregation-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.aggregation-breakdown-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  margin-bottom: 12px;
}

.aggregation-breakdown-card {
  border-radius: 12px;
  border: 1px solid #e2e8f0;
  background: #f8fafc;
  padding: 10px 12px;
}

.aggregation-breakdown-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.aggregation-breakdown-title {
  font-size: 12px;
  font-weight: 600;
  color: #0f172a;
}

.aggregation-breakdown-count {
  font-size: 13px;
  font-weight: 700;
  color: #1e40af;
}

.aggregation-breakdown-items {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 10px;
}

.aggregation-breakdown-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.aggregation-breakdown-item-label {
  font-size: 12px;
  color: #475569;
  line-height: 1.45;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.aggregation-breakdown-item-tag {
  color: #1e40af;
  border-color: #bfdbfe;
  background: #eff6ff;
  margin: 0;
}

.aggregation-breakdown-empty {
  margin-top: 10px;
  font-size: 12px;
  color: #94a3b8;
}

.aggregation-item {
  border-radius: 12px;
  border: 1px solid #e2e8f0;
  background: #f8fafc;
  padding: 10px 12px;
  cursor: pointer;
  transition:
    border-color 0.2s ease,
    box-shadow 0.2s ease;
}

.aggregation-item.active {
  border-color: #93c5fd;
  box-shadow: 0 0 0 2px rgba(191, 219, 254, 0.45);
}

.aggregation-item-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.aggregation-item-title {
  font-size: 13px;
  font-weight: 600;
  color: #0f172a;
}

.aggregation-count-tag {
  color: #1e40af;
  border-color: #bfdbfe;
  background: #eff6ff;
}

.aggregation-evidence {
  margin-top: 6px;
  font-size: 12px;
  line-height: 1.5;
  color: #475569;
}

.aggregation-meta {
  margin-top: 6px;
  font-size: 12px;
  color: #64748b;
}

.aggregation-active-tip {
  margin-top: 10px;
  border-radius: 10px;
  border: 1px solid #dbeafe;
  background: #eff6ff;
  color: #1e3a8a;
  font-size: 12px;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
}

.debug-current-rule {
  border-radius: 12px;
  border: 1px solid #dbeafe;
  background: linear-gradient(135deg, rgba(239, 246, 255, 0.95), #fff);
  padding: 10px 12px;
}

.debug-current-rule-main {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.debug-current-rule-label {
  font-size: 11px;
  color: #64748b;
}

.debug-current-rule-value {
  font-size: 13px;
  font-weight: 700;
  color: #0f172a;
}

.debug-current-rule-sub {
  margin-top: 6px;
  font-size: 12px;
  color: #475569;
  line-height: 1.5;
}

.debug-meta-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  margin-top: 12px;
}

.debug-meta-item {
  border-radius: 12px;
  border: 1px solid #e2e8f0;
  background: #fff;
  padding: 8px 10px;
}

.debug-meta-label {
  display: block;
  font-size: 11px;
  color: #94a3b8;
}

.debug-meta-value {
  display: block;
  margin-top: 4px;
  font-size: 13px;
  color: #0f172a;
  font-weight: 600;
  word-break: break-word;
}

.debug-pill-block {
  margin-top: 12px;
}

.debug-pill-title {
  font-size: 12px;
  font-weight: 600;
  color: #0f172a;
  margin-bottom: 8px;
}

.debug-pill-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.debug-pill {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  border-radius: 999px;
  border: 1px solid #bfdbfe;
  background: #eff6ff;
  color: #1e40af;
  padding: 4px 10px;
  font-size: 12px;
  line-height: 1.4;
}

.debug-pill-muted {
  border-color: #e2e8f0;
  background: #f8fafc;
  color: #475569;
}

@media (max-width: 767px) {
  .summary-grid-primary,
  .summary-grid-secondary,
  .aggregation-breakdown-grid,
  .debug-meta-grid {
    grid-template-columns: 1fr;
  }
}

:deep(.issue-row-highlight td) {
  background: rgba(239, 246, 255, 0.66);
}

:deep(.issue-row-linked td) {
  background: rgba(219, 234, 254, 0.85);
}
</style>
