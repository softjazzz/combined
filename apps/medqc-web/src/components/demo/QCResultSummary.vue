<!--
  质控结果总结组件
  展示总体评估、合规率、等级等核心指标
-->
<template>
  <a-card
    title="质控结果总结"
    :bordered="false"
    class="qc-result-summary"
  >
    <!-- 总体等级 -->
    <div class="grade-section">
      <a-badge
        :color="gradeColor"
        :text="gradeText"
        class="grade-badge"
      />
      <div class="grade-description">
        {{ gradeDescription }}
      </div>
    </div>

    <a-divider />

    <!-- 核心指标 -->
    <a-row :gutter="16">
      <!-- 合规率 -->
      <a-col
        :xs="24"
        :sm="12"
      >
        <a-statistic
          title="合规率"
          :value="result.evaluation_summary.compliance_rate"
          :precision="1"
          suffix="%"
          :value-style="{ color: complianceRateColor }"
        >
          <template #prefix>
            <CheckCircleOutlined v-if="result.evaluation_summary.compliance_rate >= 85" />
            <WarningOutlined v-else-if="result.evaluation_summary.compliance_rate >= 75" />
            <CloseCircleOutlined v-else />
          </template>
        </a-statistic>
        
        <!-- 合规率进度条 -->
        <a-progress
          :percent="result.evaluation_summary.compliance_rate"
          :stroke-color="complianceRateColor"
          :show-info="false"
          class="mt-2"
        />
      </a-col>

      <!-- 严重违规数 -->
      <a-col
        :xs="24"
        :sm="12"
      >
        <a-statistic
          title="严重违规"
          :value="result.evaluation_summary.critical_violations"
          suffix="项"
          :value-style="{ color: violationsColor }"
        >
          <template #prefix>
            <ExclamationCircleOutlined />
          </template>
        </a-statistic>
        
        <!-- 违规数提示 -->
        <div class="violations-hint">
          <a-tag
            v-if="result.evaluation_summary.critical_violations === 0"
            color="success"
          >
            无严重违规
          </a-tag>
          <a-tag
            v-else-if="result.evaluation_summary.critical_violations <= 3"
            color="warning"
          >
            需要改进
          </a-tag>
          <a-tag
            v-else
            color="error"
          >
            严重不合规
          </a-tag>
        </div>
      </a-col>
    </a-row>

    <a-divider />

    <!-- 规则统计 -->
    <a-row :gutter="16">
      <a-col
        :xs="24"
        :sm="8"
      >
        <a-statistic
          title="总规则数"
          :value="result.evaluation_summary.total_rules"
          suffix="条"
        >
          <template #prefix>
            <FileTextOutlined />
          </template>
        </a-statistic>
      </a-col>

      <a-col
        :xs="24"
        :sm="8"
      >
        <a-statistic
          title="合规规则"
          :value="result.evaluation_summary.compliant_rules"
          suffix="条"
          :value-style="{ color: '#52c41a' }"
        >
          <template #prefix>
            <CheckOutlined />
          </template>
        </a-statistic>
      </a-col>

      <a-col
        :xs="24"
        :sm="8"
      >
        <a-statistic
          title="不合规规则"
          :value="nonCompliantRules"
          suffix="条"
          :value-style="{ color: '#f5222d' }"
        >
          <template #prefix>
            <CloseOutlined />
          </template>
        </a-statistic>
      </a-col>
    </a-row>

    <a-divider />

    <!-- 性能指标 -->
    <a-descriptions
      title="性能指标"
      :column="2"
      size="small"
      bordered
    >
      <a-descriptions-item label="处理时间">
        <a-tag color="blue">
          {{ processingTimeFormatted }}
        </a-tag>
      </a-descriptions-item>
      <a-descriptions-item label="Token 使用">
        <a-tag color="purple">
          {{ tokenUsageFormatted }}
        </a-tag>
      </a-descriptions-item>
      <a-descriptions-item label="预估成本">
        <a-tag color="green">
          {{ estimatedCostFormatted }}
        </a-tag>
      </a-descriptions-item>
      <a-descriptions-item label="Token 节省率">
        <a-tag color="orange">
          {{ tokenSavingsRateFormatted }}
        </a-tag>
      </a-descriptions-item>
    </a-descriptions>

    <!-- 评估模式和时间戳 -->
    <div class="meta-info">
      <a-space>
        <a-tag color="cyan">
          {{ result.mode === 'single_prompt' ? '单次Prompt模式' : '多次调用模式' }}
        </a-tag>
        <a-tag>{{ timestampFormatted }}</a-tag>
      </a-space>
    </div>
  </a-card>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import {
  CheckCircleOutlined,
  WarningOutlined,
  CloseCircleOutlined,
  ExclamationCircleOutlined,
  FileTextOutlined,
  CheckOutlined,
  CloseOutlined
} from '@ant-design/icons-vue'

// ========== Props ==========

interface QCEvaluationSummary {
  total_rules: number
  compliant_rules: number
  compliance_rate: number
  overall_grade: string
  critical_violations: number
}

interface QCPerformanceMetrics {
  processing_time: number
  token_usage: number
  estimated_cost: number
}

interface QCOptimizationMetrics {
  token_savings_rate: number
  estimated_original_tokens: number
  actual_tokens_saved: number
  cost_savings: number
}

interface QCResult {
  document_id: string
  evaluation_summary: QCEvaluationSummary
  performance_metrics: QCPerformanceMetrics
  optimization_metrics: QCOptimizationMetrics
  evaluation_results: any[]
  timestamp: string
  status: string
  mode: string
}

const props = defineProps<{
  result: QCResult
}>()

// ========== 计算属性 ==========

/**
 * 等级颜色
 */
const gradeColor = computed(() => {
  const grade = props.result.evaluation_summary.overall_grade
  const colorMap: Record<string, string> = {
    'A': '#52c41a',  // 绿色
    'B': '#1890ff',  // 蓝色
    'C': '#faad14',  // 橙色
    'D': '#ff7a45',  // 深橙色
    'E': '#f5222d'   // 红色
  }
  return colorMap[grade] || '#d9d9d9'
})

/**
 * 等级文本
 */
const gradeText = computed(() => {
  const grade = props.result.evaluation_summary.overall_grade
  return `${grade} 级`
})

/**
 * 等级描述
 */
const gradeDescription = computed(() => {
  const grade = props.result.evaluation_summary.overall_grade
  const descriptionMap: Record<string, string> = {
    'A': '优秀 - 完全符合规范',
    'B': '良好 - 基本符合规范，有少量问题',
    'C': '合格 - 存在一些问题需要改进',
    'D': '不合格 - 存在较多问题',
    'E': '严重不合格 - 需要重新书写'
  }
  return descriptionMap[grade] || '未知等级'
})

/**
 * 合规率颜色
 */
const complianceRateColor = computed(() => {
  const rate = props.result.evaluation_summary.compliance_rate
  if (rate >= 95) return '#52c41a'  // 绿色
  if (rate >= 85) return '#1890ff'  // 蓝色
  if (rate >= 75) return '#faad14'  // 橙色
  if (rate >= 60) return '#ff7a45'  // 深橙色
  return '#f5222d'  // 红色
})

/**
 * 违规数颜色
 */
const violationsColor = computed(() => {
  const count = props.result.evaluation_summary.critical_violations
  if (count === 0) return '#52c41a'  // 绿色
  if (count <= 3) return '#faad14'   // 橙色
  return '#f5222d'  // 红色
})

/**
 * 不合规规则数
 */
const nonCompliantRules = computed(() => {
  return props.result.evaluation_summary.total_rules - props.result.evaluation_summary.compliant_rules
})

/**
 * 格式化处理时间
 */
const processingTimeFormatted = computed(() => {
  const time = props.result.performance_metrics.processing_time
  return `${time.toFixed(2)} 秒`
})

/**
 * 格式化 Token 使用量
 */
const tokenUsageFormatted = computed(() => {
  const tokens = props.result.performance_metrics.token_usage
  return tokens.toLocaleString()
})

/**
 * 格式化预估成本
 */
const estimatedCostFormatted = computed(() => {
  const cost = props.result.performance_metrics.estimated_cost
  const costInCNY = cost * 7  // 假设汇率 1 USD = 7 CNY
  return `$${cost.toFixed(6)} (约 ¥${costInCNY.toFixed(4)})`
})

/**
 * 格式化 Token 节省率
 */
const tokenSavingsRateFormatted = computed(() => {
  const rate = props.result.optimization_metrics.token_savings_rate
  return `${(rate * 100).toFixed(1)}%`
})

/**
 * 格式化时间戳
 */
const timestampFormatted = computed(() => {
  const timestamp = new Date(props.result.timestamp)
  return timestamp.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  })
})
</script>

<style scoped lang="less">
.qc-result-summary {
  .grade-section {
    text-align: center;
    padding: 24px 0;

    .grade-badge {
      font-size: 32px;
      font-weight: bold;

      :deep(.ant-badge-status-dot) {
        width: 16px;
        height: 16px;
      }

      :deep(.ant-badge-status-text) {
        font-size: 32px;
        margin-left: 12px;
      }
    }

    .grade-description {
      margin-top: 12px;
      font-size: 16px;
      color: rgba(0, 0, 0, 0.65);
    }
  }

  .violations-hint {
    margin-top: 8px;
  }

  .meta-info {
    margin-top: 16px;
    text-align: center;
  }

  .ant-statistic {
    margin-bottom: 16px;
  }

  .ant-divider {
    margin: 24px 0;
  }
}
</style>

