<template>
  <section
    v-if="!forbidden"
    class="case-manual-defects"
    data-testid="case-manual-defects"
    aria-label="本病例人工缺陷"
  >
    <header class="case-manual-defects__header">
      <strong>人工缺陷</strong>
      <span
        v-if="loaded"
        class="case-manual-defects__count"
        data-testid="case-manual-defects-total"
      >共 {{ total }} 条</span>
    </header>

    <p
      v-if="loading"
      class="case-manual-defects__hint"
      role="status"
    >
      正在读取本病例人工缺陷…
    </p>
    <div
      v-else-if="loadError"
      class="case-manual-defects__error"
      role="alert"
      data-testid="case-manual-defects-error"
    >
      <span>{{ loadError }}</span>
      <button
        type="button"
        class="case-manual-defects__retry"
        data-testid="case-manual-defects-retry"
        @click="load"
      >
        重试
      </button>
    </div>
    <template v-else-if="loaded">
      <p
        v-if="!items.length"
        class="case-manual-defects__hint"
      >
        本病例暂无人工缺陷
      </p>
      <p
        v-if="truncated"
        class="case-manual-defects__hint is-warning"
        data-testid="case-manual-defects-truncated"
      >
        仅显示最近 {{ items.length }} 条，共 {{ total }} 条
      </p>
      <ul
        v-if="items.length"
        class="case-manual-defects__list"
      >
        <li
          v-for="item in items"
          :key="item.id"
          class="case-manual-defects__item"
          data-testid="case-manual-defect-item"
        >
          <div class="case-manual-defects__item-heading">
            <strong>{{ item.rule_name || item.rule_code || '未命名问题' }}</strong>
            <span
              class="case-manual-defects__status"
              :class="`is-${statusTone(item.manual_review_status)}`"
              data-testid="case-manual-defect-status"
            >{{ statusLabel(item.manual_review_status) }}</span>
          </div>
          <p class="case-manual-defects__desc">
            {{ known(item.description) }}
          </p>
          <p class="case-manual-defects__meta">
            <span>规则 {{ known(item.rule_code) }}</span>
            <span v-if="item.location">位置 {{ item.location }}</span>
            <span>第 {{ item.run_number ?? '未知' }} 次运行</span>
            <span>{{ known(item.manual_created_by) }} · {{ formatTime(item.created_at) }}</span>
          </p>
        </li>
      </ul>
    </template>
  </section>
</template>

<script setup lang="ts">
/**
 * 病历结果抽屉内的本病例人工缺陷只读分区。
 * 身份为 institute_id/patient_id/visit_id 三坐标；审核动作仍归人工缺陷审核页，本组件不改状态。
 * 无权限（403）时整块不渲染；读取失败显示可重试，不伪造“0 条”；三坐标切换丢弃迟到响应。
 */
import { computed, ref, watch } from 'vue'
import { getCaseManualDefects } from '@/api/manualDefectReviews'
import type { CaseManualDefectList, ManualDefectReviewItem } from '@/api/manualDefectReviews'

const props = defineProps<{
  instituteId: string
  patientId: string
  visitId: string
}>()

const emit = defineEmits<{
  forbidden: []
}>()

const loading = ref(false)
const loaded = ref(false)
const forbidden = ref(false)
const loadError = ref('')
const items = ref<ManualDefectReviewItem[]>([])
const total = ref(0)
let requestSequence = 0

const truncated = computed(() => loaded.value && total.value > items.value.length)

function isOwnedList(data: CaseManualDefectList | undefined): data is CaseManualDefectList {
  if (!data || !Array.isArray(data.items)) return false
  if (typeof data.total !== 'number' || !Number.isFinite(data.total) || data.total < data.items.length) {
    return false
  }
  // 条目三坐标必须与当前病例一致，避免跨病例展示。
  return data.items.every(
    (item) =>
      item.institute_id === props.instituteId &&
      item.patient_id === props.patientId &&
      item.visit_id === props.visitId,
  )
}

async function load() {
  const sequence = ++requestSequence
  loading.value = true
  loaded.value = false
  loadError.value = ''
  items.value = []
  total.value = 0
  try {
    const response = await getCaseManualDefects({
      institute_id: props.instituteId,
      patient_id: props.patientId,
      visit_id: props.visitId,
    })
    if (sequence !== requestSequence) return
    if (response.status === 403) {
      forbidden.value = true
      emit('forbidden')
      return
    }
    if (!response.success) {
      loadError.value = response.message || '读取本病例人工缺陷失败'
      return
    }
    if (!isOwnedList(response.data)) {
      loadError.value = '人工缺陷数据与当前病例不一致，已停止展示'
      return
    }
    items.value = response.data.items
    total.value = response.data.total
    loaded.value = true
  } catch {
    if (sequence === requestSequence) loadError.value = '读取本病例人工缺陷失败'
  } finally {
    if (sequence === requestSequence) loading.value = false
  }
}

function known(value: string | null | undefined) {
  return value && String(value).trim() ? value : '未知'
}

function formatTime(value: string | null | undefined) {
  if (!value) return '时间未知'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? '时间未知' : date.toLocaleString('zh-CN', { hour12: false })
}

const STATUS_LABELS: Record<string, string> = {
  pending: '待审核',
  approved: '已通过',
  rejected: '已驳回',
}

function statusLabel(value: unknown) {
  return STATUS_LABELS[String(value)] ?? '未知'
}

function statusTone(value: unknown) {
  return typeof value === 'string' && value in STATUS_LABELS ? value : 'unknown'
}

watch(
  () => [props.instituteId, props.patientId, props.visitId],
  () => {
    forbidden.value = false
    void load()
  },
  { immediate: true },
)
</script>

<style scoped>
.case-manual-defects {
  margin-top: 12px;
  padding: 12px 14px;
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 10px;
  background: #fff;
}

.case-manual-defects__header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 8px;
  color: #1d1d1f;
  font-size: 14px;
}

.case-manual-defects__count {
  color: rgba(29, 29, 31, 0.58);
  font-size: 12px;
}

.case-manual-defects__hint {
  margin: 4px 0;
  color: rgba(29, 29, 31, 0.58);
  font-size: 13px;
}

.case-manual-defects__hint.is-warning {
  color: #ad6800;
}

.case-manual-defects__error {
  display: flex;
  align-items: center;
  gap: 10px;
  color: #cf1322;
  font-size: 13px;
}

.case-manual-defects__retry {
  padding: 2px 10px;
  border: 1px solid rgba(43, 108, 246, 0.3);
  border-radius: 6px;
  background: #f7fbff;
  color: #2b6cf6;
  cursor: pointer;
}

.case-manual-defects__list {
  display: grid;
  gap: 8px;
  max-height: 320px;
  margin: 0;
  padding: 0;
  overflow-y: auto;
  list-style: none;
}

.case-manual-defects__item {
  padding: 8px 10px;
  border: 1px solid rgba(0, 0, 0, 0.06);
  border-radius: 8px;
  background: #fafcff;
}

.case-manual-defects__item-heading {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
}

.case-manual-defects__status {
  flex: none;
  padding: 0 8px;
  border-radius: 6px;
  font-size: 12px;
  line-height: 20px;
}

.case-manual-defects__status.is-pending {
  background: #e6f4ff;
  color: #0958d9;
}

.case-manual-defects__status.is-approved {
  background: #f6ffed;
  color: #389e0d;
}

.case-manual-defects__status.is-rejected {
  background: #fff1f0;
  color: #cf1322;
}

.case-manual-defects__status.is-unknown {
  background: #f5f5f5;
  color: rgba(29, 29, 31, 0.58);
}

.case-manual-defects__desc {
  margin: 4px 0;
  color: rgba(29, 29, 31, 0.8);
  font-size: 13px;
}

.case-manual-defects__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 14px;
  margin: 0;
  color: rgba(29, 29, 31, 0.5);
  font-size: 12px;
}
</style>
