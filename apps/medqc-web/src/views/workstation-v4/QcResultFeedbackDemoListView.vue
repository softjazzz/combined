<template>
  <main class="feedback-demo-page mq-page">
    <header class="feedback-demo-head mq-page-head">
      <div class="mq-page-head__copy">
        <span class="mq-page-eyebrow">质控作业 · 演示功能</span>
        <h1 class="mq-page-title">
          质控反馈记录
        </h1>
        <p class="feedback-demo-desc">
          汇总演示账号已提交的质控结果反馈；不会修改原质控结论。
        </p>
      </div>
      <button
        type="button"
        class="feedback-demo-refresh mq-btn"
        :disabled="loading"
        @click="load"
      >
        {{ loading ? '正在刷新…' : '刷新记录' }}
      </button>
    </header>

    <section
      v-if="!isDemoAccount"
      class="feedback-demo-state"
    >
      此页面仅对演示账号开放。
    </section>
    <template v-else>
      <section class="feedback-demo-metrics mq-card">
        <article>
          <MqIconTile
            name="doc"
            tone="brand"
            :size="38"
            :icon-size="22"
          />
          <span>全部反馈</span>
          <strong>{{ feedbacks.length }}</strong>
        </article>
        <article class="is-success">
          <MqIconTile
            name="success"
            tone="success"
            :size="38"
            :icon-size="22"
          />
          <span>结果准确</span>
          <strong>{{ correctCount }}</strong>
        </article>
        <article class="is-danger">
          <MqIconTile
            name="issue"
            tone="danger"
            :size="38"
            :icon-size="22"
          />
          <span>结果有误</span>
          <strong>{{ incorrectCount }}</strong>
        </article>
        <article class="is-warning">
          <MqIconTile
            name="data_gap"
            tone="warning"
            :size="38"
            :icon-size="22"
          />
          <span>补充说明</span>
          <strong>{{ noteCount }}</strong>
        </article>
      </section>

      <section class="feedback-demo-list mq-card">
        <p
          v-if="error"
          class="feedback-demo-error"
        >
          {{ error }}
        </p>
        <p
          v-else-if="loading"
          class="feedback-demo-state"
        >
          正在读取反馈记录…
        </p>
        <p
          v-else-if="!feedbacks.length"
          class="feedback-demo-state"
        >
          暂无已提交的反馈。请在病历质控结果中展开任一质控点后提交反馈。
        </p>
        <div
          v-else
          class="feedback-demo-table-wrap"
        >
          <table>
            <thead>
              <tr>
                <th>病历</th>
                <th>科室</th>
                <th>质控点</th>
                <th>原结果</th>
                <th>反馈</th>
                <th>说明</th>
                <th>提交时间</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="feedback in feedbacks"
                :key="
                  feedback.id ||
                    `${feedback.root_job_id}-${feedback.record_ref}-${feedback.rule_id}`
                "
              >
                <td class="feedback-record">
                  <strong>{{ feedback.patient_name || '患者信息待补' }}</strong>
                  <span>{{ feedback.record_number || feedback.visit_id || '病历号待补' }}</span>
                </td>
                <td class="feedback-department">
                  {{ feedback.department || '—' }}
                </td>
                <td class="feedback-rule">
                  <strong>{{ feedback.rule_name || '质控点名称待补' }}</strong>
                  <code>{{ feedback.rule_id }}</code>
                </td>
                <td>
                  <span class="status-label">{{ statusLabel(feedback.original_status) }}</span>
                </td>
                <td>
                  <span :class="['feedback-type', `is-${feedback.feedback_type}`]">{{
                    feedbackTypeLabel(feedback.feedback_type)
                  }}</span>
                </td>
                <td class="feedback-comment">
                  {{ feedback.comment || '—' }}
                </td>
                <td>{{ formatBeijingTime(feedback.updated_at || feedback.created_at) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </template>
  </main>
</template>

<script setup lang="ts">
import MqIconTile from '@/components/icons/MqIconTile.vue'
import { computed, onMounted, ref } from 'vue'
import { useAuthStore } from '@/stores/auth'
import {
  listQcResultFeedbackDemo,
  type QcResultFeedbackRecord,
  type QcResultFeedbackType,
} from '@/api/qc-result-feedback-demo'

const authStore = useAuthStore()
const feedbacks = ref<QcResultFeedbackRecord[]>([])
const loading = ref(false)
const error = ref('')

const isDemoAccount = computed(
  () =>
    authStore.user?.is_demo_account === true &&
    String(authStore.user?.id || '').trim() === 'admin-001' &&
    String(authStore.user?.email || '')
      .trim()
      .toLowerCase() === 'admin@medqc.com',
)
const correctCount = computed(
  () => feedbacks.value.filter((item) => item.feedback_type === 'correct').length,
)
const incorrectCount = computed(
  () => feedbacks.value.filter((item) => item.feedback_type === 'incorrect').length,
)
const noteCount = computed(
  () => feedbacks.value.filter((item) => item.feedback_type === 'note').length,
)

function feedbackTypeLabel(type: QcResultFeedbackType) {
  return type === 'correct' ? '结果准确' : type === 'incorrect' ? '结果有误' : '补充说明'
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

function formatBeijingTime(value?: string) {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '—'
  return new Intl.DateTimeFormat('zh-CN', {
    timeZone: 'Asia/Shanghai',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hourCycle: 'h23',
  })
    .format(date)
    .replace(/\//gu, '-')
}

async function load() {
  if (!isDemoAccount.value) return
  loading.value = true
  error.value = ''
  const result = await listQcResultFeedbackDemo()
  loading.value = false
  if (!result.success || !result.data) {
    error.value = result.message || '反馈记录暂时无法读取，请稍后重试。'
    return
  }
  feedbacks.value = result.data
}

onMounted(() => {
  void load()
})
</script>

<style scoped>
/* v7.1：页头、玻璃卡、按钮来自 mq-components.css */
.feedback-demo-desc {
  margin: 2px 0 0;
  color: var(--mq-text-tertiary);
  font-size: var(--mq-font-13);
}

.feedback-demo-refresh:disabled {
  opacity: 0.55;
  cursor: wait;
}

/* 四栏指标：数值为零时保持中性色，不做语义强调 */
.feedback-demo-metrics {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  overflow: hidden;
}

.feedback-demo-metrics article {
  display: grid;
  grid-template-columns: 38px minmax(0, 1fr);
  grid-template-areas:
    'icon label'
    'value value';
  align-items: center;
  gap: 14px 12px;
  padding: 18px 22px;
}

.feedback-demo-metrics article + article {
  border-left: 0.5px solid var(--mq-border);
}

.feedback-demo-metrics article > :first-child {
  grid-area: icon;
}

.feedback-demo-metrics span {
  grid-area: label;
  font-size: var(--mq-font-14);
  font-weight: 600;
}

.feedback-demo-metrics strong {
  grid-area: value;
  color: var(--mq-text-primary);
  font-family: var(--mq-font-display);
  font-size: 40px;
  font-weight: 600;
  letter-spacing: -0.035em;
  line-height: 1;
  font-variant-numeric: tabular-nums;
}

/* 列表 */
.feedback-demo-list {
  overflow: hidden;
}

.feedback-demo-state,
.feedback-demo-error {
  margin: 0;
  padding: 36px 24px;
  color: var(--mq-text-tertiary);
  font-size: var(--mq-font-13);
  text-align: center;
}

.feedback-demo-error {
  color: var(--mq-danger-text);
}

section.feedback-demo-state {
  border: 1px solid var(--mq-glass-border);
  border-radius: var(--mq-radius-card);
  background: var(--mq-glass-bg);
  box-shadow: var(--mq-glass-shadow);
}

.feedback-demo-table-wrap {
  overflow-x: auto;
}

.feedback-demo-table-wrap table {
  width: 100%;
  border-collapse: collapse;
  font-size: var(--mq-font-13);
}

.feedback-demo-table-wrap th {
  height: 40px;
  padding: 0 18px;
  background: rgba(118, 128, 160, 0.06);
  color: var(--mq-text-tertiary);
  font-size: var(--mq-font-12);
  font-weight: 600;
  text-align: left;
  white-space: nowrap;
}

.feedback-demo-table-wrap td {
  padding: 14px 18px;
  border-top: 0.5px solid var(--mq-border);
  vertical-align: top;
}

.feedback-demo-table-wrap tbody tr:hover td {
  background: rgba(10, 108, 255, 0.04);
}

.feedback-record,
.feedback-rule {
  display: flex;
  flex-direction: column;
  gap: 3px;
  min-width: 180px;
}

.feedback-record strong,
.feedback-rule strong {
  font-weight: 600;
  line-height: 1.5;
}

.feedback-record span {
  color: var(--mq-text-tertiary);
  font-size: var(--mq-font-12);
}

.feedback-rule code {
  color: var(--mq-brand-700);
  font-family: var(--mq-font-mono);
  font-size: var(--mq-font-12);
}

.feedback-department {
  min-width: 140px;
  color: var(--mq-text-secondary);
  white-space: nowrap;
}

.feedback-comment {
  min-width: 200px;
  color: var(--mq-text-secondary);
}

.feedback-demo-table-wrap td:last-child {
  color: var(--mq-text-tertiary);
  white-space: nowrap;
}

.status-label,
.feedback-type {
  display: inline-flex;
  align-items: center;
  padding: 3px 10px;
  border-radius: 999px;
  background: var(--mq-neutral-bg);
  color: var(--mq-text-secondary);
  font-size: var(--mq-font-12);
  font-weight: 600;
  white-space: nowrap;
}

.feedback-type.is-correct {
  background: var(--mq-success-bg);
  color: var(--mq-success-text);
}

.feedback-type.is-incorrect {
  background: var(--mq-danger-bg);
  color: var(--mq-danger-text);
}

.feedback-type.is-note {
  background: var(--mq-warning-bg);
  color: var(--mq-warning-text);
}

@media (max-width: 1100px) {
  .feedback-demo-metrics {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .feedback-demo-metrics article:nth-child(3) {
    border-left: 0;
  }

  .feedback-demo-metrics article:nth-child(n + 3) {
    border-top: 0.5px solid var(--mq-border);
  }
}
</style>
