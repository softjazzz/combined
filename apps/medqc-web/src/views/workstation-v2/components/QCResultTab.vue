<template>
  <div class="qc-result-tab">
    <div v-if="!props.activeTab" class="qc-result-tab__tabs">
      <button
        v-for="tab in qcTabs"
        :key="tab.key"
        type="button"
        :class="['qc-result-tab__tab', { 'qc-result-tab__tab--active': currentTab === tab.key }]"
        @click="internalTab = tab.key"
      >
        <component :is="tab.icon" class="qc-result-tab__tab-icon" />
        <span>{{ tab.label }}</span>
        <span v-if="getTabCount(tab.key) > 0" class="qc-result-tab__tab-badge">{{ getTabCount(tab.key) }}</span>
      </button>
    </div>

    <div class="qc-result-tab__body custom-scrollbar">
      <template v-if="currentIssues.length > 0">
        <section v-for="(group, gIdx) in groupedIssues" :key="gIdx" class="qc-group">
          <header class="qc-group__header">
            <span class="qc-group__title">
              <span class="qc-group__dot" :style="{ background: severityColor(group.severity) }"></span>
              {{ group.title }} ({{ group.items.length }})
            </span>
          </header>

          <article
            v-for="(issue, iIdx) in group.items"
            :key="iIdx"
            :class="['qc-issue', { 'qc-issue--dismissed': issue.dismissed }]"
          >
            <div class="qc-issue__content">
              <a-tag :color="severityTagColor(issue.severity)" size="small">{{ severityLabel(issue.severity) }}</a-tag>
              <button
                type="button"
                class="qc-issue__desc qc-issue__desc--link"
                @click="locateIssue(issue)"
                :title="`定位到相关字段：${issue.description}`"
              >
                {{ issue.description }}
              </button>
              <div v-if="issue.suggestion" class="qc-issue__suggestion">
                {{ issue.suggestion }}
              </div>
            </div>

            <div class="qc-issue__actions">
              <a-button type="link" size="small" @click="locateIssue(issue)">定位字段</a-button>
              <a-button type="link" size="small" @click="$emit('jump-evidence', issue)">文书依据</a-button>
              <a-dropdown v-if="issue.id" :trigger="['click']">
                <a-button type="link" size="small">操作 <DownOutlined /></a-button>
                <template #overlay>
                  <a-menu @click="({ key }: any) => handleDefectAction(key, issue)">
                    <a-menu-item key="urge"><SendOutlined /> 催办</a-menu-item>
                    <a-menu-item key="mark_remediated"><EditOutlined /> 标记已整改</a-menu-item>
                    <a-menu-divider />
                    <a-menu-item key="approve"><CheckOutlined style="color: #52c41a" /> 审核通过</a-menu-item>
                    <a-menu-item key="reject"><CloseCircleOutlined style="color: #ff4d4f" /> 审核存疑</a-menu-item>
                  </a-menu>
                </template>
              </a-dropdown>
              <a-button
                v-else-if="issue.actionLabel"
                type="link"
                size="small"
                @click="$emit('action', issue)"
              >
                {{ issue.actionLabel }}
              </a-button>
              <a-button type="text" size="small" @click="dismissIssue(issue)">忽略</a-button>
            </div>
          </article>
        </section>
      </template>

      <div v-else class="qc-empty">
        <CheckCircleOutlined class="qc-empty__icon" />
        <div class="qc-empty__title">{{ analyzing ? '正在分析...' : '未发现质控问题' }}</div>
      </div>
    </div>

    <footer class="qc-result-tab__footer">
      <span>共 <strong>{{ totalIssueCount }}</strong> 个问题</span>
      <div class="qc-result-tab__footer-actions">
        <a-button type="link" size="small" @click="emit('refresh')" :loading="analyzing">
          <ReloadOutlined /> 刷新
        </a-button>
        <a-button type="link" size="small" @click="handleExportDefects" :loading="exporting">
          <DownloadOutlined /> 导出
        </a-button>
      </div>
    </footer>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { message, Modal } from 'ant-design-vue'
import {
  CheckCircleOutlined,
  FileTextOutlined,
  CodeOutlined,
  DollarOutlined,
  DownOutlined,
  SendOutlined,
  EditOutlined,
  CheckOutlined,
  CloseCircleOutlined,
  DownloadOutlined,
  ReloadOutlined,
} from '@ant-design/icons-vue'
import axios from 'axios'
import {
  urgeDefect,
  markDefectRemediated,
  approveDefect,
  rejectDefect,
  exportDefects,
} from '@/api/defects'
import { integratedQCEngine } from '@/services/integrated-qc-engine'
import type { QCRuleResult, DocumentType } from '@/types/enhanced-qc-rule'

interface QCIssue {
  id: string
  category: 'form' | 'coding' | 'cost'
  severity: 'error' | 'warning' | 'info'
  group: string
  description: string
  suggestion?: string
  evidence?: string
  actionLabel?: string
  dismissed?: boolean
}

type LocateTarget = 'basic' | 'admission' | 'diagnosis' | 'procedure'

const props = defineProps<{
  frontpage?: Record<string, any> | null
  analyzing?: boolean
  refreshSeed?: number
  activeTab?: 'form' | 'coding' | 'cost'
  visitId?: string | null
  patientId?: string | null
}>()

const emit = defineEmits<{
  (e: 'action', issue: QCIssue): void
  (e: 'refresh'): void
  (e: 'issues-change', issues: QCIssue[]): void
  (e: 'locate-field', payload: { target: LocateTarget; issue: QCIssue }): void
  (e: 'jump-evidence', issue: QCIssue): void
}>()

const internalTab = ref<'form' | 'coding' | 'cost'>('form')
const currentTab = computed(() => props.activeTab || internalTab.value)
const issues = ref<QCIssue[]>([])
const exporting = ref(false)
const codingQCLoading = ref(false)

const qcTabs = [
  { key: 'form' as const, label: '首页质控', icon: FileTextOutlined },
  { key: 'coding' as const, label: '编码质控', icon: CodeOutlined },
  { key: 'cost' as const, label: '控费监测', icon: DollarOutlined },
]

const currentIssues = computed(() =>
  issues.value.filter(i => i.category === currentTab.value && !i.dismissed),
)

const groupedIssues = computed(() => {
  const groups: Record<string, { title: string; severity: string; items: QCIssue[] }> = {}
  for (const issue of currentIssues.value) {
    if (!groups[issue.group]) {
      groups[issue.group] = { title: issue.group, severity: issue.severity, items: [] }
    }
    groups[issue.group].items.push(issue)
  }
  return Object.values(groups)
})

const totalIssueCount = computed(() =>
  issues.value.filter(i => !i.dismissed).length,
)

function getTabCount(tab: string) {
  return issues.value.filter(i => i.category === tab && !i.dismissed).length
}

function severityColor(sev: string) {
  return {
    error: '#ef4444',
    warning: '#f59e0b',
    info: '#2563eb',
  }[sev] || '#94a3b8'
}

function severityTagColor(sev: string) {
  return {
    error: 'error',
    warning: 'warning',
    info: 'processing',
  }[sev] || 'default'
}

function severityLabel(sev: string) {
  return {
    error: '严重',
    warning: '警告',
    info: '提示',
  }[sev] || '未知'
}

function dismissIssue(issue: QCIssue) {
  issue.dismissed = true
  emit('issues-change', issues.value.slice())
}

function locateIssue(issue: QCIssue) {
  emit('locate-field', {
    target: inferLocateTarget(issue),
    issue,
  })
}

function inferLocateTarget(issue: QCIssue): LocateTarget {
  const text = `${issue.group} ${issue.description} ${issue.suggestion || ''}`.toLowerCase()

  if (issue.category === 'coding') {
    if (/手术|操作|麻醉|icd-9|icd9|cm-3|cm3/.test(text)) return 'procedure'
    return 'diagnosis'
  }

  if (issue.category === 'cost') return 'admission'

  if (/手术|操作|麻醉|切口|术者/.test(text)) return 'procedure'
  if (/诊断|icd|病情/.test(text)) return 'diagnosis'
  if (/入院|出院|住院|科室|床号|转科|入院病情/.test(text)) return 'admission'
  return 'basic'
}

async function handleDefectAction(action: string, issue: QCIssue) {
  try {
    switch (action) {
      case 'urge': {
        const res = await urgeDefect(issue.id, { message: `请尽快处理: ${issue.description}` })
        if (res.success) message.success('催办成功')
        else message.error(res.message || '催办失败')
        break
      }
      case 'mark_remediated': {
        const res = await markDefectRemediated(issue.id, { remediation_note: '已整改' })
        if (res.success) {
          issue.dismissed = true
          emit('issues-change', issues.value.slice())
          message.success('已标记为整改')
        } else {
          message.error(res.message || '标记失败')
        }
        break
      }
      case 'approve': {
        const res = await approveDefect(issue.id, { comment: '审核通过' })
        if (res.success) {
          issue.dismissed = true
          emit('issues-change', issues.value.slice())
          message.success('审核通过')
        } else {
          message.error(res.message || '审核失败')
        }
        break
      }
      case 'reject': {
        Modal.confirm({
          title: '审核存疑',
          content: `确认将缺陷「${issue.description.slice(0, 30)}...」标记为存疑？`,
          okText: '确认',
          cancelText: '取消',
          okType: 'danger',
          async onOk() {
            const res = await rejectDefect(issue.id, { reason: '审核存疑，需进一步确认' })
            if (res.success) message.success('已标记为存疑')
            else message.error(res.message || '操作失败')
          },
        })
        break
      }
    }
  } catch (err: any) {
    message.error(err?.message || '操作失败')
  }
}

async function handleExportDefects() {
  exporting.value = true
  try {
    const res = await exportDefects({ format: 'xlsx' })
    if (res.success && res.data?.download_url) {
      window.open(res.data.download_url, '_blank')
      message.success('导出成功')
    } else {
      message.info('导出功能开发中')
    }
  } catch {
    message.error('导出失败')
  } finally {
    exporting.value = false
  }
}

async function fetchCodingQCFromBackend() {
  // 优先使用 visit_id 模式：直接从 PG 数据库读取（不依赖 LLM 草稿）
  const useVisitIdMode = !!props.visitId
  const fp = props.frontpage

  if (!useVisitIdMode && !fp) return []

  let payload: any
  if (useVisitIdMode) {
    // visit_id 模式：后端自己从 PG 查诊断/手术数据
    payload = {
      visit_id: props.visitId,
      patient_id: props.patientId || '',
    }
  } else {
    // 兼容旧版：从 frontpage LLM 草稿组装
    const diagnoses = fp!.diagnoses || {}
    const procedures = fp!.procedures || {}
    const diagList: any[] = []
    if (diagnoses.discharge_main_diagnosis_text || diagnoses.discharge_main_icd) {
      diagList.push({
        code: diagnoses.discharge_main_icd || '',
        name: diagnoses.discharge_main_diagnosis_text || '',
      })
    }
    const otherTexts = diagnoses.discharge_other_diagnoses_texts || []
    const otherICDs = diagnoses.discharge_other_icds || []
    for (let i = 0; i < otherTexts.length; i += 1) {
      diagList.push({
        code: otherICDs[i] || '',
        name: otherTexts[i] || '',
      })
    }
    const surgList: any[] = []
    if (procedures.main_procedure_text || procedures.main_procedure_code) {
      surgList.push({
        code: procedures.main_procedure_code || '',
        name: procedures.main_procedure_text || '',
      })
    }
    payload = {
      frontpage: {
        sex: fp!.sex || fp!.basic_info?.sex || fp!.basic_info?.gender_text || '',
        age: fp!.age || fp!.basic_info?.age || fp!.basic_info?.age_years || '',
        diagnoses: diagList,
        surgeries: surgList,
        clinical_summary: fp!.clinical_summary || '',
      },
    }
  }

  try {
    codingQCLoading.value = true
    const resp = await axios.post('/api/v1/qc/coding-qc/check', payload, { timeout: 30000 })
    const data = resp.data?.data
    if (!data) return []

    const codingIssues: QCIssue[] = []
    let idx = 0

    for (const issue of (data.rule_issues || [])) {
      codingIssues.push({
        id: `coding-rule-${idx += 1}`,
        category: 'coding',
        severity: issue.severity === 'error' ? 'error' : issue.severity === 'warning' ? 'warning' : 'info',
        group: issue.dimension === 'format' ? '编码格式校验' : '编码存在性验证',
        description: issue.description,
        suggestion: issue.suggestion,
        evidence: issue.evidence,
        actionLabel: '修正编码',
      })
    }

    const dimensionLabels: Record<string, string> = {
      merge: '编码合并',
      exclusion: '编码互斥',
      primary: '主诊断选择',
      consistency: '编码一致性',
    }

    for (const issue of (data.llm_issues || [])) {
      codingIssues.push({
        id: `coding-llm-${idx += 1}`,
        category: 'coding',
        severity: issue.severity === 'error' ? 'error' : issue.severity === 'warning' ? 'warning' : 'info',
        group: dimensionLabels[issue.dimension] || 'LLM 语义审查',
        description: issue.description,
        suggestion: issue.suggestion,
        evidence: issue.evidence,
        actionLabel: '查看详情',
      })
    }

    return codingIssues
  } catch (err) {
    console.error('后端编码质控调用失败', err)
    return []
  } finally {
    codingQCLoading.value = false
  }
}

async function runRealQCEngine() {
  const fp = props.frontpage
  if (!fp) {
    issues.value = []
    emit('issues-change', [])
    return
  }

  const patientData = {
    patientId: fp.case_id || fp.patient_id || `PAT_${Date.now()}`,
    documents: [
      {
        id: `doc_${Date.now()}`,
        type: 'admission_record' as DocumentType,
        content: JSON.stringify(fp),
        timestamp: new Date().toISOString(),
        status: 'draft',
      },
    ],
  }

  try {
    const [engineResult, codingIssues] = await Promise.all([
      integratedQCEngine.executeQualityControl(patientData),
      fetchCodingQCFromBackend(),
    ])

    const newIssues: QCIssue[] = []
    let issueId = 0
    if (engineResult.ruleResults && engineResult.ruleResults.length > 0) {
      engineResult.ruleResults.forEach((ruleRes: QCRuleResult) => {
        if (!ruleRes.isCompliant && ruleRes.findings && ruleRes.findings.length > 0) {
          ruleRes.findings.forEach(finding => {
            let sev: 'error' | 'warning' | 'info' = 'info'
            if (finding.severity === 'critical' || finding.severity === 'major') sev = 'error'
            else if (finding.severity === 'minor') sev = 'warning'

            let tabCat: 'form' | 'coding' | 'cost' = 'form'
            if (ruleRes.ruleName.includes('费用') || finding.description.includes('DRG')) {
              tabCat = 'cost'
            }

            newIssues.push({
              id: `sys-${issueId += 1}`,
              category: tabCat,
              severity: sev,
              group: ruleRes.ruleName || '未知规则',
              description: finding.description,
              suggestion: finding.recommendation,
              evidence: finding.evidence,
              actionLabel: '查看详情',
            })
          })
        }
      })
    }

    newIssues.push(...codingIssues)
    issues.value = newIssues
    emit('issues-change', newIssues.slice())
  } catch (error) {
    console.error('质控引擎执行异常', error)
    issues.value = []
    emit('issues-change', [])
  }
}

watch(
  () => props.frontpage,
  (newVal) => {
    if (newVal) runRealQCEngine()
    else {
      issues.value = []
      emit('issues-change', [])
    }
  },
  { deep: true, immediate: true },
)

watch(
  () => props.refreshSeed,
  () => {
    if (props.frontpage) runRealQCEngine()
  },
)
</script>

<style scoped>
.qc-result-tab {
  min-height: 100%;
  display: flex;
  flex-direction: column;
}

.qc-result-tab__tabs {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
  padding: 12px;
  background: #fff;
  border-bottom: 1px solid #e2e8f0;
}

.qc-result-tab__tab {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  border: 1px solid #dbeafe;
  background: #eff6ff;
  color: #2563eb;
  border-radius: 12px;
  padding: 9px 8px;
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
}

.qc-result-tab__tab--active {
  background: #2563eb;
  color: #fff;
  border-color: #2563eb;
}

.qc-result-tab__tab-icon {
  font-size: 13px;
}

.qc-result-tab__tab-badge {
  min-width: 16px;
  height: 16px;
  padding: 0 4px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.22);
  color: currentColor;
  font-size: 10px;
  line-height: 16px;
  text-align: center;
}

.qc-result-tab__body {
  flex: 1;
  overflow-y: auto;
  padding: 12px;
  background: #f8fafc;
}

.qc-group {
  margin-bottom: 12px;
}

.qc-group__header {
  padding: 7px 10px;
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  margin-bottom: 8px;
}

.qc-group__title {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  font-weight: 700;
  color: #334155;
}

.qc-group__dot {
  width: 8px;
  height: 8px;
  border-radius: 999px;
}

.qc-issue {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 12px;
  margin-bottom: 8px;
}

.qc-issue--dismissed {
  opacity: 0.45;
}

.qc-issue__content {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.qc-issue__desc {
  font-size: 13px;
  color: #0f172a;
  line-height: 1.6;
}

.qc-issue__desc--link {
  text-align: left;
  border: none;
  background: transparent;
  padding: 0;
  cursor: pointer;
}

.qc-issue__desc--link:hover {
  color: #2563eb;
  text-decoration: underline;
}

.qc-issue__suggestion {
  background: #fff7ed;
  border-left: 3px solid #f59e0b;
  color: #9a3412;
  font-size: 12px;
  padding: 6px 8px;
  border-radius: 8px;
  line-height: 1.5;
}

.qc-issue__actions {
  display: flex;
  justify-content: flex-end;
  gap: 4px;
  margin-top: 8px;
}

.qc-empty {
  min-height: 280px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  color: #64748b;
}

.qc-empty__icon {
  font-size: 30px;
  color: #22c55e;
  margin-bottom: 10px;
}

.qc-empty__title {
  font-size: 13px;
  font-weight: 700;
}

.qc-result-tab__footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 10px 12px;
  border-top: 1px solid #e2e8f0;
  background: #fff;
  font-size: 12px;
  color: #475569;
}

.qc-result-tab__footer-actions {
  display: flex;
  align-items: center;
  gap: 4px;
}

.custom-scrollbar::-webkit-scrollbar {
  width: 4px;
}

.custom-scrollbar::-webkit-scrollbar-track {
  background: transparent;
}

.custom-scrollbar::-webkit-scrollbar-thumb {
  background: #cbd5e1;
  border-radius: 999px;
}
</style>
