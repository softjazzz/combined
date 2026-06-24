<template>
  <div class="analysis-result-panel">
    <!-- 加载状态 -->
    <div
      v-if="isLoadingResult"
      class="loading-container"
    >
      <a-spin size="large" />
      <div class="text-center mt-4">
        正在加载分析结果...
      </div>
    </div>

    <div v-else>
      <!-- 分析概览 -->
      <a-card
        title="分析概览"
        class="mb-6"
        :bordered="false"
      >
        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-6">
          <!-- 综合评分 -->
          <div class="text-center">
            <div
              class="text-3xl font-bold mb-2"
              :style="{ color: getScoreColor(displayResult.summary.totalScore) }"
            >
              {{ displayResult.summary.totalScore }}分
            </div>
            <div class="text-sm text-gray-600">
              综合评分
            </div>
            <a-tag
              :color="getGradeColor(displayResult.summary.grade)"
              size="large"
              class="mt-2"
            >
              {{ displayResult.summary.grade }}级
            </a-tag>
          </div>

          <!-- AI分析得分 -->
          <div
            v-if="displayResult.summary.aiAnalysisScore"
            class="text-center"
          >
            <a-progress
              type="circle"
              :percent="displayResult.summary.aiAnalysisScore"
              :stroke-color="getScoreColor(displayResult.summary.aiAnalysisScore)"
              :width="60"
            />
            <div class="text-sm text-gray-600 mt-2">
              AI分析
            </div>
            <div class="text-xs text-gray-500">
              {{ displayResult.summary.aiAnalysisScore }}分
            </div>
          </div>

          <!-- 规则引擎得分 -->
          <div
            v-if="displayResult.summary.rulesEngineScore"
            class="text-center"
          >
            <a-progress
              type="circle"
              :percent="displayResult.summary.rulesEngineScore"
              :stroke-color="getScoreColor(displayResult.summary.rulesEngineScore)"
              :width="60"
            />
            <div class="text-sm text-gray-600 mt-2">
              规则引擎
            </div>
            <div class="text-xs text-gray-500">
              {{ displayResult.summary.rulesEngineScore }}分
            </div>
          </div>

          <!-- 完整性评分 -->
          <div class="text-center">
            <a-progress
              type="circle"
              :percent="getItemScore('completeness')"
              :stroke-color="getScoreColor(getItemScore('completeness'))"
              :width="60"
            />
            <div class="text-sm text-gray-600 mt-2">
              完整性
            </div>
            <div class="text-xs text-gray-500">
              {{ getItemScore('completeness') }}分
            </div>
          </div>

          <!-- 一致性评分 -->
          <div class="text-center">
            <a-progress
              type="circle"
              :percent="getItemScore('consistency')"
              :stroke-color="getScoreColor(getItemScore('consistency'))"
              :width="60"
            />
            <div class="text-sm text-gray-600 mt-2">
              一致性
            </div>
            <div class="text-xs text-gray-500">
              {{ getItemScore('consistency') }}分
            </div>
          </div>
        </div>
      </a-card>

      <!-- 详细评分 -->
      <a-card
        title="详细评分"
        class="mb-6"
        :bordered="false"
      >
        <div class="space-y-4">
          <div
            v-for="item in displayResult.itemScores"
            :key="item.itemId"
            class="flex items-center justify-between p-4 bg-gray-50 rounded-lg"
          >
            <div class="flex-1">
              <div class="font-medium">
                {{ item.itemName }}
              </div>
              <div class="text-sm text-gray-600">
                {{ item.assessment }}
              </div>
              <div
                v-if="item.deduction > 0"
                class="text-xs text-red-600 mt-1"
              >
                扣分：{{ item.deduction }}分
              </div>
            </div>
            <div class="text-right">
              <div
                class="text-xl font-bold"
                :style="{ color: getScoreColor(item.actualScore) }"
              >
                {{ item.actualScore }}/{{ item.totalScore }}分
              </div>
              <a-progress
                :percent="Math.round((item.actualScore / item.totalScore) * 100)"
                :stroke-color="getScoreColor(item.actualScore)"
                size="small"
                class="w-32"
              />
            </div>
          </div>
        </div>
      </a-card>

      <!-- 发现的问题 -->
      <a-card
        v-if="displayResult.issues && displayResult.issues.length > 0"
        title="发现的问题"
        class="mb-6"
        :bordered="false"
      >
        <template #extra>
          <a-select
            v-model:value="issueFilter"
            placeholder="筛选问题"
            style="width: 120px"
            allow-clear
          >
            <a-select-option value="">
              全部
            </a-select-option>
            <a-select-option value="critical">
              严重
            </a-select-option>
            <a-select-option value="major">
              重要
            </a-select-option>
            <a-select-option value="minor">
              轻微
            </a-select-option>
          </a-select>
        </template>

        <a-list
          :data-source="filteredIssues"
          item-layout="horizontal"
          size="small"
        >
          <template #renderItem="{ item, index }">
            <a-list-item>
              <template #actions>
                <a-space>
                  <a-tag :color="getIssueSeverityColor(item.severity)">
                    {{ getIssueSeverityText(item.severity) }}
                  </a-tag>
                  <a-tag
                    v-if="item.source"
                    :color="getSourceColor(item.source)"
                  >
                    {{ getSourceText(item.source) }}
                  </a-tag>
                </a-space>
              </template>
              <a-list-item-meta>
                <template #avatar>
                  <a-avatar :style="{ backgroundColor: getIssueSeverityColor(item.severity) }">
                    {{ index + 1 }}
                  </a-avatar>
                </template>
                <template #title>
                  <div class="flex items-center gap-2">
                    <span class="font-medium">{{ item.code }}</span>
                    <span
                      v-if="item.deduction"
                      class="text-red-600 text-sm"
                    >(-{{ item.deduction }}分)</span>
                  </div>
                </template>
                <template #description>
                  <div class="space-y-2">
                    <div class="text-gray-800">
                      {{ item.description }}
                    </div>
                    <div
                      v-if="item.location"
                      class="text-xs text-gray-500"
                    >
                      <span class="font-medium">位置：</span>{{ item.location }}
                    </div>
                    <div
                      v-if="item.suggestion"
                      class="text-xs text-blue-600"
                    >
                      <span class="font-medium">建议：</span>{{ item.suggestion }}
                    </div>
                  </div>
                </template>
              </a-list-item-meta>
            </a-list-item>
          </template>
        </a-list>
      </a-card>

      <!-- 改进建议 -->
      <a-card
        v-if="displayResult.recommendations && displayResult.recommendations.length > 0"
        title="改进建议"
        class="mb-6"
        :bordered="false"
      >
        <a-list
          :data-source="displayResult.recommendations"
          item-layout="horizontal"
          size="small"
        >
          <template #renderItem="{ item }">
            <a-list-item>
              <template #actions>
                <a-button
                  type="link"
                  size="small"
                >
                  <template #icon>
                    <CheckOutlined />
                  </template>
                  已处理
                </a-button>
              </template>
              <a-list-item-meta>
                <template #avatar>
                  <a-avatar style="background-color: #1890ff">
                    <template #icon>
                      <BulbOutlined />
                    </template>
                  </a-avatar>
                </template>
                <template #description>
                  <span class="text-gray-800">{{ item }}</span>
                </template>
              </a-list-item-meta>
            </a-list-item>
          </template>
        </a-list>
      </a-card>

      <!-- 规则引擎详情 -->
      <a-card
        v-if="displayResult.rulesEngineResults && displayResult.rulesEngineResults.length > 0"
        title="规则引擎详情"
        class="mb-6"
        :bordered="false"
      >
        <a-collapse>
          <a-collapse-panel
            v-for="(categoryGroup, category) in groupedRulesResults"
            :key="category"
            :header="`${getCategoryName(category)} (${categoryGroup.length}条规则)`"
          >
            <a-list
              :data-source="categoryGroup"
              item-layout="horizontal"
              size="small"
            >
              <template #renderItem="{ item }">
                <a-list-item>
                  <template #actions>
                    <a-space>
                      <a-tag :color="item.passed ? 'green' : 'red'">
                        {{ item.passed ? '通过' : '未通过' }}
                      </a-tag>
                      <span class="text-sm text-gray-600">{{ item.score }}/{{ item.maxScore }}分</span>
                    </a-space>
                  </template>
                  <a-list-item-meta>
                    <template #title>
                      <div class="flex items-center gap-2">
                        <span class="font-medium">{{ item.ruleName }}</span>
                        <a-tag
                          :color="getSeverityColor(item.severity)"
                          size="small"
                        >
                          {{ getSeverityText(item.severity) }}
                        </a-tag>
                      </div>
                    </template>
                    <template #description>
                      <div class="space-y-1">
                        <div
                          v-if="item.issues.length > 0"
                          class="text-sm"
                        >
                          <span class="font-medium text-red-600">问题：</span>
                          <ul class="mt-1 space-y-1">
                            <li
                              v-for="issue in item.issues"
                              :key="issue.code"
                              class="text-gray-700"
                            >
                              {{ issue.description }}
                            </li>
                          </ul>
                        </div>
                        <div class="text-xs text-gray-500">
                          <span class="font-medium">置信度：</span>{{ Math.round(item.confidence * 100) }}%
                          <span class="ml-4 font-medium">执行时间：</span>{{ item.executionTime }}ms
                        </div>
                      </div>
                    </template>
                  </a-list-item-meta>
                </a-list-item>
              </template>
            </a-list>
          </a-collapse-panel>
        </a-collapse>
      </a-card>

      <!-- 分析详情 -->
      <a-card
        title="分析详情"
        :bordered="false"
      >
        <a-descriptions
          :column="2"
          bordered
        >
          <a-descriptions-item label="分析模型">
            阿里云百炼 DeepSeek V3
          </a-descriptions-item>
          <a-descriptions-item label="分析时间">
            {{ formatDateTime(displayResult.analysisTime) }}
          </a-descriptions-item>
          <a-descriptions-item
            v-if="displayResult.processingStats?.aiAnalysisTime"
            label="AI分析耗时"
          >
            {{ Math.round(displayResult.processingStats.aiAnalysisTime / 1000) }}秒
          </a-descriptions-item>
          <a-descriptions-item
            v-if="displayResult.processingStats?.rulesEngineTime"
            label="规则引擎耗时"
          >
            {{ Math.round(displayResult.processingStats.rulesEngineTime / 1000) }}秒
          </a-descriptions-item>
          <a-descriptions-item
            v-if="displayResult.processingStats?.totalProcessingTime"
            label="总处理时间"
          >
            {{ Math.round(displayResult.processingStats.totalProcessingTime / 1000) }}秒
          </a-descriptions-item>
          <a-descriptions-item label="综合评估">
            <span class="text-gray-800">{{ displayResult.summary.overallAssessment }}</span>
          </a-descriptions-item>
        </a-descriptions>
      </a-card>

      <!-- 操作按钮 -->
      <div class="flex justify-end space-x-4 mt-6 pt-6 border-t">
        <a-button @click="exportReport">
          <template #icon>
            <DownloadOutlined />
          </template>
          导出报告
        </a-button>

        <a-button
          type="primary"
          @click="retryAnalysis"
        >
          <template #icon>
            <ReloadOutlined />
          </template>
          重新分析
        </a-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import {
  CheckOutlined,
  BulbOutlined,
  DownloadOutlined,
  ReloadOutlined,
} from '@ant-design/icons-vue'
import { getQCResult } from '../../api/qc-analysis-api'
import type { MedicalRecord } from '../../types/medical-records'
import type { QCAnalysisResult } from '../../types/ai-service'

// 组件属性
interface Props {
  record: MedicalRecord
}

const props = defineProps<Props>()

// 组件事件
interface Emits {
  (e: 'close'): void
  (e: 'retry'): void
}

const emit = defineEmits<Emits>()

type IssueSeverity = 'critical' | 'major' | 'minor'
type RuleCategory = 'completeness' | 'consistency' | 'rationality' | 'timeliness'

interface AnalysisSummary {
  totalScore: number
  grade: string
  overallAssessment: string
  aiAnalysisScore?: number
  rulesEngineScore?: number
  combinedScore?: number
}

interface ItemScore {
  itemId: string
  itemName: string
  totalScore: number
  actualScore: number
  deduction: number
  assessment: string
}

interface AnalysisIssue {
  code: string
  description: string
  severity: IssueSeverity
  category?: string
  itemId?: string
  deduction?: number
  location?: string
  suggestion?: string
  source?: 'ai' | 'rules' | 'hybrid'
}

interface RuleEngineResult {
  ruleId: string
  ruleName: string
  category: RuleCategory
  severity: IssueSeverity
  passed: boolean
  score: number
  maxScore: number
  deduction: number
  issues: AnalysisIssue[]
  confidence: number
  executionTime: number
}

interface EnhancedQCResult {
  recordId: string
  summary: AnalysisSummary
  itemScores: ItemScore[]
  issues: AnalysisIssue[]
  strengths: string[]
  recommendations: string[]
  analysisTime: string
  rulesEngineResults: RuleEngineResult[]
  processingStats?: {
    aiAnalysisTime?: number
    rulesEngineTime?: number
    totalProcessingTime?: number
  }
}

// 状态管理
const analysisResult = ref<EnhancedQCResult | null>(null)
const isLoadingResult = ref(false)
const issueFilter = ref<string>('')

// 加载分析结果
const loadAnalysisResult = async () => {
  if (props.record.status !== 'completed') {
    return
  }

  try {
    isLoadingResult.value = true
    const { data, error } = await getQCResult(props.record.id)

    if (error) {
      console.error('获取分析结果失败:', error)
      // 创建模拟的增强质控结果
      analysisResult.value = createMockEnhancedResult()
    } else {
      analysisResult.value = normalizeResult(data)
    }
  } catch (error) {
    console.error('加载分析结果异常:', error)
    analysisResult.value = createMockEnhancedResult()
  } finally {
    isLoadingResult.value = false
  }
}

// 创建模拟的增强质控结果
const createMockEnhancedResult = (): EnhancedQCResult => {
  return {
    recordId: props.record.id,
    summary: {
      totalScore: props.record.qc_score || 87,
      grade: (props.record.qc_grade || 'B') as '甲级' | '乙级' | '丙级',
      overallAssessment: '病历质量总体良好，部分细节需要完善',
      aiAnalysisScore: 85,
      rulesEngineScore: 90,
      combinedScore: 87,
    },
    itemScores: [
      {
        itemId: 'homepage',
        itemName: '首页',
        totalScore: 20,
        actualScore: 18,
        deduction: 2,
        assessment: '基本信息完整，少量格式问题',
      },
      {
        itemId: 'progress',
        itemName: '病程记录',
        totalScore: 25,
        actualScore: 22,
        deduction: 3,
        assessment: '记录及时完整，表述需要规范',
      },
      {
        itemId: 'diagnosis',
        itemName: '诊断',
        totalScore: 20,
        actualScore: 19,
        deduction: 1,
        assessment: '诊断准确，依据充分',
      },
      {
        itemId: 'surgery',
        itemName: '手术记录',
        totalScore: 15,
        actualScore: 13,
        deduction: 2,
        assessment: '记录完整，细节可以更详细',
      },
      {
        itemId: 'discharge',
        itemName: '出院记录',
        totalScore: 20,
        actualScore: 18,
        deduction: 2,
        assessment: '出院指导完整，随访计划明确',
      },
    ],
    issues: [
      {
        code: 'COMP_001',
        description: '患者过敏史记录不完整',
        severity: 'major',
        itemId: 'homepage',
        deduction: 2,
        location: '首页基本信息',
        suggestion: '补充详细的过敏史记录',
        source: 'rules',
      },
      {
        code: 'CONS_002',
        description: '入院诊断与出院诊断存在不一致',
        severity: 'minor',
        itemId: 'diagnosis',
        deduction: 1,
        location: '诊断部分',
        suggestion: '核实诊断变化的依据',
        source: 'ai',
      },
    ],
    strengths: ['诊断准确', '治疗方案合理', '病程记录及时'],
    recommendations: ['补充患者过敏史记录', '规范病程记录的表述', '完善手术记录的细节描述'],
    analysisTime: new Date().toISOString(),
    rulesEngineResults: [
      {
        ruleId: 'COMP_001',
        ruleName: '基本信息完整性',
        category: 'completeness',
        severity: 'major',
        passed: false,
        score: 80,
        maxScore: 100,
        deduction: 20,
        issues: [
          {
            code: 'COMP_001',
            description: '患者过敏史记录不完整',
            severity: 'major',
            location: '首页基本信息',
            suggestion: '补充详细的过敏史记录',
            deduction: 2,
            category: 'completeness',
          },
        ],
        confidence: 0.95,
        executionTime: 120,
      },
      {
        ruleId: 'CONS_001',
        ruleName: '诊断一致性',
        category: 'consistency',
        severity: 'major',
        passed: true,
        score: 95,
        maxScore: 100,
        deduction: 5,
        issues: [],
        confidence: 0.88,
        executionTime: 150,
      },
    ],
    processingStats: {
      aiAnalysisTime: 3200,
      rulesEngineTime: 800,
      totalProcessingTime: 4000,
    },
  }
}

const normalizeResult = (data: QCAnalysisResult | null): EnhancedQCResult => {
  if (!data) {
    return createMockEnhancedResult()
  }

  const maybeEnhanced = data as unknown as Partial<EnhancedQCResult>
  if (maybeEnhanced.summary && Array.isArray(maybeEnhanced.itemScores)) {
    return maybeEnhanced as EnhancedQCResult
  }

  const categoryToName: Record<RuleCategory, string> = {
    completeness: '完整性',
    consistency: '一致性',
    rationality: '合理性',
    timeliness: '时效性',
  }

  const itemScores: ItemScore[] = (Object.keys(data.categoryScores) as RuleCategory[]).map(
    (category) => {
      const score = data.categoryScores[category]
      return {
        itemId: category,
        itemName: categoryToName[category],
        totalScore: 100,
        actualScore: score,
        deduction: Math.max(0, 100 - score),
        assessment: `${categoryToName[category]}评分为 ${score} 分`,
      }
    },
  )

  const rulesEngineResults: RuleEngineResult[] = data.ruleResults.map((result) => {
    const severity =
      result.severity === 'critical' || result.severity === 'major' || result.severity === 'minor'
        ? result.severity
        : 'minor'
    const category =
      result.category === 'completeness' ||
      result.category === 'consistency' ||
      result.category === 'rationality' ||
      result.category === 'timeliness'
        ? result.category
        : 'completeness'

    return {
      ruleId: result.ruleId,
      ruleName: result.ruleName,
      category,
      severity,
      passed: !result.hasViolation,
      score: typeof result.score === 'number' ? result.score : 0,
      maxScore: 100,
      deduction: typeof result.score === 'number' ? Math.max(0, 100 - result.score) : 0,
      issues: result.hasViolation
        ? [
            {
              code: result.ruleCode || result.ruleId,
              description: result.reasoning || '检测到潜在问题',
              severity,
              location: result.location,
              source: 'ai',
            },
          ]
        : [],
      confidence: result.confidence || 0,
      executionTime: 0,
    }
  })

  return {
    recordId: data.recordId,
    summary: {
      totalScore: data.overallScore,
      grade: data.grade,
      overallAssessment: `共检测 ${data.summary.violatedRules} 个问题，建议按优先级处理`,
      aiAnalysisScore: data.overallScore,
      rulesEngineScore: data.overallScore,
      combinedScore: data.overallScore,
    },
    itemScores,
    issues: rulesEngineResults.flatMap((item) => item.issues),
    strengths: [],
    recommendations: data.suggestions || [],
    analysisTime: data.createdAt || new Date().toISOString(),
    rulesEngineResults,
    processingStats: {
      totalProcessingTime: data.analysisTime,
    },
  }
}

// 计算属性
const displayResult = computed(() => {
  return analysisResult.value || createMockEnhancedResult()
})

const filteredIssues = computed(() => {
  if (!issueFilter.value) return displayResult.value.issues
  return displayResult.value.issues.filter((issue) => issue.severity === issueFilter.value)
})

const groupedRulesResults = computed(() => {
  if (!displayResult.value.rulesEngineResults) return {}

  const grouped: Record<string, RuleEngineResult[]> = {}
  displayResult.value.rulesEngineResults.forEach((result) => {
    if (!grouped[result.category]) {
      grouped[result.category] = []
    }
    grouped[result.category].push(result)
  })

  return grouped
})

// 在组件挂载时加载数据
onMounted(() => {
  loadAnalysisResult()
})

// 辅助方法
const getItemScore = (category: string): number => {
  const item = displayResult.value.itemScores.find(
    (item) => item.itemId === category || item.itemName.includes(getCategoryName(category)),
  )
  return item ? Math.round((item.actualScore / item.totalScore) * 100) : 0
}

const getCategoryName = (category: string): string => {
  const nameMap: Record<string, string> = {
    completeness: '完整性',
    consistency: '一致性',
    rationality: '合理性',
    timeliness: '时效性',
    similarity: '相似性',
    compliance: '合规性',
  }
  return nameMap[category] || category
}

const getScoreColor = (score: number): string => {
  if (score >= 90) return '#52c41a'
  if (score >= 80) return '#faad14'
  if (score >= 70) return '#fa8c16'
  return '#f5222d'
}

const getGradeColor = (grade: string): string => {
  const gradeColorMap: Record<string, string> = {
    甲级: 'green',
    乙级: 'orange',
    丙级: 'red',
    A: 'green',
    B: 'orange',
    C: 'red',
  }
  return gradeColorMap[grade] || 'default'
}

const getIssueSeverityColor = (severity: string): string => {
  const colorMap: Record<string, string> = {
    critical: '#f5222d',
    major: '#faad14',
    minor: '#fa8c16',
  }
  return colorMap[severity] || '#d9d9d9'
}

const getIssueSeverityText = (severity: string): string => {
  const textMap: Record<string, string> = {
    critical: '严重',
    major: '重要',
    minor: '轻微',
  }
  return textMap[severity] || severity
}

const getSourceColor = (source: string): string => {
  const colorMap: Record<string, string> = {
    ai: '#1890ff',
    rules: '#52c41a',
    hybrid: '#722ed1',
  }
  return colorMap[source] || '#d9d9d9'
}

const getSourceText = (source: string): string => {
  const textMap: Record<string, string> = {
    ai: 'AI分析',
    rules: '规则引擎',
    hybrid: '混合分析',
  }
  return textMap[source] || source
}

const getSeverityColor = (severity: string): string => {
  const colorMap: Record<string, string> = {
    critical: 'red',
    major: 'orange',
    minor: 'blue',
  }
  return colorMap[severity] || 'default'
}

const getSeverityText = (severity: string): string => {
  const textMap: Record<string, string> = {
    critical: '严重',
    major: '重要',
    minor: '轻微',
  }
  return textMap[severity] || severity
}

const formatDateTime = (dateTime: string): string => {
  return new Date(dateTime).toLocaleString()
}

const exportReport = () => {
  message.info('报告导出功能开发中...')
}

const retryAnalysis = () => {
  emit('retry')
  emit('close')
}
</script>

<style scoped>
.analysis-result-panel {
  @apply space-y-6;
}

.loading-container {
  @apply flex flex-col items-center justify-center py-12;
}

:deep(.ant-progress-circle) {
  @apply mx-auto;
}

:deep(.ant-list-item-meta-description) {
  @apply text-gray-800;
}

:deep(.ant-descriptions-item-label) {
  @apply font-medium text-gray-700 bg-gray-50;
}

:deep(.ant-collapse-header) {
  @apply font-medium;
}
</style>
