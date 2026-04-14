<template>
  <div class="px-3 pb-4 pt-1.5 lg:px-4 lg:pb-5">
    <div
      class="relative mx-auto w-full max-w-[1200px] rounded-[16px] border border-slate-200/45 bg-[linear-gradient(180deg,rgba(255,255,255,0.9),rgba(252,253,255,0.98))] px-1 py-1.5 shadow-[0_6px_16px_rgba(15,23,42,0.02)] lg:px-1.5 lg:py-2"
    >
      <div
        v-if="selectedRecord"
        class="absolute right-4 top-0 flex items-center gap-1 rounded-b-md border-x border-b px-2 py-0.5 text-[10px] font-bold opacity-75"
        :class="
          selectedRecord.status === 'completed'
            ? 'bg-blue-50 text-blue-600 border-blue-100/50'
            : selectedRecord.status === 'has_defects' || selectedRecord.status === 'warning'
              ? 'bg-slate-50 text-slate-500 border-slate-200/70'
              : 'bg-blue-50 text-blue-600 border-blue-100/50'
        "
      >
        <CheckCircleOutlined v-if="selectedRecord.status === 'completed'" />
        <WarningOutlined
          v-else-if="selectedRecord.status === 'has_defects' || selectedRecord.status === 'warning'"
        />
        <ThunderboltOutlined v-else />
        {{
          selectedRecord.status === 'completed'
            ? 'AI 预审通过'
            : selectedRecord.status === 'has_defects' || selectedRecord.status === 'warning'
              ? 'AI 发现缺陷'
              : 'AI 待审'
        }}
      </div>

      <AsyncEMRViewer
        v-if="selectedRecord && emrRenderState !== 'fallback'"
        :record-id="selectedRecord.id"
        :visit-id="selectedRecord.visitId || selectedRecord.id"
        :patient-id="selectedRecord.patientId"
        :institute-id="selectedRecord.instituteId"
        :active-doc-key="activeDocType"
        :max-height="760"
        :hide-doc-tabs="true"
        @loaded="emit('emr-loaded', $event)"
        @error="emit('emr-error')"
        @defect-click="emit('emr-defect-click', $event)"
      />

      <template v-else>
        <div
          v-if="concatLoading"
          class="flex flex-col items-center py-20"
        >
          <a-spin size="large" />
          <div class="text-sm text-slate-400 mt-4">
            加载病历文书中...
          </div>
        </div>

        <div
          v-else-if="concatText"
          class="medical-record-document mx-auto max-w-[116ch] px-3 py-0.5"
        >
          <div
            class="mb-3 flex flex-wrap items-center justify-between gap-2 rounded-[12px] border border-slate-200/80 bg-white/82 px-3 py-2"
          >
            <div class="text-[12px] font-semibold text-slate-500">
              已加载
              <span class="font-mono text-slate-700">{{ concatSections.length }}</span>
              段文书，共
              <span class="font-mono text-slate-700">{{ concatTotalChars }}</span>
              字
            </div>
            <a-button
              size="small"
              class="!rounded-full !border-slate-200/80 !bg-white !text-slate-700"
              @click="emit('toggle-expand-all-sections')"
            >
              {{ allConcatSectionsExpanded ? '收起全文' : '展开全文' }}
            </a-button>
          </div>
          <div
            class="mb-4 flex items-center gap-2 rounded-[10px] border border-blue-100/80 bg-blue-50/55 px-3 py-2 text-xs text-blue-700"
          >
            <WarningOutlined />
            <span>EMR 高亮视图暂不可用，已自动切换到原始文书预览。</span>
          </div>
          <div
            v-for="(section, idx) in concatSections"
            :key="idx"
            class="mb-5 rounded-[12px] border border-slate-200/75 bg-white/68 p-3 transition-all"
          >
            <button
              class="mb-2 flex w-full items-center justify-between gap-2 border-none bg-transparent p-0 text-left cursor-pointer"
              @click="emit('toggle-section', idx)"
            >
              <span class="flex items-center gap-2">
                <FileTextOutlined class="text-blue-400" />
                <h3 class="m-0 text-[15px] font-bold text-slate-800 dark:text-white">
                  {{ section.title }}
                </h3>
              </span>
              <span class="text-[11px] font-semibold text-blue-600">
                {{ isSectionExpanded(idx) ? '收起' : '展开' }}
              </span>
            </button>
            <div class="h-px bg-slate-100 mb-2" />
            <div
              :class="[
                'medical-record-document__content-wrap',
                !isSectionExpanded(idx) && 'medical-record-document__content-wrap--collapsed',
              ]"
            >
              <pre
                class="medical-record-document__content m-0 whitespace-pre-wrap rounded-[6px] bg-transparent px-0 py-0 font-sans text-[14px] leading-[2.05] text-slate-700 dark:text-slate-300"
              >{{ section.content }}</pre>
            </div>
          </div>
        </div>

        <div
          v-else
          class="flex flex-col items-center justify-center py-20 text-slate-300"
        >
          <div
            class="w-20 h-20 rounded-full bg-slate-50 dark:bg-slate-800 flex items-center justify-center mb-4 border-2 border-dashed border-slate-200 dark:border-slate-700"
          >
            <FileTextOutlined class="text-3xl" />
          </div>
          <div class="text-sm font-medium mb-1">
            暂无病历文书
          </div>
          <div class="text-xs text-slate-400">
            该患者当前暂无可展示的病历文书内容。
          </div>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { defineAsyncComponent } from 'vue'
import {
  CheckCircleOutlined,
  FileTextOutlined,
  ThunderboltOutlined,
  WarningOutlined,
} from '@ant-design/icons-vue'
import type { PatientRecord } from '../types'

interface ConcatSection {
  title: string
  content: string
}

defineProps<{
  selectedRecord?: PatientRecord
  emrRenderState: 'idle' | 'loading' | 'ready' | 'fallback'
  concatLoading: boolean
  concatText: string
  concatSections: ConcatSection[]
  concatTotalChars: number
  allConcatSectionsExpanded: boolean
  activeDocType?: string
  docPreviewActive?: boolean
  docPreviewTitle?: string
  docPreviewContent?: string
  isSectionExpanded: (index: number) => boolean
}>()

const emit = defineEmits<{
  'emr-loaded': [payload: any]
  'emr-error': []
  'emr-defect-click': [payload: any]
  'toggle-expand-all-sections': []
  'toggle-section': [index: number]
}>()

const AsyncEMRViewer = defineAsyncComponent(() => import('@/components/qc/EMRViewer.vue'))
</script>
