<template>
  <aside
    class="fpqc-preview"
    aria-label="首页质控结果预览"
    data-testid="fpqc-preview"
  >
    <div
      v-if="!record"
      class="fpqc-preview__state"
    >
      点击左侧任一病历，在这里查看首页质控结果。
    </div>

    <template v-else>
      <header class="fpqc-preview__head">
        <div class="fpqc-preview__identity">
          <span class="fpqc-preview__eyebrow">首页质控结果</span>
          <strong class="fpqc-preview__name">{{ record.patient_name || '姓名待核实' }}</strong>
          <span class="fpqc-preview__visit">住院号 {{ record.inpat_no || record.visit_id }}</span>
        </div>
        <div
          v-if="result"
          class="fpqc-preview__score"
        >
          <span class="fpqc-preview__score-value">
            <strong data-testid="fpqc-preview-score">{{ formatScore(result.score) }}</strong>分
          </span>
          <span :class="['mq-status', `mq-status--${GRADE_TONES[result.grade]}`]">{{
            GRADE_LABELS[result.grade]
          }}</span>
        </div>
      </header>

      <div
        class="fpqc-preview__body"
        data-testid="fpqc-preview-body"
      >
        <dl class="fpqc-preview__facts">
        <div>
          <dt>科室</dt>
          <dd>{{ record.department || result?.department || '—' }}</dd>
        </div>
        <div>
          <dt>出院日期</dt>
          <dd>{{ record.discharge_date || result?.discharge_date || '—' }}</dd>
        </div>
        <div>
          <dt>质控时间</dt>
          <dd>{{ result ? formatDateTime(result.created_at) : '—' }}</dd>
        </div>
        <div
          v-if="!confirmedResultsOnly"
          data-testid="fpqc-preview-scorable-ratio"
        >
          <dt>可评分项</dt>
          <dd>{{ result ? formatPercent(result.scorable_ratio) : '—' }}</dd>
        </div>
      </dl>

      <div
        v-if="loading && !activeDetail"
        class="fpqc-preview__state"
        role="status"
      >
        正在读取质控结果…
      </div>
      <div
        v-else-if="loadError && !activeDetail"
        class="fpqc-preview__state fpqc-preview__state--action"
        role="alert"
      >
        <p>{{ loadError }}</p>
        <button
          type="button"
          class="mq-btn"
          data-testid="fpqc-preview-retry"
          @click="load()"
        >
          重试
        </button>
      </div>

      <template v-else-if="activeDetail">
        <div
          v-if="loadError"
          class="fpqc-preview__notice"
          role="alert"
        >
          <p>{{ loadError }}</p>
          <button
            type="button"
            class="mq-btn fpqc-preview__notice-btn"
            data-testid="fpqc-preview-retry"
            @click="load({ preserveEdit: true })"
          >
            重试
          </button>
        </div>
        <div
          v-if="activeDetail.stale"
          class="fpqc-preview__notice"
          data-testid="fpqc-preview-stale"
        >
          <p>首页内容或质控规则已更新，当前结果可能已过期。</p>
          <button
            type="button"
            class="mq-btn fpqc-preview__notice-btn"
            :disabled="runBusy"
            @click="emit('rerun', recordRef)"
          >
            重新质控
          </button>
        </div>

        <div
          v-if="!result"
          class="fpqc-preview__state fpqc-preview__state--action"
        >
          <p>这份首页还没有质控结果。</p>
          <button
            type="button"
            class="mq-btn mq-btn--primary"
            :disabled="runBusy"
            data-testid="fpqc-preview-run"
            @click="emit('rerun', recordRef)"
          >
            质控此首页
          </button>
        </div>

        <template v-else>
          <dl
            class="mq-soft fpqc-preview__counts"
            :style="{ gridTemplateColumns: `repeat(${counts.length}, minmax(0, 1fr))` }"
            aria-label="问题数量"
          >
            <div
              v-for="item in counts"
              :key="item.label"
              :class="{ [`is-${item.tone}`]: item.value > 0 }"
            >
              <dt>{{ item.label }}</dt>
              <dd>{{ item.value }}</dd>
            </div>
          </dl>

          <p
            v-if="!groups.sections.length && (confirmedResultsOnly || !groups.hints.length)"
            class="fpqc-preview__clean"
          >
            未发现扣分问题和必填缺项。
          </p>

          <section
            v-for="group in groups.sections"
            :key="group.section"
            class="fpqc-preview__group"
          >
            <h3>{{ group.label }}<span>{{ group.findings.length }} 项</span></h3>
            <article
              v-for="finding in group.findings"
              :key="finding.id"
              class="fpqc-finding"
              data-testid="fpqc-finding"
            >
              <div class="fpqc-finding__meta">
                <span :class="['mq-status', severityTone(finding)]">{{ severityText(finding) }}</span>
                <span
                  :class="['mq-status', reviewTone(finding.review_status)]"
                  data-testid="fpqc-finding-review-status"
                >{{ REVIEW_LABELS[finding.review_status] }}</span>
              </div>
              <h4 class="fpqc-finding__title">
                {{ finding.problem }}
              </h4>
              <dl
                v-for="(item, index) in finding.details"
                :key="index"
                class="fpqc-finding__detail"
              >
                <div>
                  <dt>项目</dt>
                  <dd>{{ item.field }}</dd>
                </div>
                <div>
                  <dt>当前</dt>
                  <dd :class="{ 'is-empty': !item.value }">
                    {{ item.value || '未填写' }}
                  </dd>
                </div>
                <div>
                  <dt>要求</dt>
                  <dd>{{ item.expected }}</dd>
                </div>
              </dl>
              <p class="fpqc-finding__rule">
                <span class="mq-mono">{{ finding.rule_id }}</span>{{ finding.rule_name }}
              </p>
              <p
                v-if="finding.review_note"
                class="fpqc-finding__note"
              >
                复核意见：{{ finding.review_note }}
              </p>

              <div
                v-if="editingId === finding.id"
                class="fpqc-finding__edit"
              >
                <input
                  :ref="setNoteInputRef"
                  v-model="noteDraft"
                  class="mq-input"
                  maxlength="500"
                  placeholder="填写误报原因（必填）"
                  aria-label="误报原因"
                  @keydown.enter.prevent="submitFalseAlarm(finding)"
                  @keydown.esc.prevent="cancelEdit"
                >
                <div class="fpqc-finding__edit-actions">
                  <button
                    type="button"
                    class="mq-btn"
                    @click="cancelEdit"
                  >
                    取消
                  </button>
                  <button
                    type="button"
                    class="mq-btn mq-btn--primary"
                    :disabled="!noteDraft.trim() || isSaving(finding.id)"
                    @click="saveReview(finding, 'false_alarm', noteDraft)"
                  >
                    保存为误报
                  </button>
                </div>
              </div>
              <div
                v-else
                class="fpqc-finding__actions"
              >
                <button
                  v-if="finding.review_status !== 'confirmed'"
                  type="button"
                  class="fpqc-finding__link"
                  :disabled="isSaving(finding.id)"
                  @click="saveReview(finding, 'confirmed', '')"
                >
                  确认问题
                </button>
                <button
                  v-if="finding.review_status !== 'false_alarm'"
                  type="button"
                  class="fpqc-finding__link"
                  :disabled="isSaving(finding.id)"
                  @click="startFalseAlarm(finding)"
                >
                  标记误报
                </button>
                <button
                  v-if="finding.review_status !== 'pending'"
                  type="button"
                  class="fpqc-finding__link"
                  :disabled="isSaving(finding.id)"
                  @click="saveReview(finding, 'pending', '')"
                >
                  撤回复核
                </button>
              </div>
            </article>
          </section>

          <details
            v-if="!confirmedResultsOnly && groups.hints.length"
            class="fpqc-preview__fold"
            data-testid="fpqc-preview-hints"
            open
          >
            <summary>提示 {{ groups.hints.length }} 项<span>不扣分，请人工核实</span></summary>
            <article
              v-for="finding in groups.hints"
              :key="finding.id"
              class="fpqc-finding fpqc-finding--compact"
            >
              <h4 class="fpqc-finding__title">
                {{ finding.problem }}
              </h4>
              <p
                v-for="(item, index) in finding.details"
                :key="index"
                class="fpqc-finding__line"
              >
                {{ item.field }}：当前{{ detailValueText(item.value) }}；{{ item.expected }}
              </p>
            </article>
          </details>

          <details
            v-if="!confirmedResultsOnly && groups.dataGaps.length"
            class="fpqc-preview__fold"
            data-testid="fpqc-preview-data-gaps"
          >
            <summary>资料不足 {{ groups.dataGaps.length }} 项<span>不扣分，不计入问题</span></summary>
            <dl class="mq-soft fpqc-preview__gaps">
              <div
                v-for="item in gapSummary"
                :key="item.reason"
              >
                <dt>{{ item.reason }}</dt>
                <dd>{{ item.rules.join('、') }}</dd>
              </div>
            </dl>
          </details>
        </template>
      </template>
      </div>
    </template>
  </aside>
</template>

<script setup lang="ts">
import { message } from 'ant-design-vue'
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'

import { useQcResultVisibility } from '@/composables/useQcResultVisibility'
import {
  getFrontpageQcRecord,
  isFrontpageQcAbortError,
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

const { confirmedResultsOnly } = useQcResultVisibility()

const detail = ref<FrontpageQcRecordDetail | null>(null)
const loading = ref(false)
const loadError = ref('')
const editingId = ref('')
const noteDraft = ref('')
const savingIds = ref<Set<string>>(new Set())
let noteInputEl: HTMLInputElement | null = null
let requestSeq = 0
let controller: AbortController | null = null
let disposed = false

function isSaving(id: string): boolean {
  return savingIds.value.has(id)
}

function setSaving(id: string, active: boolean) {
  const next = new Set(savingIds.value)
  if (active) next.add(id)
  else next.delete(id)
  savingIds.value = next
}

function setNoteInputRef(el: unknown) {
  noteInputEl = el instanceof HTMLInputElement ? el : null
}

const recordRef = computed<FrontpageQcRef>(() => ({
  institute_id: props.record?.institute_id ?? '',
  patient_id: props.record?.patient_id ?? '',
  visit_id: props.record?.visit_id ?? '',
}))
const activeDetail = computed<FrontpageQcRecordDetail | null>(() => {
  const currentKey = props.record?.record_key
  if (!currentKey || !detail.value) return null
  return detail.value.record.record_key === currentKey ? detail.value : null
})
const result = computed(() => activeDetail.value?.result ?? null)
const groups = computed(() => groupFindings(result.value?.findings ?? []))
const gapSummary = computed(() => summarizeDataGaps(groups.value.dataGaps))
const counts = computed(() => {
  const value = result.value
  const items = [
    { label: '扣分问题', value: value?.fail_count ?? 0, tone: 'danger' },
    { label: '必填缺项', value: value?.required_missing_count ?? 0, tone: 'danger' },
  ]
  if (!confirmedResultsOnly.value) {
    items.push(
      { label: '提示', value: value?.hint_count ?? 0, tone: 'warning' },
      { label: '资料不足', value: value?.data_gap_count ?? 0, tone: 'neutral' },
    )
  }
  return items
})

function severityText(finding: FrontpageQcFinding): string {
  if (finding.deduction) return `扣 ${formatScore(finding.deduction)} 分`
  // 同一评分项已在别的问题上扣满时，本条不再重复扣分
  return finding.severity === 'deduct' ? '同项已扣分' : SEVERITY_LABELS[finding.severity]
}

function severityTone(finding: FrontpageQcFinding): string {
  if (finding.deduction || finding.severity === 'required') return 'mq-status--danger'
  return ''
}

function reviewTone(status: FrontpageQcReviewStatus): string {
  if (status === 'confirmed') return 'mq-status--success'
  if (status === 'false_alarm') return 'mq-status--info'
  return ''
}

async function load(options: { preserveEdit?: boolean } = {}) {
  const preserveEdit = Boolean(options.preserveEdit)
  controller?.abort()
  controller = null
  const seq = ++requestSeq
  loadError.value = ''
  if (!preserveEdit) {
    cancelEdit()
    detail.value = null
  }
  if (!props.record) {
    cancelEdit()
    detail.value = null
    loading.value = false
    return
  }
  const expectedKey = props.record.record_key
  const refToLoad = { ...recordRef.value }
  const nextController = new AbortController()
  controller = nextController
  loading.value = true
  try {
    const next = await getFrontpageQcRecord(refToLoad, { signal: nextController.signal })
    if (
      disposed ||
      seq !== requestSeq ||
      nextController.signal.aborted ||
      props.record?.record_key !== expectedKey
    ) {
      return
    }
    detail.value = next
    if (preserveEdit && editingId.value) {
      const stillExists =
        next.record.record_key === expectedKey &&
        Boolean(next.result?.findings.some((item) => item.id === editingId.value))
      if (!stillExists) cancelEdit()
    }
  } catch (error) {
    if (
      disposed ||
      seq !== requestSeq ||
      nextController.signal.aborted ||
      isFrontpageQcAbortError(error) ||
      props.record?.record_key !== expectedKey
    ) {
      return
    }
    if (!preserveEdit) detail.value = null
    loadError.value = error instanceof Error ? error.message : '读取首页质控详情失败'
  } finally {
    if (!disposed && seq === requestSeq) loading.value = false
    if (controller === nextController) controller = null
  }
}

watch(
  () => [props.record?.record_key, props.refreshKey] as const,
  ([nextKey, nextRefresh], prev) => {
    const prevKey = prev?.[0]
    const isSameRecordRefresh = Boolean(
      nextKey && prevKey && nextKey === prevKey && nextRefresh !== prev?.[1],
    )
    void load({ preserveEdit: isSameRecordRefresh })
  },
  { immediate: true },
)

async function startFalseAlarm(finding: FrontpageQcFinding) {
  editingId.value = finding.id
  noteDraft.value = finding.review_note || ''
  await nextTick()
  noteInputEl?.focus()
}

function submitFalseAlarm(finding: FrontpageQcFinding) {
  if (!noteDraft.value.trim() || savingIds.value.has(finding.id)) return
  void saveReview(finding, 'false_alarm', noteDraft.value)
}

function cancelEdit() {
  editingId.value = ''
  noteDraft.value = ''
}

async function saveReview(finding: FrontpageQcFinding, status: FrontpageQcReviewStatus, note: string) {
  if (disposed || savingIds.value.has(finding.id)) return
  const trimmedNote = note.trim()
  if (status === 'false_alarm' && !trimmedNote) return
  const expectedKey = props.record?.record_key ?? ''
  setSaving(finding.id, true)
  try {
    const saved = await reviewFrontpageQcFinding(finding.id, { status, note: trimmedNote })
    if (
      !disposed &&
      props.record?.record_key === expectedKey &&
      activeDetail.value?.record.record_key === expectedKey
    ) {
      const findings = activeDetail.value.result?.findings ?? []
      const index = findings.findIndex((item) => item.id === saved.id)
      if (index >= 0) findings.splice(index, 1, saved)
      if (editingId.value === finding.id) cancelEdit()
    }
    if (!disposed) emit('reviewed')
  } catch (error) {
    if (!disposed) {
      message.error(error instanceof Error ? error.message : '保存复核失败')
    }
    // 结果被重新质控替换时，重新读取最新结果
    if (!disposed && props.record?.record_key === expectedKey) {
      void load({ preserveEdit: true })
    }
  } finally {
    setSaving(finding.id, false)
  }
}

onBeforeUnmount(() => {
  disposed = true
  requestSeq += 1
  controller?.abort()
  controller = null
})
</script>

<style scoped src="../styles/frontpage-qc-preview.css"></style>
