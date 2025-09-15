<template>
  <div class="enhanced-content-viewer">
    <!-- 内容查看器头部 -->
    <div class="viewer-header">
      <div class="header-left">
        <h3 class="viewer-title">
          <FileTextOutlined class="title-icon" />
          {{ title }}
        </h3>
        <div class="content-stats">
          <a-tag color="blue">{{ contentStats.characters }} 字符</a-tag>
          <a-tag color="green">{{ contentStats.lines }} 行</a-tag>
          <a-tag color="orange" v-if="contentStats.words">{{ contentStats.words }} 词</a-tag>
        </div>
      </div>
      <div class="header-actions">
        <a-input-search
          v-model:value="searchKeyword"
          placeholder="搜索内容..."
          style="width: 250px"
          @search="handleSearch"
          @change="handleSearchChange"
          allow-clear
        >
          <template #prefix>
            <SearchOutlined />
          </template>
        </a-input-search>
        <a-segmented
          v-if="props.enableSummaryToggle"
          :options="[{label:'全文', value:'full'},{label:'摘要', value:'summary'}]"
          :value="showSummary ? 'summary' : 'full'"
          @change="(v:any)=>{ showSummary.value = (v==='summary') }"
        />
        <a-button-group>
          <a-tooltip title="全屏查看">
            <a-button @click="toggleFullscreen">
              <FullscreenOutlined v-if="!isFullscreen" />
              <FullscreenExitOutlined v-else />
            </a-button>
          </a-tooltip>
          <a-tooltip title="复制内容">
            <a-button @click="copyContent">
              <CopyOutlined />
            </a-button>
          </a-tooltip>
          <a-dropdown>
            <a-button>
              <SettingOutlined />
            </a-button>
            <template #overlay>
              <a-menu @click="handleMenuClick">
                <a-menu-item key="fontSize">
                  <span>字体大小</span>
                  <a-slider 
                    v-model:value="fontSize" 
                    :min="12" 
                    :max="20" 
                    style="width: 100px; margin-left: 12px;"
                  />
                </a-menu-item>
                <a-menu-divider />
                <a-menu-item key="lineHeight">
                  <span>行间距</span>
                  <a-slider 
                    v-model:value="lineHeight" 
                    :min="1.2" 
                    :max="2.0" 
                    :step="0.1"
                    style="width: 100px; margin-left: 12px;"
                  />
                </a-menu-item>
                <a-menu-divider />
                <a-menu-item key="wordWrap" @click="toggleWordWrap">
                  <CheckOutlined v-if="wordWrap" />
                  自动换行
                </a-menu-item>
                <a-menu-item key="showLineNumbers" @click="toggleLineNumbers">
                  <CheckOutlined v-if="showLineNumbers" />
                  显示行号
                </a-menu-item>
              </a-menu>
            </template>
          </a-dropdown>
        </a-button-group>
      </div>
    </div>

    <!-- 搜索结果导航 -->
    <div v-if="searchResults.length > 0" class="search-navigation">
      <div class="search-info">
        找到 <strong>{{ searchResults.length }}</strong> 个匹配项
        <span v-if="currentSearchIndex >= 0">
          (第 {{ currentSearchIndex + 1 }} 个)
        </span>
      </div>
      <div class="search-controls">
        <a-button-group size="small">
          <a-button @click="previousMatch" :disabled="searchResults.length === 0">
            <UpOutlined />
          </a-button>
          <a-button @click="nextMatch" :disabled="searchResults.length === 0">
            <DownOutlined />
          </a-button>
        </a-button-group>
        <a-button size="small" @click="clearSearch">
          <CloseOutlined />
        </a-button>
      </div>
    </div>

    <!-- 内容显示区域 -->
    <div 
      class="content-container"
      :class="{ 
        'fullscreen': isFullscreen,
        'word-wrap': wordWrap,
        'show-line-numbers': showLineNumbers
      }"
    >
      <div 
        ref="contentRef"
        class="content-display"
        :style="{
          fontSize: fontSize + 'px',
          lineHeight: lineHeight,
        }"
      >
        <div 
          v-for="(line, index) in processedLines" 
          :key="index"
          class="content-line"
          :class="{ 'highlight-line': line.hasMatch }"
        >
          <span v-if="showLineNumbers" class="line-number">{{ index + 1 }}</span>
          <span class="line-content" v-html="line.content"></span>
        </div>
      </div>
    </div>

    <!-- 快速导航 -->
    <div v-if="contentSections.length > 0" class="content-navigation">
      <div class="nav-header">
        <BookOutlined />
        <span>快速导航</span>
      </div>
      <div class="nav-sections">
        <a-button
          v-for="section in contentSections"
          :key="section.id"
          type="text"
          size="small"
          @click="scrollToSection(section.line)"
          class="nav-section-btn"
        >
          {{ section.title }}
        </a-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, nextTick, onMounted, onUnmounted } from 'vue'
import { message } from 'ant-design-vue'
import {
  FileTextOutlined,
  SearchOutlined,
  FullscreenOutlined,
  FullscreenExitOutlined,
  CopyOutlined,
  SettingOutlined,
  CheckOutlined,
  UpOutlined,
  DownOutlined,
  CloseOutlined,
  BookOutlined
} from '@ant-design/icons-vue'

// Props
interface Props {
  content: string
  title?: string
  enableSummaryToggle?: boolean
  summaryText?: string
}

const props = withDefaults(defineProps<Props>(), {
  title: '内容查看器',
  enableSummaryToggle: false,
  summaryText: ''
})

// Emits
const emit = defineEmits<{
  search: [keyword: string]
  highlight: [texts: string[]]
}>()

// 响应式状态
const contentRef = ref<HTMLElement>()
const searchKeyword = ref('')
const searchResults = ref<Array<{ line: number; start: number; end: number }>>([])
const currentSearchIndex = ref(-1)
const isFullscreen = ref(false)
const fontSize = ref(14)
const lineHeight = ref(1.6)
const wordWrap = ref(true)
const showLineNumbers = ref(false)
const showSummary = ref(false)

// 计算属性
const workingContent = computed(() => (props.enableSummaryToggle && showSummary.value && (props.summaryText || '').length > 0)
  ? (props.summaryText as string)
  : (props.content || ''))

const contentStats = computed(() => {
  const content = workingContent.value || ''
  return {
    characters: content.length,
    lines: content.split('\n').length,
    words: content.split(/\s+/).filter(word => word.length > 0).length
  }
})

const processedLines = computed(() => {
  const lines = (workingContent.value || '').split('\n')
  return lines.map((line, index) => {
    let processedContent = escapeHtml(line)
    let hasMatch = false

    // 应用搜索高亮
    if (searchKeyword.value && searchKeyword.value.trim()) {
      const keyword = searchKeyword.value.trim()
      const regex = new RegExp(`(${escapeRegExp(keyword)})`, 'gi')
      if (regex.test(line)) {
        hasMatch = true
        processedContent = processedContent.replace(regex, '<mark class="search-highlight">$1</mark>')
      }
    }

    return {
      content: processedContent,
      hasMatch
    }
  })
})

const contentSections = computed(() => {
  const lines = (workingContent.value || '').split('\n')
  const sections: Array<{ id: string; title: string; line: number }> = []
  
  lines.forEach((line, index) => {
    // 检测可能的章节标题（以===、第X页、等开头的行）
    if (line.match(/^={3,}|^第\d+页|^[一二三四五六七八九十]+[、．]/)) {
      sections.push({
        id: `section-${index}`,
        title: line.substring(0, 30) + (line.length > 30 ? '...' : ''),
        line: index
      })
    }
  })
  
  return sections
})

// 方法
const handleSearch = (value: string) => {
  if (!value.trim()) {
    clearSearch()
    return
  }
  
  performSearch(value.trim())
  emit('search', value.trim())
}

const handleSearchChange = (e: Event) => {
  const value = (e.target as HTMLInputElement).value
  if (!value.trim()) {
    clearSearch()
  }
}

const performSearch = (keyword: string) => {
  const lines = (props.content || '').split('\n')
  const results: Array<{ line: number; start: number; end: number }> = []
  
  lines.forEach((line, lineIndex) => {
    const regex = new RegExp(escapeRegExp(keyword), 'gi')
    let match
    while ((match = regex.exec(line)) !== null) {
      results.push({
        line: lineIndex,
        start: match.index,
        end: match.index + match[0].length
      })
    }
  })
  
  searchResults.value = results
  currentSearchIndex.value = results.length > 0 ? 0 : -1
  
  if (results.length > 0) {
    scrollToMatch(0)
  }
}

const nextMatch = () => {
  if (searchResults.value.length === 0) return
  currentSearchIndex.value = (currentSearchIndex.value + 1) % searchResults.value.length
  scrollToMatch(currentSearchIndex.value)
}

const previousMatch = () => {
  if (searchResults.value.length === 0) return
  currentSearchIndex.value = currentSearchIndex.value <= 0 
    ? searchResults.value.length - 1 
    : currentSearchIndex.value - 1
  scrollToMatch(currentSearchIndex.value)
}

const scrollToMatch = (index: number) => {
  if (!contentRef.value || index < 0 || index >= searchResults.value.length) return
  
  const match = searchResults.value[index]
  const lineElement = contentRef.value.children[match.line] as HTMLElement
  if (lineElement) {
    lineElement.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }
}

const clearSearch = () => {
  searchKeyword.value = ''
  searchResults.value = []
  currentSearchIndex.value = -1
}

const toggleFullscreen = () => {
  isFullscreen.value = !isFullscreen.value
  if (isFullscreen.value) {
    document.body.style.overflow = 'hidden'
  } else {
    document.body.style.overflow = ''
  }
}

const copyContent = async () => {
  try {
    await navigator.clipboard.writeText(workingContent.value || '')
    message.success('内容已复制到剪贴板')
  } catch (error) {
    message.error('复制失败')
  }
}

const toggleWordWrap = () => {
  wordWrap.value = !wordWrap.value
}

const toggleLineNumbers = () => {
  showLineNumbers.value = !showLineNumbers.value
}

const scrollToSection = (lineNumber: number) => {
  if (!contentRef.value) return
  
  const lineElement = contentRef.value.children[lineNumber] as HTMLElement
  if (lineElement) {
    lineElement.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }
}

const handleMenuClick = () => {
  // 菜单点击处理（如果需要）
}

// 工具函数
const escapeHtml = (text: string) => {
  const div = document.createElement('div')
  div.textContent = text
  return div.innerHTML
}

const escapeRegExp = (string: string) => {
  return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

// 生命周期
onMounted(() => {
  // 键盘快捷键
  const handleKeydown = (e: KeyboardEvent) => {
    if (e.ctrlKey || e.metaKey) {
      switch (e.key) {
        case 'f':
          e.preventDefault()
          // 聚焦搜索框
          break
        case 'c':
          if (window.getSelection()?.toString()) return
          e.preventDefault()
          copyContent()
          break
      }
    }
    
    if (e.key === 'Escape' && isFullscreen.value) {
      toggleFullscreen()
    }
  }
  
  document.addEventListener('keydown', handleKeydown)
  
  onUnmounted(() => {
    document.removeEventListener('keydown', handleKeydown)
    if (isFullscreen.value) {
      document.body.style.overflow = ''
    }
  })
})

// 当切换到不同的文书/摘要模式时，重置滚动与搜索状态
watch(
  () => [props.content, props.summaryText, showSummary.value],
  async () => {
    await nextTick()
    if (contentRef.value) contentRef.value.scrollTop = 0
    clearSearch()
  }
)
</script>

<style scoped>
.enhanced-content-viewer {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: white;
}

.viewer-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid #e5e7eb;
  background: #f8fafc;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.viewer-title {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: #111827;
}

.title-icon {
  color: #3b82f6;
}

.content-stats {
  display: flex;
  gap: 8px;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.search-navigation {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 20px;
  background: #fef3c7;
  border-bottom: 1px solid #f59e0b;
}

.search-info {
  font-size: 14px;
  color: #92400e;
}

.search-controls {
  display: flex;
  align-items: center;
  gap: 8px;
}

.content-container {
  flex: 1;
  overflow: auto;
  position: relative;
}

.content-container.fullscreen {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 1000;
  background: white;
}

.content-display {
  padding: 20px;
  font-family: 'SF Mono', 'Monaco', 'Inconsolata', 'Roboto Mono', monospace;
  color: #374151;
  background: white;
}

.content-line {
  display: flex;
  min-height: 1.5em;
  transition: background-color 0.2s ease;
}

.content-line.highlight-line {
  background-color: #fef3c7;
}

.line-number {
  display: inline-block;
  width: 60px;
  text-align: right;
  padding-right: 12px;
  color: #9ca3af;
  font-size: 12px;
  user-select: none;
  border-right: 1px solid #e5e7eb;
  margin-right: 12px;
}

.line-content {
  flex: 1;
  white-space: pre;
}

.word-wrap .line-content {
  white-space: pre-wrap;
  word-break: break-word;
}

.content-navigation {
  border-top: 1px solid #e5e7eb;
  background: #f8fafc;
  padding: 12px 20px;
}

.nav-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
  font-size: 14px;
  font-weight: 600;
  color: #374151;
}

.nav-sections {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.nav-section-btn {
  font-size: 12px;
  height: auto;
  padding: 4px 8px;
}

/* 搜索高亮样式 */
:deep(.search-highlight) {
  background-color: #fbbf24;
  color: #92400e;
  padding: 1px 2px;
  border-radius: 2px;
  font-weight: 600;
}

/* 滚动条样式 */
.content-container::-webkit-scrollbar {
  width: 8px;
  height: 8px;
}

.content-container::-webkit-scrollbar-track {
  background: #f1f5f9;
}

.content-container::-webkit-scrollbar-thumb {
  background: #cbd5e1;
  border-radius: 4px;
}

.content-container::-webkit-scrollbar-thumb:hover {
  background: #94a3b8;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .viewer-header {
    flex-direction: column;
    gap: 12px;
    align-items: stretch;
  }
  
  .header-actions {
    justify-content: space-between;
  }
  
  .search-navigation {
    flex-direction: column;
    gap: 8px;
    align-items: stretch;
  }
  
  .content-display {
    padding: 12px;
    font-size: 13px;
  }
}
</style>
