<template>
  <div
    class="loading-spinner"
    :class="containerClass"
  >
    <!-- 默认旋转圆圈 -->
    <div
      v-if="type === 'spinner'"
      class="spinner"
      :class="spinnerClass"
    >
      <div class="spinner-circle" />
    </div>
    
    <!-- 脉冲动画 -->
    <div
      v-else-if="type === 'pulse'"
      class="pulse-container"
    >
      <div
        class="pulse-dot"
        :class="pulseClass"
      />
      <div
        class="pulse-dot"
        :class="pulseClass"
        style="animation-delay: 0.1s"
      />
      <div
        class="pulse-dot"
        :class="pulseClass"
        style="animation-delay: 0.2s"
      />
    </div>
    
    <!-- 波纹动画 -->
    <div
      v-else-if="type === 'wave'"
      class="wave-container"
    >
      <div
        class="wave-bar"
        :class="waveClass"
      />
      <div
        class="wave-bar"
        :class="waveClass"
        style="animation-delay: 0.1s"
      />
      <div
        class="wave-bar"
        :class="waveClass"
        style="animation-delay: 0.2s"
      />
      <div
        class="wave-bar"
        :class="waveClass"
        style="animation-delay: 0.3s"
      />
      <div
        class="wave-bar"
        :class="waveClass"
        style="animation-delay: 0.4s"
      />
    </div>
    
    <!-- 医疗主题动画 -->
    <div
      v-else-if="type === 'medical'"
      class="medical-container"
    >
      <div
        class="medical-cross"
        :class="medicalClass"
      >
        <div class="cross-horizontal" />
        <div class="cross-vertical" />
      </div>
    </div>
    
    <!-- 加载文本 -->
    <div
      v-if="showText"
      class="loading-text"
      :class="textClass"
    >
      {{ text }}
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

interface Props {
  type?: 'spinner' | 'pulse' | 'wave' | 'medical'
  size?: 'small' | 'medium' | 'large'
  color?: 'primary' | 'secondary' | 'success' | 'warning' | 'error'
  text?: string
  showText?: boolean
  center?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  type: 'spinner',
  size: 'medium',
  color: 'primary',
  text: '加载中...',
  showText: true,
  center: true
})

const containerClass = computed(() => [
  'loading-container',
  `loading-${props.size}`,
  `loading-${props.color}`,
  {
    'loading-center': props.center
  }
])

const spinnerClass = computed(() => [
  'spinner-animation',
  `spinner-${props.size}`,
  `spinner-${props.color}`
])

const pulseClass = computed(() => [
  'pulse-animation',
  `pulse-${props.size}`,
  `pulse-${props.color}`
])

const waveClass = computed(() => [
  'wave-animation',
  `wave-${props.size}`,
  `wave-${props.color}`
])

const medicalClass = computed(() => [
  'medical-animation',
  `medical-${props.size}`,
  `medical-${props.color}`
])

const textClass = computed(() => [
  'text-animation',
  `text-${props.size}`,
  `text-${props.color}`
])
</script>

<style scoped>
.loading-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
}

.loading-center {
  justify-content: center;
  min-height: 100px;
}

/* 尺寸变量 */
.loading-small {
  --spinner-size: 20px;
  --pulse-size: 8px;
  --wave-width: 3px;
  --wave-height: 20px;
  --medical-size: 24px;
  --text-size: 12px;
}

.loading-medium {
  --spinner-size: 32px;
  --pulse-size: 12px;
  --wave-width: 4px;
  --wave-height: 32px;
  --medical-size: 36px;
  --text-size: 14px;
}

.loading-large {
  --spinner-size: 48px;
  --pulse-size: 16px;
  --wave-width: 6px;
  --wave-height: 48px;
  --medical-size: 54px;
  --text-size: 16px;
}

/* 颜色变量 */
.loading-primary {
  --primary-color: #2b6cf6;
  --primary-light: rgba(43, 108, 246, 0.3);
}

.loading-secondary {
  --primary-color: #6c757d;
  --primary-light: rgba(108, 117, 125, 0.3);
}

.loading-success {
  --primary-color: #52c41a;
  --primary-light: rgba(82, 196, 26, 0.3);
}

.loading-warning {
  --primary-color: #faad14;
  --primary-light: rgba(250, 173, 20, 0.3);
}

.loading-error {
  --primary-color: #f5222d;
  --primary-light: rgba(245, 34, 45, 0.3);
}

/* 旋转动画 */
.spinner {
  width: var(--spinner-size);
  height: var(--spinner-size);
  position: relative;
}

.spinner-circle {
  width: 100%;
  height: 100%;
  border: 3px solid var(--primary-light);
  border-top: 3px solid var(--primary-color);
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

/* 脉冲动画 */
.pulse-container {
  display: flex;
  gap: 4px;
  align-items: center;
}

.pulse-dot {
  width: var(--pulse-size);
  height: var(--pulse-size);
  background-color: var(--primary-color);
  border-radius: 50%;
  animation: pulse 1.4s ease-in-out infinite both;
}

@keyframes pulse {
  0%, 80%, 100% {
    transform: scale(0);
    opacity: 0.5;
  }
  40% {
    transform: scale(1);
    opacity: 1;
  }
}

/* 波纹动画 */
.wave-container {
  display: flex;
  gap: 3px;
  align-items: flex-end;
  height: var(--wave-height);
}

.wave-bar {
  width: var(--wave-width);
  height: 100%;
  background-color: var(--primary-color);
  border-radius: 2px;
  animation: wave 1.2s ease-in-out infinite;
}

@keyframes wave {
  0%, 40%, 100% {
    transform: scaleY(0.4);
  }
  20% {
    transform: scaleY(1);
  }
}

/* 医疗主题动画 */
.medical-container {
  width: var(--medical-size);
  height: var(--medical-size);
  position: relative;
}

.medical-cross {
  width: 100%;
  height: 100%;
  position: relative;
  animation: medicalRotate 2s linear infinite;
}

.cross-horizontal,
.cross-vertical {
  position: absolute;
  background-color: var(--primary-color);
  border-radius: 2px;
}

.cross-horizontal {
  width: 70%;
  height: 15%;
  top: 42.5%;
  left: 15%;
}

.cross-vertical {
  width: 15%;
  height: 70%;
  top: 15%;
  left: 42.5%;
}

@keyframes medicalRotate {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

/* 加载文本 */
.loading-text {
  font-size: var(--text-size);
  color: var(--primary-color);
  font-weight: 500;
  animation: textFade 2s ease-in-out infinite;
}

@keyframes textFade {
  0%, 100% { opacity: 0.6; }
  50% { opacity: 1; }
}

/* 响应式优化 */
@media (max-width: 768px) {
  .loading-container {
    gap: 8px;
  }
  
  .loading-large {
    --spinner-size: 36px;
    --pulse-size: 12px;
    --wave-height: 36px;
    --medical-size: 42px;
    --text-size: 14px;
  }
}
</style> 