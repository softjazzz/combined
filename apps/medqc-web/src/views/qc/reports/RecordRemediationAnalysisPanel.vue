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
    <a-alert v-if="error" :message="error" type="error" show-icon />
    <a-button v-if="error" :disabled="busy" @click="load(1)"> 重试读取 </a-button>
    <a-spin :spinning="busy">
      <template v-if="analysis">
        <details class="remediation-contract">
          <summary>
            <MqIcon name="rules" :size="16" />七标签统计口径已确认<span
              >可重叠 · 申诉与整改独立</span
            >
          </summary>
          <ul class="assumptions">
            <li v-for="assumption in analysis.assumptions" :key="assumption">
              {{ assumption }}
            </li>
          </ul>
        </details>
        <div class="label-counts">
          <button
            type="button"
            class="mq-btn"
            :class="{ active: !label }"
            :aria-pressed="!label"
            @click="selectLabel()"
          >
            全部保存缺陷</button
          ><button
            v-for="item in analysis.labels"
            :key="item.key"
            type="button"
            class="mq-card remediation-metric"
            :class="{ active: label === item.key }"
            :aria-pressed="label === item.key"
            @click="selectLabel(item.key)"
          >
            <span>{{ item.label }}</span
            ><strong>{{ item.defect_total }}</strong
            ><small>{{ item.case_total }} 份病历</small>
          </button>
        </div>
        <div class="other-counts">
          <button
            v-for="(value, key) in analysis.state_counts"
            :key="key"
            class="mq-btn"
            type="button"
            :class="{ active: label === key }"
            :aria-pressed="label === key"
            @click="selectLabel(String(key))"
          >
            {{ stateName(String(key)) }}：{{ value }}
          </button>
        </div>
        <p class="remediation-total">
          当前筛选 {{ analysis.total }} 条保存缺陷；七标签只统计完整冻结来源，缺失来源单列。
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
              <tr v-for="row in analysis.items" :key="rowKey(row)">
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
                  ><small v-if="row.source_reason">{{ sourceReason(row.source_reason) }}</small
                  ><small>{{ row.labels.map(labelName).join('、') || '未纳入七标签' }}</small
                  ><small>受领医生：{{ row.assignee_name || '未知' }}</small>
                </td>
                <td>
                  <button type="button" class="mq-btn" @click="selected = row">
                    <MqIcon name="history" :size="16" />查看历史
                  </button>
                </td>
              </tr>
              <tr v-if="!analysis.items.length">
                <td colspan="4">暂无匹配的保存缺陷</td>
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
          <dt>冻结运行 / 结果</dt>
          <dd>{{ selected.root_job_id || '未知' }} / {{ selected.envelope_id || '未知' }}</dd>
          <dt>本次提交事件</dt>
          <dd>{{ selected.submission_event_id || '未知或尚未验收' }}</dd>
          <dt>提交时有效催办</dt>
          <dd>{{ selected.submission_urge_ids.join('、') || '无或尚未核实' }}</dd>
        </dl>
        <p v-if="selected.source_reason">
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
import { onBeforeUnmount, ref, watch } from 'vue'
import MqIcon from '@/components/icons/MqIcon.vue'
import CaseRectificationCreate from '@/components/qc/CaseRectificationCreate.vue'
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
const analysis = ref<RecordRemediationAnalysis>(),
  selected = ref<RemediationRow>()
const label = ref<string>(),
  busy = ref(false),
  exporting = ref(false),
  error = ref('')
let generation = 0
async function load(page = 1) {
  const token = ++generation
  exporting.value = false
  busy.value = true
  error.value = ''
  selected.value = undefined
  try {
    const response = await getRecordRemediationAnalysis({
      ...props.filters,
      label: label.value,
      page,
      page_size: 20,
    })
    if (token !== generation) return
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
    if (token === generation) {
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
  exporting.value = true
  try {
    const response = await exportRecordRemediationAnalysis({ ...props.filters, label: label.value })
    if (token !== generation) return
    if (!response.success || !response.data) throw new Error(response.message || '导出失败')
    downloadBlob(response.data, `整改分析_${props.filters.scene}.csv`)
  } catch (reason) {
    if (token === generation) error.value = reason instanceof Error ? reason.message : '导出失败'
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
    analysis.value = undefined
    selected.value = undefined
    label.value = undefined
    void load(1)
  },
  { immediate: true, deep: true },
)
onBeforeUnmount(() => {
  generation += 1
})
</script>
<style scoped src="@/views/qc/reports/styles/record-remediation-analysis.css"></style>
