<template>
  <div class="qc-alert-wrapper">
    <!-- 浮动触发按钮 -->
    <div v-if="!visible" class="qc-trigger-btn" @click="visible = true">
      <a-badge :count="totalIssueCount" :offset="[-2, 2]">
        <div class="trigger-icon">
          <BellOutlined />
        </div>
      </a-badge>
    </div>

    <!-- 浮动质控面板 -->
    <Transition name="qc-slide">
      <div v-if="visible" class="qc-alert-panel" :style="panelStyle">
        <!-- 标题栏 -->
        <div class="panel-titlebar" @mousedown="startDrag">
          <div class="titlebar-left">
            <AlertOutlined class="title-icon" />
            <span class="title-text">质控提醒</span>
            <a-tag v-if="totalIssueCount > 0" color="error" class="count-tag">
              {{ totalIssueCount }}
            </a-tag>
          </div>
          <div class="titlebar-actions">
            <a-button
              type="text"
              size="small"
              :loading="analyzing"
              class="action-btn"
              @click="refreshQC"
            >
              <ReloadOutlined />
            </a-button>
            <a-button
              type="text"
              size="small"
              class="action-btn close-btn"
              @click="visible = false"
            >
              <CloseOutlined />
            </a-button>
          </div>
        </div>

        <!-- 患者信息条 -->
        <div v-if="patientInfo" class="patient-bar">
          <div class="patient-main">
            <UserOutlined class="patient-icon" />
            <span class="patient-name">{{ patientInfo.name }}</span>
            <a-divider type="vertical" />
            <span class="patient-meta">{{ patientInfo.sex }}</span>
            <a-divider type="vertical" />
            <span class="patient-meta">{{ patientInfo.age }}</span>
          </div>
          <div class="patient-diagnosis" :title="patientInfo.diagnosis">
            {{ patientInfo.diagnosis }}
          </div>
        </div>
        <div v-else class="patient-bar patient-bar-empty">
          <span class="empty-hint">暂无病历数据，请先加载病历</span>
        </div>

        <!-- 分类 Tab -->
        <div class="qc-tabs">
          <div
            v-for="tab in qcTabs"
            :key="tab.key"
            :class="['qc-tab', { active: activeTab === tab.key }]"
            @click="activeTab = tab.key"
          >
            <component :is="tab.icon" class="tab-icon" />
            <span>{{ tab.label }}</span>
            <a-badge
              v-if="getTabCount(tab.key) > 0"
              :count="getTabCount(tab.key)"
              :number-style="{
                backgroundColor: activeTab === tab.key ? '#fff' : '#ff4d4f',
                color: activeTab === tab.key ? '#0a6cff' : '#fff',
                fontSize: '10px',
                minWidth: '16px',
                height: '16px',
                lineHeight: '16px',
              }"
              class="tab-badge"
            />
          </div>
        </div>

        <!-- 问题列表 -->
        <div class="qc-issues-container custom-scrollbar">
          <template v-if="currentIssues.length > 0">
            <div v-for="(group, gIdx) in groupedIssues" :key="gIdx" class="issue-group">
              <div class="group-header">
                <span class="group-title">
                  <span class="group-dot" :style="{ background: severityColor(group.severity) }" />
                  {{ group.title }} ({{ group.items.length }})
                </span>
              </div>
              <div
                v-for="(issue, iIdx) in group.items"
                :key="iIdx"
                :class="['issue-item', { dismissed: issue.dismissed }]"
              >
                <div class="issue-content">
                  <div class="issue-severity">
                    <a-tag :color="severityTagColor(issue.severity)" size="small">
                      {{ severityLabel(issue.severity) }}
                    </a-tag>
                  </div>
                  <div class="issue-desc">
                    {{ issue.description }}
                  </div>
                  <div v-if="issue.suggestion" class="issue-suggestion">
                    修正建议：{{ issue.suggestion }}
                  </div>
                </div>
                <div class="issue-actions">
                  <!-- 缺陷操作按钮组 -->
                  <a-dropdown v-if="issue.id" :trigger="['click']">
                    <a-button type="link" size="small" class="action-more-btn">
                      操作 <DownOutlined />
                    </a-button>
                    <template #overlay>
                      <a-menu @click="({ key }: any) => handleDefectAction(key, issue)">
                        <a-menu-item key="urge"> <SendOutlined /> 催办 </a-menu-item>
                        <a-menu-item key="mark_remediated">
                          <EditOutlined /> 标记已整改
                        </a-menu-item>
                        <a-menu-divider />
                        <a-menu-item key="approve">
                          <CheckOutlined style="color: #52c41a" /> 审核通过
                        </a-menu-item>
                        <a-menu-item key="reject">
                          <CloseCircleOutlined style="color: #ff4d4f" /> 审核存疑
                        </a-menu-item>
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
                  <a-button
                    type="text"
                    size="small"
                    class="dismiss-btn"
                    @click="dismissIssue(issue)"
                  >
                    忽略
                  </a-button>
                </div>
              </div>
            </div>
          </template>
          <div v-else class="no-issues">
            <CheckCircleOutlined class="no-issues-icon" />
            <p>{{ analyzing ? '正在分析...' : '未发现质控问题' }}</p>
          </div>
        </div>

        <!-- 底部状态栏 -->
        <div class="panel-footer">
          <span class="footer-stat">
            共 <strong>{{ totalIssueCount }}</strong> 个问题
          </span>
          <div class="footer-actions">
            <a-button type="link" size="small" :loading="exporting" @click="handleExportDefects">
              <DownloadOutlined /> 导出
            </a-button>
            <span class="footer-detail">
              <span v-if="severityCount('error') > 0" class="stat-error"
                >{{ severityCount('error') }} 严重</span
              >
              <span v-if="severityCount('warning') > 0" class="stat-warning"
                >{{ severityCount('warning') }} 警告</span
              >
              <span v-if="severityCount('info') > 0" class="stat-info"
                >{{ severityCount('info') }} 提示</span
              >
            </span>
          </div>
        </div>
      </div>
    </Transition>
  </div>
</template>

<script setup lang="ts">
import { STANDARD_REQUEST_TIMEOUT_MS } from '@/config/requestTimeouts'
import { useWorkstationConfirmation } from '@/components/layout/workstationConfirmation'
import { ref, computed, watch, reactive } from 'vue'
import { message } from 'ant-design-vue'
import {
  BellOutlined,
  AlertOutlined,
  CloseOutlined,
  ReloadOutlined,
  UserOutlined,
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
} from '@ant-design/icons-vue'
import {
  urgeDefect,
  markDefectRemediated,
  approveDefect,
  rejectDefect,
  exportDefects,
} from '@/api/defects'

// ==================== Types ====================
interface QCIssue {
  id: string
  category: 'form' | 'coding' | 'cost'
  severity: 'error' | 'warning' | 'info'
  group: string
  description: string
  suggestion?: string
  actionLabel?: string
  dismissed?: boolean
}

interface PatientInfo {
  name: string
  sex: string
  age: string
  diagnosis: string
}

// ==================== Props & Emits ====================
const props = defineProps<{
  frontpage?: Record<string, any> | null
  analyzing?: boolean
  visitId?: string | null
  patientId?: string | null
}>()

const emit = defineEmits<{
  (e: 'action', issue: QCIssue): void
  (e: 'refresh'): void
}>()

// ==================== 状态 ====================
const visible = ref(false)
const activeTab = ref<'form' | 'coding' | 'cost'>('form')
const issues = ref<QCIssue[]>([])

// 拖拽
const panelPos = reactive({ x: 0, y: 0 })
const dragging = ref(false)
const dragOffset = reactive({ x: 0, y: 0 })

const panelStyle = computed(() => {
  if (panelPos.x === 0 && panelPos.y === 0) return {}
  return {
    position: 'fixed' as const,
    right: 'auto',
    bottom: 'auto',
    left: `${panelPos.x}px`,
    top: `${panelPos.y}px`,
  }
})

// ==================== Tab 配置 ====================
const qcTabs = [
  { key: 'form' as const, label: '首页质控', icon: FileTextOutlined },
  { key: 'coding' as const, label: '编码质控', icon: CodeOutlined },
  { key: 'cost' as const, label: '控费监测', icon: DollarOutlined },
]

// ==================== 患者信息 ====================
const patientInfo = computed<PatientInfo | null>(() => {
  const fp = props.frontpage
  if (!fp) return null
  return {
    name: fp.patient_name || fp.basic_info?.name || '未知患者',
    sex: fp.sex || fp.basic_info?.sex || '--',
    age: fp.age || fp.basic_info?.age || '--',
    diagnosis:
      fp.primary_diagnosis_name ||
      fp.diagnoses?.discharge_main_diagnosis_text ||
      fp.diagnoses?.discharge_main_diagnosis ||
      '暂无诊断信息',
  }
})

// ==================== 质控结果 ====================
const currentIssues = computed(() =>
  issues.value.filter((i) => i.category === activeTab.value && !i.dismissed),
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

const totalIssueCount = computed(() => issues.value.filter((i) => !i.dismissed).length)

const getTabCount = (tab: string) =>
  issues.value.filter((i) => i.category === tab && !i.dismissed).length

const severityCount = (sev: string) =>
  issues.value.filter((i) => i.severity === sev && !i.dismissed).length

function getCodingIssueGroup(issue: Record<string, any>, source: 'rule' | 'llm') {
  const dimension = String(issue?.dimension || '').toLowerCase()
  const ruleId = String(issue?.rule_id || '').toUpperCase()
  if (dimension === 'format') return '基础编码校验 / 格式规范'
  if (dimension === 'existence') return '基础编码校验 / 编码库匹配'

  if (
    source === 'llm' ||
    ruleId.startsWith('CQ-TENDER') ||
    ['merge', 'exclusion', 'primary', 'consistency', 'additional'].includes(dimension)
  ) {
    const labels: Record<string, string> = {
      merge: '编码内涵质控 / 合并编码',
      exclusion: '编码内涵质控 / 互斥编码',
      primary: '编码内涵质控 / 主诊断选择',
      consistency: '编码内涵质控 / 逻辑一致性',
      additional: '编码内涵质控 / 附加编码',
    }
    return labels[dimension] || '编码内涵质控'
  }

  return '编码质控'
}

// ==================== 辅助方法 ====================
const severityColor = (sev: string) =>
  ({
    error: '#ff4d4f',
    warning: '#faad14',
    info: '#0a6cff',
  })[sev] || '#999'

const severityTagColor = (sev: string) =>
  ({
    error: 'error',
    warning: 'warning',
    info: 'processing',
  })[sev] || 'default'

const severityLabel = (sev: string) =>
  ({
    error: '严重',
    warning: '警告',
    info: '提示',
  })[sev] || '未知'

const dismissIssue = (issue: QCIssue) => {
  issue.dismissed = true
}

const refreshQC = () => {
  emit('refresh')
  generateMockIssues()
}

// ==================== 缺陷操作 ====================
const exporting = ref(false)

const handleDefectAction = async (action: string, issue: QCIssue) => {
  const defectId = issue.id
  try {
    switch (action) {
      case 'urge': {
        const res = await urgeDefect(defectId, { message: `请尽快处理：${issue.description}` })
        if (res.success) message.success('催办成功')
        else message.error(res.message || '催办失败')
        break
      }
      case 'mark_remediated': {
        const res = await markDefectRemediated(defectId, { remediation_note: '已整改' })
        if (res.success) {
          message.success('已标记为整改')
          issue.dismissed = true
        } else {
          message.error(res.message || '标记失败')
        }
        break
      }
      case 'approve': {
        const res = await approveDefect(defectId, '审核通过')
        if (res.success) {
          message.success('审核通过')
          issue.dismissed = true
        } else {
          message.error(res.message || '审核失败')
        }
        break
      }
      case 'reject': {
        workstationConfirmation.confirm({
          title: '审核存疑',
          content: `确认将缺陷“${issue.description.slice(0, 30)}...”标记为存疑？`,
          okText: '确认',
          cancelText: '取消',
          okType: 'danger',
          async onOk() {
            const res = await rejectDefect(defectId, { reason: '审核存疑，需进一步确认' })
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

const handleExportDefects = async () => {
  exporting.value = true
  try {
    const res = await exportDefects({ format: 'xlsx' })
    if (res.success) {
      message.success('导出成功')
    } else {
      message.info('导出功能开发中')
    }
  } catch (err) {
    message.error('导出失败')
  } finally {
    exporting.value = false
  }
}

// ==================== 拖拽 ====================
const startDrag = (e: MouseEvent) => {
  const panel = (e.target as HTMLElement).closest('.qc-alert-panel') as HTMLElement
  if (!panel) return
  dragging.value = true
  const rect = panel.getBoundingClientRect()
  dragOffset.x = e.clientX - rect.left
  dragOffset.y = e.clientY - rect.top

  const onMove = (ev: MouseEvent) => {
    if (!dragging.value) return
    panelPos.x = ev.clientX - dragOffset.x
    panelPos.y = ev.clientY - dragOffset.y
  }
  const onUp = () => {
    dragging.value = false
    document.removeEventListener('mousemove', onMove)
    document.removeEventListener('mouseup', onUp)
  }
  document.addEventListener('mousemove', onMove)
  document.addEventListener('mouseup', onUp)
}

import { integratedQCEngine } from '@/services/integrated-qc-engine'
import type { ComprehensiveQCResult, QCRuleResult, DocumentType } from '@/types/enhanced-qc-rule'
import axios from 'axios'

const workstationConfirmation = useWorkstationConfirmation()

// ==================== 引擎对接与数据生成 ====================

// --- 后端编码质控 API 调用 ---
const codingQCLoading = ref(false)

const fetchCodingQCFromBackend = async () => {
  // 优先使用 visit_id 模式：直接从 PG 数据库读取
  const useVisitIdMode = !!props.visitId
  const fp = props.frontpage
  if (!useVisitIdMode && !fp) return []

  let payload: any
  if (useVisitIdMode) {
    payload = {
      visit_id: props.visitId,
      patient_id: props.patientId || '',
    }
  } else {
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
    for (let i = 0; i < otherTexts.length; i++) {
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
    const resp = await axios.post('/api/v1/qc/coding-qc/check', payload, {
      timeout: STANDARD_REQUEST_TIMEOUT_MS,
    })
    const data = resp.data?.data
    if (!data) return []

    const codingIssues: QCIssue[] = []
    let idx = 0

    // 规则层问题
    for (const issue of data.rule_issues || []) {
      codingIssues.push({
        id: `coding-rule-${idx++}`,
        category: 'coding',
        severity:
          issue.severity === 'error' ? 'error' : issue.severity === 'warning' ? 'warning' : 'info',
        group: getCodingIssueGroup(issue, 'rule'),
        description: issue.description,
        suggestion: issue.suggestion,
        actionLabel: '修正编码',
      })
    }

    // LLM 层问题
    const dimensionLabels: Record<string, string> = {
      merge: '编码合并',
      exclusion: '编码互斥',
      primary: '主诊断选择',
      consistency: '编码一致性',
    }
    for (const issue of data.llm_issues || []) {
      codingIssues.push({
        id: `coding-llm-${idx++}`,
        category: 'coding',
        severity:
          issue.severity === 'error' ? 'error' : issue.severity === 'warning' ? 'warning' : 'info',
        group:
          getCodingIssueGroup(issue, 'llm') || dimensionLabels[issue.dimension] || 'LLM 语义审查',
        description: issue.description,
        suggestion: issue.suggestion,
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

// --- 前端引擎（首页质控）---
const runRealQCEngine = async () => {
  const fp = props.frontpage
  if (!fp) {
    issues.value = []
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
    // 并行执行：前端引擎（首页质控）+ 后端 API（编码质控）
    const [engineResult, codingIssues] = await Promise.all([
      integratedQCEngine.executeQualityControl(patientData),
      fetchCodingQCFromBackend(),
    ])

    const newIssues: QCIssue[] = []
    let issueId = 0

    // 前端引擎结果 -> 首页质控 + 控费 Tab
    if (engineResult.ruleResults && engineResult.ruleResults.length > 0) {
      engineResult.ruleResults.forEach((ruleRes: QCRuleResult) => {
        if (!ruleRes.isCompliant && ruleRes.findings && ruleRes.findings.length > 0) {
          ruleRes.findings.forEach((finding) => {
            let sev: 'error' | 'warning' | 'info' = 'info'
            if (finding.severity === 'critical' || finding.severity === 'major') sev = 'error'
            else if (finding.severity === 'minor') sev = 'warning'

            let tabCat: 'form' | 'coding' | 'cost' = 'form'
            if (ruleRes.ruleName.includes('璐圭敤') || finding.description.includes('DRG')) {
              tabCat = 'cost'
            }
            // 不再把编码相关问题放到 coding Tab，由后端 API 负责

            newIssues.push({
              id: `sys-${issueId++}`,
              category: tabCat,
              severity: sev,
              group: ruleRes.ruleName || '未知规则',
              description: finding.description,
              suggestion: finding.recommendation,
              actionLabel: '查看详情',
            })
          })
        }
      })
    }

    // 后端 API 结果 -> 编码质控 Tab
    newIssues.push(...codingIssues)

    issues.value = newIssues
  } catch (error) {
    console.error('质控引擎执行异常', error)
    issues.value = []
  }
}

const generateMockIssues = () => {
  runRealQCEngine()
}

// 监听 frontpage 变化，自动触发质控
watch(
  () => props.frontpage,
  (newVal) => {
    if (newVal) {
      generateMockIssues()
      setTimeout(() => {
        if (totalIssueCount.value > 0 && !visible.value) {
          visible.value = true
        }
      }, 4000)
    }
  },
  { deep: true },
)
</script>

<style scoped>
/* trigger */
.qc-trigger-btn {
  position: fixed;
  right: 24px;
  bottom: 24px;
  z-index: 100;
  cursor: pointer;
  transition: transform 0.2s;
}
.qc-trigger-btn:hover {
  transform: scale(1.08);
}
.trigger-icon {
  width: 52px;
  height: 52px;
  border-radius: 18px;
  background: linear-gradient(135deg, #0ea5e9 0%, #0a6cff 100%);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 22px;
  box-shadow: 0 16px 32px rgba(37, 99, 235, 0.28);
}

/* panel */
.qc-alert-panel {
  position: fixed;
  right: 24px;
  bottom: 24px;
  width: 392px;
  max-height: calc(100vh - 100px);
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.98) 0%, rgba(248, 250, 252, 0.98) 100%);
  border: 1px solid rgba(226, 232, 240, 0.9);
  border-radius: 24px;
  box-shadow: 0 22px 48px rgba(15, 23, 42, 0.14);
  display: flex;
  flex-direction: column;
  z-index: 1000;
  overflow: hidden;
}

/* title */
.panel-titlebar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 18px;
  background: linear-gradient(135deg, #eff6ff 0%, #f8fafc 72%);
  color: #1d1d1f;
  cursor: grab;
  user-select: none;
  border-bottom: 1px solid rgba(226, 232, 240, 0.85);
}
.panel-titlebar:active {
  cursor: grabbing;
}
.titlebar-left {
  display: flex;
  align-items: center;
  gap: 8px;
}
.title-icon {
  font-size: 16px;
  color: #0284c7;
}
.title-text {
  font-weight: 700;
  font-size: 14px;
}
.count-tag {
  margin-left: 4px;
}
.titlebar-actions {
  display: flex;
  gap: 2px;
}
.action-btn {
  color: #64748b !important;
}
.action-btn:hover {
  color: #1d1d1f !important;
  background: rgba(255, 255, 255, 0.8) !important;
}
.close-btn:hover {
  color: #ff4d4f !important;
}

/* patient */
.patient-bar {
  padding: 12px 18px;
  background: linear-gradient(180deg, rgba(240, 249, 255, 0.9) 0%, rgba(248, 250, 252, 0.9) 100%);
  border-bottom: 1px solid #e0f2fe;
}
.patient-main {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 13px;
}
.patient-icon {
  color: #0284c7;
  margin-right: 4px;
}
.patient-name {
  font-weight: 700;
  color: #1e293b;
}
.patient-meta {
  color: #64748b;
}
.patient-diagnosis {
  margin-top: 4px;
  font-size: 12px;
  color: #64748b;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.patient-bar-empty {
  text-align: center;
  color: #94a3b8;
}
.empty-hint {
  font-size: 12px;
}

/* tabs */
.qc-tabs {
  display: flex;
  gap: 6px;
  padding: 10px 10px 6px;
  border-bottom: 1px solid #f1f5f9;
  background: rgba(255, 255, 255, 0.72);
}
.qc-tab {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  padding: 9px 0;
  font-size: 13px;
  color: #64748b;
  cursor: pointer;
  border: 1px solid transparent;
  border-radius: 14px;
  transition: all 0.2s;
  position: relative;
}
.qc-tab:hover {
  color: #0369a1;
  background: #f8fafc;
}
.qc-tab.active {
  color: #0369a1;
  font-weight: 600;
  border-color: #bae6fd;
  background: #f0f9ff;
  box-shadow: 0 8px 18px rgba(125, 211, 252, 0.12);
}
.tab-icon {
  font-size: 14px;
}
.tab-badge {
  margin-left: 2px;
}

/* issues */
.qc-issues-container {
  flex: 1;
  overflow-y: auto;
  padding: 10px 12px 12px;
  max-height: 400px;
  background: linear-gradient(180deg, rgba(248, 250, 252, 0.2) 0%, rgba(255, 255, 255, 0.55) 100%);
}
.issue-group {
  margin-bottom: 12px;
}
.group-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 10px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 14px;
  margin-bottom: 6px;
}
.group-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-weight: 600;
  color: #334155;
}
.group-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}
.issue-item {
  padding: 11px 12px;
  border: 1px solid #e2e8f0;
  border-radius: 16px;
  margin-bottom: 6px;
  transition: all 0.2s;
  background: rgba(255, 255, 255, 0.94);
}
.issue-item:hover {
  border-color: #bae6fd;
  box-shadow: 0 12px 22px rgba(148, 163, 184, 0.12);
}
.issue-item.dismissed {
  opacity: 0.4;
  text-decoration: line-through;
}
.issue-content {
  margin-bottom: 6px;
}
.issue-severity {
  margin-bottom: 4px;
}
.issue-desc {
  font-size: 13px;
  color: #334155;
  line-height: 1.55;
}
.issue-suggestion {
  font-size: 12px;
  color: #64748b;
  margin-top: 4px;
  padding: 6px 9px;
  background: #fffbe6;
  border-radius: 12px;
  border: 1px solid #fde68a;
}
.issue-actions {
  display: flex;
  justify-content: flex-end;
  gap: 4px;
}
.dismiss-btn {
  color: #94a3b8 !important;
  font-size: 12px;
}

/* empty */
.no-issues {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px 0;
  color: #94a3b8;
}
.no-issues-icon {
  font-size: 36px;
  color: #22c55e;
  margin-bottom: 8px;
}

/* footer */
.panel-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 16px;
  background: rgba(248, 250, 252, 0.86);
  border-top: 1px solid #e2e8f0;
  font-size: 12px;
  color: #64748b;
}
.footer-detail {
  display: flex;
  gap: 8px;
}
.footer-actions {
  display: flex;
  align-items: center;
  gap: 4px;
}
.action-more-btn {
  font-size: 12px !important;
  padding: 0 4px !important;
}
.stat-error {
  color: #ef4444;
  font-weight: 600;
}
.stat-warning {
  color: #f59e0b;
  font-weight: 600;
}
.stat-info {
  color: #0284c7;
  font-weight: 600;
}

/* motion */
.qc-slide-enter-active,
.qc-slide-leave-active {
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}
.qc-slide-enter-from,
.qc-slide-leave-to {
  opacity: 0;
  transform: translateY(20px) scale(0.95);
}

/* scrollbar */
.custom-scrollbar::-webkit-scrollbar {
  width: 4px;
}
.custom-scrollbar::-webkit-scrollbar-track {
  background: transparent;
}
.custom-scrollbar::-webkit-scrollbar-thumb {
  background: #d9d9d9;
  border-radius: 4px;
}
.custom-scrollbar::-webkit-scrollbar-thumb:hover {
  background: #bfbfbf;
}
</style>
