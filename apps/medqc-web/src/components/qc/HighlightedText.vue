<template>
  <div class="highlighted-text-container">
    <!-- 高亮控制工具栏 -->
    <div v-if="highlights.length > 0" class="highlight-toolbar mb-3">
      <div class="flex items-center justify-between bg-blue-50 p-2 rounded-lg">
        <div class="flex items-center space-x-2">
          <HighlightOutlined class="text-blue-600" />
          <span class="text-sm font-medium text-blue-800">
            找到 {{ highlights.length }} 处相关证据
          </span>
        </div>
        <div class="flex items-center space-x-2">
          <a-button 
            type="link" 
            size="small" 
            @click="navigateHighlight(-1)"
            :disabled="highlights.length === 0"
          >
            <template #icon><UpOutlined /></template>
            上一个
          </a-button>
          <span class="text-xs text-gray-600">
            {{ currentHighlightIndex + 1 }} / {{ highlights.length }}
          </span>
          <a-button 
            type="link" 
            size="small" 
            @click="navigateHighlight(1)"
            :disabled="highlights.length === 0"
          >
            <template #icon><DownOutlined /></template>
            下一个
          </a-button>
          <a-button 
            type="link" 
            size="small" 
            @click="clearHighlights"
          >
            <template #icon><CloseOutlined /></template>
            清除
          </a-button>
        </div>
      </div>
    </div>

    <!-- 高亮显示的文本内容 -->
    <div 
      ref="textContainer"
      class="highlighted-text-content"
      v-html="highlightedContent"
    ></div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, nextTick, defineProps, defineExpose } from 'vue'
import {
  HighlightOutlined,
  UpOutlined,
  DownOutlined,
  CloseOutlined
} from '@ant-design/icons-vue'

// 组件属性
const props = defineProps<{
  content: string
  searchTexts?: string[]
}>()

// 组件状态
const textContainer = ref<HTMLElement>()
const highlights = ref<string[]>([])
const currentHighlightIndex = ref(0)

// 高亮显示的内容
const highlightedContent = computed(() => {
  let content = props.content
  
  if (highlights.value.length === 0) {
    return formatContent(content)
  }
  
  // 按长度排序，先处理长的文本，避免嵌套问题
  const sortedHighlights = [...highlights.value].sort((a, b) => b.length - a.length)
  
  sortedHighlights.forEach((highlight, index) => {
    if (highlight.trim().length < 3) return // 忽略太短的文本
    
    const escapedHighlight = escapeRegExp(highlight.trim())
    const regex = new RegExp(`(${escapedHighlight})`, 'gi')
    
    content = content.replace(regex, (match, p1) => {
      const isActive = index === currentHighlightIndex.value
      const highlightClass = isActive ? 'highlight-active' : 'highlight-normal'
      return `<mark class="${highlightClass}" data-highlight-index="${index}">${p1}</mark>`
    })
  })
  
  return formatContent(content)
})

// 格式化内容，保持原有的换行和段落结构
const formatContent = (content: string) => {
  return content
    .replace(/\n\s*\n/g, '</p><p class="paragraph">')
    .replace(/\n/g, '<br>')
    .replace(/^/, '<p class="paragraph">')
    .replace(/$/, '</p>')
}

// 转义正则表达式特殊字符
const escapeRegExp = (string: string) => {
  return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

// 添加高亮文本
const addHighlight = (text: string) => {
  if (!text || text.trim().length < 3) return
  
  const trimmedText = text.trim()
  if (!highlights.value.includes(trimmedText)) {
    highlights.value.push(trimmedText)
    currentHighlightIndex.value = highlights.value.length - 1
    
    // 滚动到高亮位置
    nextTick(() => {
      scrollToCurrentHighlight()
    })
  } else {
    // 如果已存在，跳转到该高亮
    const index = highlights.value.indexOf(trimmedText)
    currentHighlightIndex.value = index
    nextTick(() => {
      scrollToCurrentHighlight()
    })
  }
}

// 清除所有高亮
const clearHighlights = () => {
  highlights.value = []
  currentHighlightIndex.value = 0
}

// 导航到指定高亮
const navigateHighlight = (direction: number) => {
  if (highlights.value.length === 0) return
  
  const newIndex = currentHighlightIndex.value + direction
  if (newIndex >= 0 && newIndex < highlights.value.length) {
    currentHighlightIndex.value = newIndex
    nextTick(() => {
      scrollToCurrentHighlight()
    })
  } else if (direction > 0 && newIndex >= highlights.value.length) {
    // 循环到第一个
    currentHighlightIndex.value = 0
    nextTick(() => {
      scrollToCurrentHighlight()
    })
  } else if (direction < 0 && newIndex < 0) {
    // 循环到最后一个
    currentHighlightIndex.value = highlights.value.length - 1
    nextTick(() => {
      scrollToCurrentHighlight()
    })
  }
}

// 滚动到当前高亮位置
const scrollToCurrentHighlight = () => {
  if (!textContainer.value) return
  
  const activeHighlight = textContainer.value.querySelector('.highlight-active')
  if (activeHighlight) {
    activeHighlight.scrollIntoView({
      behavior: 'smooth',
      block: 'center'
    })
  }
}

// 监听搜索文本变化
watch(() => props.searchTexts, (newTexts) => {
  if (newTexts && newTexts.length > 0) {
    clearHighlights()
    newTexts.forEach(text => addHighlight(text))
  }
}, { immediate: true })

// 暴露方法给父组件
defineExpose({
  addHighlight,
  clearHighlights,
  navigateHighlight
})
</script>

<style scoped>
.highlighted-text-container {
  @apply w-full;
}

.highlight-toolbar {
  @apply sticky top-0 z-10;
}

.highlighted-text-content {
  @apply bg-white rounded-lg p-4 border border-gray-200;
  max-height: 500px;
  overflow-y: auto;
  line-height: 1.6;
}

.highlighted-text-content :deep(.paragraph) {
  @apply mb-3 text-gray-800;
}

.highlighted-text-content :deep(.paragraph:last-child) {
  @apply mb-0;
}

.highlighted-text-content :deep(mark.highlight-normal) {
  @apply bg-yellow-200 text-yellow-900 px-1 rounded;
  animation: highlight-pulse 2s ease-in-out;
}

.highlighted-text-content :deep(mark.highlight-active) {
  @apply bg-orange-300 text-orange-900 px-1 rounded font-medium;
  animation: highlight-active 1s ease-in-out infinite alternate;
  box-shadow: 0 0 0 2px rgba(251, 146, 60, 0.3);
}

@keyframes highlight-pulse {
  0% { background-color: rgba(254, 240, 138, 0.3); }
  50% { background-color: rgba(254, 240, 138, 0.8); }
  100% { background-color: rgba(254, 240, 138, 0.5); }
}

@keyframes highlight-active {
  0% { background-color: rgba(251, 146, 60, 0.6); }
  100% { background-color: rgba(251, 146, 60, 0.9); }
}

/* 滚动条样式 */
.highlighted-text-content::-webkit-scrollbar {
  width: 6px;
}

.highlighted-text-content::-webkit-scrollbar-track {
  @apply bg-gray-100 rounded;
}

.highlighted-text-content::-webkit-scrollbar-thumb {
  @apply bg-gray-400 rounded;
}

.highlighted-text-content::-webkit-scrollbar-thumb:hover {
  @apply bg-gray-500;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .highlight-toolbar {
    @apply text-xs;
  }
  
  .highlighted-text-content {
    @apply text-sm p-3;
    max-height: 400px;
  }
}
</style>
