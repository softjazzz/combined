<template>
  <div class="content-qc-tab">
    <!-- 顶部操作栏 -->
    <div class="content-qc-tab__header">
      <div class="content-qc-tab__header-main">
        <div class="content-qc-tab__eyebrow">当前质控</div>
        <div class="header-left">
          <SafetyCertificateOutlined class="header-icon" />
          <span class="header-title">内涵质控</span>
          <a-tag v-if="totalCount > 0" color="error" size="small">
            {{ totalCount }}
          </a-tag>
        </div>
        <div class="content-qc-tab__header-desc">
          基于病历文书内容，检查诊疗逻辑、记录完整性与内涵一致性。
        </div>
      </div>
      <a-button
        type="link"
        size="small"
        class="content-qc-tab__header-action"
        :loading="loading"
        :disabled="!patientId"
        @click="runContentQC"
      >
        <ReloadOutlined /> {{ loading ? '分析中...' : '开始分析' }}
      </a-button>
    </div>

    <!-- 加载态 — 实时进度时间线 -->
    <div v-if="loading" class="content-qc-tab__progress">
      <!-- 进度头部 -->
      <div class="progress-header">
        <div class="progress-avatar">
          <ThunderboltOutlined class="text-white text-lg" />
        </div>
        <div>
          <div class="progress-title">正在执行整份病历质控评估</div>
          <div class="progress-sub">
            已完成 {{ completedSections.length }} / {{ totalSections }} 个阶段
          </div>
        </div>
        <a-spin class="ml-auto" />
      </div>

      <!-- 进度条 -->
      <div class="progress-bar-wrap">
        <div class="progress-bar-bg">
          <div class="progress-bar-fill" :style="{ width: `${progressPercent}%` }" />
        </div>
      </div>

      <!-- 文书时间线 -->
      <div class="progress-timeline">
        <div
          v-for="sec in sectionTimeline"
          :key="sec.type"
          class="timeline-item"
          :class="{
            'timeline-done': sec.status === 'done',
            'timeline-active': sec.status === 'active',
            'timeline-pending': sec.status === 'pending',
          }"
        >
          <!-- 状态图标 -->
          <div class="timeline-dot" :class="`timeline-dot--${sec.status}`">
            <CheckCircleOutlined v-if="sec.status === 'done'" class="text-white text-[10px]" />
            <span v-else-if="sec.status === 'active'" class="dot-ping" />
            <span v-else class="dot-idle" />
          </div>
          <!-- 内容 -->
          <div class="timeline-content">
            <div class="timeline-title-row">
              <span class="timeline-label" :class="`timeline-label--${sec.status}`">{{
                sec.label
              }}</span>
              <span v-if="sec.duration" class="timeline-time">{{ sec.duration }}s</span>
              <span v-if="sec.status === 'active'" class="timeline-active-hint">分析中...</span>
            </div>
            <!-- 已完成的质控结果预览 -->
            <div
              v-if="sec.status === 'done' && sec.ruleCount !== undefined"
              class="timeline-result"
            >
              <span class="result-tag result-tag--rules">{{ sec.ruleCount }} 条规则</span>
              <span v-if="(sec.issueCount ?? 0) > 0" class="result-tag result-tag--issues"
                >{{ sec.issueCount }} 个问题</span
              >
              <span v-else class="result-tag result-tag--pass">全部通过</span>
            </div>
            <!-- 发现的问题逐条展示 -->
            <div
              v-if="sec.status === 'done' && sec.issues && sec.issues.length > 0"
              class="timeline-issues"
            >
              <div v-for="(iss, i) in sec.issues.slice(0, 3)" :key="i" class="timeline-issue-item">
                <a-tag :color="severityTagColor(iss.severity)" size="small" class="!text-[10px]">
                  {{ severityLabel(iss.severity) }}
                </a-tag>
                <span class="issue-text">{{ iss.description }}</span>
              </div>
              <div v-if="sec.issues.length > 3" class="timeline-issue-more">
                +{{ sec.issues.length - 3 }} 条...
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 空态 - 未分析 -->
    <div v-else-if="!analyzed && issues.length === 0" class="content-qc-tab__empty">
      <div class="empty-icon-wrap">
        <SafetyCertificateOutlined class="empty-icon" />
      </div>
      <div class="empty-title">内涵质控分析</div>
      <div class="empty-desc">
        基于 LLM 对病历全文进行深度语义校验，聚焦诊疗逻辑、病程记录完整性与知情同意等内涵质量。
      </div>
      <a-button
        type="primary"
        size="small"
        :disabled="!patientId"
        class="empty-btn"
        @click="runContentQC"
      >
        <template #icon>
          <ThunderboltOutlined />
        </template>
        开始内涵质控
      </a-button>
    </div>

    <!-- 结构化结果 -->
    <div v-else class="content-qc-tab__body custom-scrollbar">
      <!-- 汇总卡片 -->
      <div v-if="summary" class="summary-card">
        <div class="summary-card__hero">
          <div>
            <div class="summary-card__eyebrow">本次内涵质控</div>
            <div class="summary-card__title">病历语义校验结果</div>
          </div>
          <div class="summary-card__progress">
            {{ complianceRateText }}
          </div>
        </div>
        <div v-if="isNoRulesResult" class="summary-card__warning">
          本次未加载到可执行规则（总规则数=0），当前结果不可作为“质控通过”依据。
        </div>
        <div class="summary-row">
          <span class="summary-label">总规则数</span>
          <span class="summary-value">{{ summary.totalRules }}</span>
        </div>
        <div class="summary-row">
          <span class="summary-label">合规率</span>
          <span class="summary-value" :class="complianceClass">{{ complianceRateText }}</span>
        </div>
        <div class="summary-row">
          <span class="summary-label">发现问题</span>
          <span class="summary-value text-red-500">{{ summary.issueCount }}</span>
        </div>
        <div v-if="subitemAnchorCount > 0" class="summary-row summary-row--action">
          <span class="summary-label">专项检查项</span>
          <button type="button" class="summary-link" @click="subitemAnchorDetailOpen = true">
            {{ subitemAnchorCount }} 项待复核
          </button>
        </div>
        <div class="summary-row">
          <span class="summary-label">待复核</span>
          <span class="summary-value text-amber-500">{{ summary.uncertainCount }}</span>
        </div>
        <div class="summary-row">
          <span class="summary-label">合规</span>
          <span class="summary-value text-blue-600">{{ summary.compliantCount }}</span>
        </div>
        <div class="summary-row">
          <span class="summary-label">不适用</span>
          <span class="summary-value">{{ summary.notApplicableCount }}</span>
        </div>
        <div class="summary-row">
          <span class="summary-label">失败</span>
          <span class="summary-value text-red-500">{{ summary.failedCount }}</span>
        </div>
        <div class="summary-row">
          <span class="summary-label">文书数</span>
          <span class="summary-value">{{ summary.docCount }}</span>
        </div>
        <div class="summary-row">
          <span class="summary-label">耗时</span>
          <span class="summary-value">{{ summary.processingTimeSeconds.toFixed(1) }}s</span>
        </div>
      </div>

      <div class="result-toolbar">
        <a-radio-group v-model:value="viewMode" size="small" class="result-view-switch">
          <a-radio-button value="business"> 业务视图 </a-radio-button>
          <a-radio-button value="advanced"> 高级视图 </a-radio-button>
        </a-radio-group>
        <div class="result-toolbar-meta">
          <a-switch v-model:checked="showAllStatuses" size="small" />
          <span>{{ showAllStatuses ? '显示全部状态' : '仅显示问题项' }}</span>
        </div>
      </div>

      <div v-if="visibleGroups.length" class="group-panel">
        <div class="group-panel-title">分组聚合（点击联动筛选）</div>
        <div class="group-grid">
          <button
            v-for="group in visibleGroups"
            :key="group.key"
            type="button"
            class="group-chip"
            :class="{ 'group-chip--active': activeGroupKey === group.key }"
            @click="applyGroupFilter(group)"
          >
            <span class="group-chip__label">{{ group.label }}</span>
            <span class="group-chip__meta">{{ group.kind }} · {{ group.count }}</span>
          </button>
        </div>
      </div>

      <div class="filter-panel">
        <a-input
          v-model:value="issueFilter.keyword"
          allow-clear
          placeholder="搜索规则/结论/证据"
          class="filter-item filter-item--keyword"
          @change="detailPagination.current = 1"
        >
          <template #prefix>
            <SearchOutlined />
          </template>
        </a-input>
        <a-select
          v-model:value="issueFilter.documentType"
          allow-clear
          class="filter-item"
          placeholder="文书域"
          :options="documentTypeOptions"
          @change="detailPagination.current = 1"
        />
        <a-select
          v-model:value="issueFilter.executionDomain"
          allow-clear
          class="filter-item"
          placeholder="规则域"
          :options="executionDomainOptions"
          @change="detailPagination.current = 1"
        />
        <a-select
          v-model:value="issueFilter.defectLevel"
          allow-clear
          class="filter-item"
          placeholder="缺陷等级"
          :options="defectLevelOptions"
          @change="detailPagination.current = 1"
        />
        <a-button size="small" @click="resetIssueFilter"> 重置筛选 </a-button>
      </div>

      <template v-if="filteredIssues.length > 0">
        <div class="issue-card-list">
          <article
            v-for="record in pagedIssues"
            :key="record.id"
            class="issue-card"
            :class="`issue-card--${record.status}`"
          >
            <header class="issue-card__header">
              <a-tag class="issue-card__status" :color="statusTagColor(record.status)">
                {{ record.statusLabel }}
              </a-tag>
              <span class="issue-card__code">{{ record.ruleCode || record.ruleId || '-' }}</span>
            </header>

            <div class="issue-card__title">
              {{ record.ruleName || '-' }}
            </div>

            <div class="issue-card__findings">
              {{ record.findings || '未提供结论' }}
            </div>

            <div v-if="record.metadata.subitemAnchors.length" class="issue-card__subitem-anchors">
              <div class="subitem-anchor-head">
                <span>父规则专项检查项</span>
                <span>{{ record.metadata.subitemAnchors.length }} 项</span>
              </div>
              <div
                v-for="anchor in record.metadata.subitemAnchors"
                :key="anchor.subitemId || anchor.anchorId"
                class="subitem-anchor"
              >
                <div class="subitem-anchor__top">
                  <span class="subitem-anchor__name">{{ anchor.subitemName || '专项检查项' }}</span>
                  <a-tag
                    class="subitem-anchor__tag"
                    :color="subitemAnchorTagColor(anchor.displayStatus)"
                  >
                    {{ subitemAnchorDisplayLabel(anchor) }}
                  </a-tag>
                </div>
                <div v-if="anchor.anchorEvidence" class="subitem-anchor__evidence">
                  {{ anchor.anchorEvidence }}
                </div>
                <div v-if="anchor.anchorDecisionReason" class="subitem-anchor__reason">
                  判定原因：{{ anchor.anchorDecisionReason }}
                </div>
              </div>
            </div>

            <div v-if="record.suggestion" class="issue-card__suggestion">
              建议：{{ record.suggestion }}
            </div>

            <div class="issue-card__meta">
              <a-tag v-if="record.documentType" class="issue-card__chip">
                文书域：{{ record.documentType }}
              </a-tag>
              <a-tag v-if="record.executionDomain" class="issue-card__chip">
                规则域：{{ record.executionDomain }}
              </a-tag>
              <a-tag v-if="record.defectLevel" class="issue-card__chip">
                缺陷等级：{{ record.defectLevel }}
              </a-tag>
              <a-tag v-if="Number(record.confidence || 0) > 0" class="issue-card__chip">
                置信度：{{ formatConfidence(record.confidence) }}
              </a-tag>
            </div>

            <div v-if="viewMode === 'advanced'" class="issue-card__advanced">
              <span>trace: {{ record.metadata.traceId || '-' }}</span>
              <span
                >cache:
                {{
                  record.metadata.cacheHit === null
                    ? '-'
                    : record.metadata.cacheHit
                      ? '命中'
                      : '未命中'
                }}</span
              >
              <span>prompt: {{ record.metadata.promptVersion || '-' }}</span>
              <span>model: {{ record.metadata.modelVersion || '-' }}</span>
            </div>

            <footer class="issue-card__actions">
              <a-button
                v-if="askAssistantEnabled && record.ruleId"
                type="link"
                size="small"
                data-testid="content-qc-ask-assistant"
                @click="
                  emit('ask-assistant', {
                    ruleId: record.ruleId,
                    ruleName: record.ruleName || '',
                  })
                "
              >
                问助手
              </a-button>
              <a-button
                type="link"
                size="small"
                @click="openIssueDetail(record as StructuredQCIssue)"
              >
                查看详情
              </a-button>
              <a-button
                type="link"
                size="small"
                @click="copyIssueEvidence(record as StructuredQCIssue)"
              >
                复制证据
              </a-button>
            </footer>
          </article>
        </div>
        <div class="detail-pagination">
          <a-pagination
            :current="detailPagination.current"
            :page-size="detailPagination.pageSize"
            :total="detailPagination.total"
            :show-size-changer="false"
            size="small"
            @change="handleDetailPageChange"
          />
        </div>
      </template>

      <!-- 无问题 -->
      <div v-else class="content-qc-tab__empty-result">
        <CheckCircleOutlined class="empty-result-icon" />
        <div class="empty-result-text">
          {{ showAllStatuses ? '暂无匹配明细' : '当前仅问题视图下未发现问题' }}
        </div>
      </div>
    </div>

    <a-modal
      v-model:open="issueDetailOpen"
      title="质控明细"
      width="760px"
      :footer="null"
      destroy-on-close
    >
      <div v-if="issueDetailRecord" class="issue-detail">
        <div class="issue-detail-grid">
          <div class="issue-detail-item">
            <span class="issue-detail-label">规则</span>
            <span class="issue-detail-value">{{
              issueDetailRecord.ruleCode || issueDetailRecord.ruleId || '-'
            }}</span>
          </div>
          <div class="issue-detail-item">
            <span class="issue-detail-label">状态</span>
            <a-tag :color="statusTagColor(issueDetailRecord.status)">
              {{ issueDetailRecord.statusLabel }}
            </a-tag>
          </div>
          <div class="issue-detail-item">
            <span class="issue-detail-label">文书域</span>
            <span class="issue-detail-value">{{ issueDetailRecord.documentType || '-' }}</span>
          </div>
          <div class="issue-detail-item">
            <span class="issue-detail-label">规则域</span>
            <span class="issue-detail-value">{{ issueDetailRecord.executionDomain || '-' }}</span>
          </div>
          <div class="issue-detail-item">
            <span class="issue-detail-label">缺陷等级</span>
            <span class="issue-detail-value">{{ issueDetailRecord.defectLevel || '-' }}</span>
          </div>
          <div class="issue-detail-item">
            <span class="issue-detail-label">置信度</span>
            <span class="issue-detail-value">{{
              Number(issueDetailRecord.confidence || 0).toFixed(2)
            }}</span>
          </div>
        </div>
        <div class="issue-detail-block">
          <div class="issue-detail-block__title">结论</div>
          <div class="issue-detail-block__content">
            {{ issueDetailRecord.findings || '-' }}
          </div>
        </div>
        <div class="issue-detail-block">
          <div class="issue-detail-block__title">证据</div>
          <div class="issue-detail-block__content">
            {{ issueDetailRecord.evidence || '-' }}
          </div>
        </div>
        <div class="issue-detail-block">
          <div class="issue-detail-block__title">建议</div>
          <div class="issue-detail-block__content">
            {{ issueDetailRecord.suggestion || '-' }}
          </div>
        </div>
        <div v-if="issueDetailRecord.metadata.subitemAnchors.length" class="issue-detail-block">
          <div class="issue-detail-block__title">专项检查项</div>
          <div class="issue-detail-subitem-list">
            <div
              v-for="anchor in issueDetailRecord.metadata.subitemAnchors"
              :key="anchor.subitemId || anchor.anchorId"
              class="subitem-anchor subitem-anchor--detail"
            >
              <div class="subitem-anchor__top">
                <span class="subitem-anchor__name">{{ anchor.subitemName || '专项检查项' }}</span>
                <a-tag :color="subitemAnchorTagColor(anchor.displayStatus)">
                  {{ subitemAnchorDisplayLabel(anchor) }}
                </a-tag>
              </div>
              <div v-if="anchor.anchorEvidence" class="subitem-anchor__evidence">
                {{ anchor.anchorEvidence }}
              </div>
              <div v-if="anchor.anchorDecisionReason" class="subitem-anchor__reason">
                判定原因：{{ anchor.anchorDecisionReason }}
              </div>
            </div>
          </div>
        </div>
        <div v-if="viewMode === 'advanced'" class="issue-detail-block">
          <div class="issue-detail-block__title">高级追溯</div>
          <div class="advanced-cell advanced-cell--detail">
            <span>trace_id: {{ issueDetailRecord.metadata.traceId || '-' }}</span>
            <span
              >cache_hit:
              {{
                issueDetailRecord.metadata.cacheHit === null
                  ? '-'
                  : issueDetailRecord.metadata.cacheHit
              }}</span
            >
            <span>prompt_version: {{ issueDetailRecord.metadata.promptVersion || '-' }}</span>
            <span>model_version: {{ issueDetailRecord.metadata.modelVersion || '-' }}</span>
            <span>rule_version: {{ issueDetailRecord.metadata.ruleVersion || '-' }}</span>
            <span>evidence_source: {{ issueDetailRecord.metadata.evidenceSource || '-' }}</span>
            <span>cache_key: {{ issueDetailRecord.metadata.cacheKey || '-' }}</span>
            <span>doc_scope: {{ issueDetailRecord.metadata.docScope || '-' }}</span>
            <span>cost_class: {{ issueDetailRecord.metadata.costClass || '-' }}</span>
            <span
              >llm_fallback:
              {{
                issueDetailRecord.metadata.llmFallback === null
                  ? '-'
                  : issueDetailRecord.metadata.llmFallback
              }}</span
            >
          </div>
        </div>
      </div>
    </a-modal>

    <a-modal
      v-model:open="subitemAnchorDetailOpen"
      title="专项检查项（待复核）"
      width="760px"
      :footer="null"
      destroy-on-close
    >
      <div class="subitem-anchor-modal">
        <div class="subitem-anchor-modal__hint">
          以下为父规则下的专项检查项，只作为待复核或数据缺口提示，不计入确认缺陷数量。
        </div>
        <div
          v-for="anchor in structuredResult?.subitemAnchors || []"
          :key="`${anchor.parentRuleId}-${anchor.subitemId || anchor.anchorId}`"
          class="subitem-anchor subitem-anchor--detail"
        >
          <div class="subitem-anchor__top">
            <span class="subitem-anchor__name">{{ anchor.subitemName || '专项检查项' }}</span>
            <a-tag :color="subitemAnchorTagColor(anchor.displayStatus)">
              {{ subitemAnchorDisplayLabel(anchor) }}
            </a-tag>
          </div>
          <div class="subitem-anchor__parent">父规则：{{ anchor.parentRuleId || '-' }}</div>
          <div v-if="anchor.anchorEvidence" class="subitem-anchor__evidence">
            {{ anchor.anchorEvidence }}
          </div>
          <div v-if="anchor.anchorDecisionReason" class="subitem-anchor__reason">
            判定原因：{{ anchor.anchorDecisionReason }}
          </div>
        </div>
      </div>
    </a-modal>

    <!-- 底部 -->
    <footer v-if="analyzed && !loading" class="content-qc-tab__footer">
      <span
        >共 <strong>{{ totalCount }}</strong> 个问题</span
      >
      <a-button type="link" size="small" :loading="loading" @click="runContentQC">
        <ReloadOutlined /> 重新分析
      </a-button>
    </footer>
  </div>
</template>

<script setup lang="ts">
import { LONG_REQUEST_TIMEOUT_MS } from '@/config/requestTimeouts'
import { ref, computed, watch } from 'vue'
import { message } from 'ant-design-vue'
import {
  SafetyCertificateOutlined,
  ReloadOutlined,
  ThunderboltOutlined,
  CheckCircleOutlined,
  SearchOutlined,
} from '@ant-design/icons-vue'
import axios from 'axios'
import { evaluateSichuanBundleQC } from '@/api/qc'
import { extractApiData } from '@/utils/api-helpers'
import {
  createDefaultStructuredQCFilter,
  filterStructuredQCIssues,
  getSubitemAnchorDisplayLabel,
  isProblemStatus,
  mapSichuanEvaluationToStructuredQC,
} from '@/views/workstation-v4/utils/structuredQc'
import type {
  StructuredQCFilterState,
  StructuredQCIssue,
  StructuredQCResult,
  StructuredQCStatus,
  StructuredQCSubitemAnchor,
} from '@/views/workstation-v4/types'

// ==================== 类型 ====================

interface ContentIssue {
  ruleId: string
  ruleName: string
  severity: 'error' | 'warning' | 'info'
  group: string
  description: string
  suggestion?: string
}

interface ContentSummary {
  totalRules: number
  complianceRate: number | null
  issueCount: number
  uncertainCount: number
  compliantCount: number
  notApplicableCount: number
  failedCount: number
  docCount: number
  processingTimeSeconds: number
}

interface SectionProgress {
  type: string
  label: string
  content: string
  status: 'pending' | 'active' | 'done'
  ruleCount?: number
  issueCount?: number
  duration?: string
  issues?: ContentIssue[]
}

// ==================== 文书类型（来自 PG 数据库表） ====================

interface DocItem {
  type: string // PG 表名，如 admission_record
  label: string // 中文文书名，如 "入院记录"
  has_content: boolean
  content: string | null
  length: number
}

// PG 表名 → 质控引擎文书类型映射
const TABLE_TO_DOC_TYPE: Record<string, string> = {
  admission_record: '入院记录',
  first_course_record: '首次病程记录',
  daily_course_record: '日常病程记录',
  senior_course_record: '主任（副主任）医师查房记录',
  discharge_record: '出院记录',
  surgery_record: '手术记录',
  postsurg_firstcourse_record: '术后首次病程记录',
  consultation_record: '会诊记录',
  death_record: '死亡记录',
  rescue_record: '抢救记录',
  surgery_inform_consent: '手术知情同意书',
  preane_surveil_record: '麻醉前访视记录',
  presurg_discussion: '术前讨论记录',
  diffcase_discussion_record: '疑难病例讨论记录',
}

// ==================== Props & Emits ====================

const props = defineProps<{
  patientId?: string
  visitId?: string
  instituteId?: string
  scene?: 'running' | 'final' | string
  documents?: DocItem[] // 从 PG 各文书表查出的文书列表
  // 宿主面板有对话页签时才显示“问助手”。
  askAssistantEnabled?: boolean
}>()

const emit = defineEmits<{
  (e: 'issues-change', count: number): void
  // 请求在智能助手“对话”页签中就某条规则提问（只带规则标识，由助手读取权威数据）。
  (e: 'ask-assistant', payload: { ruleId: string; ruleName: string }): void
}>()

// ==================== 状态 ====================

const loading = ref(false)
const analyzed = ref(false)
const issues = ref<ContentIssue[]>([])
const summary = ref<ContentSummary | null>(null)
const structuredResult = ref<StructuredQCResult | null>(null)
const completedSections = ref<SectionProgress[]>([])
const sectionTimeline = ref<SectionProgress[]>([])
const totalSections = ref(0)
const viewMode = ref<'business' | 'advanced'>('business')
const showAllStatuses = ref(false)
const activeGroupKey = ref('')
const issueFilter = ref<StructuredQCFilterState>(createDefaultStructuredQCFilter())
const issueDetailOpen = ref(false)
const issueDetailRecord = ref<StructuredQCIssue | null>(null)
const subitemAnchorDetailOpen = ref(false)
const fullDocumentsVisitKey = ref('')
const fullDocumentsCache = ref<DocItem[]>([])
let fullDocumentsRequest: Promise<DocItem[]> | null = null

const detailPagination = ref({
  current: 1,
  pageSize: 8,
  total: 0,
})

const totalCount = computed(() => Number(summary.value?.issueCount || issues.value.length || 0))
const subitemAnchorCount = computed(() =>
  Number(structuredResult.value?.subitemAnchors?.length || 0),
)
const progressPercent = computed(() =>
  totalSections.value > 0
    ? Math.round((completedSections.value.length / totalSections.value) * 100)
    : 0,
)

const complianceClass = computed(() => {
  if (!summary.value) return ''
  if (summary.value.totalRules <= 0 || summary.value.complianceRate === null) return 'text-slate-400'
  const rate = summary.value.complianceRate
  if (rate >= 90) return 'text-blue-600'
  if (rate >= 70) return 'text-amber-500'
  return 'text-red-500'
})

const isNoRulesResult = computed(() => {
  return !!summary.value && Number(summary.value.totalRules || 0) <= 0
})

const complianceRateText = computed(() => {
  if (!summary.value || summary.value.totalRules <= 0) return '--'
  if (summary.value.complianceRate === null) return '无适用项'
  return `${summary.value.complianceRate}%`
})

const fallbackStructuredIssues = computed<StructuredQCIssue[]>(() => {
  return issues.value.map((item, index) => ({
    id: `${item.ruleId || 'unknown'}-${index}`,
    status: 'non_compliant',
    statusLabel: '不合规',
    displayStatus: '',
    displayBucket: '',
    postprocessLabel: '',
    postprocessReason: '',
    evidenceProblemType: '',
    canShowAsDefect: false,
    canShowToDoctor: true,
    internalOnly: false,
    postprocessMode: '',
    ruleJobId: '',
    ruleId: item.ruleId || '',
    ruleCode: item.ruleId || '',
    ruleName: item.ruleName || '未知规则',
    findings: item.description || '',
    evidence: '',
    suggestion: item.suggestion || '',
    confidence: 0,
    documentType: item.group || '',
    executionDomain: '',
    ruleFamily: '',
    defectLevel: '',
    executorType: '',
    recordId: '',
    visitId: '',
    patientName: '',
    department: '',
    metadata: {
      traceId: '',
      cacheHit: null,
      promptVersion: '',
      modelVersion: '',
      ruleVersion: '',
      evidenceSource: '',
      cacheKey: '',
      docScope: '',
      costClass: '',
      llmFallback: null,
      refined: null,
      refineReason: '',
      screeningStatus: '',
      finalDecisionSource: '',
      subitemAnchors: [],
    },
  }))
})

const effectiveStructuredIssues = computed<StructuredQCIssue[]>(() => {
  const source = structuredResult.value?.issues
  if (Array.isArray(source) && source.length > 0) return source
  return fallbackStructuredIssues.value
})

const documentTypeOptions = computed(() => {
  const set = new Set<string>()
  effectiveStructuredIssues.value.forEach((item) => {
    const label = String(item.documentType || '').trim()
    if (label) set.add(label)
  })
  return Array.from(set).map((value) => ({ label: value, value }))
})

const executionDomainOptions = computed(() => {
  const set = new Set<string>()
  effectiveStructuredIssues.value.forEach((item) => {
    const label = String(item.executionDomain || '').trim()
    if (label) set.add(label)
  })
  return Array.from(set).map((value) => ({ label: value, value }))
})

const defectLevelOptions = computed(() => {
  const set = new Set<string>()
  effectiveStructuredIssues.value.forEach((item) => {
    const label = String(item.defectLevel || '').trim()
    if (label) set.add(label)
  })
  return Array.from(set).map((value) => ({ label: value, value }))
})

const filteredIssues = computed(() => {
  const nextFilter: StructuredQCFilterState = {
    ...issueFilter.value,
    statusList: showAllStatuses.value ? [] : ['non_compliant', 'uncertain'],
  }
  return filterStructuredQCIssues(effectiveStructuredIssues.value, nextFilter)
})

const visibleGroups = computed(() => {
  const source = structuredResult.value?.groups || []
  const cards = source.filter((item) => item.kind !== 'rule')
  return cards.slice(0, 12)
})

const pagedIssues = computed<StructuredQCIssue[]>(() => {
  const pageSize = Math.max(1, Number(detailPagination.value.pageSize || 8))
  const current = Math.max(1, Number(detailPagination.value.current || 1))
  const start = (current - 1) * pageSize
  return filteredIssues.value.slice(start, start + pageSize)
})

watch(
  filteredIssues,
  (list) => {
    detailPagination.value.total = list.length
    if (
      detailPagination.value.current >
      Math.ceil(Math.max(1, list.length) / detailPagination.value.pageSize)
    ) {
      detailPagination.value.current = 1
    }
  },
  { immediate: true },
)

function handleDetailPageChange(page: number, pageSize?: number) {
  detailPagination.value.current = Number(page || 1)
  if (pageSize && Number.isFinite(pageSize)) {
    detailPagination.value.pageSize = Number(pageSize)
  }
}

// ==================== 辅助函数 ====================
function severityTagColor(sev: string) {
  return { error: 'error', warning: 'warning', info: 'processing' }[sev] || 'default'
}
function severityLabel(sev: string) {
  return { error: '严重', warning: '警告', info: '提示' }[sev] || '未知'
}

function statusTagColor(status: StructuredQCStatus) {
  if (status === 'non_compliant') return 'error'
  if (status === 'uncertain') return 'warning'
  if (status === 'not_applicable') return 'default'
  if (status === 'failed' || status === 'error') return 'error'
  return 'success'
}

function subitemAnchorDisplayLabel(anchor: StructuredQCSubitemAnchor) {
  return getSubitemAnchorDisplayLabel(anchor)
}

function subitemAnchorTagColor(status: string) {
  if (status === 'data_quality_gap') return 'default'
  return 'warning'
}

function formatConfidence(value: number | string | undefined) {
  const numeric = Number(value || 0)
  if (!Number.isFinite(numeric) || numeric <= 0) return '-'
  return numeric.toFixed(2)
}

function toSeverityByStatus(status: StructuredQCStatus): ContentIssue['severity'] {
  if (status === 'non_compliant' || status === 'failed' || status === 'error') return 'error'
  if (status === 'uncertain') return 'warning'
  return 'info'
}

function toContentIssue(item: StructuredQCIssue, fallbackGroup = '整份病历'): ContentIssue {
  return {
    ruleId: item.ruleId || item.ruleCode,
    ruleName: item.ruleName || item.ruleCode || '未知规则',
    severity: toSeverityByStatus(item.status),
    group: item.documentType || fallbackGroup,
    description: item.findings || '未提供详细说明',
    suggestion: item.suggestion || '',
  }
}

function resetIssueFilter() {
  issueFilter.value = createDefaultStructuredQCFilter()
  showAllStatuses.value = false
  activeGroupKey.value = ''
}

function applyGroupFilter(group: { key: string; kind: string; label: string }) {
  activeGroupKey.value = activeGroupKey.value === group.key ? '' : group.key
  if (!activeGroupKey.value) {
    resetIssueFilter()
    return
  }
  if (group.kind === 'status') {
    const map: Record<string, StructuredQCStatus> = {
      不合规: 'non_compliant',
      待复核: 'uncertain',
      合规: 'compliant',
      不适用: 'not_applicable',
      失败: 'failed',
      错误: 'error',
    }
    const status = map[group.label]
    if (status) {
      showAllStatuses.value = true
      issueFilter.value.statusList = [status]
    }
    return
  }
  if (group.kind === 'document') {
    issueFilter.value.documentType = group.label
    return
  }
  if (group.kind === 'domain') {
    issueFilter.value.executionDomain = group.label
    return
  }
  if (group.kind === 'defect') {
    issueFilter.value.defectLevel = group.label
    return
  }
}

function openIssueDetail(issue: StructuredQCIssue) {
  issueDetailRecord.value = issue
  issueDetailOpen.value = true
}

async function loadFullDocumentsForAnalysis(): Promise<DocItem[]> {
  const patientId = String(props.patientId || '').trim()
  const visitId = String(props.visitId || '').trim()
  if (!patientId || !visitId) return []
  const visitKey = `${patientId}::${String(props.instituteId || '').trim()}::${visitId}`
  if (fullDocumentsVisitKey.value === visitKey) return fullDocumentsCache.value
  if (fullDocumentsRequest) return fullDocumentsRequest

  fullDocumentsRequest = (async () => {
    try {
      const response = await axios.get(`/api/v1/emr/${encodeURIComponent(visitId)}/documents`, {
        params: {
          patient_id: patientId,
          ...(props.instituteId ? { institute_id: props.instituteId } : {}),
          visit_id: visitId,
          view: 'full',
        },
        timeout: LONG_REQUEST_TIMEOUT_MS,
      })
      const payload = response.data?.data || response.data || {}
      const rawDocuments = Array.isArray(payload.documents) ? payload.documents : []
      const documents = rawDocuments.filter(
        (doc: unknown): doc is DocItem =>
          !!doc && typeof doc === 'object' && 'content' in doc && Boolean((doc as DocItem).content),
      )
      const currentVisitKey = `${String(props.patientId || '').trim()}::${String(props.instituteId || '').trim()}::${String(props.visitId || '').trim()}`
      if (currentVisitKey !== visitKey) return []
      if (documents.length) {
        fullDocumentsCache.value = documents
        fullDocumentsVisitKey.value = visitKey
      }
      return documents
    } catch (error) {
      console.warn('内涵质控按需加载完整文书失败:', error)
      return []
    } finally {
      fullDocumentsRequest = null
    }
  })()
  return fullDocumentsRequest
}

async function copyIssueEvidence(issue: StructuredQCIssue) {
  const payload = issue.evidence || issue.findings || ''
  if (!payload) {
    message.warning('当前问题没有可复制内容')
    return
  }
  try {
    await navigator.clipboard.writeText(payload)
    message.success('证据已复制')
  } catch {
    message.error('复制失败，请手动复制')
  }
}

function resolveScene(): 'running' | 'final' {
  const rawScene = String(props.scene || '')
    .trim()
    .toLowerCase()
  if (rawScene === 'running') return 'running'
  if (rawScene === 'final') return 'final'
  return 'final'
}

// ==================== 回退链路：逐文书质控（旧模式） ====================

async function runContentQCLegacy(docs: DocItem[]) {
  totalSections.value = docs.length
  sectionTimeline.value = docs.map((d) => ({
    type: d.type,
    label: d.label,
    content: d.content || '',
    status: 'pending' as const,
  }))

  const allDocLabels = docs.map((d) => d.label).join('、')
  let allIssues: ContentIssue[] = []
  let allStructuredIssues: StructuredQCIssue[] = []
  const allRuleIds = new Set<string>()
  const problemRuleIds = new Set<string>()
  const startTime = Date.now()

  for (let i = 0; i < sectionTimeline.value.length; i++) {
    const sec = sectionTimeline.value[i]
    sec.status = 'active'

    // PG 表名 → 质控引擎文书类型
    const qcDocType = TABLE_TO_DOC_TYPE[sec.type] || sec.label

    const secStart = Date.now()

    try {
      // 构建上下文：PG 已经按表分好了，明确告知 LLM 文书类型
      const contextPrefix = [
        `【重要上下文】当前正在评估的文书类型是「${qcDocType}」。`,
        `该患者病历中包含以下文书：${allDocLabels}。`,
        `以下内容即为该患者的「${qcDocType}」全文，来自数据库 ${sec.type} 表：`,
        '',
      ].join('\n')

      const resp = await axios.post(
        '/api/v1/qc/sichuan/evaluate',
        {
          document_id: `${props.patientId}-${props.visitId}-${sec.type}`,
          document_content: contextPrefix + sec.content,
          document_type: qcDocType,
          patient_info: {
            current_document_type: qcDocType,
            current_table: sec.type,
            available_documents: docs.map((d) => TABLE_TO_DOC_TYPE[d.type] || d.label).join('、'),
            patient_id: props.patientId || '',
            visit_id: props.visitId || '',
          },
          persist: false,
          prompt_mode: 'plan_a',
        },
        { timeout: LONG_REQUEST_TIMEOUT_MS },
      )

      const data = extractApiData<any>(resp.data, '文书质控失败')
      const secDuration = ((Date.now() - secStart) / 1000).toFixed(1)

      if (data?.status === 'success' || data?.evaluation_summary) {
        const structured = mapSichuanEvaluationToStructuredQC(data, { docCount: 1 })
        const normalizedIssues = structured.issues.map((item) => ({
          ...item,
          documentType: item.documentType || sec.label,
        }))
        const secIssues = normalizedIssues
          .filter((item) => isProblemStatus(item.status))
          .map((item) => toContentIssue(item, sec.label))

        for (const item of normalizedIssues) {
          const key = item.ruleId || item.ruleCode
          if (key) {
            allRuleIds.add(key)
            if (isProblemStatus(item.status)) {
              problemRuleIds.add(key)
            }
          }
        }
        allStructuredIssues = [...allStructuredIssues, ...normalizedIssues]

        // 更新时间线
        sec.status = 'done'
        sec.ruleCount = structured.overview.totalRules || normalizedIssues.length
        sec.issueCount = secIssues.length
        sec.duration = secDuration
        sec.issues = secIssues

        // 累加问题
        allIssues = [...allIssues, ...secIssues]

        completedSections.value.push({ ...sec })

        // 实时更新问题列表和 badge 计数
        issues.value = [...allIssues]
        emit('issues-change', allIssues.length)
      } else {
        sec.status = 'done'
        sec.ruleCount = 0
        sec.issueCount = 0
        sec.duration = secDuration
        completedSections.value.push({ ...sec })
      }
    } catch (err: any) {
      const secDuration = ((Date.now() - secStart) / 1000).toFixed(1)
      console.error(`质控 ${sec.label} 失败:`, err)
      sec.status = 'done'
      sec.ruleCount = 0
      sec.issueCount = -1 // 标记失败
      sec.duration = secDuration
      completedSections.value.push({ ...sec })
    }
  }

  // 3. 汇总（按 rule_id 去重后的唯一规则数）
  const totalDuration = (Date.now() - startTime) / 1000
  const uniqueRuleCount = allRuleIds.size
  const compliantCount = uniqueRuleCount - problemRuleIds.size
  const legacyStructuredResult = mapSichuanEvaluationToStructuredQC(
    {
      evaluation_summary: {
        total_rules: uniqueRuleCount,
        compliance_rate:
          uniqueRuleCount > 0 ? Math.round((compliantCount / uniqueRuleCount) * 10000) / 100 : null,
        issues_found: allIssues.length,
      },
      evaluation_results: allStructuredIssues.map((item) => ({
        rule_id: item.ruleId,
        rule_code: item.ruleCode,
        rule_name: item.ruleName,
        status: item.status,
        findings: item.findings,
        evidence: item.evidence,
        suggestion: item.suggestion,
        confidence: item.confidence,
        document_type: item.documentType,
        execution_domain: item.executionDomain,
        rule_family: item.ruleFamily,
        defect_level: item.defectLevel,
        executor_type: item.executorType,
        record_id: item.recordId,
        visit_id: item.visitId,
        patient_name: item.patientName,
        department: item.department,
        metadata: {
          trace_id: item.metadata.traceId,
          cache_hit: item.metadata.cacheHit,
          prompt_version: item.metadata.promptVersion,
          model_version: item.metadata.modelVersion,
          rule_version: item.metadata.ruleVersion,
          evidence_source: item.metadata.evidenceSource,
          cache_key: item.metadata.cacheKey,
          doc_scope: item.metadata.docScope,
          cost_class: item.metadata.costClass,
          llm_fallback: item.metadata.llmFallback,
          refined: item.metadata.refined,
          refine_reason: item.metadata.refineReason,
          screening_status: item.metadata.screeningStatus,
          final_decision_source: item.metadata.finalDecisionSource,
          subitem_anchors: item.metadata.subitemAnchors,
        },
      })),
    },
    { docCount: sectionTimeline.value.length },
  )
  structuredResult.value = {
    ...legacyStructuredResult,
    overview: {
      ...legacyStructuredResult.overview,
      processingTimeSeconds: Math.round(totalDuration * 100) / 100,
    },
  }
  summary.value = structuredResult.value.overview

  analyzed.value = true
  loading.value = false

  if (uniqueRuleCount <= 0) {
    message.warning('本次未加载到可执行规则，请检查文书类型映射或规则来源')
  } else if (allIssues.length === 0) {
    message.success(
      `内涵质控通过（${totalDuration.toFixed(1)}s，${sectionTimeline.value.length} 个文书）`,
    )
  } else {
    message.warning(`发现 ${allIssues.length} 个问题（${totalDuration.toFixed(1)}s）`)
  }
}

// ==================== 主链路：单次 bundle 评估 ====================

async function runContentQCBundle(docs: DocItem[]): Promise<boolean> {
  if (!props.instituteId || !props.patientId || !props.visitId) {
    return false
  }

  loading.value = true
  analyzed.value = false
  issues.value = []
  summary.value = null
  structuredResult.value = null
  completedSections.value = []
  totalSections.value = 1
  sectionTimeline.value = [
    {
      type: 'bundle',
      label: 'Bundle 证据链',
      content: '',
      status: 'pending',
    },
  ]
  const bundleSection = sectionTimeline.value[0]
  if (bundleSection) {
    bundleSection.status = 'active'
  }
  const startTime = Date.now()

  try {
    const response = await evaluateSichuanBundleQC({
      scene: resolveScene(),
      institute_id: props.instituteId,
      patient_id: props.patientId,
      visit_id: props.visitId,
    })

    if (!response.success || !response.data) {
      throw new Error(response.message || 'Bundle 质控失败')
    }

    const data = response.data as any
    const mapped = mapSichuanEvaluationToStructuredQC(data, { docCount: docs.length })
    const allIssues = mapped.issues
      .filter((item) => isProblemStatus(item.status))
      .map((item) => toContentIssue(item, '整份病历'))

    if (bundleSection) {
      bundleSection.status = 'done'
      bundleSection.ruleCount = mapped.overview.totalRules
      bundleSection.issueCount = allIssues.length
      bundleSection.duration = ((Date.now() - startTime) / 1000).toFixed(1)
      bundleSection.issues = allIssues.slice(0, 3)
      completedSections.value = [{ ...bundleSection }]
    }

    structuredResult.value = mapped
    issues.value = allIssues
    summary.value = mapped.overview
    analyzed.value = true
    loading.value = false
    emit('issues-change', mapped.overview.issueCount)
    if (mapped.overview.totalRules <= 0) {
      message.warning('本次未加载到可执行规则，请检查规则来源、场景或病历标识')
    } else if (allIssues.length === 0) {
      message.success('内涵质控通过（Bundle）')
    } else {
      message.warning(`发现 ${allIssues.length} 个问题（Bundle）`)
    }
    return true
  } catch (error: any) {
    console.error('Bundle 质控失败，准备回退旧链路:', error)
    loading.value = false
    sectionTimeline.value = []
    totalSections.value = 0
    return false
  }
}

// ==================== 统一入口 ====================

async function runContentQC() {
  if (!props.patientId) {
    message.warning('请先选择病历')
    return
  }

  let docs = (props.documents || []).filter((d) => d.has_content && d.content)
  // summary 目录只包含长度和身份信息；真正逐文书分析前按需读取 full 视图。
  if (!docs.length || (props.documents || []).some((d) => d.has_content && !d.content)) {
    docs = await loadFullDocumentsForAnalysis()
  }
  if (docs.length === 0) {
    message.warning('该患者暂无病历文书内容，请先加载文书')
    return
  }

  const bundleDone = await runContentQCBundle(docs)
  if (bundleDone) {
    return
  }

  message.warning('Bundle 评估不可用，已回退逐文书模式')
  loading.value = true
  analyzed.value = false
  issues.value = []
  summary.value = null
  structuredResult.value = null
  completedSections.value = []
  await runContentQCLegacy(docs)
}

// 切换患者时重置
watch(
  () => [props.patientId, props.visitId, props.instituteId],
  () => {
    fullDocumentsVisitKey.value = ''
    fullDocumentsCache.value = []
    fullDocumentsRequest = null
    analyzed.value = false
    issues.value = []
    summary.value = null
    structuredResult.value = null
    resetIssueFilter()
    issueDetailOpen.value = false
    issueDetailRecord.value = null
    completedSections.value = []
    sectionTimeline.value = []
    emit('issues-change', 0)
  },
)
</script>

<style scoped>
.content-qc-tab {
  min-height: 0;
  height: 100%;
  display: flex;
  flex-direction: column;
  background: transparent;
  border: none;
  border-radius: 18px;
  box-shadow: none;
  overflow: hidden;
}

.content-qc-tab__header {
  flex-shrink: 0;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
  padding: 14px 16px;
  border-radius: 18px;
  background:
    radial-gradient(circle at top right, rgba(14, 165, 233, 0.08), transparent 32%),
    linear-gradient(180deg, rgba(255, 255, 255, 0.94), rgba(247, 250, 252, 0.98));
  border: 1px solid rgba(226, 232, 240, 0.88);
  box-shadow: 0 10px 22px rgba(15, 23, 42, 0.04);
}

.content-qc-tab__header-main {
  min-width: 0;
  flex: 1;
}

.content-qc-tab__eyebrow {
  margin-bottom: 6px;
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--mq-brand-700);
}

.content-qc-tab__header-desc {
  margin-top: 6px;
  max-width: 280px;
  font-size: 12px;
  line-height: 1.6;
  color: var(--mq-text-tertiary);
}

.content-qc-tab__header-action {
  flex-shrink: 0;
  margin-top: 2px;
  padding-inline: 0 !important;
  font-size: 12px !important;
  font-weight: 700 !important;
}

@media (max-width: 520px) {
  .content-qc-tab__header {
    flex-direction: column;
  }
}

.header-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.header-icon {
  color: var(--mq-brand-700);
  font-size: 15px;
}

.header-title {
  font-size: 15px;
  font-weight: 800;
  color: var(--mq-text-primary);
}

/* ========== 进度时间线 ========== */
.content-qc-tab__progress {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 0;
  background: transparent;
}

.progress-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 14px;
  padding: 12px 14px;
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.78);
  border: 1px solid rgba(226, 232, 240, 0.9);
  box-shadow: 0 8px 18px rgba(15, 23, 42, 0.04);
}

.progress-avatar {
  width: 38px;
  height: 38px;
  border-radius: 11px;
  background: linear-gradient(135deg, var(--mq-brand-400), var(--mq-brand-700));
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 4px 10px rgba(37, 99, 235, 0.18);
}

.progress-title {
  font-size: 14px;
  font-weight: 800;
  color: var(--mq-text-primary);
}

.progress-sub {
  font-size: 11px;
  color: var(--mq-text-tertiary);
  margin-top: 2px;
}

.progress-bar-wrap {
  margin-bottom: 14px;
  padding: 0 2px;
}

.progress-bar-bg {
  height: 6px;
  border-radius: 999px;
  background: color-mix(in srgb, var(--mq-neutral-text) 13%, var(--mq-bg-surface));
  overflow: hidden;
}

.progress-bar-fill {
  height: 100%;
  border-radius: 999px;
  background: linear-gradient(90deg, var(--mq-brand-400), var(--mq-brand-700));
  transition: width 0.5s ease;
}

.progress-timeline {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.timeline-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 12px;
  border-radius: 14px;
  border: 1px solid rgba(226, 232, 240, 0.9);
  box-shadow: 0 6px 16px rgba(15, 23, 42, 0.035);
  transition: all 0.3s ease;
}

.timeline-done {
  background: linear-gradient(180deg, color-mix(in srgb, var(--mq-brand-600) 6%, var(--mq-bg-surface)), color-mix(in srgb, var(--mq-brand-600) 3%, var(--mq-bg-surface)));
}
.timeline-active {
  background: linear-gradient(180deg, color-mix(in srgb, var(--mq-brand-600) 6%, var(--mq-bg-surface)), color-mix(in srgb, var(--mq-brand-600) 3%, var(--mq-bg-surface)));
  animation: pulse-bg 2s infinite;
}
.timeline-pending {
  background: rgba(255, 255, 255, 0.72);
}

@keyframes pulse-bg {
  0%,
  100% {
    background: color-mix(in srgb, var(--mq-brand-600) 6%, var(--mq-bg-surface));
  }
  50% {
    background: color-mix(in srgb, var(--mq-brand-600) 14%, var(--mq-bg-surface));
  }
}

.timeline-dot {
  width: 20px;
  height: 20px;
  border-radius: 999px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  margin-top: 1px;
}

.timeline-dot--done {
  background: var(--mq-brand-600);
}
.timeline-dot--active {
  background: var(--mq-brand-400);
}
.timeline-dot--pending {
  background: color-mix(in srgb, var(--mq-neutral-text) 13%, var(--mq-bg-surface));
}

.dot-ping {
  width: 8px;
  height: 8px;
  border-radius: 999px;
  background: var(--mq-bg-surface);
  animation: ping 1s cubic-bezier(0, 0, 0.2, 1) infinite;
}

.dot-idle {
  width: 6px;
  height: 6px;
  border-radius: 999px;
  background: var(--mq-text-disabled);
}

@keyframes ping {
  75%,
  100% {
    transform: scale(1.8);
    opacity: 0;
  }
}

.timeline-content {
  flex: 1;
  min-width: 0;
}

.timeline-title-row {
  display: flex;
  align-items: center;
  gap: 6px;
}

.timeline-label {
  font-size: 12px;
  font-weight: 700;
}

.timeline-label--done {
  color: var(--mq-brand-700);
}
.timeline-label--active {
  color: var(--mq-brand-700);
}
.timeline-label--pending {
  color: var(--mq-text-tertiary);
}

.timeline-time {
  font-size: 10px;
  color: var(--mq-text-tertiary);
  font-variant-numeric: tabular-nums;
}

.timeline-active-hint {
  font-size: 10px;
  color: var(--mq-brand-400);
  font-weight: 600;
}

.timeline-result {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-top: 4px;
}

.result-tag {
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 4px;
  font-weight: 600;
}

.result-tag--issues {
  background: color-mix(in srgb, var(--mq-danger-icon) 7%, var(--mq-bg-surface));
  color: color-mix(in srgb, var(--mq-danger-text) 90%, var(--mq-text-primary));
}

.result-tag--pass {
  background: color-mix(in srgb, var(--mq-brand-600) 14%, var(--mq-bg-surface));
  color: var(--mq-brand-700);
}

.timeline-issues {
  margin-top: 4px;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.timeline-issue-item {
  display: flex;
  align-items: center;
  gap: 4px;
}

.issue-text {
  font-size: 11px;
  color: var(--mq-neutral-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.timeline-issue-more {
  font-size: 10px;
  color: var(--mq-text-tertiary);
  padding-left: 4px;
}

/* ========== 空态、结果 ========== */
.content-qc-tab__empty {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 268px;
  padding: 40px 22px;
  text-align: center;
  border-radius: 20px;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.94), rgba(248, 251, 255, 0.98));
  border: 1px dashed rgba(147, 197, 253, 0.52);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.82),
    0 16px 34px rgba(148, 163, 184, 0.1);
}

.empty-icon-wrap {
  width: 56px;
  height: 56px;
  border-radius: 16px;
  background: linear-gradient(180deg, color-mix(in srgb, var(--mq-brand-600) 6%, var(--mq-bg-surface)), color-mix(in srgb, var(--mq-brand-600) 14%, var(--mq-bg-surface)));
  border: 1px solid var(--mq-brand-200);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 18px;
  box-shadow:
    0 10px 20px rgba(59, 130, 246, 0.12),
    inset 0 1px 0 rgba(255, 255, 255, 0.72);
}

.empty-icon {
  font-size: 24px;
  color: var(--mq-brand-700);
}
.empty-title {
  font-size: 15px;
  font-weight: 800;
  color: var(--mq-text-primary);
  margin-bottom: 6px;
}
.empty-desc {
  font-size: 12px;
  color: var(--mq-text-tertiary);
  line-height: 1.6;
  margin-bottom: 18px;
  max-width: 228px;
}
.empty-btn {
  border-radius: 999px !important;
  box-shadow:
    0 10px 20px rgba(37, 99, 235, 0.18),
    inset 0 1px 0 rgba(255, 255, 255, 0.14) !important;
}

.content-qc-tab__body {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  padding: 0;
  background: transparent;
}

.summary-card {
  flex-shrink: 0;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  padding: 12px;
  background: radial-gradient(circle at top right, rgba(14, 165, 233, 0.08), transparent 30%), var(--mq-bg-surface);
  border: 1px solid color-mix(in srgb, var(--mq-neutral-text) 13%, var(--mq-bg-surface));
  border-radius: 16px;
  margin-bottom: 12px;
  box-shadow: 0 8px 18px rgba(15, 23, 42, 0.035);
}

.summary-card__hero {
  grid-column: 1 / -1;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  padding: 4px 4px 8px;
  border-bottom: 1px solid rgba(226, 232, 240, 0.7);
  margin-bottom: 2px;
}

.summary-card__eyebrow {
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--mq-brand-700);
  margin-bottom: 4px;
}

.summary-card__title {
  font-size: 15px;
  font-weight: 800;
  color: var(--mq-text-primary);
}

.summary-card__progress {
  min-width: 64px;
  padding: 10px 12px;
  border-radius: 12px;
  background: linear-gradient(180deg, color-mix(in srgb, var(--mq-brand-600) 6%, var(--mq-bg-surface)), color-mix(in srgb, var(--mq-brand-600) 14%, var(--mq-bg-surface)));
  color: var(--mq-brand-700);
  text-align: center;
  font-size: 18px;
  line-height: 1;
  font-weight: 800;
}

.summary-card__warning {
  grid-column: 1 / -1;
  border-radius: 12px;
  padding: 8px 10px;
  border: 1px solid rgba(245, 158, 11, 0.35);
  background: rgba(255, 247, 237, 0.92);
  color: color-mix(in srgb, var(--mq-warning-text) 70%, var(--mq-text-primary));
  font-size: 12px;
  line-height: 1.6;
}

.summary-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 4px 8px;
}

.summary-row--action {
  border-radius: 10px;
  background: color-mix(in srgb, var(--mq-warning-icon) 8%, var(--mq-bg-surface));
}

.summary-link {
  padding: 0;
  border: 0;
  background: transparent;
  color: color-mix(in srgb, var(--mq-warning-text) 89%, var(--mq-text-primary));
  font-size: 12px;
  font-weight: 800;
  cursor: pointer;
}

.summary-link:hover {
  color: color-mix(in srgb, var(--mq-warning-text) 70%, var(--mq-text-primary));
}

.summary-label {
  font-size: 11px;
  color: var(--mq-text-tertiary);
  font-weight: 600;
}
.summary-value {
  font-size: 13px;
  font-weight: 800;
  color: var(--mq-text-primary);
}

.result-toolbar {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 10px;
}

.result-view-switch :deep(.ant-radio-button-wrapper) {
  font-size: 12px;
}

.result-toolbar-meta {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: var(--mq-text-tertiary);
}

.group-panel {
  flex-shrink: 0;
  margin-bottom: 10px;
  border: 1px solid color-mix(in srgb, var(--mq-neutral-text) 13%, var(--mq-bg-surface));
  border-radius: 14px;
  padding: 10px;
  background: rgba(255, 255, 255, 0.9);
}

.group-panel-title {
  font-size: 12px;
  font-weight: 700;
  color: var(--mq-neutral-text);
  margin-bottom: 8px;
}

.group-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 8px;
}

.group-chip {
  border: 1px solid color-mix(in srgb, var(--mq-neutral-text) 13%, var(--mq-bg-surface));
  border-radius: 10px;
  background: var(--mq-bg-surface);
  padding: 8px 10px;
  text-align: left;
  cursor: pointer;
  transition:
    border-color 0.2s ease,
    box-shadow 0.2s ease;
}

.group-chip:hover {
  border-color: color-mix(in srgb, var(--mq-brand-600) 46%, var(--mq-bg-surface));
}

.group-chip--active {
  border-color: color-mix(in srgb, var(--mq-brand-400) 82%, var(--mq-bg-surface));
  box-shadow: 0 0 0 2px rgba(191, 219, 254, 0.5);
}

.group-chip__label {
  display: block;
  font-size: 12px;
  font-weight: 700;
  color: var(--mq-text-primary);
}

.group-chip__meta {
  display: block;
  margin-top: 2px;
  font-size: 11px;
  color: var(--mq-text-tertiary);
}

.filter-panel {
  flex-shrink: 0;
  display: grid;
  grid-template-columns: minmax(180px, 1.4fr) repeat(3, minmax(110px, 1fr)) auto;
  gap: 8px;
  margin-bottom: 10px;
}

.filter-item {
  min-width: 0;
}

.filter-item--keyword :deep(.ant-input) {
  font-size: 12px;
}

.issue-card-list {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
  overflow-y: auto;
  overscroll-behavior: contain;
  padding: 0 2px 16px 0;
}

.issue-card {
  border-radius: 14px;
  border: 1px solid color-mix(in srgb, var(--mq-neutral-text) 13%, var(--mq-bg-surface));
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.97), rgba(248, 251, 255, 0.98));
  box-shadow: 0 8px 18px rgba(15, 23, 42, 0.035);
  padding: 10px 10px 8px;
}

.issue-card--non_compliant {
  border-color: rgba(248, 113, 113, 0.45);
}

.issue-card--uncertain {
  border-color: rgba(251, 191, 36, 0.46);
}

.issue-card__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.issue-card__status {
  margin-right: 0;
}

.issue-card__code {
  font-size: 12px;
  font-weight: 800;
  color: var(--mq-text-primary);
  font-family: 'SF Mono', 'Cascadia Code', 'Fira Code', monospace;
}

.issue-card__title {
  margin-top: 6px;
  font-size: 13px;
  font-weight: 800;
  color: var(--mq-text-primary);
  line-height: 1.45;
}

.issue-card__findings {
  margin-top: 6px;
  font-size: 12px;
  color: var(--mq-text-primary);
  line-height: 1.55;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.issue-card__suggestion {
  margin-top: 6px;
  font-size: 12px;
  color: var(--mq-brand-700);
  line-height: 1.55;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  background: rgba(239, 246, 255, 0.9);
  border: 1px solid rgba(191, 219, 254, 0.85);
  border-radius: 8px;
  padding: 6px 8px;
}

.issue-card__subitem-anchors {
  margin-top: 8px;
  padding: 8px;
  border-radius: 12px;
  border: 1px solid color-mix(in srgb, var(--mq-warning-icon) 25%, var(--mq-bg-surface));
  background: color-mix(in srgb, var(--mq-warning-icon) 8%, var(--mq-bg-surface));
}

.subitem-anchor-head,
.subitem-anchor__top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.subitem-anchor-head {
  margin-bottom: 6px;
  font-size: 11px;
  font-weight: 800;
  color: color-mix(in srgb, var(--mq-warning-text) 70%, var(--mq-text-primary));
}

.subitem-anchor {
  padding: 7px 8px;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.82);
  border: 1px solid rgba(253, 230, 138, 0.82);
}

.subitem-anchor + .subitem-anchor {
  margin-top: 6px;
}

.subitem-anchor--detail {
  background: var(--mq-bg-surface);
}

.subitem-anchor__name {
  min-width: 0;
  font-size: 12px;
  font-weight: 800;
  color: var(--mq-text-primary);
}

.subitem-anchor__tag {
  flex-shrink: 0;
  margin-right: 0;
}

.subitem-anchor__parent,
.subitem-anchor__evidence,
.subitem-anchor__reason {
  margin-top: 6px;
  font-size: 12px;
  line-height: 1.55;
  color: var(--mq-neutral-text);
  white-space: pre-wrap;
  word-break: break-word;
}

.subitem-anchor__reason {
  color: color-mix(in srgb, var(--mq-warning-text) 70%, var(--mq-text-primary));
}

.issue-card__subitem-anchors .subitem-anchor__evidence {
  max-height: 120px;
  overflow: auto;
}

.subitem-anchor--detail .subitem-anchor__evidence {
  max-height: 240px;
  overflow: auto;
}

.issue-card__meta {
  margin-top: 7px;
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.issue-card__chip {
  margin: 0;
  font-size: 11px;
  color: var(--mq-neutral-text);
  border-color: rgba(203, 213, 225, 0.85);
  background: rgba(248, 250, 252, 0.92);
}

.issue-card__advanced {
  margin-top: 8px;
  display: grid;
  grid-template-columns: 1fr;
  gap: 3px;
  padding: 7px 8px;
  border-radius: 8px;
  border: 1px dashed rgba(191, 219, 254, 0.95);
  background: rgba(239, 246, 255, 0.55);
  font-size: 11px;
  line-height: 1.5;
  color: var(--mq-text-tertiary);
}

.issue-card__actions {
  margin-top: 6px;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 2px;
}

.advanced-cell {
  display: flex;
  flex-direction: column;
  gap: 2px;
  font-size: 11px;
  color: var(--mq-text-tertiary);
  line-height: 1.5;
}

.advanced-cell--detail {
  font-size: 12px;
  color: var(--mq-neutral-text);
}

.detail-pagination {
  flex-shrink: 0;
  display: flex;
  justify-content: flex-end;
  margin-top: 10px;
}

.issue-detail-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.issue-detail-item {
  border: 1px solid color-mix(in srgb, var(--mq-neutral-text) 13%, var(--mq-bg-surface));
  border-radius: 10px;
  padding: 8px 10px;
  background: color-mix(in srgb, var(--mq-neutral-text) 3%, var(--mq-bg-surface));
}

.issue-detail-label {
  display: block;
  font-size: 11px;
  color: var(--mq-text-tertiary);
}

.issue-detail-value {
  display: block;
  margin-top: 4px;
  font-size: 12px;
  color: var(--mq-text-primary);
  font-weight: 700;
}

.issue-detail-block {
  margin-top: 12px;
  border: 1px solid color-mix(in srgb, var(--mq-neutral-text) 13%, var(--mq-bg-surface));
  border-radius: 10px;
  padding: 10px;
  background: var(--mq-bg-surface);
}

.issue-detail-block__title {
  font-size: 12px;
  font-weight: 700;
  color: var(--mq-neutral-text);
  margin-bottom: 6px;
}

.issue-detail-block__content {
  font-size: 12px;
  line-height: 1.6;
  color: var(--mq-text-primary);
  white-space: pre-wrap;
}

.issue-detail-subitem-list,
.subitem-anchor-modal {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.subitem-anchor-modal__hint {
  padding: 9px 10px;
  border-radius: 12px;
  background: color-mix(in srgb, var(--mq-neutral-text) 3%, var(--mq-bg-surface));
  color: var(--mq-neutral-text);
  font-size: 12px;
  line-height: 1.55;
}

.issue-group {
  margin-bottom: 12px;
}

.group-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  background: rgba(255, 255, 255, 0.82);
  border: 1px solid color-mix(in srgb, var(--mq-neutral-text) 13%, var(--mq-bg-surface));
  border-radius: 12px;
  margin-bottom: 8px;
}

.group-dot {
  width: 8px;
  height: 8px;
  border-radius: 999px;
  flex-shrink: 0;
}
.group-title {
  font-size: 12px;
  font-weight: 700;
  color: var(--mq-neutral-text);
}
.group-count {
  font-size: 11px;
  color: var(--mq-text-tertiary);
}

.issue-item {
  background: var(--mq-bg-surface);
  border: 1px solid color-mix(in srgb, var(--mq-neutral-text) 13%, var(--mq-bg-surface));
  border-radius: 14px;
  padding: 12px;
  margin-bottom: 8px;
  box-shadow: 0 6px 16px rgba(15, 23, 42, 0.035);
  transition:
    transform 0.15s ease,
    box-shadow 0.15s ease,
    border-color 0.15s ease;
}

.issue-item:hover {
  transform: translateY(-1px);
  border-color: rgba(147, 197, 253, 0.95);
  box-shadow: 0 10px 22px rgba(15, 23, 42, 0.05);
}

.issue-top {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}
.issue-rule {
  font-size: 12px;
  font-weight: 700;
  color: var(--mq-neutral-text);
}
.issue-desc {
  font-size: 13px;
  color: var(--mq-text-primary);
  line-height: 1.6;
}
.issue-suggestion {
  margin-top: 6px;
  background: linear-gradient(180deg, rgba(255, 247, 237, 0.9), rgba(255, 251, 235, 0.9));
  border-left: 3px solid var(--mq-warning-icon);
  color: color-mix(in srgb, var(--mq-warning-text) 70%, var(--mq-text-primary));
  font-size: 12px;
  padding: 6px 8px;
  border-radius: 0 8px 8px 0;
  line-height: 1.5;
}

.content-qc-tab__empty-result {
  flex: 1;
  min-height: 200px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.62);
  border: 1px dashed rgba(147, 197, 253, 0.52);
}

.empty-result-icon {
  font-size: 30px;
  color: var(--mq-brand-700);
  margin-bottom: 10px;
}
.empty-result-text {
  font-size: 13px;
  font-weight: 700;
  color: var(--mq-neutral-text);
}

.content-qc-tab__footer {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 0 0;
  border-top: none;
  background: transparent;
  font-size: 12px;
  color: var(--mq-neutral-text);
}

@media (max-width: 520px) {
  .content-qc-tab {
    min-height: 100%;
    height: auto;
  }

  .content-qc-tab__body {
    overflow: visible;
  }

  .issue-card-list {
    flex: none;
    overflow: visible;
    padding-right: 0;
  }

  .result-toolbar {
    flex-direction: column;
    align-items: flex-start;
  }

  .filter-panel {
    grid-template-columns: 1fr;
  }

  .issue-detail-grid {
    grid-template-columns: 1fr;
  }

  .summary-card {
    grid-template-columns: 1fr;
  }

  .summary-card__hero {
    flex-direction: column;
  }
}

.ml-auto {
  margin-left: auto;
}

.custom-scrollbar::-webkit-scrollbar {
  width: 4px;
}
.custom-scrollbar::-webkit-scrollbar-track {
  background: transparent;
}
.custom-scrollbar::-webkit-scrollbar-thumb {
  background: color-mix(in srgb, var(--mq-neutral-text) 26%, var(--mq-bg-surface));
  border-radius: 999px;
}

/* Apple workstation visual convergence */
.content-qc-tab {
  color: var(--mq-text-primary);
  font-family:
    'San Francisco', 'SF Pro Text', 'Source Han Sans SC', 'SF Pro Display', Inter, 'PingFang SC',
    'Microsoft YaHei UI', 'Microsoft YaHei', system-ui, sans-serif;
}

.content-qc-tab__header,
.progress-header,
.timeline-item,
.content-qc-tab__empty,
.summary-card,
.filter-panel,
.result-toolbar,
.issue-card,
.content-qc-tab__empty-result {
  border-color: rgba(0, 0, 0, 0.08) !important;
  background: rgba(255, 255, 255, 0.86) !important;
  -webkit-backdrop-filter: blur(18px);
  backdrop-filter: blur(18px);
  box-shadow:
    0 1px 4px rgba(0, 0, 0, 0.045),
    0 2px 8px rgba(0, 0, 0, 0.035) !important;
}

.content-qc-tab__header,
.summary-card,
.filter-panel,
.result-toolbar,
.issue-card {
  transition:
    border-color 0.25s cubic-bezier(0.25, 0.1, 0.25, 1),
    box-shadow 0.25s cubic-bezier(0.25, 0.1, 0.25, 1),
    transform 0.25s cubic-bezier(0.25, 0.1, 0.25, 1);
}

.content-qc-tab__header:hover,
.summary-card:hover,
.filter-panel:hover,
.result-toolbar:hover,
.issue-card:hover {
  border-color: rgba(0, 0, 0, 0.14) !important;
  box-shadow:
    0 2px 12px rgba(0, 0, 0, 0.1),
    0 6px 22px rgba(0, 0, 0, 0.075) !important;
  transform: translateY(-2px);
}

.content-qc-tab__eyebrow,
.header-icon,
.content-qc-tab__header-action,
.timeline-label--done,
.timeline-label--active,
.summary-card__eyebrow,
.summary-value,
.empty-icon,
.empty-result-icon {
  color: var(--mq-brand-700) !important;
}

.header-title,
.progress-title,
.summary-card__title,
.empty-title,
.issue-desc,
.empty-result-text {
  color: var(--mq-text-primary) !important;
  font-weight: 600 !important;
}

.content-qc-tab__header-desc,
.progress-sub,
.timeline-time,
.issue-rule,
.content-qc-tab__footer,
.timeline-issue-more {
  color: rgba(29, 29, 31, 0.56) !important;
}

.progress-avatar,
.progress-bar-fill,
.timeline-dot--done,
.timeline-dot--active {
  background: var(--mq-brand-600) !important;
}

.progress-avatar {
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.18),
    0 5px 14px rgba(10, 108, 255, 0.16) !important;
}

.timeline-pending,
.timeline-done,
.timeline-active {
  background: rgba(255, 255, 255, 0.72) !important;
}

.timeline-dot--pending,
.progress-bar-bg {
  background: rgba(0, 0, 0, 0.08) !important;
}

.result-tag--rules,
.result-tag--pass,
.empty-icon-wrap,
.summary-card__progress {
  border-color: var(--mq-info-border) !important;
  background: var(--mq-info-bg) !important;
  color: var(--mq-brand-600) !important;
}

.content-qc-tab__empty {
  border-style: dashed;
}

.issue-suggestion {
  background: rgba(245, 158, 11, 0.08) !important;
}

.custom-scrollbar::-webkit-scrollbar-thumb {
  background: rgba(0, 0, 0, 0.24);
}
</style>
