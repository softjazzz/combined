<template>
  <div class="content-qc-tab">
    <!-- 顶部操作栏 -->
    <div class="content-qc-tab__header">
      <div class="header-left">
        <SafetyCertificateOutlined class="header-icon" />
        <span class="header-title">内涵质控</span>
        <a-tag v-if="totalCount > 0" color="error" size="small">{{ totalCount }}</a-tag>
      </div>
      <a-button type="link" size="small" @click="runContentQC" :loading="loading" :disabled="!patientId">
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
      <div class="empty-desc">基于 LLM 大模型，对病历文书内容进行深度语义分析，<br/>检查诊疗逻辑、病程记录完整性、知情同意等内涵质量</div>
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

// ==================== 文书类型映射 ====================
const DOC_TYPE_LABELS: Record<string, string> = {
  '入院记录': '入院记录',
  '首次病程记录': '首次病程记录',
  '日常病程记录': '日常病程记录',
  '主任（副主任）医师查房记录': '主任查房记录',
  '出院记录': '出院记录',
  '手术记录': '手术记录',
  '术后首次病程记录': '术后首次病程',
  '会诊记录': '会诊记录',
  '死亡记录': '死亡记录',
  '病危通知': '病危通知',
  '知情同意书': '知情同意书',
  '病案首页': '病案首页',
}

// 自动识别文书段落的正则
const SECTION_PATTERNS = [
  { pattern: /入院记录/i, type: '入院记录' },
  { pattern: /首次病程记录/i, type: '首次病程记录' },
  { pattern: /日常病程记录|病程记录/i, type: '日常病程记录' },
  { pattern: /主任.*查房|副主任.*查房/i, type: '主任（副主任）医师查房记录' },
  { pattern: /出院记录|出院小结/i, type: '出院记录' },
  { pattern: /手术记录/i, type: '手术记录' },
  { pattern: /术后首次病程/i, type: '术后首次病程记录' },
  { pattern: /会诊记录/i, type: '会诊记录' },
]

// ==================== Props & Emits ====================

const props = defineProps<{
  patientId?: string
  visitId?: string
  instituteId?: string
  medicalText?: string
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
  if (rate >= 90) return 'text-green-600'
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

/** 从病历全文中识别文书段落 */
function splitDocumentSections(text: string): { type: string; label: string; content: string }[] {
  if (!text || text.trim().length === 0) return []

  const lines = text.split('\n')
  const sections: { type: string; label: string; startLine: number }[] = []

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].trim()
    if (!line) continue

    for (const sp of SECTION_PATTERNS) {
      if (sp.pattern.test(line) && line.length < 30) {
        // 避免重复同类型（除日常病程可以多次）
        const lastOfType = sections.filter(s => s.type === sp.type)
        if (lastOfType.length === 0 || sp.type === '日常病程记录') {
          sections.push({
            type: sp.type,
            label: DOC_TYPE_LABELS[sp.type] || sp.type,
            startLine: i,
          })
        }
        break
      }
    }
  }

  // 将段落按起始行切分内容
  const result: { type: string; label: string; content: string }[] = []
  for (let i = 0; i < sections.length; i++) {
    const start = sections[i].startLine
    const end = i + 1 < sections.length ? sections[i + 1].startLine : lines.length
    const content = lines.slice(start, end).join('\n')
    
    // 合并相同类型
    const existing = result.find(r => r.type === sections[i].type)
    if (existing) {
      existing.content += '\n\n' + content
    } else {
      result.push({
        type: sections[i].type,
        label: sections[i].label,
        content,
      })
    }
  }

  // 如果没有识别到任何段落，整体作为一个"病程记录"
  if (result.length === 0 && text.trim().length > 50) {
    result.push({ type: '病程记录', label: '病程记录（全文）', content: text })
  }

  return result
}

/** 解析单次 evaluate 返回中的问题 */
function parseEvalResults(data: any, docType: string): ContentIssue[] {
  const newIssues: ContentIssue[] = []

  const evalResults = data.evaluation_results || []
  for (const result of evalResults) {
    if (result.is_compliant === false || result.compliance === '不合规') {
      newIssues.push({
        ruleId: result.rule_id || '',
        ruleName: result.rule_name || result.rule_text || '未知规则',
        severity: result.severity === '严重' || result.severity === 'critical' ? 'error'
          : result.severity === '轻微' || result.severity === 'minor' ? 'info' : 'warning',
        group: docType,
        description: result.issue_description || result.analysis || '未提供详细说明',
        suggestion: result.improvement_suggestion || result.suggestion || '',
      })
    }
  }
  return newIssues
}

// ==================== 核心：逐文书质控 ====================

async function runContentQC() {
  if (!props.patientId) {
    message.warning('请先选择病历')
    return
  }

  const medText = props.medicalText || ''
  if (!medText || medText.trim().length < 20) {
    message.warning('病历文书内容为空，请先加载病历文书')
    return
  }

  // 重置状态
  loading.value = true
  analyzed.value = false
  issues.value = []
  summary.value = null
  completedSections.value = []

  // 1. 切分文书段落
  const sections = splitDocumentSections(medText)
  totalSections.value = sections.length

  // 初始化时间线
  sectionTimeline.value = sections.map(s => ({
    type: s.type,
    label: s.label,
    content: s.content,
    status: 'pending' as const,
  }))

  if (sections.length === 0) {
    // 无法识别段落，整体发送
    sectionTimeline.value = [{
      type: '病程记录',
      label: '病程记录（全文）',
      content: medText,
      status: 'active',
    }]
    totalSections.value = 1
  }

  // 2. 逐文书调用后端
  let allIssues: ContentIssue[] = []
  let totalRules = 0
  let totalCompliant = 0
  const startTime = Date.now()

  for (let i = 0; i < sectionTimeline.value.length; i++) {
    const sec = sectionTimeline.value[i]
    sec.status = 'active'

    const secStart = Date.now()

    try {
      // 构建上下文：告知 LLM 当前正在评估的文书类型、患者已有的所有文书清单
      const allDocTypes = sectionTimeline.value.map(s => s.label).join('、')
      const contextPrefix = [
        `【重要上下文】当前正在评估的文书类型是「${sec.label}」。`,
        `该患者病历中包含以下文书：${allDocTypes}。`,
        `以下内容即为该患者的「${sec.label}」全文：`,
        '',
      ].join('\n')

      const resp = await axios.post('/api/v1/qc/sichuan/evaluate', {
        document_id: `${props.patientId}-${props.visitId}-${sec.type}`,
        document_content: contextPrefix + sec.content,
        document_type: sec.type,
        patient_info: {
          current_document_type: sec.type,
          available_documents: sectionTimeline.value.map(s => s.type),
          patient_id: props.patientId,
          visit_id: props.visitId,
        },
        persist: false,
        prompt_mode: 'plan_a',
      }, { timeout: 120000 })

      const data = resp.data
      const secDuration = ((Date.now() - secStart) / 1000).toFixed(1)

      if (data?.status === 'success') {
        const evalSummary = data.evaluation_summary || {}
        const secIssues = parseEvalResults(data, sec.label)

        // 更新时间线
        sec.status = 'done'
        sec.ruleCount = evalSummary.total_rules || 0
        sec.issueCount = secIssues.length
        sec.duration = secDuration
        sec.issues = secIssues

        // 累加
        allIssues = [...allIssues, ...secIssues]
        totalRules += evalSummary.total_rules || 0
        totalCompliant += evalSummary.compliant_rules || 0

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

  // 3. 汇总
  const totalDuration = ((Date.now() - startTime) / 1000).toFixed(1)
  summary.value = {
    totalRules,
    complianceRate: totalRules > 0 ? Math.round((totalCompliant / totalRules) * 10000) / 100 : 100,
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
  background: #f8fafc;
}

.content-qc-tab__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
  background: #fff;
  border-bottom: 1px solid #e2e8f0;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 6px;
}

.header-icon {
  color: #7c3aed;
  font-size: 14px;
}

.header-title {
  font-size: 13px;
  font-weight: 800;
  color: #0f172a;
}

/* ========== 进度时间线 ========== */
.content-qc-tab__progress {
  flex: 1;
  overflow-y: auto;
  padding: 16px 12px;
}

.progress-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 14px;
}

.progress-avatar {
  width: 40px;
  height: 40px;
  border-radius: 12px;
  background: linear-gradient(135deg, #7c3aed, #6d28d9);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 4px 12px rgba(124, 58, 237, 0.3);
}

.progress-title {
  font-size: 13px;
  font-weight: 800;
  color: #0f172a;
}

.progress-sub {
  font-size: 11px;
  color: #94a3b8;
  margin-top: 2px;
}

.progress-bar-wrap {
  margin-bottom: 14px;
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
  background: linear-gradient(90deg, #7c3aed, #a855f7);
  transition: width 0.5s ease;
}

.progress-timeline {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.timeline-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 8px 10px;
  border-radius: 10px;
  transition: all 0.3s ease;
}

.timeline-done { background: #f0fdf4; }
.timeline-active { background: #eff6ff; animation: pulse-bg 2s infinite; }
.timeline-pending { background: rgba(248, 250, 252, 0.5); }

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

.timeline-dot--done { background: #22c55e; }
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

.timeline-label--done { color: #15803d; }
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
  background: #dcfce7;
  color: #16a34a;
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
  padding: 32px 20px;
  text-align: center;
}

.empty-icon-wrap {
  width: 56px;
  height: 56px;
  border-radius: 14px;
  background: linear-gradient(135deg, #ede9fe, #ddd6fe);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 16px;
}

.empty-icon { font-size: 24px; color: #7c3aed; }
.empty-title { font-size: 14px; font-weight: 800; color: #0f172a; margin-bottom: 6px; }
.empty-desc { font-size: 12px; color: #94a3b8; line-height: 1.6; margin-bottom: 16px; max-width: 240px; }
.empty-btn { border-radius: 10px !important; }

.content-qc-tab__body {
  flex: 1;
  overflow-y: auto;
  padding: 12px;
}

.summary-card {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  padding: 12px;
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  margin-bottom: 12px;
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
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  margin-bottom: 8px;
}

.group-dot { width: 8px; height: 8px; border-radius: 999px; flex-shrink: 0; }
.group-title { font-size: 12px; font-weight: 700; color: #334155; }
.group-count { font-size: 11px; color: #94a3b8; }

.issue-item {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 12px;
  margin-bottom: 8px;
}

.issue-top { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; }
.issue-rule { font-size: 12px; font-weight: 700; color: #475569; }
.issue-desc { font-size: 13px; color: #0f172a; line-height: 1.6; }
.issue-suggestion {
  margin-top: 6px;
  background: #fff7ed;
  border-left: 3px solid #f59e0b;
  color: #9a3412;
  font-size: 12px;
  padding: 6px 8px;
  border-radius: 8px;
  line-height: 1.5;
}

.content-qc-tab__empty-result {
  min-height: 200px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
}

.empty-result-icon { font-size: 30px; color: #22c55e; margin-bottom: 10px; }
.empty-result-text { font-size: 13px; font-weight: 700; color: #334155; }

.content-qc-tab__footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  border-top: 1px solid #e2e8f0;
  background: #fff;
  font-size: 12px;
  color: #475569;
}

.ml-auto { margin-left: auto; }

.custom-scrollbar::-webkit-scrollbar { width: 4px; }
.custom-scrollbar::-webkit-scrollbar-track { background: transparent; }
.custom-scrollbar::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 999px; }
</style>
