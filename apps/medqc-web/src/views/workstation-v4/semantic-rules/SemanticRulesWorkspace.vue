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
        @update:rule-set-key="handleRuleSetChange"
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
  </div>
</template>

<script setup lang="ts">
import { useSemanticRulesWorkspace } from './composables/useSemanticRulesWorkspace'
import SemanticRulesTableSection from './components/SemanticRulesTableSection.vue'
import SemanticRuleDetailModal from './components/modals/SemanticRuleDetailModal.vue'
import SemanticRuleTestModal from './components/modals/SemanticRuleTestModal.vue'
import CustomQcBatchLaunchModal from '@/views/rules/components/CustomQcBatchLaunchModal.vue'

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
  batchJobScopeOptions,
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
