<template>
  <div class="semantic-rules-page">
    <div class="semantic-rules-content">
      <SemanticRulesTableSection
        :loading="loading"
        :rules="tableRules"
        :scope-rules="filteredRules"
        :total="filteredRules.length"
        :rule-set-key="queryState.ruleSetKey"
        :rule-set-options="ruleSetOptions"
        :keyword-input="keywordInput"
        :complexity="queryState.complexity"
        :defect-level="queryState.defectLevel"
        :document-type="queryState.documentType"
        :release-scope="queryState.releaseScope"
        :complexity-options="complexityOptions"
        :defect-options="defectOptions"
        :document-options="documentOptions"
        :pagination="tablePagination"
        @update:keyword-input="keywordInput = $event"
        @rule-set-change="handleRuleSetChange"
        @update:complexity="queryState.complexity = $event"
        @update:defect-level="queryState.defectLevel = $event"
        @update:document-type="queryState.documentType = $event"
        @update:release-scope="queryState.releaseScope = $event"
        @open-qc-evaluation="openBatchLaunchModal()"
        @open-custom-workspace="goCustomWorkspace()"
        @table-change="handleTableChange"
        @view-detail="openRuleDetail"
        @start-test="startRuleTest"
      />
    </div>

    <SemanticRuleDetailModal
      :open="showRuleDetail"
      :rule="selectedRule"
      :is-admin="isAdmin"
      :prompt-loading="promptLoading"
      :prompt-error="promptError"
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
      :fetch-batch-job-debug-snapshot="confirmedResultsOnly ? undefined : fetchBatchJobDebugSnapshot"
      :batch-job-detail-loading="batchJobDetailLoading"
      :close="closeBatchJobDrawer"
      :export-batch-job-report="exportBatchJobReport"
      :cancel-batch-job="executeCancelBatchJob"
      :cancel-batch-job-loading="Boolean(cancellingBatchJobId)"
      :get-batch-job-status-tag-class="getBatchJobStatusTagClass"
      :get-batch-job-status-text="getBatchJobStatusText"
      :format-date-time="formatDateTime"
      back-label="返回语义规则"
    />
  </div>
</template>

<script setup lang="ts">
import { useSemanticRulesWorkspace } from './composables/useSemanticRulesWorkspace'
import SemanticRulesTableSection from './components/SemanticRulesTableSection.vue'
import SemanticRulesBatchResultDrawer from './components/SemanticRulesBatchResultDrawer.vue'
import SemanticRuleDetailModal from './components/modals/SemanticRuleDetailModal.vue'
import SemanticRuleTestModal from './components/modals/SemanticRuleTestModal.vue'
import CustomQcBatchLaunchModal from '@/views/rules/components/CustomQcBatchLaunchModal.vue'
import {
  getBatchJobStatusTagClass,
  getBatchJobStatusText,
} from '@/views/rules/utils/customQcWorkspacePresentation'

const {
  loading,
  queryState,
  ruleSetOptions,
  handleRuleSetChange,
  keywordInput,
  filteredRules,
  tableRules,
  tablePagination,
  complexityOptions,
  defectOptions,
  documentOptions,
  handleTableChange,
  showRuleDetail,
  selectedRule,
  openRuleDetail,
  closeRuleDetail,
  isAdmin,
  confirmedResultsOnly,
  promptLoading,
  promptError,
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
  batchJobScopeOptions,
  batchJobDetail,
  batchJobDetailLoading,
  batchJobDebugSnapshot,
  batchJobDebugLoading,
  cancellingBatchJobId,
  resultDrawerOpen,
  closeBatchJobDrawer,
  fetchBatchJobDebugSnapshot,
  executeCancelBatchJob,
  exportBatchJobReport,
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
  background: transparent;
  padding: 0;
  color: #1d1d1f;
  font-size: 14px;
  line-height: 1.5;
  font-family:
    'San Francisco', 'SF Pro Text', 'Source Han Sans SC', 'SF Pro Display', Inter, 'PingFang SC',
    'Microsoft YaHei UI', 'Microsoft YaHei', sans-serif;
}

.semantic-rules-content {
  width: 100%;
  max-width: none;
  margin: 0;
}

@media (max-width: 1023px) {
  .semantic-rules-page {
    padding: 0;
  }
}
</style>
