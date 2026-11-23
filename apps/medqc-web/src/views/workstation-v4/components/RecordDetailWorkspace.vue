<template>
  <div class="record-detail-workspace px-3 pb-4 pt-1.5 lg:px-4 lg:pb-5">
    <div v-if="materialNotice" class="mb-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800" role="status">{{ materialNotice }}</div>
    <a-button
      v-if="selectedRecord"
      class="mq-btn"
      data-testid="business-agent-record-entry"
      @click="emit('open-content-qc')"
    >
      查看质控问题与依据
    </a-button>
    <div
      class="relative mx-auto w-full max-w-[1200px] rounded-[18px] border border-black/10 bg-white/86 px-1 py-1.5 shadow-[0_1px_4px_rgba(0,0,0,0.045),0_2px_8px_rgba(0,0,0,0.035)] lg:px-1.5 lg:py-2"
    >
      <div
        v-if="selectedRecord"
        class="absolute right-4 top-0 flex items-center gap-1 rounded-b-md border-x border-b px-2 py-0.5 text-[10px] font-bold opacity-75"
        :class="
          selectedRecord.status === 'completed'
            ? 'bg-blue-50 text-[#0a6cff] border-blue-100/50'
            : selectedRecord.status === 'has_defects' || selectedRecord.status === 'warning'
              ? 'bg-slate-50 text-slate-500 border-slate-200/70'
              : 'bg-blue-50 text-[#0a6cff] border-blue-100/50'
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

      <HospitalLoading
        v-if="selectedRecord && documentsLoading && !documents?.length"
        label="正在读取病历文书目录"
      />
      <ReadonlyMedicalOrderTable
        v-else-if="activeOrderDocument"
        :documents="orderDocuments"
        :selected-key="activeDocType"
        @select="emit('select-document', $event)"
      />

      <AsyncEMRViewer
        v-else-if="selectedRecord && emrRenderState !== 'fallback'"
        :record-id="selectedRecord.id"
        :visit-id="selectedRecord.visitId || selectedRecord.id"
        :patient-id="selectedRecord.patientId"
        :institute-id="selectedRecord.instituteId"
        :active-doc-key="activeDocType"
        :documents="documents"
        :documents-managed="true"
        :documents-loading="documentsLoading"
        :max-height="760"
        :hide-doc-tabs="true"
        @loaded="emit('emr-loaded', $event)"
        @error="emit('emr-error')"
        @defect-click="emit('emr-defect-click', $event)"
      >
        <template #loading>
          <HospitalLoading label="正在读取文书正文" />
        </template>
      </AsyncEMRViewer>

      <template v-else>
        <HospitalLoading v-if="concatLoading" label="正在读取病历文书" />

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
            class="mb-4 flex items-center gap-2 rounded-[10px] border border-blue-100/80 bg-blue-50/55 px-3 py-2 text-xs text-[#0a5fd6]"
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
                <h3 class="m-0 text-[15px] font-bold text-slate-800">
                  {{ section.title }}
                </h3>
              </span>
              <span class="text-[11px] font-semibold text-[#0a6cff]">
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
                class="medical-record-document__content m-0 whitespace-pre-wrap rounded-[6px] bg-transparent px-0 py-0 font-sans text-[14px] leading-[2.05] text-slate-700"
                >{{ section.content }}</pre
              >
            </div>
          </div>
        </div>

        <div v-else class="flex flex-col items-center justify-center py-20 text-slate-300">
          <div
            class="w-20 h-20 rounded-full bg-white/74 flex items-center justify-center mb-4 border-2 border-dashed border-black/10"
          >
            <FileTextOutlined class="text-3xl" />
          </div>
          <div class="text-sm font-medium mb-1">暂无病历文书</div>
          <div class="text-xs text-slate-400">该患者当前暂无可展示的病历文书内容。</div>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { defineAsyncComponent } from 'vue'
import {
  CheckCircleOutlined,
  FileTextOutlined,
  ThunderboltOutlined,
  WarningOutlined,
} from '@ant-design/icons-vue'
import type { PatientRecord } from '../types'
import type { EditableMedicalRecordDocument } from '../customer-sample-validation/types'
import { isMedicalOrderDocument } from '../customer-sample-validation/medicalDocumentDisplay'
import ReadonlyMedicalOrderTable from '../customer-sample-validation/ReadonlyMedicalOrderTable.vue'
import HospitalLoading from '@/components/qc/HospitalLoading.vue'

interface ConcatSection {
  title: string
  content: string
}

const props = defineProps<{
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
  documents?: Array<{
    id: string
    doc_type: string
    doc_name: string
    doc_key?: string
    execution_domain?: string
    has_content?: boolean
    order_start_time?: string
    order_stop_time?: string
    order_category?: string
    order_item?: string
    order_specification?: string
    order_dosage?: string
    order_frequency?: string
    order_route?: string
    order_quantity?: string
    order_prescribed_doctor?: string
    order_status?: string
  }>
  materialNotice?: string
  documentsLoading: boolean
  isSectionExpanded: (index: number) => boolean
}>()

const orderDocuments = computed<EditableMedicalRecordDocument[]>(() =>
  (props.documents || [])
    .filter((document) =>
      isMedicalOrderDocument(document as unknown as EditableMedicalRecordDocument),
    )
    .map((document, index) => {
      const key = String(document.doc_key || document.id || `order-${index + 1}`)
      return {
        ...(document as unknown as EditableMedicalRecordDocument),
        key,
        document_type: String(document.doc_type || 'inpat_nondrug_order'),
        title: String(document.doc_name || document.doc_type || '医嘱'),
        content: String((document as { content?: string | null }).content || ''),
      }
    }),
)

const activeOrderDocument = computed(() =>
  orderDocuments.value.find((document) => document.key === String(props.activeDocType || '')),
)

const emit = defineEmits<{
  'emr-loaded': [payload: any]
  'emr-error': []
  'emr-defect-click': [payload: any]
  'toggle-expand-all-sections': []
  'toggle-section': [index: number]
  'select-document': [key: string]
  // 打开分析面板的“内涵质控”页签（面板由宿主统一持有）。
  'open-content-qc': []
}>()

const AsyncEMRViewer = defineAsyncComponent(() => import('@/components/qc/EMRViewer.vue'))
</script>

<style scoped>
.record-detail-workspace {
  color: #1d1d1f;
  font-family:
    'Source Han Sans SC', 'San Francisco', 'SF Pro Text', 'SF Pro Display', Inter, 'PingFang SC',
    'Microsoft YaHei UI', 'Microsoft YaHei', system-ui, sans-serif;
}

.record-detail-workspace > div {
  border-color: rgba(0, 0, 0, 0.08) !important;
  background: rgba(255, 255, 255, 0.86) !important;
  -webkit-backdrop-filter: blur(18px);
  backdrop-filter: blur(18px);
  transition:
    border-color 260ms cubic-bezier(0.25, 0.1, 0.25, 1),
    box-shadow 260ms cubic-bezier(0.25, 0.1, 0.25, 1),
    transform 260ms cubic-bezier(0.25, 0.1, 0.25, 1);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.72),
    0 2px 12px rgba(0, 0, 0, 0.055) !important;
}

.record-detail-workspace > div:hover {
  border-color: rgba(0, 0, 0, 0.14) !important;
  transform: translateY(-2px);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.78),
    0 2px 12px rgba(0, 0, 0, 0.1),
    0 6px 22px rgba(0, 0, 0, 0.075) !important;
}

.record-detail-workspace .text-slate-900,
.record-detail-workspace .text-slate-800,
.record-detail-workspace .text-slate-700 {
  color: #1d1d1f !important;
}

.record-detail-workspace .text-slate-600,
.record-detail-workspace .text-slate-500,
.record-detail-workspace .text-slate-400 {
  color: rgba(29, 29, 31, 0.56) !important;
}

.record-detail-workspace .text-slate-300 {
  color: rgba(29, 29, 31, 0.34) !important;
}

.record-detail-workspace .text-\[\#0a6cff\],
.record-detail-workspace .text-blue-400,
.record-detail-workspace .text-\[\#0a5fd6\] {
  color: #0a6cff !important;
}

.record-detail-workspace .bg-blue-50,
.record-detail-workspace .bg-slate-50,
.record-detail-workspace .bg-white {
  background: rgba(255, 255, 255, 0.74) !important;
}

.record-detail-workspace .border-blue-100\/80,
.record-detail-workspace .border-blue-100\/50,
.record-detail-workspace .border-slate-200\/80,
.record-detail-workspace .border-slate-200\/75,
.record-detail-workspace .border-slate-200\/70,
.record-detail-workspace .border-slate-200 {
  border-color: rgba(0, 0, 0, 0.08) !important;
}

.record-detail-workspace .font-bold {
  font-weight: 600 !important;
}

.record-detail-workspace .font-semibold {
  font-weight: 500 !important;
}

.record-detail-workspace .font-mono {
  font-family:
    'SF Pro Text', 'Source Han Sans SC', 'Cascadia Code', 'Roboto Mono', monospace !important;
  font-weight: 600 !important;
}

.record-detail-workspace :deep(.ant-btn) {
  border-color: rgba(0, 0, 0, 0.1) !important;
  background: rgba(255, 255, 255, 0.9) !important;
  color: rgba(29, 29, 31, 0.72) !important;
  font-family: inherit;
  font-size: 12px;
  font-weight: 600;
}

.record-detail-workspace :deep(.ant-btn:hover) {
  border-color: rgba(10, 108, 255, 0.2) !important;
  color: #0a6cff !important;
}

.medical-record-document__content {
  color: rgba(29, 29, 31, 0.82) !important;
  font-family:
    'Source Han Sans SC', 'San Francisco', 'SF Pro Text', 'SF Pro Display', Inter, 'PingFang SC',
    'Microsoft YaHei UI', 'Microsoft YaHei', system-ui, sans-serif !important;
  font-size: 14px !important;
  font-weight: 400;
  line-height: 2 !important;
}

.medical-record-document__content-wrap--collapsed {
  max-height: 260px;
  overflow: hidden;
  -webkit-mask-image: linear-gradient(180deg, #000 72%, transparent);
  mask-image: linear-gradient(180deg, #000 72%, transparent);
}
</style>
