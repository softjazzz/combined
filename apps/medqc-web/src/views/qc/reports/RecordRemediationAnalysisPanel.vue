<template>
  <section class="remediation-analysis" aria-label="整改分析">
    <header class="remediation-head">
      <h2 class="mq-card__title">整改分析</h2>
      <button
        type="button"
        class="mq-btn"
        :disabled="!analysis || busy || exporting"
        @click="download"
      >
        <MqIcon name="download" :size="16" />导出 CSV
      </button>
    </header>
    <p v-if="error" class="state-error" role="alert">
      <MqIcon name="issue" :size="16" />{{ error }}
    </p>
    <a-button v-if="error" :disabled="busy" @click="load(1)"> 重试读取 </a-button>
    <a-spin :spinning="busy">
      <template v-if="analysis">
        <div class="label-counts">
          <div class="remediation-toolbar">
            <button
              type="button"
              class="mq-btn"
              :class="{ active: !label }"
              :aria-pressed="!label"
              @click="selectLabel()"
            >
              全部保存缺陷
            </button>
            <details class="remediation-contract">
              <summary><MqIcon name="rules" :size="16" />统计口径</summary>
              <div class="remediation-contract-body">
                <p>七标签统计口径已确认，可重叠；申诉与整改独立。</p>
                <ul class="assumptions">
                  <li v-for="assumption in analysis.assumptions" :key="assumption">
                    {{ assumption }}
                  </li>
                </ul>
              </div>
            </details>
          </div>
          <div class="remediation-groups">
            <template v-for="group in metricGroups" :key="group.key">
              <section
                v-if="group.items.length"
                class="remediation-group"
                :class="`remediation-group--${group.key}`"
                :aria-label="group.label"
              >
                <header class="remediation-group-head">
                  <MqIcon :name="group.icon" :size="16" />
                  <h3>{{ group.label }}</h3>
                </header>
                <div class="remediation-group-metrics">
                  <button
                    v-for="item in group.items"
                    :key="item.key"
                    type="button"
                    class="remediation-metric"
                    :class="{
                      active: label === item.key,
                      'has-value': item.defect_total > 0,
                      'is-success': [
                        'self_rectified',
                        'urged_rectified',
                        'appeal_approved',
                      ].includes(item.key),
                      'is-warning': ['urged_pending', 'not_urged_pending'].includes(item.key),
                      'is-danger': item.key === 'appeal_rejected',
                    }"
                    :data-label="item.key"
                    :aria-pressed="label === item.key"
                    @click="selectLabel(item.key)"
                  >
                    <span class="remediation-metric-label">{{ item.label }}</span>
                    <span class="remediation-metric-value">
                      <strong>{{ item.defect_total }}</strong
                      ><span>条</span>
                    </span>
                    <small>{{ item.case_total }} 份病历</small>
                  </button>
                </div>
              </section>
            </template>
          </div>
        </div>
        <div class="remediation-state-bar">
          <span class="remediation-state-label">处理状态</span>
          <div class="other-counts mq-segmented" role="group" aria-label="其他处理状态">
            <button
              v-for="[key, value] in visibleStateCounts"
              :key="key"
              class="mq-segmented__item"
              type="button"
              :class="{ 'is-active': label === key, 'has-value': value > 0 }"
              :aria-pressed="label === key"
              @click="selectLabel(key)"
            >
              <span>{{ stateName(key) }}</span
              ><strong>{{ value }}</strong>
            </button>
          </div>
        </div>
        <p class="remediation-total">
          当前筛选 <strong>{{ analysis.total }}</strong> 条保存缺陷
        </p>
        <div class="table-scroll">
          <table class="mq-table">
            <thead>
              <tr>
                <th>病例 / 科室 / 医生</th>
                <th>保存缺陷</th>
                <th>整改 / 申诉</th>
                <th>来源与历史</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in visibleItems" :key="rowKey(row)">
                <td>
                  {{ row.patient_name || '姓名未知'
                  }}<small>{{ row.visit_id }} · {{ row.department }} · {{ row.doctor }}</small>
                </td>
                <td>
                  {{ row.target_label
                  }}<small
                    >{{ row.target_kind === 'canonical_defect' ? '自动缺陷' : '人工缺陷' }} ·
                    {{ row.target_id }}</small
                  >
                </td>
                <td>
                  <span class="mq-status" :class="statusClass(row.rectification_state)">{{
                    stateName(row.rectification_state)
                  }}</span
                  ><small v-if="!confirmedResultsOnly && row.source_reason">{{
                    sourceReason(row.source_reason)
                  }}</small
                  ><small>{{ row.labels.map(labelName).join('、') || '未纳入七标签' }}</small
                  ><small>受领医生：{{ row.assignee_name || '未知' }}</small>
                </td>
                <td>
                  <button type="button" class="mq-btn" @click="selected = row">
                    <MqIcon name="history" :size="16" />查看历史
                  </button>
                </td>
              </tr>
              <tr v-if="!visibleItems.length">
                <td colspan="4" class="empty-cell">暂无匹配的保存缺陷</td>
              </tr>
            </tbody>
          </table>
        </div>
        <a-pagination
          v-if="analysis.total > analysis.page_size"
          :current="analysis.page"
          :page-size="analysis.page_size"
          :total="analysis.total"
          :show-size-changer="false"
          :disabled="busy"
          @change="load"
        />
      </template>
    </a-spin>
    <a-drawer
      :open="!!selected"
      title="保存缺陷与整改历史"
      width="min(680px, 100vw)"
      :root-style="{ zIndex: 1100 }"
      root-class-name="remediation-history-drawer"
      @close="selected = undefined"
    >
      <template v-if="selected">
        <h3 class="mq-card__title">
          {{ selected.target_label }}
        </h3>
        <p class="mq-card__desc">
          {{ selected.patient_name || '姓名未知' }} · {{ selected.visit_id }} ·
          {{ selected.scene === 'running' ? '运行病历' : '终末病历' }}
        </p>
        <p>
          <span class="mq-status" :class="statusClass(selected.rectification_state)">{{
            stateName(selected.rectification_state)
          }}</span>
        </p>
        <CaseRectificationCreate
          v-if="selected.source_known && selected.root_job_id && selected.envelope_id"
          :institute-id="selected.institute_id"
          :patient-id="selected.patient_id"
          :visit-id="selected.visit_id"
          :job-id="selected.root_job_id"
          :initial-target="{
            source: selected.target_kind === 'canonical_defect' ? 'auto' : 'manual',
            ruleId: selected.target_kind === 'canonical_defect' ? selected.target_id : undefined,
            defectId:
              selected.target_kind === 'task_manual_defect' ? selected.target_id : undefined,
            rootJobId: selected.root_job_id,
            envelopeId: selected.envelope_id,
          }"
          @created="load(analysis?.page || 1)"
          @changed="load(analysis?.page || 1)"
        />
        <dl class="remediation-source mq-soft">
          <dt>三坐标</dt>
          <dd>{{ selected.institute_id }} / {{ selected.patient_id }} / {{ selected.visit_id }}</dd>
          <template v-if="!confirmedResultsOnly">
            <dt>冻结运行 / 结果</dt>
            <dd>{{ selected.root_job_id || '未知' }} / {{ selected.envelope_id || '未知' }}</dd>
            <dt>本次提交事件</dt>
            <dd>{{ selected.submission_event_id || '未知或尚未验收' }}</dd>
            <dt>提交时有效催办</dt>
            <dd>{{ selected.submission_urge_ids.join('、') || '无或尚未核实' }}</dd>
          </template>
        </dl>
        <p v-if="!confirmedResultsOnly && selected.source_reason">
          {{ sourceReason(selected.source_reason) }}
        </p>
        <h4>整改事件</h4>
        <p v-if="!selected.events.length">无已派发整改历史，不能据此认定未整改。</p>
        <ol class="remediation-events">
          <li v-for="event in selected.events" :key="event.id">
            <strong>{{ actionName(event.action) }} · 版本 {{ event.version }}</strong
            ><small>{{ event.created_at }}</small>
            <p>{{ event.comment }}</p>
            <small
              >事件 {{ event.id
              }}<template v-if="event.related_event_id">
                · 关联 {{ event.related_event_id }}</template
              ></small
            >
          </li>
        </ol>
        <h4>独立申诉</h4>
        <p v-if="!selected.appeals.length">无匹配本轮冻结目标的现代申诉</p>
        <ul>
          <li v-for="appeal in selected.appeals" :key="appeal.id">
            {{ appeal.id }} · {{ appealName(appeal.status) }}
          </li>
        </ul>
      </template>
    </a-drawer>
  </section>
</template>
<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import MqIcon from '@/components/icons/MqIcon.vue'
import CaseRectificationCreate from '@/components/qc/CaseRectificationCreate.vue'
import { useQcResultVisibility } from '@/composables/useQcResultVisibility'
import { useAuthStore } from '@/stores/auth'
import { exportRecordRemediationAnalysis, getRecordRemediationAnalysis } from '@/api/qualityReports'
import type {
  RecordQualityFilters,
  RecordRemediationAnalysis,
  RemediationRow,
} from '@/api/qualityReports'
import { downloadBlob } from '@/views/workstation-v4/customer-sample-validation/batchExport'
const props = defineProps<{ filters: RecordQualityFilters }>()
const auth = useAuthStore()
const { confirmedResultsOnly } = useQcResultVisibility()
const HIDDEN_DEMO_STATES = new Set(['source_unknown', 'history_unknown'])
const analysis = ref<RecordRemediationAnalysis>(),
  selected = ref<RemediationRow>()
const label = ref<string>(),
  busy = ref(false),
  exporting = ref(false),
  error = ref('')
const appealLabelKeys = new Set(['clinical_appeal', 'appeal_rejected', 'appeal_approved'])
const rectificationLabelOrder: Record<string, number> = {
  urged_pending: 0,
  not_urged_pending: 1,
  self_rectified: 2,
  urged_rectified: 3,
}
const metricGroups = computed(() => [
  {
    key: 'rectification',
    label: '整改跟踪',
    icon: 'task' as const,
    items: (analysis.value?.labels || [])
      .filter((item) => !appealLabelKeys.has(item.key))
      .sort(
        (left, right) =>
          (rectificationLabelOrder[left.key] ?? 4) - (rectificationLabelOrder[right.key] ?? 4),
      ),
  },
  {
    key: 'appeal',
    label: '申诉复核',
    icon: 'history' as const,
    items: (analysis.value?.labels || []).filter((item) => appealLabelKeys.has(item.key)),
  },
])
const visibleStateCounts = computed(() => {
  const entries = Object.entries(analysis.value?.state_counts || {})
  return confirmedResultsOnly.value
    ? entries.filter(([key]) => !HIDDEN_DEMO_STATES.has(key))
    : entries
})
const visibleItems = computed(() => {
  const items = analysis.value?.items || []
  return confirmedResultsOnly.value
    ? items.filter((row) => !HIDDEN_DEMO_STATES.has(row.rectification_state))
    : items
})
let generation = 0
let loadController: AbortController | null = null
let exportController: AbortController | null = null
function abortLoad() {
  loadController?.abort()
  loadController = null
}
function abortExport() {
  exportController?.abort()
  exportController = null
}
async function load(page = 1) {
  const token = ++generation
  abortLoad()
  abortExport()
  const controller = new AbortController()
  loadController = controller
  exporting.value = false
  busy.value = true
  error.value = ''
  selected.value = undefined
  try {
    const response = await getRecordRemediationAnalysis(
      {
        ...props.filters,
        label: label.value,
        page,
        page_size: 20,
      },
      controller.signal,
    )
    if (token !== generation || controller.signal.aborted) return
    if (!response.success || !response.data)
      throw new Error(response.message || '整改分析来源不可用')
    if (
      response.data.scope.scene !== props.filters.scene ||
      response.data.filter_label !== (label.value || null)
    )
      throw new Error('整改分析来源与筛选不一致')
    if (
      response.data.contract_status !== 'confirmed' ||
      !Array.isArray(response.data.items) ||
      !Array.isArray(response.data.labels) ||
      !Array.isArray(response.data.assumptions) ||
      !Number.isSafeInteger(response.data.total) ||
      response.data.total < 0 ||
      response.data.page !== page ||
      response.data.page_size !== 20 ||
      response.data.labels.some(
        (item) =>
          !Number.isSafeInteger(item.defect_total) ||
          item.defect_total < 0 ||
          !Number.isSafeInteger(item.case_total) ||
          item.case_total < 0,
      )
    )
      throw new Error('整改分析响应无法确认')
    analysis.value = response.data
  } catch (reason) {
    if (token === generation && !controller.signal.aborted) {
      analysis.value = undefined
      error.value = reason instanceof Error ? reason.message : '读取失败'
    }
  } finally {
    if (token === generation) busy.value = false
  }
}
function selectLabel(value?: string) {
  label.value = value
  void load(1)
}
async function download() {
  if (!analysis.value || busy.value || exporting.value) return
  const token = generation
  abortExport()
  const controller = new AbortController()
  exportController = controller
  exporting.value = true
  try {
    const response = await exportRecordRemediationAnalysis(
      { ...props.filters, label: label.value },
      controller.signal,
    )
    if (token !== generation || controller.signal.aborted) return
    if (!response.success || !response.data) throw new Error(response.message || '导出失败')
    downloadBlob(response.data, `整改分析_${props.filters.scene}.csv`)
  } catch (reason) {
    if (token === generation && !controller.signal.aborted) {
      error.value = reason instanceof Error ? reason.message : '导出失败'
    }
  } finally {
    if (token === generation) exporting.value = false
  }
}
const rowKey = (row: RemediationRow) =>
  [
    row.institute_id,
    row.patient_id,
    row.visit_id,
    row.scene,
    row.root_job_id,
    row.envelope_id,
    row.target_kind,
    row.target_id,
  ].join(':')
const states: Record<string, string> = {
  pending: '待整改',
  rejected: '整改驳回',
  approved: '验收通过',
  not_dispatched: '尚未派发',
  source_unknown: '冻结来源未知',
  history_unknown: '历史不足',
  pending_acceptance: '待质控验收',
}
const actions: Record<string, string> = {
  assign: '派发',
  urge: '催办',
  withdraw_urge: '撤回催办',
  submit: '医生提交',
  approve: '验收通过',
  reject: '验收驳回',
}
const appealStates: Record<string, string> = {
  pending: '待处理',
  reviewing: '复核中',
  approved: '申诉通过',
  rejected: '申诉驳回',
}
const stateName = (state: string) => states[state] || '未知'
const statusClasses: Record<string, string> = {
  approved: 'mq-status--success',
  rejected: 'mq-status--danger',
  pending: 'mq-status--warning',
  pending_acceptance: 'mq-status--info',
}
const statusClass = (state: string) => statusClasses[state] || ''
const actionName = (action: string) => actions[action] || '未知动作'
const appealName = (status: string) => appealStates[status] || '未知'
const sourceReason = (reason: string) =>
  reason === 'not_current_round'
    ? '非本轮冻结来源，未纳入当前整改标签'
    : '人工缺陷创建来源不足，无法精确绑定本轮结果'
const labelName = (key: string) =>
  analysis.value?.labels.find((item) => item.key === key)?.label || '未知标签'
watch(
  () => [props.filters, auth.user?.id],
  () => {
    generation += 1
    abortLoad()
    abortExport()
    analysis.value = undefined
    selected.value = undefined
    label.value = undefined
    void load(1)
  },
  { immediate: true, deep: true },
)
onBeforeUnmount(() => {
  generation += 1
  abortLoad()
  abortExport()
})
</script>
<style scoped src="@/views/qc/reports/styles/record-remediation-analysis.css"></style>
