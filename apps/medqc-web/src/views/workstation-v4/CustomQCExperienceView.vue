<template>
  <div class="min-h-screen bg-slate-50 p-6">
    <div class="mx-auto max-w-7xl space-y-6">
      <a-card
        :bordered="false"
        class="rounded-3xl shadow-sm"
      >
        <div class="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <div class="mb-3 flex flex-wrap gap-2">
              <a-tag color="processing">
                {{ sceneLabel }}
              </a-tag>
              <a-tag color="blue">
                Workstation V4 尝鲜版
              </a-tag>
            </div>
            <h1 class="text-3xl font-semibold text-slate-900">
              自定义质控点体验中心
            </h1>
            <p class="mt-3 max-w-3xl text-sm leading-7 text-slate-600">
              统一完成质控点定义、AI 生成
              Prompt、病历测试验证和发布上线。当前页面只做体验和验证，不接入正式自动质控流水线。
            </p>
          </div>
          <div class="flex flex-wrap gap-2">
            <a-button
              class="!rounded-xl"
              @click="goBack"
            >
              返回来源页
            </a-button>
            <a-button
              type="primary"
              class="!rounded-xl"
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
          class="rounded-3xl shadow-sm"
        >
          <template #title>
            1. 定义质控点
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
                class="!rounded-xl"
                :loading="generatingPrompt"
                :disabled="!canGeneratePrompt"
                @click="handleGeneratePrompt"
              >
                AI 生成 Prompt
              </a-button>
              <a-button
                size="large"
                class="!rounded-xl"
                @click="applyExample"
              >
                填充示例
              </a-button>
            </div>
          </a-form>
        </a-card>

        <a-card
          :bordered="false"
          class="rounded-3xl shadow-sm"
        >
          <template #title>
            2. Prompt 生成与编辑
          </template>
          <div class="space-y-4">
            <a-alert
              :type="generationMode === 'llm' ? 'success' : 'warning'"
              show-icon
              :message="
                generationMode === 'llm' ? '已使用真实 AI 生成 Prompt' : '当前为模板回退 Prompt'
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
              <a-form-item label="Prompt 模板">
                <a-textarea
                  v-model:value="draftRule.prompt_template"
                  :rows="16"
                  :maxlength="8000"
                  show-count
                />
              </a-form-item>
              <div class="grid gap-4 md:grid-cols-3">
                <a-form-item label="temperature">
                  <a-input-number
                    v-model:value="advancedParams.temperature"
                    :min="0"
                    :max="2"
                    :step="0.1"
                    class="!w-full"
                  />
                </a-form-item>
                <a-form-item label="top_p">
                  <a-input-number
                    v-model:value="advancedParams.top_p"
                    :min="0"
                    :max="1"
                    :step="0.05"
                    class="!w-full"
                  />
                </a-form-item>
                <a-form-item label="max_tokens">
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
          class="rounded-3xl shadow-sm"
        >
          <template #title>
            3. 病历选择与测试
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
                class="!rounded-xl"
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
                  class="!rounded-xl"
                  @click="selectCurrentPage"
                >
                  全选当前页
                </a-button>
                <a-button
                  class="!rounded-xl"
                  @click="selectedRecordKeys = []"
                >
                  清空选择
                </a-button>
                <a-button
                  type="primary"
                  class="!rounded-xl"
                  :loading="testing"
                  :disabled="!canRunTest"
                  @click="runSelectedTest"
                >
                  {{ selectedRecordKeys.length > 1 ? '批量测试' : '测试连接并运行' }}
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
                    单条测试
                  </a-button>
                </template>
              </template>
            </a-table>
          </div>
        </a-card>

        <a-card
          :bordered="false"
          class="rounded-3xl shadow-sm"
        >
          <template #title>
            4. 验证结果与发布
          </template>
          <div class="space-y-4">
            <a-empty
              v-if="!singleResult && !batchResult"
              description="完成一次测试后，这里会展示结果摘要和发布入口。"
            />
            <div
              v-if="singleResult"
              class="space-y-3 rounded-2xl border border-slate-200 bg-slate-50 p-4"
            >
              <div class="flex items-center justify-between gap-3">
                <div class="text-sm font-medium text-slate-900">
                  单病历测试结果
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
                    成功测试
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
                发布上线
              </div>
              <div class="mt-2 text-xs leading-6 text-slate-500">
                发布后会写入主站 `qc_rules`，规则类型固定为主观规则，编码使用 `LXE-####`。
              </div>
              <div class="mt-4 flex flex-wrap gap-2">
                <a-button
                  type="primary"
                  class="!rounded-xl"
                  :loading="publishing"
                  :disabled="!canPublish"
                  @click="handlePublish"
                >
                  发布到规则库
                </a-button>
                <a-button
                  class="!rounded-xl"
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
const sceneLabel = computed(() => (scene.value === 'final' ? '终末病历体验' : '运行病历体验'))
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
  draftRule.name = scene.value === 'final' ? '出院记录未写出院带药用法' : '日常病程记录未写当日处理意见'
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
    if (!response.success || !response.data) throw new Error(response.message || '生成 Prompt 失败')
    applyGeneratedPrompt(response.data)
    message.success(
      response.data.generation_mode === 'llm' ? 'Prompt 生成成功' : '已回退为模板 Prompt',
    )
  } catch (error: any) {
    message.error(error?.message || '生成 Prompt 失败')
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
    if (!recordsPayload.length) throw new Error('未获取到可测试的病历正文')
    const rulePayload = buildDraftRulePayload()

    if (recordsPayload.length === 1) {
      const response = await testCustomQcSingle({
        rule: rulePayload,
        records: recordsPayload,
        ...advancedParams,
      })
      if (!response.success || !response.data) throw new Error(response.message || '单病历测试失败')
      singleResult.value = response.data
      await persistSingleResult(response.data)
      message.success('单病历测试完成')
      return
    }

    const response = await testCustomQcBatch({
      rule: rulePayload,
      records: recordsPayload,
      ...advancedParams,
    })
    if (!response.success || !response.data) throw new Error(response.message || '批量测试失败')
    batchResult.value = response.data
    await persistBatchResult(response.data)
    message.success('批量测试完成')
  } catch (error: any) {
    message.error(error?.message || '测试失败')
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
