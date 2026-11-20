<template>
  <aside
    class="qc-review-preview"
    aria-label="复核预览"
    data-testid="qc-review-preview"
  >
    <header class="preview-heading">
      <ClipboardCheck :size="18" />
      <h2>复核预览</h2>
      <div
        v-if="row && ready && !loading && !loadError"
        class="preview-heading-actions"
      >
        <QcDiagnosticExport
          v-if="loadedResult"
          :items="loadedResult.items"
          :context="diagnosticContext"
        />
        <div class="preview-primary-action">
          <button
            type="button"
            class="full-result-button"
            @click="openFull"
          >
            <span class="full-result-label">
              <FileText
                :size="17"
                aria-hidden="true"
              />
              查看完整质控结果
            </span>
            <ArrowRight
              :size="16"
              aria-hidden="true"
            />
          </button>
        </div>
      </div>
    </header>
    <div
      v-if="!row"
      class="preview-state"
    >
      请选择左侧病历，查看最近一次质控结果
    </div>
    <template v-else>
      <section
        class="patient-context"
        aria-label="当前患者"
      >
        <h3>
          <img
            class="patient-avatar"
            :src="patientAvatarSrc(row)"
            alt=""
          >{{
            row.patientName || '患者信息待接入'
          }}
        </h3>
        <dl>
          <div>
            <dt>住院号</dt>
            <dd>{{ row.visitId || '—' }}</dd>
          </div>
          <div>
            <dt>科室</dt>
            <dd>{{ row.department || '—' }}</dd>
          </div>
          <div>
            <dt>{{ carePhase === 'discharged' ? '出院时间' : '入院时间' }}</dt>
            <dd>
              {{ (carePhase === 'discharged' ? row.dischargeTime : row.admissionTime) || '—' }}
            </dd>
          </div>
          <div>
            <dt>最近质控</dt>
            <dd>{{ row.latestQcTime || '—' }}</dd>
          </div>
        </dl>
      </section>
      <div
        v-if="loading"
        class="preview-state"
        role="status"
      >
        正在读取质控结果…
      </div>
      <div
        v-else-if="loadError"
        class="preview-state"
        role="alert"
      >
        <p>{{ loadError }}</p>
        <button
          type="button"
          class="text-button"
          @click="loadResult"
        >
          <RotateCcw :size="14" />重试
        </button>
      </div>
      <div
        v-else-if="!ready"
        class="preview-state"
      >
        {{ row.resultStatus === 'unknown' ? row.resultLabel : '暂无已保存质控结果，请先运行质控' }}
      </div>
      <template v-else>
        <div class="status-tabs">
          <span>问题预览</span>
          <div class="status-select">
            <Select
              v-model:value="activeTab"
              aria-label="质控状态筛选"
              class="preview-status-select"
              popup-class-name="preview-status-popup"
              :options="
                tabs.map((tab) => ({ value: tab.key, label: `${tab.label} · ${tab.count}` }))
              "
            />
          </div>
        </div>
        <div
          class="preview-results"
          aria-live="polite"
        >
          <p
            v-if="!filteredItems.length"
            class="preview-state"
          >
            该状态暂无质控项
          </p>
          <article
            v-for="item in filteredItems.slice(0, 3)"
            :key="item.key"
            class="preview-item"
            data-testid="preview-item"
          >
            <div class="item-heading">
              <div class="item-meta">
                <span
                  v-if="item.source_document"
                  class="item-source"
                >{{
                  item.source_document
                }}</span>
                <span
                  class="status-label"
                  :data-tone="item.tone"
                >{{ item.displayStatus }}</span>
              </div>
              <h3 :title="item.rule_name || item.rule_id">
                {{ displayRuleTitle(item) }}
              </h3>
            </div>
            <p class="section-label">
              判定说明
            </p>
            <p
              class="item-summary"
              :class="{ 'is-expanded': expandedItems.includes(item.key) }"
            >
              {{ item.conclusionText || '暂无结论说明' }}
            </p>
            <p
              v-if="documentLabels(item) && documentLabels(item) !== item.source_document"
              class="document-label"
            >
              <FileText :size="14" />{{ documentLabels(item) }}
            </p>
            <button
              type="button"
              class="expand-button"
              :aria-expanded="expandedItems.includes(item.key)"
              @click="toggleExplanation(item.key)"
            >
              {{ expandedItems.includes(item.key) ? '收起说明' : '查看完整说明' }}
            </button>
            <div
              v-if="expandedItems.includes(item.key)"
              class="explanation-extra"
            >
              <p
                v-if="item.detail && item.detail !== item.conclusionText"
                class="full-text"
              >
                {{ item.detail }}
              </p>
              <p
                v-if="item.actual"
                class="full-text"
              >
                实际情况：{{ item.actual }}
              </p>
              <p
                v-if="item.standard"
                class="full-text"
              >
                质控标准：{{ item.standard }}
              </p>
            </div>
            <QcRemediationSuggestion
              v-if="item.suggestion"
              :suggestion="item.suggestion"
              :status="item.status"
              :rule-id="item.rule_id"
              :record-context="diagnosticContext"
              dense
            />
            <div class="preview-item-actions">
              <button
                type="button"
                class="text-button"
                @click="openFull"
              >
                原文核对<ArrowUpRight :size="14" />
              </button>
            </div>
          </article>
        </div>
        <footer class="preview-footer">
          <span>共 {{ viewItems.length }} 项 · 当前分组 {{ filteredItems.length }} 项<span
            v-if="filteredItems.length > 3"
          >，预览前 3 项</span></span>
        </footer>
      </template>
    </template>
    <CaseCommunicationPanel
      v-if="row && ready && loadedResult?.job_id && !loading && !loadError"
      :institute-id="row.instituteId"
      :patient-id="row.patientId"
      :visit-id="row.visitId"
      :scene="carePhase === 'discharged' ? 'final' : 'running'"
      :job-id="loadedResult.job_id"
    />
  </aside>
</template>

<script setup lang="ts">
import { ArrowRight, ArrowUpRight, ClipboardCheck, FileText, RotateCcw } from 'lucide-vue-next'
import { Select } from 'ant-design-vue'
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import QcDiagnosticExport from '@/components/qc/QcDiagnosticExport.vue'
import CaseCommunicationPanel from '@/components/qc/CaseCommunicationPanel.vue'
import { getLatestLuxian0609RecordResult } from '@/services/sichuan-rule-workspace-service'
import {
  buildSingleRecordQcResultItems,
  buildSingleRecordQcStatusTabs,
  resolveSingleRecordQcResultTab,
  type SingleRecordQcResultPayload,
  type SingleRecordQcResultItem,
  type SingleRecordQcResultTabKey,
} from '../../customer-sample-validation/single-record-result-model'
import type { QcRecordCarePhase, QcRecordResultRow } from './QcRecordResultTable.vue'
import QcRemediationSuggestion from './QcRemediationSuggestion.vue'
import { patientAvatarSrc } from './patient-avatar'

const props = withDefaults(
  defineProps<{
    row: QcRecordResultRow | null
    refreshKey?: number
    carePhase?: QcRecordCarePhase
  }>(),
  {
    refreshKey: 0,
    carePhase: 'inpatient',
  },
)
const emit = defineEmits<{ 'open-full': [recordKey: string] }>()
const items = ref<SingleRecordQcResultItem[]>([])
const loadedResult = ref<SingleRecordQcResultPayload | null>(null)
const loading = ref(false)
const ready = ref(false)
const loadError = ref('')
const activeTab = ref<SingleRecordQcResultTabKey>('all')
const expandedItems = ref<string[]>([])
function toggleExplanation(key: string) {
  expandedItems.value = expandedItems.value.includes(key)
    ? expandedItems.value.filter((entry) => entry !== key)
    : [...expandedItems.value, key]
}
let requestSequence = 0
const viewItems = computed(() => buildSingleRecordQcResultItems(items.value))
const tabs = computed(() => buildSingleRecordQcStatusTabs(viewItems.value))
const filteredItems = computed(() =>
  viewItems.value.filter(
    (item) => activeTab.value === 'all' || resolveSingleRecordQcResultTab(item) === activeTab.value,
  ),
)
const diagnosticContext = computed(() => {
  const result = loadedResult.value
  const row = props.row
  if (!result || !row?.visitId) return undefined
  return {
    instituteId: row.instituteId,
    patientId: row.patientId,
    visitId: row.visitId,
    recordRef: result.record_ref,
    jobId: result.job_id,
    ruleSetKey: result.rule_set_key,
    ruleSetVersion: result.rule_set_version,
    resultSchemaVersion: result.schema_version,
    expectedRuleCount: result.expected_rule_count,
    resultRuleCount: result.result_rule_count,
    isComplete: result.is_complete,
    missingRuleIds: result.missing_rule_ids,
    conflictingRuleIds: result.conflicting_rule_ids,
    patientName: row.patientName,
  }
})


function documentLabels(item: SingleRecordQcResultItem): string {
  return [
    ...new Set(
      [item.source_document, ...(item.evidence || []).map((entry) => entry.source_label)].filter(
        (label): label is string => Boolean(label?.trim()),
      ),
    ),
  ].join(' · ')
}

function displayRuleTitle(item: SingleRecordQcResultItem): string {
  const title = (item.rule_name || item.rule_id).trim()
  const source = item.source_document?.trim()
  if (!source) return title
  for (const separator of ['：', ':']) {
    const prefix = `${source}${separator}`
    if (title.startsWith(prefix) && title.slice(prefix.length).trim()) {
      return title.slice(prefix.length).trim()
    }
  }
  return title
}

function openFull() {
  if (ready.value && props.row) emit('open-full', props.row.recordKey)
}

async function loadResult() {
  const sequence = ++requestSequence
  const row = props.row
  items.value = []
  loadedResult.value = null
  expandedItems.value = []
  ready.value = false
  loading.value = false
  loadError.value = ''
  activeTab.value = 'all'
  if (!row || row.resultStatus === 'not-run' || row.resultStatus === 'unknown') return
  if (!row.instituteId || !row.patientId || !row.visitId) {
    loadError.value = '当前病历身份信息不完整，已停止读取'
    return
  }
  loading.value = true
  try {
    const result = await getLatestLuxian0609RecordResult({
      instituteId: row.instituteId,
      patientId: row.patientId,
      visitId: row.visitId,
    })
    if (sequence !== requestSequence) return
    if (!result.success || !result.data) {
      loadError.value = result.message || '质控结果读取失败，请稍后重试'
      return
    }
    if (result.data.state === 'technical_error') {
      loadError.value = '质控结果读取异常，请联系管理员核对结果交付'
      return
    }
    if (result.data.state !== 'ready') return
    if (!String(result.data.record_ref || '').trim()) {
      loadError.value = '该质控任务缺少当前病历的服务端授权引用，已停止展示'
      return
    }
    items.value = result.data.items
    loadedResult.value = result.data
    ready.value = true
    activeTab.value =
      tabs.value.find((tab) => tab.key === 'non_compliant' && tab.count)?.key ||
      tabs.value.find((tab) => tab.key === 'pending' && tab.count)?.key ||
      'all'
  } catch {
    if (sequence === requestSequence) loadError.value = '质控结果读取失败，请稍后重试'
  } finally {
    if (sequence === requestSequence) loading.value = false
  }
}

watch(
  () => [
    props.row?.recordKey,
    props.row?.instituteId,
    props.row?.patientId,
    props.row?.visitId,
    props.row?.resultStatus,
    props.refreshKey,
  ],
  () => void loadResult(),
  { immediate: true },
)
onBeforeUnmount(() => {
  requestSequence += 1
})
</script>

<style scoped>
.qc-review-preview {
  min-width: 0;
  border-left: 1px solid #e5ebf3;
  color: var(--ws-text-primary, #1d1d1f);
  background: #f5f8fc;
  border-radius: 12px;
  padding-bottom: 4px;
  font-size: 14px;
  line-height: 1.6;
  font-family: 'Microsoft YaHei', 'PingFang SC', system-ui, sans-serif;
}
.preview-heading {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 18px 20px;
}
.preview-heading h2 {
  margin: 0;
  font-size: 17px;
  font-weight: 600;
}
.preview-heading-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  flex-wrap: wrap;
  gap: 8px;
  margin-left: auto;
}
.patient-context {
  margin: 0 16px 16px;
  padding: 16px;
  border: 1px solid #e1eaf4;
  border-radius: 10px;
  background: #fff;
  box-shadow: 0 2px 6px rgba(36, 65, 100, 0.025);
}
.patient-context h3 {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0 0 12px;
  color: #253247;
  font-size: 16px;
  font-weight: 600;
}
.patient-avatar {
  width: 28px;
  height: 28px;
  flex: 0 0 28px;
  border-radius: 50%;
  background: #eaf2ff;
  object-fit: cover;
}
dl {
  margin: 0;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 5px;
}
dl div {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 8px;
  font-size: 12px;
}
dt,
.preview-footer > span,
.document-label {
  color: rgba(29, 29, 31, 0.6);
}
dd {
  margin: 0;
  overflow-wrap: anywhere;
}
.status-tabs {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  padding: 0 18px 12px;
  background: transparent;
}
button {
  font: inherit;
  cursor: pointer;
}
.status-tabs select {
  appearance: none;
  width: 100%;
  min-height: 36px;
  padding: 6px 34px 6px 12px;
  border: 1px solid #b9cfe9;
  border-radius: 7px;
  background: #f5f9ff;
  color: #285b8f;
  cursor: pointer;
  font: inherit;
  font-size: 12px;
}
.status-select {
  position: relative;
  min-width: 148px;
  max-width: 100%;
}
.status-select-arrow {
  position: absolute;
  right: 13px;
  top: 13px;
  width: 7px;
  height: 7px;
  border-right: 2px solid #396f9f;
  border-bottom: 2px solid #396f9f;
  transform: rotate(45deg);
  pointer-events: none;
}
.status-tabs select:hover {
  border-color: #6a9dd2;
  background: #edf5ff;
}
.status-tabs select:focus-visible {
  outline: 2px solid #0a6cff;
  outline-offset: 2px;
}
.status-tabs > span {
  font-size: 14px;
  font-weight: 600;
  color: #38465a;
}
.preview-results {
  display: grid;
  gap: 12px;
  padding: 0 16px;
}
.preview-item {
  min-width: 0;
  padding: 18px;
  border: 1px solid #dce6f1;
  border-radius: 10px;
  background: #fff;
  box-shadow: 0 3px 10px rgba(36, 65, 100, 0.045);
}
.item-heading {
  display: grid;
  gap: 8px;
  align-items: baseline;
  padding-bottom: 12px;
  border-bottom: 1px solid #edf1f6;
}
.item-heading h3 {
  margin: 0;
  font-size: 16px;
  line-height: 1.55;
  color: #253247;
  font-weight: 600;
  overflow-wrap: anywhere;
}
.item-meta {
  display: flex;
  align-items: baseline;
  flex-wrap: wrap;
  gap: 4px;
  font-size: 12px;
  font-weight: 400;
}
.item-source {
  color: #7b8796;
}
.status-label {
  flex: none;
  font-size: 12px;
  color: #686870;
}
.status-label[data-tone='danger'] {
  color: #c43d3d;
}
.status-label[data-tone='warning'] {
  color: #9d6412;
}
.status-label[data-tone='success'] {
  color: #12805f;
}
.item-summary {
  margin: 8px 0;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  overflow-wrap: anywhere;
  white-space: pre-line;
  color: #465366;
  font-size: 13px;
  line-height: 1.8;
  font-weight: 400;
}
.item-summary.is-expanded {
  display: block;
  -webkit-line-clamp: unset;
}
.section-label {
  margin: 12px 0 0;
  font-size: 13px;
  font-weight: 600;
  color: #465366;
}
.expand-button {
  padding: 0;
  border: 0;
  background: transparent;
  color: #0a6cff;
  font-size: 12px;
}
.document-label {
  display: flex;
  align-items: baseline;
  gap: 5px;
  margin: 8px 0;
  font-size: 12px;
  overflow-wrap: anywhere;
}
.document-label svg {
  flex: none;
}
summary {
  cursor: pointer;
  font-size: 12px;
  color: #0a6cff;
}
.full-text {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
.text-button {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  margin-top: 10px;
  padding: 0;
  color: #0a6cff;
  border: 0;
  background: transparent;
  font-size: 13px;
}
.preview-state {
  padding: 28px 20px;
  color: rgba(29, 29, 31, 0.6);
}
.preview-state p {
  margin: 0;
}
.preview-footer {
  display: grid;
  gap: 12px;
  padding: 16px 20px 20px;
}
.preview-footer > span {
  font-size: 12px;
}
.full-result-button {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  min-height: 44px;
  padding: 0 14px;
  border: 1px solid transparent;
  border-radius: 8px;
  background: #eaf2fc;
  color: #245788;
  font-size: 14px;
  font-weight: 600;
  text-align: left;
  cursor: pointer;
  transition: background-color 160ms ease;
}
.full-result-button:hover {
  background: #dfeafb;
}
.full-result-label {
  display: inline-flex;
  align-items: center;
  gap: 9px;
}
.full-result-button > svg {
  flex-shrink: 0;
  color: #527da7;
}
button:focus-visible,
summary:focus-visible {
  outline: 2px solid #0a6cff;
  outline-offset: 3px;
}
</style>

<style scoped>
.preview-status-select {
  width: 156px;
}
.preview-status-select :deep(.ant-select-selector) {
  border-radius: 8px !important;
  border-color: #dce3ed !important;
  background: rgba(255, 255, 255, 0.85) !important;
  font-size: 13px;
  font-weight: 400;
}
:global(.preview-status-popup) {
  padding: 5px;
  border: 1px solid #e8edf3;
  border-radius: 10px;
  box-shadow: 0 8px 28px rgba(38, 58, 86, 0.14);
  font-family: 'Source Han Sans SC', 'Microsoft YaHei UI', sans-serif;
}
:global(.preview-status-popup .ant-select-item) {
  min-height: 34px;
  padding: 7px 10px;
  border-radius: 6px;
  font-size: 13px;
}
:global(.preview-status-popup .ant-select-item-option-selected) {
  color: #0a6cff;
  background: #eaf3ff;
  font-weight: 500;
}
</style>
