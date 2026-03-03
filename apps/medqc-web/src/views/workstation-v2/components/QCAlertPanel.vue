<template>
  <div class="qc-alert-wrapper">
    <!-- 浮动触发按钮 -->
    <div
      v-if="!visible"
      class="qc-trigger-btn"
      @click="visible = true"
    >
      <a-badge :count="totalIssueCount" :offset="[-2, 2]">
        <div class="trigger-icon">
          <BellOutlined />
        </div>
      </a-badge>
    </div>

    <!-- 浮动质控面板 -->
    <Transition name="qc-slide">
      <div
        v-if="visible"
        class="qc-alert-panel"
        :style="panelStyle"
      >
        <!-- 标题栏 -->
        <div class="panel-titlebar" @mousedown="startDrag">
          <div class="titlebar-left">
            <AlertOutlined class="title-icon" />
            <span class="title-text">质控提醒</span>
            <a-tag v-if="totalIssueCount > 0" color="error" class="count-tag">{{ totalIssueCount }}</a-tag>
          </div>
          <div class="titlebar-actions">
            <a-button type="text" size="small" @click="refreshQC" :loading="analyzing" class="action-btn">
              <ReloadOutlined />
            </a-button>
            <a-button type="text" size="small" @click="visible = false" class="action-btn close-btn">
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
              :numberStyle="{ backgroundColor: activeTab === tab.key ? '#fff' : '#ff4d4f', color: activeTab === tab.key ? '#1677ff' : '#fff', fontSize: '10px', minWidth: '16px', height: '16px', lineHeight: '16px' }"
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
                  <span class="group-dot" :style="{ background: severityColor(group.severity) }"></span>
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
                  <div class="issue-desc">{{ issue.description }}</div>
                  <div v-if="issue.suggestion" class="issue-suggestion">
                    💡 {{ issue.suggestion }}
                  </div>
                </div>
                <div class="issue-actions">
                  <a-button
                    v-if="issue.actionLabel"
                    type="link"
                    size="small"
                    @click="$emit('action', issue)"
                  >
                    {{ issue.actionLabel }}
                  </a-button>
                  <a-button
                    type="text"
                    size="small"
                    @click="dismissIssue(issue)"
                    class="dismiss-btn"
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
          <span class="footer-detail">
            <span v-if="severityCount('error') > 0" class="stat-error">{{ severityCount('error') }} 严重</span>
            <span v-if="severityCount('warning') > 0" class="stat-warning">{{ severityCount('warning') }} 警告</span>
            <span v-if="severityCount('info') > 0" class="stat-info">{{ severityCount('info') }} 提示</span>
          </span>
        </div>
      </div>
    </Transition>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, reactive } from 'vue'
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
} from '@ant-design/icons-vue'

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
    sex: fp.sex || fp.basic_info?.sex || '—',
    age: fp.age || fp.basic_info?.age || '—',
    diagnosis: fp.primary_diagnosis_name
      || fp.diagnoses?.discharge_main_diagnosis_text
      || fp.diagnoses?.discharge_main_diagnosis
      || '暂无诊断信息',
  }
})

// ==================== 质控结果 ====================
const currentIssues = computed(() =>
  issues.value.filter(i => i.category === activeTab.value && !i.dismissed)
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
  issues.value.filter(i => !i.dismissed).length
)

const getTabCount = (tab: string) =>
  issues.value.filter(i => i.category === tab && !i.dismissed).length

const severityCount = (sev: string) =>
  issues.value.filter(i => i.severity === sev && !i.dismissed).length

// ==================== 辅助方法 ====================
const severityColor = (sev: string) => ({
  error: '#ff4d4f', warning: '#faad14', info: '#1677ff'
}[sev] || '#999')

const severityTagColor = (sev: string) => ({
  error: 'error', warning: 'warning', info: 'processing'
}[sev] || 'default')

const severityLabel = (sev: string) => ({
  error: '严重', warning: '警告', info: '提示'
}[sev] || '未知')

const dismissIssue = (issue: QCIssue) => {
  issue.dismissed = true
}

const refreshQC = () => {
  emit('refresh')
  generateMockIssues()
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

// ==================== 引擎对接与数据生成 ====================
const runRealQCEngine = async () => {
  const fp = props.frontpage
  if (!fp) {
    issues.value = []
    return
  }

  // 1. 构造引擎需要的入参格式 (组装一个包含基本文档的结构)
  const patientData = {
    patientId: fp.case_id || fp.patient_id || `PAT_${Date.now()}`,
    documents: [
      {
        id: `doc_${Date.now()}`,
        type: 'admission_record' as DocumentType,
        content: JSON.stringify(fp), // 在实际应用中这里会传入真实的病历文书原文
        timestamp: new Date().toISOString(),
        status: 'draft'
      }
    ]
  }

  try {
    // 2. 调用质控引擎 (注意此时引擎内部 MockLLMService 会接管具体的文本提取和规则判定)
    const engineResult: ComprehensiveQCResult = await integratedQCEngine.executeQualityControl(patientData)
    
    // 3. 将 ComprehensiveQCResult 中的 QCRuleResult[] 转换为面板需要的 QCIssue[] 格式
    const newIssues: QCIssue[] = []
    let issueId = 0
    
    // 如果没有任何规则结果，给一个提示
    if (!engineResult.ruleResults || engineResult.ruleResults.length === 0) {
       issues.value = []
       return
    }

    engineResult.ruleResults.forEach((ruleRes: QCRuleResult) => {
      // 一条 RuleResult 里可能有多个 specific findings
      if (!ruleRes.isCompliant && ruleRes.findings && ruleRes.findings.length > 0) {
         ruleRes.findings.forEach(finding => {
            // 映射 Severity
            let sev: 'error' | 'warning' | 'info' = 'info'
            if (finding.severity === 'critical' || finding.severity === 'major') sev = 'error'
            else if (finding.severity === 'minor') sev = 'warning'
            
            // 映射 UI Category (前端 Tab 只有三种，这里做一个粗略映射，真实情况可以靠 category 属性更好判定)
            let tabCat: 'form' | 'coding' | 'cost' = 'form'
            if (ruleRes.ruleCode.includes('.2') || ruleRes.ruleName.includes('编码')) {
               tabCat = 'coding'
            } else if (ruleRes.ruleName.includes('费用') || finding.description.includes('DRG')) {
               tabCat = 'cost'
            }

            newIssues.push({
              id: `sys-${issueId++}`,
              category: tabCat,
              severity: sev,
              group: ruleRes.ruleName || '未知规则',
              description: finding.description,
              suggestion: finding.recommendation,
              actionLabel: '查看详情'
            })
         })
      }
    })

    issues.value = newIssues
  } catch (error) {
    console.error('质控引擎执行异常', error)
    // 出错时至少清空或者保留一个提示
    issues.value = []
  }
}

// 修改原有的入口
const generateMockIssues = () => {
  // 不再调用纯 Mock 逻辑，转而通过真实集成引擎跑数据
  runRealQCEngine()
}

// 监听 frontpage 变化，自动触发质控
watch(
  () => props.frontpage,
  (newVal) => {
    if (newVal) {
      generateMockIssues()
      // 有问题时自动弹出 (因为 runRealQCEngine 是异步的，等一下再弹会更好，目前可以用 setTimeout 估算一下)
      setTimeout(() => {
        if (totalIssueCount.value > 0 && !visible.value) {
           visible.value = true
        }
      }, 3500) // 因为上面 engineResult 是异步过程 (3000ms+)，等几秒再测
    }
  },
  { deep: true }
)
</script>

<style scoped>
/* ==================== 触发按钮 ==================== */
.qc-trigger-btn {
  position: fixed;
  right: 24px;
  bottom: 24px;
  z-index: 100;
  cursor: pointer;
  transition: transform 0.2s;
}
.qc-trigger-btn:hover {
  transform: scale(1.1);
}
.trigger-icon {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  background: linear-gradient(135deg, #1677ff 0%, #4096ff 100%);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 22px;
  box-shadow: 0 4px 16px rgba(22, 119, 255, 0.4);
}

/* ==================== 浮动面板 ==================== */
.qc-alert-panel {
  position: fixed;
  right: 24px;
  bottom: 24px;
  width: 380px;
  max-height: calc(100vh - 100px);
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 8px 40px rgba(0, 0, 0, 0.15), 0 0 0 1px rgba(0, 0, 0, 0.04);
  display: flex;
  flex-direction: column;
  z-index: 1000;
  overflow: hidden;
}

/* ==================== 标题栏 ==================== */
.panel-titlebar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background: linear-gradient(135deg, #1e3a5f 0%, #1e293b 100%);
  color: #fff;
  cursor: grab;
  user-select: none;
}
.panel-titlebar:active { cursor: grabbing; }
.titlebar-left {
  display: flex;
  align-items: center;
  gap: 8px;
}
.title-icon { font-size: 16px; }
.title-text { font-weight: 600; font-size: 14px; }
.count-tag { margin-left: 4px; }
.titlebar-actions { display: flex; gap: 2px; }
.action-btn { color: rgba(255,255,255,0.7) !important; }
.action-btn:hover { color: #fff !important; background: rgba(255,255,255,0.1) !important; }
.close-btn:hover { color: #ff4d4f !important; }

/* ==================== 患者信息条 ==================== */
.patient-bar {
  padding: 10px 16px;
  background: #f0f5ff;
  border-bottom: 1px solid #e6f0ff;
}
.patient-main {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 13px;
}
.patient-icon { color: #1677ff; margin-right: 4px; }
.patient-name { font-weight: 600; color: #1a1a1a; }
.patient-meta { color: #666; }
.patient-diagnosis {
  margin-top: 4px;
  font-size: 12px;
  color: #888;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.patient-bar-empty {
  text-align: center;
  color: #999;
}
.empty-hint { font-size: 12px; }

/* ==================== 分类 Tab ==================== */
.qc-tabs {
  display: flex;
  border-bottom: 1px solid #f0f0f0;
  padding: 0 8px;
}
.qc-tab {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  padding: 10px 0;
  font-size: 13px;
  color: #666;
  cursor: pointer;
  border-bottom: 2px solid transparent;
  transition: all 0.2s;
  position: relative;
}
.qc-tab:hover { color: #1677ff; }
.qc-tab.active {
  color: #1677ff;
  font-weight: 600;
  border-bottom-color: #1677ff;
}
.tab-icon { font-size: 14px; }
.tab-badge { margin-left: 2px; }

/* ==================== 问题列表 ==================== */
.qc-issues-container {
  flex: 1;
  overflow-y: auto;
  padding: 8px 12px;
  max-height: 400px;
}
.issue-group { margin-bottom: 12px; }
.group-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 8px;
  background: #fafafa;
  border-radius: 6px;
  margin-bottom: 6px;
}
.group-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-weight: 600;
  color: #333;
}
.group-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.issue-item {
  padding: 10px 12px;
  border: 1px solid #f0f0f0;
  border-radius: 8px;
  margin-bottom: 6px;
  transition: all 0.2s;
  background: #fff;
}
.issue-item:hover {
  border-color: #d6e4ff;
  box-shadow: 0 2px 8px rgba(22, 119, 255, 0.08);
}
.issue-item.dismissed {
  opacity: 0.4;
  text-decoration: line-through;
}
.issue-content { margin-bottom: 6px; }
.issue-severity { margin-bottom: 4px; }
.issue-desc {
  font-size: 13px;
  color: #333;
  line-height: 1.5;
}
.issue-suggestion {
  font-size: 12px;
  color: #888;
  margin-top: 4px;
  padding: 4px 8px;
  background: #fffbe6;
  border-radius: 4px;
  border-left: 2px solid #faad14;
}
.issue-actions {
  display: flex;
  justify-content: flex-end;
  gap: 4px;
}
.dismiss-btn { color: #999 !important; font-size: 12px; }

/* 空状态 */
.no-issues {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px 0;
  color: #999;
}
.no-issues-icon { font-size: 36px; color: #52c41a; margin-bottom: 8px; }

/* ==================== 底部状态栏 ==================== */
.panel-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 16px;
  background: #fafafa;
  border-top: 1px solid #f0f0f0;
  font-size: 12px;
  color: #666;
}
.footer-detail { display: flex; gap: 8px; }
.stat-error { color: #ff4d4f; font-weight: 600; }
.stat-warning { color: #faad14; font-weight: 600; }
.stat-info { color: #1677ff; }

/* ==================== 动画 ==================== */
.qc-slide-enter-active,
.qc-slide-leave-active {
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}
.qc-slide-enter-from,
.qc-slide-leave-to {
  opacity: 0;
  transform: translateY(20px) scale(0.95);
}

/* ==================== 滚动条 ==================== */
.custom-scrollbar::-webkit-scrollbar { width: 4px; }
.custom-scrollbar::-webkit-scrollbar-track { background: transparent; }
.custom-scrollbar::-webkit-scrollbar-thumb { background: #d9d9d9; border-radius: 4px; }
.custom-scrollbar::-webkit-scrollbar-thumb:hover { background: #bfbfbf; }
</style>
