<template>
  <section class="validation-panel" aria-labelledby="fixed-test-title">
    <div class="panel-heading">
      <div>
        <h2 id="fixed-test-title">固定测试病例验证</h2>
        <span v-if="validationState?.validation">已验证 {{ validationState.validation.item_count }} 例</span>
      </div>
      <button type="button" class="secondary-button" :disabled="busy" @click="refresh">刷新</button>
    </div>

    <div v-if="!enabled" class="panel-state">请先保存基础信息和缺陷触发条件</div>
    <template v-else>
      <div class="validation-toolbar">
        <input v-model="draftQuery" maxlength="100" placeholder="搜索测试病例" aria-label="搜索测试病例" @keyup.enter="applySearch" />
        <button type="button" class="secondary-button" :disabled="busy" @click="applySearch">查询</button>
        <button type="button" class="text-button" :disabled="busy" @click="resetSearch">重置</button>
        <span>已选 {{ selectedItems.length }} / 20</span>
        <button
          type="button"
          class="primary-button"
          data-testid="run-fixed-validation"
          :disabled="busy || resultUnknown || selectedItems.length < 1"
          @click="runValidation"
        >{{ validating ? '正在测试' : '开始测试' }}</button>
      </div>

      <div v-if="notice" :class="['validation-notice', noticeType]" role="alert">{{ notice }}</div>
      <div v-if="recordsLoading" class="panel-state" role="status">正在读取固定测试病例</div>
      <div v-else-if="recordsError" class="panel-state is-error" role="alert">{{ recordsError }}</div>
      <div v-else-if="records.length === 0" class="panel-state">暂无可用的固定测试病例</div>
      <div v-else class="record-table-wrap">
        <table>
          <thead><tr><th>选择</th><th>病例</th><th>科室</th><th>三坐标</th><th>文书</th></tr></thead>
          <tbody>
            <tr v-for="record in records" :key="record.id">
              <td><input type="checkbox" :aria-label="`选择 ${record.case_title}`" :checked="isSelected(record.id)" :disabled="busy || (!isSelected(record.id) && selectedItems.length >= 20)" @change="toggleRecord(record, $event)" /></td>
              <td><strong>{{ record.case_title }}</strong><span>{{ record.patient_name || '未知患者' }}</span>
                <div class="record-actions">
                  <button type="button" class="text-button" :disabled="busy" @click="detailItem = record"><Eye :size="14" />详情 / 应用质控点</button>
                  <button type="button" class="text-button" :disabled="busy" @click="editItem = record"><Pencil :size="14" />编辑</button>
                  <button type="button" class="text-button" :disabled="busy" @click="copyRecord(record)"><Copy :size="14" />复制</button>
                </div>
              </td>
              <td>{{ record.department || '未知科室' }}</td>
              <td class="mono">{{ record.institute_id }} / {{ record.patient_id }} / {{ record.visit_id }}</td>
              <td>{{ record.document_count === null ? '未知' : `${record.document_count} 份` }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div v-if="selectedItems.length" class="selected-records">
        <h3>当前测试集</h3>
        <div v-for="item in selectedItems" :key="item.id" class="selected-record">
          <span>{{ item.case_title }}</span>
          <button type="button" class="text-button" :disabled="busy" :aria-label="`从当前测试集移除 ${item.case_title}`" @click="removeSelected(item.id)"><Minus :size="14" />移除</button>
        </div>
      </div>
      <div v-if="recordsTotal !== null && recordsTotal > PAGE_SIZE" class="pagination-row">
        <button type="button" :disabled="page <= 1 || busy" @click="changePage(page - 1)">上一页</button>
        <span>第 {{ page }} 页</span>
        <button type="button" :disabled="page * PAGE_SIZE >= recordsTotal || busy" @click="changePage(page + 1)">下一页</button>
      </div>

      <div v-if="proofLoading" class="panel-state" role="status">正在读取测试证明</div>
      <div v-else-if="validationState" class="proof-section">
        <div class="proof-heading">
          <div>
            <h3>测试结果</h3>
            <span>{{ proofText }}</span>
          </div>
          <button
            v-if="validationState.publish_ready && validationState.validation"
            type="button"
            class="primary-button"
            data-testid="publish-validated-draft"
            :disabled="busy || resultUnknown || selectionChanged"
            @click="publishDraft"
          >{{ publishing ? '正在发布' : '发布质控点' }}</button>
        </div>
        <div v-if="validationState.validation" class="result-table-wrap">
          <table>
            <thead><tr><th>病例</th><th>结果</th><th>判定依据</th><th>缺陷数</th></tr></thead>
            <tbody>
              <tr v-for="item in validationState.validation.results" :key="item.item_id">
                <td class="mono">{{ item.record_ref.institute_id }} / {{ item.record_ref.patient_id }} / {{ item.record_ref.visit_id }}</td>
                <td>{{ statusText(item.status) }}</td>
                <td><strong>{{ item.finding.description || '未提供摘要' }}</strong><span>{{ item.finding.evidence || '无补充证据' }}</span><small v-for="trace in item.condition_trace" :key="trace">{{ trace }}</small></td>
                <td>{{ item.issue_count }}</td>
              </tr>
              <tr v-for="item in validationState.validation.failures" :key="`failed-${item.item_id}`">
                <td class="mono">{{ item.item_id }}</td><td class="is-error">执行失败</td><td>{{ item.message }}</td><td>未知</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </template>
    <TestRecordEditDrawer v-if="editItem" :key="`${actorKey}:${draftId}:${editItem.id}`" :open="true" :item="editItem" @close="editItem = null" @saved="recordEdited" />
    <a-drawer :open="detailItem !== null" title="测试病例详情" width="min(1380px, 100vw)" @close="detailItem = null">
      <template v-if="detailItem">
        <h3>{{ detailItem.case_title }}</h3>
        <p>应用质控点：{{ detailItem.rule_ids.length ? detailItem.rule_ids.map(ruleLabel).join('、') : '未关联' }}</p>
        <QCRecordCompareWorkbench :key="detailItem.id" :visit-id="detailItem.visit_id" :institute-id="detailItem.institute_id" :patient-id="detailItem.patient_id" :issues="[]" document-only />
      </template>
    </a-drawer>
  </section>
</template>

<script setup lang="ts">
import { computed, defineAsyncComponent, onMounted, onUnmounted, ref, watch } from 'vue'
import { Copy, Eye, Minus, Pencil } from 'lucide-vue-next'
import { copyTestRecord, getCurrentRuleSetCatalog, listTestRecords } from '@/services/test-medical-records'
import TestRecordEditDrawer from '@/views/test-medical-records/components/TestRecordEditDrawer.vue'
import {
  getFixedTestValidation, publishValidatedWorkspaceDraft, runFixedTestValidation,
} from '@/services/custom-rule-workspace-service'
import type { TestRecordItem, TestRecordListResult } from '@/types/test-medical-records'
import type { FixedTestValidationState, FixedTestValidationStatus } from '@/types/custom-rule-workspace'

const PAGE_SIZE = 100
const QCRecordCompareWorkbench = defineAsyncComponent(() => import('@/views/workstation-v4/semantic-rules/components/QCRecordCompareWorkbench.vue'))
const props = defineProps<{
  draftId: string
  draftUpdatedAt: string
  actorKey: string
  enabled: boolean
}>()
const emit = defineEmits<{
  published: []
  'refresh-drafts': []
  'draft-updated': [updatedAt: string]
}>()

const records = ref<TestRecordItem[]>([])
const recordsTotal = ref<number | null>(null)
const page = ref(1)
const draftQuery = ref('')
const appliedQuery = ref('')
const selectedItems = ref<TestRecordItem[]>([])
const editItem = ref<TestRecordItem | null>(null)
const detailItem = ref<TestRecordItem | null>(null)
const copying = ref(false)
const selectionChanged = ref(false)
const ruleNames = ref<Record<string, string>>({})
const recordsLoading = ref(false)
const recordsError = ref('')
const proofLoading = ref(false)
const validationState = ref<FixedTestValidationState | null>(null)
const validating = ref(false)
const publishing = ref(false)
const resultUnknown = ref(false)
const unknownOperation = ref<'validation' | 'publish' | null>(null)
const unknownBaselineValidationId = ref('')
const notice = ref('')
const noticeType = ref<'success' | 'error' | 'warning'>('success')
let disposed = false
let contextRevision = 0
let listRevision = 0
let proofRevision = 0

const busy = computed(() => recordsLoading.value || proofLoading.value || validating.value || publishing.value || copying.value || editItem.value !== null)
const proofText = computed(() => {
  const state = validationState.value
  if (!state?.validation) return '尚未完成测试'
  if (selectionChanged.value) return '测试集已修改，请重新测试'
  if (state.publish_ready) return '测试证明有效，可以发布'
  const labels = {
    not_tested: '尚未完成测试', draft_changed: '草稿已修改，请重新测试',
    validation_incomplete: '存在数据不足或执行失败，暂不可发布', draft_not_executable: '当前草稿不可执行',
    test_records_changed: '测试病例已修改或移除，请重新测试',
  }
  return state.unavailable_reason ? labels[state.unavailable_reason] : '测试证明暂不可用于发布'
})

function contextCurrent(revision: number, actor: string, draft: string) {
  return !disposed && revision === contextRevision && actor === props.actorKey && draft === props.draftId
}
function validRecords(value: unknown): value is TestRecordListResult {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return false
  const data = value as Record<string, unknown>
  return Array.isArray(data.items) && Number.isInteger(data.total) && Number(data.total) >= 0
    && Number.isInteger(data.page) && Number(data.page) >= 1 && data.page_size === PAGE_SIZE
    && data.items.every((item) => Boolean(item) && typeof item === 'object'
      && typeof (item as TestRecordItem).id === 'string' && Boolean((item as TestRecordItem).id.trim())
      && typeof (item as TestRecordItem).institute_id === 'string' && Boolean((item as TestRecordItem).institute_id.trim())
      && typeof (item as TestRecordItem).patient_id === 'string' && Boolean((item as TestRecordItem).patient_id.trim())
      && typeof (item as TestRecordItem).visit_id === 'string' && Boolean((item as TestRecordItem).visit_id.trim())
      && typeof (item as TestRecordItem).updated_at === 'string'
      && !Number.isNaN(Date.parse((item as TestRecordItem).updated_at))
      && (item as TestRecordItem).state === 'active')
}
async function loadRecords(revision = contextRevision, actor = props.actorKey, draft = props.draftId) {
  const request = ++listRevision
  recordsLoading.value = true; recordsError.value = ''; records.value = []; recordsTotal.value = null
  const result = await listTestRecords({ include_removed: false, q: appliedQuery.value, page: page.value, page_size: PAGE_SIZE })
  if (!contextCurrent(revision, actor, draft) || request !== listRevision) return
  recordsLoading.value = false
  if (!result.success || !validRecords(result.data)) { recordsError.value = result.message || '固定测试病例回执格式异常'; return }
  records.value = result.data.items; recordsTotal.value = result.data.total; page.value = result.data.page
}
async function loadProof(revision = contextRevision, actor = props.actorKey, draft = props.draftId) {
  const request = ++proofRevision
  proofLoading.value = true
  const result = await getFixedTestValidation(draft)
  if (!contextCurrent(revision, actor, draft) || request !== proofRevision) return null
  proofLoading.value = false
  if (!result.success || !result.data) { noticeType.value = 'error'; notice.value = result.message || '读取测试证明失败'; return null }
  validationState.value = result.data
  if (result.data.draft_updated_at !== props.draftUpdatedAt) emit('draft-updated', result.data.draft_updated_at)
  reconcileUnknownResult(result.data)
  return result.data
}
async function initialize() {
  if (!props.enabled || !props.draftId || !props.actorKey) return
  const revision = contextRevision; const actor = props.actorKey; const draft = props.draftId
  await Promise.all([loadRecords(revision, actor, draft), loadProof(revision, actor, draft)])
}
function resetContext(clearUnknown: boolean) {
  if (!clearUnknown && (validating.value || publishing.value)) {
    resultUnknown.value = true
    unknownOperation.value = validating.value ? 'validation' : 'publish'
    unknownBaselineValidationId.value = validationState.value?.validation?.validation_id || ''
  }
  contextRevision += 1; listRevision += 1; proofRevision += 1
  recordsLoading.value = false; proofLoading.value = false; validating.value = false; publishing.value = false
  records.value = []; recordsTotal.value = null; selectedItems.value = []; validationState.value = null
  editItem.value = null; detailItem.value = null; copying.value = false; selectionChanged.value = false; ruleNames.value = {}
  recordsError.value = ''; notice.value = ''; page.value = 1
  if (clearUnknown) {
    resultUnknown.value = false
    unknownOperation.value = null
    unknownBaselineValidationId.value = ''
  } else if (resultUnknown.value) {
    noticeType.value = 'warning'
    notice.value = '操作结果仍无法确认，请继续核对，勿盲目重试'
  }
  draftQuery.value = ''; appliedQuery.value = ''
  void initialize()
}
function isSelected(id: string) { return selectedItems.value.some((item) => item.id === id) }
function toggleRecord(record: TestRecordItem, event: Event) {
  if (busy.value) return
  selectionChanged.value = true
  const checked = (event.target as HTMLInputElement).checked
  selectedItems.value = checked
    ? [...selectedItems.value, record].slice(0, 20)
    : selectedItems.value.filter((item) => item.id !== record.id)
}
function removeSelected(id: string) {
  if (busy.value) return
  selectedItems.value = selectedItems.value.filter((item) => item.id !== id)
  selectionChanged.value = true
}
function ruleLabel(id: string) { return ruleNames.value[id] ? `${id} ${ruleNames.value[id]}` : id }
async function recordEdited() {
  const revision = contextRevision; const actor = props.actorKey; const draft = props.draftId
  const oldId = editItem.value?.id
  editItem.value = null
  selectedItems.value = selectedItems.value.filter((item) => item.id !== oldId)
  selectionChanged.value = true
  validationState.value = null
  await initialize()
  if (!contextCurrent(revision, actor, draft)) return
  noticeType.value = 'warning'
  notice.value = '病例已更新，请添加新版病例并重新测试'
}
async function copyRecord(record: TestRecordItem) {
  if (busy.value) return
  const revision = contextRevision; const actor = props.actorKey; const draft = props.draftId
  copying.value = true
  const result = await copyTestRecord(record)
  if (!contextCurrent(revision, actor, draft)) return
  copying.value = false
  noticeType.value = result.success ? 'success' : 'error'
  notice.value = result.success ? '已创建复制病例，请在列表中选择后添加到测试集' : result.message || '复制结果无法确认，请刷新核对'
  if (result.success) { page.value = 1; appliedQuery.value = ''; draftQuery.value = ''; await loadRecords() }
}
function applySearch() { if (busy.value) return; appliedQuery.value = draftQuery.value.trim(); page.value = 1; void loadRecords() }
function resetSearch() { if (busy.value) return; draftQuery.value = ''; appliedQuery.value = ''; page.value = 1; void loadRecords() }
function changePage(next: number) { if (next < 1 || busy.value) return; page.value = next; void loadRecords() }
function refresh() { if (busy.value) return; notice.value = ''; void initialize() }
function statusText(status: FixedTestValidationStatus) {
  return {
    compliant: '符合', non_compliant: '发现缺陷', ai_suggested_compliant: '建议符合',
    ai_suggested_non_compliant: '建议存在缺陷', data_gap: '数据不足', not_applicable: '不适用',
    not_executed: '未执行', technical_error: '技术错误', uncertain: '待确认',
  }[status]
}
function reconcileUnknownResult(state: FixedTestValidationState) {
  if (!resultUnknown.value || !unknownOperation.value) return
  if (unknownOperation.value === 'validation'
    && state.validation?.validation_id
    && state.validation.validation_id !== unknownBaselineValidationId.value) {
    resultUnknown.value = false
    unknownOperation.value = null
    unknownBaselineValidationId.value = ''
    noticeType.value = 'success'
    notice.value = '已重新读取并确认测试证明'
  } else if (unknownOperation.value === 'publish'
    && state.draft_status === 'published' && state.published_rule_id) {
    resultUnknown.value = false
    unknownOperation.value = null
    unknownBaselineValidationId.value = ''
    noticeType.value = 'success'
    notice.value = '已重新读取并确认质控点发布成功'
    emit('published')
  } else {
    noticeType.value = 'warning'
    notice.value = '操作结果仍无法确认，请继续核对，勿盲目重试'
  }
}
async function runValidation() {
  if (busy.value || resultUnknown.value || selectedItems.value.length < 1 || selectedItems.value.length > 20) return
  const revision = contextRevision; const actor = props.actorKey; const draft = props.draftId
  const previousId = validationState.value?.validation?.validation_id || ''
  validating.value = true; notice.value = ''
  const result = await runFixedTestValidation(draft, {
    expected_updated_at: props.draftUpdatedAt,
    items: selectedItems.value.map((item) => ({ item_id: item.id, expected_updated_at: item.updated_at })),
  })
  if (!contextCurrent(revision, actor, draft)) return
  validating.value = false
  if (result.success === false) {
    noticeType.value = result.conflict ? 'warning' : 'error'; notice.value = result.message
    resultUnknown.value = result.resultUnknown
    if (result.resultUnknown) {
      unknownOperation.value = 'validation'
      unknownBaselineValidationId.value = previousId
      await loadProof(revision, actor, draft)
    } else if (result.conflict) {
      unknownOperation.value = null
      unknownBaselineValidationId.value = ''
    }
    return
  }
  validationState.value = result.data; resultUnknown.value = false
  selectionChanged.value = false
  unknownOperation.value = null; unknownBaselineValidationId.value = ''
  if (result.data.draft_updated_at !== props.draftUpdatedAt) emit('draft-updated', result.data.draft_updated_at)
  noticeType.value = result.data.publish_ready ? 'success' : 'warning'
  notice.value = result.data.publish_ready ? '固定测试已完成，可以发布' : '固定测试已完成，但仍有不可用结果'
}
async function publishDraft() {
  const proof = validationState.value?.validation
  if (busy.value || resultUnknown.value || selectionChanged.value || !validationState.value?.publish_ready || !proof) return
  const revision = contextRevision; const actor = props.actorKey; const draft = props.draftId
  publishing.value = true; notice.value = ''
  const result = await publishValidatedWorkspaceDraft(draft, {
    expected_updated_at: props.draftUpdatedAt, validation_id: proof.validation_id,
  })
  if (!contextCurrent(revision, actor, draft)) return
  publishing.value = false
  if (result.success === false) {
    resultUnknown.value = result.resultUnknown; noticeType.value = result.conflict ? 'warning' : 'error'; notice.value = result.message
    if (result.resultUnknown) {
      unknownOperation.value = 'publish'
      unknownBaselineValidationId.value = proof.validation_id
      await loadProof(revision, actor, draft)
      if (resultUnknown.value) emit('refresh-drafts')
    } else if (result.conflict) {
      unknownOperation.value = null
      unknownBaselineValidationId.value = ''
    }
    return
  }
  resultUnknown.value = false; unknownOperation.value = null; unknownBaselineValidationId.value = ''
  noticeType.value = 'success'; notice.value = `质控点 ${result.data.rule_code} 已发布`; emit('published')
}

watch(() => [props.draftId, props.actorKey], () => resetContext(true))
watch(() => [props.draftUpdatedAt, props.enabled], () => resetContext(false))
watch(detailItem, async (item) => {
  if (!item) return
  const revision = contextRevision; const actor = props.actorKey; const draft = props.draftId
  const result = await getCurrentRuleSetCatalog()
  if (!contextCurrent(revision, actor, draft) || detailItem.value?.id !== item.id) return
  ruleNames.value = Object.fromEntries((result.data?.entries || []).map((entry) => [entry.rule_id, entry.qc_point || '']))
})
onMounted(initialize)
onUnmounted(() => { disposed = true; contextRevision += 1; listRevision += 1; proofRevision += 1 })
</script>

<style scoped>
.validation-panel { padding: 22px; border: 1px solid rgba(0,0,0,.08); border-radius: 12px; background: #fff; }
.record-actions,.selected-record { display:flex; align-items:center; flex-wrap:wrap; gap:8px; }.record-actions .text-button,.selected-record .text-button { display:inline-flex; align-items:center; gap:4px; padding:0 4px; }.selected-records { margin-top:16px; }.selected-record { justify-content:space-between; border-bottom:1px solid rgba(0,0,0,.07); }
.panel-heading,.proof-heading,.validation-toolbar,.pagination-row { display:flex; align-items:center; justify-content:space-between; gap:12px; }
.panel-heading h2,.proof-heading h3 { margin:0; }.panel-heading span,.proof-heading span,.validation-toolbar span { color:rgba(29,29,31,.6); font-size:13px; }
.validation-toolbar { justify-content:flex-start; flex-wrap:wrap; margin:18px 0 12px; }.validation-toolbar input { min-width:240px; height:36px; padding:0 11px; border:1px solid rgba(0,0,0,.12); border-radius:8px; }
.record-table-wrap,.result-table-wrap { overflow-x:auto; max-width:100%; }.result-table-wrap { margin-top:12px; }
table { width:100%; min-width:760px; border-collapse:collapse; } th,td { padding:10px 12px; border-bottom:1px solid rgba(0,0,0,.07); text-align:left; vertical-align:top; overflow-wrap:anywhere; } th { color:rgba(29,29,31,.6); font-weight:400; } td strong,td span { display:block; }.mono { font-family:ui-monospace,Consolas,monospace; font-size:12px; }
.panel-state,.validation-notice { margin:14px 0; padding:12px; background:#f5f5f7; border-radius:8px; }.is-error,.validation-notice.error { color:#b42318; }.validation-notice.warning { color:#9a6700; }.validation-notice.success { color:#067647; }
.proof-section { margin-top:18px; padding-top:18px; border-top:1px solid rgba(0,0,0,.08); }.pagination-row { justify-content:flex-end; margin-top:12px; }
.primary-button,.secondary-button,.text-button,.pagination-row button { min-height:34px; border-radius:8px; padding:0 13px; cursor:pointer; }.primary-button { color:#fff; background:#007aff; border:1px solid #007aff; }.secondary-button,.pagination-row button { background:#fff; border:1px solid rgba(0,0,0,.12); }.text-button { color:#007aff; background:transparent; border:0; }.primary-button:disabled,.secondary-button:disabled,.text-button:disabled { opacity:.5; cursor:not-allowed; }
</style>
