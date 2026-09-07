<template>
  <aside class="qc-review-preview" aria-label="复核预览" data-testid="qc-review-preview">
    <header class="preview-heading">
      <ClipboardCheck :size="18" />
      <h2>复核预览</h2>
    </header>
    <div v-if="!row" class="preview-state">请选择左侧病历，查看最近一次质控结果</div>
    <template v-else>
      <section class="patient-context" aria-label="当前患者">
        <h3>{{ row.patientName || '患者信息待接入' }}</h3>
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
            <dt>入院时间</dt>
            <dd>{{ row.admissionTime || '—' }}</dd>
          </div>
          <div>
            <dt>最近质控</dt>
            <dd>{{ row.latestQcTime || '—' }}</dd>
          </div>
        </dl>
      </section>
      <div v-if="loading" class="preview-state" role="status">正在读取质控结果…</div>
      <div v-else-if="loadError" class="preview-state" role="alert">
        <p>{{ loadError }}</p>
        <button type="button" class="text-button" @click="loadResult">
          <RotateCcw :size="14" />重试
        </button>
      </div>
      <div v-else-if="!ready" class="preview-state">暂无已保存质控结果，请先运行质控</div>
      <template v-else>
        <nav class="status-tabs" aria-label="质控状态筛选">
          <button
            v-for="tab in tabs"
            :key="tab.key"
            type="button"
            :aria-pressed="activeTab === tab.key"
            :data-tab="tab.key"
            @click="activeTab = tab.key"
          >
            {{ tab.label }} <span>{{ tab.count }}</span>
          </button>
        </nav>
        <div class="preview-results" aria-live="polite">
          <p v-if="!filteredItems.length" class="preview-state">该状态暂无质控项</p>
          <article
            v-for="item in filteredItems.slice(0, 3)"
            :key="item.key"
            class="preview-item"
            data-testid="preview-item"
          >
            <div class="item-heading">
              <span class="status-label" :data-tone="item.tone">{{ item.displayStatus }}</span>
              <h3>{{ item.rule_name || item.rule_id }}</h3>
            </div>
            <p class="item-summary">
              {{ item.conclusionText || '暂无结论说明' }}
            </p>
            <p v-if="documentLabels(item)" class="document-label">
              <FileText :size="14" />{{ documentLabels(item) }}
            </p>
            <details>
              <summary>展开结果全文</summary>
              <p class="full-text">
                {{ item.conclusionText || '暂无结论说明' }}
              </p>
              <p v-if="item.detail" class="full-text">
                {{ item.detail }}
              </p>
              <p v-if="item.actual" class="full-text">实际情况：{{ item.actual }}</p>
              <p v-if="item.standard" class="full-text">质控标准：{{ item.standard }}</p>
              <p v-if="item.suggestion" class="full-text">建议：{{ item.suggestion }}</p>
            </details>
            <button type="button" class="text-button" @click="openFull">
              查看原文与结果<ArrowUpRight :size="14" />
            </button>
          </article>
        </div>
        <footer class="preview-footer">
          <span
            >共 {{ viewItems.length }} 项 · 当前分组 {{ filteredItems.length }} 项<span
              v-if="filteredItems.length > 3"
              >，预览前 3 项</span
            ></span
          >
          <button type="button" class="full-result-button" @click="openFull">
            打开完整质控结果<ArrowRight :size="16" />
          </button>
        </footer>
      </template>
    </template>
  </aside>
</template>

<script setup lang="ts">
import { ArrowRight, ArrowUpRight, ClipboardCheck, FileText, RotateCcw } from 'lucide-vue-next'
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { getLatestLuxian0609RecordResult } from '@/services/sichuan-rule-workspace-service'
import {
  buildSingleRecordQcResultItems,
  buildSingleRecordQcStatusTabs,
  resolveSingleRecordQcResultTab,
  type SingleRecordQcResultItem,
  type SingleRecordQcResultTabKey,
} from '../../customer-sample-validation/single-record-result-model'
import type { QcRecordResultRow } from './QcRecordResultTable.vue'

const props = withDefaults(defineProps<{ row: QcRecordResultRow | null; refreshKey?: number }>(), {
  refreshKey: 0,
})
const emit = defineEmits<{ 'open-full': [recordKey: string] }>()
const items = ref<SingleRecordQcResultItem[]>([])
const loading = ref(false)
const ready = ref(false)
const loadError = ref('')
const activeTab = ref<SingleRecordQcResultTabKey>('all')
let requestSequence = 0
const viewItems = computed(() => buildSingleRecordQcResultItems(items.value))
const tabs = computed(() => buildSingleRecordQcStatusTabs(viewItems.value))
const filteredItems = computed(() =>
  viewItems.value.filter(
    (item) => activeTab.value === 'all' || resolveSingleRecordQcResultTab(item) === activeTab.value,
  ),
)

function documentLabels(item: SingleRecordQcResultItem): string {
  return [
    ...new Set(
      [item.source_document, ...(item.evidence || []).map((entry) => entry.source_label)].filter(
        (label): label is string => Boolean(label?.trim()),
      ),
    ),
  ].join(' · ')
}

function openFull() {
  if (ready.value && props.row) emit('open-full', props.row.recordKey)
}

async function loadResult() {
  const sequence = ++requestSequence
  const row = props.row
  items.value = []
  ready.value = false
  loading.value = false
  loadError.value = ''
  activeTab.value = 'all'
  if (!row || row.resultStatus === 'not-run') return
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
  background: #fff;
  font-size: 14px;
  line-height: 1.6;
}
.preview-heading {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 18px 20px;
  border-bottom: 1px solid rgba(0, 0, 0, 0.08);
}
.preview-heading h2 {
  margin: 0;
  font-size: 17px;
  font-weight: 600;
}
.patient-context {
  padding: 18px 20px;
}
.patient-context h3 {
  margin: 0 0 12px;
  color: var(--ws-primary, #0066cc);
  font-size: 18px;
  font-weight: 600;
}
dl {
  margin: 0;
  display: grid;
  gap: 5px;
}
dl div {
  display: grid;
  grid-template-columns: 70px minmax(0, 1fr);
  gap: 8px;
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
  gap: 16px;
  overflow-x: auto;
  padding: 0 20px;
  border-bottom: 1px solid rgba(0, 0, 0, 0.08);
}
button {
  font: inherit;
  cursor: pointer;
}
.status-tabs button {
  flex: none;
  padding: 10px 0;
  border: 0;
  border-bottom: 2px solid transparent;
  background: transparent;
  color: rgba(29, 29, 31, 0.6);
}
.status-tabs button[aria-pressed='true'] {
  color: #0066cc;
  border-bottom-color: #0066cc;
}
.status-tabs span {
  font-size: 12px;
}
.preview-results {
  padding: 0 20px;
}
.preview-item {
  padding: 18px 0;
  border-bottom: 1px solid rgba(0, 0, 0, 0.08);
}
.item-heading {
  display: flex;
  gap: 8px;
  align-items: baseline;
}
.item-heading h3 {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  overflow-wrap: anywhere;
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
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
  overflow-wrap: anywhere;
  white-space: pre-line;
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
  color: #0066cc;
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
  color: #0066cc;
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
  justify-content: center;
  align-items: center;
  gap: 8px;
  min-height: 36px;
  border: 1px solid rgba(0, 102, 204, 0.2);
  border-radius: 8px;
  background: #fff;
  color: #0066cc;
}
button:focus-visible,
summary:focus-visible {
  outline: 2px solid #0066cc;
  outline-offset: 3px;
}
</style>
