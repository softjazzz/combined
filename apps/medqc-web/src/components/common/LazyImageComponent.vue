<template>
  <div 
    ref="containerRef"
    class="lazy-image-container"
    :class="{ 'lazy-image-loading': isLoading, 'lazy-image-error': hasError }"
    :style="containerStyle"
  >
    <!-- 占位符 -->
    <div 
      v-if="isLoading && !hasError" 
      class="lazy-image-placeholder"
    >
      <div class="lazy-image-skeleton" v-if="showSkeleton">
        <div class="skeleton-content"></div>
      </div>
      <a-spin v-else size="small" />
      <span v-if="loadingText" class="lazy-image-text">{{ loadingText }}</span>
    </div>
    
    <!-- 错误状态 -->
    <div 
      v-else-if="hasError" 
      class="lazy-image-error-content"
      @click="retry"
    >
      <div class="error-icon">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor">
          <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/>
        </svg>
      </div>
      <span class="error-text">{{ errorText || '加载失败，点击重试' }}</span>
    </div>
    
    <!-- 实际图片 -->
    <img
      v-else
      ref="imageRef"
      :src="currentSrc"
      :alt="alt"
      :class="imageClass"
      :style="imageStyle"
      @load="handleLoad"
      @error="handleError"
      @click="handleClick"
    />
    
    <!-- 遮罩层 -->
    <div 
      v-if="overlay && !isLoading && !hasError"
      class="lazy-image-overlay"
      :class="overlayClass"
    >
      <slot name="overlay">
        <div class="overlay-content">{{ overlay }}</div>
      </slot>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'

// Props 定义
interface Props {
  src: string
  alt?: string
  placeholder?: string
  fallback?: string
  width?: string | number
  height?: string | number
  fit?: 'fill' | 'contain' | 'cover' | 'none' | 'scale-down'
  loading?: 'lazy' | 'eager'
  threshold?: number
  rootMargin?: string
  showSkeleton?: boolean
  loadingText?: string
  errorText?: string
  overlay?: string
  overlayClass?: string
  imageClass?: string
  retryCount?: number
  retryDelay?: number
  preload?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  alt: '',
  fit: 'cover',
  loading: 'lazy',
  threshold: 0.1,
  rootMargin: '50px',
  showSkeleton: true,
  retryCount: 3,
  retryDelay: 1000,
  preload: false
})

// Emits 定义
const emit = defineEmits<{
  load: [Event]
  error: [Event]
  click: [Event]
  intersect: [IntersectionObserverEntry]
}>()

// 响应式数据
const containerRef = ref<HTMLElement>()
const imageRef = ref<HTMLImageElement>()
const isLoading = ref(true)
const hasError = ref(false)
const isIntersecting = ref(false)
const currentRetryCount = ref(0)
const currentSrc = ref('')

// 计算属性
const containerStyle = computed(() => ({
  width: typeof props.width === 'number' ? `${props.width}px` : props.width,
  height: typeof props.height === 'number' ? `${props.height}px` : props.height,
}))

const imageStyle = computed(() => ({
  objectFit: props.fit,
  width: '100%',
  height: '100%',
}))

// IntersectionObserver 实例
let observer: IntersectionObserver | null = null

// 方法
const loadImage = () => {
  if (hasError.value && currentRetryCount.value >= props.retryCount) {
    return
  }
  
  isLoading.value = true
  hasError.value = false
  currentSrc.value = props.src
}

const handleLoad = (event: Event) => {
  isLoading.value = false
  hasError.value = false
  currentRetryCount.value = 0
  emit('load', event)
}

const handleError = (event: Event) => {
  isLoading.value = false
  hasError.value = true
  
  // 如果有fallback图片且还没尝试过，则使用fallback
  if (props.fallback && currentSrc.value !== props.fallback) {
    currentSrc.value = props.fallback
    return
  }
  
  emit('error', event)
  
  // 自动重试
  if (currentRetryCount.value < props.retryCount) {
    setTimeout(() => {
      currentRetryCount.value++
      loadImage()
    }, props.retryDelay)
  }
}

const handleClick = (event: Event) => {
  emit('click', event)
}

const retry = () => {
  currentRetryCount.value = 0
  loadImage()
}

const setupIntersectionObserver = () => {
  if (!containerRef.value || props.loading === 'eager' || props.preload) {
    loadImage()
    return
  }
  
  observer = new IntersectionObserver((entries) => {
      const entry = entries[0]
      isIntersecting.value = entry.isIntersecting
      emit('intersect', entry)
      
      if (entry.isIntersecting && !currentSrc.value) {
        loadImage()
        observer?.unobserve(containerRef.value!)
      }
    },
    {
      threshold: props.threshold,
      rootMargin: props.rootMargin
    }
  )
  
  observer.observe(containerRef.value)
}

const cleanup = () => {
  if (observer && containerRef.value) {
    observer.unobserve(containerRef.value)
    observer.disconnect()
    observer = null
  }
}

// 监听 src 变化
watch(() => props.src, () => {
  currentRetryCount.value = 0
  hasError.value = false
  
  if (props.loading === 'eager' || props.preload || isIntersecting.value) {
    loadImage()
  } else {
    currentSrc.value = ''
    isLoading.value = true
  }
})

// 生命周期
onMounted(() => {
  setupIntersectionObserver()
})

onUnmounted(() => {
  cleanup()
})

// 暴露方法给父组件
defineExpose({
  retry,
  reload: loadImage
})
</script>

<style scoped>
.lazy-image-container {
  position: relative;
  display: inline-block;
  overflow: hidden;
  background-color: #f5f5f5;
}

.lazy-image-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  width: 100%;
  height: 100%;
  background-color: #fafafa;
  color: #999;
}

.lazy-image-skeleton {
  width: 100%;
  height: 100%;
  position: relative;
  overflow: hidden;
  background-color: #f2f2f2;
}

.skeleton-content {
  width: 100%;
  height: 100%;
  background: linear-gradient(90deg, #f2f2f2 25%, #e6e6e6 50%, #f2f2f2 75%);
  background-size: 200% 100%;
  animation: skeleton-loading 1.5s infinite;
}

@keyframes skeleton-loading {
  0% {
    background-position: 200% 0;
  }
  100% {
    background-position: -200% 0;
  }
}

.lazy-image-text {
  margin-top: 8px;
  font-size: 12px;
  color: #999;
}

.lazy-image-error-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  width: 100%;
  height: 100%;
  background-color: #fafafa;
  color: #999;
  cursor: pointer;
  transition: all 0.3s ease;
}

.lazy-image-error-content:hover {
  background-color: #f0f0f0;
  color: #666;
}

.error-icon {
  margin-bottom: 8px;
  opacity: 0.6;
}

.error-text {
  font-size: 12px;
  text-align: center;
  padding: 0 8px;
}

.lazy-image-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0;
  transition: opacity 0.3s ease;
}

.lazy-image-container:hover .lazy-image-overlay {
  opacity: 1;
}

.overlay-content {
  text-align: center;
  padding: 8px;
  font-size: 14px;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .lazy-image-text,
  .error-text {
    font-size: 11px;
  }
  
  .overlay-content {
    font-size: 12px;
    padding: 6px;
  }
}

/* 加载状态动画 */
.lazy-image-loading {
  animation: pulse 1.5s ease-in-out infinite;
}

@keyframes pulse {
  0% {
    opacity: 1;
  }
  50% {
    opacity: 0.8;
  }
  100% {
    opacity: 1;
  }
}

/* 错误状态样式 */
.lazy-image-error {
  border: 1px dashed #d9d9d9;
}
</style>
