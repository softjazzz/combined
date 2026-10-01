<template>
  <section
    ref="panelRoot"
    class="case-defect-partitions"
    aria-label="缺陷分区"
    data-testid="case-defect-partitions"
  >
    <header class="case-defect-partitions__heading">
      <h4>缺陷分区</h4>
      <button
        type="button"
        class="case-defect-partitions__refresh"
        :disabled="loading"
        @click="loadAll"
      >
        <RefreshCw :size="14" :class="{ 'is-spinning': loading }" />刷新
      </button>
    </header>

    <div class="case-defect-partitions__tabs" role="tablist" aria-label="缺陷类型">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        type="button"
        role="tab"
        :aria-selected="activeTab === tab.key"
        :class="{ 'is-active': activeTab === tab.key }"
        @click="activeTab = tab.key"
      >
        {{ tab.label }}<span>{{ tab.count }}</span>
      </button>
    </div>

    <p
      v-if="activeTab === 'veto' && partition?.veto.status === 'ready'"
      class="case-defect-partitions__source-note"
    >
      评分标准：{{ partition.veto.standard_name || '默认标准名称未返回' }}
    </p>

    <div
      v-if="activeMessage"
      class="case-defect-partitions__state"
      :class="{ 'is-error': activeError }"
    >
      <CircleAlert v-if="activeError" :size="16" />
      <Info v-else :size="16" />
      <span>{{ activeMessage }}</span>
    </div>

    <div
      v-else-if="activeTab === 'confirmed' || activeTab === 'veto'"
      class="case-defect-partitions__list"
    >
      <article
        v-for="item in activeCanonicalItems"
        :key="item.rule_id"
        class="case-defect-partitions__item"
        :class="{ 'is-target': isCanonicalTarget(item) }"
        :data-target="isCanonicalTarget(item) ? 'true' : undefined"
      >
        <div class="case-defect-partitions__item-title">
          <strong>{{ item.rule_name || item.rule_id }}</strong>
          <span>{{ item.rule_id }}</span>
        </div>
        <p>{{ item.conclusion || item.detail || '暂无结论说明' }}</p>
        <small v-if="item.source_document">{{ item.source_document }}</small>
      </article>
    </div>

    <div v-else-if="activeTab === 'manual'" class="case-defect-partitions__list">
      <article
        v-for="item in manualItems"
        :key="item.id"
        class="case-defect-partitions__item"
        :class="{ 'is-target': isManualTarget(item) }"
        :data-target="isManualTarget(item) ? 'true' : undefined"
      >
        <div class="case-defect-partitions__item-title">
          <strong>{{ item.rule_name || item.rule_code || '人工缺陷' }}</strong>
          <span>{{ manualStatusLabel(item.manual_review_status) }}</span>
        </div>
        <p>{{ item.description || '暂无问题说明' }}</p>
        <small v-if="item.location">{{ item.location }}</small>
      </article>
      <p v-if="manualTotal > manualItems.length" class="case-defect-partitions__footnote">
        预览最近 {{ manualItems.length }} 条，共 {{ manualTotal }} 条。
      </p>
    </div>

    <p v-if="targetNotice" class="case-defect-partitions__target-notice" role="status">
      {{ targetNotice }}
    </p>

    <div v-else-if="activeTab === 'coding'" class="case-defect-partitions__list">
      <article
        v-for="(item, index) in codingItems"
        :key="String(item.id || index)"
        class="case-defect-partitions__item"
      >
        <div class="case-defect-partitions__item-title">
          <strong>{{ item.rule_name || item.rule_code || '编码缺陷' }}</strong>
          <span v-if="item.severity">{{ item.severity }}</span>
        </div>
        <p>{{ item.description || '暂无问题说明' }}</p>
        <small v-if="item.location">{{ item.location }}</small>
      </article>
      <p v-if="codingHasMore" class="case-defect-partitions__footnote">
        预览本次前 {{ codingItems.length }} 条<span v-if="codingTotal !== null"
          >，共 {{ codingTotal }} 条</span
        >。
      </p>
    </div>
  </section>
</template>

<script setup lang="ts">
import { isAxiosError } from 'axios'
import { CircleAlert, Info, RefreshCw } from 'lucide-vue-next'
import { computed, nextTick, ref, watch } from 'vue'
import { getCaseManualDefects } from '@/api/manualDefectReviews'
import type { ManualDefectReviewItem } from '@/api/manualDefectReviews'
import { getModernCaseQcSnapshot } from '@/api/modernCaseQcResult'
import type { ModernCaseQcDefect, ModernCaseQcSnapshot } from '@/api/modernCaseQcResult'
import {
  getLatestLuxian0609RecordDefectPartitions,
  type CaseDefectPartitionsPayload,
} from '@/services/sichuan-rule-workspace-service'
import type { SingleRecordQcResultItem } from '@/views/workstation-v4/customer-sample-validation/single-record-result-model'

type PartitionKey = 'confirmed' | 'veto' | 'manual' | 'coding' | 'core'
export interface CaseDefectTarget {
  source: 'auto' | 'manual'
  ruleId?: string
  defectId?: string
}

const props = defineProps<{
  instituteId: string
  patientId: string
  visitId: string
  jobId: string
  scene: 'running' | 'final' | 'outpatient'
  canonicalItems: SingleRecordQcResultItem[]
  initialTab?: 'confirmed' | 'manual'
  initialTarget?: CaseDefectTarget | null
}>()
const emit = defineEmits<{ forbidden: [] }>()

const activeTab = ref<PartitionKey>(props.initialTab ?? 'confirmed')
const panelRoot = ref<HTMLElement | null>(null)
const partition = ref<CaseDefectPartitionsPayload | null>(null)
const partitionError = ref('')
const manualItems = ref<ManualDefectReviewItem[]>([])
const manualTotal = ref(0)
const manualReady = ref(false)
const manualError = ref('')
const codingSnapshot = ref<ModernCaseQcSnapshot | null>(null)
const codingReady = ref(false)
const codingError = ref('')
const loading = ref(false)
let requestSequence = 0

const manualStatusLabel = (status: ManualDefectReviewItem['manual_review_status']) =>
  ({ pending: '待审核', approved: '审核通过', rejected: '已驳回' })[status]

function normalizedRuleIds(values: string[] | undefined): string[] {
  return Array.isArray(values)
    ? [
        ...new Set(
          values
            .map((value) =>
              String(value || '')
                .trim()
                .toUpperCase(),
            )
            .filter(Boolean),
        ),
      ]
    : []
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function isRulePartition(
  value: unknown,
  source: 'luxian_0609_canonical_projection' | 'scoring_deductions',
) {
  if (!isRecord(value) || value.source !== source || !Array.isArray(value.rule_ids)) return false
  return value.rule_ids.every((ruleId) => typeof ruleId === 'string' && Boolean(ruleId.trim()))
}

function isPartitionPayload(value: unknown): value is CaseDefectPartitionsPayload {
  return (
    isRecord(value) &&
    value.schema_version === 'case-defect-partitions-v1' &&
    isRulePartition(value.confirmed, 'luxian_0609_canonical_projection') &&
    isRulePartition(value.veto, 'scoring_deductions') &&
    isRecord(value.core) &&
    value.core.source === 'core_system_classification' &&
    value.core.status === 'not_integrated'
  )
}

function canonicalItemsFor(values: string[] | undefined): SingleRecordQcResultItem[] {
  const wanted = new Set(normalizedRuleIds(values))
  return props.canonicalItems.filter((item) =>
    wanted.has(
      String(item.rule_id || '')
        .trim()
        .toUpperCase(),
    ),
  )
}

const confirmedRuleIds = computed(() => normalizedRuleIds(partition.value?.confirmed.rule_ids))
const vetoRuleIds = computed(() => normalizedRuleIds(partition.value?.veto.rule_ids))
const confirmedItems = computed(() => canonicalItemsFor(confirmedRuleIds.value))
const vetoItems = computed(() => canonicalItemsFor(vetoRuleIds.value))
const activeCanonicalItems = computed(() =>
  activeTab.value === 'veto' ? vetoItems.value : confirmedItems.value,
)
const normalizedTargetRuleId = computed(() =>
  String(props.initialTarget?.ruleId || '')
    .trim()
    .toUpperCase(),
)
const isCanonicalTarget = (item: SingleRecordQcResultItem) =>
  props.initialTarget?.source === 'auto' &&
  Boolean(normalizedTargetRuleId.value) &&
  String(item.rule_id || '')
    .trim()
    .toUpperCase() === normalizedTargetRuleId.value
const isManualTarget = (item: ManualDefectReviewItem) =>
  props.initialTarget?.source === 'manual' &&
  Boolean(props.initialTarget.defectId) &&
  item.id === props.initialTarget.defectId
const targetNotice = computed(() => {
  if (!props.initialTarget || loading.value) return ''
  if (props.initialTarget.source === 'auto') {
    if (!partition.value || partitionError.value) return ''
    return activeCanonicalItems.value.some(isCanonicalTarget)
      ? ''
      : `未在当前 Canonical 结果中找到规则 ${normalizedTargetRuleId.value || '未知'} 的缺陷`
  }
  if (!manualReady.value || manualError.value || manualItems.value.some(isManualTarget)) return ''
  return manualTotal.value > manualItems.value.length
    ? `目标人工缺陷 ${props.initialTarget.defectId || '未知'} 不在最近 200 条预览范围`
    : `未找到目标人工缺陷 ${props.initialTarget.defectId || '未知'}`
})

async function scrollToTarget() {
  await nextTick()
  panelRoot.value?.querySelector<HTMLElement>('[data-target="true"]')?.scrollIntoView?.({
    block: 'center',
  })
}
const codingItems = computed<ModernCaseQcDefect[]>(
  () => codingSnapshot.value?.current_result_defects || [],
)
const codingHasMore = computed(() => codingSnapshot.value?.current_result_defects_has_more === true)
const codingTotal = computed<number | null>(() => {
  const raw = codingSnapshot.value?.latest_qc_result?.defect_count
  return typeof raw === 'number' && Number.isInteger(raw) && raw >= 0 ? raw : null
})

function partitionCount(status: string | undefined, count: number): string {
  return status === 'ready' ? String(count) : '—'
}

const tabs = computed(() => [
  {
    key: 'confirmed' as const,
    label: '全部缺陷',
    count: partitionCount(partition.value?.confirmed.status, confirmedRuleIds.value.length),
  },
  {
    key: 'veto' as const,
    label: '单否',
    count: partitionCount(partition.value?.veto.status, vetoRuleIds.value.length),
  },
  {
    key: 'manual' as const,
    label: '人工',
    count: manualReady.value && !manualError.value ? String(manualTotal.value) : '—',
  },
  {
    key: 'coding' as const,
    label: '编码',
    count:
      codingError.value || !codingReady.value || !codingSnapshot.value?.latest_qc_result
        ? '—'
        : String(codingTotal.value ?? '—'),
  },
  { key: 'core' as const, label: '核心制度', count: '—' },
])

const canonicalReferenceMismatch = computed(() => {
  if (activeTab.value === 'confirmed')
    return confirmedItems.value.length !== confirmedRuleIds.value.length
  if (activeTab.value === 'veto') return vetoItems.value.length !== vetoRuleIds.value.length
  return false
})

const activeError = computed(() => {
  if (activeTab.value === 'manual') return Boolean(manualError.value)
  if (activeTab.value === 'coding') return Boolean(codingError.value)
  if (activeTab.value === 'core') return false
  return Boolean(partitionError.value || canonicalReferenceMismatch.value)
})

const activeMessage = computed(() => {
  if (activeTab.value === 'core') return '未接入（缺核心制度归类）'
  if (activeTab.value === 'manual') {
    if (manualError.value) return manualError.value
    if (!manualReady.value) return loading.value ? '正在读取人工缺陷…' : '人工缺陷暂时不可用'
    return manualItems.value.length ? '' : '当前病历暂无人工缺陷'
  }
  if (activeTab.value === 'coding') {
    if (codingError.value) return codingError.value
    if (!codingReady.value)
      return loading.value ? '正在读取编码质控结果…' : '编码质控结果暂时不可用'
    if (!codingSnapshot.value?.latest_qc_result) return '未做编码质控'
    return codingItems.value.length ? '' : '本次编码质控未发现缺陷'
  }
  if (partitionError.value) return partitionError.value
  if (canonicalReferenceMismatch.value) return '分区引用与当前质控结果不一致，已停止展示该分区'
  const current = activeTab.value === 'veto' ? partition.value?.veto : partition.value?.confirmed
  if (!current) return loading.value ? '正在读取缺陷分区…' : '缺陷分区暂时不可用'
  if (current.status === 'no_standard') return '未配置评分标准'
  if (current.status === 'no_scene') return '当前页面未提供计分场景，无法读取单否'
  if (current.status !== 'ready') return '该分区暂时不可用，请稍后重试'
  return activeCanonicalItems.value.length ? '' : '当前分区暂无缺陷'
})

function isCurrent(sequence: number) {
  return sequence === requestSequence
}

async function loadPartition(sequence: number) {
  const response = await getLatestLuxian0609RecordDefectPartitions({
    instituteId: props.instituteId,
    patientId: props.patientId,
    visitId: props.visitId,
    scene: props.scene,
  })
  if (!isCurrent(sequence)) return
  if (response.status === 403) emit('forbidden')
  const data: unknown = response.data
  if (!response.success || !isPartitionPayload(data)) {
    partitionError.value = response.message || '缺陷分区读取失败，请稍后重试'
    return
  }
  if (
    data.institute_id !== props.instituteId ||
    data.patient_id !== props.patientId ||
    data.visit_id !== props.visitId ||
    data.job_id !== props.jobId
  ) {
    partitionError.value = '缺陷分区与当前病例结果不一致，已停止展示'
    return
  }
  partition.value = data
}

async function loadManual(sequence: number) {
  const response = await getCaseManualDefects({
    institute_id: props.instituteId,
    patient_id: props.patientId,
    visit_id: props.visitId,
    scene: props.scene === 'outpatient' ? 'outpatient_emergency' : props.scene,
  })
  if (!isCurrent(sequence)) return
  if (response.status === 403) emit('forbidden')
  if (
    !response.success ||
    !response.data ||
    !Array.isArray(response.data.items) ||
    !Number.isInteger(response.data.total) ||
    response.data.total < 0
  ) {
    manualError.value = response.message || '人工缺陷读取失败，请稍后重试'
    return
  }
  if (
    response.data.items.some(
      (item) =>
        item.institute_id !== props.instituteId ||
        item.patient_id !== props.patientId ||
        item.visit_id !== props.visitId,
    )
  ) {
    manualError.value = '人工缺陷身份校验失败，已停止展示'
    return
  }
  manualItems.value = response.data.items
  manualTotal.value = response.data.total
  manualReady.value = true
}

async function loadCoding(sequence: number) {
  try {
    const snapshot = await getModernCaseQcSnapshot(
      {
        institute_id: props.instituteId,
        patient_id: props.patientId,
        visit_id: props.visitId,
        source_key: 'coding_qc',
      },
      { defects_limit: 50 },
    )
    if (isCurrent(sequence)) {
      codingSnapshot.value = snapshot
      codingReady.value = true
    }
  } catch (error) {
    if (!isCurrent(sequence)) return
    if (isAxiosError(error) && error.response?.status === 403) emit('forbidden')
    codingError.value = '编码质控结果暂时不可用，请稍后重试'
  }
}

async function loadAll() {
  const sequence = ++requestSequence
  partition.value = null
  partitionError.value = ''
  manualItems.value = []
  manualTotal.value = 0
  manualReady.value = false
  manualError.value = ''
  codingSnapshot.value = null
  codingReady.value = false
  codingError.value = ''
  loading.value = true
  await Promise.allSettled([loadPartition(sequence), loadManual(sequence), loadCoding(sequence)])
  if (isCurrent(sequence)) loading.value = false
  if (isCurrent(sequence)) await scrollToTarget()
}

watch(
  () => [props.instituteId, props.patientId, props.visitId, props.jobId, props.scene],
  () => void loadAll(),
  { immediate: true },
)

watch(
  () => [props.initialTab, props.initialTarget] as const,
  ([tab]) => {
    if (tab === 'confirmed' || tab === 'manual') activeTab.value = tab
    void scrollToTarget()
  },
)
</script>

<style scoped>
.case-defect-partitions {
  margin-top: 14px;
  padding: 16px;
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 12px;
  background: #fff;
  color: #1d1d1f;
  font-family: 'Source Han Sans SC', 'Microsoft YaHei UI', 'PingFang SC', sans-serif;
}
.case-defect-partitions__heading {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}
.case-defect-partitions__heading h4 {
  margin: 0;
}
.case-defect-partitions__heading h4 {
  font-size: 17px;
  line-height: 22px;
  font-weight: 600;
}
.case-defect-partitions__footnote {
  color: rgba(29, 29, 31, 0.6);
  font-size: 12px;
  line-height: 20px;
}
.case-defect-partitions__item.is-target {
  border-color: #1677ff;
  box-shadow: 0 0 0 2px rgba(22, 119, 255, 0.16);
}
.case-defect-partitions__target-notice {
  margin: 10px 0 0;
  color: #ad6800;
  font-size: 13px;
  line-height: 20px;
}
.case-defect-partitions__refresh {
  display: inline-flex;
  min-height: 32px;
  align-items: center;
  gap: 5px;
  padding: 0 10px;
  border: 1px solid rgba(0, 0, 0, 0.1);
  border-radius: 8px;
  background: #fff;
  color: rgba(29, 29, 31, 0.72);
  cursor: pointer;
}
.case-defect-partitions__refresh:disabled {
  cursor: wait;
  opacity: 0.55;
}
.case-defect-partitions__tabs {
  display: grid;
  grid-template-columns: repeat(5, minmax(92px, 1fr));
  gap: 4px;
  margin-top: 14px;
  padding: 4px;
  border-radius: 10px;
  background: #f2f3f5;
}
.case-defect-partitions__tabs button {
  display: flex;
  min-height: 36px;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 0 9px;
  border: 0;
  border-radius: 7px;
  background: transparent;
  color: rgba(29, 29, 31, 0.64);
  cursor: pointer;
  font: inherit;
  white-space: nowrap;
}
.case-defect-partitions__tabs button.is-active {
  background: #fff;
  color: #007aff;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
}
.case-defect-partitions__tabs span {
  min-width: 20px;
  color: inherit;
  font-size: 12px;
}
.case-defect-partitions__state {
  display: flex;
  min-height: 68px;
  align-items: center;
  gap: 8px;
  margin-top: 12px;
  padding: 12px;
  border-radius: 8px;
  background: #f7f8fa;
  color: rgba(29, 29, 31, 0.62);
}
.case-defect-partitions__state.is-error {
  background: #fff7f6;
  color: #b42318;
}
.case-defect-partitions__list {
  display: grid;
  gap: 0;
  margin-top: 12px;
  border-top: 1px solid rgba(0, 0, 0, 0.07);
}
.case-defect-partitions__source-note {
  margin: 10px 4px 0;
  color: rgba(29, 29, 31, 0.6);
  font-size: 12px;
  line-height: 20px;
}
.case-defect-partitions__item {
  min-width: 0;
  padding: 12px 4px;
  border-bottom: 1px solid rgba(0, 0, 0, 0.07);
}
.case-defect-partitions__item-title {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
}
.case-defect-partitions__item-title strong {
  font-size: 14px;
  line-height: 22px;
  font-weight: 600;
  overflow-wrap: anywhere;
}
.case-defect-partitions__item-title span,
.case-defect-partitions__item small {
  flex: none;
  color: rgba(29, 29, 31, 0.48);
  font-size: 12px;
}
.case-defect-partitions__item p {
  margin: 4px 0;
  color: rgba(29, 29, 31, 0.72);
  font-size: 13px;
  line-height: 21px;
  overflow-wrap: anywhere;
}
.case-defect-partitions__footnote {
  margin: 10px 4px 0;
}
.is-spinning {
  animation: defect-partition-spin 900ms linear infinite;
}
@keyframes defect-partition-spin {
  to {
    transform: rotate(360deg);
  }
}
@media (max-width: 760px) {
  .case-defect-partitions__tabs {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .case-defect-partitions__item-title {
    align-items: flex-start;
    flex-direction: column;
    gap: 2px;
  }
}
</style>
