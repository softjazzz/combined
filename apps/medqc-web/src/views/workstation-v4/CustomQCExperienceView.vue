<template>
  <div class="custom-qc-page">
    <div class="custom-qc-container">
      <a-card
        :bordered="false"
        class="custom-qc-surface custom-qc-hero"
      >
        <div class="custom-qc-hero-inner">
          <div>
            <div class="custom-qc-chip-row">
              <a-tag color="processing">
                {{ sceneLabel }}
              </a-tag>
              <a-tag color="blue">
                只读试跑
              </a-tag>
              <a-tag color="default">
                待人工复核后发布
              </a-tag>
            </div>
            <h1 class="custom-qc-title">
              自定义质控点工作台
            </h1>
            <p class="custom-qc-subtitle">
              按“规则定义、病历试跑、结果复核”完成自定义质控点验证。试跑过程只读病历，不写正式质控结果表。
            </p>
          </div>
          <div class="custom-qc-actions">
            <a-button
              class="custom-qc-secondary-btn"
              @click="goBack"
            >
              返回来源页
            </a-button>
            <a-button
              type="primary"
              class="custom-qc-primary-btn"
              @click="jumpToRulesList"
            >
              查看规则库
            </a-button>
          </div>
        </div>
      </a-card>

      <div class="grid gap-6 xl:grid-cols-[1.15fr_0.85fr]">
        <a-card
          :bordered="false"
          class="custom-qc-surface"
        >
          <template #title>
            1. 规则定义
          </template>
          <a-form layout="vertical">
            <div class="grid gap-4 md:grid-cols-2">
              <a-form-item
                label="质控点名称"
                required
              >
                <a-input
                  v-model:value="draftRule.name"
                  size="large"
                  placeholder="例如：出院记录未写出院带药用法"
                />
              </a-form-item>
              <a-form-item
                label="适用文书"
                required
              >
                <a-select
                  v-model:value="draftRule.document_type"
                  size="large"
                  :options="documentTypeOptions"
                />
              </a-form-item>
            </div>
            <div class="grid gap-4 md:grid-cols-2">
              <a-form-item
                label="严重程度"
                required
              >
                <a-select
                  v-model:value="draftRule.severity"
                  size="large"
                  :options="severityOptions"
                />
              </a-form-item>
              <a-form-item label="运行场景">
                <a-input
                  :value="sceneLabel"
                  size="large"
                  disabled
                />
              </a-form-item>
            </div>
            <a-form-item
              label="质控要求"
              required
            >
              <a-textarea
                v-model:value="draftRule.description"
                :rows="6"
                :maxlength="800"
                show-count
                placeholder="请描述触发条件、检查要点以及期望输出的问题类型。"
              />
            </a-form-item>
            <div class="flex flex-wrap items-center gap-3">
              <a-button
                type="primary"
                size="large"
                class="!rounded-lg"
                :loading="generatingPrompt"
                :disabled="!canGeneratePrompt"
                @click="handleGeneratePrompt"
              >
                生成检查逻辑
              </a-button>
              <a-button
                size="large"
                class="!rounded-lg"
                @click="applyExample"
              >
                填充示例
              </a-button>
            </div>
          </a-form>
        </a-card>

        <a-card
          :bordered="false"
          class="custom-qc-surface"
        >
          <template #title>
            2. 检查逻辑复核
          </template>
          <div class="space-y-4">
            <a-alert
              :type="generationMode === 'llm' ? 'success' : 'warning'"
              show-icon
              :message="
                generationMode === 'llm' ? '检查逻辑已生成' : '该能力待接入，当前使用规则草稿'
              "
              :description="promptSummary || '生成后将在这里展示摘要与检查要点。'"
            />
            <div
              v-if="generatedCheckPoints.length"
              class="rounded-2xl border border-slate-200 bg-slate-50 p-4"
            >
              <div class="mb-2 text-sm font-medium text-slate-700">
                检查要点
              </div>
              <div
                v-for="(point, index) in generatedCheckPoints"
                :key="`${index}-${point}`"
                class="text-sm leading-7 text-slate-600"
              >
                {{ index + 1 }}. {{ point }}
              </div>
            </div>
            <a-form layout="vertical">
              <a-form-item label="检查逻辑">
                <a-textarea
                  v-model:value="draftRule.prompt_template"
                  :rows="16"
                  :maxlength="8000"
                  show-count
                />
              </a-form-item>
              <div class="grid gap-4 md:grid-cols-3">
                <a-form-item label="结果稳定性">
                  <a-input-number
                    v-model:value="advancedParams.temperature"
                    :min="0"
                    :max="2"
                    :step="0.1"
                    class="!w-full"
                  />
                </a-form-item>
                <a-form-item label="候选范围">
                  <a-input-number
                    v-model:value="advancedParams.top_p"
                    :min="0"
                    :max="1"
                    :step="0.05"
                    class="!w-full"
                  />
                </a-form-item>
                <a-form-item label="最大输出长度">
                  <a-input-number
                    v-model:value="advancedParams.max_tokens"
                    :min="256"
                    :max="16000"
                    :step="256"
                    class="!w-full"
                  />
                </a-form-item>
              </div>
            </a-form>
          </div>
        </a-card>
      </div>

      <div class="grid gap-6 xl:grid-cols-[1.15fr_0.85fr]">
        <a-card
          :bordered="false"
          class="custom-qc-surface"
        >
          <template #title>
            3. 病历试跑
          </template>
          <div class="space-y-4">
            <div class="grid gap-4 lg:grid-cols-[160px_220px_1fr_auto]">
              <a-select
                v-model:value="filters.department"
                allow-clear
                size="large"
                placeholder="科室"
                :options="departmentOptions"
              />
              <a-range-picker
                v-model:value="filters.dateRange"
                size="large"
              />
              <a-input
                v-model:value="filters.keyword"
                size="large"
                placeholder="搜索病历号/姓名"
                @press-enter="handleSearchRecords"
              />
              <a-button
                size="large"
                class="!rounded-lg"
                :loading="recordsLoading"
                @click="handleSearchRecords"
              >
                刷新列表
              </a-button>
            </div>
            <div
              class="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3"
            >
              <div class="text-sm text-slate-600">
                已选择
                <span class="font-semibold text-slate-900">{{ selectedRecordKeys.length }}</span>
                条病历
                <span
                  v-if="prefillText"
                  class="ml-2 text-xs text-slate-500"
                >{{
                  prefillText
                }}</span>
              </div>
              <div class="flex flex-wrap gap-2">
                <a-button
                  class="!rounded-lg"
                  @click="selectCurrentPage"
                >
                  全选当前页
                </a-button>
                <a-button
                  class="!rounded-lg"
                  @click="selectedRecordKeys = []"
                >
                  清空选择
                </a-button>
                <a-button
                  type="primary"
                  class="!rounded-lg"
                  :loading="testing"
                  :disabled="!canRunTest"
                  @click="runSelectedTest"
                >
                  {{ selectedRecordKeys.length > 1 ? '批量试跑' : '单病历试跑' }}
                </a-button>
              </div>
            </div>
            <a-table
              row-key="record_id"
              :loading="recordsLoading"
              :columns="recordColumns"
              :data-source="records"
              :pagination="pagination"
              :row-selection="rowSelection"
              :scroll="{ x: 880 }"
              @change="handleTableChange"
            >
              <template #bodyCell="{ column, record }">
                <template v-if="column.key === 'record_id'">
                  <div class="font-mono font-semibold text-slate-800">
                    {{ record.record_id }}
                  </div>
                </template>
                <template v-if="column.key === 'status'">
                  <a-tag
                    :color="
                      record.status === 'completed' || record.status === 'passed'
                        ? 'success'
                        : 'processing'
                    "
                  >
                    {{ record.status || '-' }}
                  </a-tag>
                </template>
                <template v-if="column.key === 'action'">
                  <a-button
                    size="small"
                    class="!rounded-lg"
                    @click="runDirectSingle(record)"
                  >
                    单条试跑
                  </a-button>
                </template>
              </template>
            </a-table>
          </div>
        </a-card>

        <a-card
          :bordered="false"
          class="custom-qc-surface"
        >
          <template #title>
            4. 结果复核
          </template>
          <div class="space-y-4">
            <a-empty
              v-if="!singleResult && !batchResult"
              description="完成一次试跑后，这里会展示结果摘要、证据和复核入口。"
            />
            <div
              v-if="singleResult"
              class="space-y-3 rounded-2xl border border-slate-200 bg-slate-50 p-4"
            >
              <div class="flex items-center justify-between gap-3">
                <div class="text-sm font-medium text-slate-900">
                  单病历试跑结果
                </div>
                <a-tag :color="singleResult.result.is_compliant ? 'success' : 'error'">
                  {{ singleResult.result.is_compliant ? '合规 / 不适用' : '发现问题' }}
                </a-tag>
              </div>
              <div class="text-sm leading-7 text-slate-700">
                {{ singleResult.result.findings || '无补充说明' }}
              </div>
              <div class="rounded-xl bg-white p-3 text-xs leading-6 text-slate-600">
                <div class="font-medium text-slate-700">
                  证据
                </div>
                <div class="mt-1 whitespace-pre-wrap">
                  {{ singleResult.result.evidence || '未返回证据' }}
                </div>
              </div>
              <div class="rounded-xl bg-white p-3 text-xs leading-6 text-slate-600">
                <div class="font-medium text-slate-700">
                  建议
                </div>
                <div class="mt-1 whitespace-pre-wrap">
                  {{ singleResult.result.suggestion || '未返回整改建议' }}
                </div>
              </div>
            </div>
            <div
              v-if="batchResult"
              class="space-y-3 rounded-2xl border border-slate-200 bg-slate-50 p-4"
            >
              <div class="grid grid-cols-2 gap-3">
                <div class="rounded-xl bg-white p-3">
                  <div class="text-xs text-slate-400">
                    成功试跑
                  </div>
                  <div class="mt-2 text-xl font-semibold text-slate-900">
                    {{ batchResult.summary.success_count }}
                  </div>
                </div>
                <div class="rounded-xl bg-white p-3">
                  <div class="text-xs text-slate-400">
                    发现问题
                  </div>
                  <div class="mt-2 text-xl font-semibold text-rose-600">
                    {{ batchResult.summary.issue_records }}
                  </div>
                </div>
                <div class="rounded-xl bg-white p-3">
                  <div class="text-xs text-slate-400">
                    失败条目
                  </div>
                  <div class="mt-2 text-xl font-semibold text-amber-600">
                    {{ batchResult.summary.failed_count }}
                  </div>
                </div>
                <div class="rounded-xl bg-white p-3">
                  <div class="text-xs text-slate-400">
                    总耗时
                  </div>
                  <div class="mt-2 text-xl font-semibold text-slate-900">
                    {{ batchResult.summary.total_processing_time.toFixed(2) }}s
                  </div>
                </div>
              </div>
              <a-table
                row-key="record_id"
                size="small"
                :pagination="false"
                :columns="batchResultColumns"
                :data-source="batchResult.items"
                :scroll="{ y: 320 }"
              />
            </div>
            <div class="rounded-2xl border border-dashed border-slate-300 bg-white p-4">
              <div class="text-sm font-medium text-slate-900">
                规则发布
              </div>
              <div class="mt-2 text-xs leading-6 text-slate-500">
                发布后仅写入规则库，不写病历、首页、结算清单或正式质控结果；规则编码使用
                `LXE-####`。
              </div>
              <div class="mt-4 flex flex-wrap gap-2">
                <a-button
                  type="primary"
                  class="!rounded-lg"
                  :loading="publishing"
                  :disabled="!canPublish"
                  @click="handlePublish"
                >
                  复核通过并发布
                </a-button>
                <a-button
                  class="!rounded-lg"
                  :disabled="!publishedRuleId"
                  @click="jumpToRulesList"
                >
                  跳转规则列表
                </a-button>
              </div>
              <div
                v-if="publishedRuleCode"
                class="mt-3 text-xs text-emerald-700"
              >
                已发布规则：{{ publishedRuleCode }}
              </div>
            </div>
          </div>
        </a-card>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import type { Dayjs } from 'dayjs'
import { message } from 'ant-design-vue'
import type { TableColumnsType, TableProps } from 'ant-design-vue'
import { useRoute, useRouter } from 'vue-router'
import {
  getAdminRecordList,
  getDepartmentList,
  getRecordDetail,
  type AdminRecordItem,
} from '@/api/qcAdmin'
import { RulesService } from '@/services/rules-service'
import {
  generateCustomQcPrompt,
  saveCustomQcTestResult,
  testCustomQcBatch,
  testCustomQcSingle,
} from '@/services/custom-qc-experience-service'
import {
  STANDARD_DOCUMENT_TYPE_OPTIONS,
  defaultDocumentTypeByScene,
  normalizeWorkspaceDocumentType,
} from '@/constants/standard-document-types'
import type {
  CustomQcBatchTestResult,
  CustomQcCandidateRecord,
  CustomQcDraftRule,
  CustomQcPromptGenerationResult,
  CustomQcPublishPayload,
  CustomQcRecordPayload,
  CustomQcSingleTestResult,
} from '@/types/custom-qc'

type DateRange = [Dayjs, Dayjs] | null
type Scene = 'running' | 'final'

const route = useRoute()
const router = useRouter()
const scene = computed<Scene>(() => (route.query.scene === 'final' ? 'final' : 'running'))
const sceneLabel = computed(() => (scene.value === 'final' ? '终末病历' : '运行病历'))
const recordsLoading = ref(false)
const generatingPrompt = ref(false)
const testing = ref(false)
const publishing = ref(false)
const records = ref<CustomQcCandidateRecord[]>([])
const selectedRecordKeys = ref<string[]>([])
const departmentOptions = ref<Array<{ label: string; value: string }>>([])
const singleResult = ref<CustomQcSingleTestResult | null>(null)
const batchResult = ref<CustomQcBatchTestResult | null>(null)
const publishedRuleId = ref('')
const publishedRuleCode = ref('')
const generationMode = ref<'llm' | 'fallback_template'>('fallback_template')
const promptSummary = ref('')
const generatedCheckPoints = ref<string[]>([])
const generatedExamples = ref<Array<{ title: string; content: string }>>([])

const draftRule = reactive<CustomQcDraftRule>({
  name: '',
  description: '',
  prompt_template: '',
  severity: 'major',
  document_type: defaultDocumentTypeByScene(scene.value),
  scene: scene.value,
  check_logic: {},
})

const advancedParams = reactive({ temperature: 0.2, top_p: 0.9, max_tokens: 4096 })
const filters = reactive<{ department?: string; keyword: string; dateRange: DateRange }>({
  department: typeof route.query.department === 'string' ? route.query.department : undefined,
  keyword: '',
  dateRange: null,
})

const pagination = reactive({
  current: 1,
  pageSize: 10,
  total: 0,
  showSizeChanger: true,
  showQuickJumper: true,
  showTotal: (total: number) => `共 ${total} 条病历`,
})

const documentTypeOptions = STANDARD_DOCUMENT_TYPE_OPTIONS

const severityOptions = [
  { label: '严重', value: 'critical' },
  { label: '一般', value: 'major' },
  { label: '提示', value: 'minor' },
]

const recordColumns: TableColumnsType<CustomQcCandidateRecord> = [
  { title: '病历号', dataIndex: 'record_id', key: 'record_id', width: 150 },
  { title: '患者', dataIndex: 'patient_name', key: 'patient_name', width: 120 },
  { title: '科室', dataIndex: 'department', key: 'department', width: 140 },
  { title: '出院日期', dataIndex: 'discharge_date', key: 'discharge_date', width: 140 },
  { title: '状态', dataIndex: 'status', key: 'status', width: 120 },
  { title: '缺陷数', dataIndex: 'defect_count', key: 'defect_count', width: 100 },
  { title: '操作', key: 'action', width: 110, fixed: 'right' as const },
]

const batchResultColumns: TableColumnsType<CustomQcBatchTestResult['items'][number]> = [
  { title: '病历号', dataIndex: 'record_id', key: 'record_id', width: 140 },
  { title: '患者', dataIndex: 'patient_name', key: 'patient_name', width: 120 },
  { title: '状态', dataIndex: 'status', key: 'status', width: 120 },
  { title: '问题说明', dataIndex: 'findings', key: 'findings', ellipsis: true },
]

const rowSelection = computed<TableProps['rowSelection']>(() => ({
  selectedRowKeys: selectedRecordKeys.value,
  onChange: (keys: Array<string | number>) => {
    selectedRecordKeys.value = keys.map((key) => String(key))
  },
}))

const canGeneratePrompt = computed(
  () =>
    draftRule.name.trim().length >= 4 &&
    draftRule.description.trim().length >= 12 &&
    draftRule.document_type.trim().length > 0,
)
const canRunTest = computed(
  () =>
    selectedRecordKeys.value.length > 0 &&
    draftRule.name.trim() &&
    draftRule.description.trim() &&
    draftRule.prompt_template.trim(),
)
const canPublish = computed(() =>
  Boolean((singleResult.value || batchResult.value) && draftRule.prompt_template.trim()),
)
const prefillText = computed(() => {
  const parts: string[] = []
  if (typeof route.query.department === 'string' && route.query.department)
    parts.push(`预置科室：${route.query.department}`)
  if (typeof route.query.start_date === 'string' && typeof route.query.end_date === 'string')
    parts.push(`预置日期：${route.query.start_date} 至 ${route.query.end_date}`)
  const ids = parseRecordIds()
  if (ids.length) parts.push(`预置病历：${ids.length} 条`)
  return parts.join('；')
})

function parseRecordIds(): string[] {
  const raw = route.query.record_ids
  if (typeof raw !== 'string') return []
  return raw
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean)
}

function formatDateRangeValue(value?: Dayjs): string | undefined {
  return value?.format?.('YYYY-MM-DD')
}

async function loadDepartmentOptions() {
  const response = await getDepartmentList()
  if (response.success && response.data) {
    departmentOptions.value = response.data.map((item) => ({
      label: item.name,
      value: item.code || item.name,
    }))
  }
}

async function fetchRecords() {
  recordsLoading.value = true
  try {
    const response = await getAdminRecordList({
      scene: scene.value,
      department: filters.department,
      keyword: filters.keyword || undefined,
      start_date: formatDateRangeValue(filters.dateRange?.[0]),
      end_date: formatDateRangeValue(filters.dateRange?.[1]),
      page: pagination.current,
      page_size: pagination.pageSize,
    })
    if (!response.success || !response.data) throw new Error(response.message || '获取病历列表失败')

    records.value = (response.data.items || []).map((item: AdminRecordItem) => ({
      id: item.id,
      record_id: item.record_id,
      visit_id: item.visit_type,
      patient_name: item.patient_name,
      department: item.department,
      discharge_date: item.discharge_date,
      status: item.status,
      score: item.score,
      defect_count: item.defect_count,
    }))
    pagination.total = response.data.total || 0
    applyPrefillSelection()
  } catch (error: any) {
    message.error(error?.message || '获取病历列表失败')
  } finally {
    recordsLoading.value = false
  }
}

function applyPrefillSelection() {
  const presetIds = new Set(parseRecordIds())
  if (presetIds.size === 0) return
  const matched = records.value
    .filter((record) => presetIds.has(record.record_id))
    .map((record) => record.record_id)
  if (matched.length)
    selectedRecordKeys.value = Array.from(new Set([...selectedRecordKeys.value, ...matched]))
}

function handleSearchRecords() {
  pagination.current = 1
  fetchRecords()
}

function handleTableChange(pag: { current?: number; pageSize?: number }) {
  pagination.current = pag.current || 1
  pagination.pageSize = pag.pageSize || 10
  fetchRecords()
}

function selectCurrentPage() {
  selectedRecordKeys.value = Array.from(
    new Set([...selectedRecordKeys.value, ...records.value.map((record) => record.record_id)]),
  )
}

function applyExample() {
  draftRule.name =
    scene.value === 'final' ? '出院记录未写出院带药用法' : '日常病程记录未写当日处理意见'
  draftRule.document_type = defaultDocumentTypeByScene(scene.value)
  draftRule.severity = 'major'
  draftRule.description =
    scene.value === 'final'
      ? '检查出院记录中是否明确列出了带药药名及其用法用量。若仅写“继续原方案”或“带药出院”而没有具体药物及频次，应判定为问题。'
      : '检查运行病历的病程记录中是否写明针对当前病情的处理意见、检查计划和复评安排。若只描述病情而无处理计划，应提示问题。'
}

function applyGeneratedPrompt(data: CustomQcPromptGenerationResult) {
  draftRule.prompt_template = data.prompt_template
  generationMode.value = data.generation_mode
  promptSummary.value = data.summary
  generatedCheckPoints.value = data.check_points || []
  generatedExamples.value = data.examples || []
}

async function handleGeneratePrompt() {
  generatingPrompt.value = true
  try {
    const response = await generateCustomQcPrompt({
      scene: scene.value,
      document_type: draftRule.document_type,
      rule_name: draftRule.name.trim(),
      description: draftRule.description.trim(),
      severity: draftRule.severity,
    })
    if (!response.success || !response.data) throw new Error(response.message || '生成检查逻辑失败')
    applyGeneratedPrompt(response.data)
    message.success(
      response.data.generation_mode === 'llm' ? '检查逻辑生成成功' : '该能力待接入，已使用规则草稿',
    )
  } catch (error: any) {
    message.error(error?.message || '生成检查逻辑失败')
  } finally {
    generatingPrompt.value = false
  }
}

function buildCheckLogic() {
  const normalizedDocumentType = normalizeWorkspaceDocumentType(
    draftRule.document_type,
    defaultDocumentTypeByScene(scene.value),
  )
  return {
    source: 'workstation_experience',
    scene: scene.value,
    document_type: normalizedDocumentType,
    applicable_documents: [normalizedDocumentType],
    generation_mode: generationMode.value,
    generated_check_points: generatedCheckPoints.value,
    examples: generatedExamples.value,
    advanced_params: { ...advancedParams },
  }
}

function buildDraftRulePayload(): CustomQcDraftRule {
  const normalizedDocumentType = normalizeWorkspaceDocumentType(
    draftRule.document_type,
    defaultDocumentTypeByScene(scene.value),
  )
  return {
    name: draftRule.name.trim(),
    description: draftRule.description.trim(),
    prompt_template: draftRule.prompt_template.trim(),
    severity: draftRule.severity,
    document_type: normalizedDocumentType,
    scene: scene.value,
    check_logic: buildCheckLogic(),
  }
}

function composeMedicalText(detail: any): string {
  const documents = detail?.documents || {}
  const rawDocuments = Array.isArray(documents.raw_documents) ? documents.raw_documents : []
  const pieces: string[] = []
  const pushBlock = (title: string, content?: string) => {
    const normalized = String(content || '').trim()
    if (!normalized) return
    pieces.push(`【${title}】\n${normalized}`)
  }
  pushBlock('入院记录', documents.admissionNote || detail?.admissionNote)
  pushBlock('病程记录', documents.progressNote || detail?.progressNote)
  pushBlock('手术记录', documents.surgeryNote || detail?.surgeryNote)
  pushBlock('出院记录', documents.dischargeNote || detail?.dischargeNote)
  rawDocuments.forEach((doc: any) => {
    const title = String(doc?.title || doc?.document_type || '文书').trim()
    const content = String(doc?.content || '').trim()
    if (content) {
      const block = `【${title}】\n${content}`
      if (!pieces.includes(block)) pieces.push(block)
    }
  })
  if (pieces.length === 0 && detail?.record?.content)
    pushBlock('病历内容', String(detail.record.content))
  return pieces.join('\n\n')
}

async function fetchSelectedRecordPayloads(recordIds: string[]): Promise<CustomQcRecordPayload[]> {
  const payloads = await Promise.all(
    recordIds.map(async (recordId) => {
      const baseRecord = records.value.find((item) => item.record_id === recordId)
      const response = await getRecordDetail(recordId)
      if (!response.success || !response.data) throw new Error(`获取病历 ${recordId} 详情失败`)
      return {
        record_id: recordId,
        visit_id: baseRecord?.visit_id,
        patient_name: baseRecord?.patient_name,
        department: baseRecord?.department,
        medical_text: composeMedicalText(response.data),
      }
    }),
  )
  return payloads.filter((item) => item.medical_text.trim())
}

async function persistSingleResult(result: CustomQcSingleTestResult) {
  await saveCustomQcTestResult({
    mode: 'custom_experience_single',
    document_type: result.rule.document_type,
    rule_ids: [result.rule.name],
    medical_text_length: 0,
    stats: {
      total: 1,
      issues: result.result.is_compliant ? 0 : 1,
      compliance_rate: result.result.is_compliant ? 100 : 0,
    },
    performance: result.result.performance || {},
    results: [result.result],
    payload: result as unknown as Record<string, unknown>,
    document_id: result.record.record_id,
    metadata: buildCheckLogic(),
  })
}

async function persistBatchResult(result: CustomQcBatchTestResult) {
  await saveCustomQcTestResult({
    mode: 'custom_experience_batch',
    document_type: result.rule.document_type,
    rule_ids: [result.rule.name],
    medical_text_length: 0,
    stats: {
      total: result.summary.total_records,
      issues: result.summary.issue_records,
      compliance_rate:
        result.summary.success_count > 0
          ? (result.summary.compliant_records / result.summary.success_count) * 100
          : 0,
    },
    performance: {
      total_processing_time: result.summary.total_processing_time,
      total_tokens: result.summary.total_tokens,
    },
    results: result.items as unknown[],
    payload: result as unknown as Record<string, unknown>,
    metadata: buildCheckLogic(),
  })
}

async function runSelectedTest() {
  if (!canRunTest.value) return
  testing.value = true
  singleResult.value = null
  batchResult.value = null
  try {
    const recordsPayload = await fetchSelectedRecordPayloads([...selectedRecordKeys.value])
    if (!recordsPayload.length) throw new Error('未获取到可试跑的病历正文')
    const rulePayload = buildDraftRulePayload()

    if (recordsPayload.length === 1) {
      const response = await testCustomQcSingle({
        rule: rulePayload,
        records: recordsPayload,
        ...advancedParams,
      })
      if (!response.success || !response.data) throw new Error(response.message || '单病历试跑失败')
      singleResult.value = response.data
      await persistSingleResult(response.data)
      message.success('单病历试跑完成')
      return
    }

    const response = await testCustomQcBatch({
      rule: rulePayload,
      records: recordsPayload,
      ...advancedParams,
    })
    if (!response.success || !response.data) throw new Error(response.message || '批量试跑失败')
    batchResult.value = response.data
    await persistBatchResult(response.data)
    message.success('批量试跑完成')
  } catch (error: any) {
    message.error(error?.message || '试跑失败')
  } finally {
    testing.value = false
  }
}

async function runDirectSingle(record: any) {
  selectedRecordKeys.value = [record.record_id]
  await runSelectedTest()
}

async function generateNextLxeRuleCode() {
  const rules = await RulesService.getAllRules()
  const max = rules.reduce((currentMax, rule) => {
    const code = String(rule.rule_code || '')
      .trim()
      .toUpperCase()
    const match = code.match(/^LXE-(\d{1,})$/)
    return match ? Math.max(currentMax, Number(match[1])) : currentMax
  }, 0)
  return `LXE-${String(max + 1).padStart(4, '0')}`
}

async function handlePublish() {
  publishing.value = true
  try {
    const nextCode = await generateNextLxeRuleCode()
    const checkLogic = JSON.parse(
      JSON.stringify({
        ...buildCheckLogic(),
        test_summary: batchResult.value?.summary || singleResult.value?.result || null,
      }),
    ) as Record<string, unknown>
    const payload: CustomQcPublishPayload = {
      rule_code: nextCode,
      name: draftRule.name.trim(),
      description: draftRule.description.trim(),
      category: 'completeness',
      rule_type: 'subjective',
      severity: draftRule.severity,
      max_score: 10,
      weight: 1,
      is_active: true,
      prompt_template: draftRule.prompt_template.trim(),
      check_logic: checkLogic as any,
      version: '1.0',
    }
    const created = await RulesService.createRule(payload)
    publishedRuleId.value = created.id
    publishedRuleCode.value = created.rule_code || nextCode
    message.success(`规则 ${publishedRuleCode.value} 已发布到规则库`)
  } catch (error: any) {
    message.error(error?.message || '发布规则失败')
  } finally {
    publishing.value = false
  }
}

function jumpToRulesList() {
  router.push('/dashboard/rules')
}

function goBack() {
  router.push(
    scene.value === 'final' ? '/workstation-v4/records/final' : '/workstation-v4/records/running',
  )
}

watch(
  () => scene.value,
  () => {
    draftRule.scene = scene.value
    if (!draftRule.name && !draftRule.description && !draftRule.prompt_template) {
      draftRule.document_type = defaultDocumentTypeByScene(scene.value)
    }
    fetchRecords()
  },
)

onMounted(async () => {
  await loadDepartmentOptions()
  await fetchRecords()
})
</script>

<style scoped>
.custom-qc-page {
  min-height: 100%;
  padding: 24px;
  background: #f5f5f7;
  color: #1d1d1f;
  font-family:
    'Source Han Sans SC', 'San Francisco', 'SF Pro Text', 'SF Pro Display', Inter, 'PingFang SC',
    'Microsoft YaHei UI', 'Microsoft YaHei', system-ui, sans-serif;
  font-feature-settings:
    'rlig' 1,
    'calt' 1;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

.custom-qc-container {
  max-width: 1280px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.custom-qc-surface {
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.86);
  -webkit-backdrop-filter: blur(18px);
  backdrop-filter: blur(18px);
  box-shadow:
    0 1px 4px rgba(0, 0, 0, 0.045),
    0 2px 8px rgba(0, 0, 0, 0.035);
  overflow: hidden;
  transition:
    border-color 0.25s cubic-bezier(0.25, 0.1, 0.25, 1),
    box-shadow 0.25s cubic-bezier(0.25, 0.1, 0.25, 1),
    transform 0.25s cubic-bezier(0.25, 0.1, 0.25, 1);
}

.custom-qc-surface:hover {
  border-color: rgba(0, 0, 0, 0.14);
  box-shadow:
    0 2px 12px rgba(0, 0, 0, 0.1),
    0 6px 22px rgba(0, 0, 0, 0.075);
  transform: translateY(-2px);
}

.custom-qc-hero {
  background: rgba(255, 255, 255, 0.88);
}

.custom-qc-hero-inner {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 18px;
}

.custom-qc-chip-row,
.custom-qc-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.custom-qc-chip-row {
  margin-bottom: 12px;
}

.custom-qc-title {
  margin: 0;
  color: #1d1d1f;
  font-size: 28px;
  font-weight: 700;
  line-height: 31px;
  letter-spacing: 0;
}

.custom-qc-subtitle {
  max-width: 760px;
  margin: 9px 0 0;
  color: rgba(29, 29, 31, 0.6);
  font-size: 14px;
  font-weight: 500;
  line-height: 22px;
}

.custom-qc-primary-btn,
.custom-qc-secondary-btn {
  height: 36px;
  border-radius: 10px;
  font-size: 13px;
  font-weight: 600;
}

.custom-qc-primary-btn {
  background: #0066cc;
  border-color: #0066cc;
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.18),
    0 5px 14px rgba(0, 102, 204, 0.18);
}

.custom-qc-secondary-btn {
  background: rgba(255, 255, 255, 0.94);
  color: rgba(29, 29, 31, 0.68);
  border-color: rgba(29, 29, 31, 0.1);
}

:deep(.custom-qc-surface .ant-card-head) {
  min-height: 54px;
  border-bottom-color: rgba(0, 0, 0, 0.08);
  background: rgba(255, 255, 255, 0.74);
}

:deep(.custom-qc-surface .ant-card-head-title) {
  color: #1d1d1f;
  font-size: 17px;
  font-weight: 650;
  line-height: 22px;
}

:deep(.custom-qc-surface .ant-card-body) {
  padding: 20px;
}

:deep(.custom-qc-surface .ant-form-item-label > label) {
  color: rgba(29, 29, 31, 0.66);
  font-size: 13px;
  font-weight: 600;
}

:deep(.custom-qc-surface .ant-input),
:deep(.custom-qc-surface .ant-select),
:deep(.custom-qc-surface .ant-select-item),
:deep(.custom-qc-surface .ant-picker),
:deep(.custom-qc-surface .ant-input-number),
:deep(.custom-qc-surface .ant-btn),
:deep(.custom-qc-surface .ant-table),
:deep(.custom-qc-surface .ant-tag),
:deep(.custom-qc-surface .ant-alert) {
  font-family:
    'Source Han Sans SC', 'San Francisco', 'SF Pro Text', 'SF Pro Display', Inter, 'PingFang SC',
    'Microsoft YaHei UI', 'Microsoft YaHei', system-ui, sans-serif;
}

:deep(.custom-qc-surface .ant-input),
:deep(.custom-qc-surface .ant-select-selector),
:deep(.custom-qc-surface .ant-picker),
:deep(.custom-qc-surface .ant-input-number) {
  border-color: rgba(0, 0, 0, 0.1) !important;
  border-radius: 10px !important;
  background: rgba(255, 255, 255, 0.92) !important;
  box-shadow: none !important;
}

:deep(.custom-qc-surface .ant-input:hover),
:deep(.custom-qc-surface .ant-select-selector:hover),
:deep(.custom-qc-surface .ant-picker:hover),
:deep(.custom-qc-surface .ant-input-number:hover) {
  border-color: rgba(0, 102, 204, 0.28) !important;
}

:deep(.custom-qc-surface .ant-input:focus),
:deep(.custom-qc-surface .ant-input-focused),
:deep(.custom-qc-surface .ant-select-focused .ant-select-selector),
:deep(.custom-qc-surface .ant-picker-focused),
:deep(.custom-qc-surface .ant-input-number-focused) {
  border-color: rgba(0, 102, 204, 0.5) !important;
  box-shadow: 0 0 0 3px rgba(0, 102, 204, 0.08) !important;
}

:deep(.custom-qc-surface .ant-btn-primary) {
  background: #0066cc;
  border-color: #0066cc;
  border-radius: 10px;
  box-shadow: 0 5px 14px rgba(0, 102, 204, 0.16);
}

:deep(.custom-qc-surface .ant-alert) {
  border-radius: 14px;
}

:deep(.custom-qc-surface .ant-table) {
  color: rgba(29, 29, 31, 0.76);
}

:deep(.custom-qc-surface .ant-table-thead > tr > th) {
  background: rgba(255, 255, 255, 0.92);
  color: rgba(29, 29, 31, 0.42);
  font-size: 12px;
  font-weight: 600;
}

:deep(.custom-qc-surface .ant-table-tbody > tr > td) {
  border-bottom-color: rgba(0, 0, 0, 0.06);
}

:deep(.custom-qc-surface .ant-table-tbody > tr:hover > td) {
  background: rgba(0, 0, 0, 0.025) !important;
}

.custom-qc-page .rounded-2xl.border,
.custom-qc-page .rounded-xl.bg-white,
.custom-qc-page .border-dashed.bg-white {
  border-color: rgba(0, 0, 0, 0.08) !important;
  background: rgba(255, 255, 255, 0.72) !important;
}

.custom-qc-page .rounded-2xl.bg-slate-50,
.custom-qc-page .rounded-xl.bg-white,
.custom-qc-page .border-dashed.bg-white {
  -webkit-backdrop-filter: blur(18px);
  backdrop-filter: blur(18px);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.86),
    0 1px 3px rgba(0, 0, 0, 0.035);
}

.custom-qc-page .bg-slate-50 {
  background-color: rgba(255, 255, 255, 0.72) !important;
}

.custom-qc-page .bg-white {
  background-color: rgba(255, 255, 255, 0.76) !important;
}

.custom-qc-page .border-slate-200,
.custom-qc-page .border-slate-300,
.custom-qc-page .border-dashed {
  border-color: rgba(0, 0, 0, 0.08) !important;
}

.custom-qc-page .text-slate-900,
.custom-qc-page .text-slate-800 {
  color: #1d1d1f !important;
}

.custom-qc-page .text-slate-700,
.custom-qc-page .text-slate-600 {
  color: rgba(29, 29, 31, 0.68) !important;
}

.custom-qc-page .text-slate-500,
.custom-qc-page .text-slate-400 {
  color: rgba(29, 29, 31, 0.46) !important;
}

.custom-qc-page .font-mono {
  font-family: 'SF Pro Text', 'Cascadia Code', 'Roboto Mono', ui-monospace, monospace !important;
}

.custom-qc-page .rounded-2xl,
.custom-qc-page .rounded-xl {
  transition:
    border-color 250ms cubic-bezier(0.25, 0.1, 0.25, 1),
    box-shadow 250ms cubic-bezier(0.25, 0.1, 0.25, 1),
    transform 250ms cubic-bezier(0.25, 0.1, 0.25, 1);
}

.custom-qc-page .rounded-2xl:hover,
.custom-qc-page .rounded-xl:hover {
  border-color: rgba(0, 0, 0, 0.14) !important;
  box-shadow:
    0 2px 12px rgba(0, 0, 0, 0.1),
    0 6px 22px rgba(0, 0, 0, 0.075);
  transform: translateY(-2px);
}

.custom-qc-page :deep(.ant-tag) {
  border-color: rgba(0, 0, 0, 0.08);
  border-radius: 999px;
  background: rgba(0, 102, 204, 0.08);
  color: #0066cc;
  font-size: 12px;
  font-weight: 600;
}

.custom-qc-page :deep(.ant-tag-green),
.custom-qc-page :deep(.ant-tag-success) {
  border-color: rgba(16, 185, 129, 0.18);
  background: rgba(16, 185, 129, 0.1);
  color: #047857;
}

.custom-qc-page :deep(.ant-tag-orange),
.custom-qc-page :deep(.ant-tag-warning) {
  border-color: rgba(245, 158, 11, 0.22);
  background: rgba(245, 158, 11, 0.1);
  color: #b45309;
}

.custom-qc-page :deep(.ant-tag-red),
.custom-qc-page :deep(.ant-tag-error) {
  border-color: rgba(239, 68, 68, 0.2);
  background: rgba(239, 68, 68, 0.09);
  color: #be123c;
}

@media (max-width: 900px) {
  .custom-qc-page {
    padding: 16px;
  }

  .custom-qc-hero-inner {
    flex-direction: column;
  }
}
</style>
