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
        @open-qc-evaluation="openQCEvaluation()"
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

    <SemanticRuleEvaluationModal
      :open="showQCEvaluation"
      @update:open="handleEvaluationOpenChange"
    />
  </div>
</template>

<script setup lang="ts">
import { useSemanticRulesWorkspace } from './composables/useSemanticRulesWorkspace'
import SemanticRulesOverviewPanels from './components/SemanticRulesOverviewPanels.vue'
import SemanticRulesTableSection from './components/SemanticRulesTableSection.vue'
import SemanticRuleDetailModal from './components/modals/SemanticRuleDetailModal.vue'
import SemanticRuleEvaluationModal from './components/modals/SemanticRuleEvaluationModal.vue'
import SemanticRuleTestModal from './components/modals/SemanticRuleTestModal.vue'

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
  showQCEvaluation,
  openQCEvaluation,
  closeQCEvaluation,
  goCustomWorkspace,
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

function handleEvaluationOpenChange(value: boolean) {
  if (!value) {
    closeQCEvaluation()
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
