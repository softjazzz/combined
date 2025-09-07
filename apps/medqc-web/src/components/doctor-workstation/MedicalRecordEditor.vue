<template>
  <!-- 医疗风格记录编辑器 -->
  <div class="bg-white rounded-2xl shadow-lg border border-gray-200 overflow-hidden">
    <!-- 医疗风格工具栏 -->
    <div class="bg-gradient-to-r from-blue-50 to-green-50 px-6 py-4 border-b border-gray-200">
      <div class="flex items-center justify-between">
        <!-- 左侧工具组 -->
        <div class="flex items-center space-x-4">
          <!-- 格式化工具组 -->
          <div class="flex items-center space-x-1 bg-white rounded-lg p-1 shadow-sm">
            <button
              :class="[
                'p-2 rounded-md transition-all duration-200 hover:scale-105',
                isFormatActive('bold')
                  ? 'bg-blue-500 text-white shadow-md'
                  : 'text-gray-600 hover:bg-blue-50 hover:text-blue-600'
              ]"
              @click="toggleFormat('bold')"
              title="粗体"
            >
              <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                <path d="M3 4a1 1 0 011-1h4.5a3.5 3.5 0 013.5 3.5v.5a3 3 0 01-3 3H4v3a1 1 0 11-2 0V4zm2 1v4h3.5a1.5 1.5 0 001.5-1.5V6.5A1.5 1.5 0 008.5 5H5z"/>
              </svg>
            </button>
            <button
              :class="[
                'p-2 rounded-md transition-all duration-200 hover:scale-105',
                isFormatActive('italic')
                  ? 'bg-blue-500 text-white shadow-md'
                  : 'text-gray-600 hover:bg-blue-50 hover:text-blue-600'
              ]"
              @click="toggleFormat('italic')"
              title="斜体"
            >
              <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                <path d="M8 3a1 1 0 011-1h2a1 1 0 110 2h-.5l-2 8H9a1 1 0 110 2H7a1 1 0 110-2h.5l2-8H9a1 1 0 01-1-1z"/>
              </svg>
            </button>
            <button
              :class="[
                'p-2 rounded-md transition-all duration-200 hover:scale-105',
                isFormatActive('underline')
                  ? 'bg-blue-500 text-white shadow-md'
                  : 'text-gray-600 hover:bg-blue-50 hover:text-blue-600'
              ]"
              @click="toggleFormat('underline')"
              title="下划线"
            >
              <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                <path d="M4 18a1 1 0 011-1h10a1 1 0 110 2H5a1 1 0 01-1-1zM6 3a1 1 0 011-1h6a1 1 0 110 2H7v6a3 3 0 106 0V4h-1a1 1 0 110-2h2a1 1 0 011 1v7a5 5 0 11-10 0V3z"/>
              </svg>
            </button>
          </div>

          <!-- 分隔线 -->
          <div class="w-px h-8 bg-gray-300"></div>

          <!-- 医疗模板工具组 -->
          <div class="flex items-center space-x-2">
            <button
              @click="insertTemplate('chief_complaint')"
              title="插入主诉模板"
              class="bg-green-500 hover:bg-green-600 text-white px-3 py-2 rounded-lg text-sm font-medium transition-all duration-200 hover:scale-105 shadow-sm"
            >
              主诉
            </button>
            <button
              @click="insertTemplate('present_illness')"
              title="插入现病史模板"
              class="bg-blue-500 hover:bg-blue-600 text-white px-3 py-2 rounded-lg text-sm font-medium transition-all duration-200 hover:scale-105 shadow-sm"
            >
              现病史
            </button>
            <button
              @click="insertTemplate('physical_exam')"
              title="插入体格检查模板"
              class="bg-purple-500 hover:bg-purple-600 text-white px-3 py-2 rounded-lg text-sm font-medium transition-all duration-200 hover:scale-105 shadow-sm"
            >
              体检
            </button>
            <button
              @click="insertTemplate('diagnosis')"
              title="插入诊断模板"
              class="bg-orange-500 hover:bg-orange-600 text-white px-3 py-2 rounded-lg text-sm font-medium transition-all duration-200 hover:scale-105 shadow-sm"
            >
              诊断
            </button>
          </div>
        </div>

        <!-- 右侧工具组 -->
        <div class="flex items-center space-x-2">
          <button
            @click="insertCurrentTime"
            title="插入当前时间"
            class="bg-gray-500 hover:bg-gray-600 text-white p-2 rounded-lg transition-all duration-200 hover:scale-105 shadow-sm"
          >
            <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
              <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm1-12a1 1 0 10-2 0v4a1 1 0 00.293.707l2.828 2.829a1 1 0 101.415-1.415L11 9.586V6z" clip-rule="evenodd" />
            </svg>
          </button>
          <button
            @click="showSymbolPicker = !showSymbolPicker"
            title="特殊符号"
            :class="[
              'p-2 rounded-lg transition-all duration-200 hover:scale-105 shadow-sm',
              showSymbolPicker
                ? 'bg-teal-500 text-white'
                : 'bg-teal-500 hover:bg-teal-600 text-white'
            ]"
          >
            <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
              <path fill-rule="evenodd" d="M10 3a1 1 0 011 1v5h5a1 1 0 110 2h-5v5a1 1 0 11-2 0v-5H4a1 1 0 110-2h5V4a1 1 0 011-1z" clip-rule="evenodd" />
            </svg>
          </button>
        </div>
      </div>
    </div>

    <!-- 医疗风格特殊符号选择器 -->
    <div v-if="showSymbolPicker" class="bg-white border-b border-gray-200 p-4">
      <div class="space-y-4">
        <!-- 常用符号 -->
        <div>
          <div class="flex items-center space-x-2 mb-3">
            <div class="w-2 h-2 bg-blue-500 rounded-full"></div>
            <span class="text-sm font-semibold text-gray-700">常用符号</span>
          </div>
          <div class="flex flex-wrap gap-2">
            <button
              v-for="symbol in commonSymbols"
              :key="symbol"
              @click="insertSymbol(symbol)"
              class="bg-blue-50 hover:bg-blue-100 text-blue-700 px-3 py-2 rounded-lg text-sm font-medium transition-all duration-200 hover:scale-105 border border-blue-200"
            >
              {{ symbol }}
            </button>
          </div>
        </div>

        <!-- 医学符号 -->
        <div>
          <div class="flex items-center space-x-2 mb-3">
            <div class="w-2 h-2 bg-green-500 rounded-full"></div>
            <span class="text-sm font-semibold text-gray-700">医学符号</span>
          </div>
          <div class="flex flex-wrap gap-2">
            <button
              v-for="symbol in medicalSymbols"
              :key="symbol"
              @click="insertSymbol(symbol)"
              class="bg-green-50 hover:bg-green-100 text-green-700 px-3 py-2 rounded-lg text-sm font-medium transition-all duration-200 hover:scale-105 border border-green-200"
            >
              {{ symbol }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- 医疗风格编辑器主体 -->
    <div class="relative">
      <div
        ref="editorRef"
        :class="[
          'min-h-96 p-6 text-gray-800 leading-relaxed focus:outline-none',
          'prose prose-lg max-w-none',
          isFocused ? 'bg-blue-50/30' : 'bg-white',
          readonly ? 'cursor-not-allowed bg-gray-50' : 'cursor-text'
        ]"
        contenteditable="true"
        :placeholder="placeholder"
        @input="onInput"
        @keydown="onKeydown"
        @paste="onPaste"
        @focus="onFocus"
        @blur="onBlur"
        v-html="formattedContent"
      ></div>

      <!-- 占位符显示 -->
      <div
        v-if="!modelValue && !isFocused"
        class="absolute top-6 left-6 text-gray-400 pointer-events-none select-none"
      >
        {{ placeholder || '请输入医疗记录内容...' }}
      </div>

      <!-- 保存状态指示器 -->
      <div
        v-if="saveStatus !== 'idle'"
        class="absolute top-4 right-4 flex items-center space-x-2 bg-white rounded-lg shadow-md px-3 py-2 border"
      >
        <div
          v-if="saveStatus === 'saving'"
          class="w-4 h-4 border-2 border-blue-500 border-t-transparent rounded-full animate-spin"
        ></div>
        <svg
          v-else-if="saveStatus === 'saved'"
          class="w-4 h-4 text-green-500"
          fill="currentColor"
          viewBox="0 0 20 20"
        >
          <path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd" />
        </svg>
        <svg
          v-else-if="saveStatus === 'error'"
          class="w-4 h-4 text-red-500"
          fill="currentColor"
          viewBox="0 0 20 20"
        >
          <path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clip-rule="evenodd" />
        </svg>
        <span
          class="text-sm font-medium"
          :class="{
            'text-blue-600': saveStatus === 'saving',
            'text-green-600': saveStatus === 'saved',
            'text-red-600': saveStatus === 'error'
          }"
        >
          {{ getSaveStatusText() }}
        </span>
      </div>
    </div>

    <!-- 医疗风格状态栏 -->
    <div class="bg-gradient-to-r from-gray-50 to-blue-50 px-6 py-3 border-t border-gray-200 flex items-center justify-between text-sm">
      <div class="flex items-center space-x-6 text-gray-600">
        <div class="flex items-center space-x-2">
          <div class="w-2 h-2 bg-blue-500 rounded-full"></div>
          <span>行 {{ cursorLine }}，列 {{ cursorColumn }}</span>
        </div>
        <div class="flex items-center space-x-2">
          <div class="w-2 h-2 bg-green-500 rounded-full"></div>
          <span>字数：{{ wordCount }}</span>
        </div>
      </div>
      <div class="flex items-center space-x-4 text-gray-600">
        <span v-if="hasSelection" class="flex items-center space-x-2">
          <div class="w-2 h-2 bg-orange-500 rounded-full"></div>
          <span>已选择 {{ selectionLength }} 个字符</span>
        </span>
        <div class="flex items-center space-x-2">
          <div
            class="w-2 h-2 rounded-full"
            :class="readonly ? 'bg-gray-500' : 'bg-green-500'"
          ></div>
          <span>{{ readonly ? '只读模式' : '编辑模式' }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, nextTick, onMounted, watch } from 'vue'

// Props
interface Props {
  modelValue: string
  placeholder?: string
  readonly?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  placeholder: '请输入内容...',
  readonly: false
})

// Emits
const emit = defineEmits<{
  'update:modelValue': [value: string]
  input: [value: string]
  save: []
  focus: []
  blur: []
}>()

// 响应式数据
const editorRef = ref<HTMLElement>()
const showSymbolPicker = ref(false)
const cursorLine = ref(1)
const cursorColumn = ref(1)
const hasSelection = ref(false)
const selectionLength = ref(0)
const isFocused = ref(false)
const saveStatus = ref<'idle' | 'saving' | 'saved' | 'error'>('idle')

// 计算字数
const wordCount = computed(() => {
  return props.modelValue ? props.modelValue.length : 0
})

// 常用符号和医学符号
const commonSymbols = ['°', '±', '×', '÷', '≥', '≤', '≠', '≈', '∞', '√', '²', '³']
const medicalSymbols = ['♂', '♀', '℃', 'mmHg', 'mg/dl', 'ml/min', 'bpm', 'kg/m²']

// 模板内容
const templates = {
  chief_complaint: '主诉：\n',
  present_illness: '现病史：\n患者于____前无明显诱因出现____，表现为____，伴有____，无____。\n',
  physical_exam: '体格检查：\nT ____℃，P ____次/分，R ____次/分，BP ____/____mmHg\n一般情况：____\n皮肤黏膜：____\n浅表淋巴结：____\n',
  diagnosis: '诊断：\n1. \n2. \n3. \n'
}

// 计算属性
const formattedContent = computed(() => {
  return props.modelValue || ''
})

// 方法
const onInput = (event: Event) => {
  const target = event.target as HTMLElement
  const content = target.innerText || ''
  emit('update:modelValue', content)
  emit('input', content)
  updateCursorPosition()
}

const onKeydown = (event: KeyboardEvent) => {
  // Ctrl+S 保存
  if (event.ctrlKey && event.key === 's') {
    event.preventDefault()
    emit('save')
    return
  }

  // Tab 键插入空格
  if (event.key === 'Tab') {
    event.preventDefault()
    insertText('    ') // 4个空格
    return
  }

  // 更新光标位置
  nextTick(() => {
    updateCursorPosition()
    updateSelection()
  })
}

const onPaste = (event: ClipboardEvent) => {
  event.preventDefault()
  const text = event.clipboardData?.getData('text/plain') || ''
  insertText(text)
}

const onFocus = () => {
  isFocused.value = true
  emit('focus')
}

const onBlur = () => {
  isFocused.value = false
  emit('blur')
  showSymbolPicker.value = false
}

// 保存状态相关方法
const getSaveStatusText = () => {
  const statusMap = {
    'idle': '',
    'saving': '保存中...',
    'saved': '已保存',
    'error': '保存失败'
  }
  return statusMap[saveStatus.value]
}

// 模拟保存状态变化
const simulateSave = () => {
  saveStatus.value = 'saving'
  setTimeout(() => {
    saveStatus.value = 'saved'
    setTimeout(() => {
      saveStatus.value = 'idle'
    }, 2000)
  }, 1000)
}

// 格式化相关方法
const isFormatActive = (format: string): boolean => {
  return document.queryCommandState(format)
}

const toggleFormat = (format: string) => {
  document.execCommand(format, false)
  editorRef.value?.focus()
}

// 插入文本
const insertText = (text: string) => {
  const selection = window.getSelection()
  if (selection && selection.rangeCount > 0) {
    const range = selection.getRangeAt(0)
    range.deleteContents()
    range.insertNode(document.createTextNode(text))
    range.collapse(false)
    selection.removeAllRanges()
    selection.addRange(range)
  }
  
  // 触发输入事件
  const event = new Event('input', { bubbles: true })
  editorRef.value?.dispatchEvent(event)
}

// 插入模板
const insertTemplate = (templateKey: keyof typeof templates) => {
  const template = templates[templateKey]
  insertText(template)
}

// 插入当前时间
const insertCurrentTime = () => {
  const now = new Date()
  const timeString = now.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
  insertText(timeString)
}

// 插入符号
const insertSymbol = (symbol: string) => {
  insertText(symbol)
  showSymbolPicker.value = false
}

// 更新光标位置
const updateCursorPosition = () => {
  const selection = window.getSelection()
  if (selection && selection.rangeCount > 0 && editorRef.value) {
    const range = selection.getRangeAt(0)
    const preCaretRange = range.cloneRange()
    preCaretRange.selectNodeContents(editorRef.value)
    preCaretRange.setEnd(range.endContainer, range.endOffset)
    
    const content = preCaretRange.toString()
    const lines = content.split('\n')
    cursorLine.value = lines.length
    cursorColumn.value = lines[lines.length - 1].length + 1
  }
}

// 更新选择信息
const updateSelection = () => {
  const selection = window.getSelection()
  if (selection) {
    hasSelection.value = !selection.isCollapsed
    selectionLength.value = selection.toString().length
  }
}

// 监听内容变化
watch(() => props.modelValue, (newValue) => {
  if (editorRef.value && editorRef.value.innerText !== newValue) {
    editorRef.value.innerText = newValue || ''
  }
})

// 组件挂载后初始化
onMounted(() => {
  if (editorRef.value) {
    editorRef.value.innerText = props.modelValue || ''
  }
})
</script>

<style scoped>
/* 使用 Tailwind CSS 进行样式设计，移除所有自定义CSS */
</style>
