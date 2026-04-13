<template>
  <div class="semantic-rules-page">
    <div class="semantic-rules-content">
      <SemanticRulesOverviewPanels
        :loading="loading"
        :kpi-cards="heroKpiCards"
        :critical-defect-count="criticalDefectCount"
        :major-defect-count="majorDefectCount"
        :minor-defect-count="minorDefectCount"
        :risk-density="riskDensity"
        :top-categories="topCategories"
        :get-defect-rate="getDefectRate"
        :get-category-ratio="getCategoryRatio"
        @query="applyFilterQuery()"
        @reset="resetFilters()"
        @refresh="refreshRules()"
      />

      <SemanticRulesTableSection
        :loading="loading"
        :rules="tableRules"
        :total="filteredRules.length"
        :keyword-input="keywordInput"
        :complexity="queryState.complexity"
        :defect-level="queryState.defectLevel"
        :document-type="queryState.documentType"
        :complexity-options="complexityOptions"
        :defect-options="defectOptions"
        :document-options="documentOptions"
        :pagination="tablePagination"
        @update:keyword-input="keywordInput = $event"
        @update:complexity="queryState.complexity = $event"
        @update:defect-level="queryState.defectLevel = $event"
        @update:document-type="queryState.documentType = $event"
        @open-qc-evaluation="openBatchLaunchModal()"
        @open-custom-workspace="goCustomWorkspace()"
        @table-change="handleTableChange"
        @view-detail="openRuleDetail"
        @start-test="startRuleTest"
      />

      <SemanticRulesBatchPanel
        :loading="batchJobLoading"
        :batch-jobs="batchJobs"
        :total="Number(batchJobPagination.total || 0)"
        :pagination="batchJobPagination"
        :query="batchJobQuery"
        :status-options="batchJobStatusOptions"
        :scope-options="batchJobScopeOptions"
        :cancelling-batch-job-id="cancellingBatchJobId"
        :retrying-batch-job-id="retryingBatchJobId"
        :format-date-time="formatDateTime"
        @open-batch-launch="openBatchLaunchModal()"
        @search-batch-jobs="searchBatchJobs"
        @table-change="handleBatchJobTableChange"
        @open-batch-job-drawer="openBatchJobDrawer"
        @cancel-batch-job="executeCancelBatchJob"
        @retry-batch-job="executeRetryBatchJob"
        @update-query="(value) => Object.assign(batchJobQuery, value)"
      />
    </div>

    <SemanticRuleDetailModal
      :open="showRuleDetail"
      :rule="selectedRule"
      :is-admin="isAdmin"
      :prompt-loading="promptLoading"
      :is-editing-prompt="isEditingPrompt"
      :current-prompt="currentPrompt"
      :editing-prompt="editingPrompt"
      @update:open="handleDetailOpenChange"
      @start-edit-prompt="startEditPrompt"
      @cancel-edit-prompt="cancelEditPrompt"
      @save-prompt="savePromptChanges"
      @update:editing-prompt="editingPrompt = $event"
      @start-test="handleStartTestFromDetail"
    />

    <SemanticRuleTestModal
      :open="showRuleTest"
      :rule="testingRule"
      :example-type="testExampleType"
      :medical-text="testMedicalText"
      :loading="testLoading"
      :result="testResult"
      @update:open="handleTestOpenChange"
      @update:example-type="switchExampleType"
      @update:medical-text="testMedicalText = $event"
      @execute="executeRuleTestAction"
    />

    <CustomQcBatchLaunchModal
      :open="batchLaunchModalOpen"
      :testing-batch="testingBatch"
      :confirm-batch-launch="confirmBatchLaunch"
      :selected-run-draft-count="filteredRules.length"
      :selected-run-scene-label="
        batchLaunchFilters.scope === 'running'
          ? '运行病历'
          : batchLaunchFilters.scope === 'all'
            ? '全量病历'
            : '终末病历'
      "
      :selected-record-count="0"
      :batch-launch-filters="batchLaunchFilters"
      :scope-options="batchJobScopeOptions"
      :batch-launch-filters-loading="batchLaunchFiltersLoading"
      :batch-launch-department-options="batchLaunchDepartmentOptions"
      :batch-launch-doctor-options="batchLaunchDoctorOptions"
      :handle-batch-launch-scope-change="handleBatchLaunchScopeChange"
      :handle-batch-launch-department-change="handleBatchLaunchDepartmentChange"
      :batch-launch-date-field-label="
        batchLaunchFilters.date_field === 'admission' ? '入院日期' : '出院日期'
      "
      @update:open="(value) => (batchLaunchModalOpen = value)"
      @update:batch-launch-filters="(value) => Object.assign(batchLaunchFilters, value)"
    />

    <SemanticRulesBatchResultDrawer
      :open="resultDrawerOpen"
      :batch-job-detail="batchJobDetail"
      :batch-job-debug-snapshot="batchJobDebugSnapshot"
      :batch-job-debug-loading="batchJobDebugLoading"
      :batch-job-detail-loading="batchJobDetailLoading"
      :fetch-batch-job-debug-snapshot="fetchBatchJobDebugSnapshot"
      :close="closeBatchJobDrawer"
      :export-batch-job-report="exportBatchJobReport"
      :get-batch-job-status-tag-class="getBatchJobStatusTagClass"
      :get-batch-job-status-text="getBatchJobStatusText"
      :format-date-time="formatDateTime"
    />
  </div>
</template>

<script setup lang="ts">
import { useSemanticRulesWorkspace } from './composables/useSemanticRulesWorkspace'
import SemanticRulesOverviewPanels from './components/SemanticRulesOverviewPanels.vue'
import SemanticRulesTableSection from './components/SemanticRulesTableSection.vue'
import SemanticRulesBatchPanel from './components/SemanticRulesBatchPanel.vue'
import SemanticRulesBatchResultDrawer from './components/SemanticRulesBatchResultDrawer.vue'
import SemanticRuleDetailModal from './components/modals/SemanticRuleDetailModal.vue'
import SemanticRuleTestModal from './components/modals/SemanticRuleTestModal.vue'
import CustomQcBatchLaunchModal from '@/views/rules/components/workspace/CustomQcBatchLaunchModal.vue'
import {
  getBatchJobStatusTagClass,
  getBatchJobStatusText,
} from '@/views/rules/utils/customQcWorkspacePresentation'

const {
  loading,
  criticalDefectCount,
  majorDefectCount,
  minorDefectCount,
  riskDensity,
  topCategories,
  heroKpiCards,
  getDefectRate,
  getCategoryRatio,
  queryState,
  keywordInput,
  filteredRules,
  tableRules,
  tablePagination,
  complexityOptions,
  defectOptions,
  documentOptions,
  refreshRules,
  resetFilters,
  applyFilterQuery,
  handleTableChange,
  showRuleDetail,
  selectedRule,
  openRuleDetail,
  closeRuleDetail,
  isAdmin,
  promptLoading,
  isEditingPrompt,
  currentPrompt,
  editingPrompt,
  startEditPrompt,
  cancelEditPrompt,
  savePromptChanges,
  showRuleTest,
  testingRule,
  testMedicalText,
  testLoading,
  testExampleType,
  testResult,
  startRuleTest,
  switchExampleType,
  closeRuleTest,
  executeRuleTestAction,
  goCustomWorkspace,
  batchLaunchModalOpen,
  batchLaunchFiltersLoading,
  batchLaunchDepartmentOptions,
  batchLaunchDoctorOptions,
  batchLaunchFilters,
  handleBatchLaunchScopeChange,
  handleBatchLaunchDepartmentChange,
  openBatchLaunchModal,
  confirmBatchLaunch,
  testingBatch,
  batchJobLoading,
  batchJobDetailLoading,
  batchJobDebugLoading,
  cancellingBatchJobId,
  retryingBatchJobId,
  batchJobs,
  batchJobDetail,
  batchJobDebugSnapshot,
  batchJobPagination,
  batchJobQuery,
  batchJobStatusOptions,
  batchJobScopeOptions,
  handleBatchJobTableChange,
  searchBatchJobs,
  openBatchJobDrawer,
  closeBatchJobDrawer,
  fetchBatchJobDebugSnapshot,
  executeCancelBatchJob,
  executeRetryBatchJob,
  exportBatchJobReport,
  resultDrawerOpen,
  formatDateTime,
} = useSemanticRulesWorkspace()

function handleDetailOpenChange(value: boolean) {
  if (!value) {
    closeRuleDetail()
    return
  }
}

function handleTestOpenChange(value: boolean) {
  if (!value) {
    closeRuleTest()
    return
  }
}

function handleStartTestFromDetail() {
  if (!selectedRule.value) return
  closeRuleDetail()
  startRuleTest(selectedRule.value)
}
</script>

<style scoped>
.semantic-rules-page {
  min-height: 100%;
  background: linear-gradient(180deg, #f8fafc 0%, #edf2f7 100%);
  padding: 16px;
  color: #0f172a;
  font-size: 14px;
  line-height: 1.5;
  font-family:
    'PingFang SC',
    'Microsoft YaHei',
    'Noto Sans SC',
    'Hiragino Sans GB',
    'Source Han Sans SC',
    -apple-system,
    BlinkMacSystemFont,
    'Segoe UI',
    sans-serif;
}

.semantic-rules-content {
  width: 100%;
  max-width: 1440px;
  margin: 0 auto;
}

@media (max-width: 1023px) {
  .semantic-rules-page {
    padding: 12px;
  }
}
</style>
