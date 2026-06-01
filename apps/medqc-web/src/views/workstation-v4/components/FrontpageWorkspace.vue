<template>
  <div class="px-3 pb-4 pt-1.5 lg:px-4 lg:pb-5">
    <div
      class="mx-auto w-full max-w-[1200px] rounded-[18px] border border-slate-200/55 bg-[linear-gradient(180deg,rgba(255,255,255,0.9),rgba(250,252,255,0.98))] p-2.5 shadow-[0_8px_20px_rgba(15,23,42,0.03)]"
    >
      <div
        v-if="
          frontpageGenerating ||
            frontpagePostProcessing ||
            draft ||
            frontpageSheetLoading ||
            frontpageSheetData
        "
        class="mb-2 flex flex-wrap items-center justify-end gap-2 px-1"
      >
        <a-tooltip title="基于当前已选病历/同步文书">
          <a-button
            type="primary"
            class="!h-9 !rounded-full !border-0 !px-4 !text-sm !font-bold !shadow-[0_8px_18px_rgba(37,99,235,0.16)]"
            :loading="frontpageGenerating"
            :disabled="!canGenerateFrontpage"
            @click="emit('generate-frontpage')"
          >
            <template #icon>
              <ThunderboltOutlined />
            </template>
            AI 生成首页
          </a-button>
        </a-tooltip>
        <a-tooltip title="直接粘贴完整病历原文抽取">
          <a-button
            class="!h-9 !rounded-full !border-blue-100 !bg-blue-50/70 !px-4 !text-sm !font-semibold !text-blue-700 hover:!border-blue-200 hover:!bg-blue-50"
            :disabled="frontpageGenerating || frontpagePostProcessing"
            @click="emit('paste-frontpage')"
          >
            <template #icon>
              <FileTextOutlined />
            </template>
            粘贴病历生成首页
          </a-button>
        </a-tooltip>
      </div>
      <div
        v-if="
          !frontpageGenerating &&
            !frontpagePostProcessing &&
            !draft &&
            !frontpageSheetLoading &&
            !frontpageSheetData
        "
        class="flex min-h-[360px] flex-col items-center justify-center rounded-[16px] border border-dashed border-blue-200/80 bg-[linear-gradient(180deg,rgba(255,255,255,0.95),rgba(245,249,255,0.98))] px-6 py-12 text-center shadow-[inset_0_1px_0_rgba(255,255,255,0.88),0_14px_32px_rgba(148,163,184,0.08)]"
      >
        <div
          class="mb-4 flex h-16 w-16 items-center justify-center rounded-[20px] border border-blue-200/80 bg-[linear-gradient(180deg,#eef4ff,#dbeafe)] shadow-[0_12px_24px_rgba(59,130,246,0.14),inset_0_1px_0_rgba(255,255,255,0.8)]"
        >
          <FileSearchOutlined class="text-[28px] text-blue-600" />
        </div>
        <div class="text-[18px] font-black text-slate-900">
          暂无病案首页数据
        </div>
        <div class="mt-2 max-w-[360px] text-[13px] leading-6 text-slate-500">
          当前病历还没有可展示的病案首页正式数据，可先生成首页草稿后再继续复核与补录。
        </div>
        <div class="mt-6 flex items-center gap-2">
          <a-button
            type="primary"
            class="!h-10 !rounded-full !border-0 !px-5 !text-sm !font-bold !shadow-[0_10px_20px_rgba(37,99,235,0.18)]"
            :disabled="!canGenerateFrontpage"
            @click="emit('generate-frontpage')"
          >
            <template #icon>
              <ThunderboltOutlined />
            </template>
            AI 生成首页
          </a-button>
          <a-button
            class="!h-10 !rounded-full !border-blue-100 !bg-blue-50/70 !px-5 !text-sm !font-semibold !text-blue-700"
            @click="emit('paste-frontpage')"
          >
            <template #icon>
              <FileTextOutlined />
            </template>
            粘贴病历生成首页
          </a-button>
          <a-button
            class="!h-10 !rounded-full !border-slate-200/90 !bg-white/85 !px-5 !text-sm !font-semibold !text-slate-600"
            @click="emit('reload-frontpage-sheet')"
          >
            <template #icon>
              <SyncOutlined />
            </template>
            重新加载
          </a-button>
        </div>
      </div>
      <FrontpageWorkspacePanel
        v-else
        :generating="frontpageGenerating"
        :post-processing="frontpagePostProcessing"
        :draft="draft"
        :frontpage-tab="frontpageTab"
        :module-cards="frontpageModuleCards"
        :completed-count="completedCount"
        :total-count="totalCount"
        :sheet-loading="frontpageSheetLoading"
        :sheet-data="frontpageSheetData"
        @update:frontpage-tab="emit('update:frontpage-tab', $event)"
        @export-frontpage="emit('export-frontpage', $event)"
        @save-frontpage="emit('save-frontpage')"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import {
  FileSearchOutlined,
  FileTextOutlined,
  SyncOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons-vue'
import FrontpageWorkspacePanel from './FrontpageWorkspacePanel.vue'

type FrontpageTabKey = 'fields' | 'preview' | 'official'
type FrontpageModuleCard = {
  key: string
  label: string
  status: 'done' | 'active' | 'pending'
  entry?: {
    preview?: { label: string; value: string; isLongText?: boolean }[]
    timestamp?: number
  }
}

defineProps<{
  frontpageGenerating: boolean
  frontpagePostProcessing: boolean
  draft: Record<string, any> | null
  frontpageTab: FrontpageTabKey
  frontpageModuleCards: FrontpageModuleCard[]
  completedCount: number
  totalCount: number
  frontpageSheetLoading: boolean
  frontpageSheetData: Record<string, any> | null
  canGenerateFrontpage: boolean
}>()

const emit = defineEmits<{
  'generate-frontpage': []
  'paste-frontpage': []
  'reload-frontpage-sheet': []
  'update:frontpage-tab': [tab: FrontpageTabKey]
  'export-frontpage': [format: 'health' | 'insurance' | 'settlement']
  'save-frontpage': []
}>()
</script>
