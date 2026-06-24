<template>
  <div class="bg-white dark:bg-slate-800 rounded-2xl shadow-sm flex flex-col flex-1 border border-slate-100 dark:border-slate-700 overflow-hidden relative min-h-[500px]">
    <div class="px-6 py-4 border-b border-slate-100 dark:border-slate-700 flex justify-between items-center bg-gradient-to-r from-blue-500/5 to-transparent">
      <div class="flex items-center gap-2">
        <FileTextOutlined class="text-blue-500" />
        <h3 class="font-semibold text-slate-800 dark:text-white">
          病历原文
        </h3>
      </div>
      <div class="flex gap-2">
        <button class="text-xs font-medium text-slate-500 hover:text-blue-500 px-2 py-1 bg-slate-100 dark:bg-slate-700 rounded-md">
          全屏
        </button>
        <button class="text-xs font-medium text-slate-500 hover:text-blue-500 px-2 py-1 bg-slate-100 dark:bg-slate-700 rounded-md">
          放大
        </button>
      </div>
    </div>

    <div
      v-if="loading"
      class="p-8"
    >
      <a-skeleton
        active
        :paragraph="{ rows: 10 }"
      />
    </div>
    <div
      v-else-if="medicalText"
      class="flex-1 p-6 bg-slate-50/30 dark:bg-slate-900/30 overflow-y-auto custom-scrollbar"
    >
      <pre class="font-mono text-sm leading-relaxed whitespace-pre-wrap text-slate-700 dark:text-slate-300">{{ medicalText }}</pre>
    </div>
    <div
      v-else
      class="flex-1 flex flex-col items-center justify-start p-10 pt-16 bg-slate-50/50 dark:bg-slate-800/30"
    >
      <div
        class="w-32 h-32 bg-blue-50 dark:bg-blue-900/20 rounded-full flex items-center justify-center mb-6 relative group cursor-pointer transition-all hover:scale-105"
        @click="() => $emit('selectTestCase', 0)"
      >
        <UploadOutlined class="text-6xl text-blue-500/40 group-hover:text-blue-500 transition-colors" />
        <div class="absolute -bottom-2 -right-2 bg-white dark:bg-slate-700 p-2 rounded-full shadow-md">
          <RobotOutlined class="text-blue-500 text-xl" />
        </div>
      </div>
      <h3 class="text-lg font-medium text-slate-700 dark:text-slate-200 mb-2">
        未加载病历
      </h3>
      <p class="text-slate-500 dark:text-slate-400 text-sm mb-6 text-center max-w-xs">
        上传扫描的 PDF 或图片以开始 AI 分析流程。
      </p>
      <a-dropdown>
        <button class="bg-blue-500 hover:bg-blue-600 text-white px-6 py-3 rounded-xl font-medium shadow-lg shadow-blue-500/30 transition-all flex items-center gap-2">
          <PlusOutlined />
          加载测试病历
          <DownOutlined class="text-xs" />
        </button>
        <template #overlay>
          <a-menu>
            <a-menu-item
              v-for="(testCase, index) in testCases"
              :key="String(index)"
              @click="() => emit('selectTestCase', index)"
            >
              <div class="flex flex-col py-1">
                <span class="font-medium">{{ testCase.name }}</span>
                <span class="text-xs text-slate-400">{{ testCase.description }}</span>
              </div>
            </a-menu-item>
          </a-menu>
        </template>
      </a-dropdown>
    </div>
  </div>
</template>

<script setup lang="ts">
import { DownOutlined, FileTextOutlined, PlusOutlined, RobotOutlined, UploadOutlined } from '@ant-design/icons-vue'

export interface TestCaseItem {
  name: string
  description: string
  medical_text: string
}

const props = defineProps<{
  loading: boolean
  medicalText?: string
  testCases: TestCaseItem[]
}>()

const emit = defineEmits<{
  (e: 'selectTestCase', index: number): void
}>()
</script>
