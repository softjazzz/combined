<template>
  <aside
    class="pool-preview"
    aria-label="病历预览"
    data-testid="record-pool-preview"
  >
    <div
      v-if="!row"
      class="pool-preview__empty"
    >
      点击左侧任一病历，在这里预览住院信息与最新质控结果。
    </div>

    <template v-else>
      <header class="pool-preview__head">
        <img
          class="pool-preview__avatar"
          :src="patientAvatarSrc(row)"
          :alt="`${row.patientName || '患者'}头像`"
        >
        <div class="pool-preview__identity">
          <span class="pool-preview__eyebrow">病历预览</span>
          <strong class="pool-preview__name">{{ row.patientName || '患者信息待补' }}</strong>
          <span class="pool-preview__visit">住院号 {{ row.visitId || '—' }}</span>
        </div>
        <span
          class="mq-status"
          :class="hospitalizationTone"
        >{{ hospitalizationLabel }}</span>
      </header>

      <dl class="pool-preview__facts">
        <div>
          <dt>科室</dt>
          <dd>{{ row.department || '—' }}</dd>
        </div>
        <div>
          <dt>住院天数</dt>
          <dd>{{ stayDaysLabel }}</dd>
        </div>
        <div>
          <dt>入院日期</dt>
          <dd>{{ displayHospitalDate(row.admissionDate) }}{{ row.admissionPrecision === 'date' ? '（仅日期）' : '' }}</dd>
        </div>
        <div>
          <dt>出院日期</dt>
          <dd>{{ dischargeDateLabel(row) }}{{ row.dischargePrecision === 'date' ? '（仅日期）' : '' }}</dd>
        </div>
        <div v-if="row.sourceId === 'independent_cdm'">
          <dt>数据来源</dt>
          <dd>独立CDM · {{ row.materialCompleteness || '发布完整性未确认' }}</dd>
        </div>
      </dl>

      <section class="pool-preview__qc">
        <div class="pool-preview__qc-head">
          <span>最新质控结果</span>
          <span
            class="mq-status"
            :class="qcTone"
          >{{ qc.resultLabel }}</span>
        </div>
        <p class="pool-preview__qc-summary">
          {{ qc.issueSummary }}
        </p>
        <span class="pool-preview__qc-time">最近质控 {{ qc.latestQcTime }}</span>
      </section>

      <footer class="pool-preview__actions">
        <button
          type="button"
          class="mq-btn"
          data-testid="record-pool-preview-open"
          @click="emit('open-record', rowKey)"
        >
          查看病历
        </button>
        <button
          type="button"
          class="mq-btn mq-btn--primary"
          data-testid="record-pool-preview-qc"
          :disabled="qcLoading"
          @click="emit('run-qc', rowKey)"
        >
          质控此病历
        </button>
      </footer>
    </template>
  </aside>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { WorkbenchRow } from './BatchTablePanel.vue'
import { patientAvatarSrc } from '../qc/patient-avatar'
import { resolveResultPresentation } from '../qc/latestQcSummaryPresentation'
import type { QcSummaryLoadState } from '../../types'
import {
  dischargeDateLabel,
  displayHospitalDate,
  hospitalizationStatusLabel,
  resolvedHospitalizationStatus,
} from './hospitalizationPresentation'

const props = defineProps<{
  row: WorkbenchRow | null
  qcLoading?: boolean
  qcSummaryState?: QcSummaryLoadState
}>()

const emit = defineEmits<{
  'open-record': [recordKey: string]
  'run-qc': [recordKey: string]
}>()

const rowKey = computed(() => props.row?.recordKey || props.row?.id || '')
// 住院状态与列表共用同一口径
const status = computed(() => (props.row ? resolvedHospitalizationStatus(props.row) : 'unknown'))
const isDischarged = computed(() => status.value === 'discharged')
const hospitalizationLabel = computed(() =>
  props.row ? hospitalizationStatusLabel(props.row) : '待核验',
)
const hospitalizationTone = computed(() => {
  if (status.value === 'inpatient') return 'mq-status--info'
  if (status.value === 'unknown') return 'mq-status--warning'
  return ''
})

// 质控结果文案与运行/终末病历质控列表共用同一口径
const qc = computed(() => resolveResultPresentation(props.row?.latestQcSummary, props.qcSummaryState))

const qcTone = computed(() => {
  switch (qc.value.resultStatus) {
    case 'priority':
      return 'mq-status--danger'
    case 'data-gap':
    case 'uncertain':
    case 'technical-error':
      return 'mq-status--warning'
    case 'completed':
      return 'mq-status--success'
    default:
      return ''
  }
})

// 只有带年份的完整日期才计算住院天数，演示数据的“月-日”不推算
const FULL_DATE = /^(\d{4}-\d{2}-\d{2})/

function fullDate(value?: string): number {
  const match = String(value || '').trim().match(FULL_DATE)
  return match ? Date.parse(match[1]) : Number.NaN
}

const stayDaysLabel = computed(() => {
  const start = fullDate(props.row?.admissionDate)
  if (Number.isNaN(start)) return '—'
  const end = isDischarged.value ? fullDate(props.row?.dischargeDate) : Date.now()
  if (Number.isNaN(end) || end < start) return '—'
  const days = Math.max(1, Math.round((end - start) / 86_400_000))
  return isDischarged.value ? `${days} 天` : `已住 ${days} 天`
})
</script>

<style scoped>
.pool-preview {
  position: sticky;
  top: 16px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border: 1px solid var(--mq-glass-border);
  border-radius: var(--mq-radius-card);
  background: var(--mq-glass-bg);
  -webkit-backdrop-filter: var(--mq-glass-blur);
  backdrop-filter: var(--mq-glass-blur);
  box-shadow: var(--mq-glass-shadow);
  color: var(--mq-text-primary);
}

.pool-preview__empty {
  padding: 48px 24px;
  color: var(--mq-text-tertiary);
  font-size: var(--mq-font-13);
  text-align: center;
}

.pool-preview__head {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 20px 20px 16px;
  border-bottom: 0.5px solid var(--mq-border);
}

.pool-preview__avatar {
  width: 52px;
  height: 52px;
  flex-shrink: 0;
  border-radius: 50%;
  background: var(--mq-brand-50);
}

.pool-preview__identity {
  display: flex;
  flex: 1 1 auto;
  flex-direction: column;
  min-width: 0;
  line-height: 1.4;
}

.pool-preview__eyebrow {
  color: var(--mq-text-tertiary);
  font-size: var(--mq-font-12);
  font-weight: 600;
}

.pool-preview__name {
  overflow: hidden;
  font-family: var(--mq-font-display);
  font-size: 22px;
  font-weight: 700;
  letter-spacing: -0.02em;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.pool-preview__visit {
  overflow: hidden;
  color: var(--mq-text-tertiary);
  font-size: var(--mq-font-12);
  font-variant-numeric: tabular-nums;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.pool-preview__facts {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  margin: 0;
}

.pool-preview__facts > div {
  display: flex;
  flex-direction: column;
  gap: 3px;
  padding: 14px 20px;
  border-bottom: 0.5px solid var(--mq-border);
}

.pool-preview__facts > div:nth-child(odd) {
  border-right: 0.5px solid var(--mq-border);
}

.pool-preview__facts dt {
  color: var(--mq-text-tertiary);
  font-size: var(--mq-font-12);
}

.pool-preview__facts dd {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}

.pool-preview__qc {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin: 16px;
  padding: 14px 16px;
  border-radius: 16px;
  background: rgba(118, 128, 160, 0.07);
}

.pool-preview__qc-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  font-size: var(--mq-font-14);
  font-weight: 600;
}

.pool-preview__qc-summary {
  margin: 0;
  color: var(--mq-text-secondary);
  font-size: var(--mq-font-13);
}

.pool-preview__qc-time {
  color: var(--mq-text-tertiary);
  font-size: var(--mq-font-12);
}

.pool-preview__actions {
  display: flex;
  gap: 10px;
  padding: 16px;
  border-top: 0.5px solid var(--mq-border);
}

.pool-preview__actions .mq-btn {
  flex: 1 1 0;
  height: 42px;
}
</style>
