<template>
  <div class="content-qc-tab">
    <!-- 顶部操作栏 -->
    <div class="content-qc-tab__header">
      <div class="content-qc-tab__header-main">
        <div class="content-qc-tab__eyebrow">当前质控</div>
        <div class="header-left">
          <SafetyCertificateOutlined class="header-icon" />
          <span class="header-title">内涵质控</span>
          <a-tag v-if="totalCount > 0" color="error" size="small">{{ totalCount }}</a-tag>
        </div>
        <div class="content-qc-tab__header-desc">基于病历文书内容，检查诊疗逻辑、记录完整性与内涵一致性。</div>
      </div>
      <a-button
        type="link"
        size="small"
        class="content-qc-tab__header-action"
        @click="runContentQC"
        :loading="loading"
        :disabled="!patientId"
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
          <div class="progress-title">正在逐文书质控分析</div>
          <div class="progress-sub">已完成 {{ completedSections.length }} / {{ totalSections }} 个文书</div>
        </div>
        <a-spin class="ml-auto" />
      </div>

      <!-- 进度条 -->
      <div class="progress-bar-wrap">
        <div class="progress-bar-bg">
          <div class="progress-bar-fill" :style="{ width: `${progressPercent}%` }"></div>
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
            <span v-else-if="sec.status === 'active'" class="dot-ping"></span>
            <span v-else class="dot-idle"></span>
          </div>
          <!-- 内容 -->
          <div class="timeline-content">
            <div class="timeline-title-row">
              <span class="timeline-label" :class="`timeline-label--${sec.status}`">{{ sec.label }}</span>
              <span v-if="sec.duration" class="timeline-time">{{ sec.duration }}s</span>
              <span v-if="sec.status === 'active'" class="timeline-active-hint">分析中...</span>
            </div>
            <!-- 已完成的质控结果预览 -->
            <div v-if="sec.status === 'done' && sec.ruleCount !== undefined" class="timeline-result">
              <span class="result-tag result-tag--rules">{{ sec.ruleCount }} 条规则</span>
              <span v-if="sec.issueCount > 0" class="result-tag result-tag--issues">{{ sec.issueCount }} 个问题</span>
              <span v-else class="result-tag result-tag--pass">全部通过</span>
            </div>
            <!-- 发现的问题逐条展示 -->
            <div v-if="sec.status === 'done' && sec.issues && sec.issues.length > 0" class="timeline-issues">
              <div v-for="(iss, i) in sec.issues.slice(0, 3)" :key="i" class="timeline-issue-item">
                <a-tag :color="severityTagColor(iss.severity)" size="small" class="!text-[10px]">{{ severityLabel(iss.severity) }}</a-tag>
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
      <div class="empty-desc">基于 LLM 对病历全文进行深度语义校验，聚焦诊疗逻辑、病程记录完整性与知情同意等内涵质量。</div>
      <a-button
        type="primary"
        size="small"
        @click="runContentQC"
        :disabled="!patientId"
        class="empty-btn"
      >
        <template #icon><ThunderboltOutlined /></template>
        开始内涵质控
      </a-button>
    </div>

    <!-- 结果列表 -->
    <div v-else class="content-qc-tab__body custom-scrollbar">
      <!-- 汇总卡片 -->
      <div v-if="summary" class="summary-card">
        <div class="summary-card__hero">
          <div>
            <div class="summary-card__eyebrow">本次内涵质控</div>
            <div class="summary-card__title">逐文书语义校验结果</div>
          </div>
          <div class="summary-card__progress">{{ summary.complianceRate }}%</div>
        </div>
        <div class="summary-row">
          <span class="summary-label">总规则数</span>
          <span class="summary-value">{{ summary.totalRules }}</span>
        </div>
        <div class="summary-row">
          <span class="summary-label">合规率</span>
          <span class="summary-value" :class="complianceClass">{{ summary.complianceRate }}%</span>
        </div>
        <div class="summary-row">
          <span class="summary-label">发现问题</span>
          <span class="summary-value text-red-500">{{ summary.issuesFound }}</span>
        </div>
        <div class="summary-row">
          <span class="summary-label">文书数</span>
          <span class="summary-value">{{ summary.docCount }}</span>
        </div>
      </div>

      <!-- 文书分类结果 -->
      <template v-if="issues.length > 0">
        <section v-for="(group, gIdx) in groupedIssues" :key="gIdx" class="issue-group">
          <header class="group-header">
            <span class="group-dot" :style="{ background: severityColor(group.severity) }"></span>
            <span class="group-title">{{ group.title }}</span>
            <span class="group-count">({{ group.items.length }})</span>
          </header>
          <article v-for="(issue, iIdx) in group.items" :key="iIdx" class="issue-item">
            <div class="issue-top">
              <a-tag :color="severityTagColor(issue.severity)" size="small">{{ severityLabel(issue.severity) }}</a-tag>
              <span class="issue-rule">{{ issue.ruleName }}</span>
            </div>
            <div class="issue-desc">{{ issue.description }}</div>
            <div v-if="issue.suggestion" class="issue-suggestion">
              💡 {{ issue.suggestion }}
            </div>
          </article>
        </section>
      </template>

      <!-- 无问题 -->
      <div v-else class="content-qc-tab__empty-result">
        <CheckCircleOutlined class="empty-result-icon" />
        <div class="empty-result-text">内涵质控通过，未发现问题</div>
      </div>
    </div>

    <!-- 底部 -->
    <footer v-if="analyzed && !loading" class="content-qc-tab__footer">
      <span>共 <strong>{{ totalCount }}</strong> 个问题</span>
      <a-button type="link" size="small" @click="runContentQC" :loading="loading">
        <ReloadOutlined /> 重新分析
      </a-button>
    </footer>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, reactive } from 'vue'
import { message } from 'ant-design-vue'
import {
  SafetyCertificateOutlined,
  ReloadOutlined,
  ThunderboltOutlined,
  CheckCircleOutlined,
} from '@ant-design/icons-vue'
import axios from 'axios'

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
  complianceRate: number
  issuesFound: number
  docCount: number
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
  type: string       // PG 表名，如 admission_record
  label: string      // 中文文书名，如 "入院记录"
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
  documents?: DocItem[]   // 从 PG 各文书表查出的文书列表
}>()

const emit = defineEmits<{
  (e: 'issues-change', count: number): void
}>()

// ==================== 状态 ====================

const loading = ref(false)
const analyzed = ref(false)
const issues = ref<ContentIssue[]>([])
const summary = ref<ContentSummary | null>(null)
const completedSections = ref<SectionProgress[]>([])
const sectionTimeline = ref<SectionProgress[]>([])
const totalSections = ref(0)

const totalCount = computed(() => issues.value.length)
const progressPercent = computed(() =>
  totalSections.value > 0
    ? Math.round((completedSections.value.length / totalSections.value) * 100)
    : 0,
)

const complianceClass = computed(() => {
  if (!summary.value) return ''
  const rate = summary.value.complianceRate
  if (rate >= 90) return 'text-blue-600'
  if (rate >= 70) return 'text-amber-500'
  return 'text-red-500'
})

const groupedIssues = computed(() => {
  const groups: Record<string, { title: string; severity: string; items: ContentIssue[] }> = {}
  for (const issue of issues.value) {
    const key = issue.group || '其他'
    if (!groups[key]) {
      groups[key] = { title: key, severity: issue.severity, items: [] }
    }
    groups[key].items.push(issue)
  }
  return Object.values(groups)
})

// ==================== 辅助函数 ====================

function severityColor(sev: string) {
  return { error: '#ef4444', warning: '#f59e0b', info: '#2563eb' }[sev] || '#94a3b8'
}
function severityTagColor(sev: string) {
  return { error: 'error', warning: 'warning', info: 'processing' }[sev] || 'default'
}
function severityLabel(sev: string) {
  return { error: '严重', warning: '警告', info: '提示' }[sev] || '未知'
}

/** 解析单次 evaluate 返回中的问题 */
function parseEvalResults(data: any, docLabel: string): ContentIssue[] {
  const newIssues: ContentIssue[] = []
  const evalResults = data.evaluation_results || []
  for (const result of evalResults) {
    if (result.is_compliant === false || result.compliance === '不合规') {
      newIssues.push({
        ruleId: result.rule_id || '',
        ruleName: result.rule_name || result.rule_text || '未知规则',
        severity: result.severity === '严重' || result.severity === 'critical' ? 'error'
          : result.severity === '轻微' || result.severity === 'minor' ? 'info' : 'warning',
        group: docLabel,
        description: result.issue_description || result.analysis || '未提供详细说明',
        suggestion: result.improvement_suggestion || result.suggestion || '',
      })
    }
  }
  return newIssues
}

// ==================== 核心：逐文书质控（从 PG 分表数据） ====================

async function runContentQC() {
  if (!props.patientId) {
    message.warning('请先选择病历')
    return
  }

  // 直接使用 PG 数据库按表存储的文书列表（每个 DocItem 自带 type/label/content）
  const docs = (props.documents || []).filter(d => d.has_content && d.content)
  if (docs.length === 0) {
    message.warning('该患者暂无病历文书内容，请先加载文书')
    return
  }

  // 重置状态
  loading.value = true
  analyzed.value = false
  issues.value = []
  summary.value = null
  completedSections.value = []

  totalSections.value = docs.length

  // 初始化时间线（直接使用 PG 表的 type 和 label）
  sectionTimeline.value = docs.map(d => ({
    type: d.type,
    label: d.label,
    content: d.content || '',
    status: 'pending' as const,
  }))

  // 所有文书类型清单（用于告知 LLM 患者有哪些文书）
  const allDocLabels = docs.map(d => d.label).join('、')

  // 逐文书调用后端 LLM 质控
  let allIssues: ContentIssue[] = []
  const allRuleIds = new Set<string>()       // 按 rule_id 去重
  const nonCompliantRuleIds = new Set<string>() // 不合规的 rule_id
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

      const resp = await axios.post('/api/v1/qc/sichuan/evaluate', {
        document_id: `${props.patientId}-${props.visitId}-${sec.type}`,
        document_content: contextPrefix + sec.content,
        document_type: qcDocType,
        patient_info: {
          current_document_type: qcDocType,
          current_table: sec.type,
          available_documents: docs.map(d => TABLE_TO_DOC_TYPE[d.type] || d.label).join('、'),
          patient_id: props.patientId || '',
          visit_id: props.visitId || '',
        },
        persist: false,
        prompt_mode: 'plan_a',
      }, { timeout: 120000 })

      const data = resp.data
      const secDuration = ((Date.now() - secStart) / 1000).toFixed(1)

      if (data?.status === 'success') {
        const evalSummary = data.evaluation_summary || {}
        const secIssues = parseEvalResults(data, sec.label)

        // 收集唯一 rule_id（去重统计）
        const evalResults = data.evaluation_results || []
        for (const r of evalResults) {
          if (r.rule_id) {
            allRuleIds.add(r.rule_id)
            if (r.is_compliant === false || r.compliance === '不合规') {
              nonCompliantRuleIds.add(r.rule_id)
            }
          }
        }

        // 更新时间线
        sec.status = 'done'
        sec.ruleCount = evalSummary.total_rules || 0
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
      sec.issueCount = -1  // 标记失败
      sec.duration = secDuration
      completedSections.value.push({ ...sec })
    }
  }

  // 3. 汇总（按 rule_id 去重后的唯一规则数）
  const totalDuration = ((Date.now() - startTime) / 1000).toFixed(1)
  const uniqueRuleCount = allRuleIds.size
  const compliantCount = uniqueRuleCount - nonCompliantRuleIds.size
  summary.value = {
    totalRules: uniqueRuleCount,
    complianceRate: uniqueRuleCount > 0 ? Math.round((compliantCount / uniqueRuleCount) * 10000) / 100 : 100,
    issuesFound: allIssues.length,
    docCount: sectionTimeline.value.length,
  }

  analyzed.value = true
  loading.value = false

  if (allIssues.length === 0) {
    message.success(`内涵质控通过（${totalDuration}s，${sectionTimeline.value.length} 个文书）`)
  } else {
    message.warning(`发现 ${allIssues.length} 个问题（${totalDuration}s）`)
  }
}

// 切换患者时重置
watch(() => props.patientId, () => {
  analyzed.value = false
  issues.value = []
  summary.value = null
  completedSections.value = []
  sectionTimeline.value = []
  emit('issues-change', 0)
})
</script>

<style scoped>
.content-qc-tab {
  min-height: 100%;
  display: flex;
  flex-direction: column;
  background: transparent;
  border: none;
  border-radius: 18px;
  box-shadow: none;
  overflow: hidden;
}

.content-qc-tab__header {
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
  color: #2563eb;
}

.content-qc-tab__header-desc {
  margin-top: 6px;
  max-width: 280px;
  font-size: 12px;
  line-height: 1.6;
  color: #6b7f96;
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
  color: #2563eb;
  font-size: 15px;
}

.header-title {
  font-size: 15px;
  font-weight: 800;
  color: #0f172a;
}

/* ========== 进度时间线 ========== */
.content-qc-tab__progress {
  flex: 1;
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
  background: linear-gradient(135deg, #0ea5e9, #2563eb);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 4px 10px rgba(37, 99, 235, 0.18);
}

.progress-title {
  font-size: 14px;
  font-weight: 800;
  color: #0f172a;
}

.progress-sub {
  font-size: 11px;
  color: #64748b;
  margin-top: 2px;
}

.progress-bar-wrap {
  margin-bottom: 14px;
  padding: 0 2px;
}

.progress-bar-bg {
  height: 6px;
  border-radius: 999px;
  background: #e2e8f0;
  overflow: hidden;
}

.progress-bar-fill {
  height: 100%;
  border-radius: 999px;
  background: linear-gradient(90deg, #0ea5e9, #2563eb);
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

.timeline-done { background: linear-gradient(180deg, #eff6ff, #f8fbff); }
.timeline-active { background: linear-gradient(180deg, #eff6ff, #f8fbff); animation: pulse-bg 2s infinite; }
.timeline-pending { background: rgba(255, 255, 255, 0.72); }

@keyframes pulse-bg {
  0%, 100% { background: #eff6ff; }
  50% { background: #dbeafe; }
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

.timeline-dot--done { background: #2563eb; }
.timeline-dot--active { background: #3b82f6; }
.timeline-dot--pending { background: #e2e8f0; }

.dot-ping {
  width: 8px;
  height: 8px;
  border-radius: 999px;
  background: #fff;
  animation: ping 1s cubic-bezier(0, 0, 0.2, 1) infinite;
}

.dot-idle {
  width: 6px;
  height: 6px;
  border-radius: 999px;
  background: #94a3b8;
}

@keyframes ping {
  75%, 100% {
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

.timeline-label--done { color: #2563eb; }
.timeline-label--active { color: #2563eb; }
.timeline-label--pending { color: #94a3b8; }

.timeline-time {
  font-size: 10px;
  color: #94a3b8;
  font-variant-numeric: tabular-nums;
}

.timeline-active-hint {
  font-size: 10px;
  color: #3b82f6;
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

.result-tag--rules {
  background: #e0e7ff;
  color: #4338ca;
}

.result-tag--issues {
  background: #fef2f2;
  color: #dc2626;
}

.result-tag--pass {
  background: #dbeafe;
  color: #2563eb;
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
  color: #475569;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.timeline-issue-more {
  font-size: 10px;
  color: #94a3b8;
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
  background: linear-gradient(180deg, #eef4ff, #dbeafe);
  border: 1px solid #bfdbfe;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 18px;
  box-shadow:
    0 10px 20px rgba(59, 130, 246, 0.12),
    inset 0 1px 0 rgba(255, 255, 255, 0.72);
}

.empty-icon { font-size: 24px; color: #2563eb; }
.empty-title { font-size: 15px; font-weight: 800; color: #1e293b; margin-bottom: 6px; }
.empty-desc { font-size: 12px; color: #6b7f96; line-height: 1.6; margin-bottom: 18px; max-width: 228px; }
.empty-btn {
  border-radius: 999px !important;
  box-shadow:
    0 10px 20px rgba(37, 99, 235, 0.18),
    inset 0 1px 0 rgba(255, 255, 255, 0.14) !important;
}

.content-qc-tab__body {
  flex: 1;
  overflow-y: auto;
  padding: 0;
  background: transparent;
}

.summary-card {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  padding: 12px;
  background:
    radial-gradient(circle at top right, rgba(14, 165, 233, 0.08), transparent 30%),
    #fff;
  border: 1px solid #e2e8f0;
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
  color: #2563eb;
  margin-bottom: 4px;
}

.summary-card__title {
  font-size: 15px;
  font-weight: 800;
  color: #0f172a;
}

.summary-card__progress {
  min-width: 64px;
  padding: 10px 12px;
  border-radius: 12px;
  background: linear-gradient(180deg, #eff6ff, #dbeafe);
  color: #2563eb;
  text-align: center;
  font-size: 18px;
  line-height: 1;
  font-weight: 800;
}

.summary-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 4px 8px;
}

.summary-label { font-size: 11px; color: #94a3b8; font-weight: 600; }
.summary-value { font-size: 13px; font-weight: 800; color: #0f172a; }

.issue-group { margin-bottom: 12px; }

.group-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  background: rgba(255, 255, 255, 0.82);
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  margin-bottom: 8px;
}

.group-dot { width: 8px; height: 8px; border-radius: 999px; flex-shrink: 0; }
.group-title { font-size: 12px; font-weight: 700; color: #334155; }
.group-count { font-size: 11px; color: #94a3b8; }

.issue-item {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 14px;
  padding: 12px;
  margin-bottom: 8px;
  box-shadow: 0 6px 16px rgba(15, 23, 42, 0.035);
  transition: transform 0.15s ease, box-shadow 0.15s ease, border-color 0.15s ease;
}

.issue-item:hover {
  transform: translateY(-1px);
  border-color: rgba(147, 197, 253, 0.95);
  box-shadow: 0 10px 22px rgba(15, 23, 42, 0.05);
}

.issue-top { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; }
.issue-rule { font-size: 12px; font-weight: 700; color: #475569; }
.issue-desc { font-size: 13px; color: #0f172a; line-height: 1.6; }
.issue-suggestion {
  margin-top: 6px;
  background: linear-gradient(180deg, rgba(255, 247, 237, 0.9), rgba(255, 251, 235, 0.9));
  border-left: 3px solid #f59e0b;
  color: #9a3412;
  font-size: 12px;
  padding: 6px 8px;
  border-radius: 0 8px 8px 0;
  line-height: 1.5;
}

.content-qc-tab__empty-result {
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

.empty-result-icon { font-size: 30px; color: #2563eb; margin-bottom: 10px; }
.empty-result-text { font-size: 13px; font-weight: 700; color: #334155; }

.content-qc-tab__footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 0 0;
  border-top: none;
  background: transparent;
  font-size: 12px;
  color: #475569;
}

@media (max-width: 520px) {
  .summary-card {
    grid-template-columns: 1fr;
  }

  .summary-card__hero {
    flex-direction: column;
  }
}

.ml-auto { margin-left: auto; }

.custom-scrollbar::-webkit-scrollbar { width: 4px; }
.custom-scrollbar::-webkit-scrollbar-track { background: transparent; }
.custom-scrollbar::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 999px; }
</style>
