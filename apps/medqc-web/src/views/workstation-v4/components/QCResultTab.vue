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
        <span v-if="getTabCount(tab.key) > 0" class="qc-result-tab__tab-badge">{{
          getTabCount(tab.key)
        }}</span>
      </button>
    </div>

    <div class="qc-result-tab__body custom-scrollbar">
      <div class="qc-overview">
        <div>
          <div class="qc-overview__eyebrow">当前质控</div>
          <div class="qc-overview__title">
            {{ currentTabConfig.label }}
          </div>
          <div class="qc-overview__desc">
            {{ currentTabConfig.desc }}
          </div>
        </div>
        <div v-if="!isTabEmpty || totalIssueCount > 0" class="qc-overview__status">
          <span class="qc-overview__status-label">{{
            currentIssues.length > 0 ? '当前问题' : '当前状态'
          }}</span>
          <strong class="qc-overview__status-value">{{
            currentIssues.length > 0 ? currentIssues.length : '待分析'
          }}</strong>
        </div>
      </div>

      <div v-if="currentTab === 'coding' && !isTabEmpty" class="qc-coding-summary">
        <div class="qc-coding-summary__item">
          <span>基础编码校验</span>
          <strong>{{ codingBaseIssueCount }}</strong>
        </div>
        <div class="qc-coding-summary__item qc-coding-summary__item--semantic">
          <span>编码内涵质控</span>
          <strong>{{ codingSemanticIssueCount }}</strong>
        </div>
        <div class="qc-coding-summary__item">
          <span>LLM 语义审查</span>
          <strong>{{ codingLlmIssueCount }}</strong>
        </div>
      </div>

      <template v-if="isTabEmpty">
        <div v-if="!isTabLoading" class="qc-start">
          <div class="qc-start__icon-wrap">
            <component :is="currentTabConfig.icon" class="qc-start__icon" />
          </div>
          <div class="qc-start__title">
            {{ currentTabConfig.label }}
          </div>
          <div class="qc-start__desc">
            {{ currentTabConfig.desc }}
          </div>
          <a-button type="primary" size="small" class="qc-start__btn" @click="startCurrentTab">
            <template #icon>
              <ThunderboltOutlined />
            </template>
            开始分析
          </a-button>
        </div>
        <div v-else class="qc-start">
          <a-spin />
          <div class="qc-start__title" style="margin-top: 16px">正在分析...</div>
          <div class="qc-start__desc">
            {{ currentTabConfig.loadingHint }}
          </div>
        </div>
      </template>

      <template v-else-if="currentIssues.length > 0">
        <div class="qc-issue-list custom-scrollbar">
          <section v-for="(group, gIdx) in groupedIssues" :key="gIdx" class="qc-group">
            <header class="qc-group__header">
              <span class="qc-group__dot" :style="{ background: severityColor(group.severity) }" />
              <span class="qc-group__title">{{ group.title }} ({{ group.items.length }})</span>
            </header>

            <article
              v-for="(issue, iIdx) in group.items"
              :key="iIdx"
              :class="['qc-issue', { 'qc-issue--dismissed': issue.dismissed }]"
            >
              <div class="qc-issue__content">
                <span :class="['qc-issue__badge', `qc-issue__badge--${issue.severity}`]">{{
                  severityLabel(issue.severity)
                }}</span>
                <p class="qc-issue__desc" title="定位到相关字段" @click="locateIssue(issue)">
                  {{ issue.description }}
                </p>
              </div>

              <div v-if="issue.suggestion" class="qc-issue__ai-suggestion">
                <div class="qc-issue__ai-label">
                  <ThunderboltOutlined class="qc-issue__ai-icon" />
                  <span>修正建议</span>
                </div>
                <p class="qc-issue__ai-text">
                  {{ issue.suggestion }}
                </p>
              </div>

              <div class="qc-issue__action-bar">
                <div class="qc-issue__action-group">
                  <button type="button" class="qc-issue__ghost-btn" @click="locateIssue(issue)">
                    <svg
                      class="qc-issue__btn-icon"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        stroke-linecap="round"
                        stroke-linejoin="round"
                        stroke-width="2"
                        d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
                      />
                      <path
                        stroke-linecap="round"
                        stroke-linejoin="round"
                        stroke-width="2"
                        d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"
                      />
                    </svg>
                    定位字段
                  </button>
                  <button
                    type="button"
                    class="qc-issue__ghost-btn"
                    @click="$emit('jump-evidence', issue)"
                  >
                    <svg
                      class="qc-issue__btn-icon"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        stroke-linecap="round"
                        stroke-linejoin="round"
                        stroke-width="2"
                        d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                      />
                    </svg>
                    文书依据
                  </button>
                  <a-dropdown v-if="issue.id" :trigger="['click']">
                    <button type="button" class="qc-issue__ghost-btn">操作 <DownOutlined /></button>
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
                </div>
                <button
                  type="button"
                  class="qc-issue__ghost-btn qc-issue__ghost-btn--muted"
                  @click="dismissIssue(issue)"
                >
                  忽略
                </button>
              </div>
            </article>
          </section>
        </div>
      </template>

      <div v-else class="qc-empty">
        <CheckCircleOutlined class="qc-empty__icon" style="color: #52c41a" />
        <div class="qc-empty__title">未发现质控问题</div>
        <a-button type="link" size="small" style="margin-top: 8px" @click="startCurrentTab">
          <ReloadOutlined /> 重新分析
        </a-button>
      </div>
    </div>

    <footer v-if="totalIssueCount > 0" class="qc-result-tab__footer">
      <span
        >共 <strong>{{ totalIssueCount }}</strong> 个问题</span
      >
      <div class="qc-result-tab__footer-actions">
        <a-button type="link" size="small" :loading="isTabLoading" @click="startCurrentTab">
          <ReloadOutlined /> 刷新
        </a-button>
        <a-button type="link" size="small" :loading="exporting" @click="handleExportDefects">
          <DownloadOutlined /> 导出
        </a-button>
      </div>
    </footer>
  </div>
</template>

<script setup lang="ts">
import { useWorkstationConfirmation } from '@/components/layout/workstationConfirmation'
import { computed, ref, watch } from 'vue'
import { message } from 'ant-design-vue'
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
  ThunderboltOutlined,
} from '@ant-design/icons-vue'
import { apiClient } from '@/services/apiService'
import {
  urgeDefect,
  markDefectRemediated,
  approveDefect,
  rejectDefect,
  exportDefects,
} from '@/api/defects'
import type { WorkstationSnapshotState } from '../types'

const workstationConfirmation = useWorkstationConfirmation()

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
  snapshotState?: Partial<Record<'form' | 'coding' | 'cost', WorkstationSnapshotState>>
}>()

const emit = defineEmits<{
  (e: 'action', issue: QCIssue): void
  (e: 'refresh'): void
  (e: 'issues-change', issues: QCIssue[]): void
  (e: 'locate-field', payload: { target: LocateTarget; issue: QCIssue }): void
  (e: 'jump-evidence', issue: QCIssue): void
  (
    e: 'persistence-finished',
    payload: {
      workflow: 'form' | 'coding' | 'cost'
      persistence?: Record<string, any> | null
    },
  ): void
}>()

const internalTab = ref<'form' | 'coding' | 'cost'>('form')
const currentTab = computed(() => props.activeTab || internalTab.value)
const issues = ref<QCIssue[]>([])
const exporting = ref(false)
const codingQCLoading = ref(false)
const formQCLoading = ref(false)
const costQCLoading = ref(false)
const formAnalyzed = ref(false)
const codingAnalyzed = ref(false)
const costAnalyzed = ref(false)

const qcTabs = [
  {
    key: 'form' as const,
    label: '首页质控',
    icon: FileTextOutlined,
    desc: '基于病案首页数据，检查完整性与一致性规则',
    loadingHint: '正在核验首页填报规范...',
  },
  {
    key: 'coding' as const,
    label: '编码质控',
    icon: CodeOutlined,
    desc: '校验 ICD 编码的逻辑一致性与规范性',
    loadingHint: '正在调用后端编码校验引擎...',
  },
  {
    key: 'cost' as const,
    label: '控费监测',
    icon: DollarOutlined,
    desc: '监控费用异常波动与 DRG 盈亏风险',
    loadingHint: '正在计算费用异常指标...',
  },
]

const currentTabConfig = computed(() => qcTabs.find((t) => t.key === currentTab.value) || qcTabs[0])

const isTabLoading = computed(() => {
  const tab = currentTab.value
  if (tab === 'form') return formQCLoading.value
  if (tab === 'coding') return codingQCLoading.value
  if (tab === 'cost') return costQCLoading.value
  return false
})

const isTabEmpty = computed(() => {
  const tab = currentTab.value
  if (tab === 'form') return !formAnalyzed.value
  if (tab === 'coding') return !codingAnalyzed.value
  if (tab === 'cost') return !costAnalyzed.value
  return true
})

const currentIssues = computed(() =>
  issues.value.filter((i) => i.category === currentTab.value && !i.dismissed),
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

const codingBaseIssueCount = computed(
  () =>
    currentIssues.value.filter(
      (issue) => issue.category === 'coding' && issue.group.startsWith('基础编码校验'),
    ).length,
)

const codingSemanticIssueCount = computed(
  () =>
    currentIssues.value.filter(
      (issue) => issue.category === 'coding' && issue.group.startsWith('编码内涵质控'),
    ).length,
)

const codingLlmIssueCount = computed(
  () =>
    currentIssues.value.filter(
      (issue) =>
        issue.category === 'coding' &&
        (issue.id.startsWith('coding-llm') || issue.group.includes('LLM')),
    ).length,
)

const totalIssueCount = computed(() => issues.value.filter((i) => !i.dismissed).length)

function getTabCount(tab: string) {
  return issues.value.filter((i) => i.category === tab && !i.dismissed).length
}

function severityColor(sev: string) {
  return (
    {
      error: '#ef4444',
      warning: '#f59e0b',
      info: '#2563eb',
    }[sev] || '#94a3b8'
  )
}

function severityLabel(sev: string) {
  return (
    {
      error: '严重',
      warning: '警告',
      info: '提示',
    }[sev] || '未知'
  )
}

function notifyPersistence(
  workflow: 'form' | 'coding' | 'cost',
  persistence?: Record<string, any> | null,
) {
  emit('persistence-finished', {
    workflow,
    persistence: persistence || null,
  })
}

function buildPersistenceMessage(
  workflow: 'form' | 'coding' | 'cost',
  persistence?: Record<string, any> | null,
) {
  const defectsCreated = Number(persistence?.defects_created || 0)
  const defectsUpdated = Number(persistence?.defects_updated || 0)
  const defectsResolved = Number(persistence?.defects_resolved || 0)
  const totalActive = defectsCreated + defectsUpdated

  if (workflow === 'form') {
    if (totalActive > 0) {
      return `首页质控完成，发现 ${totalActive} 条问题并更新消息`
    }
    if (defectsResolved > 0) {
      return '首页质控完成，未发现问题，已更新最新状态'
    }
    return '首页质控完成，结果已保存'
  }
  if (workflow === 'coding') {
    if (totalActive > 0) {
      return `编码质控完成，发现 ${totalActive} 条缺陷并更新消息`
    }
    if (defectsResolved > 0) {
      return '编码质控完成，未发现问题，已更新最新状态'
    }
    return '编码质控完成，结果已保存'
  }
  if (totalActive > 0) {
    return `控费监测完成，发现 ${totalActive} 条问题并更新消息`
  }
  if (defectsResolved > 0) {
    return '控费监测完成，未发现问题，已更新最新状态'
  }
  return '控费监测完成，结果已保存'
}

function hydrateIssuesFromSnapshot(
  snapshotState?: Partial<Record<'form' | 'coding' | 'cost', WorkstationSnapshotState>>,
) {
  if (!snapshotState) return

  const nextIssues: QCIssue[] = []
  const tabs: Array<'form' | 'coding' | 'cost'> = ['form', 'coding', 'cost']
  for (const tab of tabs) {
    const snapshot = snapshotState[tab]
    if (snapshot?.analyzed) {
      if (tab === 'form') formAnalyzed.value = true
      if (tab === 'coding') codingAnalyzed.value = true
      if (tab === 'cost') costAnalyzed.value = true
    }
    for (const [index, issue] of (snapshot?.issues || []).entries()) {
      nextIssues.push({
        id: issue.id || `${tab}-snapshot-${index + 1}`,
        category: tab,
        severity: toIssueSeverity(String(issue.severity || 'info')),
        group: String(issue.category || currentTabConfig.value.label || '质控结果'),
        description: String(issue.description || issue.rule_name || '未命名问题'),
        suggestion: issue.suggestion,
        evidence:
          typeof issue.evidence === 'string' ? issue.evidence : String(issue.location || ''),
      })
    }
  }

  issues.value = nextIssues
  emit('issues-change', nextIssues.slice())
}

function toIssueSeverity(severity: string): 'error' | 'warning' | 'info' {
  if (severity === 'error' || severity === 'critical' || severity === 'major') return 'error'
  if (severity === 'warning' || severity === 'minor') return 'warning'
  return 'info'
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

async function handleDefectAction(action: string, issue: QCIssue) {
  try {
    switch (action) {
      case 'urge': {
        const res = await urgeDefect(issue.id, { message: `请尽快处理：${issue.description}` })
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
        const res = await approveDefect(issue.id, '审核通过')
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
        workstationConfirmation.confirm({
          title: '审核存疑',
          content: `确认将缺陷“${issue.description.slice(0, 30)}...”标记为存疑？`,
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
    if (res.success) {
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
  const useVisitIdMode = !!props.visitId
  const fp = props.frontpage

  if (!useVisitIdMode && !fp) return { issues: [], persistence: null }

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

  const executeRequest = async (requestPayload: Record<string, any>, timeout = 30000) => {
    const resp = await apiClient.post('/api/v1/qc/coding-qc/check', requestPayload, { timeout })
    const data = resp.data?.data
    if (!data) return { issues: [], persistence: null, degraded: false }

    const codingIssues: QCIssue[] = []
    let idx = 0

    for (const issue of data.rule_issues || []) {
      codingIssues.push({
        id: `coding-rule-${(idx += 1)}`,
        category: 'coding',
        severity: toIssueSeverity(issue.severity),
        group: getCodingIssueGroup(issue, 'rule'),
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

    for (const issue of data.llm_issues || []) {
      codingIssues.push({
        id: `coding-llm-${(idx += 1)}`,
        category: 'coding',
        severity: toIssueSeverity(issue.severity),
        group:
          getCodingIssueGroup(issue, 'llm') || dimensionLabels[issue.dimension] || 'LLM 语义审查',
        description: issue.description,
        suggestion: issue.suggestion,
        evidence: issue.evidence,
        actionLabel: '查看详情',
      })
    }

    return {
      issues: codingIssues,
      persistence: data.persistence || null,
      degraded: Boolean(requestPayload.skip_llm),
    }
  }

  try {
    return await executeRequest(payload)
  } catch (err: any) {
    const maybeTimeout =
      err?.code === 'ECONNABORTED' ||
      String(err?.message || '')
        .toLowerCase()
        .includes('timeout')
    if (maybeTimeout) {
      try {
        const degradedResult = await executeRequest({ ...payload, skip_llm: true }, 20000)
        message.info('编码质控已降级为规则层执行，结果仍会保存并更新消息')
        return degradedResult
      } catch (retryErr) {
        console.error('后端编码质控降级调用失败', retryErr)
        return { issues: [], persistence: null, degraded: false }
      }
    }
    console.error('后端编码质控调用失败', err)
    return { issues: [], persistence: null, degraded: false }
  }
}

async function fetchFrontpageQCFromBackend(frontpage: Record<string, any>) {
  const payload = {
    patient_id: props.patientId || '',
    visit_id: props.visitId || '',
    frontpage,
  }
  const resp = await apiClient.post('/api/v1/qc/formal-qc/validate', payload, { timeout: 30000 })
  const data = resp.data?.data
  if (!data) return { issues: [], persistence: null, passed: 0, total: 0 }

  const issues: QCIssue[] = (data.results || []).map((item: any, index: number) => ({
    id: `form-${index + 1}`,
    category: 'form',
    severity: toIssueSeverity(item.severity),
    group: item.category || '首页质控',
    description: item.message || '',
    suggestion: item.message || '请根据规则提示修正相关字段',
    evidence: item.field_name,
    actionLabel: '定位字段',
  }))

  return {
    issues,
    persistence: data.persistence || null,
    passed: Number(data.passed || 0),
    total: Number(data.total_rules || 0),
  }
}

async function fetchCostQCFromBackend() {
  if (!props.visitId || !props.patientId) {
    return { issues: [], persistence: null, passed: 0, total: 0 }
  }

  const urls = [
    `/api/medical-records/settlement/${props.patientId}/${props.visitId}/qc`,
    `/api/medical-records/settlement/${props.patientId}/${props.visitId}/generate/qc`,
  ]

  let lastError: unknown = null
  for (const url of urls) {
    try {
      const resp = await apiClient.post(url, undefined, { timeout: 30000 })
      const data = resp.data
      const issues: QCIssue[] = (data.results || [])
        .filter((item: any) => !item.passed)
        .map((item: any, index: number) => ({
          id: `cost-${index + 1}`,
          category: 'cost',
          severity: toIssueSeverity(item.severity),
          group: item.category || '控费监测',
          description: item.message || '',
          suggestion: item.message || '请复核结算清单相关字段',
          evidence: item.field_name,
          actionLabel: '查看结算',
        }))
      return {
        issues,
        persistence: data.persistence || null,
        passed: Number(data.summary?.passed || 0),
        total: Number(data.summary?.total || 0),
      }
    } catch (err: any) {
      lastError = err
      if (err?.response?.status !== 404) break
    }
  }
  throw lastError
}

async function loadFrontpageData(): Promise<Record<string, any> | null> {
  if (props.visitId && props.patientId) {
    try {
      const resp = await apiClient.get(
        `/api/medical-records/frontpage-sheet/${props.patientId}/${props.visitId}`,
      )
      if (resp.data) return resp.data
    } catch (err: any) {
      if (err?.response?.status !== 404) {
        console.warn('从 PG 读取首页数据失败，回退到 LLM 草稿:', err)
      }
    }
  }
  return props.frontpage || null
}

async function runFormQC() {
  const fpData = await loadFrontpageData()
  if (!fpData) return

  formQCLoading.value = true
  try {
    const result = await fetchFrontpageQCFromBackend(fpData)
    const kept = issues.value.filter((i) => i.category !== 'form')
    kept.push(...result.issues)
    issues.value = kept
    emit('issues-change', kept.slice())
    message.success(buildPersistenceMessage('form', result.persistence))
    notifyPersistence('form', result.persistence)
  } catch (err) {
    console.error('首页质控引擎异常', err)
    message.error('首页质控执行失败')
  } finally {
    formQCLoading.value = false
    formAnalyzed.value = true
  }
}

async function runCodingQC() {
  codingQCLoading.value = true
  try {
    const kept = issues.value.filter((i) => i.category !== 'coding')
    const result = await fetchCodingQCFromBackend()
    kept.push(...result.issues)
    issues.value = kept
    emit('issues-change', kept.slice())
    message.success(buildPersistenceMessage('coding', result.persistence))
    notifyPersistence('coding', result.persistence)
  } catch (err) {
    console.error('编码质控异常', err)
    message.error('编码质控执行失败')
  } finally {
    codingQCLoading.value = false
    codingAnalyzed.value = true
  }
}

async function runCostQC() {
  costQCLoading.value = true
  try {
    const kept = issues.value.filter((i) => i.category !== 'cost')
    const result = await fetchCostQCFromBackend()
    kept.push(...result.issues)
    issues.value = kept
    emit('issues-change', kept.slice())
    message.success(buildPersistenceMessage('cost', result.persistence))
    notifyPersistence('cost', result.persistence)
  } catch (err) {
    console.error('控费监测异常', err)
    message.error('控费监测执行失败')
  } finally {
    costQCLoading.value = false
    costAnalyzed.value = true
  }
}

async function runAllQC() {
  formQCLoading.value = true
  codingQCLoading.value = true
  costQCLoading.value = true
  try {
    const fpData = await loadFrontpageData()
    if (!fpData) {
      issues.value = []
      emit('issues-change', [])
      return
    }
    const [formResult, codingResult, costResult] = await Promise.all([
      fetchFrontpageQCFromBackend(fpData),
      fetchCodingQCFromBackend(),
      fetchCostQCFromBackend(),
    ])
    const newIssues: QCIssue[] = [
      ...formResult.issues,
      ...codingResult.issues,
      ...costResult.issues,
    ]
    issues.value = newIssues
    emit('issues-change', newIssues.slice())
    notifyPersistence('form', formResult.persistence)
    notifyPersistence('coding', codingResult.persistence)
    notifyPersistence('cost', costResult.persistence)
    message.success('全部质控执行完成，结果已保存')
  } catch (error) {
    console.error('质控引擎执行异常', error)
    issues.value = []
    emit('issues-change', [])
    message.error('全部质控执行失败')
  } finally {
    formQCLoading.value = false
    codingQCLoading.value = false
    costQCLoading.value = false
    formAnalyzed.value = true
    codingAnalyzed.value = true
    costAnalyzed.value = true
  }
}

function startCurrentTab() {
  const tab = currentTab.value
  if (tab === 'form') runFormQC()
  else if (tab === 'coding') runCodingQC()
  else if (tab === 'cost') runCostQC()
  else runAllQC()
}

defineExpose({ runFormQC, runCodingQC, runCostQC, runAllQC, startCurrentTab })

watch(
  () => props.frontpage,
  (newVal) => {
    if (!newVal) {
      issues.value = []
      emit('issues-change', [])
      formAnalyzed.value = false
      codingAnalyzed.value = false
      costAnalyzed.value = false
    }
  },
  { deep: true, immediate: true },
)

watch(
  () => props.visitId,
  () => {
    formAnalyzed.value = false
    codingAnalyzed.value = false
    costAnalyzed.value = false
    issues.value = []
    emit('issues-change', [])
  },
)

watch(
  () => props.snapshotState,
  (snapshotState) => {
    if (!snapshotState) return
    hydrateIssuesFromSnapshot(snapshotState)
  },
  { deep: true, immediate: true },
)

watch(
  () => props.refreshSeed,
  () => {
    if (props.frontpage) runAllQC()
  },
)
</script>

<style scoped>
.qc-result-tab {
  min-height: 0;
  height: 100%;
  display: flex;
  flex-direction: column;
  border-radius: 14px;
  background: transparent;
  border: none;
  box-shadow: none;
  overflow: hidden;
}

.qc-result-tab__tabs {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
  padding: 0 0 12px;
  background: transparent;
  border-bottom: none;
}

.qc-result-tab__tab {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  border: 1px solid rgba(203, 213, 225, 0.74);
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.92), rgba(243, 247, 252, 0.96));
  color: #475569;
  border-radius: 12px;
  padding: 10px 8px;
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
  transition: all 0.18s ease;
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.72),
    0 4px 12px rgba(148, 163, 184, 0.06);
}

.qc-result-tab__tab--active {
  background: linear-gradient(180deg, #ffffff, #edf4ff);
  color: #1d4ed8;
  border-color: rgba(147, 197, 253, 0.92);
  box-shadow:
    0 12px 22px rgba(59, 130, 246, 0.12),
    inset 0 1px 0 rgba(255, 255, 255, 0.78);
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
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  padding: 0;
  background: transparent;
}

.qc-issue-list {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 0 2px 14px 0;
  overscroll-behavior: contain;
}

.qc-overview {
  flex-shrink: 0;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  padding: 14px 14px;
  margin-bottom: 12px;
  border-radius: 16px;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.94), rgba(244, 248, 254, 0.98));
  border: 1px solid rgba(203, 213, 225, 0.76);
  box-shadow:
    0 12px 28px rgba(148, 163, 184, 0.1),
    inset 0 1px 0 rgba(255, 255, 255, 0.72);
}

.qc-overview__eyebrow {
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: #2563eb;
  margin-bottom: 4px;
}

.qc-overview__title {
  font-size: 16px;
  line-height: 1.2;
  font-weight: 800;
  color: #0f172a;
  margin-bottom: 4px;
  letter-spacing: -0.02em;
}

.qc-overview__desc {
  max-width: 250px;
  font-size: 12px;
  line-height: 1.6;
  color: #64748b;
}

.qc-overview__status {
  display: flex;
  min-width: 96px;
  flex-direction: column;
  align-items: flex-end;
  justify-content: center;
  gap: 4px;
  padding: 8px 10px;
  border-radius: 10px;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.92), rgba(241, 245, 249, 0.98));
  border: 1px solid rgba(203, 213, 225, 0.74);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.76);
}

.qc-overview__status-label {
  display: block;
  font-size: 10px;
  font-weight: 700;
  color: #64748b;
}

.qc-overview__status-value {
  display: block;
  font-size: 15px;
  line-height: 1;
  font-weight: 800;
  color: #0f172a;
}

.qc-coding-summary {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
  margin: -4px 0 12px;
  flex-shrink: 0;
}

.qc-coding-summary__item {
  min-width: 0;
  padding: 9px 10px;
  border-radius: 12px;
  border: 1px solid rgba(226, 232, 240, 0.92);
  background: rgba(255, 255, 255, 0.86);
  box-shadow: 0 8px 18px rgba(15, 23, 42, 0.04);
}

.qc-coding-summary__item span {
  display: block;
  font-size: 11px;
  color: #64748b;
  line-height: 1.2;
}

.qc-coding-summary__item strong {
  display: block;
  margin-top: 5px;
  font-size: 18px;
  line-height: 1;
  color: #0f172a;
}

.qc-coding-summary__item--semantic {
  border-color: rgba(37, 99, 235, 0.24);
  background: linear-gradient(180deg, rgba(239, 246, 255, 0.9), rgba(255, 255, 255, 0.92));
}

.qc-coding-summary__item--semantic strong {
  color: #2563eb;
}

.qc-start {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  padding: 40px 22px;
  min-height: 268px;
  border-radius: 20px;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.94), rgba(248, 251, 255, 0.98));
  border: 1px dashed rgba(147, 197, 253, 0.52);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.82),
    0 16px 34px rgba(148, 163, 184, 0.1);
}

.qc-start__icon-wrap {
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

.qc-start__icon {
  font-size: 24px;
  color: #2563eb;
}

.qc-start__title {
  font-size: 15px;
  font-weight: 800;
  color: #1e293b;
  margin-bottom: 6px;
}

.qc-start__desc {
  font-size: 12px;
  color: #6b7f96;
  max-width: 228px;
  line-height: 1.6;
  margin-bottom: 18px;
}

.qc-start__btn {
  border-radius: 999px !important;
  box-shadow:
    0 10px 20px rgba(37, 99, 235, 0.18),
    inset 0 1px 0 rgba(255, 255, 255, 0.14) !important;
}

.qc-group {
  margin-bottom: 10px;
}

.qc-group__header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 7px 2px 6px;
  margin-bottom: 6px;
  border-radius: 0;
  background: transparent;
  border: none;
  box-shadow: none;
}

.qc-group__title {
  font-size: 11px;
  font-weight: 800;
  color: #64748b;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}

.qc-group__dot {
  width: 6px;
  height: 6px;
  border-radius: 999px;
  flex-shrink: 0;
  transform: translateY(1px);
}

.qc-issue {
  position: relative;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.96), rgba(248, 250, 252, 0.98));
  border: 1px solid rgba(203, 213, 225, 0.68);
  border-radius: 12px;
  margin-bottom: 8px;
  overflow: hidden;
  box-shadow: 0 8px 18px rgba(148, 163, 184, 0.07);
  transition:
    transform 0.15s ease,
    box-shadow 0.15s ease,
    border-color 0.15s ease;
}

.qc-issue::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 3px;
  background: linear-gradient(180deg, rgba(59, 130, 246, 0.9), rgba(96, 165, 250, 0.56));
}

.qc-issue:hover {
  border-color: rgba(147, 197, 253, 0.95);
  box-shadow: 0 12px 24px rgba(148, 163, 184, 0.11);
}

.qc-issue--dismissed {
  opacity: 0.4;
}

.qc-issue__content {
  padding: 12px 12px 9px 14px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.qc-issue__badge {
  display: inline-flex;
  align-items: center;
  padding: 3px 9px;
  border-radius: 999px;
  font-size: 10px;
  font-weight: 700;
  width: fit-content;
  letter-spacing: 0.01em;
}

.qc-issue__badge--error {
  background: #fef2f2;
  color: #dc2626;
}

.qc-issue__badge--warning {
  background: #fffbeb;
  color: #d97706;
}

.qc-issue__badge--info {
  background: #eff6ff;
  color: #2563eb;
}

.qc-issue__desc {
  font-size: 12px;
  color: #334155;
  line-height: 1.66;
  margin: 0;
  cursor: pointer;
  border: none;
  background: transparent;
  text-align: left;
  padding: 0;
}

.qc-issue__desc:hover {
  color: #1d4ed8;
}

.qc-issue__ai-suggestion {
  margin: 0 12px 10px 14px;
  background: linear-gradient(180deg, rgba(239, 246, 255, 0.78), rgba(248, 250, 252, 0.94));
  border-left: 3px solid #3b82f6;
  border-radius: 0 10px 10px 0;
  padding: 8px 10px;
}

.qc-issue__ai-label {
  display: flex;
  align-items: center;
  gap: 5px;
  margin-bottom: 4px;
}

.qc-issue__ai-label span {
  font-size: 12px;
  font-weight: 700;
  color: #1e40af;
}

.qc-issue__ai-icon {
  font-size: 12px;
  color: #2563eb;
}

.qc-issue__ai-text {
  font-size: 12px;
  color: #475569;
  line-height: 1.55;
  margin: 0;
  font-weight: 500;
}

.qc-issue__action-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 7px 8px 7px 10px;
  background: linear-gradient(180deg, rgba(248, 250, 252, 0.96), rgba(241, 245, 249, 0.98));
  border-top: 1px solid rgba(226, 232, 240, 0.92);
}

.qc-issue__action-group {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-wrap: wrap;
}

.qc-issue__ghost-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 7px;
  border-radius: 999px;
  border: none;
  background: rgba(255, 255, 255, 0.78);
  color: #64748b;
  font-size: 10px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s ease;
  white-space: nowrap;
}

.qc-issue__ghost-btn:hover {
  color: #1d4ed8;
  background: #eaf2ff;
}

.qc-issue__ghost-btn--muted {
  color: #94a3b8;
}

.qc-issue__ghost-btn--muted:hover {
  color: #64748b;
  background: #f1f5f9;
}

.qc-issue__btn-icon {
  width: 14px;
  height: 14px;
}

.qc-empty {
  min-height: 280px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  color: #64748b;
  border-radius: 14px;
  background: #f7fbff;
  border: 1px dashed rgba(147, 197, 253, 0.92);
}

.qc-empty__icon {
  font-size: 30px;
  color: #2563eb;
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
  padding: 10px 2px 0;
  border-top: none;
  background: transparent;
  font-size: 12px;
  color: #475569;
}

.qc-result-tab__footer-actions {
  display: flex;
  align-items: center;
  gap: 4px;
}

@media (max-width: 520px) {
  .qc-result-tab {
    min-height: 100%;
    height: auto;
  }

  .qc-result-tab__body {
    overflow: visible;
  }

  .qc-issue-list {
    flex: none;
    overflow: visible;
    padding-right: 0;
  }

  .qc-overview {
    flex-direction: column;
  }

  .qc-overview__desc {
    max-width: none;
  }

  .qc-overview__status {
    width: 100%;
    align-items: flex-start;
  }
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
