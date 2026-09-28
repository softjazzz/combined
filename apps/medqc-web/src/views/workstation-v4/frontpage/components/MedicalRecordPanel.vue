<template>
  <div
    class="bg-white/90 rounded-2xl shadow-sm flex flex-col flex-1 border border-black/[0.08] overflow-hidden relative min-h-[500px] backdrop-blur-[18px]"
  >
    <div
      class="px-6 py-4 border-b border-black/[0.08] flex justify-between items-center bg-[rgba(10, 108, 255,0.04)]"
    >
      <div class="flex items-center gap-2">
        <FileTextOutlined class="text-[#0a6cff]" />
        <h3 class="font-semibold text-[#1d1d1f]">
          病历原文
        </h3>
      </div>
      <div class="flex gap-2">
        <button
          class="text-xs font-medium text-[rgba(29,29,31,0.56)] hover:text-[#0a6cff] px-2 py-1 bg-white border border-black/[0.08] rounded-md"
        >
          全屏
        </button>
        <button
          class="text-xs font-medium text-[rgba(29,29,31,0.56)] hover:text-[#0a6cff] px-2 py-1 bg-white border border-black/[0.08] rounded-md"
        >
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
      class="flex-1 p-6 bg-[#f5f5f7]/55 overflow-y-auto custom-scrollbar"
    >
      <pre
        class="font-mono text-sm leading-relaxed whitespace-pre-wrap text-[rgba(29,29,31,0.78)]"
      >{{ medicalText }}</pre>
    </div>
    <div
      v-else
      class="flex-1 flex flex-col items-center justify-start p-10 pt-16 bg-[#f5f5f7]/55"
    >
      <div
        class="w-32 h-32 bg-[rgba(10, 108, 255,0.06)] border border-[rgba(10, 108, 255,0.12)] rounded-2xl flex items-center justify-center mb-6 relative group cursor-pointer transition-all hover:-translate-y-0.5 hover:shadow-[0_2px_12px_rgba(0,0,0,0.10),0_6px_22px_rgba(0,0,0,0.075)]"
        @click="() => $emit('selectTestCase', 0)"
      >
        <UploadOutlined
          class="text-6xl text-[#0a6cff]/40 group-hover:text-[#0a6cff] transition-colors"
        />
        <div
          class="absolute -bottom-2 -right-2 bg-white p-2 rounded-full shadow-md border border-black/[0.08]"
        >
          <RobotOutlined class="text-[#0a6cff] text-xl" />
        </div>
      </div>
      <h3 class="text-lg font-medium text-[#1d1d1f] mb-2">
        未加载病历
      </h3>
      <p class="text-[rgba(29,29,31,0.6)] text-sm mb-6 text-center max-w-xs">
        上传扫描的 PDF 或图片以开始 AI 分析流程。
      </p>
      <a-dropdown>
        <button
          class="bg-[#0a6cff] hover:bg-[#0a5fd6] text-white px-6 py-3 rounded-xl font-medium shadow-[0_5px_14px_rgba(10, 108, 255,0.18)] transition-all flex items-center gap-2"
        >
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
import {
  DownOutlined,
  FileTextOutlined,
  PlusOutlined,
  RobotOutlined,
  UploadOutlined,
} from '@ant-design/icons-vue'

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
