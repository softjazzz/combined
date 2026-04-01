<template>
  <div class="custom-rule-workspace">
    <section class="ops-context">
      <div>
        <p class="ops-eyebrow">
          Custom Rule Workspace
        </p>
        <h1 class="ops-title">
          自定义规则工作台
        </h1>
        <p class="ops-subtitle">
          在统一页面完成草稿创建、Prompt 生成、病历批量质控和发布入库。
        </p>
      </div>
      <div class="ops-kpis">
        <div class="ops-kpi">
          <span class="ops-kpi-label">草稿总数</span>
          <span class="ops-kpi-value">{{ draftPagination.total }}</span>
        </div>
        <div class="ops-kpi">
          <span class="ops-kpi-label">当前范围</span>
          <span class="ops-kpi-value">{{ scopeLabelMap[recordFilters.scope] }}</span>
        </div>
        <div class="ops-kpi">
          <span class="ops-kpi-label">已选病历</span>
          <span class="ops-kpi-value">{{ selectedRecordKeys.length }}</span>
        </div>
      </div>
    </section>

    <section class="workspace-grid workspace-grid-half">
      <article class="workspace-panel">
        <div class="panel-head">
          <div>
            <p class="panel-eyebrow">
              Draft List
            </p>
            <h2 class="panel-title">
              1. 规则草稿列表
            </h2>
          </div>
          <a-button
            size="small"
            :loading="draftLoading"
            @click="loadDrafts"
          >
            <template #icon>
              <ReloadOutlined />
            </template>
            刷新
          </a-button>
        </div>

        <div class="draft-filters">
          <a-input
            v-model:value="draftQuery.keyword"
            allow-clear
            placeholder="搜索规则编码/名称"
            @press-enter="searchDrafts"
          >
            <template #prefix>
              <SearchOutlined />
            </template>
          </a-input>
          <a-select
            v-model:value="draftQuery.status"
            allow-clear
            placeholder="状态"
            :options="draftStatusOptions"
            @change="searchDrafts"
          />
        </div>

        <a-table
          row-key="id"
          size="small"
          :loading="draftLoading"
          :columns="draftColumns"
          :data-source="drafts"
          :pagination="draftPagination"
          :scroll="{ y: 260 }"
          @change="handleDraftTableChange"
        >
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'rule_code'">
              <button
                class="rule-code-pill"
                :class="{ active: selectedDraftId === record.id }"
                @click="selectDraft(record as CustomRuleDraft)"
              >
                {{ record.rule_code }}
              </button>
            </template>
            <template v-else-if="column.key === 'name'">
              <div class="draft-title">
                {{ record.name || '未命名草稿' }}
              </div>
              <div class="draft-subtitle">
                {{ record.description || '-' }}
              </div>
            </template>
            <template v-else-if="column.key === 'status'">
              <a-tag :color="record.status === 'published' ? 'success' : 'processing'">
                {{ record.status === 'published' ? '已发布' : '草稿' }}
              </a-tag>
            </template>
            <template v-else-if="column.key === 'actions'">
              <div class="draft-actions">
                <a-tooltip title="继续编辑">
                  <a-button
                    type="text"
                    size="small"
                    @click="selectDraft(record as CustomRuleDraft)"
                  >
                    <template #icon>
                      <EditOutlined />
                    </template>
                  </a-button>
                </a-tooltip>
                <a-tooltip title="复制草稿">
                  <a-button
                    type="text"
                    size="small"
                    @click="copyDraft(record as CustomRuleDraft)"
                  >
                    <template #icon>
                      <CopyOutlined />
                    </template>
                  </a-button>
                </a-tooltip>
                <a-popconfirm
                  title="确认删除该草稿？"
                  @confirm="deleteDraft(record as CustomRuleDraft)"
                >
                  <a-button
                    type="text"
                    danger
                    size="small"
                  >
                    <template #icon>
                      <DeleteOutlined />
                    </template>
                  </a-button>
                </a-popconfirm>
                <a-button
                  v-if="record.status === 'draft'"
                  type="link"
                  size="small"
                  :disabled="!canPublishRecord(record as CustomRuleDraft)"
                  @click="publishDraftById(record.id)"
                >
                  发布
                </a-button>
              </div>
            </template>
          </template>
        </a-table>
      </article>

      <article class="workspace-panel">
        <div class="panel-head">
          <div>
            <p class="panel-eyebrow">
              Draft Creator
            </p>
            <h2 class="panel-title">
              2. 规则创建区
            </h2>
          </div>
          <a-button
            type="primary"
            :loading="creatingDraft"
            @click="createDraft"
          >
            <template #icon>
              <PlusOutlined />
            </template>
            创建草稿
          </a-button>
        </div>

        <a-form layout="vertical">
          <div class="form-grid">
            <a-form-item
              label="规则名称"
              required
            >
              <a-input
                v-model:value="createForm.name"
                placeholder="例如：出院记录缺少出院带药明细"
              />
            </a-form-item>
            <a-form-item
              label="适用文书"
              required
            >
              <a-select
                v-model:value="createForm.document_type"
                :options="documentTypeOptions"
              />
            </a-form-item>
          </div>
          <div class="form-grid">
            <a-form-item label="病历范围">
              <a-select
                v-model:value="createForm.scene"
                :options="sceneOptions"
              />
            </a-form-item>
            <a-form-item label="复杂度">
              <a-select
                v-model:value="createForm.complexity"
                :options="complexityOptions"
              />
            </a-form-item>
          </div>
          <div class="form-grid">
            <a-form-item label="缺陷级别">
              <a-select
                v-model:value="createForm.defect_level"
                :options="defectLevelOptions"
              />
            </a-form-item>
            <a-form-item label="严重程度">
              <a-select
                v-model:value="createForm.severity"
                :options="severityOptions"
              />
            </a-form-item>
          </div>
          <a-form-item
            label="需求描述"
            required
          >
            <a-textarea
              v-model:value="createForm.source_requirement"
              :rows="5"
              :maxlength="1200"
              show-count
              placeholder="描述你希望 AI 检查的问题边界、证据形式和建议口径。"
            />
          </a-form-item>
        </a-form>
      </article>
    </section>

    <section class="workspace-panel">
      <div class="panel-head">
        <div>
          <p class="panel-eyebrow">
            Prompt Editor
          </p>
          <h2 class="panel-title">
            3. Prompt 生成与编辑
          </h2>
        </div>
        <div class="panel-actions">
          <a-button
            :disabled="!selectedDraft"
            :loading="generatingPrompt"
            @click="generatePromptForDraft"
          >
            <template #icon>
              <RobotOutlined />
            </template>
            AI 生成 Prompt
          </a-button>
          <a-button
            type="primary"
            :disabled="!selectedDraft"
            :loading="savingDraft"
            @click="saveDraftEditor"
          >
            保存草稿
          </a-button>
        </div>
      </div>

      <a-alert
        :type="editorGenerationMode === 'llm' ? 'success' : 'warning'"
        show-icon
        :message="
          editorGenerationMode === 'llm' ? '当前 Prompt 来自 AI 生成' : '当前 Prompt 为模板回退'
        "
        :description="editorPromptSummary || '请先选中草稿后生成 Prompt，也可手工编辑。'"
      />

      <div
        v-if="editorCheckPoints.length > 0"
        class="check-point-list"
      >
        <div class="check-point-title">
          生成检查要点
        </div>
        <div
          v-for="(item, idx) in editorCheckPoints"
          :key="`${idx}-${item}`"
          class="check-point-item"
        >
          {{ idx + 1 }}. {{ item }}
        </div>
      </div>

      <a-form
        layout="vertical"
        class="mt-4"
      >
        <div class="form-grid">
          <a-form-item
            label="规则名称"
            required
          >
            <a-input
              v-model:value="editorForm.name"
              :disabled="!selectedDraft"
            />
          </a-form-item>
          <a-form-item label="适用文书">
            <a-select
              v-model:value="editorForm.document_type"
              :options="documentTypeOptions"
              :disabled="!selectedDraft"
            />
          </a-form-item>
        </div>
        <a-form-item
          label="规则描述"
          required
        >
          <a-textarea
            v-model:value="editorForm.description"
            :rows="4"
            :disabled="!selectedDraft"
          />
        </a-form-item>
        <a-form-item
          label="Prompt 模板"
          required
        >
          <a-textarea
            v-model:value="editorForm.prompt_template"
            :rows="10"
            :disabled="!selectedDraft"
          />
        </a-form-item>
        <div class="form-grid">
          <a-form-item label="合规示例">
            <a-textarea
              v-model:value="editorForm.positive_example"
              :rows="4"
              :disabled="!selectedDraft"
            />
          </a-form-item>
          <a-form-item label="不合规模例">
            <a-textarea
              v-model:value="editorForm.negative_example"
              :rows="4"
              :disabled="!selectedDraft"
            />
          </a-form-item>
        </div>
      </a-form>
    </section>

    <section class="workspace-panel">
      <div class="panel-head">
        <div>
          <p class="panel-eyebrow">
            Record QA
          </p>
          <h2 class="panel-title">
            4. 病历筛选与批量质控
          </h2>
        </div>
        <div class="panel-actions">
          <a-button
            :disabled="!selectedDraft || selectedRecordKeys.length === 0"
            :loading="testingBatch"
            @click="runBatchTest"
          >
            <template #icon>
              <PlayCircleOutlined />
            </template>
            批量质控
          </a-button>
          <a-button
            type="primary"
            :disabled="!selectedDraft || !canPublishSelectedDraft"
            :loading="publishingDraft"
            @click="publishSelectedDraft"
          >
            <template #icon>
              <RocketOutlined />
            </template>
            发布到正式规则库
          </a-button>
        </div>
      </div>

      <div class="record-filter-grid">
        <a-select
          v-model:value="recordFilters.scope"
          :options="scopeOptions"
        />
        <a-select
          v-model:value="recordFilters.department"
          allow-clear
          show-search
          :options="departmentOptions"
          placeholder="科室"
          @change="handleDepartmentChange"
        />
        <a-select
          v-model:value="recordFilters.doctor"
          allow-clear
          show-search
          :options="doctorOptions"
          placeholder="医生"
        />
        <a-select
          v-model:value="recordFilters.date_field"
          :options="dateFieldOptions"
        />
        <a-range-picker v-model:value="recordFilters.dateRange" />
        <a-input
          v-model:value="recordFilters.keyword"
          allow-clear
          placeholder="关键词：患者/住院号/visit"
          @press-enter="searchRecords"
        />
        <a-button
          :loading="recordLoading"
          @click="searchRecords"
        >
          查询病历
        </a-button>
      </div>

      <a-form
        layout="vertical"
        class="advanced-grid"
      >
        <a-form-item label="temperature">
          <a-input-number
            v-model:value="advancedParams.temperature"
            :min="0"
            :max="2"
            :step="0.1"
            class="w-full"
          />
        </a-form-item>
        <a-form-item label="top_p">
          <a-input-number
            v-model:value="advancedParams.top_p"
            :min="0"
            :max="1"
            :step="0.05"
            class="w-full"
          />
        </a-form-item>
        <a-form-item label="max_tokens">
          <a-input-number
            v-model:value="advancedParams.max_tokens"
            :min="256"
            :max="16000"
            :step="256"
            class="w-full"
          />
        </a-form-item>
      </a-form>

      <div class="record-toolbar">
        <span>已选择 {{ selectedRecordKeys.length }} 条病历</span>
        <div class="panel-actions">
          <a-button
            size="small"
            @click="selectCurrentPageRecords"
          >
            全选当前页
          </a-button>
          <a-button
            size="small"
            @click="selectedRecordKeys = []"
          >
            清空
          </a-button>
        </div>
      </div>

      <a-table
        row-key="record_id"
        size="small"
        :loading="recordLoading"
        :columns="recordColumns"
        :data-source="records"
        :pagination="recordPagination"
        :row-selection="recordRowSelection"
        :scroll="{ x: 1100, y: 360 }"
        @change="handleRecordTableChange"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'scope'">
            <a-tag
              :color="
                record.scope === 'final' ? 'blue' : record.scope === 'running' ? 'gold' : 'default'
              "
            >
              {{ scopeLabelMap[record.scope] }}
            </a-tag>
          </template>
          <template v-else-if="column.key === 'actions'">
            <a-button
              type="link"
              size="small"
              :disabled="!selectedDraft"
              :loading="testingSingleRecordId === record.record_id"
              @click="runSingleTest(record as CustomRuleWorkspaceRecord)"
            >
              单条质控
            </a-button>
          </template>
        </template>
      </a-table>

      <div class="result-grid">
        <div class="result-panel">
          <h3>批量结果摘要</h3>
          <a-empty
            v-if="!batchResult"
            description="执行批量质控后展示统计"
          />
          <template v-else>
            <div class="result-kpis">
              <div class="result-kpi">
                <span>总病历</span>
                <strong>{{ batchResult.summary.total_records }}</strong>
              </div>
              <div class="result-kpi">
                <span>成功</span>
                <strong>{{ batchResult.summary.success_count }}</strong>
              </div>
              <div class="result-kpi">
                <span>失败</span>
                <strong>{{ batchResult.summary.failed_count }}</strong>
              </div>
              <div class="result-kpi">
                <span>命中问题</span>
                <strong>{{ batchResult.summary.issue_records }}</strong>
              </div>
              <div class="result-kpi">
                <span>总耗时</span>
                <strong>{{ batchResult.summary.total_processing_time.toFixed(2) }}s</strong>
              </div>
            </div>
          </template>
        </div>

        <div class="result-panel">
          <h3>单病历结果</h3>
          <a-empty
            v-if="!singleResult"
            description="点击病历行的单条质控查看"
          />
          <template v-else>
            <a-tag :color="singleResult.result.is_compliant ? 'success' : 'error'">
              {{ singleResult.result.is_compliant ? '合规/不适用' : '命中问题' }}
            </a-tag>
            <p class="result-text">
              {{ singleResult.result.findings || '无附加结论' }}
            </p>
            <p class="result-text">
              证据：{{ singleResult.result.evidence || '无' }}
            </p>
            <p class="result-text">
              建议：{{ singleResult.result.suggestion || '无' }}
            </p>
          </template>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import type { Dayjs } from 'dayjs'
import { message } from 'ant-design-vue'
import type { TableColumnsType, TableProps } from 'ant-design-vue'
import {
  CopyOutlined,
  DeleteOutlined,
  EditOutlined,
  PlayCircleOutlined,
  PlusOutlined,
  ReloadOutlined,
  RobotOutlined,
  RocketOutlined,
  SearchOutlined,
} from '@ant-design/icons-vue'
import {
  createWorkspaceDraft,
  deleteWorkspaceDraft,
  generateWorkspaceDraftPrompt,
  getWorkspaceRecordFilters,
  getWorkspaceRecords,
  listWorkspaceDrafts,
  publishWorkspaceDraft,
  runWorkspaceBatchTest,
  runWorkspaceSingleTest,
  updateWorkspaceDraft,
} from '@/services/custom-rule-workspace-service'
import type {
  CustomRuleBatchResult,
  CustomRuleDraft,
  CustomRuleDraftPayload,
  CustomRuleSingleTestResult,
  CustomRuleWorkspaceRecord,
  WorkspaceDraftStatus,
  WorkspaceScope,
  WorkspaceSeverity,
} from '@/types/custom-rule-workspace'

type DateRangeValue = [Dayjs, Dayjs] | null

const draftLoading = ref(false)
const creatingDraft = ref(false)
const savingDraft = ref(false)
const generatingPrompt = ref(false)
const publishingDraft = ref(false)
const testingBatch = ref(false)
const testingSingleRecordId = ref('')
const drafts = ref<CustomRuleDraft[]>([])
const selectedDraftId = ref('')
const singleResult = ref<CustomRuleSingleTestResult | null>(null)
const batchResult = ref<CustomRuleBatchResult | null>(null)

const draftQuery = reactive({
  keyword: '',
  status: undefined as WorkspaceDraftStatus | undefined,
})

const draftPagination = reactive({
  current: 1,
  pageSize: 8,
  total: 0,
  showSizeChanger: true,
  showQuickJumper: true,
  showTotal: (total: number) => `共 ${total} 条`,
})

const createForm = reactive({
  name: '',
  source_requirement: '',
  document_type: '入院记录',
  scene: 'running' as 'running' | 'final',
  severity: 'major' as WorkspaceSeverity,
  defect_level: '一般缺陷',
  complexity: '中复杂度',
})

const editorForm = reactive({
  name: '',
  description: '',
  prompt_template: '',
  source_requirement: '',
  document_type: '入院记录',
  scene: 'running' as 'running' | 'final',
  severity: 'major' as WorkspaceSeverity,
  defect_level: '一般缺陷',
  complexity: '中复杂度',
  generation_mode: 'fallback_template' as 'llm' | 'fallback_template',
  positive_example: '',
  negative_example: '',
  check_logic: {} as Record<string, unknown>,
})

const editorPromptSummary = ref('')
const editorCheckPoints = ref<string[]>([])

const draftStatusOptions = [
  { label: '草稿', value: 'draft' },
  { label: '已发布', value: 'published' },
]

const documentTypeOptions = [
  { label: '入院记录', value: '入院记录' },
  { label: '病程记录', value: '病程记录' },
  { label: '首次病程记录', value: '首次病程记录' },
  { label: '出院记录', value: '出院记录' },
  { label: '手术记录', value: '手术记录' },
]

const sceneOptions = [
  { label: '运行病历', value: 'running' },
  { label: '终末病历', value: 'final' },
]

const severityOptions = [
  { label: '严重', value: 'critical' },
  { label: '一般', value: 'major' },
  { label: '提示', value: 'minor' },
]

const defectLevelOptions = [
  { label: '严重缺陷', value: '严重缺陷' },
  { label: '一般缺陷', value: '一般缺陷' },
  { label: '提示性缺陷', value: '提示性缺陷' },
]

const complexityOptions = [
  { label: '低复杂度', value: '低复杂度' },
  { label: '中复杂度', value: '中复杂度' },
  { label: '高复杂度', value: '高复杂度' },
]

const selectedDraft = computed(
  () => drafts.value.find((item) => item.id === selectedDraftId.value) || null,
)

const canPublishSelectedDraft = computed(
  () =>
    !!selectedDraft.value &&
    selectedDraft.value.status === 'draft' &&
    hasSuccessfulTest(selectedDraft.value),
)

const editorGenerationMode = computed(
  () => editorForm.generation_mode || selectedDraft.value?.generation_mode || 'fallback_template',
)

const draftColumns: TableColumnsType<CustomRuleDraft> = [
  { title: '编码', dataIndex: 'rule_code', key: 'rule_code', width: 110 },
  { title: '规则', dataIndex: 'name', key: 'name' },
  { title: '状态', dataIndex: 'status', key: 'status', width: 90 },
  { title: '操作', key: 'actions', width: 170, fixed: 'right' },
]

function hasSuccessfulTest(draft: CustomRuleDraft): boolean {
  return Number((draft.last_test_summary || {}).success_count || 0) > 0
}

function getExamplesFromDraft(draft: CustomRuleDraft): { positive: string; negative: string } {
  const examples = Array.isArray(draft.examples) ? draft.examples : []
  const positive = examples.find((item) => String(item.title || '').includes('合规'))?.content || ''
  const negative =
    examples.find((item) => String(item.title || '').includes('不合规'))?.content || ''
  return { positive, negative }
}

function hydrateEditorFromDraft(draft: CustomRuleDraft) {
  const examples = getExamplesFromDraft(draft)
  editorForm.name = draft.name || ''
  editorForm.description = draft.description || ''
  editorForm.prompt_template = draft.prompt_template || ''
  editorForm.source_requirement = draft.source_requirement || ''
  editorForm.document_type = draft.document_type || '入院记录'
  editorForm.scene = draft.scene || 'running'
  editorForm.severity = draft.severity || 'major'
  editorForm.defect_level = draft.defect_level || '一般缺陷'
  editorForm.complexity = draft.complexity || '中复杂度'
  editorForm.generation_mode = draft.generation_mode || 'fallback_template'
  editorForm.positive_example = examples.positive
  editorForm.negative_example = examples.negative
  editorForm.check_logic = (draft.check_logic || {}) as Record<string, unknown>
  editorPromptSummary.value = String((draft.check_logic || {}).last_prompt_summary || '')
  editorCheckPoints.value = Array.isArray((draft.check_logic || {}).generated_check_points)
    ? ((draft.check_logic || {}).generated_check_points as string[])
    : []
}

async function loadDrafts() {
  draftLoading.value = true
  try {
    const response = await listWorkspaceDrafts({
      page: draftPagination.current,
      page_size: draftPagination.pageSize,
      status: draftQuery.status,
      q: draftQuery.keyword || undefined,
    })
    if (!response.success || !response.data) {
      throw new Error(response.message || '获取草稿列表失败')
    }
    drafts.value = response.data.items
    draftPagination.total = response.data.total
    if (!selectedDraftId.value && drafts.value.length > 0) {
      selectedDraftId.value = drafts.value[0].id
    }
    const currentDraft = drafts.value.find((item) => item.id === selectedDraftId.value)
    if (currentDraft) {
      hydrateEditorFromDraft(currentDraft)
    }
  } catch (error: any) {
    message.error(error?.message || '获取草稿列表失败')
  } finally {
    draftLoading.value = false
  }
}

function searchDrafts() {
  draftPagination.current = 1
  loadDrafts()
}

function handleDraftTableChange(pagination: { current?: number; pageSize?: number }) {
  draftPagination.current = pagination.current || 1
  draftPagination.pageSize = pagination.pageSize || 8
  loadDrafts()
}

function selectDraft(record: CustomRuleDraft) {
  selectedDraftId.value = record.id
  hydrateEditorFromDraft(record)
  singleResult.value = null
  batchResult.value = null
}

function mapDefectLevelToSeverity(defectLevel: string): WorkspaceSeverity {
  if (defectLevel === '严重缺陷') return 'critical'
  if (defectLevel === '提示性缺陷') return 'minor'
  return 'major'
}

async function createDraft() {
  const name = createForm.name.trim()
  const requirement = createForm.source_requirement.trim()
  if (!name) {
    message.warning('请先填写规则名称')
    return
  }
  if (!requirement) {
    message.warning('请先填写需求描述')
    return
  }

  creatingDraft.value = true
  try {
    const payload: CustomRuleDraftPayload = {
      name,
      description: requirement,
      source_requirement: requirement,
      document_type: createForm.document_type,
      severity: createForm.severity || mapDefectLevelToSeverity(createForm.defect_level),
      defect_level: createForm.defect_level,
      complexity: createForm.complexity,
      scene: createForm.scene,
      applicable_documents: [createForm.document_type],
      generation_mode: 'fallback_template',
      check_logic: {
        source: 'custom_rule_workspace',
        scene: createForm.scene,
        applicable_documents: [createForm.document_type],
      },
    }
    const response = await createWorkspaceDraft(payload)
    if (!response.success || !response.data) {
      throw new Error(response.message || '创建草稿失败')
    }
    message.success(`草稿 ${response.data.rule_code} 已创建`)
    selectedDraftId.value = response.data.id
    await loadDrafts()
    selectDraft(response.data)
  } catch (error: any) {
    message.error(error?.message || '创建草稿失败')
  } finally {
    creatingDraft.value = false
  }
}

function buildEditorExamples() {
  const examples: Array<{ title: string; content: string }> = []
  if (editorForm.positive_example.trim()) {
    examples.push({ title: '合规示例', content: editorForm.positive_example.trim() })
  }
  if (editorForm.negative_example.trim()) {
    examples.push({ title: '不合规模例', content: editorForm.negative_example.trim() })
  }
  return examples
}

async function saveDraftEditor() {
  if (!selectedDraft.value) {
    message.warning('请先选择草稿')
    return
  }
  const name = editorForm.name.trim()
  const description = editorForm.description.trim()
  const promptTemplate = editorForm.prompt_template.trim()
  if (!name || !description || !promptTemplate) {
    message.warning('规则名称、描述、Prompt 均不能为空')
    return
  }
  savingDraft.value = true
  try {
    const response = await updateWorkspaceDraft(selectedDraft.value.id, {
      name,
      description,
      source_requirement: editorForm.source_requirement || description,
      prompt_template: promptTemplate,
      document_type: editorForm.document_type,
      scene: editorForm.scene,
      severity: editorForm.severity,
      defect_level: editorForm.defect_level,
      complexity: editorForm.complexity,
      generation_mode: editorForm.generation_mode,
      examples: buildEditorExamples(),
      check_logic: {
        ...(editorForm.check_logic || {}),
        last_prompt_summary: editorPromptSummary.value,
        generated_check_points: editorCheckPoints.value,
      },
      applicable_documents: [editorForm.document_type],
    })
    if (!response.success || !response.data) {
      throw new Error(response.message || '保存草稿失败')
    }
    const next = response.data
    drafts.value = drafts.value.map((item) => (item.id === next.id ? next : item))
    selectDraft(next)
    message.success('草稿已保存')
  } catch (error: any) {
    message.error(error?.message || '保存草稿失败')
  } finally {
    savingDraft.value = false
  }
}

async function generatePromptForDraft() {
  if (!selectedDraft.value) {
    message.warning('请先选择草稿')
    return
  }
  generatingPrompt.value = true
  try {
    await saveDraftEditor()
    const response = await generateWorkspaceDraftPrompt(selectedDraft.value.id)
    if (!response.success || !response.data) {
      throw new Error(response.message || '生成 Prompt 失败')
    }
    const { draft, prompt_result: promptResult } = response.data
    drafts.value = drafts.value.map((item) => (item.id === draft.id ? draft : item))
    selectDraft(draft)
    editorPromptSummary.value = promptResult.summary || ''
    editorCheckPoints.value = promptResult.check_points || []
    message.success(
      promptResult.generation_mode === 'llm' ? 'Prompt 生成成功' : '已回退模板 Prompt',
    )
  } catch (error: any) {
    message.error(error?.message || '生成 Prompt 失败')
  } finally {
    generatingPrompt.value = false
  }
}

async function copyDraft(record: CustomRuleDraft) {
  try {
    const response = await createWorkspaceDraft({
      name: `${record.name}-副本`,
      description: record.description,
      source_requirement: record.source_requirement,
      prompt_template: record.prompt_template,
      document_type: record.document_type,
      severity: record.severity,
      defect_level: record.defect_level,
      complexity: record.complexity,
      scene: record.scene,
      generation_mode: record.generation_mode,
      applicable_documents: record.applicable_documents,
      examples: record.examples,
      check_logic: record.check_logic,
    })
    if (!response.success || !response.data) {
      throw new Error(response.message || '复制草稿失败')
    }
    message.success('草稿已复制')
    selectedDraftId.value = response.data.id
    await loadDrafts()
  } catch (error: any) {
    message.error(error?.message || '复制草稿失败')
  }
}

async function deleteDraft(record: CustomRuleDraft) {
  try {
    const response = await deleteWorkspaceDraft(record.id)
    if (!response.success) {
      throw new Error(response.message || '删除草稿失败')
    }
    message.success('草稿已删除')
    if (selectedDraftId.value === record.id) {
      selectedDraftId.value = ''
    }
    await loadDrafts()
  } catch (error: any) {
    message.error(error?.message || '删除草稿失败')
  }
}

async function publishDraftById(draftId: string) {
  publishingDraft.value = true
  try {
    const response = await publishWorkspaceDraft(draftId)
    if (!response.success || !response.data) {
      throw new Error(response.message || '发布失败')
    }
    message.success(`发布成功：${response.data.rule_code}`)
    await loadDrafts()
  } catch (error: any) {
    message.error(error?.message || '发布失败')
  } finally {
    publishingDraft.value = false
  }
}

async function publishSelectedDraft() {
  if (!selectedDraft.value) {
    message.warning('请先选择草稿')
    return
  }
  if (!canPublishSelectedDraft.value) {
    message.warning('请先完成至少一次成功测试')
    return
  }
  await saveDraftEditor()
  await publishDraftById(selectedDraft.value.id)
}

function canPublishRecord(record: CustomRuleDraft): boolean {
  return record.status === 'draft' && hasSuccessfulTest(record)
}

const scopeLabelMap: Record<WorkspaceScope, string> = {
  all: '全部病历',
  running: '运行病历',
  final: '终末病历',
}

const scopeOptions = [
  { label: scopeLabelMap.all, value: 'all' },
  { label: scopeLabelMap.running, value: 'running' },
  { label: scopeLabelMap.final, value: 'final' },
]

const dateFieldOptions = [
  { label: '按入院日期', value: 'admission' },
  { label: '按出院日期', value: 'discharge' },
]

const recordFilters = reactive({
  scope: 'all' as WorkspaceScope,
  department: undefined as string | undefined,
  doctor: undefined as string | undefined,
  date_field: 'admission' as 'admission' | 'discharge',
  dateRange: null as DateRangeValue,
  keyword: '',
})

const departmentOptions = ref<Array<{ label: string; value: string }>>([])
const doctorOptions = ref<Array<{ label: string; value: string }>>([])
const recordLoading = ref(false)
const records = ref<CustomRuleWorkspaceRecord[]>([])
const selectedRecordKeys = ref<string[]>([])

const recordPagination = reactive({
  current: 1,
  pageSize: 20,
  total: 0,
  showSizeChanger: true,
  showQuickJumper: true,
  showTotal: (total: number) => `共 ${total} 条病历`,
})

const recordColumns: TableColumnsType<CustomRuleWorkspaceRecord> = [
  { title: '患者', dataIndex: 'patient_name', key: 'patient_name', width: 120 },
  { title: '住院号/visit', dataIndex: 'visit_id', key: 'visit_id', width: 140 },
  { title: '病历范围', dataIndex: 'scope', key: 'scope', width: 100 },
  { title: '科室', dataIndex: 'department', key: 'department', width: 140 },
  { title: '医生', dataIndex: 'doctor', key: 'doctor', width: 140 },
  { title: '入院日期', dataIndex: 'admission_date', key: 'admission_date', width: 120 },
  { title: '出院日期', dataIndex: 'discharge_date', key: 'discharge_date', width: 120 },
  { title: '操作', key: 'actions', width: 110, fixed: 'right' as const },
]

const recordRowSelection = computed<TableProps['rowSelection']>(() => ({
  selectedRowKeys: selectedRecordKeys.value,
  onChange: (keys: Array<string | number>) => {
    selectedRecordKeys.value = keys.map((item) => String(item))
  },
}))

const advancedParams = reactive({
  temperature: 0.2,
  top_p: 0.9,
  max_tokens: 4096,
})

function selectedTestRecords() {
  const keySet = new Set(selectedRecordKeys.value)
  return records.value
    .filter((item) => keySet.has(item.record_id))
    .map((item) => ({
      record_id: item.record_id,
      visit_id: item.visit_id,
      patient_name: item.patient_name,
      department: item.department,
      doctor: item.doctor,
    }))
}

async function loadRecordFilters() {
  const response = await getWorkspaceRecordFilters({
    scope: recordFilters.scope,
    department: recordFilters.department,
  })
  if (!response.success || !response.data) {
    throw new Error(response.message || '获取筛选项失败')
  }
  departmentOptions.value = (response.data.departments || []).map((item) => ({
    label: item,
    value: item,
  }))
  doctorOptions.value = (response.data.doctors || []).map((item) => ({
    label: item,
    value: item,
  }))
}

async function loadRecords() {
  recordLoading.value = true
  try {
    const response = await getWorkspaceRecords({
      scope: recordFilters.scope,
      department: recordFilters.department,
      doctor: recordFilters.doctor,
      date_field: recordFilters.date_field,
      start_date: recordFilters.dateRange?.[0]?.format('YYYY-MM-DD'),
      end_date: recordFilters.dateRange?.[1]?.format('YYYY-MM-DD'),
      keyword: recordFilters.keyword || undefined,
      page: recordPagination.current,
      page_size: recordPagination.pageSize,
    })
    if (!response.success || !response.data) {
      throw new Error(response.message || '获取病历列表失败')
    }
    records.value = response.data.items
    recordPagination.total = response.data.total
  } catch (error: any) {
    message.error(error?.message || '获取病历列表失败')
  } finally {
    recordLoading.value = false
  }
}

async function searchRecords() {
  recordPagination.current = 1
  await Promise.all([loadRecordFilters(), loadRecords()])
}

async function handleDepartmentChange() {
  recordFilters.doctor = undefined
  await loadRecordFilters()
}

function handleRecordTableChange(pagination: { current?: number; pageSize?: number }) {
  recordPagination.current = pagination.current || 1
  recordPagination.pageSize = pagination.pageSize || 20
  loadRecords()
}

function selectCurrentPageRecords() {
  selectedRecordKeys.value = Array.from(
    new Set([...selectedRecordKeys.value, ...records.value.map((item) => item.record_id)]),
  )
}

function syncDraftSummary(summary: Record<string, unknown>) {
  if (!selectedDraft.value) return
  drafts.value = drafts.value.map((item) =>
    item.id === selectedDraft.value?.id
      ? {
          ...item,
          last_test_summary: summary,
        }
      : item,
  )
}

async function runSingleTest(record: CustomRuleWorkspaceRecord) {
  if (!selectedDraft.value) {
    message.warning('请先选择草稿规则')
    return
  }
  testingSingleRecordId.value = record.record_id
  try {
    await saveDraftEditor()
    const response = await runWorkspaceSingleTest({
      draft_id: selectedDraft.value.id,
      records: [
        {
          record_id: record.record_id,
          visit_id: record.visit_id,
          patient_name: record.patient_name,
          department: record.department,
          doctor: record.doctor,
        },
      ],
      temperature: advancedParams.temperature,
      top_p: advancedParams.top_p,
      max_tokens: advancedParams.max_tokens,
    })
    if (!response.success || !response.data) {
      throw new Error(response.message || '单病历测试失败')
    }
    singleResult.value = response.data
    batchResult.value = null
    syncDraftSummary(response.data.summary || {})
    message.success('单病历测试完成')
  } catch (error: any) {
    message.error(error?.message || '单病历测试失败')
  } finally {
    testingSingleRecordId.value = ''
  }
}

async function runBatchTest() {
  if (!selectedDraft.value) {
    message.warning('请先选择草稿规则')
    return
  }
  const selectedRecords = selectedTestRecords()
  if (selectedRecords.length === 0) {
    message.warning('请先选择病历')
    return
  }
  if (selectedRecords.length === 1) {
    const target = records.value.find((item) => item.record_id === selectedRecords[0].record_id)
    if (target) {
      await runSingleTest(target)
      return
    }
  }

  testingBatch.value = true
  try {
    await saveDraftEditor()
    const response = await runWorkspaceBatchTest({
      draft_id: selectedDraft.value.id,
      records: selectedRecords,
      temperature: advancedParams.temperature,
      top_p: advancedParams.top_p,
      max_tokens: advancedParams.max_tokens,
    })
    if (!response.success || !response.data) {
      throw new Error(response.message || '批量测试失败')
    }
    batchResult.value = response.data
    singleResult.value = null
    syncDraftSummary(response.data.summary || {})
    message.success('批量质控完成')
  } catch (error: any) {
    message.error(error?.message || '批量测试失败')
  } finally {
    testingBatch.value = false
  }
}

watch(
  () => selectedDraftId.value,
  () => {
    const draft = selectedDraft.value
    if (draft) {
      hydrateEditorFromDraft(draft)
    }
  },
)

watch(
  () => recordFilters.scope,
  async () => {
    recordFilters.department = undefined
    recordFilters.doctor = undefined
    await searchRecords()
  },
)

onMounted(async () => {
  await Promise.all([loadDrafts(), searchRecords()])
})
</script>

<style scoped>
.custom-rule-workspace {
  --panel-bg: linear-gradient(180deg, #ffffff 0%, #f8fbff 100%);
  --panel-border: #dbe7f5;
  --panel-shadow: 0 14px 30px rgba(15, 23, 42, 0.06);
  --ink-strong: #0f2747;
  --ink-main: #1f3b63;
  --ink-muted: #6a7d99;
  min-height: 100%;
  padding: 14px;
  color: var(--ink-main);
}

.ops-context {
  display: flex;
  justify-content: space-between;
  gap: 14px;
  align-items: flex-start;
  border: 1px solid var(--panel-border);
  border-radius: 18px;
  background: radial-gradient(circle at right top, #edf4ff 0%, #ffffff 55%);
  box-shadow: var(--panel-shadow);
  padding: 16px 18px;
  margin-bottom: 12px;
}

.ops-eyebrow {
  margin: 0 0 4px;
  font-size: 11px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: #597198;
  font-weight: 600;
}

.ops-title {
  margin: 0;
  font-size: 1.4rem;
  font-weight: 700;
  color: var(--ink-strong);
}

.ops-subtitle {
  margin: 8px 0 0;
  color: var(--ink-muted);
  font-size: 13px;
}

.ops-kpis {
  display: grid;
  grid-template-columns: repeat(3, minmax(88px, 1fr));
  gap: 10px;
  width: min(420px, 100%);
}

.ops-kpi {
  border: 1px solid #dce8fb;
  border-radius: 12px;
  padding: 8px 10px;
  background: rgba(255, 255, 255, 0.9);
  display: flex;
  flex-direction: column;
}

.ops-kpi-label {
  font-size: 11px;
  color: #6f82a0;
}

.ops-kpi-value {
  margin-top: 2px;
  font-size: 14px;
  font-weight: 700;
  color: var(--ink-strong);
}

.workspace-grid {
  display: grid;
  gap: 12px;
  margin-bottom: 12px;
}

.workspace-grid-half {
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
}

.workspace-panel {
  border-radius: 16px;
  border: 1px solid var(--panel-border);
  background: var(--panel-bg);
  box-shadow: var(--panel-shadow);
  padding: 14px;
}

.panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 10px;
}

.panel-eyebrow {
  margin: 0;
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: #6f86aa;
  font-weight: 700;
}

.panel-title {
  margin: 2px 0 0;
  font-size: 16px;
  line-height: 1.2;
  color: var(--ink-strong);
  font-weight: 700;
}

.panel-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.draft-filters {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 130px;
  gap: 8px;
  margin-bottom: 10px;
}

.rule-code-pill {
  min-width: 88px;
  padding: 5px 10px;
  border-radius: 10px;
  border: 1px solid #d3e0f5;
  background: linear-gradient(180deg, #f6faff 0%, #eaf2ff 100%);
  color: #27456b;
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
}

.rule-code-pill.active {
  border-color: #7ea6ed;
  box-shadow: 0 0 0 3px rgba(47, 111, 238, 0.12);
}

.draft-title {
  font-size: 13px;
  color: #102746;
  font-weight: 700;
  line-height: 1.45;
}

.draft-subtitle {
  margin-top: 2px;
  font-size: 11px;
  color: #7a90ad;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.draft-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 4px;
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.check-point-list {
  margin-top: 10px;
  border: 1px solid #dbe7f5;
  border-radius: 12px;
  background: rgba(247, 251, 255, 0.88);
  padding: 10px 12px;
}

.check-point-title {
  margin-bottom: 4px;
  font-size: 12px;
  font-weight: 700;
  color: #32557f;
}

.check-point-item {
  font-size: 12px;
  color: #526f95;
  line-height: 1.7;
}

.record-filter-grid {
  display: grid;
  grid-template-columns: 140px 150px 150px 120px 260px minmax(200px, 1fr) 94px;
  gap: 8px;
  margin-bottom: 10px;
}

.record-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
  font-size: 12px;
  color: #6f82a0;
}

.advanced-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
  margin-bottom: 8px;
}

.advanced-grid :deep(.ant-form-item) {
  margin-bottom: 0;
}

.result-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: 10px;
  margin-top: 10px;
}

.result-panel {
  border-radius: 12px;
  border: 1px solid #dbe7f5;
  background: #ffffff;
  padding: 10px;
}

.result-panel h3 {
  margin: 0 0 8px;
  color: #1c3f72;
  font-size: 13px;
  font-weight: 700;
}

.result-kpis {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 6px;
}

.result-kpi {
  border: 1px solid #e1ebf9;
  border-radius: 10px;
  padding: 8px;
  background: #f7fbff;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.result-kpi span {
  font-size: 11px;
  color: #6f82a0;
}

.result-kpi strong {
  font-size: 14px;
  color: #153965;
}

.result-text {
  margin-top: 6px;
  margin-bottom: 0;
  font-size: 12px;
  color: #3f5e87;
  line-height: 1.6;
}

:deep(.ant-table-thead > tr > th) {
  background: #f2f7ff !important;
  color: #36547b !important;
  font-size: 12px;
  font-weight: 600 !important;
  border-bottom: 1px solid #dbe7f5 !important;
}

:deep(.ant-table-tbody > tr > td) {
  border-bottom: 1px solid #edf3fc !important;
}

:deep(.ant-table-tbody > tr:hover > td) {
  background: #f3f8ff !important;
}

@media (max-width: 1440px) {
  .record-filter-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 1024px) {
  .workspace-grid-half {
    grid-template-columns: minmax(0, 1fr);
  }

  .ops-context {
    flex-direction: column;
  }

  .ops-kpis {
    width: 100%;
  }

  .result-grid {
    grid-template-columns: minmax(0, 1fr);
  }
}

@media (max-width: 768px) {
  .custom-rule-workspace {
    padding: 8px;
  }

  .form-grid {
    grid-template-columns: minmax(0, 1fr);
  }

  .record-filter-grid {
    grid-template-columns: minmax(0, 1fr);
  }

  .advanced-grid {
    grid-template-columns: minmax(0, 1fr);
  }

  .result-kpis {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
