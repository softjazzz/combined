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

    <!-- 加载态 -->
    <div v-if="loading" class="content-qc-tab__loading">
      <a-spin />
      <div class="loading-text">大模型正在分析病历文书内涵质量...</div>
      <div class="loading-sub">预计耗时 30-60 秒</div>
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
          <span class="summary-label">评定等级</span>
          <a-tag :color="gradeColor(summary.grade)">{{ summary.grade }}</a-tag>
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
          <article
            v-for="(issue, iIdx) in group.items"
            :key="iIdx"
            class="issue-item"
          >
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
    <footer v-if="analyzed" class="content-qc-tab__footer">
      <span>共 <strong>{{ totalCount }}</strong> 个问题</span>
      <a-button type="link" size="small" @click="runContentQC" :loading="loading">
        <ReloadOutlined /> 重新分析
      </a-button>
    </footer>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { message } from 'ant-design-vue'
import {
  SafetyCertificateOutlined,
  ReloadOutlined,
  ThunderboltOutlined,
  CheckCircleOutlined,
} from '@ant-design/icons-vue'
import axios from 'axios'

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
  grade: string
}

const props = defineProps<{
  patientId?: string
  visitId?: string
  instituteId?: string
  medicalText?: string
}>()

const emit = defineEmits<{
  (e: 'issues-change', count: number): void
}>()

const loading = ref(false)
const analyzed = ref(false)
const issues = ref<ContentIssue[]>([])
const summary = ref<ContentSummary | null>(null)

const totalCount = computed(() => issues.value.length)

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

function severityColor(sev: string) {
  return { error: '#ef4444', warning: '#f59e0b', info: '#2563eb' }[sev] || '#94a3b8'
}
function severityTagColor(sev: string) {
  return { error: 'error', warning: 'warning', info: 'processing' }[sev] || 'default'
}
function severityLabel(sev: string) {
  return { error: '严重', warning: '警告', info: '提示' }[sev] || '未知'
}
function gradeColor(grade: string) {
  if (grade === '甲') return 'green'
  if (grade === '乙') return 'blue'
  if (grade === '丙') return 'red'
  return 'default'
}

async function runContentQC() {
  if (!props.patientId) {
    message.warning('请先选择病历')
    return
  }

  loading.value = true
  analyzed.value = false
  issues.value = []
  summary.value = null

  try {
    // 优先使用 CDM 数据库中的病历文书数据
    // 调用后端的四川质控引擎分段 Pipeline
    const documentContent = props.medicalText || ''
    
    if (!documentContent) {
      // 如果没有文书文本，尝试从后端获取
      message.info('正在从数据库加载病历文书...')
    }

    const resp = await axios.post('/api/v1/qc/sichuan/evaluate', {
      document_id: `${props.patientId}-${props.visitId}`,
      document_content: documentContent,
      document_type: '病程记录',
      persist: false,
      prompt_mode: 'plan_a',
    }, { timeout: 120000 })

    const data = resp.data

    if (data?.status === 'success') {
      // 解析评估结果
      const evalSummary = data.evaluation_summary || {}
      summary.value = {
        totalRules: evalSummary.total_rules || 0,
        complianceRate: Math.round((evalSummary.compliance_rate || 0) * 100) / 100,
        issuesFound: evalSummary.issues_found || evalSummary.critical_violations || 0,
        grade: evalSummary.overall_grade || '-',
      }

      // 解析每条质控结果
      const newIssues: ContentIssue[] = []
      const evalResults = data.evaluation_results || []
      for (const result of evalResults) {
        if (result.is_compliant === false || result.compliance === '不合规') {
          newIssues.push({
            ruleId: result.rule_id || '',
            ruleName: result.rule_name || result.rule_text || '未知规则',
            severity: result.severity === '严重' || result.severity === 'critical' ? 'error'
              : result.severity === '轻微' || result.severity === 'minor' ? 'info' : 'warning',
            group: result.document_type || result.category || '病历文书',
            description: result.issue_description || result.analysis || '未提供详细说明',
            suggestion: result.improvement_suggestion || result.suggestion || '',
          })
        }
      }

      // 如果有 document_results（分段模式），也解析
      if (data.document_results) {
        for (const [docType, docData] of Object.entries(data.document_results as Record<string, any>)) {
          const docResults = docData?.evaluation_results || []
          for (const result of docResults) {
            if (result.is_compliant === false || result.compliance === '不合规') {
              // 避免重复（如果 evaluation_results 已经包含了）
              const exists = newIssues.some(i => i.ruleId === result.rule_id && i.group === docType)
              if (!exists) {
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
          }
        }
      }

      issues.value = newIssues
      analyzed.value = true
      emit('issues-change', newIssues.length)

      if (newIssues.length === 0) {
        message.success('内涵质控通过，未发现问题')
      } else {
        message.warning(`发现 ${newIssues.length} 个内涵质控问题`)
      }
    } else {
      message.error('内涵质控分析失败')
    }
  } catch (err: any) {
    console.error('内涵质控分析异常', err)
    message.error(err?.response?.data?.detail || err?.message || '内涵质控分析失败')
  } finally {
    loading.value = false
  }
}

// 当患者切换时重置状态
watch(() => props.patientId, () => {
  analyzed.value = false
  issues.value = []
  summary.value = null
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

.content-qc-tab__loading {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px 20px;
  text-align: center;
}

.loading-text {
  margin-top: 16px;
  font-size: 13px;
  font-weight: 700;
  color: #334155;
}

.loading-sub {
  margin-top: 4px;
  font-size: 11px;
  color: #94a3b8;
}

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

.empty-icon {
  font-size: 24px;
  color: #7c3aed;
}

.empty-title {
  font-size: 14px;
  font-weight: 800;
  color: #0f172a;
  margin-bottom: 6px;
}

.empty-desc {
  font-size: 12px;
  color: #94a3b8;
  line-height: 1.6;
  margin-bottom: 16px;
  max-width: 240px;
}

.empty-btn {
  border-radius: 10px !important;
}

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

.summary-label {
  font-size: 11px;
  color: #94a3b8;
  font-weight: 600;
}

.summary-value {
  font-size: 13px;
  font-weight: 800;
  color: #0f172a;
}

.issue-group {
  margin-bottom: 12px;
}

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

.group-dot {
  width: 8px;
  height: 8px;
  border-radius: 999px;
  flex-shrink: 0;
}

.group-title {
  font-size: 12px;
  font-weight: 700;
  color: #334155;
}

.group-count {
  font-size: 11px;
  color: #94a3b8;
}

.issue-item {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 12px;
  margin-bottom: 8px;
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
  color: #475569;
}

.issue-desc {
  font-size: 13px;
  color: #0f172a;
  line-height: 1.6;
}

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

.empty-result-icon {
  font-size: 30px;
  color: #22c55e;
  margin-bottom: 10px;
}

.empty-result-text {
  font-size: 13px;
  font-weight: 700;
  color: #334155;
}

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

.custom-scrollbar::-webkit-scrollbar { width: 4px; }
.custom-scrollbar::-webkit-scrollbar-track { background: transparent; }
.custom-scrollbar::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 999px; }
</style>
