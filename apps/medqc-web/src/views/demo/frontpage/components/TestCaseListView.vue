<template>
  <div class="h-full w-full flex flex-col bg-slate-50 dark:bg-slate-900 p-6 overflow-hidden">
    <!-- Header -->
    <div class="flex items-center gap-3 mb-6">
      <button @click="$emit('back')" class="text-slate-400 hover:text-slate-600 dark:hover:text-slate-300">
        <ArrowLeftOutlined class="text-lg" />
      </button>
      <h2 class="text-xl font-semibold text-slate-800 dark:text-white">测试病历列表</h2>
      <span class="text-sm text-slate-400">{{ testCases.length }} 个测试病历</span>
    </div>

    <div class="flex-1 flex gap-4 overflow-hidden">
      <!-- Left: Test Case List -->
      <div class="w-80 flex-shrink-0 bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 flex flex-col overflow-hidden">
        <div class="px-4 py-3 border-b border-slate-200 dark:border-slate-700">
          <h3 class="text-sm font-semibold text-slate-700 dark:text-slate-200">病历列表</h3>
        </div>
        
        <div class="flex-1 overflow-y-auto">
          <div
            v-for="(testCase, index) in testCases"
            :key="index"
            @click="selectedIndex = index"
            :class="[
              'p-4 border-b border-slate-100 dark:border-slate-700 cursor-pointer transition-colors',
              selectedIndex === index 
                ? 'bg-blue-50 dark:bg-blue-900/20 border-l-4 border-l-blue-500' 
                : 'hover:bg-slate-50 dark:hover:bg-slate-700/30'
            ]"
          >
            <div class="flex items-start gap-3">
              <div class="w-10 h-10 rounded-lg bg-blue-100 dark:bg-blue-900/30 flex items-center justify-center flex-shrink-0">
                <FileTextOutlined class="text-blue-600 dark:text-blue-400" />
              </div>
              <div class="flex-1 min-w-0">
                <div class="font-medium text-slate-800 dark:text-white mb-1">
                  测试病历{{ index + 1 }}
                </div>
                <div class="text-xs text-slate-500 dark:text-slate-400 line-clamp-2">
                  {{ testCase.description }}
                </div>
                <div class="mt-2 flex items-center gap-2 text-xs text-slate-400">
                  <ClockCircleOutlined />
                  <span>{{ formatDate(testCase.createdAt) }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Right: Case Content -->
      <div class="flex-1 bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 flex flex-col overflow-hidden">
        <div class="px-5 py-4 border-b border-slate-200 dark:border-slate-700 flex items-center justify-between">
          <div>
            <h3 class="text-sm font-semibold text-slate-700 dark:text-slate-200">
              测试病历{{ selectedIndex + 1 }}
            </h3>
            <p class="text-xs text-slate-500 dark:text-slate-400 mt-1">
              {{ selectedCase?.description }}
            </p>
          </div>
          <div class="flex gap-2">
            <button
              @click="loadCase"
              class="px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition-colors text-sm flex items-center gap-2"
            >
              <UploadOutlined />
              加载到工作台
            </button>
            <button
              @click="copyContent"
              class="px-4 py-2 bg-slate-100 dark:bg-slate-700 text-slate-700 dark:text-slate-300 rounded-lg hover:bg-slate-200 dark:hover:bg-slate-600 transition-colors text-sm flex items-center gap-2"
            >
              <CopyOutlined />
              复制内容
            </button>
          </div>
        </div>
        
        <div class="flex-1 overflow-y-auto p-5">
          <div class="bg-slate-50 dark:bg-slate-900 rounded-lg p-4 border border-slate-200 dark:border-slate-700">
            <div class="flex items-center justify-between mb-3">
              <span class="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase">病历原文</span>
              <span class="text-xs text-slate-400">{{ selectedCase?.medical_text.length }} 字符</span>
            </div>
            <pre class="text-sm text-slate-700 dark:text-slate-300 whitespace-pre-wrap font-mono leading-relaxed">{{ selectedCase?.medical_text }}</pre>
          </div>

          <!-- Metadata -->
          <div class="mt-4 grid grid-cols-2 gap-4">
            <div class="bg-slate-50 dark:bg-slate-900 rounded-lg p-4 border border-slate-200 dark:border-slate-700">
              <div class="text-xs font-semibold text-slate-500 dark:text-slate-400 mb-2">病历信息</div>
              <div class="space-y-2 text-sm">
                <div class="flex justify-between">
                  <span class="text-slate-500 dark:text-slate-400">病历类型:</span>
                  <span class="text-slate-700 dark:text-slate-300">{{ selectedCase?.type || '住院病历' }}</span>
                </div>
                <div class="flex justify-between">
                  <span class="text-slate-500 dark:text-slate-400">创建时间:</span>
                  <span class="text-slate-700 dark:text-slate-300">{{ formatDate(selectedCase?.createdAt) }}</span>
                </div>
              </div>
            </div>

            <div class="bg-slate-50 dark:bg-slate-900 rounded-lg p-4 border border-slate-200 dark:border-slate-700">
              <div class="text-xs font-semibold text-slate-500 dark:text-slate-400 mb-2">统计信息</div>
              <div class="space-y-2 text-sm">
                <div class="flex justify-between">
                  <span class="text-slate-500 dark:text-slate-400">字符数:</span>
                  <span class="text-slate-700 dark:text-slate-300">{{ selectedCase?.medical_text.length }}</span>
                </div>
                <div class="flex justify-between">
                  <span class="text-slate-500 dark:text-slate-400">行数:</span>
                  <span class="text-slate-700 dark:text-slate-300">{{ selectedCase?.medical_text.split('\n').length }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { message } from 'ant-design-vue'
import {
  ArrowLeftOutlined,
  FileTextOutlined,
  ClockCircleOutlined,
  UploadOutlined,
  CopyOutlined
} from '@ant-design/icons-vue'

const props = defineProps<{
  testCases: Array<{
    description: string
    medical_text: string
    type?: string
    createdAt?: string
  }>
}>()

const emit = defineEmits<{
  (e: 'back'): void
  (e: 'loadCase', index: number): void
}>()

const selectedIndex = ref(0)

const selectedCase = computed(() => props.testCases[selectedIndex.value])

const formatDate = (date?: string) => {
  if (!date) return '2026-01-05'
  return new Date(date).toLocaleDateString('zh-CN')
}

const loadCase = () => {
  emit('loadCase', selectedIndex.value)
  message.success(`已加载测试病历${selectedIndex.value + 1}到工作台`)
}

const copyContent = async () => {
  try {
    await navigator.clipboard.writeText(selectedCase.value?.medical_text || '')
    message.success('病历内容已复制到剪贴板')
  } catch (error) {
    message.error('复制失败')
  }
}
</script>
