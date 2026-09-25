<template>
  <section
    class="case-qc-panel"
    data-role="modern-case-qc-readonly"
  >
    <header class="case-qc-panel__header">
      <div class="case-qc-panel__heading">
        <h3 class="case-qc-panel__title">
          质控结果
        </h3>
      </div>
      <div class="case-qc-panel__badges">
        <span class="case-qc-panel__chip">{{ sourceLabel }}</span>
        <span class="case-qc-panel__chip case-qc-panel__chip--accent">只读</span>
      </div>
    </header>

    <div
      v-if="props.loading"
      class="case-qc-panel__state"
      data-role="loading"
      role="status"
    >
      <LoaderCircle class="case-qc-panel__state-icon case-qc-panel__state-icon--spin" />
      <p class="case-qc-panel__state-title">
        正在读取质控结果…
      </p>
    </div>

    <div
      v-else-if="errorMessage"
      class="case-qc-panel__state case-qc-panel__state--error"
      data-role="error"
      role="alert"
    >
      <TriangleAlert class="case-qc-panel__state-icon case-qc-panel__state-icon--danger" />
      <p class="case-qc-panel__state-title">
        质控结果暂不可用
      </p>
      <p class="case-qc-panel__state-desc">
        {{ errorMessage }}
      </p>
      <button
        type="button"
        class="case-qc-panel__retry"
        @click="emit('retry')"
      >
        <RotateCw class="case-qc-panel__retry-icon" />
        重试
      </button>
    </div>

    <div
      v-else-if="!hasSnapshot"
      class="case-qc-panel__state"
      data-role="empty"
    >
      <ClipboardX class="case-qc-panel__state-icon" />
      <p class="case-qc-panel__state-title">
        暂无已核验质控结果
      </p>
      <p class="case-qc-panel__state-desc">
        尚未返回该病例的质控快照。
      </p>
    </div>

    <div
      v-else-if="!hasVerifiedResult"
      class="case-qc-panel__state"
      data-role="empty"
    >
      <ClipboardX class="case-qc-panel__state-icon" />
      <p class="case-qc-panel__state-title">
        暂无已核验质控结果
      </p>
      <p class="case-qc-panel__state-desc">
        该来源下没有可核验的质控结果记录。
      </p>
    </div>

    <div
      v-else
      class="case-qc-panel__body"
    >
      <section
        class="case-qc-panel__section"
        data-section="latest-result"
      >
        <div class="case-qc-panel__section-head">
          <h4 class="case-qc-panel__section-title">
            最新质控结果
          </h4>
        </div>
        <dl class="case-qc-panel__facts">
          <div class="case-qc-panel__fact">
            <dt>结果编号</dt>
            <dd>{{ resultId }}</dd>
          </div>
          <div class="case-qc-panel__fact">
            <dt>规则集</dt>
            <dd>{{ valueOrDash(latestResult?.rule_set) }}</dd>
          </div>
          <div class="case-qc-panel__fact">
            <dt>综合得分</dt>
            <dd>{{ valueOrDash(latestResult?.overall_score) }}</dd>
          </div>
          <div class="case-qc-panel__fact">
            <dt>等级</dt>
            <dd>
              <span class="case-qc-panel__chip">{{ valueOrDash(latestResult?.grade) }}</span>
            </dd>
          </div>
          <div class="case-qc-panel__fact">
            <dt>缺陷数</dt>
            <dd>{{ valueOrDash(latestResult?.defect_count) }}</dd>
          </div>
          <div class="case-qc-panel__fact">
            <dt>分析日期</dt>
            <dd>{{ formatDate(latestResult?.analysis_date) }}</dd>
          </div>
          <div class="case-qc-panel__fact">
            <dt>生成时间</dt>
            <dd>{{ formatTime(latestResult?.created_at) }}</dd>
          </div>
        </dl>
      </section>

      <section
        class="case-qc-panel__section"
        data-section="active-defects"
      >
        <div class="case-qc-panel__section-head">
          <h4 class="case-qc-panel__section-title">
            当前活跃缺陷
          </h4>
          <span class="case-qc-panel__count">{{ activeDefects.length }} 项</span>
        </div>
        <p class="case-qc-panel__section-desc">
          该病例尚未关闭的缺陷，可能来自更早的质控结果。
        </p>
        <ul
          v-if="activeDefects.length > 0"
          class="case-qc-panel__defects"
        >
          <li
            v-for="(defect, index) in activeDefects"
            :key="defectKey('active', defect, index)"
            class="case-qc-panel__defect"
          >
            <div class="case-qc-panel__defect-head">
              <span class="case-qc-panel__defect-name">{{ defectTitle(defect, index) }}</span>
              <span
                v-if="text(defect.severity)"
                class="case-qc-panel__chip"
              >{{ text(defect.severity) }}</span>
              <span
                v-if="text(defect.status)"
                class="case-qc-panel__chip"
              >{{ text(defect.status) }}</span>
            </div>
            <p
              v-if="text(defect.rule_code)"
              class="case-qc-panel__defect-meta"
            >
              规则编号：{{ text(defect.rule_code) }}
            </p>
            <p
              v-if="text(defect.description)"
              class="case-qc-panel__defect-desc"
            >
              {{ text(defect.description) }}
            </p>
            <p
              v-if="text(defect.location)"
              class="case-qc-panel__defect-meta"
            >
              定位：{{ text(defect.location) }}
            </p>
            <p
              v-if="text(defect.suggestion)"
              class="case-qc-panel__defect-meta"
            >
              建议：{{ text(defect.suggestion) }}
            </p>
          </li>
        </ul>
        <p
          v-else
          class="case-qc-panel__empty"
        >
          暂无未关闭缺陷
        </p>
      </section>

      <section
        class="case-qc-panel__section"
        data-section="current-result-defects"
      >
        <div class="case-qc-panel__section-head">
          <h4 class="case-qc-panel__section-title">
            本次结果缺陷
          </h4>
          <span class="case-qc-panel__count">{{ currentResultDefects.length }} 项</span>
        </div>
        <p class="case-qc-panel__section-desc">
          仅归属最新质控结果的缺陷，可能包含已关闭项。
        </p>
        <ul
          v-if="currentResultDefects.length > 0"
          class="case-qc-panel__defects"
        >
          <li
            v-for="(defect, index) in currentResultDefects"
            :key="defectKey('current', defect, index)"
            class="case-qc-panel__defect"
          >
            <div class="case-qc-panel__defect-head">
              <span class="case-qc-panel__defect-name">{{ defectTitle(defect, index) }}</span>
              <span
                v-if="text(defect.severity)"
                class="case-qc-panel__chip"
              >{{ text(defect.severity) }}</span>
              <span
                v-if="text(defect.status)"
                class="case-qc-panel__chip"
              >{{ text(defect.status) }}</span>
            </div>
            <p
              v-if="text(defect.rule_code)"
              class="case-qc-panel__defect-meta"
            >
              规则编号：{{ text(defect.rule_code) }}
            </p>
            <p
              v-if="text(defect.description)"
              class="case-qc-panel__defect-desc"
            >
              {{ text(defect.description) }}
            </p>
            <p
              v-if="text(defect.location)"
              class="case-qc-panel__defect-meta"
            >
              定位：{{ text(defect.location) }}
            </p>
            <p
              v-if="text(defect.suggestion)"
              class="case-qc-panel__defect-meta"
            >
              建议：{{ text(defect.suggestion) }}
            </p>
          </li>
        </ul>
        <p
          v-else
          class="case-qc-panel__empty"
        >
          本次结果未记录缺陷
        </p>
      </section>

      <section
        class="case-qc-panel__section"
        data-section="recent-results"
      >
        <div class="case-qc-panel__section-head">
          <h4 class="case-qc-panel__section-title">
            最近执行历史
          </h4>
          <span class="case-qc-panel__count">{{ recentResults.length }} 项</span>
        </div>
        <ul
          v-if="recentResults.length > 0"
          class="case-qc-panel__history"
        >
          <li
            v-for="(record, index) in recentResults"
            :key="recordKey(record, index)"
            class="case-qc-panel__history-row"
          >
            <span class="case-qc-panel__history-id">{{ recordLabel(record, index) }}</span>
            <span class="case-qc-panel__history-meta">{{ valueOrDash(record.grade) }}</span>
            <span class="case-qc-panel__history-meta">{{ valueOrDash(record.overall_score) }}</span>
            <span class="case-qc-panel__history-time">{{ historyTime(record) }}</span>
          </li>
        </ul>
        <p
          v-else
          class="case-qc-panel__empty"
        >
          暂无更早的执行记录
        </p>
      </section>

      <section
        class="case-qc-panel__section"
        data-section="latest-notification"
      >
        <div class="case-qc-panel__section-head">
          <h4 class="case-qc-panel__section-title">
            当前用户通知
          </h4>
        </div>
        <template v-if="latestNotification">
          <div class="case-qc-panel__notice-head">
            <span class="case-qc-panel__notice-title">{{
              valueOrDash(latestNotification.title)
            }}</span>
            <span
              v-if="text(latestNotification.severity)"
              class="case-qc-panel__chip"
            >{{ text(latestNotification.severity) }}</span>
          </div>
          <p
            v-if="text(latestNotification.content)"
            class="case-qc-panel__notice-content"
          >
            {{ text(latestNotification.content) }}
          </p>
          <p class="case-qc-panel__notice-time">
            {{ formatTime(latestNotification.created_at) }}
          </p>
        </template>
        <p
          v-else
          class="case-qc-panel__empty"
        >
          暂无通知
        </p>
      </section>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { ClipboardX, LoaderCircle, RotateCw, TriangleAlert } from 'lucide-vue-next'

import type {
  ModernCaseQcDefect,
  ModernCaseQcNotification,
  ModernCaseQcResultRecord,
  ModernCaseQcSnapshot,
  ModernCaseQcSourceKey,
} from '@/api/modernCaseQcResult'

const props = defineProps<{
  snapshot: ModernCaseQcSnapshot | null
  loading: boolean
  error: string | null
  sourceKey: ModernCaseQcSourceKey
}>()

const emit = defineEmits<{
  (e: 'retry'): void
}>()

const SOURCE_LABELS: Record<ModernCaseQcSourceKey, string> = {
  frontpage_formal_qc: '首页质控',
  coding_qc: '编码质控',
  settlement_qc: '结算质控',
  settlement_generate_qc: '结算生成质控',
}

const sourceLabel = computed(() => SOURCE_LABELS[props.sourceKey] ?? '未知来源')
const errorMessage = computed(() => (typeof props.error === 'string' ? props.error.trim() : ''))
const hasSnapshot = computed(() => props.snapshot !== null)
const latestResult = computed<ModernCaseQcResultRecord | null>(
  () => props.snapshot?.latest_qc_result ?? null,
)
const hasVerifiedResult = computed(() => latestResult.value !== null)
const activeDefects = computed<ModernCaseQcDefect[]>(() => props.snapshot?.active_defects ?? [])
const currentResultDefects = computed<ModernCaseQcDefect[]>(
  () => props.snapshot?.current_result_defects ?? [],
)
const recentResults = computed<ModernCaseQcResultRecord[]>(
  () => props.snapshot?.recent_results ?? [],
)
const latestNotification = computed<ModernCaseQcNotification | null>(
  () => props.snapshot?.latest_notification ?? null,
)
const resultId = computed(() => {
  const record = latestResult.value
  if (!record) {
    return '—'
  }
  return text(record.id ?? record.result_id) || '—'
})

/** 只做搬运：非字符串或空值一律按安全空值处理，不解释字段含义。 */
function text(value: unknown): string {
  if (typeof value === 'string') {
    return value.trim()
  }
  if (typeof value === 'number' || typeof value === 'boolean') {
    return String(value)
  }
  return ''
}

function valueOrDash(value: unknown): string {
  return text(value) || '—'
}

function toDate(value: unknown): Date | null {
  const raw = text(value)
  if (!raw) {
    return null
  }
  const parsed = new Date(raw)
  return Number.isNaN(parsed.getTime()) ? null : parsed
}

function pad(part: number): string {
  return String(part).padStart(2, '0')
}

function formatDate(value: unknown): string {
  const parsed = toDate(value)
  if (!parsed) {
    return valueOrDash(value)
  }
  return `${parsed.getFullYear()}-${pad(parsed.getMonth() + 1)}-${pad(parsed.getDate())}`
}

function formatTime(value: unknown): string {
  const parsed = toDate(value)
  if (!parsed) {
    return valueOrDash(value)
  }
  return `${formatDate(value)} ${pad(parsed.getHours())}:${pad(parsed.getMinutes())}`
}

function historyTime(record: ModernCaseQcResultRecord): string {
  return text(record.analysis_date) ? formatDate(record.analysis_date) : formatTime(record.created_at)
}

function defectTitle(defect: ModernCaseQcDefect, index: number): string {
  return text(defect.rule_name) || text(defect.category) || `缺陷 ${index + 1}`
}

function defectKey(scope: string, defect: ModernCaseQcDefect, index: number): string {
  return `${scope}-${text(defect.id) || index}`
}

function recordLabel(record: ModernCaseQcResultRecord, index: number): string {
  return text(record.id) || `结果 ${index + 1}`
}

function recordKey(record: ModernCaseQcResultRecord, index: number): string {
  return `history-${text(record.id) || index}`
}
</script>

<style scoped>
.case-qc-panel {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 16px;
  color: #1d1d1f;
  font-family: 'Source Han Sans SC', 'Microsoft YaHei UI', 'PingFang SC', sans-serif;
  font-size: 14px;
  line-height: 22px;
}

.case-qc-panel__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.case-qc-panel__heading {
  min-width: 0;
}

.case-qc-panel__title {
  margin: 0;
  font-size: 17px;
  font-weight: 600;
  line-height: 22px;
  color: #1d1d1f;
}

.case-qc-panel__badges {
  display: flex;
  align-items: center;
  flex: none;
  gap: 6px;
}

.case-qc-panel__chip {
  display: inline-block;
  padding: 1px 8px;
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 999px;
  background: rgba(0, 0, 0, 0.04);
  color: rgba(29, 29, 31, 0.78);
  font-size: 12px;
  line-height: 18px;
  white-space: nowrap;
}

.case-qc-panel__chip--accent {
  border-color: rgba(0, 122, 255, 0.24);
  background: rgba(0, 122, 255, 0.08);
  color: #007aff;
  font-weight: 600;
}

.case-qc-panel__state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  padding: 24px 16px;
  border: 1px dashed rgba(0, 0, 0, 0.12);
  border-radius: 8px;
  text-align: center;
}

.case-qc-panel__state--error {
  border-style: solid;
  border-color: rgba(239, 68, 68, 0.28);
  background: rgba(239, 68, 68, 0.04);
}

.case-qc-panel__state-icon {
  width: 20px;
  height: 20px;
  color: rgba(29, 29, 31, 0.38);
  stroke-width: 2;
}

.case-qc-panel__state-icon--danger {
  color: #ef4444;
}

.case-qc-panel__state-icon--spin {
  color: #007aff;
  animation: case-qc-spin 0.9s linear infinite;
}

@keyframes case-qc-spin {
  to {
    transform: rotate(360deg);
  }
}

.case-qc-panel__state-title {
  margin: 0;
  color: #1d1d1f;
  font-size: 14px;
  font-weight: 600;
  line-height: 22px;
}

.case-qc-panel__state-desc {
  margin: 0;
  max-width: 520px;
  color: rgba(29, 29, 31, 0.6);
  font-size: 13px;
  line-height: 20px;
}

.case-qc-panel__retry {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin-top: 8px;
  padding: 3px 14px;
  border: 1px solid rgba(0, 0, 0, 0.12);
  border-radius: 8px;
  background: #ffffff;
  color: #1d1d1f;
  font-family: inherit;
  font-size: 14px;
  line-height: 22px;
  cursor: pointer;
  transition:
    border-color 250ms cubic-bezier(0.25, 0.1, 0.25, 1),
    color 250ms cubic-bezier(0.25, 0.1, 0.25, 1);
}

.case-qc-panel__retry:hover {
  border-color: rgba(0, 122, 255, 0.32);
  color: #007aff;
}

.case-qc-panel__retry-icon {
  width: 14px;
  height: 14px;
  stroke-width: 2.1;
}

.case-qc-panel__body {
  display: flex;
  flex-direction: column;
}

.case-qc-panel__section {
  padding: 12px 0;
  border-top: 1px solid rgba(0, 0, 0, 0.06);
}

.case-qc-panel__section:first-child {
  padding-top: 0;
  border-top: none;
}

.case-qc-panel__section:last-child {
  padding-bottom: 0;
}

.case-qc-panel__section-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
}

.case-qc-panel__section-title {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  line-height: 22px;
  color: #1d1d1f;
}

.case-qc-panel__count {
  color: rgba(29, 29, 31, 0.38);
  font-size: 12px;
  line-height: 18px;
}

.case-qc-panel__section-desc {
  margin: 4px 0 0;
  color: rgba(29, 29, 31, 0.6);
  font-size: 12px;
  line-height: 18px;
}

.case-qc-panel__facts {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 8px 18px;
  margin: 10px 0 0;
}

.case-qc-panel__fact {
  min-width: 0;
}

.case-qc-panel__fact dt {
  color: rgba(29, 29, 31, 0.6);
  font-size: 12px;
  line-height: 18px;
}

.case-qc-panel__fact dd {
  margin: 2px 0 0;
  color: #1d1d1f;
  font-size: 14px;
  line-height: 22px;
  word-break: break-word;
}

.case-qc-panel__defects {
  display: flex;
  flex-direction: column;
  margin: 8px 0 0;
  padding: 0;
  list-style: none;
}

.case-qc-panel__defect {
  padding: 8px 0;
  border-top: 1px solid rgba(0, 0, 0, 0.06);
}

.case-qc-panel__defect:first-child {
  padding-top: 0;
  border-top: none;
}

.case-qc-panel__defect:last-child {
  padding-bottom: 0;
}

.case-qc-panel__defect-head {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
}

.case-qc-panel__defect-name {
  color: #1d1d1f;
  font-size: 14px;
  font-weight: 600;
  line-height: 22px;
}

.case-qc-panel__defect-desc {
  margin: 4px 0 0;
  color: rgba(29, 29, 31, 0.78);
  font-size: 14px;
  line-height: 22px;
  word-break: break-word;
}

.case-qc-panel__defect-meta {
  margin: 2px 0 0;
  color: rgba(29, 29, 31, 0.6);
  font-size: 13px;
  line-height: 20px;
  word-break: break-word;
}

.case-qc-panel__history {
  display: flex;
  flex-direction: column;
  margin: 8px 0 0;
  padding: 0;
  list-style: none;
}

.case-qc-panel__history-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 7px 0;
  border-top: 1px solid rgba(0, 0, 0, 0.06);
}

.case-qc-panel__history-row:first-child {
  padding-top: 0;
  border-top: none;
}

.case-qc-panel__history-id {
  min-width: 0;
  flex: 1 1 auto;
  color: #1d1d1f;
  font-size: 14px;
  line-height: 22px;
  word-break: break-all;
}

.case-qc-panel__history-meta,
.case-qc-panel__history-time {
  flex: none;
  color: rgba(29, 29, 31, 0.6);
  font-size: 13px;
  line-height: 20px;
}

.case-qc-panel__notice-head {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 8px;
}

.case-qc-panel__notice-title {
  color: #1d1d1f;
  font-size: 14px;
  font-weight: 600;
  line-height: 22px;
}

.case-qc-panel__notice-content {
  margin: 4px 0 0;
  color: rgba(29, 29, 31, 0.78);
  font-size: 14px;
  line-height: 22px;
  word-break: break-word;
}

.case-qc-panel__notice-time {
  margin: 4px 0 0;
  color: rgba(29, 29, 31, 0.38);
  font-size: 12px;
  line-height: 18px;
}

.case-qc-panel__empty {
  margin: 8px 0 0;
  color: rgba(29, 29, 31, 0.38);
  font-size: 13px;
  line-height: 20px;
}
</style>
