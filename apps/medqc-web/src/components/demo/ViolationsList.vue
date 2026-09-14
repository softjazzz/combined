<!--
  严重违规项列表组件
  展示质控发现的违规项，按严重程度分类
-->
<template>
  <a-card
    title="违规项列表"
    :bordered="false"
    class="violations-list"
  >
    <!-- 统计摘要 -->
    <a-alert
      :message="`共发现 ${violations.length} 项违规`"
      :description="summaryDescription"
      :type="alertType"
      show-icon
      class="mb-4"
    />

    <!-- 违规项列表 -->
    <a-collapse
      v-model:active-key="activeKeys"
      accordion
    >
      <a-collapse-panel
        v-for="(violation, index) in violations"
        :key="violation.id"
        :header="violationHeader(violation, index)"
      >
        <template #extra>
          <a-tag :color="severityColor(violation.severity)">
            {{ severityText(violation.severity) }}
          </a-tag>
        </template>

        <!-- 违规详情 -->
        <div class="violation-detail">
          <!-- 描述 -->
          <div class="detail-section">
            <h4>
              <ExclamationCircleOutlined class="section-icon" />
              问题描述
            </h4>
            <p>{{ violation.description }}</p>
          </div>

          <!-- 改进建议 -->
          <div class="detail-section">
            <h4>
              <BulbOutlined class="section-icon" />
              改进建议
            </h4>
            <p>{{ violation.suggestion }}</p>
          </div>

          <!-- 操作按钮 -->
          <div class="detail-actions">
            <a-space>
              <a-button
                size="small"
                @click="handleCopyViolation(violation)"
              >
                <template #icon>
                  <CopyOutlined />
                </template>
                复制
              </a-button>
              <a-button
                size="small"
                type="link"
                @click="handleViewDetail(violation)"
              >
                查看详情
              </a-button>
            </a-space>
          </div>
        </div>
      </a-collapse-panel>
    </a-collapse>

    <!-- 空状态 -->
    <a-empty
      v-if="violations.length === 0"
      description="暂无违规项"
      :image="Empty.PRESENTED_IMAGE_SIMPLE"
    />

    <!-- 按严重程度分组统计 -->
    <a-divider v-if="violations.length > 0" />
    
    <div
      v-if="violations.length > 0"
      class="severity-stats"
    >
      <h4>严重程度分布</h4>
      <a-row :gutter="16">
        <a-col :span="8">
          <a-statistic
            title="高"
            :value="severityCount.high"
            suffix="项"
            :value-style="{ color: '#f5222d' }"
          >
            <template #prefix>
              <CloseCircleOutlined />
            </template>
          </a-statistic>
        </a-col>
        <a-col :span="8">
          <a-statistic
            title="中"
            :value="severityCount.medium"
            suffix="项"
            :value-style="{ color: '#faad14' }"
          >
            <template #prefix>
              <WarningOutlined />
            </template>
          </a-statistic>
        </a-col>
        <a-col :span="8">
          <a-statistic
            title="低"
            :value="severityCount.low"
            suffix="项"
            :value-style="{ color: '#2b6cf6' }"
          >
            <template #prefix>
              <InfoCircleOutlined />
            </template>
          </a-statistic>
        </a-col>
      </a-row>
    </div>
  </a-card>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { message, Empty } from 'ant-design-vue'
import {
  ExclamationCircleOutlined,
  BulbOutlined,
  CopyOutlined,
  CloseCircleOutlined,
  WarningOutlined,
  InfoCircleOutlined
} from '@ant-design/icons-vue'

// ========== Props ==========

interface Violation {
  id: string
  title: string
  severity: 'high' | 'medium' | 'low'
  description: string
  suggestion: string
}

const props = defineProps<{
  violations: Violation[]
}>()

// ========== 状态 ==========

// 展开的面板
const activeKeys = ref<string[]>([])

// ========== 计算属性 ==========

/**
 * 统计摘要描述
 */
const summaryDescription = computed(() => {
  const high = severityCount.value.high
  const medium = severityCount.value.medium
  const low = severityCount.value.low

  const parts: string[] = []
  if (high > 0) parts.push(`高严重度 ${high} 项`)
  if (medium > 0) parts.push(`中严重度 ${medium} 项`)
  if (low > 0) parts.push(`低严重度 ${low} 项`)

  return parts.join('，') || '暂无违规项'
})

/**
 * 警告类型
 */
const alertType = computed(() => {
  const high = severityCount.value.high
  if (high > 0) return 'error'
  if (severityCount.value.medium > 0) return 'warning'
  if (severityCount.value.low > 0) return 'info'
  return 'success'
})

/**
 * 按严重程度统计
 */
const severityCount = computed(() => {
  return {
    high: props.violations.filter(v => v.severity === 'high').length,
    medium: props.violations.filter(v => v.severity === 'medium').length,
    low: props.violations.filter(v => v.severity === 'low').length
  }
})

// ========== 方法 ==========

/**
 * 违规项标题
 */
const violationHeader = (violation: Violation, index: number): string => {
  return `${index + 1}. ${violation.title}`
}

/**
 * 严重程度颜色
 */
const severityColor = (severity: 'high' | 'medium' | 'low'): string => {
  const colorMap = {
    high: 'error',
    medium: 'warning',
    low: 'processing'
  }
  return colorMap[severity]
}

/**
 * 严重程度文本
 */
const severityText = (severity: 'high' | 'medium' | 'low'): string => {
  const textMap = {
    high: '高',
    medium: '中',
    low: '低'
  }
  return textMap[severity]
}

/**
 * 复制违规项
 */
const handleCopyViolation = async (violation: Violation) => {
  const text = `【${violation.title}】
严重程度：${severityText(violation.severity)}
问题描述：${violation.description}
改进建议：${violation.suggestion}`

  try {
    await navigator.clipboard.writeText(text)
    message.success('已复制到剪贴板')
  } catch (error) {
    console.error('复制失败:', error)
    message.error('复制失败')
  }
}

/**
 * 查看详情（预留接口）
 */
const handleViewDetail = (violation: Violation) => {
  console.log('查看违规项详情:', violation)
  message.info('详情功能开发中...')
}
</script>

<style scoped lang="less">
.violations-list {
  .violation-detail {
    .detail-section {
      margin-bottom: 16px;

      h4 {
        font-size: 14px;
        font-weight: 600;
        color: rgba(0, 0, 0, 0.85);
        margin-bottom: 8px;

        .section-icon {
          margin-right: 8px;
          color: #2b6cf6;
        }
      }

      p {
        font-size: 14px;
        color: rgba(0, 0, 0, 0.65);
        line-height: 1.6;
        margin: 0;
        padding-left: 24px;
      }
    }

    .detail-actions {
      margin-top: 16px;
      padding-top: 16px;
      border-top: 1px solid #f0f0f0;
    }
  }

  .severity-stats {
    h4 {
      font-size: 14px;
      font-weight: 600;
      margin-bottom: 16px;
    }
  }

  :deep(.ant-collapse-header) {
    font-weight: 500;
  }

  :deep(.ant-collapse-content-box) {
    padding: 16px;
  }
}
</style>

