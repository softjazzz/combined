<template>
  <div class="content-highlighter">
    <div class="relative">
      <!-- 工具栏 -->
      <div
        class="flex items-center justify-between mb-4 p-3 rounded-lg bg-slate-700/30 border border-slate-600/30"
      >
        <div class="flex items-center gap-3">
          <h4 class="text-sm font-medium text-slate-200 flex items-center gap-2">
            <HighlightOutlined class="text-cyan-400" />
            病案内容分析
          </h4>
          <div class="flex items-center gap-2">
            <span class="text-xs text-slate-400">问题高亮：</span>
            <a-switch
              v-model:checked="highlightEnabled"
              size="small"
              @change="toggleHighlight"
            />
          </div>
        </div>

        <div class="flex items-center gap-2">
          <!-- 问题筛选 -->
          <a-select
            v-model:value="selectedSeverity"
            size="small"
            style="width: 100px"
            class="severity-filter"
            @change="updateHighlights"
          >
            <a-select-option value="all">
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

          <!-- 导航按钮 -->
          <div class="flex items-center gap-1">
            <a-button
              size="small"
              :disabled="currentHighlightIndex <= 0"
              class="nav-btn"
              @click="previousHighlight"
            >
              <UpOutlined />
            </a-button>
            <span class="text-xs text-slate-400 px-2">
              {{ currentHighlightIndex + 1 }}/{{ visibleHighlights.length }}
            </span>
            <a-button
              size="small"
              :disabled="currentHighlightIndex >= visibleHighlights.length - 1"
              class="nav-btn"
              @click="nextHighlight"
            >
              <DownOutlined />
            </a-button>
          </div>

          <!-- 全屏按钮 -->
          <a-button
            size="small"
            class="nav-btn"
            @click="toggleFullscreen"
          >
            <ExpandOutlined v-if="!isFullscreen" />
            <CompressOutlined v-else />
          </a-button>
        </div>
      </div>

      <!-- 内容区域 -->
      <div
        class="relative content-container"
        :class="{ fullscreen: isFullscreen }"
      >
        <div
          v-if="isFullscreen"
          class="absolute top-4 right-4 z-10"
        >
          <a-button
            size="large"
            class="bg-slate-800/80 border-slate-600/50 text-slate-300"
            @click="toggleFullscreen"
          >
            <CompressOutlined />
            退出全屏
          </a-button>
        </div>

        <div
          ref="contentRef"
          class="content-text"
          :class="{ 'fullscreen-content': isFullscreen }"
          v-html="highlightedContent"
        />

        <!-- 问题详情浮层 -->
        <div
          v-if="selectedIssue"
          class="absolute z-20 p-4 rounded-lg bg-slate-800 border border-slate-600 shadow-xl max-w-sm"
          :style="tooltipStyle"
        >
          <div class="flex items-start gap-3">
            <div
              class="w-6 h-6 rounded-full flex items-center justify-center flex-shrink-0"
              :class="getSeverityIconClass(selectedIssue.severity)"
            >
              <ExclamationOutlined class="text-xs" />
            </div>
            <div class="flex-1 min-w-0">
              <div class="flex items-center gap-2 mb-2">
                <h5 class="font-medium text-slate-100 text-sm">
                  {{ selectedIssue.rule_name }}
                </h5>
                <a-tag
                  :color="getSeverityColor(selectedIssue.severity)"
                  size="small"
                >
                  {{ getSeverityLabel(selectedIssue.severity) }}
                </a-tag>
              </div>
              <p class="text-xs text-slate-300 mb-2">
                {{ selectedIssue.description }}
              </p>
              <div class="text-xs text-slate-400 mb-2">
                位置：{{ selectedIssue.location }}
              </div>
              <div class="p-2 rounded bg-blue-500/10 border border-blue-500/20">
                <div class="text-xs text-blue-200 font-medium mb-1">
                  建议：
                </div>
                <div class="text-xs text-blue-300">
                  {{ selectedIssue.suggestion }}
                </div>
              </div>
            </div>
          </div>
          <div
            class="absolute -bottom-2 left-6 w-4 h-4 bg-slate-800 border-r border-b border-slate-600 transform rotate-45"
          />
        </div>
      </div>

      <!-- 问题统计 -->
      <div
        class="mt-4 flex items-center justify-between p-3 rounded-lg bg-slate-700/20 border border-slate-600/20"
      >
        <div class="flex items-center gap-4 text-xs">
          <div class="flex items-center gap-1">
            <div class="w-3 h-3 rounded-full bg-red-500" />
            <span class="text-slate-400">严重: {{ getSeverityCount('critical') }}</span>
          </div>
          <div class="flex items-center gap-1">
            <div class="w-3 h-3 rounded-full bg-orange-500" />
            <span class="text-slate-400">重要: {{ getSeverityCount('major') }}</span>
          </div>
          <div class="flex items-center gap-1">
            <div class="w-3 h-3 rounded-full bg-yellow-500" />
            <span class="text-slate-400">轻微: {{ getSeverityCount('minor') }}</span>
          </div>
        </div>
        <div class="text-xs text-slate-400">
          共发现 {{ issues.length }} 个问题
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, nextTick, onMounted, onUnmounted } from 'vue'
import {
  HighlightOutlined,
  UpOutlined,
  DownOutlined,
  ExpandOutlined,
  CompressOutlined,
  ExclamationOutlined,
} from '@ant-design/icons-vue'
import type { QCIssue } from '@/types'

// Props
interface Props {
  content: string
  issues: QCIssue[]
  activeIssue?: QCIssue | null
}

const props = withDefaults(defineProps<Props>(), {
  activeIssue: null,
})

// Emits
const emit = defineEmits<{
  'issue-click': [issue: QCIssue]
}>()

// 状态
const contentRef = ref<HTMLElement>()
const highlightEnabled = ref(true)
const selectedSeverity = ref('all')
const currentHighlightIndex = ref(0)
const isFullscreen = ref(false)
const selectedIssue = ref<QCIssue | null>(null)
const tooltipStyle = ref({})

// 计算属性
const visibleHighlights = computed(() => {
  if (selectedSeverity.value === 'all') {
    return props.issues
  }
  return props.issues.filter((issue) => issue.severity === selectedSeverity.value)
})

const highlightedContent = computed(() => {
  if (!highlightEnabled.value || !props.content) {
    return props.content.replace(/\n/g, '<br>')
  }

  let content = props.content
  const highlights: Array<{
    issue: QCIssue
    start: number
    end: number
    text: string
  }> = []

  // 模拟问题位置检测（实际应用中应该由后端提供精确位置）
  visibleHighlights.value.forEach((issue: QCIssue) => {
    const keywords = extractKeywords(issue.description, issue.location || '')

    keywords.forEach((keyword) => {
      const regex = new RegExp(keyword, 'gi')
      let match

      while ((match = regex.exec(content)) !== null) {
        highlights.push({
          issue,
          start: match.index,
          end: match.index + match[0].length,
          text: match[0],
        })
      }
    })
  })

  // 按位置排序，从后往前处理避免位置偏移
  highlights.sort((a, b) => b.start - a.start)

  // 应用高亮
  highlights.forEach((highlight, index: number) => {
    const className = `highlight-${highlight.issue.severity}`
    const dataAttrs = `data-issue-id="${highlight.issue.id}" data-highlight-index="${index}"`
    const highlightHtml = `<span class="${className} highlight-text" ${dataAttrs}>${highlight.text}</span>`

    content =
      content.substring(0, highlight.start) + highlightHtml + content.substring(highlight.end)
  })

  return content.replace(/\n/g, '<br>')
})

// 方法
const extractKeywords = (description: string, location: string): string[] => {
  // 简单的关键词提取逻辑，实际应用中应该更智能
  const keywords: string[] = []

  // 从描述中提取关键词
  const descWords = description.match(/[\u4e00-\u9fa5]{2,}/g) || []
  keywords.push(...descWords.slice(0, 3))

  // 从位置中提取关键词
  const locationWords = location.match(/[\u4e00-\u9fa5]{2,}/g) || []
  keywords.push(...locationWords)

  return [...new Set(keywords)].filter((word) => word.length >= 2)
}

const toggleHighlight = () => {
  updateHighlights()
}

const updateHighlights = () => {
  currentHighlightIndex.value = 0
  nextTick(() => {
    setupHighlightEvents()
  })
}

const setupHighlightEvents = () => {
  if (!contentRef.value) return

  const highlightElements = contentRef.value.querySelectorAll('.highlight-text')

  highlightElements.forEach((element) => {
    element.addEventListener('mouseenter', (e: Event) => {
      const issueId = (e.target as HTMLElement).getAttribute('data-issue-id')
      const issue = props.issues.find((i) => i.id === issueId)

      if (issue) {
        selectedIssue.value = issue
        updateTooltipPosition(e as MouseEvent)
      }
    })

    element.addEventListener('mouseleave', () => {
      selectedIssue.value = null
    })

    element.addEventListener('click', (e: Event) => {
      const issueId = (e.target as HTMLElement).getAttribute('data-issue-id')
      const issue = props.issues.find((i) => i.id === issueId)

      if (issue) {
        emit('issue-click', issue)
      }
    })
  })
}

const updateTooltipPosition = (event: MouseEvent) => {
  const rect = (event.target as HTMLElement).getBoundingClientRect()
  const containerRect = contentRef.value?.getBoundingClientRect()

  if (containerRect) {
    tooltipStyle.value = {
      top: `${rect.bottom - containerRect.top + 10}px`,
      left: `${rect.left - containerRect.left}px`,
    }
  }
}

const previousHighlight = () => {
  if (currentHighlightIndex.value > 0) {
    currentHighlightIndex.value--
    scrollToHighlight()
  }
}

const nextHighlight = () => {
  if (currentHighlightIndex.value < visibleHighlights.value.length - 1) {
    currentHighlightIndex.value++
    scrollToHighlight()
  }
}

const scrollToHighlight = () => {
  if (!contentRef.value) return

  const highlightElements = contentRef.value.querySelectorAll('.highlight-text')
  const targetElement = highlightElements[currentHighlightIndex.value]

  if (targetElement) {
    targetElement.scrollIntoView({
      behavior: 'smooth',
      block: 'center',
    })

    // 临时高亮当前项
    targetElement.classList.add('current-highlight')
    setTimeout(() => {
      targetElement.classList.remove('current-highlight')
    }, 2000)
  }
}

const toggleFullscreen = () => {
  isFullscreen.value = !isFullscreen.value
}

const getSeverityColor = (severity: string) => {
  const colors = {
    critical: 'red',
    major: 'orange',
    minor: 'yellow',
    low: 'blue',
  }
  return colors[severity as keyof typeof colors] || 'default'
}

const getSeverityLabel = (severity: string) => {
  const labels = {
    critical: '严重',
    major: '重要',
    minor: '轻微',
    low: '提示',
  }
  return labels[severity as keyof typeof labels] || severity
}

const getSeverityIconClass = (severity: string) => {
  const classes = {
    critical: 'bg-red-500 text-white',
    major: 'bg-orange-500 text-white',
    minor: 'bg-yellow-500 text-white',
    low: 'bg-blue-500 text-white',
  }
  return classes[severity as keyof typeof classes] || 'bg-gray-500 text-white'
}

const getSeverityCount = (severity: string) => {
  return props.issues.filter((issue) => issue.severity === severity).length
}

// 监听 activeIssue 变化
watch(
  () => props.activeIssue,
  (newIssue: QCIssue | null | undefined) => {
    if (newIssue) {
      const index = visibleHighlights.value.findIndex((issue) => issue.id === newIssue.id)
      if (index !== -1) {
        currentHighlightIndex.value = index
        nextTick(() => {
          scrollToHighlight()
        })
      }
    }
  },
)

// 生命周期
onMounted(() => {
  nextTick(() => {
    setupHighlightEvents()
  })
})

onUnmounted(() => {
  selectedIssue.value = null
})

// 监听内容变化
watch(
  () => props.content,
  () => {
    nextTick(() => {
      setupHighlightEvents()
    })
  },
)

watch(
  () => props.issues,
  () => {
    nextTick(() => {
      setupHighlightEvents()
    })
  },
  { deep: true },
)
</script>

<style scoped>
.content-container {
  position: relative;
}

.content-container.fullscreen {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 1000;
  background: rgba(15, 23, 42, 0.95);
  backdrop-filter: blur(8px);
  padding: 2rem;
}

.content-text {
  max-height: 500px;
  overflow-y: auto;
  padding: 1.5rem;
  background: rgba(30, 41, 59, 0.5);
  border: 1px solid rgba(71, 85, 105, 0.3);
  border-radius: 0.75rem;
  color: rgb(241 245 249);
  line-height: 1.8;
  font-family:
    'SF Mono', Monaco, 'Cascadia Code', 'Roboto Mono', Consolas, 'Courier New', monospace;
}

.content-text.fullscreen-content {
  max-height: calc(100vh - 8rem);
  font-size: 1.1rem;
  line-height: 2;
}

/* 高亮样式 */
:deep(.highlight-text) {
  cursor: pointer;
  padding: 2px 4px;
  border-radius: 4px;
  transition: all 0.2s ease;
  position: relative;
}

:deep(.highlight-critical) {
  background: rgba(239, 68, 68, 0.2);
  border: 1px solid rgba(239, 68, 68, 0.4);
  color: rgb(252, 165, 165);
}

:deep(.highlight-major) {
  background: rgba(249, 115, 22, 0.2);
  border: 1px solid rgba(249, 115, 22, 0.4);
  color: rgb(253, 186, 116);
}

:deep(.highlight-minor) {
  background: rgba(234, 179, 8, 0.2);
  border: 1px solid rgba(234, 179, 8, 0.4);
  color: rgb(254, 240, 138);
}

:deep(.highlight-low) {
  background: rgba(59, 130, 246, 0.2);
  border: 1px solid rgba(59, 130, 246, 0.4);
  color: rgb(147, 197, 253);
}

:deep(.highlight-text:hover) {
  transform: scale(1.05);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
  z-index: 10;
}

:deep(.current-highlight) {
  animation: pulse 2s ease-in-out;
  box-shadow: 0 0 20px rgba(6, 182, 212, 0.6);
}

@keyframes pulse {
  0%,
  100% {
    box-shadow: 0 0 20px rgba(6, 182, 212, 0.6);
  }
  50% {
    box-shadow: 0 0 30px rgba(6, 182, 212, 0.8);
  }
}

/* 导航按钮样式 */
.nav-btn {
  background: rgba(255, 255, 255, 0.05) !important;
  border: 1px solid rgba(255, 255, 255, 0.1) !important;
  color: rgb(203 213 225) !important;
}

.nav-btn:hover {
  background: rgba(255, 255, 255, 0.1) !important;
  border-color: rgba(6, 182, 212, 0.5) !important;
}

.nav-btn:disabled {
  background: rgba(255, 255, 255, 0.02) !important;
  border-color: rgba(255, 255, 255, 0.05) !important;
  color: rgb(100 116 139) !important;
}

/* 筛选器样式 */
:deep(.severity-filter .ant-select-selector) {
  background: rgba(255, 255, 255, 0.05) !important;
  border: 1px solid rgba(255, 255, 255, 0.1) !important;
  color: rgb(241 245 249) !important;
}

/* 滚动条样式 */
.content-text::-webkit-scrollbar {
  width: 8px;
}

.content-text::-webkit-scrollbar-track {
  background: rgba(71, 85, 105, 0.2);
  border-radius: 4px;
}

.content-text::-webkit-scrollbar-thumb {
  background: rgba(148, 163, 184, 0.4);
  border-radius: 4px;
}

.content-text::-webkit-scrollbar-thumb:hover {
  background: rgba(148, 163, 184, 0.6);
}

/* 响应式设计 */
@media (max-width: 768px) {
  .flex.items-center.justify-between {
    flex-direction: column;
    align-items: flex-start;
    gap: 0.75rem;
  }

  .content-text {
    font-size: 0.875rem;
    padding: 1rem;
  }

  .content-container.fullscreen {
    padding: 1rem;
  }
}
</style>
