<template>
  <div class="detail-workspace-shell relative z-10 flex-1 flex flex-col min-w-0 h-full">
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
      <div class="detail-workspace-tabs-bar border-b px-4 py-2.5">
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
            type="button"
            class="frontpage-profile-entry"
            title="打开疾病诊断画像、手术操作画像、诊断时间轴和执行验证"
            @click="emit('open-ai-profile')"
          >
            <span class="frontpage-profile-entry__icon"><AuditOutlined /></span>
            <span class="frontpage-profile-entry__main">
              <span>画像辅助</span>
              <small>首页对照</small>
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

        <main class="detail-workspace-main relative flex flex-1 flex-col overflow-hidden">
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
  'open-ai-profile': []
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
.detail-workspace-shell {
  background: #f5f5f7 !important;
  color: #1d1d1f;
  font-family:
    'Source Han Sans SC', 'San Francisco', 'SF Pro Text', 'SF Pro Display', Inter, 'PingFang SC',
    'Microsoft YaHei UI', 'Microsoft YaHei', system-ui, sans-serif;
}

.detail-workspace-tabs-bar {
  border-color: rgba(0, 0, 0, 0.08) !important;
  background: rgba(255, 255, 255, 0.76) !important;
  -webkit-backdrop-filter: blur(18px);
  backdrop-filter: blur(18px);
}

.detail-workspace-main {
  background: #f5f5f7 !important;
}

.detail-workspace-tab {
  display: inline-flex;
  min-width: 188px;
  align-items: center;
  gap: 10px;
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 12px;
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
  background: rgba(255, 255, 255, 0.68);
  color: rgba(29, 29, 31, 0.6);
}

.detail-workspace-tab--idle:hover {
  border-color: rgba(0, 0, 0, 0.12);
  background: rgba(255, 255, 255, 0.92);
  color: #1d1d1f;
  transform: translateY(-1px);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.055);
}

.detail-workspace-tab--active {
  border-color: rgba(43, 108, 246, 0.22);
  background: rgba(43, 108, 246, 0.08);
  color: #1d1d1f;
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.95),
    0 3px 12px rgba(43, 108, 246, 0.08);
}

.detail-workspace-tab__icon {
  display: inline-flex;
  width: 34px;
  height: 34px;
  flex: 0 0 auto;
  align-items: center;
  justify-content: center;
  border-radius: 11px;
  background: rgba(43, 108, 246, 0.08);
  color: #2b6cf6;
  font-size: 17px;
}

.detail-workspace-tab--active .detail-workspace-tab__icon {
  background: #2b6cf6;
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
  font-weight: 650;
  line-height: 18px;
}

.detail-workspace-tab__desc {
  overflow: hidden;
  color: rgba(29, 29, 31, 0.5);
  font-size: 12px;
  font-weight: 500;
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
  background: rgba(43, 108, 246, 0.1);
  color: #2b6cf6;
  font-size: 10px;
  font-weight: 650;
  padding: 0 5px;
}

.frontpage-profile-entry {
  display: inline-flex;
  min-width: 132px;
  align-items: center;
  gap: 8px;
  border: 1px solid rgba(43, 108, 246, 0.16);
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.68);
  color: #2b6cf6;
  cursor: pointer;
  padding: 7px 12px;
  text-align: left;
  transition:
    background-color 160ms ease,
    border-color 160ms ease,
    box-shadow 160ms ease;
}

.frontpage-profile-entry:hover {
  border-color: rgba(43, 108, 246, 0.24);
  background: rgba(255, 255, 255, 0.94);
  box-shadow: 0 3px 12px rgba(43, 108, 246, 0.1);
}

.frontpage-profile-entry__icon {
  display: inline-flex;
  width: 28px;
  height: 28px;
  flex: 0 0 auto;
  align-items: center;
  justify-content: center;
  border-radius: 999px;
  background: #2b6cf6;
  color: #ffffff;
  font-size: 14px;
}

.frontpage-profile-entry__main {
  display: grid;
  min-width: 0;
  gap: 1px;
}

.frontpage-profile-entry__main span {
  color: #2b6cf6;
  font-size: 13px;
  font-weight: 650;
  line-height: 16px;
}

.frontpage-profile-entry__main small {
  color: rgba(29, 29, 31, 0.52);
  font-size: 11px;
  font-weight: 500;
  line-height: 14px;
}
</style>
