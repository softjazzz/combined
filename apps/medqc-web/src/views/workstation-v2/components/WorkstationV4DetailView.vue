<template>
  <div
    class="relative z-10 flex-1 flex flex-col min-w-0 h-full bg-[linear-gradient(180deg,rgba(248,250,252,0.9),rgba(241,245,249,0.96))]"
  >
    <DetailHeader
      :record="selectedRecord"
      :current-index="currentRecordIndex"
      :total-count="filteredRecordsLength"
      :generating="frontpageGenerating"
      :has-draft="hasDraft"
      :can-generate="canGenerateFrontpage"
      :disabled-reason="frontpageDisabledReason"
      @back="emit('back')"
      @prev="emit('prev')"
      @next="emit('next')"
      @open-icd="emit('open-icd')"
      @generate-frontpage="emit('generate-frontpage')"
    />

    <div class="flex flex-1 overflow-hidden">
      <DetailSidebar
        :record="selectedRecord"
        :documents="documentsList"
        :documents-loading="documentsLoading"
        :active-doc-type="activeDocType"
        @preview-doc="emit('preview-doc', $event)"
      />

      <a-drawer
        :open="docDrawerVisible"
        :title="docDrawerTitle"
        placement="right"
        :width="560"
        :header-style="{
          borderBottom: '1px solid rgba(148,163,184,0.14)',
          background:
            'linear-gradient(180deg, rgba(255,255,255,0.96) 0%, rgba(247,250,252,0.96) 100%)',
          padding: '16px 18px',
        }"
        :body-style="{
          padding: '16px',
          background: 'linear-gradient(180deg, #f8fafc 0%, #f3f6fa 100%)',
        }"
        @update:open="emit('update:docDrawerVisible', $event)"
      >
        <div
          class="rounded-[20px] border border-slate-200/70 bg-white/92 p-4 shadow-[0_8px_18px_rgba(15,23,42,0.045)]"
        >
          <pre class="m-0 whitespace-pre-wrap font-sans text-[13px] leading-7 text-slate-700">{{
            docDrawerContent
          }}</pre>
        </div>
      </a-drawer>

      <main
        class="relative flex flex-1 flex-col overflow-hidden bg-[linear-gradient(180deg,#f8fafc_0%,#eef2f7_100%)] dark:bg-slate-950"
      >
        <div
          class="sticky top-0 z-10 border-b border-slate-200/55 bg-white/40 px-3 pb-1 pt-1 backdrop-blur-xl lg:px-4"
        >
          <div
            class="inline-flex items-center gap-1 rounded-full border border-slate-200/65 bg-white/66 p-1"
          >
            <button :class="tabClass('records')" @click="emit('update:detailMainTab', 'records')">
              <span class="flex items-center gap-1.5"><FileTextOutlined />病历详情</span>
            </button>
            <button
              :class="tabClass('frontpage')"
              @click="emit('update:detailMainTab', 'frontpage')"
            >
              <span class="flex items-center gap-1.5"><FileSearchOutlined />病案首页</span>
            </button>
            <button
              :class="tabClass('settlement')"
              @click="emit('update:detailMainTab', 'settlement')"
            >
              <span class="flex items-center gap-1.5">
                <span style="font-size: 14px">💰</span>结算清单
                <span
                  v-if="settlementQcFailed > 0"
                  class="ml-1 min-w-[18px] h-[18px] flex items-center justify-center rounded-full bg-blue-100 text-blue-600 text-[10px] font-bold px-1"
                  >{{ settlementQcFailed }}</span
                >
              </span>
            </button>
          </div>
        </div>

        <div class="flex-1 overflow-y-auto custom-scrollbar">
          <slot v-if="detailMainTab === 'records'" name="records" />
          <slot v-else-if="detailMainTab === 'frontpage'" name="frontpage" />
          <slot v-else-if="detailMainTab === 'settlement'" name="settlement" />
        </div>
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { FileSearchOutlined, FileTextOutlined } from '@ant-design/icons-vue'

import DetailHeader from './DetailHeader.vue'
import DetailSidebar from './DetailSidebar.vue'
import type { DocItem, PatientRecord } from '../types'

const props = defineProps<{
  selectedRecord?: PatientRecord
  currentRecordIndex: number
  filteredRecordsLength: number
  frontpageGenerating: boolean
  hasDraft: boolean
  canGenerateFrontpage: boolean
  frontpageDisabledReason: string
  documentsList: DocItem[]
  documentsLoading: boolean
  activeDocType?: string
  docDrawerVisible: boolean
  docDrawerTitle: string
  docDrawerContent: string
  detailMainTab: 'records' | 'frontpage' | 'settlement'
  settlementQcFailed: number
}>()

const emit = defineEmits<{
  back: []
  prev: []
  next: []
  'open-icd': []
  'generate-frontpage': []
  'preview-doc': [doc: DocItem]
  'update:docDrawerVisible': [open: boolean]
  'update:detailMainTab': [tab: 'records' | 'frontpage' | 'settlement']
}>()

function tabClass(tab: 'records' | 'frontpage' | 'settlement') {
  return [
    'rounded-full border px-4 py-1.5 text-[13px] transition-all cursor-pointer',
    props.detailMainTab === tab
      ? 'font-bold text-blue-900 bg-blue-50 border-blue-200 shadow-[0_3px_8px_rgba(37,99,235,0.05)]'
      : 'font-medium text-slate-500 border-transparent hover:bg-white/70 hover:text-slate-800',
  ]
}
</script>
