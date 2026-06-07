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

    <div class="flex min-h-0 flex-1 flex-col overflow-hidden">
      <div class="border-b border-slate-200/70 bg-white/70 px-4 py-2.5 backdrop-blur-xl">
        <div class="flex flex-wrap items-center gap-2">
          <button
            :class="tabClass('records')"
            @click="emit('update:detailMainTab', 'records')"
          >
            <span class="detail-workspace-tab__icon"><FileTextOutlined /></span>
            <span class="detail-workspace-tab__main">
              <span class="detail-workspace-tab__title">病历详情</span>
              <span class="detail-workspace-tab__desc">文书阅读与证据定位</span>
            </span>
          </button>
          <button
            :class="tabClass('frontpage')"
            @click="emit('update:detailMainTab', 'frontpage')"
          >
            <span class="detail-workspace-tab__icon"><FileSearchOutlined /></span>
            <span class="detail-workspace-tab__main">
              <span class="detail-workspace-tab__title">病案首页</span>
              <span class="detail-workspace-tab__desc">抽取、预览、系统首页</span>
            </span>
          </button>
          <button
            :class="tabClass('settlement')"
            @click="emit('update:detailMainTab', 'settlement')"
          >
            <span class="detail-workspace-tab__icon"><MedicineBoxOutlined /></span>
            <span class="detail-workspace-tab__main">
              <span class="detail-workspace-tab__title">
                结算清单
                <span
                  v-if="settlementQcFailed > 0"
                  class="detail-workspace-tab__badge"
                >{{
                  settlementQcFailed
                }}</span>
              </span>
              <span class="detail-workspace-tab__desc">清单预览与控费质控</span>
            </span>
          </button>
          <button
            :class="tabClass('completeness')"
            @click="emit('update:detailMainTab', 'completeness')"
          >
            <span class="detail-workspace-tab__icon"><AuditOutlined /></span>
            <span class="detail-workspace-tab__main">
              <span class="detail-workspace-tab__title">诊疗完整性</span>
              <span class="detail-workspace-tab__desc">诊断时间轴与手术验证</span>
            </span>
          </button>
        </div>
      </div>

      <div class="flex min-h-0 flex-1 overflow-hidden">
        <DetailSidebar
          v-if="detailMainTab === 'records'"
          :record="selectedRecord"
          :documents="documentsList"
          :documents-tree="documentsTree"
          :documents-loading="documentsLoading"
          :active-doc-type="activeDocType"
          @preview-doc="emit('preview-doc', $event)"
          @show-concat="emit('show-concat')"
        />

        <main
          class="relative flex flex-1 flex-col overflow-hidden bg-[linear-gradient(180deg,#f8fafc_0%,#eef2f7_100%)]"
        >
          <div class="flex-1 overflow-y-auto custom-scrollbar">
            <slot
              v-if="detailMainTab === 'records'"
              name="records"
            />
            <slot
              v-else-if="detailMainTab === 'frontpage'"
              name="frontpage"
            />
            <slot
              v-else-if="detailMainTab === 'settlement'"
              name="settlement"
            />
            <ClinicalCompletenessPanel
              v-else-if="detailMainTab === 'completeness'"
              :record="selectedRecord"
            />
          </div>
        </main>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import {
  AuditOutlined,
  FileSearchOutlined,
  FileTextOutlined,
  MedicineBoxOutlined,
} from '@ant-design/icons-vue'

import ClinicalCompletenessPanel from './ClinicalCompletenessPanel.vue'
import DetailHeader from './DetailHeader.vue'
import DetailSidebar from './DetailSidebar.vue'
import type { DocItem, DocTreeGroup, PatientRecord } from '../types'

type DetailMainTab = 'records' | 'frontpage' | 'settlement' | 'completeness'

const props = defineProps<{
  selectedRecord?: PatientRecord
  currentRecordIndex: number
  filteredRecordsLength: number
  frontpageGenerating: boolean
  hasDraft: boolean
  canGenerateFrontpage: boolean
  frontpageDisabledReason: string
  documentsList: DocItem[]
  documentsTree: DocTreeGroup[]
  documentsLoading: boolean
  activeDocType?: string
  detailMainTab: DetailMainTab
  settlementQcFailed: number
}>()

const emit = defineEmits<{
  back: []
  prev: []
  next: []
  'open-icd': []
  'generate-frontpage': []
  'preview-doc': [doc: DocItem]
  'show-concat': []
  'update:detailMainTab': [tab: DetailMainTab]
}>()

function tabClass(tab: DetailMainTab) {
  return [
    'detail-workspace-tab',
    props.detailMainTab === tab ? 'detail-workspace-tab--active' : 'detail-workspace-tab--idle',
  ]
}
</script>

<style scoped>
.detail-workspace-tab {
  display: inline-flex;
  min-width: 188px;
  align-items: center;
  gap: 10px;
  border: 1px solid rgba(226, 232, 240, 0.86);
  border-radius: 14px;
  padding: 10px 14px;
  text-align: left;
  cursor: pointer;
  transition:
    background-color 160ms ease,
    border-color 160ms ease,
    box-shadow 160ms ease,
    transform 160ms ease;
}

.detail-workspace-tab--idle {
  background: rgba(255, 255, 255, 0.78);
  color: #64748b;
}

.detail-workspace-tab--idle:hover {
  border-color: rgba(191, 219, 254, 0.92);
  background: rgba(255, 255, 255, 0.94);
  color: #0f172a;
}

.detail-workspace-tab--active {
  border-color: rgba(37, 99, 235, 0.3);
  background: linear-gradient(180deg, rgba(239, 246, 255, 0.96), rgba(255, 255, 255, 0.98));
  color: #0f172a;
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.95),
    0 10px 24px rgba(37, 99, 235, 0.1);
}

.detail-workspace-tab__icon {
  display: inline-flex;
  width: 34px;
  height: 34px;
  flex: 0 0 auto;
  align-items: center;
  justify-content: center;
  border-radius: 11px;
  background: rgba(239, 246, 255, 0.95);
  color: #2563eb;
  font-size: 17px;
}

.detail-workspace-tab--active .detail-workspace-tab__icon {
  background: #2563eb;
  color: #fff;
}

.detail-workspace-tab__main {
  display: grid;
  min-width: 0;
  gap: 2px;
}

.detail-workspace-tab__title {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
  font-weight: 800;
  line-height: 18px;
}

.detail-workspace-tab__desc {
  overflow: hidden;
  color: #64748b;
  font-size: 12px;
  font-weight: 600;
  line-height: 16px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.detail-workspace-tab__badge {
  display: inline-flex;
  min-width: 18px;
  height: 18px;
  align-items: center;
  justify-content: center;
  border-radius: 999px;
  background: #dbeafe;
  color: #1d4ed8;
  font-size: 10px;
  font-weight: 800;
  padding: 0 5px;
}
</style>
