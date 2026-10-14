<template>
  <aside
    class="fpqc-preview mq-card"
    aria-label="首页质控结果预览"
    data-testid="fpqc-preview"
  >
    <p
      v-if="!record"
      class="fpqc-preview__placeholder"
    >
      在左侧选择一份病历查看首页质控结果
    </p>

    <template v-else>
      <header class="fpqc-preview__head">
        <div class="fpqc-preview__who">
          <strong>{{ record.patient_name || '姓名待核实' }}</strong>
          <span>{{ record.department || '—' }} · 住院号 {{ record.inpat_no || record.visit_id }}</span>
          <span v-if="record.discharge_date">出院 {{ record.discharge_date }}</span>
        </div>
        <div
          v-if="result"
          class="fpqc-preview__score"
        >
          <strong data-testid="fpqc-preview-score">{{ formatScore(result.score) }}</strong>
          <span :class="['mq-status', `mq-status--${GRADE_TONES[result.grade]}`]">{{
            GRADE_LABELS[result.grade]
          }}</span>
        </div>
      </header>

      <p
        v-if="loading"
        class="fpqc-preview__placeholder"
      >
        正在读取…
      </p>
      <p
        v-else-if="loadError"
        class="fpqc-preview__alert fpqc-preview__alert--danger"
        role="alert"
      >
        {{ loadError }}
      </p>

      <template v-else-if="detail">
        <div
          v-if="detail.stale"
          class="fpqc-preview__alert fpqc-preview__alert--warning"
          data-testid="fpqc-preview-stale"
        >
          <span>首页内容或质控规则已更新，当前结果可能已过期。</span>
          <button
            type="button"
            class="mq-btn fpqc-preview__inline-btn"
            :disabled="runBusy"
            @click="emit('rerun', recordRef)"
          >
            重新质控这一份
          </button>
        </div>

        <div
          v-if="!result"
          class="fpqc-preview__empty"
        >
          <p>这份首页还没有质控结果。</p>
          <button
            type="button"
            class="mq-btn mq-btn--primary"
            :disabled="runBusy"
            data-testid="fpqc-preview-run"
            @click="emit('rerun', recordRef)"
          >
            质控这一份
          </button>
        </div>

        <template v-else>
          <p class="fpqc-preview__meta">
            扣分问题 {{ result.fail_count }} 项 · 必填缺项 {{ result.required_missing_count }} 项 · 提示
            {{ result.hint_count }} 项 · 可评分项 {{ formatPercent(result.scorable_ratio) }} · 质控于
            {{ formatDateTime(result.created_at) }}
          </p>

          <p
            v-if="!groups.sections.length && !groups.hints.length"
            class="fpqc-preview__clean"
          >
            未发现扣分问题和必填缺项。
          </p>

          <section
            v-for="group in groups.sections"
            :key="group.section"
            class="fpqc-preview__section"
          >
            <h3>{{ group.label }}</h3>
            <article
              v-for="finding in group.findings"
              :key="finding.id"
              class="fpqc-finding"
              :class="`fpqc-finding--${finding.severity}`"
              data-testid="fpqc-finding"
            >
              <div class="fpqc-finding__head">
                <strong>{{ finding.problem }}</strong>
                <span
                  v-if="finding.deduction"
                  class="fpqc-finding__deduct"
                >-{{ formatScore(finding.deduction) }} 分</span>
                <span
                  v-else
                  class="fpqc-finding__tag"
                >{{ finding.severity === 'deduct' ? '同项已扣分' : SEVERITY_LABELS[finding.severity] }}</span>
              </div>
              <ul class="fpqc-finding__details">
                <li
                  v-for="(item, index) in finding.details"
                  :key="index"
                >
                  <span class="fpqc-finding__field">{{ item.field }}</span>：当前{{ detailValueText(item.value) }}；要求：{{
                    item.expected
                  }}
                </li>
              </ul>
              <div class="fpqc-finding__foot">
                <span class="mq-mono fpqc-finding__rule">{{ finding.rule_id }} {{ finding.rule_name }}</span>
                <span
                  :class="['mq-status', reviewTone(finding.review_status)]"
                  data-testid="fpqc-finding-review-status"
                >{{ REVIEW_LABELS[finding.review_status] }}</span>
              </div>
              <p
                v-if="finding.review_note"
                class="fpqc-finding__note"
              >
                复核意见：{{ finding.review_note }}
              </p>
              <div class="fpqc-finding__actions">
                <template v-if="editingId === finding.id">
                  <input
                    v-model="noteDraft"
                    class="mq-input fpqc-finding__input"
                    maxlength="500"
                    placeholder="填写误报原因（必填）"
                    aria-label="误报原因"
                  >
                  <button
                    type="button"
                    class="mq-btn fpqc-finding__btn"
                    :disabled="!noteDraft.trim() || savingId === finding.id"
                    @click="saveReview(finding, 'false_alarm', noteDraft)"
                  >
                    保存为误报
                  </button>
                  <button
                    type="button"
                    class="mq-btn fpqc-finding__btn"
                    @click="cancelEdit"
                  >
                    取消
                  </button>
                </template>
                <template v-else>
                  <button
                    v-if="finding.review_status !== 'confirmed'"
                    type="button"
                    class="mq-btn fpqc-finding__btn"
                    :disabled="savingId === finding.id"
                    @click="saveReview(finding, 'confirmed', '')"
                  >
                    确认问题
                  </button>
                  <button
                    v-if="finding.review_status !== 'false_alarm'"
                    type="button"
                    class="mq-btn fpqc-finding__btn"
                    :disabled="savingId === finding.id"
                    @click="startFalseAlarm(finding)"
                  >
                    标记误报
                  </button>
                  <button
                    v-if="finding.review_status !== 'pending'"
                    type="button"
                    class="mq-btn fpqc-finding__btn"
                    :disabled="savingId === finding.id"
                    @click="saveReview(finding, 'pending', '')"
                  >
                    撤回复核
                  </button>
                </template>
              </div>
            </article>
          </section>

          <details
            v-if="groups.hints.length"
            class="fpqc-preview__fold"
            open
          >
            <summary>提示 {{ groups.hints.length }} 项（不扣分，请核实）</summary>
            <article
              v-for="finding in groups.hints"
              :key="finding.id"
              class="fpqc-finding fpqc-finding--hint"
            >
              <div class="fpqc-finding__head">
                <strong>{{ finding.problem }}</strong>
              </div>
              <ul class="fpqc-finding__details">
                <li
                  v-for="(item, index) in finding.details"
                  :key="index"
                >
                  <span class="fpqc-finding__field">{{ item.field }}</span>：当前{{ detailValueText(item.value) }}；{{
                    item.expected
                  }}
                </li>
              </ul>
            </article>
          </details>

          <details
            v-if="groups.dataGaps.length"
            class="fpqc-preview__fold"
            data-testid="fpqc-preview-data-gaps"
          >
            <summary>资料不足 {{ groups.dataGaps.length }} 项（不扣分，不计入问题）</summary>
            <ul class="fpqc-preview__gaps">
              <li
                v-for="item in gapSummary"
                :key="item.reason"
              >
                <strong>{{ item.reason }}</strong>：{{ item.rules.join('、') }}
              </li>
            </ul>
          </details>
        </template>
      </template>
    </template>
  </aside>
</template>

<script setup lang="ts">
import { message } from 'ant-design-vue'
import { computed, ref, watch } from 'vue'

import {
  getFrontpageQcRecord,
  reviewFrontpageQcFinding,
  type FrontpageQcFinding,
  type FrontpageQcRecordDetail,
  type FrontpageQcRecordItem,
  type FrontpageQcRef,
  type FrontpageQcReviewStatus,
} from '@/services/frontpage-qc-v2-service'

import {
  detailValueText,
  formatDateTime,
  formatPercent,
  formatScore,
  GRADE_LABELS,
  GRADE_TONES,
  groupFindings,
  REVIEW_LABELS,
  SEVERITY_LABELS,
  summarizeDataGaps,
} from './presentation'

const props = defineProps<{
  record: FrontpageQcRecordItem | null
  refreshKey: number
  runBusy: boolean
}>()
const emit = defineEmits<{ rerun: [ref: FrontpageQcRef]; reviewed: [] }>()

const detail = ref<FrontpageQcRecordDetail | null>(null)
const loading = ref(false)
const loadError = ref('')
const editingId = ref('')
const noteDraft = ref('')
const savingId = ref('')
let requestSeq = 0

const recordRef = computed<FrontpageQcRef>(() => ({
  institute_id: props.record?.institute_id ?? '',
  patient_id: props.record?.patient_id ?? '',
  visit_id: props.record?.visit_id ?? '',
}))
const result = computed(() => detail.value?.result ?? null)
const groups = computed(() => groupFindings(result.value?.findings ?? []))
const gapSummary = computed(() => summarizeDataGaps(groups.value.dataGaps))

function reviewTone(status: FrontpageQcReviewStatus): string {
  if (status === 'confirmed') return 'mq-status--danger'
  if (status === 'false_alarm') return 'mq-status--info'
  return ''
}

async function load() {
  const seq = ++requestSeq
  editingId.value = ''
  if (!props.record) {
    detail.value = null
    return
  }
  loading.value = true
  loadError.value = ''
  try {
    const next = await getFrontpageQcRecord(recordRef.value)
    if (seq === requestSeq) detail.value = next
  } catch (error) {
    if (seq === requestSeq) {
      detail.value = null
      loadError.value = error instanceof Error ? error.message : '读取首页质控详情失败'
    }
  } finally {
    if (seq === requestSeq) loading.value = false
  }
}

watch(
  () => [props.record?.record_key, props.refreshKey],
  () => {
    void load()
  },
  { immediate: true },
)

function startFalseAlarm(finding: FrontpageQcFinding) {
  editingId.value = finding.id
  noteDraft.value = finding.review_note || ''
}

function cancelEdit() {
  editingId.value = ''
  noteDraft.value = ''
}

async function saveReview(finding: FrontpageQcFinding, status: FrontpageQcReviewStatus, note: string) {
  savingId.value = finding.id
  try {
    const saved = await reviewFrontpageQcFinding(finding.id, { status, note: note.trim() })
    const findings = result.value?.findings ?? []
    const index = findings.findIndex((item) => item.id === saved.id)
    if (index >= 0) findings.splice(index, 1, saved)
    cancelEdit()
    emit('reviewed')
  } catch (error) {
    message.error(error instanceof Error ? error.message : '保存复核失败')
    // 结果被重新质控替换时，重新读取最新结果
    void load()
  } finally {
    savingId.value = ''
  }
}
</script>

<style scoped>
.fpqc-preview {
  display: flex;
  flex-direction: column;
  gap: 14px;
  min-width: 0;
  max-height: calc(100vh - 160px);
  overflow-y: auto;
  padding: 20px 22px;
}

.fpqc-preview__placeholder {
  margin: 40px 0;
  color: var(--mq-text-tertiary);
  text-align: center;
}

.fpqc-preview__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.fpqc-preview__who {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.fpqc-preview__who strong {
  font-size: var(--mq-font-16, 16px);
}

.fpqc-preview__who span {
  color: var(--mq-text-tertiary);
  font-size: var(--mq-font-12);
}

.fpqc-preview__score {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 4px;
}

.fpqc-preview__score strong {
  font-family: var(--mq-font-display);
  font-size: 30px;
  line-height: 1;
}

.fpqc-preview__meta {
  margin: 0;
  color: var(--mq-text-secondary);
  font-size: var(--mq-font-12);
}

.fpqc-preview__alert {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px 12px;
  margin: 0;
  padding: 10px 14px;
  border-radius: 12px;
  font-size: var(--mq-font-13);
}

.fpqc-preview__alert--warning {
  background: var(--mq-warning-bg);
  color: var(--mq-warning-text);
}

.fpqc-preview__alert--danger {
  background: var(--mq-danger-bg);
  color: var(--mq-danger-text);
}

.fpqc-preview__inline-btn {
  height: 30px;
  padding: 0 12px;
  font-size: var(--mq-font-12);
}

.fpqc-preview__empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: 24px 0;
  color: var(--mq-text-secondary);
}

.fpqc-preview__empty p,
.fpqc-preview__clean {
  margin: 0;
}

.fpqc-preview__clean {
  padding: 12px 14px;
  border-radius: 12px;
  background: var(--mq-success-bg);
  color: var(--mq-success-text);
  font-size: var(--mq-font-13);
}

.fpqc-preview__section {
  display: grid;
  gap: 10px;
}

.fpqc-preview__section h3 {
  margin: 0;
  color: var(--mq-text-secondary);
  font-size: var(--mq-font-13);
  font-weight: 700;
}

.fpqc-finding {
  display: grid;
  gap: 8px;
  padding: 12px 14px;
  border: 1px solid var(--mq-border);
  border-left: 3px solid var(--mq-danger-icon);
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.8);
}

.fpqc-finding--required {
  border-left-color: var(--mq-warning-icon);
}

.fpqc-finding--hint {
  border-left-color: var(--mq-info-icon);
}

.fpqc-finding__head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 10px;
}

.fpqc-finding__head strong {
  font-size: var(--mq-font-14);
}

.fpqc-finding__deduct {
  color: var(--mq-danger-text);
  font-weight: 700;
  white-space: nowrap;
}

.fpqc-finding__tag {
  color: var(--mq-text-tertiary);
  font-size: var(--mq-font-12);
  white-space: nowrap;
}

.fpqc-finding__details {
  display: grid;
  gap: 4px;
  margin: 0;
  padding-left: 16px;
  color: var(--mq-text-secondary);
  font-size: var(--mq-font-13);
}

.fpqc-finding__field {
  color: var(--mq-text-primary);
  font-weight: 600;
}

.fpqc-finding__foot {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
}

.fpqc-finding__rule {
  color: var(--mq-text-tertiary);
}

.fpqc-finding__note {
  margin: 0;
  color: var(--mq-text-secondary);
  font-size: var(--mq-font-12);
}

.fpqc-finding__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.fpqc-finding__btn {
  height: 30px;
  padding: 0 12px;
  font-size: var(--mq-font-12);
}

.fpqc-finding__input {
  flex: 1 1 200px;
  height: 30px;
}

.fpqc-preview__fold summary {
  color: var(--mq-text-secondary);
  font-size: var(--mq-font-13);
  font-weight: 600;
  cursor: pointer;
}

.fpqc-preview__fold > .fpqc-finding {
  margin-top: 8px;
}

.fpqc-preview__gaps {
  display: grid;
  gap: 4px;
  margin: 8px 0 0;
  padding-left: 18px;
  color: var(--mq-text-secondary);
  font-size: var(--mq-font-13);
}
</style>
