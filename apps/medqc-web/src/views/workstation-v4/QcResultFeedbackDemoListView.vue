<template>
  <main class="feedback-demo-page">
    <header class="feedback-demo-head">
      <div>
        <p class="feedback-demo-eyebrow">
          演示功能
        </p>
        <h1>质控反馈记录</h1>
        <p>汇总演示账号已提交的质控结果反馈；不会修改原质控结论。</p>
      </div>
      <button
        type="button"
        class="feedback-demo-refresh"
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
      <section class="feedback-demo-metrics">
        <article>
          <span>全部反馈</span>
          <strong>{{ feedbacks.length }}</strong>
        </article>
        <article class="is-success">
          <span>结果准确</span>
          <strong>{{ correctCount }}</strong>
        </article>
        <article class="is-danger">
          <span>结果有误</span>
          <strong>{{ incorrectCount }}</strong>
        </article>
        <article class="is-warning">
          <span>补充说明</span>
          <strong>{{ noteCount }}</strong>
        </article>
      </section>

      <section class="feedback-demo-list">
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
.feedback-demo-page {
  min-height: 100%;
  padding: 28px;
  background: #f5f5f7;
  color: #1d1d1f;
}
.feedback-demo-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 20px;
  margin-bottom: 18px;
}
.feedback-demo-eyebrow {
  margin: 0 0 4px;
  color: #2b6cf6;
  font-size: 12px;
  font-weight: 650;
}
.feedback-demo-head h1 {
  margin: 0;
  font-size: 28px;
  line-height: 34px;
}
.feedback-demo-head p:not(.feedback-demo-eyebrow) {
  margin: 6px 0 0;
  color: rgba(29, 29, 31, 0.58);
  font-size: 14px;
}
.feedback-demo-refresh {
  min-height: 34px;
  padding: 0 13px;
  border: 1px solid rgba(43, 108, 246, 0.2);
  border-radius: 8px;
  background: #fff;
  color: #2b6cf6;
  cursor: pointer;
  font-size: 13px;
  font-weight: 650;
}
.feedback-demo-refresh:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}
.feedback-demo-metrics {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  overflow: hidden;
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.88);
}
.feedback-demo-metrics article {
  display: grid;
  gap: 7px;
  min-height: 96px;
  padding: 18px 20px;
  border-right: 1px solid rgba(0, 0, 0, 0.08);
}
.feedback-demo-metrics article:last-child {
  border-right: 0;
}
.feedback-demo-metrics span {
  color: rgba(29, 29, 31, 0.58);
  font-size: 13px;
  font-weight: 600;
}
.feedback-demo-metrics strong {
  color: #2b6cf6;
  font-size: 28px;
  line-height: 32px;
}
.feedback-demo-metrics .is-success strong {
  color: #087443;
}
.feedback-demo-metrics .is-danger strong {
  color: #c24136;
}
.feedback-demo-metrics .is-warning strong {
  color: #9a6700;
}
.feedback-demo-list,
.feedback-demo-state {
  margin-top: 18px;
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.9);
}
.feedback-demo-state {
  padding: 36px;
  color: rgba(29, 29, 31, 0.58);
  text-align: center;
}
.feedback-demo-error {
  margin: 0;
  padding: 16px 18px;
  color: #b42318;
}
.feedback-demo-table-wrap {
  overflow: auto;
}
.feedback-demo-table-wrap table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}
.feedback-demo-table-wrap th {
  padding: 12px 16px;
  color: rgba(29, 29, 31, 0.52);
  font-size: 12px;
  font-weight: 650;
  text-align: left;
  white-space: nowrap;
}
.feedback-demo-table-wrap td {
  padding: 15px 16px;
  border-top: 1px solid rgba(0, 0, 0, 0.07);
  color: rgba(29, 29, 31, 0.8);
  vertical-align: top;
}
.feedback-demo-table-wrap tr:hover td {
  background: rgba(43, 108, 246, 0.025);
}
.feedback-demo-table-wrap code {
  color: #174f83;
  font-family: 'SFMono-Regular', Consolas, monospace;
  font-size: 12px;
}
.feedback-record,
.feedback-rule {
  min-width: 190px;
}
.feedback-record strong,
.feedback-rule strong {
  display: block;
  color: #1d1d1f;
  font-size: 13px;
  font-weight: 650;
  line-height: 20px;
}
.feedback-record span,
.feedback-rule code {
  display: block;
  margin-top: 3px;
}
.feedback-record span {
  color: rgba(29, 29, 31, 0.48);
  font-size: 12px;
  line-height: 18px;
}
.feedback-department {
  min-width: 138px;
  color: rgba(29, 29, 31, 0.66) !important;
}
.status-label,
.feedback-type {
  display: inline-flex;
  padding: 3px 7px;
  border-radius: 999px;
  background: rgba(0, 0, 0, 0.05);
  color: rgba(29, 29, 31, 0.7);
  font-size: 12px;
  font-weight: 650;
  white-space: nowrap;
}
.feedback-type.is-correct {
  background: rgba(16, 185, 129, 0.1);
  color: #087443;
}
.feedback-type.is-incorrect {
  background: rgba(239, 68, 68, 0.09);
  color: #c24136;
}
.feedback-type.is-note {
  background: rgba(245, 158, 11, 0.12);
  color: #9a6700;
}
.feedback-comment {
  min-width: 280px;
  white-space: pre-wrap;
  word-break: break-word;
}
@media (max-width: 800px) {
  .feedback-demo-page {
    padding: 18px;
  }
  .feedback-demo-head {
    align-items: stretch;
    flex-direction: column;
  }
  .feedback-demo-metrics {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .feedback-demo-metrics article:nth-child(2) {
    border-right: 0;
  }
  .feedback-demo-metrics article:nth-child(-n + 2) {
    border-bottom: 1px solid rgba(0, 0, 0, 0.08);
  }
}
</style>
