<template>
  <div class="batch-rule-test-v3">
    <!-- 顶部导航 -->
    <div class="page-header">
      <div class="header-content">
        <div class="header-left">
          <h1 class="header-title">
            批量质控评估
          </h1>
          <p class="header-subtitle">
            上下分屏布局 + 标签页 · 可拖动调整高度
          </p>
        </div>
        <div class="header-right">
          <a-space :size="12">
            <!-- LLM 设置按钮 -->
            <a-button
              size="large"
              class="llm-settings-button"
              data-testid="llm-settings-btn"
              @click="showLLMSettings"
            >
              <template #icon>
                <ApiOutlined />
              </template>
              <span>LLM 设置</span>
            </a-button>

            <a-tag color="blue">
              进度：{{ testProgress.completed }}/{{ testProgress.total }}
            </a-tag>
            <a-button @click="goBack">
              <template #icon>
                <ArrowLeftOutlined />
              </template>
              返回列表
            </a-button>
          </a-space>
        </div>
      </div>
    </div>

    <!-- 上下分屏容器 -->
    <div class="split-container">
      <!-- 上半部：输入区 -->
      <div
        class="top-section"
        :style="{ height: topHeight + '%' }"
      >
        <div class="top-content">
          <!-- 左侧：规则选择 (35%) -->
          <div class="rules-panel">
            <a-card
              :bordered="false"
              class="panel-card"
            >
              <template #title>
                <div class="panel-title">
                  <AppstoreOutlined />
                  <span>规则选择</span>
                  <a-tag
                    v-if="selectedRuleIds.length > 0"
                    color="blue"
                  >
                    {{ selectedRuleIds.length }} 条
                  </a-tag>
                </div>
              </template>

              <!-- 文书类型选择 -->
              <div class="control-group">
                <label class="control-label">文书类型</label>
                <a-select
                  v-model:value="currentDocumentType"
                  style="width: 100%"
                  :disabled="isTesting"
                  @change="handleDocumentTypeChange"
                >
                  <a-select-option
                    v-for="config in documentTypeConfigs"
                    :key="config.key"
                    :value="config.key"
                  >
                    <component
                      :is="iconComponents[config.icon]"
                      style="margin-right: 4px"
                    />
                    {{ config.label }}
                  </a-select-option>
                </a-select>
              </div>

              <!-- 筛选工具 -->
              <div class="control-group">
                <label class="control-label">筛选</label>
                <a-space
                  direction="vertical"
                  style="width: 100%"
                  :size="8"
                >
                  <a-input
                    v-model:value="searchText"
                    placeholder="搜索规则..."
                    allow-clear
                    :disabled="isTesting"
                  >
                    <template #prefix>
                      <SearchOutlined />
                    </template>
                  </a-input>

                  <a-select
                    v-model:value="filterDefectLevel"
                    placeholder="缺陷等级"
                    allow-clear
                    style="width: 100%"
                    :disabled="isTesting"
                  >
                    <a-select-option value="严重缺陷">
                      🔴 严重
                    </a-select-option>
                    <a-select-option value="一般缺陷">
                      🟡 一般
                    </a-select-option>
                    <a-select-option value="轻微缺陷">
                      🟢 轻微
                    </a-select-option>
                  </a-select>

                  <a-select
                    v-model:value="filterComplexity"
                    placeholder="复杂度"
                    allow-clear
                    style="width: 100%"
                    :disabled="isTesting"
                  >
                    <a-select-option value="高复杂度">
                      🟠 高
                    </a-select-option>
                    <a-select-option value="中复杂度">
                      🟢 中
                    </a-select-option>
                    <a-select-option value="低复杂度">
                      🔵 低
                    </a-select-option>
                  </a-select>
                </a-space>
              </div>

              <!-- 全选控制 -->
              <div class="selection-control">
                <a-checkbox
                  :checked="isAllSelected"
                  :indeterminate="isIndeterminate"
                  :disabled="isTesting || filteredRules.length === 0"
                  @change="toggleSelectAll"
                >
                  全选
                </a-checkbox>
                <span class="selection-count">
                  {{ selectedRuleIds.length }}/{{ filteredRules.length }}
                </span>
              </div>

              <!-- 规则列表 -->
              <div class="rules-list-container">
                <div
                  v-for="rule in filteredRules"
                  :key="rule.rule_id"
                  :class="[
                    'rule-item-compact',
                    {
                      selected: selectedRuleIds.includes(rule.rule_id),
                      disabled: isTesting,
                    },
                  ]"
                  @click="toggleRuleSelection(rule.rule_id)"
                >
                  <a-checkbox
                    :checked="selectedRuleIds.includes(rule.rule_id)"
                    :disabled="isTesting"
                    @click.stop
                    @change="() => toggleRuleSelection(rule.rule_id)"
                  />
                  <div class="rule-info-compact">
                    <div class="rule-header-compact">
                      <span class="rule-id-compact">{{ rule.rule_id }}</span>
                      <a-tag
                        :color="getDefectLevelColor(rule.defect_level)"
                        size="small"
                      >
                        {{ normalizeDefectLevel(rule.defect_level) }}
                      </a-tag>
                    </div>
                    <div
                      class="rule-name-compact"
                      :title="rule.name"
                    >
                      {{ rule.name }}
                    </div>
                  </div>
                </div>
              </div>
            </a-card>
          </div>

          <!-- 右侧：病历编辑 (65%) -->
          <div class="medical-panel">
            <a-card
              :bordered="false"
              class="panel-card"
            >
              <template #title>
                <div class="panel-title">
                  <FileTextOutlined />
                  <span>病历文本</span>
                  <a-tag :color="currentConfig.tagColor">
                    {{ currentConfig.label }}
                  </a-tag>
                </div>
              </template>
              <template #extra>
                <a-button
                  size="small"
                  :disabled="isTesting"
                  @click="resetMedicalText"
                >
                  重置文本
                </a-button>
              </template>

              <div class="medical-editor-wrapper">
                <a-textarea
                  v-model:value="medicalText"
                  :disabled="isTesting"
                  :placeholder="`请输入或编辑${currentConfig.label}...`"
                  :auto-size="{ minRows: 15, maxRows: 25 }"
                  class="medical-textarea"
                  show-count
                  :maxlength="5000"
                />
              </div>

              <!-- 操作按钮 -->
              <div class="action-bar">
                <a-button
                  type="primary"
                  size="large"
                  :loading="isTesting"
                  :disabled="selectedRuleIds.length === 0 || !medicalText.trim()"
                  style="flex: 1"
                  @click="startBatchTest"
                >
                  <template #icon>
                    <ThunderboltOutlined />
                  </template>
                  {{
                    isTesting
                      ? `评估中 ${testProgress.completed}/${testProgress.total}`
                      : '开始批量评估'
                  }}
                </a-button>

                <a-button
                  size="large"
                  :loading="isProductionTesting"
                  :disabled="selectedRuleIds.length === 0 || !medicalText.trim() || isTesting"
                  style="flex: 1"
                  @click="startProductionBatchQC"
                >
                  <template #icon>
                    <RocketOutlined />
                  </template>
                  {{ isProductionTesting ? '生产质控中...' : '生产批量质控' }}
                </a-button>
              </div>
            </a-card>
          </div>
        </div>
      </div>

      <!-- 可拖动的分隔条 -->
      <div
        class="drag-handle"
        :class="{ dragging: isDragging }"
        @mousedown="startDrag"
      >
        <div class="drag-handle-line">
          <div class="drag-handle-icon">
            <DragOutlined />
          </div>
        </div>
      </div>

      <!-- 下半部：结果区 -->
      <div
        class="bottom-section"
        :style="{ height: 100 - topHeight + '%' }"
      >
        <div class="bottom-content">
          <a-card
            :bordered="false"
            class="results-card"
          >
            <template #title>
              <div class="results-header-title">
                <BarChartOutlined />
                <span>评估结果</span>
              </div>
            </template>

            <!-- 标签页 -->
            <a-tabs
              v-model:active-key="activeTab"
              type="card"
              class="results-tabs"
            >
              <!-- 概览标签 -->
              <a-tab-pane
                key="overview"
                tab="📊 概览"
              >
                <div
                  v-if="!productionResult && testResults.length === 0"
                  class="empty-state"
                >
                  <div class="empty-icon">
                    📊
                  </div>
                  <div class="empty-text">
                    尚无评估结果
                  </div>
                  <div class="empty-hint">
                    选择规则并点击评估按钮开始
                  </div>
                </div>

                <div
                  v-else-if="isTesting || isProductionTesting"
                  class="loading-state"
                >
                  <a-spin size="large" />
                  <div class="loading-text">
                    AI 正在评估中...
                  </div>
                </div>

                <div
                  v-else-if="productionResult?.data"
                  class="overview-content"
                >
                  <div class="overview-grid">
                    <!-- 大卡片：合规率 -->
                    <div class="overview-card overview-card-large">
                      <div class="overview-chart">
                        <svg
                          viewBox="0 0 200 200"
                          class="circular-chart-large"
                        >
                          <circle
                            class="circle-bg"
                            cx="100"
                            cy="100"
                            r="90"
                          />
                          <circle
                            class="circle-progress"
                            cx="100"
                            cy="100"
                            r="90"
                            :stroke-dasharray="`${(productionResult.data.evaluation_summary.compliance_rate || 0) * 5.654} 565.4`"
                          />
                        </svg>
                        <div class="chart-center">
                          <div class="chart-value-large">
                            {{
                              productionResult.data.evaluation_summary.compliance_rate?.toFixed(
                                1,
                              ) || '0.0'
                            }}%
                          </div>
                          <div class="chart-label-large">
                            合规率
                          </div>
                        </div>
                      </div>
                    </div>

                    <!-- 统计卡片 -->
                    <div class="overview-card">
                      <div class="stat-icon error">
                        ⚠️
                      </div>
                      <div class="stat-value">
                        {{ productionResult.data.evaluation_summary.issues_found ?? 0 }}
                      </div>
                      <div class="stat-label">
                        发现问题
                      </div>
                    </div>

                    <div class="overview-card">
                      <div class="stat-icon success">
                        ✅
                      </div>
                      <div class="stat-value">
                        {{
                          productionResult.data.evaluation_results?.filter((r) => r.is_compliant)
                            .length || 0
                        }}
                      </div>
                      <div class="stat-label">
                        合规项目
                      </div>
                    </div>

                    <div class="overview-card">
                      <div class="stat-icon">
                        ⏱️
                      </div>
                      <div class="stat-value">
                        {{
                          productionResult.data.performance_metrics?.processing_time.toFixed(2) ||
                            '0.00'
                        }}s
                      </div>
                      <div class="stat-label">
                        处理时间
                      </div>
                    </div>

                    <div class="overview-card">
                      <div class="stat-icon">
                        🎯
                      </div>
                      <div class="stat-value">
                        {{ productionResult.data.performance_metrics?.token_usage || 0 }}
                      </div>
                      <div class="stat-label">
                        Token消耗
                      </div>
                    </div>
                  </div>

                  <!-- 问题分布图 -->
                  <div
                    v-if="issuesByLevel"
                    class="issues-breakdown"
                  >
                    <div class="breakdown-title">
                      问题分布
                    </div>
                    <div class="breakdown-bars">
                      <div class="breakdown-item">
                        <div class="breakdown-label">
                          <span class="breakdown-icon error">🔴</span>
                          <span>严重</span>
                        </div>
                        <div class="breakdown-bar-wrapper">
                          <div
                            class="breakdown-bar error"
                            :style="{ width: getBarWidth(issuesByLevel.severe, totalIssues) }"
                          />
                          <span class="breakdown-count">{{ issuesByLevel.severe }}</span>
                        </div>
                      </div>

                      <div class="breakdown-item">
                        <div class="breakdown-label">
                          <span class="breakdown-icon warning">🟡</span>
                          <span>一般</span>
                        </div>
                        <div class="breakdown-bar-wrapper">
                          <div
                            class="breakdown-bar warning"
                            :style="{ width: getBarWidth(issuesByLevel.moderate, totalIssues) }"
                          />
                          <span class="breakdown-count">{{ issuesByLevel.moderate }}</span>
                        </div>
                      </div>

                      <div class="breakdown-item">
                        <div class="breakdown-label">
                          <span class="breakdown-icon success">🟢</span>
                          <span>轻微</span>
                        </div>
                        <div class="breakdown-bar-wrapper">
                          <div
                            class="breakdown-bar success"
                            :style="{ width: getBarWidth(issuesByLevel.minor, totalIssues) }"
                          />
                          <span class="breakdown-count">{{ issuesByLevel.minor }}</span>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </a-tab-pane>

              <!-- 详细标签 -->
              <a-tab-pane
                key="details"
                tab="📝 详细"
              >
                <div
                  v-if="productionResult?.data?.evaluation_results"
                  class="details-content"
                >
                  <div class="details-toolbar">
                    <a-radio-group
                      v-model:value="resultFilter"
                      size="small"
                    >
                      <a-radio-button value="all">
                        全部
                      </a-radio-button>
                      <a-radio-button value="issues">
                        仅问题
                      </a-radio-button>
                    </a-radio-group>
                    <span class="details-count">
                      共 {{ filteredEvaluationResults.length }} 项
                    </span>
                  </div>

                  <div class="details-list">
                    <div
                      v-for="result in filteredEvaluationResults"
                      :key="result.rule_id"
                      :class="['detail-item', result.is_compliant ? 'compliant' : 'non-compliant']"
                    >
                      <div class="detail-header">
                        <div class="detail-icon">
                          <CheckCircleOutlined v-if="result.is_compliant" />
                          <CloseCircleOutlined v-else />
                        </div>
                        <div class="detail-info">
                          <div class="detail-rule-id">
                            {{ result.rule_id }}
                          </div>
                          <div class="detail-rule-name">
                            {{ result.rule_name }}
                          </div>
                        </div>
                        <a-tag :color="result.is_compliant ? 'success' : 'error'">
                          {{ result.is_compliant ? '合规' : '不合规' }}
                        </a-tag>
                      </div>

                      <div
                        v-if="!result.is_compliant && result.findings"
                        class="detail-findings"
                      >
                        <div class="detail-section-label">
                          问题描述：
                        </div>
                        <div class="detail-section-content">
                          {{ result.findings }}
                        </div>
                      </div>

                      <div
                        v-if="!result.is_compliant && result.evidence"
                        class="detail-evidence"
                      >
                        <div class="detail-section-label">
                          证据引用：
                        </div>
                        <div class="detail-section-content evidence-text">
                          {{ result.evidence }}
                        </div>
                      </div>

                      <div
                        v-if="!result.is_compliant && result.suggestion"
                        class="detail-suggestion"
                      >
                        <div class="detail-section-label">
                          整改建议：
                        </div>
                        <div class="detail-section-content">
                          {{ result.suggestion }}
                        </div>
                      </div>
                    </div>
                  </div>
                </div>

                <div
                  v-else
                  class="empty-state"
                >
                  <div class="empty-text">
                    暂无详细结果
                  </div>
                </div>
              </a-tab-pane>

              <!-- 时间线标签 -->
              <a-tab-pane
                key="timeline"
                tab="⏱ 时间线"
              >
                <div
                  v-if="evaluationTimeline.length > 0"
                  class="timeline-content"
                >
                  <a-timeline>
                    <a-timeline-item
                      v-for="(event, index) in evaluationTimeline"
                      :key="index"
                      :color="event.color"
                    >
                      <template #dot>
                        <component
                          :is="event.icon"
                          style="font-size: 16px"
                        />
                      </template>
                      <div class="timeline-item-content">
                        <div class="timeline-time">
                          {{ event.time }}
                        </div>
                        <div class="timeline-title">
                          {{ event.title }}
                        </div>
                        <div
                          v-if="event.description"
                          class="timeline-desc"
                        >
                          {{ event.description }}
                        </div>
                      </div>
                    </a-timeline-item>
                  </a-timeline>
                </div>

                <div
                  v-else
                  class="empty-state"
                >
                  <div class="empty-text">
                    暂无评估记录
                  </div>
                </div>
              </a-tab-pane>

              <!-- 导出标签 -->
              <a-tab-pane
                key="export"
                tab="💾 导出"
              >
                <div class="export-content">
                  <a-space
                    direction="vertical"
                    style="width: 100%"
                    :size="16"
                  >
                    <a-alert
                      message="导出评估报告"
                      description="将质控评估结果导出为不同格式，便于存档和分享"
                      type="info"
                      show-icon
                    />

                    <div class="export-options">
                      <div
                        class="export-option-card"
                        @click="exportAsJSON"
                      >
                        <FileTextOutlined class="export-icon" />
                        <div class="export-title">
                          导出为 JSON
                        </div>
                        <div class="export-desc">
                          结构化数据格式，便于程序处理
                        </div>
                      </div>

                      <div
                        class="export-option-card"
                        @click="exportAsExcel"
                      >
                        <FileExcelOutlined class="export-icon" />
                        <div class="export-title">
                          导出为 Excel
                        </div>
                        <div class="export-desc">
                          表格格式，便于数据分析
                        </div>
                      </div>

                      <div
                        class="export-option-card"
                        @click="exportAsPDF"
                      >
                        <FilePdfOutlined class="export-icon" />
                        <div class="export-title">
                          导出为 PDF
                        </div>
                        <div class="export-desc">
                          标准文档格式，便于打印存档
                        </div>
                      </div>

                      <div
                        class="export-option-card"
                        @click="copyToClipboard"
                      >
                        <CopyOutlined class="export-icon" />
                        <div class="export-title">
                          复制到剪贴板
                        </div>
                        <div class="export-desc">
                          快速复制结果文本
                        </div>
                      </div>
                    </div>
                  </a-space>
                </div>
              </a-tab-pane>
            </a-tabs>
          </a-card>
        </div>
      </div>
    </div>

    <!-- LLM 设置抽屉 -->
    <a-drawer
      v-model:open="llmSettingsVisible"
      title="LLM 配置"
      width="80%"
      placement="right"
      :destroy-on-close="true"
    >
      <template #extra>
        <a-space>
          <a-button @click="llmSettingsVisible = false">
            关闭
          </a-button>
        </a-space>
      </template>
      <LLMApiConfig />
    </a-drawer>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import {
  ArrowLeftOutlined,
  ThunderboltOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  AppstoreOutlined,
  FileTextOutlined,
  BarChartOutlined,
  SearchOutlined,
  DragOutlined,
  RocketOutlined,
  PlayCircleOutlined,
  CheckOutlined,
  ClockCircleOutlined,
  FileExcelOutlined,
  FilePdfOutlined,
  CopyOutlined,
  ApiOutlined,
} from '@ant-design/icons-vue'
import { SolutionOutlined, ScissorOutlined, HomeOutlined } from '@ant-design/icons-vue'
import {
  PRESET_ADMISSION_RECORD,
  filterRulesByDocumentType,
  DOCUMENT_TYPE_CONFIGS,
  filterRules,
  type BatchTestResult,
  type BatchTestProgress,
  type DocumentTypeConfig,
} from '@/utils/batchTestHelpers'
import { testQCRule, batchEvaluateQC } from '@/api/qc'
import type { TestQCRuleData, BatchQCEvaluateResponse } from '@/api/qc'
import { loadCustomRules } from '@/utils/custom-rules-loader'
import LLMApiConfig from '@/components/LLMApiConfig.vue'

const router = useRouter()

// 图标组件映射
const iconComponents: Record<string, any> = {
  admission: SolutionOutlined,
  course: FileTextOutlined,
  operation: ScissorOutlined,
  discharge: HomeOutlined,
}

// LLM 设置相关
const llmSettingsVisible = ref(false)

// 数据状态
const currentDocumentType = ref<string>('admission_record')
const documentTypeConfigs = ref<DocumentTypeConfig[]>(DOCUMENT_TYPE_CONFIGS)
const medicalText = ref(PRESET_ADMISSION_RECORD)
const originalMedicalText = ref(PRESET_ADMISSION_RECORD)
const customRules = ref<any[]>([])
const admissionRules = ref<any[]>([])
const selectedRuleIds = ref<string[]>([])
const isTesting = ref(false)
const testResults = ref<BatchTestResult[]>([])
const testProgress = ref<BatchTestProgress>({
  total: 0,
  completed: 0,
})

// 生产批量质控状态
const isProductionTesting = ref(false)
const productionResult = ref<BatchQCEvaluateResponse | null>(null)
const resultFilter = ref<'all' | 'issues'>('all')
const activeTab = ref('overview')

// 筛选状态
const searchText = ref('')
const filterDefectLevel = ref<string | undefined>(undefined)
const filterComplexity = ref<string | undefined>(undefined)

// 分屏拖动状态
const topHeight = ref(50) // 上半部分高度百分比
const isDragging = ref(false)

// 时间线
const evaluationTimeline = ref<
  Array<{
    time: string
    title: string
    description?: string
    icon: any
    color: string
  }>
>([])

// 当前配置
const currentConfig = computed(() => {
  return (
    documentTypeConfigs.value.find((c) => c.key === currentDocumentType.value) ||
    documentTypeConfigs.value[0]
  )
})

// 过滤后的规则
const filteredRules = computed(() => {
  return filterRules(
    admissionRules.value,
    searchText.value,
    filterDefectLevel.value,
    filterComplexity.value,
  )
})

// 全选状态
const isAllSelected = computed(() => {
  return (
    filteredRules.value.length > 0 &&
    filteredRules.value.every((rule) => selectedRuleIds.value.includes(rule.rule_id))
  )
})

const isIndeterminate = computed(() => {
  const selectedCount = filteredRules.value.filter((rule) =>
    selectedRuleIds.value.includes(rule.rule_id),
  ).length
  return selectedCount > 0 && selectedCount < filteredRules.value.length
})

// 过滤评估结果
const filteredEvaluationResults = computed(() => {
  if (!productionResult.value?.data?.evaluation_results) return []
  if (resultFilter.value === 'issues') {
    return productionResult.value.data.evaluation_results.filter((r) => !r.is_compliant)
  }
  return productionResult.value.data.evaluation_results
})

// 问题级别统计
const issuesByLevel = computed(() => {
  if (!productionResult.value?.data?.evaluation_results) return null

  const results = productionResult.value.data.evaluation_results
  const nonCompliant = results.filter((r) => !r.is_compliant)

  // 根据规则获取缺陷级别
  const severe = nonCompliant.filter((r) => {
    const rule = admissionRules.value.find((rule) => rule.rule_id === r.rule_id)
    return rule && rule.defect_level.includes('严重')
  }).length

  const moderate = nonCompliant.filter((r) => {
    const rule = admissionRules.value.find((rule) => rule.rule_id === r.rule_id)
    return rule && rule.defect_level.includes('一般')
  }).length

  const minor = nonCompliant.filter((r) => {
    const rule = admissionRules.value.find((rule) => rule.rule_id === r.rule_id)
    return rule && rule.defect_level.includes('轻微')
  }).length

  return { severe, moderate, minor }
})

const totalIssues = computed(() => {
  if (!issuesByLevel.value) return 0
  return issuesByLevel.value.severe + issuesByLevel.value.moderate + issuesByLevel.value.minor
})

// LLM 设置相关方法
const showLLMSettings = () => {
  llmSettingsVisible.value = true
}

// 方法
const goBack = () => {
  router.back()
}

const handleDocumentTypeChange = (value: string) => {
  currentDocumentType.value = value
  loadRulesForDocumentType(value)
  resetMedicalText()
}

const loadRulesForDocumentType = (documentType: string) => {
  admissionRules.value = filterRulesByDocumentType(customRules.value, documentType)
  selectedRuleIds.value = []
}

const resetMedicalText = () => {
  medicalText.value = originalMedicalText.value
}

const toggleSelectAll = (e: any) => {
  if (e.target.checked) {
    selectedRuleIds.value = filteredRules.value.map((rule) => rule.rule_id)
  } else {
    selectedRuleIds.value = []
  }
}

const toggleRuleSelection = (ruleId: string) => {
  if (isTesting.value) return
  const index = selectedRuleIds.value.indexOf(ruleId)
  if (index > -1) {
    selectedRuleIds.value.splice(index, 1)
  } else {
    selectedRuleIds.value.push(ruleId)
  }
}

const normalizeDefectLevel = (level: string) => {
  if (level.includes('严重')) return '严重'
  if (level.includes('一般')) return '一般'
  if (level.includes('轻微')) return '轻微'
  return level
}

const getDefectLevelColor = (level: string) => {
  if (level.includes('严重')) return 'red'
  if (level.includes('一般')) return 'orange'
  if (level.includes('轻微')) return 'green'
  return 'default'
}

const getBarWidth = (count: number, total: number) => {
  if (total === 0) return '0%'
  return `${(count / total) * 100}%`
}

// 拖动分隔条
const startDrag = (e: MouseEvent) => {
  isDragging.value = true
  const startY = e.clientY
  const startHeight = topHeight.value

  const onMouseMove = (e: MouseEvent) => {
    const deltaY = e.clientY - startY
    const containerHeight = window.innerHeight - 80 // 减去header高度
    const deltaPercent = (deltaY / containerHeight) * 100
    let newHeight = startHeight + deltaPercent

    // 限制高度范围
    newHeight = Math.max(30, Math.min(70, newHeight))
    topHeight.value = newHeight
  }

  const onMouseUp = () => {
    isDragging.value = false
    document.removeEventListener('mousemove', onMouseMove)
    document.removeEventListener('mouseup', onMouseUp)
  }

  document.addEventListener('mousemove', onMouseMove)
  document.addEventListener('mouseup', onMouseUp)
}

// 批量测试
const startBatchTest = async () => {
  if (selectedRuleIds.value.length === 0 || !medicalText.value.trim()) {
    message.warning('请选择规则并输入病历文本')
    return
  }

  // 添加时间线事件
  addTimelineEvent(
    '开始批量评估',
    `选择了 ${selectedRuleIds.value.length} 条规则`,
    PlayCircleOutlined,
    'blue',
  )

  isTesting.value = true
  testResults.value = []
  testProgress.value = {
    total: selectedRuleIds.value.length,
    completed: 0,
  }

  try {
    for (const ruleId of selectedRuleIds.value) {
      const rule = admissionRules.value.find((r) => r.rule_id === ruleId)
      if (!rule) continue

      try {
        const response = await testQCRule({
          rule_id: ruleId,
          medical_text: medicalText.value,
        })

        if (response.success && response.data) {
          testResults.value.push({
            ruleId,
            ruleName: rule.name,
            isCompliant: response.data.is_compliant,
            status: response.data.status,
            findings: response.data.findings,
            applicability: response.data.applicability,
            notApplicable: response.data.not_applicable,
            notApplicableReason: response.data.not_applicable_reason,
            evidenceVerified: response.data.evidence_verified,
            confidence: response.data.confidence ?? 0,
            evidence: response.data.findings || response.data.evidence,
            suggestion: response.data.suggestion,
            issues: response.data.issues || [],
            llmRawOutput: response.data.llm_raw_output,
            metadata: response.data.metadata,
            error: response.success ? undefined : response.message || '评估失败',
          })
        }
      } catch (error) {
        console.error(`测试规则 ${ruleId} 失败:`, error)
      }

      testProgress.value.completed++
    }

    addTimelineEvent(
      '批量评估完成',
      `共测试 ${testResults.value.length} 条规则`,
      CheckOutlined,
      'green',
    )
    message.success(`批量测试完成！共测试 ${testResults.value.length} 条规则`)
  } catch (error) {
    console.error('批量测试失败:', error)
    message.error('批量测试失败')
  } finally {
    isTesting.value = false
  }
}

// 生产批量质控
const startProductionBatchQC = async () => {
  if (selectedRuleIds.value.length === 0 || !medicalText.value.trim()) {
    message.warning('请选择规则并输入病历文本')
    return
  }

  addTimelineEvent(
    '启动生产质控',
    `使用优化提示词评估 ${selectedRuleIds.value.length} 条规则`,
    RocketOutlined,
    'blue',
  )

  isProductionTesting.value = true
  productionResult.value = null

  try {
    const response = await batchEvaluateQC({
      document_id: `test-${Date.now()}`,
      document_content: medicalText.value,
      document_type: currentConfig.value.label,
      rule_ids: selectedRuleIds.value,
      persist: false,
    })

    productionResult.value = response
    addTimelineEvent(
      '生产质控完成',
      `合规率 ${response.data?.evaluation_summary.compliance_rate?.toFixed(1)}%，发现 ${response.data?.evaluation_summary.issues_found} 个问题`,
      CheckOutlined,
      'green',
    )
    message.success('生产批量质控完成！')
    activeTab.value = 'overview' // 切换到概览页
  } catch (error) {
    console.error('生产批量质控失败:', error)
    message.error('生产批量质控失败')
  } finally {
    isProductionTesting.value = false
  }
}

// 添加时间线事件
const addTimelineEvent = (title: string, description: string, icon: any, color: string) => {
  const now = new Date()
  const time = `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}:${now.getSeconds().toString().padStart(2, '0')}`

  evaluationTimeline.value.unshift({
    time,
    title,
    description,
    icon,
    color,
  })
}

// 导出功能
const exportAsJSON = () => {
  if (!productionResult.value) {
    message.warning('暂无评估结果')
    return
  }

  const dataStr = JSON.stringify(productionResult.value, null, 2)
  const blob = new Blob([dataStr], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `质控评估结果_${Date.now()}.json`
  link.click()
  URL.revokeObjectURL(url)
  message.success('导出成功')
}

const exportAsExcel = () => {
  message.info('Excel导出功能开发中...')
}

const exportAsPDF = () => {
  message.info('PDF导出功能开发中...')
}

const copyToClipboard = () => {
  if (!productionResult.value?.data) {
    message.warning('暂无评估结果')
    return
  }

  const text = `质控评估结果\n\n合规率：${productionResult.value.data.evaluation_summary.compliance_rate}%\n发现问题：${productionResult.value.data.evaluation_summary.issues_found}个\n\n详细结果请查看导出文件`

  navigator.clipboard
    .writeText(text)
    .then(() => {
      message.success('已复制到剪贴板')
    })
    .catch(() => {
      message.error('复制失败')
    })
}

// 初始化
onMounted(async () => {
  customRules.value = await loadCustomRules()
  loadRulesForDocumentType(currentDocumentType.value)
  addTimelineEvent('页面加载', '批量质控评估页面已就绪', ClockCircleOutlined, 'gray')
})
</script>

<style scoped lang="less">
.batch-rule-test-v3 {
  min-height: 100vh;
  background: #f5f7fa;
  display: flex;
  flex-direction: column;
}

// 页面头部
.page-header {
  background: #fff;
  border-bottom: 1px solid #e8eaed;
  padding: 16px 24px;
  position: sticky;
  top: 0;
  z-index: 100;

  .header-content {
    display: flex;
    justify-content: space-between;
    align-items: center;
    max-width: 1600px;
    margin: 0 auto;
  }

  .header-left {
    .header-title {
      margin: 0;
      font-size: 20px;
      font-weight: 600;
      color: #1f2937;
    }

    .header-subtitle {
      margin: 4px 0 0;
      font-size: 14px;
      color: #6b7280;
    }
  }
}

// 分屏容器
.split-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

// 上半部分
.top-section {
  overflow: hidden;
  padding: 20px 24px 0;

  .top-content {
    height: 100%;
    display: grid;
    grid-template-columns: 35% 65%;
    gap: 20px;
    max-width: 1600px;
    margin: 0 auto;
  }
}

.panel-card {
  height: 100%;
  display: flex;
  flex-direction: column;

  :deep(.ant-card-body) {
    flex: 1;
    overflow-y: auto;
  }
}

.panel-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
}

// 规则面板
.rules-panel {
  .control-group {
    margin-bottom: 16px;

    .control-label {
      display: block;
      font-size: 13px;
      font-weight: 600;
      color: #374151;
      margin-bottom: 8px;
    }
  }

  .selection-control {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 12px;
    background: #f8fafc;
    border-radius: 6px;
    margin-bottom: 12px;

    .selection-count {
      font-size: 14px;
      font-weight: 600;
      color: #1890ff;
    }
  }

  .rules-list-container {
    max-height: 400px;
    overflow-y: auto;

    .rule-item-compact {
      display: flex;
      align-items: flex-start;
      padding: 10px;
      margin-bottom: 8px;
      background: #fff;
      border: 1px solid #e2e8f0;
      border-radius: 6px;
      cursor: pointer;
      transition: all 0.2s;

      &:hover:not(.disabled) {
        border-color: #1890ff;
        box-shadow: 0 2px 8px rgba(24, 144, 255, 0.1);
      }

      &.selected {
        background: #e6f7ff;
        border-color: #91d5ff;
      }

      &.disabled {
        opacity: 0.6;
        cursor: not-allowed;
      }

      .rule-info-compact {
        flex: 1;
        margin-left: 8px;
        min-width: 0;

        .rule-header-compact {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 4px;

          .rule-id-compact {
            font-size: 12px;
            font-weight: 600;
            color: #1890ff;
          }
        }

        .rule-name-compact {
          font-size: 13px;
          color: #1f2937;
          line-height: 1.4;
          overflow: hidden;
          text-overflow: ellipsis;
          display: -webkit-box;
          -webkit-line-clamp: 2;
          -webkit-box-orient: vertical;
        }
      }
    }
  }
}

// 病历面板
.medical-panel {
  .medical-editor-wrapper {
    margin-bottom: 16px;

    .medical-textarea {
      font-family: 'Monaco', 'Menlo', monospace;
      font-size: 13px;
      line-height: 1.6;

      :deep(textarea) {
        resize: none;
      }
    }
  }

  .action-bar {
    display: flex;
    gap: 12px;
  }
}

// 可拖动的分隔条
.drag-handle {
  height: 12px;
  background: #e8eaed;
  cursor: ns-resize;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  transition: background-color 0.2s;

  &:hover,
  &.dragging {
    background: #cbd5e1;

    .drag-handle-line {
      border-color: #64748b;
    }
  }

  .drag-handle-line {
    width: 60px;
    height: 4px;
    border-top: 2px solid #94a3b8;
    border-bottom: 2px solid #94a3b8;
    border-radius: 2px;
    transition: border-color 0.2s;
    position: relative;

    .drag-handle-icon {
      position: absolute;
      top: 50%;
      left: 50%;
      transform: translate(-50%, -50%);
      font-size: 12px;
      color: #64748b;
    }
  }
}

// 下半部分
.bottom-section {
  overflow: hidden;
  padding: 0 24px 20px;

  .bottom-content {
    height: 100%;
    max-width: 1600px;
    margin: 0 auto;
  }

  .results-card {
    height: 100%;
    display: flex;
    flex-direction: column;

    :deep(.ant-card-body) {
      flex: 1;
      overflow-y: auto;
    }
  }

  .results-header-title {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 16px;
  }
}

// 标签页内容
.results-tabs {
  height: 100%;

  :deep(.ant-tabs-content) {
    height: calc(100% - 46px);
  }

  :deep(.ant-tabs-tabpane) {
    height: 100%;
    overflow-y: auto;
  }
}

// 空状态
.empty-state,
.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
  text-align: center;

  .empty-icon,
  .loading-text {
    font-size: 48px;
    margin-bottom: 16px;
  }

  .empty-text,
  .loading-text {
    font-size: 16px;
    font-weight: 500;
    color: #1f2937;
    margin-bottom: 8px;
  }

  .empty-hint {
    font-size: 14px;
    color: #6b7280;
  }
}

// 概览内容
.overview-content {
  .overview-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 16px;
    margin-bottom: 24px;

    .overview-card {
      background: #fff;
      border: 1px solid #e2e8f0;
      border-radius: 12px;
      padding: 24px;
      text-align: center;
      transition: all 0.3s;

      &:hover {
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
        transform: translateY(-2px);
      }

      &.overview-card-large {
        grid-column: 1 / 2;
        grid-row: 1 / 3;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: #fff;
        display: flex;
        align-items: center;
        justify-content: center;
      }

      .stat-icon {
        font-size: 32px;
        margin-bottom: 8px;

        &.error {
          color: #ef4444;
        }

        &.success {
          color: #10b981;
        }
      }

      .stat-value {
        font-size: 28px;
        font-weight: 700;
        color: #1f2937;
        margin-bottom: 4px;
      }

      .stat-label {
        font-size: 13px;
        color: #64748b;
      }
    }

    .overview-chart {
      position: relative;
      width: 200px;
      height: 200px;

      .circular-chart-large {
        transform: rotate(-90deg);

        .circle-bg {
          fill: none;
          stroke: rgba(255, 255, 255, 0.2);
          stroke-width: 12;
        }

        .circle-progress {
          fill: none;
          stroke: #fff;
          stroke-width: 12;
          stroke-linecap: round;
          transition: stroke-dasharray 0.6s ease;
        }
      }

      .chart-center {
        position: absolute;
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%);
        text-align: center;

        .chart-value-large {
          font-size: 40px;
          font-weight: 700;
          line-height: 1;
        }

        .chart-label-large {
          font-size: 16px;
          margin-top: 8px;
          opacity: 0.9;
        }
      }
    }
  }

  .issues-breakdown {
    background: #f8fafc;
    border-radius: 12px;
    padding: 20px;

    .breakdown-title {
      font-size: 16px;
      font-weight: 600;
      color: #1f2937;
      margin-bottom: 16px;
    }

    .breakdown-bars {
      .breakdown-item {
        display: flex;
        align-items: center;
        margin-bottom: 16px;

        &:last-child {
          margin-bottom: 0;
        }

        .breakdown-label {
          width: 100px;
          display: flex;
          align-items: center;
          gap: 6px;
          font-size: 14px;
          color: #374151;

          .breakdown-icon {
            font-size: 16px;
          }
        }

        .breakdown-bar-wrapper {
          flex: 1;
          position: relative;
          height: 32px;
          background: #e2e8f0;
          border-radius: 6px;
          overflow: hidden;

          .breakdown-bar {
            height: 100%;
            border-radius: 6px;
            transition: width 0.6s ease;

            &.error {
              background: linear-gradient(90deg, #ef4444 0%, #f87171 100%);
            }

            &.warning {
              background: linear-gradient(90deg, #f59e0b 0%, #fbbf24 100%);
            }

            &.success {
              background: linear-gradient(90deg, #10b981 0%, #34d399 100%);
            }
          }

          .breakdown-count {
            position: absolute;
            right: 12px;
            top: 50%;
            transform: translateY(-50%);
            font-size: 14px;
            font-weight: 600;
            color: #1f2937;
          }
        }
      }
    }
  }
}

// 详细内容
.details-content {
  .details-toolbar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 16px;

    .details-count {
      font-size: 13px;
      color: #64748b;
    }
  }

  .details-list {
    .detail-item {
      background: #fff;
      border: 1px solid #e2e8f0;
      border-radius: 8px;
      padding: 16px;
      margin-bottom: 12px;

      &.compliant {
        border-left: 3px solid #10b981;
      }

      &.non-compliant {
        border-left: 3px solid #ef4444;
      }

      .detail-header {
        display: flex;
        align-items: flex-start;
        gap: 12px;
        margin-bottom: 12px;

        .detail-icon {
          font-size: 20px;
          margin-top: 2px;

          .anticon-check-circle {
            color: #10b981;
          }

          .anticon-close-circle {
            color: #ef4444;
          }
        }

        .detail-info {
          flex: 1;

          .detail-rule-id {
            font-size: 12px;
            color: #1890ff;
            font-weight: 600;
            margin-bottom: 4px;
          }

          .detail-rule-name {
            font-size: 14px;
            color: #1f2937;
            font-weight: 500;
          }
        }
      }

      .detail-findings,
      .detail-evidence,
      .detail-suggestion {
        margin-top: 12px;
        padding: 12px;
        background: #f8fafc;
        border-radius: 6px;

        .detail-section-label {
          font-size: 12px;
          font-weight: 600;
          color: #64748b;
          margin-bottom: 6px;
        }

        .detail-section-content {
          font-size: 13px;
          color: #374151;
          line-height: 1.6;

          &.evidence-text {
            font-family: 'Monaco', 'Menlo', monospace;
            background: #fff;
            padding: 8px;
            border-radius: 4px;
            border: 1px solid #e2e8f0;
          }
        }
      }
    }
  }
}

// 时间线内容
.timeline-content {
  padding: 20px;

  .timeline-item-content {
    .timeline-time {
      font-size: 12px;
      color: #64748b;
      margin-bottom: 4px;
    }

    .timeline-title {
      font-size: 14px;
      font-weight: 600;
      color: #1f2937;
      margin-bottom: 4px;
    }

    .timeline-desc {
      font-size: 13px;
      color: #6b7280;
    }
  }
}

// 导出内容
.export-content {
  padding: 20px;

  .export-options {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 16px;

    .export-option-card {
      background: #fff;
      border: 2px solid #e2e8f0;
      border-radius: 12px;
      padding: 24px;
      text-align: center;
      cursor: pointer;
      transition: all 0.3s;

      &:hover {
        border-color: #1890ff;
        box-shadow: 0 4px 12px rgba(24, 144, 255, 0.1);
        transform: translateY(-2px);
      }

      .export-icon {
        font-size: 48px;
        color: #1890ff;
        margin-bottom: 12px;
      }

      .export-title {
        font-size: 16px;
        font-weight: 600;
        color: #1f2937;
        margin-bottom: 6px;
      }

      .export-desc {
        font-size: 13px;
        color: #6b7280;
      }
    }
  }
}

// 响应式
@media (max-width: 1200px) {
  .top-section .top-content {
    grid-template-columns: 1fr;
  }

  .overview-content .overview-grid {
    grid-template-columns: repeat(2, 1fr);

    .overview-card-large {
      grid-column: 1 / -1;
      grid-row: auto;
    }
  }

  .export-content .export-options {
    grid-template-columns: 1fr;
  }
}

// LLM 设置按钮样式
.llm-settings-button {
  height: 48px !important;
  font-size: 15px !important;
  font-weight: 500 !important;
  padding: 0 24px !important;
  border-radius: 20px !important;
  border: 2px solid #3b82f6 !important;
  color: #3b82f6 !important;
  background: white !important;
  box-shadow: 0 2px 8px rgba(59, 130, 246, 0.15) !important;
  transition: all 0.3s ease !important;
  display: inline-flex !important;
  align-items: center !important;
  gap: 8px !important;
}

.llm-settings-button:hover {
  background: #3b82f6 !important;
  color: white !important;
  border-color: #3b82f6 !important;
  transform: translateY(-2px) !important;
  box-shadow: 0 4px 16px rgba(59, 130, 246, 0.3) !important;
}

.llm-settings-button :deep(.anticon) {
  font-size: 18px !important;
}

.llm-settings-button span {
  font-weight: 500 !important;
}
</style>
