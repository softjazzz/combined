<template>
  <div class="workstation-shell relative h-full flex overflow-hidden">
    <!-- ====== 列表模式 ====== -->
    <template v-if="viewMode === 'list'">
      <WorkstationV4ListView
        :active-priority-group="activePriorityGroup"
        :priority-groups="priorityGroups"
        :priority-cards-filtered="priorityCardsFiltered"
        :is-stage-queue-mode="isStageQueueMode"
        :search-text="searchText"
        :date-range="dateRange"
        :date-field="dateField"
        :department-select-options="departmentSelectOptions"
        :quick-departments="quickDepartments"
        :active-dept="activeDept"
        :workbench-rows="workbenchRows"
        :selected-workbench-keys="selectedWorkbenchKeys"
        :table-summary-text="tableSummaryText"
        :display-loading="displayLoading"
        :stage-meta="stageMeta"
        :current-stage-filter="currentStageFilter"
        :list-records="listRecords"
        :stage-empty-text="stageEmptyText"
        :display-server-total-pages="displayServerTotalPages"
        :current-page="currentPage"
        :page-size="pageSize"
        :display-server-total="displayServerTotal"
        @update:active-priority-group="activePriorityGroup = $event"
        @update:search-text="searchText = $event"
        @update:date-range="dateRange = $event"
        @update:date-field="dateField = $event"
        @update:selected-row-keys="selectedWorkbenchKeys = $event"
        @priority-open="handlePriorityOpen"
        @priority-defer="handlePriorityDefer"
        @select-dept="selectDept"
        @open-record="handleRowOpen"
        @batch-extract="handleBatchExtract"
        @batch-defer="handleBatchDefer"
        @batch-assign="handleBatchAssign"
        @clear-filters="handleClearFilters"
        @page-change="handlePageChange"
      />
    </template>
    <!-- ====== 详情模式（全屏） ====== -->
    <template v-else-if="viewMode === 'detail'">
      <div class="relative z-10 flex-1 flex min-w-0 h-full">
        <WorkstationV4DetailView
          :selected-record="selectedRecord"
          :current-record-index="currentRecordIndex"
          :filtered-records-length="filteredRecords.length"
          :frontpage-generating="frontpageGenerating"
          :has-draft="!!frontpageDraft"
          :can-generate-frontpage="canGenerateFrontpage"
          :frontpage-disabled-reason="frontpageDisabledReason"
          :documents-list="documentsList"
          :documents-tree="documentsTree"
          :documents-loading="documentsLoading"
          :active-doc-type="activeDocType"
          :detail-main-tab="detailMainTab"
          :settlement-qc-failed="settlementQcFailed"
          @back="goBackToList"
          @prev="goToPrevRecord"
          @next="goToNextRecord"
          @open-icd="icdDrawerVisible = true"
          @open-ai-profile="openAiProfilePanel"
          @generate-frontpage="handleGenerateFrontpage"
          @preview-doc="openDocPreview"
          @show-concat="showConcatRecord"
          @update:detail-main-tab="detailMainTab = $event"
        >
          <template #records>
            <RecordDetailWorkspace
              :selected-record="selectedRecord"
              :emr-render-state="emrRenderState"
              :concat-loading="concatLoading"
              :concat-text="concatText"
              :concat-sections="concatSections"
              :concat-total-chars="concatTotalChars"
              :all-concat-sections-expanded="allConcatSectionsExpanded"
              :is-section-expanded="isConcatSectionExpanded"
              :active-doc-type="activeDocType"
              :doc-preview-active="!!activeDocType"
              :doc-preview-title="docPreviewTitle"
              :doc-preview-content="docPreviewContent"
              @emr-loaded="handleEmrLoaded"
              @emr-error="handleEmrError"
              @emr-defect-click="handleEmrDefectClick"
              @toggle-expand-all-sections="toggleExpandAllSections"
              @toggle-section="toggleConcatSection"
            />
          </template>
          <template #frontpage>
            <FrontpageWorkspace
              :frontpage-generating="frontpageGenerating"
              :frontpage-post-processing="frontpagePostProcessing"
              :draft="frontpageDraft"
              :frontpage-tab="frontpageTab"
              :frontpage-module-cards="frontpageModuleCards"
              :completed-count="completedModules.length"
              :total-count="ALL_MODULE_KEYS.length"
              :frontpage-sheet-loading="frontpageSheetLoading"
              :frontpage-sheet-data="frontpageSheetData"
              :can-generate-frontpage="canGenerateFrontpage"
              :report-result="frontpageReportResult"
              @generate-frontpage="handleGenerateFrontpage"
              @paste-frontpage="openPasteFrontpageModal"
              @reload-frontpage-sheet="
                selectedRecord?.patientId && selectedRecord?.visitId
                  ? loadFrontpageSheet(selectedRecord.patientId, selectedRecord.visitId)
                  : undefined
              "
              @update:frontpage-tab="frontpageTab = $event"
              @export-frontpage="(format) => handleExportFrontpage(format)"
              @save-frontpage="
                () => {
                  void handleSaveFrontpage()
                }
              "
            />
          </template>
          <template #settlement>
            <SettlementWorkspace
              :settlement-loading="settlementLoading"
              :settlement-data="settlementData"
              :settlement-qc-loading="settlementQcLoading"
              :settlement-qc-report="settlementQcReport"
              :can-generate-settlement="canGenerateSettlement"
              :selected-record="selectedRecord"
              @run-settlement-qc="runSettlementQc"
              @generate-settlement-draft="generateSettlementDraft"
              @reload-settlement="
                selectedRecord?.patientId && selectedRecord?.visitId
                  ? loadSettlement(selectedRecord.patientId, selectedRecord.visitId)
                  : undefined
              "
            />
          </template>
        </WorkstationV4DetailView>

        <WorkstationV4AssistView
          ref="assistViewRef"
          :visible="assistPanelVisible"
          :assist-tab="assistTab"
          :selected-record="selectedRecord"
          :assist-patient-info="assistPatientInfo"
          :content-q-c-count="contentQCCount"
          :assist-badge-count="assistBadgeCount"
          :frontpage-draft="frontpageDraft"
          :frontpage-generating="frontpageGenerating"
          :qc-refresh-seed="qcRefreshSeed"
          :selected-id="selectedId"
          :documents-list="documentsList"
          :notification-unread-count="notificationUnreadCount"
          :profile-analyzed="profileAnalyzed"
          :profile-analyzing="profileAnalyzing"
          :ai-profile-modal-visible="aiProfileModalVisible"
          :combined-medical-text="combinedMedicalText"
          :drg-result="drgResult"
          :drg-loading="drgLoading"
          :drg-detail-modal-visible="drgDetailModalVisible"
          :overview-view-mode="overviewViewMode"
          :overview-department-filter="overviewDepartmentFilter"
          :overview-type-filter="overviewTypeFilter"
          :overview-severity-filter="overviewSeverityFilter"
          :notification-read-filter="notificationReadFilter"
          :overview-departments="overviewDepartments"
          :overview-types="overviewTypes"
          :overview-severities="overviewSeverities"
          :notification-loading="notificationLoading"
          :overview-loading="overviewLoading"
          :filtered-notification-overview-items="filteredNotificationOverviewItems"
          :filtered-assist-notifications="filteredAssistNotifications"
          :format-relative-time="formatRelativeTime"
          :suggestion-drawer-visible="suggestionDrawerVisible"
          :suggestions="suggestions"
          :suggestions-loading="suggestionsLoading"
          :get-suggestion-title="getSuggestionTitle"
          :suggestion-severity-tag="suggestionSeverityTag"
          :icd-drawer-visible="icdDrawerVisible"
          :icd-apply-target="icdApplyTarget"
          :icd-target-options="icdTargetOptions"
          :is-other-target="isOtherTarget"
          :icd-apply-index="icdApplyIndex"
          :icd-apply-label="icdApplyLabel"
          @update:visible="assistPanelVisible = $event"
          @tab-change="handleAssistTabChange"
          @refresh-tab="handleAssistTabRefresh"
          @content-issues-change="contentQCCount = $event"
          @qc-issues-change="(issues) => handleAssistIssuesChange(issues)"
          @locate-field="handleLocateFromQC"
          @jump-evidence="handleJumpEvidenceFromQC"
          @open-ai-profile="openAiProfilePanel"
          @update:ai-profile-modal-visible="aiProfileModalVisible = $event"
          @group-drg="performDRGGrouping"
          @open-optimization="openOptimization"
          @update:drg-detail-modal-visible="drgDetailModalVisible = $event"
          @update:overview-view-mode="overviewViewMode = $event"
          @mark-all-assist-notifications-read="markAllAssistNotificationsRead"
          @update:overview-department-filter="overviewDepartmentFilter = $event"
          @update:overview-type-filter="overviewTypeFilter = $event"
          @update:overview-severity-filter="overviewSeverityFilter = $event"
          @update:notification-read-filter="notificationReadFilter = $event"
          @assist-overview-click="handleAssistOverviewClick"
          @assist-notification-click="handleAssistNotificationClick"
          @mark-assist-notification-read="markAssistNotificationRead"
          @update:suggestion-drawer-visible="suggestionDrawerVisible = $event"
          @drg-suggestion="handleDRGSuggestion"
          @update:icd-drawer-visible="icdDrawerVisible = $event"
          @update:icd-apply-target="icdApplyTarget = $event as typeof icdApplyTarget"
          @update:icd-apply-index="icdApplyIndex = $event"
          @apply-icd-code="handleApplyICDCode"
        />
      </div>
    </template>
    <!-- ====== 质控规则模式 ====== -->
    <template v-else-if="viewMode === 'rules'">
      <WorkstationV4RulesView
        :departments="departments"
        :rules-sub-tab="rulesSubTab"
        :rules-sub-tab-title="rulesSubTabTitle"
        @select-department="
          (dept) => {
            viewMode = 'list'
            selectDept(dept)
          }
        "
        @back="viewMode = 'list'"
      />
    </template>

    <a-modal
      v-model:open="pasteFrontpageModalVisible"
      title="粘贴病历生成首页"
      width="920px"
      :confirm-loading="frontpageGenerating"
      :mask-closable="!frontpageGenerating"
      @cancel="handlePasteFrontpageCancel"
    >
      <div class="space-y-3">
        <a-segmented
          v-model:value="pasteFrontpageScene"
          :options="pasteFrontpageSceneOptions"
          :disabled="frontpageGenerating"
        />
        <div class="paste-frontpage-presets">
          <div class="paste-frontpage-presets__head">
            <span>演示病历</span>
            <small>覆盖首页自动生成、医保清单与卫健委首页上报字段</small>
          </div>
          <div class="paste-frontpage-presets__grid">
            <button
              v-for="preset in pasteFrontpagePresets"
              :key="preset.id"
              type="button"
              class="paste-frontpage-preset"
              :class="{ active: selectedPastePresetId === preset.id }"
              :disabled="frontpageGenerating"
              @click="applyPasteFrontpagePreset(preset.id)"
            >
              <span class="paste-frontpage-preset__title">{{ preset.title }}</span>
              <span class="paste-frontpage-preset__subtitle">{{ preset.subtitle }}</span>
              <span class="paste-frontpage-preset__tags">
                <span
                  v-for="tag in preset.tags"
                  :key="tag"
                >{{ tag }}</span>
              </span>
            </button>
          </div>
        </div>
        <a-textarea
          v-model:value="pastedMedicalText"
          placeholder="粘贴完整病历原文..."
          :auto-size="{ minRows: 12, maxRows: 18 }"
          :maxlength="50000"
          show-count
          :disabled="frontpageGenerating"
        />
        <div
          v-if="frontpageGenerating"
          class="paste-frontpage-progress"
        >
          <FrontpageWorkspacePanel
            :generating="frontpageGenerating"
            :post-processing="frontpagePostProcessing"
            :draft="frontpageDraft"
            :frontpage-tab="frontpageTab"
            :module-cards="frontpageModuleCards"
            :completed-count="completedModules.length"
            :total-count="ALL_MODULE_KEYS.length"
            :sheet-loading="false"
            :sheet-data="null"
          />
        </div>
      </div>

      <template #footer>
        <div class="flex items-center justify-end gap-2">
          <a-button
            :disabled="frontpageGenerating || !pastedMedicalText"
            @click="pastedMedicalText = ''"
          >
            清空
          </a-button>
          <a-button @click="handlePasteFrontpageCancel">
            取消
          </a-button>
          <a-button
            type="primary"
            :loading="frontpageGenerating"
            @click="handleGenerateFrontpageFromText"
          >
            生成首页草稿
          </a-button>
        </div>
      </template>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { defineAsyncComponent, ref, computed, onMounted, watch, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { apiClient } from '@/services/apiService'
import { message, Modal } from 'ant-design-vue'
import {
  WarningOutlined,
  InboxOutlined,
  FileTextOutlined,
  RightOutlined,
  UserOutlined,
  NotificationOutlined,
  ScanOutlined,
} from '@ant-design/icons-vue'
import WorkstationV4ListView from './components/WorkstationV4ListView.vue'
import WorkstationV4DetailView from './components/WorkstationV4DetailView.vue'
import WorkstationV4AssistView from './components/WorkstationV4AssistView.vue'
import WorkstationV4RulesView from './components/WorkstationV4RulesView.vue'
import RecordDetailWorkspace from './components/RecordDetailWorkspace.vue'
import FrontpageWorkspace from './components/FrontpageWorkspace.vue'
import FrontpageWorkspacePanel from './components/FrontpageWorkspacePanel.vue'
import SettlementWorkspace from './components/SettlementWorkspace.vue'
import { useWorkstationRouteEffects } from './workstationRouteEffects'
import { runBatchExtract } from './workstationBatchController'
import {
  createDetailNavigation,
  findRecordById,
  openRecordForStage,
} from './workstationNavigationController'
import {
  resolveStageStatus,
  updateBatchRuntimeStatuses,
  updateSingleBatchRuntimeStatus,
} from './workstationQueueStatusController'
import type { BatchRuntimeStatus } from './workstationQueueStatusController'
import {
  buildSnapshotState,
  mapWorklistItemToRecord,
  normalizeStageDepartments,
  snapshotEndpoint,
  stageWorklistEndpoint,
} from './workstationDataController'
import type { SnapshotTabKey, StageWorklistResponse } from './workstationDataController'
import {
  QUEUE_STATUS_LABEL_MAP,
  aggregatedStageWorkflows,
  getStageMeta,
  workflowLabelMap,
} from './workstationStageController'
import {
  buildDepartmentSelectOptions,
  buildQuickDepartments,
  buildWorkstationFilterSummary,
} from './utils/workstationFilterPresentation'
import { useDRGGrouping } from './composables/useDRGGrouping'
import type { ICDCodeDetail } from './components/ICDDetailPanel.vue'
import { useWorkstationSession } from './composables/useWorkstationSession'
import { useFrontpageDraft } from './composables/useFrontpageDraft'
import { useQcPipeline } from './composables/useQcPipeline'
import { usePatientRecords } from './composables/usePatientRecords'
import { useNotifications } from './composables/useNotifications'
import { pasteFrontpagePresets } from './data/pasteFrontpagePresets'
import {
  canGenerateFrontpageDraft,
  canGenerateSettlementDraft,
  getFrontpageDraftDisabledReason,
} from './frontpageAvailability'
import { normalizeWorklistItem } from './normalize'
import { parseDocSortTime, resolveDocDisplayTitle } from './utils/documentDisplay'
import type {
  PatientRecord,
  DeptInfo,
  DocItem,
  DocTreeGroup,
  DocTreeNode,
  FrontpageFocusTarget,
  QCIssueLike,
  WorkstationWorklistItem,
  WorkstationSnapshotState,
} from './types'
import type { PriorityCard, PriorityGroup } from './components/workbench/PriorityLane.vue'
import type { WorkbenchRow } from './components/workbench/BatchTablePanel.vue'
import type { WorkstationLaunchAction, WorkflowStageKey } from '@/types/workflow'
import type { FrontpageReportScene } from '@/api/frontpage'

const {
  viewMode,
  selectedId,
  frontpageTab,
  assistPanelVisible,
  assistTab,
  icdDrawerVisible,
  icdApplyTarget,
  icdApplyIndex,
  isOtherTarget,
  openRecord: openSessionRecord,
  goBackToList: backToList,
  resetPerRecordTransient,
} = useWorkstationSession()

const route = useRoute()
const router = useRouter()

const {
  allRecords,
  departments,
  currentPage,
  pageSize,
  serverTotal,
  serverTotalPages,
  loading,
  activeDept,
  searchText,
  dateRange,
  dateField,
  hospFilter,
  hospOptions,
  filteredRecords,
  fetchData,
  handlePageChange: handleBasePageChange,
  refreshData,
  selectDept,
  resetFilters,
} = usePatientRecords()
const departmentSelectOptions = computed(() =>
  buildDepartmentSelectOptions(displayDepartments.value),
)

const quickDepartments = computed(() =>
  buildQuickDepartments(displayDepartments.value, activeDept.value),
)

const stageQueues = computed(() => {
  const records = filteredRecords.value
  const generateQueue = records.filter((record) => hasAdmissionRecord(record))
  const codingQcQueue = records.filter((record) => hasFrontpageOfficialRecord(record))
  const frontpageQcQueue = records.filter((record) => hasFrontpageOfficialRecord(record))
  const settlementQcQueue = records.filter((record) => hasSettlementOfficialRecord(record))

  return {
    frontpage_generate: generateQueue,
    coding_qc: codingQcQueue,
    frontpage_qc: frontpageQcQueue,
    settlement_qc: settlementQcQueue,
  }
})

const currentStageFilter = computed<WorkflowStageKey | ''>(() => {
  const stage = String(route.query.stage || '').trim()
  return validStages.includes(stage as WorkflowStageKey) ? (stage as WorkflowStageKey) : ''
})

const stageWorklistItems = ref<WorkstationWorklistItem[]>([])
const stageDepartments = ref<DeptInfo[]>([])
const stageServerTotal = ref(0)
const stageServerTotalPages = ref(1)
const stageLoading = ref(false)
const batchExtracting = ref(false)
const batchRuntimeStatusMap = ref<Record<string, BatchRuntimeStatus>>({})
const selectedStageRecord = ref<PatientRecord | null>(null)
const qcSnapshotState = ref<Partial<Record<SnapshotTabKey, WorkstationSnapshotState>>>({})

const isAggregatedStageMode = computed(() =>
  Boolean(aggregatedStageWorkflows[currentStageFilter.value]),
)

const displayDepartments = computed(() =>
  isAggregatedStageMode.value ? stageDepartments.value : departments.value,
)

const displayLoading = computed(
  () => (isAggregatedStageMode.value ? stageLoading.value : loading.value) || batchExtracting.value,
)

const displayServerTotal = computed(() =>
  isAggregatedStageMode.value ? stageServerTotal.value : serverTotal.value,
)

const displayServerTotalPages = computed(() =>
  isAggregatedStageMode.value ? stageServerTotalPages.value : serverTotalPages.value,
)

const isStageQueueMode = computed(() => Boolean(currentStageFilter.value))

const stageMeta = computed(() => getStageMeta(currentStageFilter.value))

async function fetchStageWorklist(stage: WorkflowStageKey | '') {
  const endpoint = stageWorklistEndpoint(stage)
  if (!endpoint) {
    stageWorklistItems.value = []
    stageDepartments.value = []
    stageServerTotal.value = 0
    stageServerTotalPages.value = 1
    return
  }

  stageLoading.value = true
  try {
    const { data } = await apiClient.get<StageWorklistResponse>(endpoint, {
      params: {
        page: currentPage.value,
        page_size: pageSize.value,
        department: activeDept.value === '全部科室' ? undefined : activeDept.value,
        keyword: searchText.value.trim() || undefined,
      },
    })
    const payload = data?.data || {}
    const items = Array.isArray(payload.items) ? payload.items : []
    stageWorklistItems.value = items.map((item) => normalizeWorklistItem(item))
    stageServerTotal.value = Number(payload.total || 0)
    stageServerTotalPages.value = Math.max(
      1,
      Number(
        payload.total_pages ||
          Math.ceil(
            Number(payload.total || 0) / Math.max(1, Number(payload.page_size || pageSize.value)),
          ),
      ),
    )
    stageDepartments.value = normalizeStageDepartments(payload.departments, stageServerTotal.value)
  } catch (error) {
    console.error('加载聚合工作台数据失败:', error)
    stageWorklistItems.value = []
    stageDepartments.value = [{ name: '全部科室', total: 0, warningCount: 0 }]
    stageServerTotal.value = 0
    stageServerTotalPages.value = 1
  } finally {
    stageLoading.value = false
  }
}

async function refreshActiveWorklist() {
  if (!isAggregatedStageMode.value) return
  await fetchStageWorklist(currentStageFilter.value)
}

async function refreshSelectedSnapshots() {
  if (!selectedId.value) {
    qcSnapshotState.value = {}
    return
  }
  const visitId = selectedId.value
  const workflows: Array<[SnapshotTabKey, WorkstationWorklistItem['workflowType']]> = [
    ['form', 'frontpage'],
    ['coding', 'coding'],
    ['cost', 'settlement'],
  ]

  const nextState: Partial<Record<SnapshotTabKey, WorkstationSnapshotState>> = {}
  await Promise.all(
    workflows.map(async ([tabKey, workflow]) => {
      try {
        const { data } = await apiClient.get(snapshotEndpoint(workflow, visitId))
        const payload = data?.data || data
        nextState[tabKey] = buildSnapshotState(payload, tabKey, workflow, workflowLabelMap)
        if (tabKey === 'cost' && payload?.latest_qc_result?.raw_output) {
          settlementQcReport.value = payload.latest_qc_result.raw_output as any
        }
      } catch (error) {
        console.warn(`加载 ${workflow} snapshot 失败:`, error)
      }
    }),
  )
  qcSnapshotState.value = nextState
}

const stageStatusText = computed(() => {
  if (currentStageFilter.value === 'frontpage_generate')
    return QUEUE_STATUS_LABEL_MAP.frontpage_generate.pending
  if (currentStageFilter.value === 'coding_qc') return QUEUE_STATUS_LABEL_MAP.coding.pending
  if (currentStageFilter.value === 'frontpage_qc') return QUEUE_STATUS_LABEL_MAP.frontpage.pending
  if (currentStageFilter.value === 'settlement_qc') return QUEUE_STATUS_LABEL_MAP.settlement.pending
  return '待处理'
})

const stageStatusClass = computed(() => {
  if (currentStageFilter.value === 'frontpage_generate') {
    return 'border-sky-200 bg-sky-50 text-sky-700'
  }
  if (currentStageFilter.value === 'coding_qc') {
    return 'border-violet-200 bg-violet-50 text-violet-700'
  }
  if (currentStageFilter.value === 'frontpage_qc') {
    return 'border-emerald-200 bg-emerald-50 text-emerald-700'
  }
  if (currentStageFilter.value === 'settlement_qc') {
    return 'border-amber-200 bg-amber-50 text-amber-700'
  }
  return 'border-slate-200 bg-slate-50 text-slate-600'
})

const stageEmptyText = computed(() => {
  if (currentStageFilter.value === 'frontpage_generate') return '当前筛选条件下暂无待生成首页病历'
  if (currentStageFilter.value === 'coding_qc') return '当前筛选条件下暂无待编码质控病历'
  if (currentStageFilter.value === 'frontpage_qc') return '当前筛选条件下暂无待首页质控病历'
  if (currentStageFilter.value === 'settlement_qc') return '当前筛选条件下暂无待结算清单质控病历'
  return '当前筛选条件下暂无病历数据'
})

const DEMO_HOME_RECORD_ORDER = ['V-ZS-001', 'V-LM-001']
const DEMO_HOME_RECORD_ORDER_MAP = new Map(DEMO_HOME_RECORD_ORDER.map((id, index) => [id, index]))
const DEMO_HOME_RECORD_ID_SET = new Set(DEMO_HOME_RECORD_ORDER)
const DEMO_HOME_NAME_MAP: Record<string, string> = {
  'V-ZS-001': '寮犱笁',
  'V-LM-001': '鏉庢槑',
}

const stageListRecords = computed<PatientRecord[]>(() =>
  stageWorklistItems.value.map((item) => mapWorklistItemToRecord(item)),
)

const listRecords = computed(() => {
  if (isAggregatedStageMode.value) {
    return stageListRecords.value
  }
  const sourceRecords = currentStageFilter.value
    ? stageQueues.value[currentStageFilter.value] || []
    : filteredRecords.value
  const demoIdsInView = new Set(
    sourceRecords
      .filter((record) => record.isDemoRecord && DEMO_HOME_RECORD_ID_SET.has(record.id))
      .map((record) => record.id),
  )
  if (!demoIdsInView.size) return sourceRecords
  return sourceRecords.filter((record) => {
    if (!demoIdsInView.has(record.id)) return true
    return record.isDemoRecord === true
  })
})

function isDemoRecord(record: PatientRecord): boolean {
  return record.isDemoRecord === true
}

function displayRecordName(record: PatientRecord): string {
  const rawName = String(record.name || '').trim()
  if (isDemoRecord(record)) {
    const normalized = rawName.replace(/\s+/g, '')
    if (normalized.length >= 2 && normalized.length <= 3) return normalized
    return DEMO_HOME_NAME_MAP[record.id] || normalized || '演示患者'
  }
  return rawName || '未知患者'
}

function hasAdmissionRecord(record: PatientRecord): boolean {
  return (
    Boolean(record.hasAdmission) ||
    Boolean(record.admissionDate && record.admissionDate.trim() !== '') ||
    Boolean(record.visitId || record.id)
  )
}

function hasFrontpageOfficialRecord(record: PatientRecord): boolean {
  if (typeof record.hasFrontpageOfficial === 'boolean') return record.hasFrontpageOfficial
  if (typeof record.cdmFrontpageEmpty === 'boolean') return !record.cdmFrontpageEmpty
  return false
}

function hasSettlementOfficialRecord(record: PatientRecord): boolean {
  if (typeof record.hasSettlementOfficial === 'boolean') return record.hasSettlementOfficial
  return false
}

async function handleStageRecordAction(record: PatientRecord) {
  const action = stageMeta.value.action
  if (action === 'open_record') {
    openRecord(record)
    return
  }
  openRecord(record)
  await nextTick()
  if (action === 'generate_frontpage') {
    detailMainTab.value = 'records'
    return
  }
  if (action === 'qc_coding') {
    detailMainTab.value = 'frontpage'
    assistPanelVisible.value = true
    assistTab.value = 'coding'
    assistViewRef.value?.runCodingQC()
    return
  }
  if (action === 'qc_frontpage') {
    detailMainTab.value = 'frontpage'
    assistPanelVisible.value = true
    assistTab.value = 'form'
    assistViewRef.value?.runFormQC()
    return
  }
  if (action === 'qc_settlement') {
    detailMainTab.value = 'settlement'
    if (!isDischarged.value) {
      message.warning('当前病历未出院，暂不可执行结算质控')
      return
    }
    await runSettlementQc()
    assistPanelVisible.value = true
    assistTab.value = 'cost'
    return
  }
}

const activePriorityGroup = ref('all')
const selectedWorkbenchKeys = ref<string[]>([])

function priorityScore(record: PatientRecord) {
  let score = 0
  const days = record.days || 0
  const isDischarged = Boolean(record.dischargeDate && record.dischargeDate.trim() !== '')
  const cdmFrontpageEmpty = Boolean(record.cdmFrontpageEmpty)

  // 鏈€楂樹紭鍏堬細宸插嚭闄絾 CDM 鐥呮棣栭〉浠嶄负绌猴紙褰卞搷涓婃姤涓庡尰淇濇彁浜ゆ祦杞級
  if (isDischarged && cdmFrontpageEmpty) score += 200
  // 娆′紭鍏堬細宸插嚭闄絾浣忛櫌澶╂暟杈冮暱
  if (isDischarged) score += 50

  score += Math.min(days * 2, 40)
  return score
}

function riskTypeOf(record: PatientRecord): string {
  if (isDemoRecord(record)) return 'demo'
  const isDischarged = Boolean(record.dischargeDate && record.dischargeDate.trim() !== '')
  if (isDischarged && Boolean(record.cdmFrontpageEmpty)) return 'incomplete'
  if (isDischarged && (record.days || 0) >= 8) return 'timeout'
  if (record.status === 'warning' || record.status === 'has_defects') return 'ai_failed'
  return 'normal'
}

function priorityReason(record: PatientRecord) {
  void record
  return ''
}

const priorityCards = computed<PriorityCard[]>(() => {
  const pinnedDemoRecords = [...listRecords.value]
    .filter((record) => isDemoRecord(record) && DEMO_HOME_RECORD_ID_SET.has(record.id))
    .sort(
      (a, b) =>
        (DEMO_HOME_RECORD_ORDER_MAP.get(a.id) ?? 99) - (DEMO_HOME_RECORD_ORDER_MAP.get(b.id) ?? 99),
    )
  const pinnedSet = new Set(pinnedDemoRecords.map((record) => record.id))
  const rankedNormalRecords = [...listRecords.value]
    .filter((record) => !pinnedSet.has(record.id))
    .sort((a, b) => priorityScore(b) - priorityScore(a))
  return [...pinnedDemoRecords, ...rankedNormalRecords].map((record) => ({
    id: record.id,
    patientName: displayRecordName(record),
    visitId: record.id,
    department: record.department || '未分科室',
    hospitalDays: Number(record.days || 0),
    riskType: riskTypeOf(record),
    riskText: priorityReason(record),
    isDemo: isDemoRecord(record),
    updatedAt:
      record.sortTime || record.updateTime || record.dischargeDate || record.admissionDate || '',
  }))
})

const priorityGroups = computed<PriorityGroup[]>(() => {
  const counters = {
    all: priorityCards.value.length,
    timeout: 0,
    incomplete: 0,
    ai_failed: 0,
    demo: 0,
  }
  priorityCards.value.forEach((card) => {
    if (card.riskType in counters) {
      counters[card.riskType as keyof typeof counters] += 1
    }
  })
  return [
    { key: 'all', label: '全部', count: counters.all },
    { key: 'timeout', label: '超时风险', count: counters.timeout },
    { key: 'incomplete', label: '资料不全', count: counters.incomplete },
    { key: 'ai_failed', label: 'AI抽取失败', count: counters.ai_failed },
    { key: 'demo', label: 'Demo演示', count: counters.demo },
  ]
})

const priorityCardsFiltered = computed(() => {
  if (activePriorityGroup.value === 'all') return priorityCards.value.slice(0, 8)
  return priorityCards.value
    .filter((card) => card.riskType === activePriorityGroup.value)
    .slice(0, 8)
})

const totalVisibleCount = computed(() => displayServerTotal.value || listRecords.value.length)
const activeHospLabel = computed(
  () => hospOptions.find((option) => option.value === hospFilter.value)?.label || '全部',
)
const scopeStatusText = computed(() => {
  const parts = [activeDept.value]
  if (activeHospLabel.value !== '全部') {
    parts.push(activeHospLabel.value)
  }
  if (currentStageFilter.value) {
    parts.push(stageMeta.value.tableTitle)
  }
  return parts.join(' / ')
})

function setBatchRuntimeStatus(
  stage: WorkflowStageKey | '',
  visitIds: string[],
  status: BatchRuntimeStatus,
) {
  batchRuntimeStatusMap.value = updateBatchRuntimeStatuses(
    batchRuntimeStatusMap.value,
    stage,
    visitIds,
    status,
  )
}

function setSingleBatchRuntimeStatus(
  stage: WorkflowStageKey | '',
  visitId: string,
  status: BatchRuntimeStatus,
) {
  batchRuntimeStatusMap.value = updateSingleBatchRuntimeStatus(
    batchRuntimeStatusMap.value,
    stage,
    visitId,
    status,
  )
}

const workbenchRows = computed<WorkbenchRow[]>(() => {
  if (isAggregatedStageMode.value) {
    return stageWorklistItems.value.map((item) => ({
      id: item.visitId,
      patientName: item.patientName,
      patientSex: item.patientSex,
      patientAge: item.patientAge,
      visitId: item.visitId,
      department: item.department || '未分科室',
      stageStatus: resolveStageStatus({
        stage: currentStageFilter.value,
        visitId: item.visitId,
        fallback: item.queueStatus || 'pending',
        runtimeStatusMap: batchRuntimeStatusMap.value,
        workflowType: item.workflowType,
      }),
      riskReason: item.riskReason || '',
      admissionDate: item.admissionDate || '-',
      dischargeDate: item.dischargeDate || '-',
      updatedAt:
        item.latestQcTime ||
        item.notificationUpdatedAt ||
        item.dischargeDate ||
        item.admissionDate ||
        '-',
      isDemo: false,
    }))
  }

  return listRecords.value.map((record) => ({
    id: record.id,
    patientName: displayRecordName(record),
    patientSex: record.sex,
    patientAge: record.age,
    visitId: record.id,
    department: record.department || '未分科室',
    stageStatus: resolveStageStatus({
      stage: currentStageFilter.value,
      visitId: record.id,
      fallback:
        currentStageFilter.value === 'frontpage_generate' && record.frontpageGenerateQueueStatus
          ? record.frontpageGenerateQueueStatus
          : stageStatusText.value,
      runtimeStatusMap: batchRuntimeStatusMap.value,
      record,
    }),
    riskReason: priorityReason(record),
    admissionDate: record.admissionDate || '-',
    dischargeDate: record.dischargeDate || '-',
    updatedAt:
      record.sortTime || record.updateTime || record.dischargeDate || record.admissionDate || '-',
    isDemo: isDemoRecord(record),
  }))
})

const tableSummaryText = computed(() => {
  const baseSummary = buildWorkstationFilterSummary({
    activeDept: activeDept.value,
    dateField: dateField.value,
    dateRange: dateRange.value,
    total: displayServerTotal.value,
    stageTitle: stageMeta.value.tableTitle,
    isStageQueueMode: isStageQueueMode.value,
  })
  if (activeHospLabel.value === '全部') return baseSummary
  return `${baseSummary} / ${activeHospLabel.value}`
})

// ========== 质控规则 Tab ==========
const rulesSubTab = ref<'coding' | 'frontpage' | 'settlement'>('coding')
const rulesSubTabTitle = computed(() => {
  const map: Record<string, string> = {
    coding: '编码质控规则管理',
    frontpage: '首页质控规则管理',
    settlement: '结算清单质控规则管理',
  }
  return map[rulesSubTab.value] || '质控规则管理'
})

const rulesSubTabSubtitle = computed(() => {
  const map: Record<string, string> = {
    coding: '按编码规范维护规则，聚焦主诊断、手术操作与编码逻辑一致性。',
    frontpage: '按病案首页字段维护规则，聚焦完整性、口径一致性与填写规范。',
    settlement: '按结算清单数据维护规则，聚焦费用字段、必填项与清单逻辑校验。',
  }
  return map[rulesSubTab.value] || ''
})

const rulesSubTabDescription = computed(() => {
  const map: Record<string, string> = {
    coding: '基于 ICD 编码规范的质控规则，覆盖诊断与手术编码的完整性、格式与逻辑校验。',
    frontpage: '基于病案首页数据的质控规则，校验首页字段的完整性、一致性和填写规范。',
    settlement: '针对医保结算清单数据的质控规则，覆盖必填项校验及清单逻辑一致性检查。',
  }
  return map[rulesSubTab.value] || ''
})

// ========== ?? Tab ???? ==========
const contentQCCount = ref(0)

// ========== 质控 Tab 独立刷新 ==========
const assistViewRef = ref<InstanceType<typeof WorkstationV4AssistView> | null>(null)

function handleAssistTabRefresh(tabKey: string) {
  if (tabKey === 'form' || tabKey === 'cost') {
    assistViewRef.value?.runFormQC()
  } else if (tabKey === 'coding') {
    assistViewRef.value?.runCodingQC()
  } else if (tabKey === 'drg') {
    performDRGGrouping()
  } else if (tabKey === 'content') {
    message.info('内涵质控将在后续版本支持独立刷新')
  }
}

const icdTargetOptions = [
  { label: '主诊断编码', value: 'mainDiagnosis' },
  { label: '其他诊断编码', value: 'otherDiagnosis' },
  { label: '主手术编码', value: 'mainProcedure' },
  { label: '其他手术编码', value: 'otherProcedure' },
]

const {
  drgLoading,
  drgResult,
  suggestionDrawerVisible,
  suggestionsLoading,
  suggestions,
  performDRGGrouping: doDRGGrouping,
  openOptimizationDrawer,
  handleSuggestion,
  getSuggestionTitle,
} = useDRGGrouping()

// ========== 娑堟伅閫氱煡锛堟潵鑷?composable锛?==========
const {
  assistNotifications,
  notificationUnreadCount,
  notificationLoading,
  notificationReadFilter,
  overviewLoading,
  overviewViewMode,
  overviewTypeFilter,
  overviewSeverityFilter,
  overviewDepartmentFilter,
  filteredNotificationOverviewItems,
  overviewDepartments,
  overviewTypes,
  overviewSeverities,
  filteredAssistNotifications,
  fetchAssistNotifications,
  markAssistNotificationRead,
  markAllAssistNotificationsRead,
  handleAssistNotificationClick,
  handleAssistOverviewClick,
  formatRelativeTime,
} = useNotifications(allRecords, openSessionRecord, assistPanelVisible, assistTab, frontpageTab)

const AsyncEMRViewer = defineAsyncComponent(() => import('@/components/qc/EMRViewer.vue'))
const AsyncAIProfileDashboard = defineAsyncComponent(
  () => import('@/views/workstation-v4/frontpage/components/AIProfileDashboard.vue'),
)
const AsyncDRGGroupingTab = defineAsyncComponent(
  () => import('@/views/workstation-v4/frontpage/components/DRGGroupingTab.vue'),
)

// ========== 鐥呭巻鏂囦功棰勮 ==========
const documentsList = ref<DocItem[]>([])
const documentsTree = ref<DocTreeGroup[]>([])
const documentsLoading = ref(false)
const activeDocType = ref<string>('')
const docPreviewTitle = ref('')
const docPreviewContent = ref('')

// ========== 详情主 Tab ==========
type DetailMainTab = 'records' | 'frontpage' | 'settlement' | 'completeness'
const detailMainTab = ref<DetailMainTab>('records')
const pendingDetailMainTab = ref<DetailMainTab | null>(null)
const emrRenderState = ref<'idle' | 'loading' | 'ready' | 'fallback'>('idle')

// ========== 鐥呭巻璇︽儏锛堟嫾鎺ユ枃涔︼級 ==========
const concatText = ref('')
const concatLoading = ref(false)

function buildConcatTextFromDocuments(docs: DocItem[]): string {
  const available = (docs || []).filter((doc) => doc.has_content && doc.content)
  if (!available.length) return ''
  const sorted = [...available].sort((a, b) => {
    const ta = parseDocSortTime(a.sort_time)
    const tb = parseDocSortTime(b.sort_time)
    if (ta !== tb) return ta - tb
    const ida = String(a.document_id || '')
    const idb = String(b.document_id || '')
    return ida.localeCompare(idb, 'zh-CN')
  })
  const sep = '='.repeat(40)
  return sorted
    .map((doc) => `${sep}\n${resolveDocDisplayTitle(doc, true)}\n${sep}\n\n${doc.content || ''}`)
    .join('\n\n\n')
}

const concatSections = computed(() => {
  if (!concatText.value) return []
  const sections: { title: string; content: string }[] = []
  const pattern =
    /={40}\s*\r?\n(?:馃搵\s*)?([^\r\n]+)\r?\n={40}\s*\r?\n\r?\n([\s\S]*?)(?=(?:\r?\n){3}={40}|$)/g

  for (const match of concatText.value.matchAll(pattern)) {
    const [, rawTitle = '', rawContent = ''] = match
    sections.push({
      title: rawTitle.trim(),
      content: rawContent.trim(),
    })
  }

  if (!sections.length) {
    sections.push({
      title: '完整病历',
      content: concatText.value.trim(),
    })
  }

  return sections
})
const expandedConcatSectionIndexes = ref<Set<number>>(new Set())
const concatTotalChars = computed(() =>
  concatSections.value.reduce((sum, section) => sum + (section.content?.length || 0), 0),
)
const allConcatSectionsExpanded = computed(
  () =>
    concatSections.value.length > 0 &&
    concatSections.value.every((_, index) => expandedConcatSectionIndexes.value.has(index)),
)

function isConcatSectionExpanded(index: number) {
  return expandedConcatSectionIndexes.value.has(index)
}

function toggleConcatSection(index: number) {
  const next = new Set(expandedConcatSectionIndexes.value)
  if (next.has(index)) {
    next.delete(index)
  } else {
    next.add(index)
  }
  expandedConcatSectionIndexes.value = next
}

function toggleExpandAllSections() {
  if (allConcatSectionsExpanded.value) {
    expandedConcatSectionIndexes.value = new Set()
    return
  }
  expandedConcatSectionIndexes.value = new Set(concatSections.value.map((_, index) => index))
}

// ========== 缁撶畻娓呭崟 ==========
const settlementData = ref<any>(null)
const settlementLoading = ref(false)
const settlementQcReport = ref<any>(null)
const settlementQcLoading = ref(false)

// ========== 鐥呮棣栭〉瀹樻柟鏍煎紡鏁版嵁 ==========
const frontpageSheetData = ref<any>(null)
const frontpageSheetLoading = ref(false)
const pasteFrontpageModalVisible = ref(false)
const pastedMedicalText = ref('')
const pasteFrontpageScene = ref<FrontpageReportScene>('combined')
const selectedPastePresetId = ref('')
const pasteFrontpageSceneOptions = [
  { label: '联合草稿', value: 'combined' },
  { label: '病案首页', value: 'nhc_frontpage' },
  { label: '医保清单', value: 'insurance_settlement' },
]

async function loadFrontpageSheet(patientId: string, visitId: string) {
  frontpageSheetLoading.value = true
  try {
    const { data } = await apiClient.get(
      `/api/medical-records/frontpage-sheet/${patientId}/${visitId}`,
    )
    frontpageSheetData.value = data ?? null
  } catch (e: any) {
    if (e?.response?.status !== 404) {
      console.error('加载病案首页数据失败:', e)
    }
    frontpageSheetData.value = null
  } finally {
    frontpageSheetLoading.value = false
  }
}
const settlementQcFailed = computed(() => settlementQcReport.value?.summary?.failed || 0)

// ========== 鍔熻兘鍙敤鎬у垽鏂紙PRD 6锛?==========
// AI 鐢熸垚棣栭〉锛氬湪闄㈡偅鑰呬篃鍏佽鐢熸垚鍙傝€冭崏绋匡紝宸叉湁棣栭〉鏁版嵁鏃跺脊纭妗?
const isDischarged = computed(() => !!selectedRecord.value?.dischargeDate)
const hasExistingFrontpage = computed(() => !!frontpageSheetData.value)
const canGenerateFrontpage = computed(() =>
  canGenerateFrontpageDraft(selectedRecord.value, documentsList.value, combinedMedicalText.value),
)
const frontpageDisabledReason = computed(() =>
  getFrontpageDraftDisabledReason(
    selectedRecord.value,
    documentsList.value,
    combinedMedicalText.value,
  ),
)
function handleGenerateFrontpage() {
  if (hasExistingFrontpage.value) {
    Modal.confirm({
      title: '该患者已有病案首页数据',
      content: '重新生成将覆盖已有的首页数据，是否继续？',
      okText: '重新生成',
      cancelText: '取消',
      onOk: () => {
        detailMainTab.value = 'frontpage'
        generateFrontpage()
      },
    })
  } else {
    detailMainTab.value = 'frontpage'
    generateFrontpage()
  }
}

function openPasteFrontpageModal() {
  detailMainTab.value = 'frontpage'
  pasteFrontpageModalVisible.value = true
}

function applyPasteFrontpagePreset(presetId: string) {
  const preset = pasteFrontpagePresets.find((item) => item.id === presetId)
  if (!preset) return
  selectedPastePresetId.value = preset.id
  pastedMedicalText.value = preset.text
  pasteFrontpageScene.value = preset.scene
  message.success(`已填入${preset.title}`)
}

function handlePasteFrontpageCancel() {
  if (frontpageGenerating.value) return
  pasteFrontpageModalVisible.value = false
}

async function handleGenerateFrontpageFromText() {
  if (!pastedMedicalText.value.trim()) {
    message.warning('请先粘贴病历原文')
    return
  }

  detailMainTab.value = 'frontpage'
  let previewReleased = false
  const releasePreview = () => {
    if (previewReleased) return
    previewReleased = true
    frontpageTab.value = defaultPreviewTab.value
    pasteFrontpageModalVisible.value = false
    pastedMedicalText.value = ''
    selectedPastePresetId.value = ''
  }
  const generated = await generateFrontpageFromText(
    pastedMedicalText.value,
    pasteFrontpageScene.value,
    {
      onPreviewReady: releasePreview,
    },
  )
  if (!generated) return

  releasePreview()
}
// 缁撶畻娓呭崟鐢熸垚锛氫粎瀵瑰凡鍑洪櫌涓旀棤缁撶畻鏁版嵁鐨勭梾鍘嗗彲鐢?
const hasExistingSettlement = computed(
  () => !!settlementData.value && settlementData.value?.data_source !== 'generated_from_frontpage',
)
const canGenerateSettlement = computed(() =>
  canGenerateSettlementDraft(selectedRecord.value, hasExistingSettlement.value),
)

const costColumns = [
  { title: '收费类别', dataIndex: 'type', width: 120 },
  { title: '等级', dataIndex: 'level', width: 80 },
  { title: '实收金额', dataIndex: 'charge', width: 100 },
  { title: '甲类', dataIndex: 'class_a_amount', width: 80 },
  { title: '乙类', dataIndex: 'class_b_amount', width: 80 },
  { title: '自费', dataIndex: 'own_pay_amount', width: 80 },
]

const settlementBasicFields = computed(() => {
  const d = settlementData.value
  if (!d) return []
  return [
    { label: '患者姓名', value: d.patient_name },
    { label: '性别', value: d.patient_sex },
    { label: '年龄', value: d.patient_age },
    { label: '医保类型', value: d.patient_insurance_type || d.insurance_type },
    { label: '病案号', value: d.mr_no },
    { label: '住院号', value: d.inpat_no },
  ]
})

const settlementHospFields = computed(() => {
  const d = settlementData.value
  if (!d) return []
  return [
    { label: '入院科室', value: d.admission_dept_name },
    { label: '出院科室', value: d.discharge_dept_name },
    { label: '入院时间', value: d.admission_datetime },
    { label: '出院时间', value: d.discharge_datetime },
    { label: '入院途径', value: d.admission_route },
    { label: '离院方式', value: d.leaving_hospital_way },
  ]
})

const settlementInsurFields = computed(() => {
  const d = settlementData.value
  if (!d) return []
  return [
    { label: '参保地', value: d.insured_place },
    { label: '个人自付', value: d.out_of_pocket_advance },
    { label: '个人自费', value: d.out_of_pocket_amount },
    { label: '个人现金支付', value: d.cash_payment_amount },
    { label: '医保支付方式', value: d.insurance_type },
    { label: '结算状态', value: d.settlement_status },
  ]
})

const settlementDataVisitKey = ref('')

async function loadSettlement(patientId: string, visitId: string) {
  settlementLoading.value = true
  settlementData.value = null
  settlementQcReport.value = null
  settlementDataVisitKey.value = ''
  try {
    const { data } = await apiClient.get(`/api/medical-records/settlement/${patientId}/${visitId}`)
    settlementData.value = data
    settlementDataVisitKey.value = `${patientId}::${visitId}`
  } catch (err: any) {
    if (err?.response?.status === 404) {
      // Fallback: 浠庨椤垫娊鍙栫粨鏋滀笌 CDM SQL 鐢熸垚鑽夌
      try {
        const { data: draft } = await apiClient.post(
          `/api/medical-records/settlement/${patientId}/${visitId}/generate`,
        )
        settlementData.value = draft
        settlementDataVisitKey.value = `${patientId}::${visitId}`
      } catch (genErr: any) {
        if (genErr?.response?.status !== 404) {
          console.warn('鑽夌鐢熸垚涔熷け璐ワ紝鏄剧ず绌虹櫧鏍疯〃:', genErr)
        }
      }
    } else {
      console.error('加载结算清单失败:', err)
    }
  } finally {
    settlementLoading.value = false
  }
}

async function generateSettlementDraft() {
  if (!selectedRecord.value?.patientId || !selectedRecord.value?.visitId) return
  settlementLoading.value = true
  settlementQcReport.value = null
  try {
    const { data } = await apiClient.post(
      `/api/medical-records/settlement/${selectedRecord.value.patientId}/${selectedRecord.value.visitId}/generate`,
    )
    settlementData.value = data ?? null
    if (settlementData.value) {
      message.success('结算草稿已生成')
    }
  } catch (err) {
    message.warning('当前病历暂无可生成的结算清单数据')
    console.warn('生成结算草稿失败:', err)
  } finally {
    settlementLoading.value = false
  }
}

async function runSettlementQc() {
  if (!selectedRecord.value) return
  settlementQcLoading.value = true
  try {
    // 鏍规嵁鏁版嵁鏉ユ簮閫夋嫨瀵瑰簲鐨?QC 绔偣
    const isGenerated = settlementData.value?.data_source === 'generated_from_frontpage'
    const qcUrl = isGenerated
      ? `/api/medical-records/settlement/${selectedRecord.value.patientId}/${selectedRecord.value.visitId}/generate/qc`
      : `/api/medical-records/settlement/${selectedRecord.value.patientId}/${selectedRecord.value.visitId}/qc`
    const { data } = await apiClient.post(qcUrl)
    settlementQcReport.value = data
    await fetchAssistNotifications()
    await refreshActiveWorklist()
    await refreshSelectedSnapshots()
    const persistence = data.persistence || {}
    const activeDefects =
      Number(persistence.defects_created || 0) + Number(persistence.defects_updated || 0)
    if (activeDefects > 0) {
      message.success(`控费监测完成，发现 ${activeDefects} 条问题并更新消息`)
    } else if (Number(persistence.defects_resolved || 0) > 0) {
      message.success('控费监测完成，未发现问题，已更新最新状态')
    } else {
      message.success(`控费监测完成: ${data.summary.passed}/${data.summary.total} 通过`)
    }
  } catch (err) {
    message.error('结算清单质控执行失败')
    console.error(err)
  } finally {
    settlementQcLoading.value = false
  }
}

async function handleQcPersistenceFinished() {
  await fetchAssistNotifications()
  await refreshActiveWorklist()
  await refreshSelectedSnapshots()
}

// ========== AI鐢诲儚 & DRG Modal ==========
const aiProfileModalVisible = ref(false)
const profileAnalyzed = ref(false)
const profileAnalyzing = ref(false)
const drgDetailModalVisible = ref(false)

function openAiProfilePanel() {
  aiProfileModalVisible.value = true
  profileAnalyzed.value = true
}

function pickText(source: Record<string, unknown>, keys: string[]): string {
  for (const key of keys) {
    const raw = source[key]
    if (raw === null || raw === undefined) continue
    const text = String(raw).trim()
    if (text) return text
  }
  return ''
}

function pickNumber(source: Record<string, unknown>, keys: string[]): number {
  for (const key of keys) {
    const raw = source[key]
    const num = Number(raw)
    if (Number.isFinite(num)) return num
  }
  return 0
}

function normalizeDocumentAuthors(raw: unknown): DocItem['authors'] {
  if (!Array.isArray(raw)) return []
  return raw.flatMap((item) => {
    if (!item || typeof item !== 'object') return []
    const source = item as Record<string, unknown>
    const name = pickText(source, ['name'])
    const role = pickText(source, ['role'])
    const code = pickText(source, ['code'])
    return name || role || code
      ? [{ name: name || undefined, role: role || undefined, code: code || undefined }]
      : []
  })
}

function normalizeDocumentSignatures(raw: unknown): DocItem['signatures'] {
  if (!Array.isArray(raw)) return []
  return raw.flatMap((item) => {
    if (!item || typeof item !== 'object') return []
    const source = item as Record<string, unknown>
    const name = pickText(source, ['name'])
    const role = pickText(source, ['role'])
    const signedAt = pickText(source, ['signed_at'])
    const sourceField = pickText(source, ['source_field'])
    return name || role || signedAt || sourceField
      ? [
          {
            name: name || undefined,
            role: role || undefined,
            signed_at: signedAt || undefined,
            source_field: sourceField || undefined,
          },
        ]
      : []
  })
}

function normalizeDocItem(raw: unknown): DocItem {
  const source = (raw || {}) as Record<string, unknown>
  const docType = pickText(source, ['doc_type', 'type', 'document_type'])
  const id = pickText(source, ['id', 'doc_id', 'document_id'])
  const docKey = pickText(source, ['doc_key']) || (docType && id ? `${docType}::${id}` : '')
  const contentRaw = source.content
  const content = typeof contentRaw === 'string' ? contentRaw : null
  const length =
    pickNumber(source, ['length']) || (content ? content.replace(/\s+/g, '').length : 0)
  const hasContentRaw = source.has_content
  const hasContent =
    typeof hasContentRaw === 'boolean'
      ? hasContentRaw
      : Boolean((content || '').trim() || length > 0)
  const label =
    pickText(source, ['label', 'doc_name', 'document_title', 'title', 'name']) ||
    docType ||
    (id ? `文书${id}` : '未命名文书')

  return {
    ...(source as Partial<DocItem>),
    id: id || undefined,
    doc_id: pickText(source, ['doc_id']) || id || undefined,
    doc_key: docKey || undefined,
    doc_type: docType || undefined,
    doc_name: pickText(source, ['doc_name', 'document_title', 'title']) || label,
    type: pickText(source, ['type']) || docType || 'unknown',
    label,
    has_content: hasContent,
    content,
    length,
    document_id: pickText(source, ['document_id']) || id || undefined,
    document_title: pickText(source, ['document_title', 'doc_name', 'title']) || label,
    sort_time: pickText(source, ['sort_time', 'record_time']) || undefined,
    record_time: pickText(source, ['record_time', 'sort_time']) || undefined,
    source_table: pickText(source, ['source_table']) || undefined,
    group_key: pickText(source, ['group_key']) || undefined,
    authors: normalizeDocumentAuthors(source.authors),
    signatures: normalizeDocumentSignatures(source.signatures),
    projection_incomplete: source.projection_incomplete === true,
    projection_notice: pickText(source, ['projection_notice']) || undefined,
  }
}

function buildTreeNodeFromDoc(doc: DocItem): DocTreeNode {
  const id = String(doc.document_id || doc.id || doc.doc_id || doc.label || '')
  const docType = String(doc.doc_type || doc.type || '')
  const docKey = String(doc.doc_key || `${docType}::${id}`)
  return {
    id,
    doc_key: docKey,
    doc_type: docType,
    document_id: String(doc.document_id || doc.id || doc.doc_id || '') || undefined,
    title: String(doc.label || doc.doc_name || doc.document_title || docType || '未命名文书'),
    record_time: String(doc.record_time || doc.sort_time || ''),
    source_table: String(doc.source_table || ''),
    group_key: String(doc.group_key || ''),
    has_content: Boolean(doc.has_content),
    length: Number(doc.length || 0),
    projection_incomplete: doc.projection_incomplete === true,
    projection_notice: String(doc.projection_notice || '') || undefined,
  }
}

function inferGroupKey(doc: DocItem): string {
  const explicit = String(doc.group_key || '').trim()
  const docType = String(doc.doc_type || doc.type || '').toLowerCase()
  const sourceTable = String(doc.source_table || '').toLowerCase()
  const title = String(doc.label || doc.doc_name || doc.document_title || '').toLowerCase()
  const identity = `${explicit} ${docType} ${sourceTable} ${title}`
  if (['mr', 'mr_surgery', 'mr_cost'].includes(docType)) return 'frontpage'
  if (docType.includes('admission')) return 'admission'
  if (isRoundCourseIdentity(identity)) return 'round_course'
  if (isDailyCourseIdentity(identity)) return 'daily_course'
  if (explicit && explicit !== 'course') return explicit
  if (docType.includes('course')) return 'course'
  if (
    docType.includes('surgery') ||
    docType.includes('operation') ||
    docType.includes('anesthesia')
  )
    return 'surgery'
  if (docType.includes('discharge') || docType.includes('terminal')) return 'terminal'
  if (docType.includes('order')) return 'orders'
  return 'course'
}

function isRoundCourseIdentity(identity: string): boolean {
  return /查房|主任医师|副主任医师|主治医师|上级医师|round|ward[_-]?round|chief[_-]?round|attending[_-]?round/.test(
    identity,
  )
}

function isDailyCourseIdentity(identity: string): boolean {
  return /日常病程|日常病历|daily[_-]?course|daily[_-]?progress|progress[_-]?note/.test(identity)
}

function buildFallbackTreeFromDocs(docs: DocItem[]): DocTreeGroup[] {
  const groups: Array<{ key: string; label: string }> = [
    { key: 'all', label: '全部' },
    { key: 'frontpage', label: '病案首页(临床医生)' },
    { key: 'admission', label: '入院记录' },
    { key: 'round_course', label: '查房记录' },
    { key: 'daily_course', label: '日常病程记录' },
    { key: 'course', label: '其他病程记录' },
    { key: 'surgery', label: '手术相关单据' },
    { key: 'terminal', label: '出院记录' },
    { key: 'orders', label: '医嘱' },
  ]
  const byGroup = new Map<string, DocTreeNode[]>()
  for (const doc of docs) {
    const node = buildTreeNodeFromDoc(doc)
    const groupKey = inferGroupKey(doc)
    byGroup.set(groupKey, [...(byGroup.get(groupKey) || []), node])
    byGroup.set('all', [...(byGroup.get('all') || []), node])
  }
  return groups.map((group) => {
    const children = byGroup.get(group.key) || []
    return {
      key: group.key,
      label: group.label,
      count: children.length,
      children,
    }
  })
}

function shouldSplitCourseGroup(group: DocTreeGroup): boolean {
  const key = String(group.key || '').toLowerCase()
  const label = String(group.label || '').toLowerCase()
  if (key === 'course') return true
  if (label.includes('病程') && !label.includes('日常病程')) return true
  return false
}

function inferCourseGroupKey(node: DocTreeNode, doc?: DocItem): string {
  const identity = [
    node.group_key,
    node.doc_type,
    node.source_table,
    node.title,
    doc?.group_key,
    doc?.doc_type || doc?.type,
    doc?.source_table,
    doc?.label,
    doc?.doc_name,
    doc?.document_title,
  ]
    .map((item) => String(item || '').toLowerCase())
    .join(' ')
  if (isRoundCourseIdentity(identity)) return 'round_course'
  if (isDailyCourseIdentity(identity)) return 'daily_course'
  return 'course'
}

function splitCourseGroups(groups: DocTreeGroup[], docs: DocItem[]): DocTreeGroup[] {
  const docByKey = new Map(docs.map((doc) => [String(doc.doc_key || ''), doc]))
  const groupLabels: Record<string, string> = {
    round_course: '查房记录',
    daily_course: '日常病程记录',
    course: '其他病程记录',
  }

  const result: DocTreeGroup[] = []
  const appendGroup = (nextGroup: DocTreeGroup) => {
    const existed = result.find((group) => group.key === nextGroup.key)
    if (!existed) {
      result.push(nextGroup)
      return
    }
    existed.children = [...existed.children, ...nextGroup.children]
    existed.count = existed.children.length
  }

  for (const group of groups) {
    if (!shouldSplitCourseGroup(group)) {
      appendGroup(group)
      continue
    }

    const buckets = new Map<string, DocTreeNode[]>()
    for (const node of group.children || []) {
      const doc = docByKey.get(String(node.doc_key || ''))
      const groupKey = inferCourseGroupKey(node, doc)
      buckets.set(groupKey, [...(buckets.get(groupKey) || []), node])
    }

    for (const key of ['round_course', 'daily_course', 'course']) {
      const children = buckets.get(key) || []
      if (!children.length) continue
      appendGroup({
        key,
        label: groupLabels[key],
        count: children.length,
        children,
      })
    }
  }

  return result
}

function normalizeDocumentsTree(rawTree: unknown, docs: DocItem[]): DocTreeGroup[] {
  const groups = Array.isArray(rawTree) ? rawTree : []
  const normalized = groups
    .map((rawGroup) => {
      const source = (rawGroup || {}) as Record<string, unknown>
      const groupKey = pickText(source, ['key', 'group_key'])
      const groupLabel = pickText(source, ['label', 'title', 'name']) || groupKey || '分组'
      const rawChildren = Array.isArray(source.children)
        ? source.children
        : Array.isArray(source.nodes)
          ? source.nodes
          : []
      const children = rawChildren
        .map((rawNode) => {
          const nodeSource = (rawNode || {}) as Record<string, unknown>
          const id = pickText(nodeSource, ['id', 'doc_id', 'document_id'])
          const docType = pickText(nodeSource, ['doc_type', 'type'])
          const docKey =
            pickText(nodeSource, ['doc_key']) || (docType && id ? `${docType}::${id}` : '')
          const title =
            pickText(nodeSource, ['title', 'label', 'doc_name', 'name']) ||
            docs.find((doc) => String(doc.doc_key || '') === docKey)?.label ||
            docType ||
            '未命名文书'
          const hasContentRaw = nodeSource.has_content
          const hasContent =
            typeof hasContentRaw === 'boolean'
              ? hasContentRaw
              : Boolean(docs.find((doc) => String(doc.doc_key || '') === docKey)?.has_content)
          return {
            id: id || docKey || title,
            doc_key: docKey || `${docType || 'unknown'}::${id || title}`,
            doc_type: docType || '',
            document_id: pickText(nodeSource, ['document_id']) || id || undefined,
            title,
            record_time: pickText(nodeSource, ['record_time', 'sort_time']) || undefined,
            source_table: pickText(nodeSource, ['source_table']) || undefined,
            group_key: pickText(nodeSource, ['group_key']) || groupKey || undefined,
            has_content: hasContent,
            length: pickNumber(nodeSource, ['length']),
            projection_incomplete: nodeSource.projection_incomplete === true,
            projection_notice: pickText(nodeSource, ['projection_notice']) || undefined,
          } as DocTreeNode
        })
        .filter((node) => Boolean(node.id))

      return {
        key: groupKey || groupLabel,
        label: groupLabel,
        count: children.length,
        children,
      } as DocTreeGroup
    })
    .filter((group) => Boolean(group.key))

  const hasUsefulGroup = normalized.some(
    (group) => group.key !== 'all' && Array.isArray(group.children) && group.children.length > 0,
  )
  if (hasUsefulGroup) return splitCourseGroups(normalized, docs)
  if (docs.length > 0) return buildFallbackTreeFromDocs(docs)
  return normalized
}

async function loadDocuments(visitId: string) {
  documentsLoading.value = true
  concatLoading.value = true
  documentsList.value = []
  documentsTree.value = []
  concatText.value = ''
  try {
    const record = selectedRecord.value
    const params: Record<string, string> = {}
    if (record?.patientId) params.patient_id = record.patientId
    if (record?.instituteId) params.institute_id = record.instituteId
    if (record?.visitId) {
      params.visit_id = record.visitId
    } else {
      params.visit_id = visitId
    }

    const { data } = await apiClient.get(`/api/v1/emr/${visitId}/documents`, { params })
    const payload = data?.data || data || {}
    const docsRaw = Array.isArray(payload.documents)
      ? payload.documents
      : Array.isArray(payload)
        ? payload
        : []
    const docs: DocItem[] = docsRaw.map((item) => normalizeDocItem(item))
    const tree: DocTreeGroup[] = normalizeDocumentsTree(payload.documents_tree, docs)
    documentsList.value = docs
    documentsTree.value = tree
    concatText.value = buildConcatTextFromDocuments(docs)
    if (docs.length > 0) {
      const defaultDoc = docs.find((item) => item.has_content) || docs[0]
      activeDocType.value = docIdentityKey(defaultDoc)
      docPreviewTitle.value = resolveDocDisplayTitle(defaultDoc, true)
      docPreviewContent.value = defaultDoc.content || ''
    }
  } catch (err) {
    console.error('加载病历文书失败:', err)
  } finally {
    documentsLoading.value = false
    concatLoading.value = false
  }
}

function docIdentityKey(doc: DocItem) {
  return String(
    doc.doc_key ||
      `${doc.doc_type || doc.type || ''}::${doc.document_id || doc.id || doc.label || ''}`,
  )
}

function openDocPreview(doc: DocItem) {
  activeDocType.value = docIdentityKey(doc)
  docPreviewTitle.value = resolveDocDisplayTitle(doc, true)
  docPreviewContent.value = doc.content || '暂无内容'
  detailMainTab.value = 'records'
}

function showConcatRecord() {
  activeDocType.value = ''
  docPreviewTitle.value = ''
  docPreviewContent.value = ''
  detailMainTab.value = 'records'
}

const combinedMedicalText = computed(() =>
  documentsList.value
    .filter((doc) => doc.has_content && doc.content)
    .map((doc) => `${doc.label}\n${doc.content}`)
    .join('\n\n'),
)

const selectedRecord = computed(
  () =>
    allRecords.value.find((r) => r.id === selectedId.value) ||
    (selectedStageRecord.value?.id === selectedId.value ? selectedStageRecord.value : null),
)

const {
  assistIssues,
  assistBadgeCount: qcIssueCount,
  qcRefreshSeed,
  handleAssistIssuesChange,
  touchCodingRefresh,
  findEvidenceDoc,
  findEvidenceSnippet,
} = useQcPipeline()

const {
  frontpageGenerating,
  frontpagePostProcessing,
  frontpageDraft,
  frontpageReportResult,
  frontpageModule,
  frontpageFocusTarget,
  frontpageFields,
  defaultPreviewTab,
  completedModules,
  setDraftEmpty,
  ensureExtractionSettingsLoaded,
  generateFrontpage,
  generateFrontpageFromText,
  handleExportFrontpage,
  handleSaveFrontpage,
  focusFrontpageSection,
  handleApplyICDCode: applyICDCodeToDraft,
  applyFrontPanelEdits,
} = useFrontpageDraft(selectedId, selectedRecord, combinedMedicalText, touchCodingRefresh)

// ========== AI 鐢熸垚杩涘害杈呭姪 ==========
import { MODULE_LABELS, type CompletedModule } from './composables/useFrontpageDraft'

const ALL_MODULE_KEYS = [
  'basic_info',
  'hospitalization',
  'diagnoses',
  'procedures',
  'other_medical_info',
  'staff',
  'costs',
  'confidence',
]
const MODULE_LABELS_MAP = MODULE_LABELS

const frontpageModuleCards = computed(() =>
  ALL_MODULE_KEYS.map((key) => ({
    key,
    label: MODULE_LABELS_MAP[key] || key,
    status: getModuleStatus(key),
    entry: getModuleEntry(key),
  })),
)

function getModuleEntry(m: string): CompletedModule | undefined {
  return completedModules.value.find((c) => c.name === m)
}

function getModuleStatus(m: string): 'done' | 'active' | 'pending' {
  if (getModuleEntry(m)) return 'done'
  if (frontpageModule.value === m) return 'active'
  return 'pending'
}

// 鐢熸垚瀹屾垚鍚庡欢杩?5 绉掕嚜鍔ㄥ垏鍒扳€滈椤甸瑙?鎵撳嵃鈥?tab锛岃鐢ㄦ埛鏈夋椂闂存煡鐪嬫彁鍙栫粨鏋?
let autoJumpTimer: ReturnType<typeof setTimeout> | null = null

watch(frontpageGenerating, (generating, wasGenerating) => {
  if (wasGenerating && !generating && frontpageDraft.value) {
    if (autoJumpTimer) clearTimeout(autoJumpTimer)
    autoJumpTimer = setTimeout(() => {
      // 鍙湁褰撳墠杩樺湪鎻愬彇缁撴灉椤垫椂鎵嶈嚜鍔ㄨ烦杞紝閬垮厤瑕嗙洊鐢ㄦ埛鐨勬墜鍔ㄥ垏鎹㈣涓?
      if (frontpageTab.value === 'fields') {
        frontpageTab.value = defaultPreviewTab.value
      }
    }, 5000)
  }
})

const launchHandling = ref(false)
const handledLaunchKey = ref('')
const validLaunchActions: WorkstationLaunchAction[] = [
  'open_record',
  'generate_frontpage',
  'qc_coding',
  'qc_frontpage',
  'qc_settlement',
]
const validStages: WorkflowStageKey[] = [
  'frontpage_generate',
  'coding_qc',
  'frontpage_qc',
  'settlement_qc',
]

useWorkstationRouteEffects({
  route,
  router,
  allRecords,
  allRecordsCount: computed(() => allRecords.value.length),
  validLaunchActions,
  validStages,
  handledLaunchKey,
  launchHandling,
  openRecord,
  setDetailMainTab: (tab) => {
    detailMainTab.value = tab
  },
  setAssistPanelVisible: (visible) => {
    assistPanelVisible.value = visible
  },
  setAssistTab: (tab) => {
    assistTab.value = tab
  },
  nextTick,
  handleGenerateFrontpage: async () => {
    await Promise.resolve(handleGenerateFrontpage())
  },
  runCodingQc: () => {
    assistViewRef.value?.runCodingQC()
  },
  runFormQc: () => {
    assistViewRef.value?.runFormQC()
  },
  isDischarged: isDischarged.value,
  runSettlementQc,
  getSettlementLoading: () => settlementLoading.value,
  showWarning: (msg) => {
    message.warning(msg)
  },
  activeDept,
  searchText,
  hospFilter,
  currentPage,
  viewMode,
  backToList,
  assistPanelVisible,
  icdDrawerVisible,
  suggestionDrawerVisible,
})

onMounted(() => {
  void ensureExtractionSettingsLoaded()
  fetchData()
  void refreshActiveWorklist()
  fetchAssistNotifications()
})

// 鍒囨崲鐥呭巻鏃舵竻闄や笂娆＄敓鎴愮粨鏋滐紝骞跺姞杞芥枃涔﹀垪琛ㄤ笌缁撶畻娓呭崟
watch(selectedId, (newId) => {
  setDraftEmpty()
  resetPerRecordTransient()
  assistIssues.value = []
  suggestionDrawerVisible.value = false
  activeDocType.value = ''
  docPreviewTitle.value = ''
  docPreviewContent.value = ''
  expandedConcatSectionIndexes.value = new Set()
  settlementQcReport.value = null
  detailMainTab.value = pendingDetailMainTab.value || 'records'
  pendingDetailMainTab.value = null
  emrRenderState.value = newId ? 'loading' : 'idle'
  if (newId) {
    loadDocuments(newId)
    void refreshSelectedSnapshots()
    const record = selectedRecord.value || allRecords.value.find((r) => r.id === newId)
    if (record?.patientId) {
      if (record.hasFrontpageOfficial) {
        loadFrontpageSheet(record.patientId, newId)
      } else {
        frontpageSheetData.value = null
      }
    }
  } else {
    qcSnapshotState.value = {}
    documentsList.value = []
    documentsTree.value = []
    concatText.value = ''
    settlementData.value = null
    frontpageSheetData.value = null
  }
})

watch(detailMainTab, (tab) => {
  if (tab !== 'settlement') return
  void ensureSettlementLoadedForSelectedRecord()
})

watch(
  [currentStageFilter, activeDept, searchText, currentPage, pageSize],
  ([stage]) => {
    if (!aggregatedStageWorkflows[stage]) return
    void fetchStageWorklist(stage)
  },
  { immediate: true },
)

watch(concatSections, (sections) => {
  if (!sections.length) {
    expandedConcatSectionIndexes.value = new Set()
    return
  }
  if (!expandedConcatSectionIndexes.value.size) {
    expandedConcatSectionIndexes.value = new Set([0])
  }
})

// ========== 璁＄畻 ==========

const detailItems = computed(() => {
  const r = selectedRecord.value
  if (!r) return []
  return [
    { label: '科室', value: r.department },
    { label: '床号', value: r.bedNo ? `${r.bedNo}床` : '' },
    { label: '性别/年龄', value: `${r.sex} / ${r.age}岁` },
    { label: '医保类型', value: r.insurance },
    { label: '入院日期', value: r.admissionDate },
    { label: '住院天数', value: `${r.days}天` },
    { label: '主管医生', value: r.doctor },
    { label: '出院日期', value: r.dischargeDate },
    { label: '病案号', value: r.id },
  ]
})

const assistPatientInfo = computed(() => {
  const record = selectedRecord.value
  if (!record) return null
  return {
    name: record.name,
    sex: record.sex,
    age: `${record.age}岁`,
    diagnosis: record.diagnosis,
    visitId: record.id,
  }
})

const assistBadgeCount = computed(() => {
  if (qcIssueCount.value > 0) return qcIssueCount.value
  const record = selectedRecord.value
  if (!record) return 0
  return record.status === 'warning' ? 1 : 0
})

const icdApplyLabel = computed(() => {
  if (icdApplyTarget.value === 'mainDiagnosis') return '回填主诊断编码'
  if (icdApplyTarget.value === 'mainProcedure') return '回填主手术编码'
  if (icdApplyTarget.value === 'otherDiagnosis')
    return `回填其他诊断编码（第 ${icdApplyIndex.value} 条）`
  return `回填其他手术编码（第 ${icdApplyIndex.value} 条）`
})

function openRecord(record: PatientRecord) {
  selectedStageRecord.value = record
  openSessionRecord(record.id)
  assistPanelVisible.value = false
  icdDrawerVisible.value = false
}

function handlePriorityOpen(recordId: string) {
  const record = findRecordById(listRecords.value, recordId)
  if (!record) return
  handleStageRecordAction(record)
}

function handlePriorityDefer(recordId: string) {
  message.info(`已将 ${recordId} 标记为稍后处理`)
}

async function ensureSettlementLoadedForSelectedRecord() {
  const record = selectedRecord.value
  if (!record?.patientId || !record?.visitId) return
  if (settlementLoading.value) return
  if (
    settlementData.value &&
    settlementDataVisitKey.value === `${record.patientId}::${record.visitId}`
  )
    return
  await loadSettlement(record.patientId, record.visitId)
}

function handleRowOpen(recordId: string) {
  const record = findRecordById(listRecords.value, recordId)
  if (!record) return
  openRecordForStage({
    stage: currentStageFilter.value,
    record,
    openRecord,
    setPendingDetailMainTab: (tab) => {
      pendingDetailMainTab.value = tab
    },
    setDetailMainTab: (tab) => {
      detailMainTab.value = tab
    },
    setAssistPanelVisible: (visible) => {
      assistPanelVisible.value = visible
    },
    setAssistTab: (tab) => {
      assistTab.value = tab
    },
    ensureSettlementLoadedForSelectedRecord,
  })
}

function findBatchRecordByVisitId(visitId: string): PatientRecord | null {
  const normalized = String(visitId || '').trim()
  if (!normalized) return null
  return (
    stageListRecords.value.find(
      (record) => String(record.visitId || record.id || '').trim() === normalized,
    ) ||
    allRecords.value.find(
      (record) => String(record.visitId || record.id || '').trim() === normalized,
    ) ||
    null
  )
}

async function handleBatchExtract(keys: string[]) {
  await runBatchExtract({
    keys,
    currentStageFilter: currentStageFilter.value,
    isStageQueueMode: isStageQueueMode.value,
    isAggregatedStageMode: isAggregatedStageMode.value,
    getBatchExtracting: () => batchExtracting.value,
    setBatchExtracting: (value) => {
      batchExtracting.value = value
    },
    findBatchRecordByVisitId,
    setBatchRuntimeStatus,
    setSingleBatchRuntimeStatus,
    setSelectedWorkbenchKeys: (nextKeys) => {
      selectedWorkbenchKeys.value = nextKeys
    },
    fetchAssistNotifications,
    refreshActiveWorklist,
    refreshData: async () => {
      await Promise.resolve(refreshData())
    },
    refreshSelectedSnapshots,
  })
}

function handleBatchDefer(keys: string[]) {
  if (!keys.length) return
  message.info(`已批量标记稍后：${keys.length} 条`)
}

function handleBatchAssign(keys: string[]) {
  if (!keys.length) return
  message.info(`批量分派功能准备中，已选择 ${keys.length} 条`)
}

function handlePageChange(page: number, nextPageSize?: number) {
  const resolvedPageSize =
    Number.isFinite(Number(nextPageSize)) && Number(nextPageSize) > 0
      ? Number(nextPageSize)
      : pageSize.value
  if (isAggregatedStageMode.value) {
    const pageSizeChanged = resolvedPageSize !== pageSize.value
    pageSize.value = resolvedPageSize
    currentPage.value = pageSizeChanged ? 1 : page
    void fetchStageWorklist(currentStageFilter.value)
    document.querySelector('.custom-scrollbar')?.scrollTo({ top: 0, behavior: 'smooth' })
    return
  }
  handleBasePageChange(page, resolvedPageSize)
}

function handleClearFilters() {
  resetFilters()
  selectedWorkbenchKeys.value = []
  if (isAggregatedStageMode.value) {
    void fetchStageWorklist(currentStageFilter.value)
    return
  }
  void fetchData(1)
}

function goToFinalRecords() {
  router.push('/workstation-v4/records/final')
}

function goToSichuanRules() {
  router.push('/workstation-v4/rules?tab=semantic&ruleSetKey=luxian_0609_qc_v1')
}

const { currentRecordIndex, goToPrevRecord, goToNextRecord, goBackToList } = createDetailNavigation(
  {
    getSelectedRecord: () => selectedRecord.value,
    getFilteredRecords: () => filteredRecords.value,
    openRecord,
    backToList,
    clearPanels: () => {
      assistPanelVisible.value = false
      icdDrawerVisible.value = false
      suggestionDrawerVisible.value = false
    },
  },
)

function handleLocateFromQC(payload: {
  target: FrontpageFocusTarget
  issue: { description?: string }
}) {
  if (!frontpageDraft.value) {
    message.warning('请先生成首页后再定位字段')
    return
  }
  frontpageTab.value = 'fields'
  focusFrontpageSection(payload.target as FrontpageFocusTarget)
  if (payload?.issue?.description) {
    message.info(`已定位：${payload.issue.description}`)
  }
}

function handleApplyICDCode(detail: ICDCodeDetail) {
  const applied = applyICDCodeToDraft(
    detail,
    icdApplyTarget.value,
    Number(icdApplyIndex.value || 1),
  )
  if (!applied) return
  frontpageTab.value = 'fields'
  icdDrawerVisible.value = false
  touchCodingRefresh()
}

function handleFrontPanelDraftChange(payload: { diagnoses: any[]; procedures: any[] }) {
  applyFrontPanelEdits(payload)
  touchCodingRefresh()
}

function handleJumpEvidenceFromQC(issue: QCIssueLike) {
  const doc = findEvidenceDoc(issue, documentsList.value)
  if (!doc) {
    message.warning('暂无可跳转的文书依据')
    return
  }
  activeDocType.value = docIdentityKey(doc)
  docPreviewTitle.value = `依据文书：${doc.label}`
  docPreviewContent.value = findEvidenceSnippet(issue, doc.content) || doc.content || '暂无内容'
  detailMainTab.value = 'records'
}

function handleEmrLoaded(payload: { content?: string }) {
  emrRenderState.value = payload?.content ? 'ready' : 'fallback'
}

function handleEmrError() {
  if (selectedId.value) {
    emrRenderState.value = 'fallback'
  }
}

function handleEmrDefectClick(defectId: string) {
  assistPanelVisible.value = true
  assistTab.value = 'form'
  const matched = assistIssues.value.find((issue) => issue?.id === defectId)
  if (matched?.description) {
    message.info(`已定位质控问题：${matched.description}`)
  }
}

function handleAssistTabChange(tab: unknown) {
  assistTab.value = tab as typeof assistTab.value
  if (tab === 'message') {
    fetchAssistNotifications()
  }
}

function performDRGGrouping() {
  if (!selectedId.value) {
    message.warning('请先选择病历')
    return
  }
  doDRGGrouping(selectedId.value)
}

function openOptimization() {
  if (!selectedId.value) {
    message.warning('请先选择病历')
    return
  }
  openOptimizationDrawer(selectedId.value)
}

function suggestionSeverityTag(severity?: string) {
  if (severity === 'high' || severity === 'error' || severity === 'critical') return 'error'
  if (severity === 'medium' || severity === 'warning') return 'warning'
  return 'processing'
}

function handleDRGSuggestion(action: 'accept' | 'reject', suggestionId: number) {
  if (!selectedId.value) {
    message.warning('请先选择病历')
    return
  }
  handleSuggestion(suggestionId, action, selectedId.value)
}
</script>

<style>
@import './styles/workstation-v4-view.css';
</style>
