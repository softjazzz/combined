<template>
  <a-drawer
    :open="Boolean(row)"
    width="min(760px, 100vw)"
    placement="right"
    :closable="false"
    :body-style="{ padding: 0 }"
    root-class-name="rv-review-drawer"
    @close="emit('close')"
  >
    <div
      v-if="row"
      class="rv-review"
      data-testid="case-review-drawer"
    >
      <header class="rv-review__head">
        <div class="rv-review__title">
          <span class="rv-muted">逐例核对 · {{ index + 1 }} / {{ rows.length }} · 运行 {{ runTime }}</span>
          <h2>{{ row.case_title }}</h2>
          <div class="rv-review__tags">
            <span class="rv-tag">{{ SOURCE_KINDS[row.source_kind] }}</span>
            <span class="rv-tag">{{ PURPOSES[row.purpose] }}</span>
            <span class="rv-tag">评价时间点 {{ row.evaluation_as_of_date || '未固定' }}</span>
          </div>
        </div>
        <div class="rv-review__nav">
          <button
            type="button"
            class="mq-btn rv-icon-btn"
            aria-label="上一例"
            :disabled="index === 0"
            @click="emit('navigate', index - 1)"
          >
            ‹
          </button>
          <button
            type="button"
            class="mq-btn rv-icon-btn"
            aria-label="下一例"
            :disabled="index >= rows.length - 1"
            @click="emit('navigate', index + 1)"
          >
            ›
          </button>
          <button
            type="button"
            class="mq-btn rv-icon-btn"
            aria-label="关闭"
            @click="emit('close')"
          >
            ×
          </button>
        </div>
      </header>

      <div class="rv-review__body">
        <div class="rv-review__pair">
          <div class="mq-inset rv-review__side">
            <span class="rv-muted">人工预期 · r{{ row.answer_revision
            }}{{ row.labeled_by ? ` · 标注人 ${row.labeled_by}` : '' }}</span>
            <span :class="statusClass(STATUS[row.expected_status].tone)">{{
              STATUS[row.expected_status].label
            }}</span>
            <p>{{ row.human_reason }}</p>
          </div>
          <div
            class="mq-inset rv-review__side"
            :class="{ 'is-different': row.comparison !== 'same' }"
          >
            <span class="rv-muted">系统结论 · {{ COMPARISONS[row.comparison].label }}</span>
            <span :class="statusClass(actual.tone)">{{ actual.label }}</span>
            <p>{{ conclusion || '（无结论文案）' }}</p>
          </div>
        </div>

        <section v-if="findings.length">
          <h3>判定事实</h3>
          <ul class="mq-soft rv-review__list">
            <li
              v-for="(item, i) in findings"
              :key="i"
            >
              {{ item }}
            </li>
          </ul>
        </section>

        <section v-if="publicFacts.length">
          <h3>结构化判定事实</h3>
          <ul class="mq-soft rv-review__list">
            <li
              v-for="fact in publicFacts"
              :key="fact.path"
            >
              {{ fact.path }}：{{ fact.value }}
            </li>
          </ul>
        </section>
        <CriterionResultBlock
          v-if="row.result?.criterion_results?.length"
          :criteria="row.result.criterion_results"
          variant="decision"
        />
        <section>
          <h3>证据原文</h3>
          <div
            v-if="evidence.length"
            class="rv-review__evidence"
          >
            <div
              v-for="(item, i) in evidence"
              :key="i"
              class="mq-inset rv-review__quote"
            >
              <div class="rv-review__quote-head">
                <b>{{ item.title }}</b>
                <span class="mq-mono rv-muted">{{ item.time }}</span>
              </div>
              <p>{{ item.text }}</p>
            </div>
          </div>
          <p
            v-else
            class="rv-muted"
          >
            本条结果没有返回证据片段。
          </p>
        </section>

        <section>
          <h3>修改建议</h3>
          <p class="mq-soft rv-review__text">
            {{ suggestion || '（无修改建议）' }}
          </p>
        </section>

        <section v-if="history.length">
          <h3>核对记录</h3>
          <ul class="rv-review__history">
            <li
              v-for="entry in history"
              :key="entry.id"
            >
              <span :class="statusClass(entry.decision === 'confirmed' ? 'success' : 'danger')">{{
                entry.decision === 'confirmed' ? '已确认' : '有问题'
              }}</span>
              <span>{{ entry.note }}</span>
              <span class="rv-muted">{{ entry.actor }} · {{ formatTime(entry.created_at) }}</span>
            </li>
          </ul>
        </section>

        <label class="mq-field">
          <span class="mq-field__label">核对意见</span>
          <a-textarea
            v-model:value="note"
            aria-label="核对意见"
            :rows="3"
            :maxlength="4000"
            placeholder="写明证据是否指向正确原文、建议是否可用；状态不一致时说明原因"
          />
        </label>
        <a-alert
          v-if="error"
          type="error"
          :message="error"
          show-icon
        />
      </div>

      <footer class="rv-review__foot">
        <span class="rv-muted">状态与预期不一致时只能记录问题；确认通过要求状态一致且证据、建议均正确。</span>
        <div class="rv-review__actions">
          <button
            type="button"
            class="mq-btn"
            :disabled="busy || !reviewable || !note.trim()"
            @click="submit('problem')"
          >
            记录问题
          </button>
          <button
            type="button"
            class="mq-btn mq-btn--primary"
            data-testid="confirm-case"
            :disabled="busy || row.comparison !== 'same' || !note.trim()"
            @click="submit('confirmed')"
          >
            确认证据与建议正确
          </button>
        </div>
      </footer>
    </div>
  </a-drawer>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import CriterionResultBlock from '../customer-sample-validation/CriterionResultBlock.vue'
import { customerFactValueLabel } from '../customer-sample-validation/customerFactValuePresentation'
import { reviewCase } from '@/services/rule-validation-service'
import type { ComparisonRow, ValidationEvent } from '@/services/rule-validation-service'
import {
  COMPARISONS,
  PURPOSES,
  SOURCE_KINDS,
  STATUS,
  formatTime,
  statusClass,
  statusLabel,
} from './presentation'
import { typeLabel } from './caseDraft'

const props = defineProps<{
  runId: string
  runTime: string
  rows: ComparisonRow[]
  index: number
  reviews: ValidationEvent[]
}>()
const emit = defineEmits<{ close: []; navigate: [index: number]; reviewed: [] }>()

const note = ref('')
const busy = ref(false)
const error = ref('')

const row = computed<ComparisonRow | null>(() =>
  props.index >= 0 ? (props.rows[props.index] ?? null) : null,
)
const actual = computed(() => statusLabel(row.value?.actual_status))
const reviewable = computed(() =>
  Boolean(row.value && !['pending', 'failed'].includes(row.value.comparison)),
)
const conclusion = computed(
  () => text(row.value?.result?.customer_conclusion) || text(row.value?.result?.conclusion),
)
const suggestion = computed(
  () => text(row.value?.result?.customer_suggestion) || text(row.value?.result?.suggestion),
)
const history = computed(() => props.reviews.filter((e) => e.item_id === row.value?.item_id))

function text(value: unknown): string {
  return typeof value === 'string' ? value.trim() : ''
}
function asList(value: unknown): Record<string, unknown>[] {
  if (!Array.isArray(value)) return []
  return value.map((v) =>
    v && typeof v === 'object' ? (v as Record<string, unknown>) : { text: String(v) },
  )
}
function pick(item: Record<string, unknown>, keys: string[]): string {
  for (const key of keys) {
    const value = text(item[key])
    if (value) return value
  }
  return ''
}

/** 判定事实与证据结构随规则执行器不同，这里只按常见字段展示，不重判。 */
const findings = computed(() =>
  asList(row.value?.result?.findings)
    .map((f) => pick(f, ['text', 'summary', 'finding', 'description', 'message']))
    .filter(Boolean),
)
// 只展开已通过服务端客户安全投影的事实，不重算状态或删减事件。
function factRows(value: unknown, path = ''): { path: string; value: string }[] {
  if (Array.isArray(value)) return value.flatMap((v, i) => factRows(v, `${path} · 第${i + 1}项`))
  if (value !== null && typeof value === 'object') {
    return Object.entries(value).flatMap(([key, child]) =>
      factRows(child, [path, customerFactValueLabel(key) || key].filter(Boolean).join(' / ')),
    )
  }
  return [
    { path, value: value == null ? '未提供' : customerFactValueLabel(value) || String(value) },
  ]
}
const publicFacts = computed(() => factRows(row.value?.result?.customer_display_facts || {}))
const evidence = computed(() =>
  asList(row.value?.result?.evidence).map((e) => ({
    title:
      pick(e, ['document_title', 'document_name', 'source_label']) ||
      typeLabel(pick(e, ['source_type', 'document_type', 'source'])) ||
      '证据',
    time: pick(e, ['document_time', 'record_time', 'time']),
    text:
      pick(e, ['evidence_excerpt', 'excerpt', 'matched_text', 'text', 'summary']) || '（无摘录）',
  })),
)

watch(
  () => [props.index, props.runId],
  () => {
    note.value = ''
    error.value = ''
  },
)

async function submit(decision: 'confirmed' | 'problem') {
  if (!row.value) return
  busy.value = true
  error.value = ''
  const response = await reviewCase(props.runId, row.value.item_id, decision, note.value.trim())
  busy.value = false
  if (!response.success) {
    error.value = response.error || '提交核对失败'
    return
  }
  note.value = ''
  emit('reviewed')
}
</script>

<style scoped>
.rv-review {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.rv-muted {
  color: var(--mq-text-tertiary);
  font-size: var(--mq-font-12);
}

.rv-tag {
  display: inline-flex;
  align-items: center;
  height: 22px;
  padding: 0 8px;
  border-radius: var(--mq-radius-tag);
  background: var(--mq-neutral-bg);
  color: var(--mq-neutral-text);
  font-size: var(--mq-font-12);
}

.rv-review__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  padding: 22px 28px 16px;
  border-bottom: 0.5px solid var(--mq-bg-muted);
}

.rv-review__title {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.rv-review__title h2 {
  margin: 0;
  font-size: var(--mq-font-20);
}

.rv-review__tags,
.rv-review__nav,
.rv-review__actions {
  display: flex;
  gap: 8px;
}

.rv-icon-btn {
  width: 36px;
  padding: 0;
  font-size: 18px;
}

.rv-review__body {
  display: flex;
  flex: 1 1 auto;
  flex-direction: column;
  gap: 18px;
  padding: 20px 28px;
  overflow-y: auto;
}

.rv-review__body h3 {
  margin: 0 0 10px;
  font-size: var(--mq-font-16);
  font-weight: 600;
}

.rv-review__pair {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.rv-review__side {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 8px;
  padding: 14px 16px;
}

.rv-review__side.is-different {
  border-color: var(--mq-danger-border);
}

.rv-review__side p,
.rv-review__quote p,
.rv-review__text {
  margin: 0;
  color: var(--mq-text-secondary);
  font-size: var(--mq-font-13);
  line-height: 1.7;
  white-space: pre-line;
}

.rv-review__text {
  padding: 12px 16px;
}

.rv-review__list {
  margin: 0;
  padding: 12px 16px 12px 32px;
  font-size: var(--mq-font-13);
  line-height: 1.7;
}

.rv-review__evidence {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.rv-review__quote {
  padding: 14px 16px;
}

.rv-review__quote-head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 6px;
  font-size: var(--mq-font-13);
}

.rv-review__history {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin: 0;
  padding: 0;
  list-style: none;
  font-size: var(--mq-font-13);
}

.rv-review__history li {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
}

.rv-review__foot {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 16px 28px 22px;
  border-top: 0.5px solid var(--mq-bg-muted);
}

.rv-review__actions > * {
  flex: 1 1 0;
}
</style>
