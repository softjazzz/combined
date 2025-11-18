<template>
  <transition name="fade">
    <div v-if="visible" class="pause-overlay">
      <div class="pause-content">
        <!-- 暂停图标和标题 -->
        <div class="pause-header">
          <PauseCircleOutlined class="pause-icon" />
          <h2 class="pause-title">演示已暂停</h2>
        </div>

        <!-- 当前进度信息 -->
        <div class="progress-info">
          <div class="current-step">
            <component :is="currentStepIcon" class="step-icon" />
            <span class="step-name">{{ currentStepName }}</span>
          </div>
          <div class="progress-bar">
            <a-progress
              :percent="progress"
              :stroke-color="{
                '0%': '#108ee9',
                '100%': '#87d068',
              }"
              :show-info="true"
            />
          </div>
          <div class="pause-duration" v-if="pauseDuration">
            已暂停：{{ pauseDuration }}
          </div>
        </div>

        <!-- 已完成的步骤 -->
        <div class="completed-steps" v-if="completedSteps.length > 0">
          <h3 class="section-title">
            <CheckCircleOutlined class="title-icon" />
            已完成的步骤
          </h3>
          <ul class="steps-list">
            <li
              v-for="step in completedSteps"
              :key="step.key"
              class="step-item completed"
            >
              <CheckCircleOutlined class="check-icon" />
              <span>{{ step.label }}</span>
            </li>
          </ul>
        </div>

        <!-- 剩余步骤 -->
        <div class="remaining-steps" v-if="remainingSteps.length > 0">
          <h3 class="section-title">
            <ClockCircleOutlined class="title-icon" />
            剩余步骤
          </h3>
          <ul class="steps-list">
            <li
              v-for="step in remainingSteps"
              :key="step.key"
              class="step-item pending"
            >
              <component :is="step.icon" class="step-icon-small" />
              <span>{{ step.label }}</span>
            </li>
          </ul>
        </div>

        <!-- 操作按钮 -->
        <div class="pause-actions">
          <a-button
            type="primary"
            size="large"
            @click="$emit('resume')"
            class="resume-button"
          >
            <PlayCircleOutlined />
            继续演示
          </a-button>
          <a-button
            size="large"
            @click="$emit('stop')"
            danger
          >
            <StopOutlined />
            停止演示
          </a-button>
        </div>

        <!-- 提示信息 -->
        <div class="pause-hint">
          <InfoCircleOutlined />
          点击"继续演示"按钮或按 ESC 键恢复演示
        </div>
      </div>
    </div>
  </transition>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import {
  PauseCircleOutlined,
  PlayCircleOutlined,
  StopOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
  InfoCircleOutlined,
  FileTextOutlined,
  SettingOutlined
} from '@ant-design/icons-vue'

// Props
interface Props {
  visible: boolean
  currentStep: 'target' | 'rules' | 'run'
  progress: number
  pauseStartTime?: Date | null
}

const props = defineProps<Props>()

// Emits
const emit = defineEmits<{
  resume: []
  stop: []
}>()

// 步骤配置
const allSteps = [
  { key: 'target', label: '选择测试对象', icon: FileTextOutlined },
  { key: 'rules', label: '配置质控规则', icon: SettingOutlined },
  { key: 'run', label: '运行质控分析', icon: CheckCircleOutlined }
]

// 当前步骤索引
const currentStepIndex = computed(() => {
  return allSteps.findIndex(s => s.key === props.currentStep)
})

// 当前步骤名称
const currentStepName = computed(() => {
  const step = allSteps.find(s => s.key === props.currentStep)
  return step?.label || '未知步骤'
})

// 当前步骤图标
const currentStepIcon = computed(() => {
  const step = allSteps.find(s => s.key === props.currentStep)
  return step?.icon || FileTextOutlined
})

// 已完成的步骤
const completedSteps = computed(() => {
  return allSteps.slice(0, currentStepIndex.value)
})

// 剩余步骤（包括当前步骤）
const remainingSteps = computed(() => {
  return allSteps.slice(currentStepIndex.value + 1)
})

// 暂停时长
const pauseDuration = ref('')
let pauseTimer: number | null = null

// 更新暂停时长
const updatePauseDuration = () => {
  if (!props.pauseStartTime) {
    pauseDuration.value = ''
    return
  }

  const now = new Date()
  const diff = now.getTime() - props.pauseStartTime.getTime()
  const seconds = Math.floor(diff / 1000)
  const minutes = Math.floor(seconds / 60)
  const remainingSeconds = seconds % 60

  if (minutes > 0) {
    pauseDuration.value = `${minutes}分${remainingSeconds}秒`
  } else {
    pauseDuration.value = `${seconds}秒`
  }
}

// 监听暂停状态
watch(() => props.visible, (newVal) => {
  if (newVal) {
    // 开始计时
    pauseTimer = window.setInterval(updatePauseDuration, 1000)
    updatePauseDuration()
  } else {
    // 停止计时
    if (pauseTimer) {
      clearInterval(pauseTimer)
      pauseTimer = null
    }
    pauseDuration.value = ''
  }
})

// 键盘事件处理
const handleKeyPress = (event: KeyboardEvent) => {
  if (props.visible && event.key === 'Escape') {
    emit('resume')
  }
}

onMounted(() => {
  window.addEventListener('keydown', handleKeyPress)
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeyPress)
  if (pauseTimer) {
    clearInterval(pauseTimer)
  }
})
</script>

<style scoped lang="less">
.pause-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.75);
  backdrop-filter: blur(8px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
  animation: fadeIn 0.3s ease-in-out;
}

.pause-content {
  background: white;
  border-radius: 16px;
  padding: 40px;
  max-width: 600px;
  width: 90%;
  max-height: 80vh;
  overflow-y: auto;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
  animation: slideIn 0.3s ease-out;
}

.pause-header {
  text-align: center;
  margin-bottom: 32px;
}

.pause-icon {
  font-size: 64px;
  color: #faad14;
  margin-bottom: 16px;
}

.pause-title {
  font-size: 28px;
  font-weight: 600;
  color: #262626;
  margin: 0;
}

.progress-info {
  background: #f5f5f5;
  border-radius: 12px;
  padding: 24px;
  margin-bottom: 24px;
}

.current-step {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
  font-size: 18px;
  font-weight: 500;
  color: #1890ff;
}

.step-icon {
  font-size: 24px;
}

.progress-bar {
  margin-bottom: 12px;
}

.pause-duration {
  text-align: center;
  color: #8c8c8c;
  font-size: 14px;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  font-weight: 600;
  color: #262626;
  margin-bottom: 12px;
}

.title-icon {
  font-size: 18px;
}

.steps-list {
  list-style: none;
  padding: 0;
  margin: 0 0 24px 0;
}

.step-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  border-radius: 8px;
  margin-bottom: 8px;
  transition: background 0.2s;

  &.completed {
    background: #f6ffed;
    border: 1px solid #b7eb8f;

    .check-icon {
      color: #52c41a;
      font-size: 18px;
    }
  }

  &.pending {
    background: #fafafa;
    border: 1px solid #d9d9d9;
    color: #8c8c8c;

    .step-icon-small {
      font-size: 16px;
      color: #8c8c8c;
    }
  }
}

.pause-actions {
  display: flex;
  gap: 12px;
  justify-content: center;
  margin-bottom: 16px;
}

.resume-button {
  min-width: 140px;
}

.pause-hint {
  text-align: center;
  color: #8c8c8c;
  font-size: 13px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
}

@keyframes fadeIn {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

@keyframes slideIn {
  from {
    transform: translateY(-20px);
    opacity: 0;
  }
  to {
    transform: translateY(0);
    opacity: 1;
  }
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>

