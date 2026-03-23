<template>
  <div class="step-progress">
    <!-- 步骤指示器 -->
    <a-steps
      :current="currentStepIndex"
      size="small"
      class="mb-4"
    >
      <a-step
        v-for="step in steps"
        :key="step.key"
        :title="step.label"
        :status="getStepStatus(step.key)"
      >
        <template #icon>
          <component :is="step.icon" />
        </template>
      </a-step>
    </a-steps>

    <!-- 进度条 -->
    <div class="progress-section">
      <div class="progress-header">
        <span class="progress-label">
          <component
            :is="currentStepIcon"
            class="step-icon"
          />
          {{ currentStepLabel }}
        </span>
        <span class="progress-percentage">{{ progress }}%</span>
      </div>
      <a-progress
        :percent="progress"
        :status="progressStatus"
        :stroke-color="progressColor"
        :show-info="false"
      />
    </div>

    <!-- 条件引导提示 -->
    <a-alert
      v-if="readinessAlert"
      :type="readinessAlert.type"
      :message="readinessAlert.message"
      show-icon
      class="mt-3"
    />

    <!-- 错误提示 -->
    <a-alert
      v-if="error"
      type="error"
      :message="error"
      closable
      class="mt-3"
      @close="$emit('clear-error')"
    />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import {
  FileTextOutlined,
  SettingOutlined,
  CheckCircleOutlined
} from '@ant-design/icons-vue'

// Props
interface Props {
  currentStep: 'target' | 'rules' | 'run'
  progress: number
  error: string | null
  hasRecord: boolean
  hasDocuments: boolean
  hasRules: boolean
  analysisResult: any
}

const props = defineProps<Props>()

// Emits
defineEmits<{
  'clear-error': []
}>()

// 步骤配置
const steps = [
  { key: 'target', label: '测试对象', icon: FileTextOutlined },
  { key: 'rules', label: '规则配置', icon: SettingOutlined },
  { key: 'run', label: '运行与结果', icon: CheckCircleOutlined }
]

// 计算当前步骤索引
const currentStepIndex = computed(() => {
  return steps.findIndex(s => s.key === props.currentStep)
})

// 当前步骤标签
const currentStepLabel = computed(() => {
  const step = steps.find(s => s.key === props.currentStep)
  return step?.label || '运行与结果'
})

// 当前步骤图标
const currentStepIcon = computed(() => {
  const step = steps.find(s => s.key === props.currentStep)
  return step?.icon || CheckCircleOutlined
})

// 获取步骤状态
const getStepStatus = (stepKey: string) => {
  const stepIndex = steps.findIndex(s => s.key === stepKey)
  if (stepIndex < currentStepIndex.value) return 'finish'
  if (stepIndex === currentStepIndex.value) return 'process'
  return 'wait'
}

// 进度条状态
const progressStatus = computed(() => {
  if (props.error) return 'exception'
  if (props.currentStep === 'run' && props.analysisResult) return 'success'
  return 'active'
})

// 进度条颜色
const progressColor = computed(() => {
  if (props.error) return '#ff4d4f'
  if (props.currentStep === 'run' && props.analysisResult) return '#52c41a'
  return '#1890ff'
})

// 条件引导提示
const readinessAlert = computed(() => {
  const { hasRecord, hasDocuments, hasRules } = props

  if (hasRecord && hasDocuments && hasRules) {
    return { type: 'success', message: '✅ 条件满足，点击"开始分析"进入运行与结果' }
  }
  if (!hasRecord) {
    return { type: 'warning', message: '⚠️ 请先选择测试对象（病历+文书）' }
  }
  if (hasRecord && !hasDocuments) {
    return { type: 'warning', message: '⚠️ 已选择病历，请继续选择文书' }
  }
  if (!hasRules) {
    return { type: 'warning', message: '⚠️ 请在右侧"质控规则管理"中选择要应用的规则' }
  }
  return { type: 'info', message: 'ℹ️ 请完善测试对象与规则' }
})
</script>

<style scoped lang="less">
.step-progress {
  .progress-section {
    margin-top: 16px;
  }

  .progress-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 8px;
  }

  .progress-label {
    display: flex;
    align-items: center;
    gap: 8px;
    font-weight: 500;
    color: #1890ff;
  }

  .step-icon {
    font-size: 16px;
  }

  .progress-percentage {
    font-weight: 600;
    color: #1890ff;
  }
}
</style>

