<template>
  <div class="document-editor">
    <!-- 编辑器工具栏 -->
    <div class="editor-toolbar">
      <div class="editor-toolbar-left">
        <a-button-group size="small">
          <a-button @click="undo" :disabled="!canUndo" title="撤销 (Ctrl+Z)">
            <UndoOutlined />
          </a-button>
          <a-button @click="redo" :disabled="!canRedo" title="重做 (Ctrl+Y)">
            <RedoOutlined />
          </a-button>
        </a-button-group>

        <a-divider type="vertical" />

        <a-button-group size="small">
          <a-button @click="openFindReplace" title="查找替换 (Ctrl+H)">
            <SearchOutlined />
            查找替换
          </a-button>
        </a-button-group>
      </div>

      <div class="editor-toolbar-right">
        <span class="char-count">
          字符数: {{ characterCount }} / 行数: {{ lineCount }}
        </span>
        
        <a-button 
          size="small" 
          @click="toggleAutoSave"
          :type="autoSave ? 'primary' : 'default'"
          title="自动保存"
        >
          <CloudSyncOutlined />
          {{ autoSave ? '自动保存' : '手动保存' }}
        </a-button>
      </div>
    </div>

    <!-- 查找替换面板 -->
    <div v-if="showFindReplace" class="find-replace-panel">
      <div class="find-replace-row">
        <a-input
          v-model:value="findText"
          placeholder="查找..."
          size="small"
          style="width: 200px"
          @pressEnter="findNext"
        />
        <a-button-group size="small">
          <a-button @click="findPrev" :disabled="!findText">上一个</a-button>
          <a-button @click="findNext" :disabled="!findText">下一个</a-button>
        </a-button-group>
        <span class="find-count" v-if="findMatches > 0">
          {{ currentFindIndex + 1 }}/{{ findMatches }}
        </span>
      </div>
      
      <div class="find-replace-row">
        <a-input
          v-model:value="replaceText"
          placeholder="替换为..."
          size="small"
          style="width: 200px"
          @pressEnter="replaceNext"
        />
        <a-button-group size="small">
          <a-button @click="replaceNext" :disabled="!findText">替换</a-button>
          <a-button @click="replaceAll" :disabled="!findText">全部替换</a-button>
        </a-button-group>
        <a-button size="small" @click="closeFindReplace">
          <CloseOutlined />
        </a-button>
      </div>
    </div>

    <!-- 文本编辑器 -->
    <div class="editor-container">
      <a-textarea
        ref="editorRef"
        v-model:value="editorContent"
        :auto-size="{ minRows: 20, maxRows: 50 }"
        placeholder="请输入文档内容..."
        class="document-textarea"
        @input="handleInput"
        @keydown="handleKeydown"
      />
    </div>

    <!-- 状态栏 -->
    <div class="editor-status">
      <div class="status-left">
        <span v-if="isDirty" class="dirty-indicator">● 未保存</span>
        <span v-if="lastSaved" class="last-saved">
          最后保存: {{ formatTime(lastSaved) }}
        </span>
      </div>
      
      <div class="status-right">
        <span class="cursor-position">
          行 {{ cursorLine }}, 列 {{ cursorColumn }}
        </span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, nextTick, onMounted, onUnmounted } from 'vue'
import { message } from 'ant-design-vue'
import {
  UndoOutlined,
  RedoOutlined,
  SearchOutlined,
  CloseOutlined,
  CloudSyncOutlined
} from '@ant-design/icons-vue'

interface Props {
  content: string
  autoSave?: boolean
  saveInterval?: number // 自动保存间隔（毫秒）
}

const props = withDefaults(defineProps<Props>(), {
  content: '',
  autoSave: true,
  saveInterval: 30000 // 30秒
})

const emit = defineEmits<{
  'update:content': [value: string]
  'save': [content: string]
  'change': [content: string]
}>()

// 编辑器引用
const editorRef = ref<any>(null)

// 编辑器状态
const editorContent = ref('')
const isDirty = ref(false)
const lastSaved = ref<Date | null>(null)

// 撤销重做
const history = ref<string[]>([])
const historyIndex = ref(-1)
const maxHistorySize = 100

// 查找替换
const showFindReplace = ref(false)
const findText = ref('')
const replaceText = ref('')
const findMatches = ref(0)
const currentFindIndex = ref(0)

// 光标位置
const cursorLine = ref(1)
const cursorColumn = ref(1)

// 自动保存
const autoSave = ref(props.autoSave)
let autoSaveTimer: NodeJS.Timeout | null = null

// 计算属性
const characterCount = computed(() => editorContent.value.length)
const lineCount = computed(() => editorContent.value.split('\n').length)
const canUndo = computed(() => historyIndex.value > 0)
const canRedo = computed(() => historyIndex.value < history.value.length - 1)

// 初始化
onMounted(() => {
  editorContent.value = props.content
  addToHistory(props.content)
  
  if (autoSave.value) {
    startAutoSave()
  }
  
  // 监听光标位置变化
  nextTick(() => {
    if (editorRef.value?.resizableTextArea?.textArea) {
      const textarea = editorRef.value.resizableTextArea.textArea
      textarea.addEventListener('selectionchange', updateCursorPosition)
      textarea.addEventListener('keyup', updateCursorPosition)
      textarea.addEventListener('click', updateCursorPosition)
    }
  })
})

onUnmounted(() => {
  if (autoSaveTimer) {
    clearInterval(autoSaveTimer)
  }
})

// 监听内容变化
watch(() => props.content, (newContent) => {
  if (newContent !== editorContent.value) {
    editorContent.value = newContent
    addToHistory(newContent)
    isDirty.value = false
  }
})

// 处理输入
const handleInput = () => {
  isDirty.value = true
  emit('update:content', editorContent.value)
  emit('change', editorContent.value)
}

// 添加到历史记录
const addToHistory = (content: string) => {
  // 移除当前位置之后的历史记录
  history.value = history.value.slice(0, historyIndex.value + 1)
  
  // 添加新记录
  history.value.push(content)
  historyIndex.value = history.value.length - 1
  
  // 限制历史记录大小
  if (history.value.length > maxHistorySize) {
    history.value = history.value.slice(-maxHistorySize)
    historyIndex.value = history.value.length - 1
  }
}

// 撤销
const undo = () => {
  if (canUndo.value) {
    historyIndex.value--
    editorContent.value = history.value[historyIndex.value]
    emit('update:content', editorContent.value)
    isDirty.value = true
  }
}

// 重做
const redo = () => {
  if (canRedo.value) {
    historyIndex.value++
    editorContent.value = history.value[historyIndex.value]
    emit('update:content', editorContent.value)
    isDirty.value = true
  }
}

// 保存
const save = () => {
  emit('save', editorContent.value)
  isDirty.value = false
  lastSaved.value = new Date()
  addToHistory(editorContent.value)
}

// 自动保存
const startAutoSave = () => {
  if (autoSaveTimer) {
    clearInterval(autoSaveTimer)
  }
  
  autoSaveTimer = setInterval(() => {
    if (isDirty.value) {
      save()
      message.success('自动保存成功', 1)
    }
  }, props.saveInterval)
}

const toggleAutoSave = () => {
  autoSave.value = !autoSave.value
  
  if (autoSave.value) {
    startAutoSave()
    message.success('已开启自动保存')
  } else {
    if (autoSaveTimer) {
      clearInterval(autoSaveTimer)
      autoSaveTimer = null
    }
    message.info('已关闭自动保存')
  }
}

// 查找替换功能
const openFindReplace = () => {
  showFindReplace.value = true
  nextTick(() => {
    const findInput = document.querySelector('.find-replace-panel .ant-input') as HTMLInputElement
    findInput?.focus()
  })
}

const closeFindReplace = () => {
  showFindReplace.value = false
  findText.value = ''
  replaceText.value = ''
  findMatches.value = 0
  currentFindIndex.value = 0
}

const findNext = () => {
  // 简单的查找实现
  if (!findText.value) return
  
  const content = editorContent.value
  const regex = new RegExp(escapeRegExp(findText.value), 'gi')
  const matches = Array.from(content.matchAll(regex))
  
  findMatches.value = matches.length
  
  if (matches.length > 0) {
    currentFindIndex.value = (currentFindIndex.value + 1) % matches.length
    const match = matches[currentFindIndex.value]
    
    // 选中匹配的文本
    if (editorRef.value?.resizableTextArea?.textArea) {
      const textarea = editorRef.value.resizableTextArea.textArea
      textarea.focus()
      textarea.setSelectionRange(match.index, match.index + match[0].length)
    }
  } else {
    message.info('未找到匹配项')
  }
}

const findPrev = () => {
  if (!findText.value || findMatches.value === 0) return
  
  currentFindIndex.value = currentFindIndex.value === 0 
    ? findMatches.value - 1 
    : currentFindIndex.value - 1
  
  findNext()
}

const replaceNext = () => {
  if (!findText.value) return
  
  const content = editorContent.value
  const newContent = content.replace(new RegExp(escapeRegExp(findText.value), 'i'), replaceText.value)
  
  if (newContent !== content) {
    editorContent.value = newContent
    handleInput()
    message.success('替换成功')
  }
}

const replaceAll = () => {
  if (!findText.value) return
  
  const content = editorContent.value
  const regex = new RegExp(escapeRegExp(findText.value), 'gi')
  const newContent = content.replace(regex, replaceText.value)
  
  if (newContent !== content) {
    const count = (content.match(regex) || []).length
    editorContent.value = newContent
    handleInput()
    message.success(`已替换 ${count} 处`)
  } else {
    message.info('未找到匹配项')
  }
}

// 更新光标位置
const updateCursorPosition = () => {
  if (editorRef.value?.resizableTextArea?.textArea) {
    const textarea = editorRef.value.resizableTextArea.textArea
    const cursorPos = textarea.selectionStart
    const textBeforeCursor = editorContent.value.substring(0, cursorPos)
    const lines = textBeforeCursor.split('\n')
    
    cursorLine.value = lines.length
    cursorColumn.value = lines[lines.length - 1].length + 1
  }
}

// 键盘事件处理
const handleKeydown = (e: KeyboardEvent) => {
  if (e.ctrlKey || e.metaKey) {
    if (e.key === 'z' && !e.shiftKey) {
      e.preventDefault()
      undo()
    } else if ((e.key === 'y') || (e.key === 'z' && e.shiftKey)) {
      e.preventDefault()
      redo()
    } else if (e.key === 'h') {
      e.preventDefault()
      openFindReplace()
    } else if (e.key === 's') {
      e.preventDefault()
      save()
    }
  }
  
  // 记录历史（在某些操作后）
  if (e.key === 'Enter' || e.key === ' ') {
    setTimeout(() => {
      addToHistory(editorContent.value)
    }, 100)
  }
}

// 格式化时间
const formatTime = (date: Date) => {
  return date.toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  })
}

// 转义正则表达式
const escapeRegExp = (string: string) => {
  return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

// 暴露方法给父组件
defineExpose({
  save,
  undo,
  redo,
  focus: () => editorRef.value?.focus()
})
</script>

<style scoped>
.document-editor {
  display: flex;
  flex-direction: column;
  height: 100%;
  border: 1px solid #d9d9d9;
  border-radius: 6px;
  overflow: hidden;
}

.editor-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  background: #fafafa;
  border-bottom: 1px solid #d9d9d9;
}

.editor-toolbar-left,
.editor-toolbar-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.char-count {
  font-size: 12px;
  color: #666;
  margin-right: 8px;
}

.find-replace-panel {
  padding: 8px 12px;
  background: #f5f5f5;
  border-bottom: 1px solid #d9d9d9;
}

.find-replace-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}

.find-replace-row:last-child {
  margin-bottom: 0;
}

.find-count {
  font-size: 12px;
  color: #666;
  margin-left: 8px;
}

.editor-container {
  flex: 1;
  padding: 12px;
  overflow: auto;
}

.document-textarea {
  font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
  font-size: 14px;
  line-height: 1.6;
  border: none !important;
  box-shadow: none !important;
  resize: none;
}

.document-textarea:focus {
  border: none !important;
  box-shadow: none !important;
}

.editor-status {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 4px 12px;
  background: #fafafa;
  border-top: 1px solid #d9d9d9;
  font-size: 12px;
  color: #666;
}

.dirty-indicator {
  color: #ff4d4f;
  font-weight: bold;
}

.last-saved {
  margin-left: 8px;
  color: #52c41a;
}

.cursor-position {
  font-family: monospace;
}
</style>
