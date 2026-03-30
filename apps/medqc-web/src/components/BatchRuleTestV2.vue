<template>
  <div class="batch-rule-test-v2">
    <!-- 顶部导航区域 -->
    <div class="page-header">
      <div class="header-content">
        <div class="header-left">
          <h1 class="header-title">
            批量质控评估
          </h1>
          <p class="header-subtitle">
            三栏卡片式布局：选择规则 → 输入病历 → 查看结果
          </p>
        </div>
        <div class="header-right">
          <a-button @click="goBack">
            <template #icon>
              <ArrowLeftOutlined />
            </template>
            返回列表
          </a-button>
        </div>
      </div>
    </div>

    <!-- 三栏布局主体 -->
    <div class="three-column-container">
      <!-- 左栏：规则选择区 (25%) -->
      <div class="left-column">
        <a-card
          :bordered="false"
          class="rules-card"
        >
          <template #title>
            <div class="card-title-wrapper">
              <AppstoreOutlined class="title-icon" />
              <span>规则选择</span>
              <a-tag
                v-if="selectedRuleIds.length > 0"
                color="blue"
                style="margin-left: 8px"
              >
                已选 {{ selectedRuleIds.length }}
              </a-tag>
            </div>
          </template>

          <!-- 文书类型选择 -->
          <div class="document-type-selector">
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

          <!-- 筛选工具栏 -->
          <div class="filter-section">
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

            <a-space
              direction="vertical"
              style="width: 100%; margin-top: 8px"
              :size="8"
            >
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
          <div class="selection-summary">
            <a-checkbox
              :checked="isAllSelected"
              :indeterminate="isIndeterminate"
              :disabled="isTesting || filteredRules.length === 0"
              @change="toggleSelectAll"
            >
              全选
            </a-checkbox>
            <span class="summary-text">
              {{ selectedRuleIds.length }}/{{ filteredRules.length }}
            </span>
          </div>

          <!-- 规则列表（紧凑型） -->
          <div class="rules-list">
            <div
              v-for="rule in filteredRules"
              :key="rule.rule_id"
              :class="[
                'rule-item',
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
              <div class="rule-info">
                <div class="rule-id">
                  {{ rule.rule_id }}
                </div>
                <div
                  class="rule-name"
                  :title="rule.name"
                >
                  {{ rule.name }}
                </div>
                <div class="rule-tags">
                  <a-tag
                    :color="getDefectLevelColor(rule.defect_level)"
                    size="small"
                  >
                    {{ normalizeDefectLevel(rule.defect_level) }}
                  </a-tag>
                </div>
              </div>
            </div>
          </div>
        </a-card>
      </div>

      <!-- 中栏：病历编辑区 (40%) -->
      <div class="middle-column">
        <a-card
          :bordered="false"
          class="medical-text-card"
        >
          <template #title>
            <div class="card-title-wrapper">
              <FileTextOutlined class="title-icon" />
              <span>病历文本</span>
              <a-tag
                :color="currentConfig.tagColor"
                style="margin-left: 8px"
              >
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
              重置
            </a-button>
          </template>

          <div class="medical-editor">
            <a-textarea
              v-model:value="medicalText"
              :disabled="isTesting"
              :placeholder="`请输入或编辑${currentConfig.label}...`"
              :auto-size="{ minRows: 20, maxRows: 30 }"
              class="medical-textarea"
              show-count
              :maxlength="5000"
            />
          </div>

          <!-- 操作按钮区 -->
          <div class="action-buttons">
            <a-button
              type="primary"
              size="large"
              block
              :loading="isTesting"
              :disabled="selectedRuleIds.length === 0 || !medicalText.trim()"
              @click="startBatchTest"
            >
              <template #icon>
                <ThunderboltOutlined />
              </template>
              {{
                isTesting
                  ? `评估中 ${testProgress.completed}/${testProgress.total}`
                  : '🚀 开始批量评估'
              }}
            </a-button>

            <a-button
              size="large"
              block
              :loading="isProductionTesting"
              :disabled="selectedRuleIds.length === 0 || !medicalText.trim() || isTesting"
              style="margin-top: 12px"
              @click="startProductionBatchQC"
            >
              <template #icon>
                <ThunderboltOutlined />
              </template>
              {{ isProductionTesting ? '生产质控中...' : '⚡ 生产批量质控' }}
            </a-button>
          </div>
        </a-card>
      </div>

      <!-- 右栏：评估结果区 (35%) -->
      <div class="right-column">
        <a-card
          :bordered="false"
          class="results-card"
        >
          <template #title>
            <div class="card-title-wrapper">
              <BarChartOutlined class="title-icon" />
              <span>评估结果</span>
            </div>
          </template>

          <!-- 空状态 -->
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

          <!-- 评估中状态 -->
          <div
            v-else-if="isTesting || isProductionTesting"
            class="evaluating-state"
          >
            <a-spin size="large" />
            <div class="evaluating-text">
              AI 正在评估中...
            </div>
            <div class="evaluating-hint">
              {{
                isTesting
                  ? `${testProgress.completed}/${testProgress.total} 条规则`
                  : '使用优化提示词批量评估'
              }}
            </div>
          </div>

          <!-- 生产质控结果 -->
          <div
            v-else-if="productionResult && productionResult.data"
            class="production-results"
          >
            <!-- 合规率卡片 -->
            <div class="compliance-card">
              <div class="compliance-chart">
                <div class="chart-circle">
                  <svg
                    viewBox="0 0 100 100"
                    class="circular-chart"
                  >
                    <circle
                      class="circle-bg"
                      cx="50"
                      cy="50"
                      r="45"
                    />
                    <circle
                      class="circle-progress"
                      cx="50"
                      cy="50"
                      r="45"
                      :stroke-dasharray="`${(productionResult.data.evaluation_summary.compliance_rate || 0) * 2.827} 282.7`"
                    />
                  </svg>
                  <div class="chart-text">
                    <div class="chart-value">
                      {{
                        productionResult.data.evaluation_summary.compliance_rate?.toFixed(1) ||
                          '0.0'
                      }}%
                    </div>
                    <div class="chart-label">
                      合规率
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <!-- 问题汇总 -->
            <div class="issues-summary">
              <div class="summary-title">
                📋 问题汇总
              </div>
              <div class="summary-items">
                <div class="summary-row">
                  <span class="summary-label">发现问题：</span>
                  <span class="summary-value error">
                    {{ productionResult.data.evaluation_summary.issues_found ?? 0 }} 个
                  </span>
                </div>
                <div class="summary-row">
                  <span class="summary-label">处理时间：</span>
                  <span class="summary-value">
                    {{
                      productionResult.data.performance_metrics?.processing_time.toFixed(2) ||
                        '0.00'
                    }}s
                  </span>
                </div>
                <div class="summary-row">
                  <span class="summary-label">Token消耗：</span>
                  <span class="summary-value">
                    {{ productionResult.data.performance_metrics?.token_usage || 0 }}
                  </span>
                </div>
              </div>
            </div>

            <!-- 详细结果列表 -->
            <div
              v-if="
                productionResult.data.evaluation_results &&
                  productionResult.data.evaluation_results.length > 0
              "
              class="results-list"
            >
              <div class="results-header">
                <span class="results-title">详细结果</span>
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
              </div>

              <div class="results-items">
                <div
                  v-for="result in filteredEvaluationResults"
                  :key="result.rule_id"
                  :class="['result-item', result.is_compliant ? 'compliant' : 'non-compliant']"
                >
                  <div class="result-header">
                    <div class="result-icon">
                      <CheckCircleOutlined v-if="result.is_compliant" />
                      <CloseCircleOutlined v-else />
                    </div>
                    <div class="result-info">
                      <div class="result-rule-id">
                        {{ result.rule_id }}
                      </div>
                      <div class="result-rule-name">
                        {{ result.rule_name }}
                      </div>
                    </div>
                    <a-tag
                      :color="result.is_compliant ? 'success' : 'error'"
                      size="small"
                    >
                      {{ result.is_compliant ? '合规' : '不合规' }}
                    </a-tag>
                  </div>

                  <div
                    v-if="!result.is_compliant && result.findings"
                    class="result-findings"
                  >
                    <div class="findings-label">
                      问题：
                    </div>
                    <div class="findings-text">
                      {{ result.findings }}
                    </div>
                  </div>

                  <div
                    v-if="!result.is_compliant && result.evidence"
                    class="result-evidence"
                  >
                    <div class="evidence-label">
                      证据：
                    </div>
                    <div class="evidence-text">
                      {{ result.evidence }}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- 传统批量测试结果 -->
          <div
            v-else-if="testResults.length > 0"
            class="test-results"
          >
            <div class="results-stats">
              <div class="stat-item">
                <div class="stat-value">
                  {{ testResults.filter((r) => r.isCompliant).length }}
                </div>
                <div class="stat-label">
                  合规
                </div>
              </div>
              <div class="stat-item">
                <div class="stat-value error">
                  {{ testResults.filter((r) => !r.isCompliant).length }}
                </div>
                <div class="stat-label">
                  不合规
                </div>
              </div>
            </div>

            <div class="results-list">
              <div
                v-for="result in testResults"
                :key="result.ruleId"
                :class="['result-item', result.isCompliant ? 'compliant' : 'non-compliant']"
              >
                <div class="result-header">
                  <div class="result-icon">
                    <CheckCircleOutlined v-if="result.isCompliant" />
                    <CloseCircleOutlined v-else />
                  </div>
                  <div class="result-info">
                    <div class="result-rule-id">
                      {{ result.ruleId }}
                    </div>
                    <div class="result-rule-name">
                      {{ result.ruleName }}
                    </div>
                  </div>
                  <a-tag
                    :color="result.isCompliant ? 'success' : 'error'"
                    size="small"
                  >
                    {{ result.isCompliant ? '合规' : '不合规' }}
                  </a-tag>
                </div>
                <div
                  v-if="!result.isCompliant && result.evidence"
                  class="result-evidence"
                >
                  {{ result.evidence }}
                </div>
              </div>
            </div>
          </div>
        </a-card>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
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

const router = useRouter()

// 图标组件映射
const iconComponents: Record<string, any> = {
  admission: SolutionOutlined,
  course: FileTextOutlined,
  operation: ScissorOutlined,
  discharge: HomeOutlined,
}

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

// 筛选状态
const searchText = ref('')
const filterDefectLevel = ref<string | undefined>(undefined)
const filterComplexity = ref<string | undefined>(undefined)

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

const normalizeComplexity = (complexity: string) => {
  if (complexity.includes('高')) return '高'
  if (complexity.includes('中')) return '中'
  if (complexity.includes('低')) return '低'
  return complexity
}

// 批量测试
const startBatchTest = async () => {
  if (selectedRuleIds.value.length === 0 || !medicalText.value.trim()) {
    message.warning('请选择规则并输入病历文本')
    return
  }

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
    message.success('生产批量质控完成！')
  } catch (error) {
    console.error('生产批量质控失败:', error)
    message.error('生产批量质控失败')
  } finally {
    isProductionTesting.value = false
  }
}

// 初始化
onMounted(async () => {
  customRules.value = await loadCustomRules()
  loadRulesForDocumentType(currentDocumentType.value)
})
</script>

<style scoped lang="less">
.batch-rule-test-v2 {
  min-height: 100vh;
  background: #f5f7fa;
  padding: 0;
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

// 三栏布局容器
.three-column-container {
  display: grid;
  grid-template-columns: 300px 1fr 420px;
  gap: 20px;
  max-width: 1600px;
  margin: 20px auto;
  padding: 0 24px;
  min-height: calc(100vh - 120px);
}

// 卡片标题样式
.card-title-wrapper {
  display: flex;
  align-items: center;
  gap: 8px;

  .title-icon {
    font-size: 18px;
    color: #1890ff;
  }
}

// 左栏：规则选择
.left-column {
  .rules-card {
    height: 100%;
    display: flex;
    flex-direction: column;

    :deep(.ant-card-body) {
      flex: 1;
      display: flex;
      flex-direction: column;
      padding: 16px;
    }
  }

  .document-type-selector {
    margin-bottom: 16px;
  }

  .filter-section {
    margin-bottom: 16px;
  }

  .selection-summary {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 12px;
    background: #f8fafc;
    border-radius: 6px;
    margin-bottom: 12px;

    .summary-text {
      font-size: 14px;
      color: #64748b;
      font-weight: 500;
    }
  }

  .rules-list {
    flex: 1;
    overflow-y: auto;
    max-height: calc(100vh - 480px);

    .rule-item {
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

      .rule-info {
        flex: 1;
        margin-left: 8px;
        min-width: 0;

        .rule-id {
          font-size: 12px;
          color: #1890ff;
          font-weight: 600;
          margin-bottom: 4px;
        }

        .rule-name {
          font-size: 13px;
          color: #1f2937;
          line-height: 1.4;
          margin-bottom: 6px;
          overflow: hidden;
          text-overflow: ellipsis;
          display: -webkit-box;
          -webkit-line-clamp: 2;
          -webkit-box-orient: vertical;
        }

        .rule-tags {
          display: flex;
          gap: 4px;
        }
      }
    }
  }
}

// 中栏：病历编辑
.middle-column {
  .medical-text-card {
    height: 100%;
    display: flex;
    flex-direction: column;

    :deep(.ant-card-body) {
      flex: 1;
      display: flex;
      flex-direction: column;
      padding: 16px;
    }
  }

  .medical-editor {
    flex: 1;
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

  .action-buttons {
    margin-top: auto;
  }
}

// 右栏：评估结果
.right-column {
  .results-card {
    height: 100%;
    display: flex;
    flex-direction: column;

    :deep(.ant-card-body) {
      flex: 1;
      display: flex;
      flex-direction: column;
      padding: 16px;
      overflow-y: auto;
      max-height: calc(100vh - 180px);
    }
  }

  .empty-state,
  .evaluating-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 60px 20px;
    text-align: center;

    .empty-icon,
    .evaluating-text {
      font-size: 48px;
      margin-bottom: 16px;
    }

    .empty-text,
    .evaluating-text {
      font-size: 16px;
      font-weight: 500;
      color: #1f2937;
      margin-bottom: 8px;
    }

    .empty-hint,
    .evaluating-hint {
      font-size: 14px;
      color: #6b7280;
    }
  }

  // 生产质控结果
  .production-results {
    .compliance-card {
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
      border-radius: 12px;
      padding: 24px;
      margin-bottom: 16px;
      color: #fff;

      .compliance-chart {
        display: flex;
        justify-content: center;

        .chart-circle {
          position: relative;
          width: 160px;
          height: 160px;

          .circular-chart {
            transform: rotate(-90deg);

            .circle-bg {
              fill: none;
              stroke: rgba(255, 255, 255, 0.2);
              stroke-width: 8;
            }

            .circle-progress {
              fill: none;
              stroke: #fff;
              stroke-width: 8;
              stroke-linecap: round;
              transition: stroke-dasharray 0.6s ease;
            }
          }

          .chart-text {
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            text-align: center;

            .chart-value {
              font-size: 32px;
              font-weight: 700;
              line-height: 1;
            }

            .chart-label {
              font-size: 14px;
              margin-top: 4px;
              opacity: 0.9;
            }
          }
        }
      }
    }

    .issues-summary {
      background: #f8fafc;
      border-radius: 8px;
      padding: 16px;
      margin-bottom: 16px;

      .summary-title {
        font-size: 14px;
        font-weight: 600;
        color: #1f2937;
        margin-bottom: 12px;
      }

      .summary-items {
        .summary-row {
          display: flex;
          justify-content: space-between;
          padding: 8px 0;
          border-bottom: 1px solid #e2e8f0;

          &:last-child {
            border-bottom: none;
          }

          .summary-label {
            font-size: 13px;
            color: #64748b;
          }

          .summary-value {
            font-size: 14px;
            font-weight: 600;
            color: #1f2937;

            &.error {
              color: #ef4444;
            }
          }
        }
      }
    }

    .results-list {
      .results-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 12px;

        .results-title {
          font-size: 14px;
          font-weight: 600;
          color: #1f2937;
        }
      }

      .results-items {
        .result-item {
          background: #fff;
          border: 1px solid #e2e8f0;
          border-radius: 8px;
          padding: 12px;
          margin-bottom: 12px;
          transition: all 0.2s;

          &:hover {
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
          }

          &.compliant {
            border-left: 3px solid #10b981;
          }

          &.non-compliant {
            border-left: 3px solid #ef4444;
          }

          .result-header {
            display: flex;
            align-items: flex-start;
            gap: 8px;
            margin-bottom: 8px;

            .result-icon {
              font-size: 18px;
              margin-top: 2px;

              .anticon-check-circle {
                color: #10b981;
              }

              .anticon-close-circle {
                color: #ef4444;
              }
            }

            .result-info {
              flex: 1;
              min-width: 0;

              .result-rule-id {
                font-size: 12px;
                color: #1890ff;
                font-weight: 600;
                margin-bottom: 2px;
              }

              .result-rule-name {
                font-size: 13px;
                color: #1f2937;
                line-height: 1.4;
              }
            }
          }

          .result-findings,
          .result-evidence {
            margin-top: 8px;
            padding: 8px;
            background: #f8fafc;
            border-radius: 4px;

            .findings-label,
            .evidence-label {
              font-size: 12px;
              color: #64748b;
              font-weight: 600;
              margin-bottom: 4px;
            }

            .findings-text,
            .evidence-text {
              font-size: 13px;
              color: #374151;
              line-height: 1.5;
            }
          }
        }
      }
    }
  }

  // 传统测试结果
  .test-results {
    .results-stats {
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 12px;
      margin-bottom: 16px;

      .stat-item {
        background: #f8fafc;
        border-radius: 8px;
        padding: 16px;
        text-align: center;

        .stat-value {
          font-size: 28px;
          font-weight: 700;
          color: #1f2937;

          &.error {
            color: #ef4444;
          }
        }

        .stat-label {
          font-size: 13px;
          color: #64748b;
          margin-top: 4px;
        }
      }
    }
  }
}

// 响应式
@media (max-width: 1400px) {
  .three-column-container {
    grid-template-columns: 280px 1fr 380px;
  }
}

@media (max-width: 1200px) {
  .three-column-container {
    grid-template-columns: 1fr;
    gap: 16px;

    .left-column,
    .middle-column,
    .right-column {
      .ant-card {
        height: auto;
      }
    }

    .left-column .rules-list {
      max-height: 400px;
    }
  }
}
</style>
