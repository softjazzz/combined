<template>
  <a-tag :color="tagColor">
    {{ tagText }}
  </a-tag>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import {
  codingStatusMap,
  reviewStatusMap,
  severityMap,
  alertLevelMap,
  riskLevelMap,
  codingStatusColor,
  reviewStatusColor,
  severityColor,
  alertLevelColor,
  riskLevelColor
} from '@/utils/drg'
import type {
  CodingStatus,
  ReviewStatus,
  Severity,
  AlertLevel,
  RiskLevel
} from '@/types/drg'

interface Props {
  /** 状态类型 */
  type: 'coding' | 'review' | 'severity' | 'alert' | 'risk'
  /** 状态值 */
  value: CodingStatus | ReviewStatus | Severity | AlertLevel | RiskLevel
}

const props = defineProps<Props>()

/** 标签文本 */
const tagText = computed(() => {
  switch (props.type) {
    case 'coding':
      return codingStatusMap[props.value as CodingStatus] || props.value
    case 'review':
      return reviewStatusMap[props.value as ReviewStatus] || props.value
    case 'severity':
      return severityMap[props.value as Severity] || props.value
    case 'alert':
      return alertLevelMap[props.value as AlertLevel] || props.value
    case 'risk':
      return riskLevelMap[props.value as RiskLevel] || props.value
    default:
      return props.value
  }
})

/** 标签颜色 */
const tagColor = computed(() => {
  switch (props.type) {
    case 'coding':
      return codingStatusColor[props.value as CodingStatus] || 'default'
    case 'review':
      return reviewStatusColor[props.value as ReviewStatus] || 'default'
    case 'severity':
      return severityColor[props.value as Severity] || 'default'
    case 'alert':
      return alertLevelColor[props.value as AlertLevel] || 'default'
    case 'risk':
      return riskLevelColor[props.value as RiskLevel] || 'default'
    default:
      return 'default'
  }
})
</script>

<style scoped>
/* 自定义样式（如需要） */
</style>
