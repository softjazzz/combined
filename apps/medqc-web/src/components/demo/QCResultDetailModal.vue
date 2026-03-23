<template>
  <a-modal
    v-model:open="visible"
    title="质控分析详细报告"
    :width="'90%'"
    :footer="null"
    :destroy-on-close="true"
    class="qc-result-detail-modal"
  >
    <div
      v-if="result"
      class="modal-content"
    >
      <!-- 总体评分区域 -->
      <div class="summary-section">
        <a-row :gutter="24">
          <a-col :span="6">
            <a-statistic 
              title="总体评分" 
              :value="result.overallScore" 
              suffix="分"
              :value-style="{ color: getScoreColor(result.overallScore), fontSize: '32px', fontWeight: 'bold' }"
            />
          </a-col>
          <a-col :span="6">
            <a-statistic 
              title="质控等级" 
              :value="result.overallGrade"
              :value-style="{ color: getGradeColor(result.overallGrade), fontSize: '32px', fontWeight: 'bold' }"
            />
          </a-col>
          <a-col :span="6">
            <a-statistic 
              title="发现问题" 
              :value="result.issues.length" 
              suffix="个"
              :value-style="{ color: result.issues.length > 0 ? '#cf1322' : '#52c41a', fontSize: '28px' }"
            />
          </a-col>
          <a-col :span="6">
            <a-statistic 
              title="改进建议" 
              :value="result.suggestions.length" 
              suffix="条"
              :value-style="{ color: '#1890ff', fontSize: '28px' }"
            />
          </a-col>
        </a-row>
      </div>

      <a-divider />

      <!-- 分析步骤 -->
      <div
        v-if="analysisSteps && analysisSteps.length > 0"
        class="steps-section"
      >
        <h3>分析步骤</h3>
        <a-steps
          :current="getCurrentStepIndex()"
          direction="vertical"
          size="small"
        >
          <a-step 
            v-for="step in analysisSteps" 
            :key="step.id"
            :title="step.name"
            :description="step.description"
            :status="getStepStatus(step)"
          >
            <template #icon>
              <LoadingOutlined v-if="step.status === 'running'" />
              <CheckCircleOutlined v-else-if="step.status === 'completed'" />
              <ExclamationCircleOutlined v-else-if="step.status === 'error'" />
              <ClockCircleOutlined v-else />
            </template>
          </a-step>
        </a-steps>
      </div>

      <a-divider v-if="analysisSteps && analysisSteps.length > 0" />

      <!-- 发现的问题 -->
      <div
        v-if="result.issues.length > 0"
        class="issues-section"
      >
        <h3>
          <ExclamationCircleOutlined style="color: #cf1322; margin-right: 8px" />
          发现的问题 ({{ result.issues.length }})
        </h3>
        <a-list
          :data-source="result.issues"
          size="default"
          :bordered="true"
        >
          <template #renderItem="{ item, index }">
            <a-list-item>
              <a-list-item-meta>
                <template #title>
                  <a-space>
                    <a-tag :color="getSeverityColor(item.severity)">
                      {{ getSeverityText(item.severity) }}
                    </a-tag>
                    <span style="font-weight: 600; font-size: 15px">{{ index + 1 }}. {{ item.ruleName }}</span>
                  </a-space>
                </template>
                <template #description>
                  <div class="issue-detail">
                    <div class="detail-row">
                      <span class="label">问题说明：</span>
                      <span class="content">{{ item.description }}</span>
                    </div>
                    <div
                      v-if="item.evidence"
                      class="detail-row evidence-row"
                    >
                      <span class="label">原文证据：</span>
                      <div class="evidence-content">
                        <blockquote>{{ item.evidence }}</blockquote>
                      </div>
                    </div>
                    <div
                      v-if="item.location"
                      class="detail-row"
                    >
                      <span class="label">问题定位：</span>
                      <span class="content">{{ item.location }}</span>
                    </div>
                    <div
                      v-if="item.suggestion"
                      class="detail-row suggestion-row"
                    >
                      <span class="label">整改建议：</span>
                      <span class="content suggestion-text">{{ item.suggestion }}</span>
                    </div>
                  </div>
                </template>
              </a-list-item-meta>
            </a-list-item>
          </template>
        </a-list>
      </div>

      <a-divider v-if="result.issues.length > 0" />

      <!-- 规则明细 -->
      <div
        v-if="result.ruleResults && result.ruleResults.length > 0"
        class="rules-section"
      >
        <h3>
          <FileTextOutlined style="margin-right: 8px" />
          规则明细 ({{ result.ruleResults.length }})
        </h3>
        <a-collapse
          v-model:active-key="activeRuleKeys"
          :bordered="false"
        >
          <a-collapse-panel 
            v-for="(item, index) in result.ruleResults" 
            :key="index"
            :header="getRuleHeader(item, index)"
          >
            <template #extra>
              <a-tag :color="item.passed ? 'green' : 'red'">
                {{ item.passed ? '✓ 通过' : '✗ 不通过' }}
              </a-tag>
            </template>
            <div class="rule-detail">
              <a-descriptions
                :column="2"
                size="small"
                bordered
              >
                <a-descriptions-item label="规则ID">
                  {{ item.ruleId || '-' }}
                </a-descriptions-item>
                <a-descriptions-item label="执行时间">
                  {{ item.executionTime.toFixed(2) }}ms
                </a-descriptions-item>
                <a-descriptions-item label="得分">
                  <span :style="{ color: item.passed ? '#52c41a' : '#cf1322', fontWeight: 'bold' }">
                    {{ item.score }}/{{ item.maxScore }}
                  </span>
                </a-descriptions-item>
                <a-descriptions-item label="置信度">
                  {{ (item.confidence * 100).toFixed(0) }}%
                </a-descriptions-item>
              </a-descriptions>
              
              <div class="rule-content">
                <div class="detail-row">
                  <span class="label">详细说明：</span>
                  <span
                    class="content"
                    :class="{ 'text-danger': !item.passed }"
                  >{{ item.details || '（无详细描述）' }}</span>
                </div>
                <div
                  v-if="!item.passed && item.evidence"
                  class="detail-row evidence-row"
                >
                  <span class="label">原文证据：</span>
                  <div class="evidence-content">
                    <blockquote>{{ item.evidence }}</blockquote>
                  </div>
                </div>
                <div
                  v-if="!item.passed && item.location"
                  class="detail-row"
                >
                  <span class="label">问题定位：</span>
                  <span class="content">{{ item.location }}</span>
                </div>
                <div
                  v-if="!item.passed && item.suggestion"
                  class="detail-row suggestion-row"
                >
                  <span class="label">整改建议：</span>
                  <span class="content suggestion-text">{{ item.suggestion }}</span>
                </div>
              </div>
            </div>
          </a-collapse-panel>
        </a-collapse>
      </div>

      <a-divider v-if="result.suggestions.length > 0" />

      <!-- 改进建议 -->
      <div
        v-if="structuredSuggestions.length > 0"
        class="suggestions-section"
      >
        <h3>
          <BulbOutlined style="color: #1890ff; margin-right: 8px" />
          改进建议 ({{ structuredSuggestions.length }})
        </h3>
        <a-list
          :data-source="structuredSuggestions"
          size="default"
          :bordered="true"
        >
          <template #renderItem="{ item, index }">
            <a-list-item>
              <a-list-item-meta>
                <template #title>
                  <a-space>
                    <a-tag :color="getPriorityColor(item.priority)">
                      {{ getPriorityText(item.priority) }}
                    </a-tag>
                    <span style="font-weight: 600">{{ index + 1 }}. {{ item.title }}</span>
                  </a-space>
                </template>
                <template #description>
                  <ol class="list-decimal list-inside space-y-1 text-sm text-gray-700">
                    <li
                      v-for="(step, i) in item.steps"
                      :key="i"
                    >
                      {{ step }}
                    </li>
                  </ol>
                </template>
              </a-list-item-meta>
            </a-list-item>
          </template>
        </a-list>
      </div>

      <!-- 元数据信息 -->
      <a-divider v-if="result.metadata" />
      <div
        v-if="result.metadata"
        class="metadata-section"
      >
        <h3>分析元数据</h3>
        <a-descriptions
          :column="3"
          size="small"
          bordered
        >
          <a-descriptions-item label="分析版本">
            {{ result.metadata.analysisVersion }}
          </a-descriptions-item>
          <a-descriptions-item label="模型版本">
            {{ result.metadata.modelVersion }}
          </a-descriptions-item>
          <a-descriptions-item label="引擎">
            {{ result.metadata.engine || '-' }}
          </a-descriptions-item>
          <a-descriptions-item label="处理时间">
            {{ result.metadata.processingTime.toFixed(2) }}ms
          </a-descriptions-item>
          <a-descriptions-item label="应用规则数">
            {{ result.metadata.rulesApplied }}
          </a-descriptions-item>
          <a-descriptions-item label="总体置信度">
            {{ (result.metadata.confidence * 100).toFixed(0) }}%
          </a-descriptions-item>
          <a-descriptions-item
            label="分析时间"
            :span="3"
          >
            {{ formatDate(result.analysisDate) }}
          </a-descriptions-item>
        </a-descriptions>
      </div>
    </div>

    <template #footer>
      <a-space>
        <a-button @click="handleClose">
          关闭
        </a-button>
        <a-button
          type="primary"
          @click="handleExport"
        >
          <DownloadOutlined />
          导出报告
        </a-button>
      </a-space>
    </template>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { message } from 'ant-design-vue'
import {
  LoadingOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
  ExclamationCircleOutlined,
  FileTextOutlined,
  BulbOutlined,
  DownloadOutlined
} from '@ant-design/icons-vue'
import type { QCResult, AnalysisStep } from '@/types/quality-control'
import { structureSuggestions } from '@/utils/suggestionFormatter'

// Props
const props = defineProps<{
  result: QCResult | null
  analysisSteps?: AnalysisStep[]
}>()

// Emits
const emit = defineEmits<{
  close: []
}>()

// State
const visible = defineModel<boolean>('visible', { default: false })
const activeRuleKeys = ref<number[]>([])

const structuredSuggestions = computed(() =>
  props.result ? structureSuggestions(props.result.suggestions) : []
)

// 计算属性
const getCurrentStepIndex = () => {
  if (!props.analysisSteps) return -1
  const runningIndex = props.analysisSteps.findIndex(step => step.status === 'running')
  if (runningIndex !== -1) return runningIndex
  const completedCount = props.analysisSteps.filter(step => step.status === 'completed').length
  return completedCount - 1
}

// 方法
const getStepStatus = (step: AnalysisStep) => {
  switch (step.status) {
    case 'completed': return 'finish'
    case 'running': return 'process'
    case 'error': return 'error'
    default: return 'wait'
  }
}

const getScoreColor = (score: number) => {
  if (score >= 90) return '#52c41a'
  if (score >= 80) return '#faad14'
  if (score >= 60) return '#fa8c16'
  return '#f5222d'
}

const getGradeColor = (grade: string) => {
  const colors: Record<string, string> = {
    'A': '#52c41a',
    'B': '#faad14',
    'C': '#fa8c16',
    'D': '#f5222d'
  }
  return colors[grade] || '#1890ff'
}

const getSeverityColor = (severity: string) => {
  const colors: Record<string, string> = {
    low: 'green',
    medium: 'orange',
    high: 'red',
    critical: 'red'
  }
  return colors[severity] || 'default'
}

const getSeverityText = (severity: string) => {
  const texts: Record<string, string> = {
    low: '轻微',
    medium: '中等',
    high: '严重',
    critical: '严重'
  }
  return texts[severity] || severity
}

const getPriorityColor = (priority: string) => {
  const colors: Record<string, string> = {
    low: 'default',
    medium: 'blue',
    high: 'orange'
  }
  return colors[priority] || 'default'
}

const getPriorityText = (priority: string) => {
  const texts: Record<string, string> = {
    low: '低优先级',
    medium: '中优先级',
    high: '高优先级'
  }
  return texts[priority] || priority
}

const getRuleHeader = (item: any, index: number) => {
  return `${index + 1}. ${item.ruleName}`
}

const formatDate = (dateStr: string) => {
  return new Date(dateStr).toLocaleString('zh-CN')
}

const handleClose = () => {
  visible.value = false
  emit('close')
}

const handleExport = () => {
  message.info('导出功能开发中...')
}
</script>

<style scoped lang="less">
.qc-result-detail-modal {
  :deep(.ant-modal-body) {
    max-height: 75vh;
    overflow-y: auto;
    padding: 24px;
  }

  .modal-content {
    .summary-section {
      margin-bottom: 16px;
    }

    h3 {
      font-size: 16px;
      font-weight: 600;
      margin-bottom: 16px;
      color: #262626;
      display: flex;
      align-items: center;
    }

    .steps-section {
      margin-bottom: 16px;
    }

    .issues-section,
    .rules-section,
    .suggestions-section {
      margin-bottom: 16px;
    }

    .issue-detail,
    .rule-content {
      .detail-row {
        margin-bottom: 12px;
        display: flex;
        align-items: flex-start;

        .label {
          font-weight: 600;
          color: #595959;
          min-width: 80px;
          margin-right: 8px;
        }

        .content {
          flex: 1;
          color: #262626;
        }

        &.evidence-row {
          flex-direction: column;

          .evidence-content {
            width: 100%;
            margin-top: 8px;
            padding: 12px;
            background: #fafafa;
            border-left: 3px solid #1890ff;
            border-radius: 4px;

            blockquote {
              margin: 0;
              color: #262626;
              white-space: pre-wrap;
              word-break: break-word;
              font-family: 'Courier New', monospace;
              font-size: 13px;
            }
          }
        }

        &.suggestion-row {
          .suggestion-text {
            color: #1890ff;
            font-weight: 500;
          }
        }
      }
    }

    .rule-detail {
      .rule-content {
        margin-top: 16px;
      }
    }

    .text-danger {
      color: #cf1322;
    }

    .metadata-section {
      margin-top: 16px;
    }
  }
}
</style>
