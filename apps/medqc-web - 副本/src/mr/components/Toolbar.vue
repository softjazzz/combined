<template>
  <div class="toolbar">
    <!-- 左侧工具 -->
    <div class="toolbar-section">
      <a-button-group size="small">
        <a-button
          :type="summary ? 'primary' : 'default'"
          title="切换摘要/全文"
          @click="toggleSummary"
        >
          <FileTextOutlined />
          {{ summary ? '摘要' : '全文' }}
        </a-button>
      </a-button-group>

      <a-divider type="vertical" />

      <!-- 文档管理功能 -->
      <a-button-group
        v-if="!isEditing"
        size="small"
      >
        <a-button
          title="新增文档"
          @click="createDocument"
        >
          <PlusOutlined />
          新增
        </a-button>
        <a-button
          title="编辑文档内容"
          :disabled="!canEdit"
          @click="startEdit"
        >
          <EditOutlined />
          编辑
        </a-button>
        <a-button
          title="删除文档"
          :disabled="!canDelete"
          danger
          @click="deleteDocument"
        >
          <DeleteOutlined />
          删除
        </a-button>
      </a-button-group>

      <!-- 编辑模式下的操作 -->
      <a-button-group
        v-else
        size="small"
      >
        <a-button
          type="primary"
          title="保存修改 (Ctrl+S)"
          :loading="saving"
          @click="saveEdit"
        >
          <SaveOutlined />
          保存
        </a-button>
        <a-button
          title="取消编辑 (Esc)"
          @click="cancelEdit"
        >
          <CloseOutlined />
          取消
        </a-button>
      </a-button-group>
    </div>

    <!-- 中间工具 -->
    <div class="toolbar-section toolbar-center">
      <a-button-group size="small">
        <a-button
          title="减小字号 (Ctrl+-)"
          @click="fontDown"
        >
          <span class="font-btn">A-</span>
        </a-button>
        <a-button
          title="增大字号 (Ctrl++)"
          @click="fontUp"
        >
          <span class="font-btn">A+</span>
        </a-button>
      </a-button-group>

      <a-divider type="vertical" />

      <!-- 搜索框 -->
      <a-input-search
        v-model:value="searchText"
        placeholder="文内搜索..."
        style="width: 200px"
        size="small"
        allow-clear
        @search="handleSearch"
        @press-enter="handleSearch"
      >
        <template #enterButton>
          <SearchOutlined />
        </template>
      </a-input-search>

      <!-- 搜索导航 -->
      <div
        v-if="searchResults.length > 0"
        class="search-nav"
      >
        <span class="search-info"> {{ currentSearchIndex + 1 }}/{{ searchResults.length }} </span>
        <a-button-group size="small">
          <a-button
            :disabled="searchResults.length === 0"
            @click="prevSearch"
          >
            <UpOutlined />
          </a-button>
          <a-button
            :disabled="searchResults.length === 0"
            @click="nextSearch"
          >
            <DownOutlined />
          </a-button>
        </a-button-group>
      </div>
    </div>

    <!-- 右侧工具 -->
    <div class="toolbar-section">
      <a-button-group size="small">
        <a-button
          title="复制链接"
          @click="copyLink"
        >
          <LinkOutlined />
        </a-button>
        <a-button
          title="全屏"
          @click="toggleFullscreen"
        >
          <FullscreenOutlined v-if="!isFullscreen" />
          <FullscreenExitOutlined v-else />
        </a-button>
        <a-button
          title="打印"
          @click="print"
        >
          <PrinterOutlined />
        </a-button>
      </a-button-group>

      <a-divider type="vertical" />

      <a-button
        size="small"
        title="对比视图（开发中）"
        disabled
        @click="openCompare"
      >
        <SwapOutlined />
        对比
      </a-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, nextTick } from 'vue'
import { message } from 'ant-design-vue'
import {
  FileTextOutlined,
  SearchOutlined,
  UpOutlined,
  DownOutlined,
  LinkOutlined,
  FullscreenOutlined,
  FullscreenExitOutlined,
  PrinterOutlined,
  SwapOutlined,
  EditOutlined,
  SaveOutlined,
  CloseOutlined,
  PlusOutlined,
  DeleteOutlined,
} from '@ant-design/icons-vue'

defineOptions({ name: 'MrToolbar' })

interface Props {
  summary?: boolean
  isEditing?: boolean
  canEdit?: boolean
  canDelete?: boolean
  saving?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  summary: false,
  isEditing: false,
  canEdit: true,
  canDelete: true,
  saving: false,
})

const emit = defineEmits<{
  'update:summary': [value: boolean]
  'font-up': []
  'font-down': []
  'toggle-summary': []
  search: [keyword: string, results: Element[]]
  'copy-link': []
  fullscreen: []
  print: []
  'open-compare': []
  'start-edit': []
  'save-edit': []
  'cancel-edit': []
  'create-document': []
  'delete-document': []
}>()

// 响应式状态
const searchText = ref('')
const searchResults = ref<Element[]>([])
const currentSearchIndex = ref(0)
const isFullscreen = ref(false)

// 切换摘要
const toggleSummary = () => {
  const newValue = !props.summary
  emit('update:summary', newValue)
  emit('toggle-summary')
  localStorage.setItem('mr_summary', String(newValue))
}

// 字号调整
const fontUp = () => {
  emit('font-up')
}

const fontDown = () => {
  emit('font-down')
}

// 文内搜索
const handleSearch = () => {
  if (!searchText.value.trim()) {
    clearSearch()
    return
  }

  const keyword = searchText.value.trim()
  const contentEl = document.querySelector('.layout-content-main')

  if (!contentEl) return

  // 清除之前的高亮
  clearHighlights(contentEl)

  // 查找匹配项
  const results = findAndHighlight(contentEl, keyword)
  searchResults.value = results
  currentSearchIndex.value = 0

  if (results.length > 0) {
    scrollToResult(0)
    message.success(`找到 ${results.length} 个匹配项`)
  } else {
    message.info('未找到匹配内容')
  }

  emit('search', keyword, results)
}

// 查找并高亮
const findAndHighlight = (container: Element, keyword: string): Element[] => {
  const results: Element[] = []
  const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT, null)

  const textNodes: Text[] = []
  let node: Node | null

  while ((node = walker.nextNode()) !== null) {
    textNodes.push(node as Text)
  }

  const regex = new RegExp(escapeRegExp(keyword), 'gi')

  textNodes.forEach((textNode) => {
    const text = textNode.textContent || ''
    if (regex.test(text)) {
      const parent = textNode.parentElement
      if (parent && !parent.closest('.toolbar')) {
        const highlightedHTML = text.replace(
          regex,
          (match) => `<mark class="search-highlight" data-search-result>${match}</mark>`,
        )

        const wrapper = document.createElement('span')
        wrapper.innerHTML = highlightedHTML
        parent.replaceChild(wrapper, textNode)

        const marks = wrapper.querySelectorAll('.search-highlight')
        results.push(...Array.from(marks))
      }
    }
  })

  return results
}

// 清除高亮
const clearHighlights = (container: Element) => {
  const highlights = container.querySelectorAll('.search-highlight')
  highlights.forEach((highlight) => {
    const parent = highlight.parentNode
    if (parent) {
      parent.replaceChild(document.createTextNode(highlight.textContent || ''), highlight)
      parent.normalize()
    }
  })
}

// 清除搜索
const clearSearch = () => {
  const contentEl = document.querySelector('.layout-content-main')
  if (contentEl) {
    clearHighlights(contentEl)
  }
  searchResults.value = []
  currentSearchIndex.value = 0
}

// 搜索导航
const scrollToResult = (index: number) => {
  if (index >= 0 && index < searchResults.value.length) {
    const element = searchResults.value[index]

    // 移除之前的当前高亮
    searchResults.value.forEach((el) => el.classList.remove('current-result'))

    // 添加当前高亮
    element.classList.add('current-result')

    // 滚动到视图
    element.scrollIntoView({
      behavior: 'smooth',
      block: 'center',
    })
  }
}

const nextSearch = () => {
  if (searchResults.value.length === 0) return
  currentSearchIndex.value = (currentSearchIndex.value + 1) % searchResults.value.length
  scrollToResult(currentSearchIndex.value)
}

const prevSearch = () => {
  if (searchResults.value.length === 0) return
  currentSearchIndex.value =
    currentSearchIndex.value === 0 ? searchResults.value.length - 1 : currentSearchIndex.value - 1
  scrollToResult(currentSearchIndex.value)
}

// 复制链接
const copyLink = () => {
  navigator.clipboard
    .writeText(window.location.href)
    .then(() => {
      message.success('链接已复制到剪贴板')
      emit('copy-link')
    })
    .catch(() => {
      message.error('复制失败')
    })
}

// 全屏切换
const toggleFullscreen = () => {
  const contentEl = document.querySelector('.layout-content-main')
  if (!contentEl) return

  if (!isFullscreen.value) {
    contentEl.requestFullscreen?.()
    isFullscreen.value = true
  } else {
    document.exitFullscreen?.()
    isFullscreen.value = false
  }

  emit('fullscreen')
}

// 监听全屏状态变化
document.addEventListener('fullscreenchange', () => {
  isFullscreen.value = !!document.fullscreenElement
})

// 打印
const print = () => {
  window.print()
  emit('print')
}

// 对比视图
const openCompare = () => {
  emit('open-compare')
}

// 编辑功能
const startEdit = () => {
  emit('start-edit')
}

const saveEdit = () => {
  emit('save-edit')
}

const cancelEdit = () => {
  emit('cancel-edit')
}

// 文档管理功能
const createDocument = () => {
  emit('create-document')
}

const deleteDocument = () => {
  emit('delete-document')
}

// 转义正则表达式
const escapeRegExp = (string: string) => {
  return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

// 键盘快捷键
document.addEventListener('keydown', (e) => {
  if (e.ctrlKey || e.metaKey) {
    if (e.key === '=' || e.key === '+') {
      e.preventDefault()
      fontUp()
    } else if (e.key === '-') {
      e.preventDefault()
      fontDown()
    } else if (e.key === 'f') {
      e.preventDefault()
      nextTick(() => {
        const searchInput = document.querySelector('.toolbar .ant-input') as HTMLInputElement
        searchInput?.focus()
      })
    } else if (e.key === 's' && props.isEditing) {
      e.preventDefault()
      saveEdit()
    }
  } else if (e.key === 'Escape' && props.isEditing) {
    e.preventDefault()
    cancelEdit()
  }
})
</script>

<style scoped>
.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  width: 100%;
}

.toolbar-section {
  display: flex;
  align-items: center;
  gap: 8px;
}

.toolbar-center {
  flex: 1;
  justify-content: center;
}

.font-btn {
  font-weight: bold;
  font-size: 12px;
}

.search-nav {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-left: 8px;
}

.search-info {
  font-size: 12px;
  color: #666;
  white-space: nowrap;
}

/* 搜索高亮样式 */
:deep(.search-highlight) {
  background: #fff566;
  padding: 1px 2px;
  border-radius: 2px;
}

:deep(.search-highlight.current-result) {
  background: #ff7875;
  color: white;
}

/* 响应式 */
@media (max-width: 768px) {
  .toolbar {
    flex-wrap: wrap;
    gap: 8px;
  }

  .toolbar-center {
    order: 3;
    width: 100%;
    justify-content: flex-start;
  }

  .toolbar-center .ant-input-search {
    width: 100% !important;
  }
}
</style>
