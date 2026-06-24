<template>
  <div class="quality-control-view">
    <div class="max-w-7xl mx-auto p-6">
      <!-- 页面标题 -->
      <div class="mb-8">
        <div class="flex items-center justify-between">
          <div>
            <div class="flex items-center gap-3 mb-2">
              <div class="w-8 h-8 rounded-lg bg-gradient-to-br from-purple-400 to-indigo-600 flex items-center justify-center">
                <ThunderboltOutlined class="text-white text-sm" />
              </div>
              <h1 class="text-2xl font-bold text-slate-100">
                质控分析中心
              </h1>
            </div>
            <p class="text-slate-400 text-sm">
              AI驱动的医疗质控分析，提供专业的质量评估和改进建议
            </p>
          </div>

          <!-- 快速操作 -->
          <div class="flex items-center gap-3">
            <a-button 
              class="bg-purple-500/20 border-purple-400/30 text-purple-300 hover:bg-purple-500/30"
              @click="showRuleConfig = true"
            >
              <SettingOutlined />
              规则配置
            </a-button>
            <a-button 
              type="primary"
              :loading="isAnalyzing"
              class="bg-gradient-to-r from-purple-500 to-indigo-600 hover:from-purple-400 hover:to-indigo-500 border-none"
              @click="startNewAnalysis"
            >
              <ThunderboltOutlined />
              开始分析
            </a-button>
          </div>
        </div>
      </div>

      <!-- 主要内容区域 -->
      <div class="space-y-8">
        <!-- 分析进度（当有分析任务时显示） -->
        <div
          v-if="currentAnalysis"
          class="analysis-section"
        >
          <AnalysisProgress
            ref="analysisProgressRef"
            :record-id="currentAnalysis.recordId"
            @analysis-completed="handleAnalysisCompleted"
            @analysis-failed="handleAnalysisFailed"
            @analysis-paused="handleAnalysisPaused"
            @analysis-resumed="handleAnalysisResumed"
            @analysis-stopped="handleAnalysisStopped"
          />
        </div>

        <!-- 分析结果展示 -->
        <div
          v-if="analysisResult"
          class="results-section"
        >
          <div class="mb-6">
            <h2 class="text-xl font-semibold text-slate-100 flex items-center gap-2 mb-2">
              <TrophyOutlined class="text-cyan-400" />
              分析结果
            </h2>
            <p class="text-sm text-slate-400">
              详细的质控分析结果和改进建议
            </p>
          </div>

          <div class="grid grid-cols-1 xl:grid-cols-3 gap-8">
            <!-- 左侧：分析结果 -->
            <div class="xl:col-span-2 space-y-6">
              <QCResultDisplay 
                :result="analysisResult"
                @highlight-issue="handleHighlightIssue"
              />
            </div>

            <!-- 右侧：内容高亮 -->
            <div class="space-y-6">
              <ContentHighlighter
                :content="recordContent"
                :issues="analysisResult.issues"
                :active-issue="activeIssue"
                @issue-click="handleIssueClick"
              />
            </div>
          </div>

          <!-- 改进建议面板 -->
          <div class="mt-8">
            <SuggestionPanel
              :suggestions="analysisResult.suggestions"
              @suggestion-implemented="handleSuggestionImplemented"
              @suggestion-saved="handleSuggestionSaved"
            />
          </div>
        </div>

        <!-- 历史分析记录 -->
        <div class="history-section">
          <div class="mb-6">
            <h2 class="text-xl font-semibold text-slate-100 flex items-center gap-2 mb-2">
              <HistoryOutlined class="text-emerald-400" />
              历史分析记录
            </h2>
            <p class="text-sm text-slate-400">
              查看之前的质控分析结果
            </p>
          </div>

          <div class="rounded-xl bg-slate-800/50 backdrop-blur-sm border border-slate-700/50 p-6">
            <div class="space-y-4">
              <div
                v-for="record in historyRecords"
                :key="record.id"
                class="p-4 rounded-lg border border-slate-600/30 bg-slate-700/20 hover:border-slate-500/50 hover:bg-slate-700/30 transition-all duration-300 cursor-pointer"
                @click="loadHistoryRecord(record)"
              >
                <div class="flex items-center justify-between">
                  <div class="flex items-center gap-4">
                    <div class="w-12 h-12 rounded-full bg-gradient-to-br from-cyan-400 to-blue-600 flex items-center justify-center text-white font-bold">
                      {{ record.patient_name.charAt(0) }}
                    </div>
                    <div>
                      <h4 class="font-medium text-slate-100">
                        {{ record.patient_name }}
                      </h4>
                      <div class="flex items-center gap-3 text-sm text-slate-400">
                        <span>{{ record.department }}</span>
                        <span>•</span>
                        <span>{{ formatDate(record.analysis_date) }}</span>
                      </div>
                    </div>
                  </div>
                  <div class="flex items-center gap-4">
                    <div class="text-center">
                      <div 
                        class="text-lg font-bold"
                        :class="getScoreColor(record.overall_score)"
                      >
                        {{ record.overall_score }}
                      </div>
                      <div class="text-xs text-slate-400">
                        评分
                      </div>
                    </div>
                    <div class="text-center">
                      <div class="text-lg font-bold text-red-400">
                        {{ record.issue_count }}
                      </div>
                      <div class="text-xs text-slate-400">
                        问题
                      </div>
                    </div>
                    <a-tag 
                      :color="getGradeColor(record.overall_grade)" 
                      size="small"
                    >
                      {{ record.overall_grade }}级
                    </a-tag>
                  </div>
                </div>
              </div>
            </div>

            <div
              v-if="historyRecords.length === 0"
              class="text-center py-8"
            >
              <div class="w-16 h-16 rounded-full bg-slate-700/50 flex items-center justify-center mx-auto mb-3">
                <HistoryOutlined class="text-slate-400 text-2xl" />
              </div>
              <div class="text-slate-400">
                暂无历史分析记录
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 规则配置抽屉 -->
    <a-drawer
      v-model:open="showRuleConfig"
      title="质控规则配置"
      width="80%"
      placement="right"
      class="rule-config-drawer"
    >
      <RuleConfiguration
        :rules="qcRules"
        @rule-updated="handleRuleUpdated"
        @rule-created="handleRuleCreated"
        @rule-deleted="handleRuleDeleted"
      />
    </a-drawer>

    <!-- 记录选择模态框 -->
    <a-modal
      v-model:open="showRecordSelector"
      title="选择要分析的记录"
      :footer="null"
      width="800px"
      class="record-selector-modal"
    >
      <div class="max-h-96 overflow-y-auto">
        <div class="space-y-3">
          <div
            v-for="record in availableRecords"
            :key="record.id"
            class="p-4 rounded-lg border border-slate-600/30 bg-slate-700/20 hover:border-cyan-500/50 hover:bg-cyan-500/10 transition-all duration-300 cursor-pointer"
            @click="selectRecord(record)"
          >
            <div class="flex items-center justify-between">
              <div class="flex items-center gap-3">
                <div class="w-10 h-10 rounded-full bg-gradient-to-br from-cyan-400 to-blue-600 flex items-center justify-center text-white font-semibold">
                  {{ record.patient_name.charAt(0) }}
                </div>
                <div>
                  <div class="font-medium text-slate-100">
                    {{ record.patient_name }}
                  </div>
                  <div class="text-sm text-slate-400">
                    {{ record.department }} • {{ (record as any).record_type || '病历' }}
                  </div>
                </div>
              </div>
              <div class="flex items-center gap-2">
                <a-tag 
                  :color="getRecordStatusColor(record.status)" 
                  size="small"
                >
                  {{ getRecordStatusLabel(record.status) }}
                </a-tag>
              </div>
            </div>
          </div>
        </div>
      </div>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, computed } from 'vue'
import { message } from 'ant-design-vue'
import {
  ThunderboltOutlined,
  SettingOutlined,
  TrophyOutlined,
  HistoryOutlined
} from '@ant-design/icons-vue'
import type { QCResult, QCIssue, QCRule, MedicalRecord } from '@/types'
import QCResultDisplay from '@/components/qc/QCResultDisplay.vue'
import ContentHighlighter from '@/components/qc/ContentHighlighter.vue'
import SuggestionPanel from '@/components/qc/SuggestionPanel.vue'
import RuleConfiguration from '@/components/qc/RuleConfiguration.vue'
import AnalysisProgress from '@/components/qc/AnalysisProgress.vue'
import { ApiService } from '@/services/apiService'

// 组件引用
const analysisProgressRef = ref<{ startAnalysis: () => void } | null>(null)

// 状态
const isAnalyzing = ref(false)
const showRuleConfig = ref(false)
const showRecordSelector = ref(false)
const activeIssue = ref<QCIssue | null>(null)

// 当前分析任务
const currentAnalysis = ref<{
  recordId: string
  recordName: string
} | null>(null)

// 分析结果
const analysisResult = ref<QCResult | null>(null)

// 记录内容
const recordContent = ref('')

// 质控规则
const qcRules = ref<any[]>([])

// 历史记录
const historyRecords = ref<any[]>([])

// 可用记录
const availableRecords = ref<MedicalRecord[]>([])

// 初始化页面
onMounted(async () => {
  await loadHistoryRecords()
  await loadAvailableRecords()
  await loadQCRules()
})

// 加载历史记录
const loadHistoryRecords = async () => {
  try {
    const response = await ApiService.getQCHistory()
    if (response.success && response.data) {
      historyRecords.value = response.data
    }
  } catch (error) {
    console.error('加载历史记录失败:', error)
  }
}

// 加载可用记录
const loadAvailableRecords = async () => {
  try {
    const response = await ApiService.getMedicalRecords()
    if (response.success && response.data) {
      availableRecords.value = response.data.data
    }
  } catch (error) {
    console.error('加载可用记录失败:', error)
  }
}

// 加载质控规则
const loadQCRules = async () => {
  try {
    const response = await ApiService.getQCRules()
    if (response.success && response.data) {
      qcRules.value = response.data
    }
  } catch (error) {
    console.error('加载质控规则失败:', error)
  }
}

// 开始新分析
const startNewAnalysis = () => {
  showRecordSelector.value = true
}

// 选择记录进行分析
const selectRecord = async (record: MedicalRecord) => {
  showRecordSelector.value = false
  
  currentAnalysis.value = {
    recordId: record.id,
    recordName: record.patient_name
  }
  
  recordContent.value = record.content
  isAnalyzing.value = true
  
  // 开始分析进度
  analysisProgressRef.value?.startAnalysis()
}

// 处理分析完成
const handleAnalysisCompleted = async (result: unknown) => {
  void result
  try {
    // 获取分析结果
    const response = await ApiService.getQCResult(currentAnalysis.value!.recordId)
    if (response.success && response.data) {
      analysisResult.value = response.data
      message.success('质控分析完成')
    }
  } catch (error) {
    console.error('获取分析结果失败:', error)
    message.error('获取分析结果失败')
  } finally {
    isAnalyzing.value = false
    currentAnalysis.value = null
  }
}

// 处理分析失败
const handleAnalysisFailed = (error: string) => {
  message.error(`分析失败: ${error}`)
  isAnalyzing.value = false
  currentAnalysis.value = null
}

// 处理分析暂停
const handleAnalysisPaused = () => {
  message.info('分析已暂停')
}

// 处理分析恢复
const handleAnalysisResumed = () => {
  message.info('分析已恢复')
}

// 处理分析停止
const handleAnalysisStopped = () => {
  message.warning('分析已停止')
  isAnalyzing.value = false
  currentAnalysis.value = null
}

// 处理问题高亮
const handleHighlightIssue = (issue: unknown) => {
  activeIssue.value = issue as QCIssue
}

// 处理问题点击
const handleIssueClick = (issue: QCIssue) => {
  activeIssue.value = issue
  message.info(`已定位到问题: ${issue.rule_name}`)
}

// 处理建议实施
const handleSuggestionImplemented = (suggestionId: string) => {
  // 更新建议状态
  console.log('建议已实施:', suggestionId)
}

// 处理建议保存
const handleSuggestionSaved = (suggestionId: string) => {
  // 保存建议
  console.log('建议已保存:', suggestionId)
}

// 处理规则更新
const handleRuleUpdated = (rule: any) => {
  const index = qcRules.value.findIndex(r => r.id === rule.id)
  if (index > -1) {
    qcRules.value[index] = rule
  }
}

// 处理规则创建
const handleRuleCreated = (rule: any) => {
  qcRules.value.unshift(rule)
}

// 处理规则删除
const handleRuleDeleted = (ruleId: string) => {
  const index = qcRules.value.findIndex(r => r.id === ruleId)
  if (index > -1) {
    qcRules.value.splice(index, 1)
  }
}

// 加载历史记录
const loadHistoryRecord = async (record: { id: string; content?: string; patient_name: string }) => {
  try {
    const response = await ApiService.getQCResult(record.id)
    if (response.success && response.data) {
      analysisResult.value = response.data
      recordContent.value = record.content || '历史记录内容...'
      activeIssue.value = null

      message.success(`已加载 ${record.patient_name} 的分析结果`)
    }
  } catch (error) {
    console.error('加载历史记录失败:', error)
    message.error('加载历史记录失败')
  }
}

// 样式相关方法
const getScoreColor = (score: number) => {
  if (score >= 90) return 'text-emerald-400'
  if (score >= 80) return 'text-blue-400'
  if (score >= 70) return 'text-amber-400'
  return 'text-red-400'
}

const getGradeColor = (grade: string) => {
  const colors = {
    A: 'green',
    B: 'blue',
    C: 'orange'
  }
  return colors[grade as keyof typeof colors] || 'default'
}

const getRecordStatusColor = (status: string) => {
  const colors = {
    pending: 'orange',
    analyzing: 'blue',
    completed: 'green',
    failed: 'red'
  }
  return colors[status as keyof typeof colors] || 'default'
}

const getRecordStatusLabel = (status: string) => {
  const labels = {
    pending: '待处理',
    analyzing: '分析中',
    completed: '已完成',
    failed: '失败'
  }
  return labels[status as keyof typeof labels] || status
}

const formatDate = (dateString: string) => {
  try {
    return new Date(dateString).toLocaleDateString('zh-CN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit'
    })
  } catch {
    return dateString
  }
}
</script>

<style scoped>
.quality-control-view {
  @apply min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900;
}

/* 抽屉样式 */
:deep(.rule-config-drawer .ant-drawer-content) {
  background: rgb(15 23 42);
}

:deep(.rule-config-drawer .ant-drawer-header) {
  background: rgb(30 41 59);
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

:deep(.rule-config-drawer .ant-drawer-title) {
  color: rgb(241 245 249);
}

:deep(.rule-config-drawer .ant-drawer-close) {
  color: rgb(148 163 184);
}

:deep(.rule-config-drawer .ant-drawer-close:hover) {
  color: rgb(241 245 249);
}

/* 模态框样式 */
:deep(.record-selector-modal .ant-modal-content) {
  background: rgb(30 41 59);
  border: 1px solid rgba(255, 255, 255, 0.1);
}

:deep(.record-selector-modal .ant-modal-header) {
  background: rgb(30 41 59);
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

:deep(.record-selector-modal .ant-modal-title) {
  color: rgb(241 245 249);
}

:deep(.record-selector-modal .ant-modal-close) {
  color: rgb(148 163 184);
}

:deep(.record-selector-modal .ant-modal-close:hover) {
  color: rgb(241 245 249);
}

/* 卡片悬浮效果 */
.rounded-xl,
.rounded-lg {
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.rounded-xl:hover,
.rounded-lg:hover {
  transform: translateY(-2px);
}

/* 按钮动画 */
:deep(.ant-btn) {
  transition: all 0.2s ease-out;
}

:deep(.ant-btn:hover) {
  transform: translateY(-1px);
}

/* 响应式设计 */
@media (max-width: 1280px) {
  .xl\\:col-span-2 {
    grid-column: span 1;
  }
}

@media (max-width: 768px) {
  .max-w-7xl {
    padding-left: 1rem;
    padding-right: 1rem;
  }
  
  .flex.items-center.justify-between {
    flex-direction: column;
    align-items: flex-start;
    gap: 1rem;
  }
  
  .grid.grid-cols-1.xl\\:grid-cols-3 {
    grid-template-columns: 1fr;
  }
}
</style>
