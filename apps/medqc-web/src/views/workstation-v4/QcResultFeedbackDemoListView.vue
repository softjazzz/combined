<template>
  <section class="feedback-demo-page mq-page" aria-label="质控反馈记录">
    <header class="feedback-demo-head mq-page-head">
      <div>
        <h1 class="mq-page-title">质控反馈记录</h1>
        <p class="feedback-demo-desc">查看已提交的反馈与说明，原质控结论保持不变。</p>
      </div>
      <button type="button" class="mq-btn" :disabled="loading" @click="load">
        {{ loading ? '正在刷新…' : '刷新记录' }}
      </button>
    </header>

    <section v-if="!canViewFeedback" class="feedback-demo-state mq-card">
      当前账号没有反馈记录查看权限。
    </section>
    <template v-else>
      <section class="feedback-demo-filters mq-card" aria-label="反馈筛选">
        <input
          v-model.trim="keyword"
          class="feedback-demo-search mq-input"
          placeholder="搜索病历、科室或质控点"
          aria-label="搜索反馈"
        />
        <div
          class="mq-segmented mq-segmented--sm feedback-demo-types"
          role="tablist"
          aria-label="反馈类型"
        >
          <button
            v-for="option in typeOptions"
            :key="option.value"
            type="button"
            role="tab"
            class="mq-segmented__item"
            :class="{ 'is-active': feedbackType === option.value }"
            :aria-selected="feedbackType === option.value"
            :data-testid="`feedback-filter-${option.value || 'all'}`"
            @click="feedbackType = option.value"
          >
            {{ option.label }} <span class="feedback-demo-type-count">{{ option.count }}</span>
          </button>
        </div>
        <span class="feedback-demo-total">{{ filteredFeedbacks.length }} 条记录</span>
      </section>

      <section class="feedback-demo-list mq-card" aria-label="反馈记录">
        <p v-if="error" class="feedback-demo-state feedback-demo-error" role="alert">{{ error }}</p>
        <p v-else-if="loading" class="feedback-demo-state" role="status">正在读取反馈记录…</p>
        <p v-else-if="!feedbacks.length" class="feedback-demo-state">
          暂无已提交的反馈。请在病历质控结果中展开任一质控点后提交反馈。
        </p>
        <p v-else-if="!filteredFeedbacks.length" class="feedback-demo-state">
          没有符合条件的反馈记录。
        </p>
        <template v-else>
          <section v-for="group in feedbackGroups" :key="group.date" :aria-label="group.date">
            <h2 class="feedback-demo-date">{{ group.date }}</h2>
            <article
              v-for="feedback in group.items"
              :key="feedbackKey(feedback)"
              class="feedback-demo-row"
              data-testid="feedback-row"
            >
              <div class="feedback-demo-main">
                <div class="feedback-demo-title-line">
                  <span class="mq-status" :class="feedbackStatusClass(feedback.feedback_type)">
                    {{ feedbackTypeLabel(feedback.feedback_type) }}
                  </span>
                  <strong
                    class="feedback-demo-title"
                    :title="feedback.rule_name || feedback.rule_id"
                  >
                    {{ feedback.rule_name || feedback.rule_id }}
                  </strong>
                </div>
                <div class="feedback-demo-meta">
                  <span>{{ feedback.patient_name || '患者信息待补' }}</span>
                  <span>病历号 {{ feedback.record_number || feedback.visit_id || '待补' }}</span>
                  <span>{{ feedback.department || '科室待补' }}</span>
                  <code>{{ feedback.rule_id }}</code>
                  <span>原结果：{{ statusLabel(feedback.original_status) }}</span>
                  <span>{{ formatTime(feedback.updated_at || feedback.created_at) }}</span>
                </div>
                <p v-if="feedback.comment" class="feedback-demo-preview">
                  说明：{{ feedback.comment }}
                </p>
              </div>
              <button
                type="button"
                class="mq-btn mq-btn--primary feedback-demo-open"
                :aria-expanded="expandedKeys.has(feedbackKey(feedback))"
                @click="toggleFeedback(feedback)"
              >
                {{ expandedKeys.has(feedbackKey(feedback)) ? '收起详情' : '查看详情' }}
              </button>
              <div v-if="expandedKeys.has(feedbackKey(feedback))" class="feedback-demo-detail">
                <dl>
                  <div class="feedback-demo-full-field">
                    <dt>质控点</dt>
                    <dd>{{ feedback.rule_name || feedback.rule_id }}</dd>
                  </div>
                  <div>
                    <dt>原质控结果</dt>
                    <dd>{{ statusLabel(feedback.original_status) }}</dd>
                  </div>
                  <div>
                    <dt>反馈类型</dt>
                    <dd>{{ feedbackTypeLabel(feedback.feedback_type) }}</dd>
                  </div>
                  <div v-if="feedback.expected_status">
                    <dt>期望结果</dt>
                    <dd>{{ statusLabel(feedback.expected_status) }}</dd>
                  </div>
                  <div v-if="feedback.error_category">
                    <dt>反馈问题</dt>
                    <dd>{{ errorCategoryLabel(feedback.error_category) }}</dd>
                  </div>
                  <div>
                    <dt>提交时间</dt>
                    <dd>{{ formatBeijingTime(feedback.created_at) }}</dd>
                  </div>
                  <div>
                    <dt>更新时间</dt>
                    <dd>{{ formatBeijingTime(feedback.updated_at) }}</dd>
                  </div>
                </dl>
                <div class="feedback-demo-comment">
                  <strong>反馈说明</strong>
                  <p>{{ feedback.comment || '未填写说明。' }}</p>
                </div>
              </div>
            </article>
          </section>
        </template>
      </section>
    </template>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useAuthStore } from '@/stores/auth'
import {
  listQcResultFeedbackDemo,
  type QcResultFeedbackRecord,
  type QcResultFeedbackType,
  type QcResultFeedbackErrorCategory,
} from '@/api/qc-result-feedback-demo'

const authStore = useAuthStore()
const feedbacks = ref<QcResultFeedbackRecord[]>([])
const loading = ref(false)
const error = ref('')
const keyword = ref('')
const feedbackType = ref<'' | QcResultFeedbackType>('')
const expandedKeys = ref(new Set<string>())

const isDemoAccount = computed(
  () =>
    authStore.user?.is_demo_account === true &&
    String(authStore.user?.id || '').trim() === 'admin-001' &&
    String(authStore.user?.email || '')
      .trim()
      .toLowerCase() === 'admin@medqc.com',
)
const canViewFeedback = computed(
  () => isDemoAccount.value || authStore.userRoles?.includes('sync_admin') === true,
)
const typeOptions = computed(() => [
  { value: '' as const, label: '全部反馈', count: feedbacks.value.length },
  ...(['incorrect', 'correct', 'note'] as const).map((value) => ({
    value,
    label: feedbackTypeLabel(value),
    count: feedbacks.value.filter((item) => item.feedback_type === value).length,
  })),
])
const filteredFeedbacks = computed(() => {
  const text = keyword.value.toLocaleLowerCase()
  return feedbacks.value.filter((item) => {
    if (feedbackType.value && item.feedback_type !== feedbackType.value) return false
    return (
      !text ||
      [
        item.patient_name,
        item.record_number,
        item.visit_id,
        item.department,
        item.rule_id,
        item.rule_name,
        item.comment,
      ].some((value) =>
        String(value || '')
          .toLocaleLowerCase()
          .includes(text),
      )
    )
  })
})
const feedbackGroups = computed(() => {
  const groups: Array<{ date: string; items: QcResultFeedbackRecord[] }> = []
  for (const item of filteredFeedbacks.value) {
    const formatted = formatBeijingTime(item.updated_at || item.created_at)
    const date = formatted === '—' ? '时间未返回' : formatted.split(' ')[0]
    let group = groups.find((value) => value.date === date)
    if (!group) {
      group = { date, items: [] }
      groups.push(group)
    }
    group.items.push(item)
  }
  return groups
})

function feedbackKey(feedback: QcResultFeedbackRecord) {
  return feedback.id || `${feedback.root_job_id}-${feedback.record_ref}-${feedback.rule_id}`
}

function toggleFeedback(feedback: QcResultFeedbackRecord) {
  const key = feedbackKey(feedback)
  const next = new Set(expandedKeys.value)
  if (next.has(key)) next.delete(key)
  else next.add(key)
  expandedKeys.value = next
}

function feedbackTypeLabel(type: QcResultFeedbackType) {
  return type === 'correct' ? '结果准确' : type === 'incorrect' ? '结果有误' : '补充说明'
}

function feedbackStatusClass(type: QcResultFeedbackType) {
  return type === 'correct'
    ? 'mq-status--success'
    : type === 'incorrect'
      ? 'mq-status--danger'
      : 'mq-status--warning'
}

function errorCategoryLabel(category: QcResultFeedbackErrorCategory) {
  const labels: Record<QcResultFeedbackErrorCategory, string> = {
    wrong_status: '结论有误',
    wrong_reason: '判定理由有误',
    wrong_evidence: '引用依据有误',
    missing_data_read: '资料漏读',
    wrong_suggestion: '修改建议有误',
    rule_definition: '规则口径问题',
    other: '其他问题',
  }
  return labels[category] || '其他问题'
}

function statusLabel(status: string) {
  const labels: Record<string, string> = {
    non_compliant: '不合规',
    compliant: '合规',
    data_gap: '数据不足',
    not_applicable: '不适用',
    evaluation_unknown: '待确认',
    not_executed: '未执行',
    technical_error: '技术异常',
    uncertain: '资料待核实',
  }
  return labels[status] || '待核实'
}

const dateFormatter = new Intl.DateTimeFormat('zh-CN', {
  timeZone: 'Asia/Shanghai',
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
  hourCycle: 'h23',
})

function formatBeijingTime(value?: string) {
  if (!value) return '—'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? '—' : dateFormatter.format(date).replace(/\//gu, '-')
}

function formatTime(value?: string) {
  const text = formatBeijingTime(value)
  return text === '—' ? '时间未返回' : `${text.split(' ')[1]} 更新`
}

async function load() {
  if (!canViewFeedback.value) return
  loading.value = true
  error.value = ''
  try {
    const result = await listQcResultFeedbackDemo()
    if (!result.success || !result.data) {
      const rawMessage = String(result.message || '').trim()
      error.value =
        rawMessage === 'clinical_source_disabled'
          ? '当前临床数据源已停用，请在系统配置中启用临床数据源后重试。'
          : rawMessage || '反馈记录暂时无法读取，请稍后重试。'
      return
    }
    feedbacks.value = result.data
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  void load()
})
</script>

<style scoped>
/* 沿用质控记录的两列信息布局与日期分组，不把反馈说明挤进窄表格。 */
.feedback-demo-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: var(--mq-space-5);
}
.feedback-demo-desc {
  margin: 4px 0 0;
  color: var(--mq-text-tertiary);
  font-size: var(--mq-font-13);
}
.feedback-demo-filters {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--mq-space-3);
  padding: 12px 16px;
}
.feedback-demo-search {
  flex: 1 1 240px;
  min-width: 0;
}
.feedback-demo-types {
  flex-wrap: wrap;
}
.feedback-demo-type-count {
  margin-left: 4px;
  font-variant-numeric: tabular-nums;
}
.feedback-demo-total {
  margin-left: auto;
  color: var(--mq-text-tertiary);
  font-size: var(--mq-font-12);
  white-space: nowrap;
}
.feedback-demo-list {
  overflow: hidden;
}
.feedback-demo-date {
  margin: 0;
  padding: 8px 20px;
  background: var(--mq-bg-subtle);
  color: var(--mq-text-tertiary);
  font-size: var(--mq-font-12);
  font-weight: 600;
}
.feedback-demo-list > section + section {
  border-top: 1px solid var(--mq-border);
}
.feedback-demo-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 88px;
  align-items: center;
  gap: 8px 24px;
  padding: 12px 20px;
  border-top: 1px solid var(--mq-border);
}
.feedback-demo-row:hover {
  background: var(--mq-glass-bg-strong);
}
.feedback-demo-main {
  display: grid;
  gap: 4px;
  min-width: 0;
}
.feedback-demo-title-line {
  display: grid;
  grid-template-columns: 96px minmax(0, 1fr);
  align-items: center;
  gap: var(--mq-space-2);
}
.feedback-demo-title-line .mq-status {
  justify-self: start;
}
.feedback-demo-title {
  overflow: hidden;
  color: var(--mq-text-primary);
  font-size: var(--mq-font-14);
  text-overflow: ellipsis;
  white-space: nowrap;
}
.feedback-demo-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 2px 12px;
  color: var(--mq-text-tertiary);
  font-size: var(--mq-font-12);
  line-height: 20px;
}
.feedback-demo-meta code {
  font-size: inherit;
}
.feedback-demo-preview {
  overflow: hidden;
  margin: 0;
  color: var(--mq-text-secondary);
  font-size: var(--mq-font-13);
  line-height: 20px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.feedback-demo-open {
  width: 88px;
  min-height: 32px;
  padding: 6px 12px;
  font-size: var(--mq-font-13);
}
.feedback-demo-detail {
  grid-column: 1 / -1;
  padding-top: 12px;
  border-top: 1px solid var(--mq-border);
}
.feedback-demo-detail dl {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px 24px;
  margin: 0;
}
.feedback-demo-detail dl > div {
  display: grid;
  grid-template-columns: 88px minmax(0, 1fr);
  gap: 12px;
  font-size: var(--mq-font-13);
}
.feedback-demo-detail dt {
  color: var(--mq-text-tertiary);
}
.feedback-demo-full-field {
  grid-column: 1 / -1;
}
.feedback-demo-detail dd {
  min-width: 0;
  margin: 0;
  color: var(--mq-text-primary);
  overflow-wrap: anywhere;
}
.feedback-demo-comment {
  margin-top: 16px;
  font-size: var(--mq-font-13);
}
.feedback-demo-comment strong {
  font-weight: 500;
  color: var(--mq-text-tertiary);
}
.feedback-demo-comment p {
  margin: 8px 0 0;
  color: var(--mq-text-primary);
  line-height: 1.7;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
.feedback-demo-state {
  margin: 0;
  padding: 32px 20px;
  color: var(--mq-text-tertiary);
  font-size: var(--mq-font-13);
  text-align: center;
}
.feedback-demo-error {
  color: var(--mq-danger-text);
}
@media (max-width: 900px) {
  .feedback-demo-row {
    grid-template-columns: minmax(0, 1fr) 88px;
    gap: 8px 12px;
    padding: 12px 16px;
  }
  .feedback-demo-meta {
    gap: 2px 8px;
  }
  .feedback-demo-detail dl {
    grid-template-columns: minmax(0, 1fr);
  }
}
@media (max-width: 560px) {
  .feedback-demo-head {
    align-items: flex-start;
    flex-wrap: wrap;
  }
  .feedback-demo-row {
    grid-template-columns: minmax(0, 1fr);
  }
  .feedback-demo-open {
    justify-self: end;
  }
}
</style>
