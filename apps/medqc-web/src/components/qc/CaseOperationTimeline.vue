<template>
  <section
    v-if="!forbidden"
    class="case-operations"
    data-testid="case-operations"
    aria-label="本病例操作记录"
  >
    <header class="case-operations__header">
      <strong>操作记录</strong>
      <span
        v-if="loaded"
        class="case-operations__count"
        data-testid="case-operations-total"
      >共 {{ total }} 条</span>
    </header>

    <p
      v-if="loading"
      class="case-operations__hint"
      role="status"
    >
      正在读取本病例操作记录…
    </p>
    <div
      v-else-if="loadError"
      class="case-operations__error"
      role="alert"
      data-testid="case-operations-error"
    >
      <span>{{ loadError }}</span>
      <button
        type="button"
        class="case-operations__retry"
        data-testid="case-operations-retry"
        @click="load"
      >
        重试
      </button>
    </div>
    <template v-else-if="loaded">
      <p
        v-if="!items.length"
        class="case-operations__hint"
        data-testid="case-operations-empty"
      >
        本病例暂无操作记录
      </p>
      <p
        v-if="truncated"
        class="case-operations__hint is-warning"
        data-testid="case-operations-truncated"
      >
        仅显示最近 {{ items.length }} 条，共 {{ total }} 条
      </p>
      <ol
        v-if="items.length"
        class="case-operations__list"
      >
        <li
          v-for="item in items"
          :key="item.id"
          class="case-operations__item"
          data-testid="case-operation-item"
        >
          <div class="case-operations__item-heading">
            <span
              class="case-operations__type"
              data-testid="case-operation-type"
            >{{ typeLabel(item) }}</span>
            <span
              class="case-operations__actor"
              data-testid="case-operation-actor"
            >{{ actorLabel(item) }}</span>
            <time
              class="case-operations__time"
              data-testid="case-operation-time"
            >{{ formatTime(item.occurred_at) }}</time>
          </div>
          <p
            v-if="summaryParts(item).length"
            class="case-operations__summary"
            data-testid="case-operation-summary"
          >
            <span
              v-for="part in summaryParts(item)"
              :key="part"
            >{{ part }}</span>
          </p>
        </li>
      </ol>
    </template>
  </section>
</template>

<script setup lang="ts">
/**
 * 病历结果抽屉内的本病例操作记录时间线（只读）。
 * 身份为 institute_id/patient_id/visit_id 三坐标；每条事件的事实由来源 owner 负责，本组件只搬运展示。
 * 无权限（403）时整块不渲染；读取失败显示可重试，不显示为“无记录”；三坐标切换丢弃迟到响应。
 */
import { computed, ref, watch } from 'vue'
import { getCaseOperations, isKnownCaseOperation } from '@/api/recordOperations'
import type { CaseOperation, CaseOperationList } from '@/api/recordOperations'

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
const items = ref<CaseOperation[]>([])
const total = ref(0)
let requestSequence = 0

const truncated = computed(() => loaded.value && total.value > items.value.length)

/** 若对象回显了三坐标字段，必须与当前病例一致；未回显的字段不做假设。 */
function echoedIdentityMatches(value: unknown) {
  if (typeof value !== 'object' || value === null) return true
  const record = value as Record<string, unknown>
  const expected: Record<string, string> = {
    institute_id: props.instituteId,
    patient_id: props.patientId,
    visit_id: props.visitId,
  }
  return Object.entries(expected).every(
    ([key, want]) => record[key] === undefined || record[key] === want,
  )
}

function isOwnedList(data: CaseOperationList | undefined): data is CaseOperationList {
  if (!data || !Array.isArray(data.items)) return false
  if (typeof data.total !== 'number' || !Number.isFinite(data.total) || data.total < data.items.length) {
    return false
  }
  if (!echoedIdentityMatches(data)) return false
  return data.items.every(
    (item) =>
      typeof item === 'object' &&
      item !== null &&
      typeof item.id === 'string' &&
      typeof item.type === 'string' &&
      echoedIdentityMatches(item),
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
    const response = await getCaseOperations({
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
      loadError.value = response.message || '读取本病例操作记录失败'
      return
    }
    if (!isOwnedList(response.data)) {
      loadError.value = '操作记录数据与当前病例不一致，已停止展示'
      return
    }
    items.value = response.data.items
    total.value = response.data.total
    loaded.value = true
  } catch {
    if (sequence === requestSequence) loadError.value = '读取本病例操作记录失败'
  } finally {
    if (sequence === requestSequence) loading.value = false
  }
}

const TYPE_LABELS: Record<string, string> = {
  qc_run_completed: '质控运行完成',
  record_review: '病历审核',
  manual_defect_created: '人工缺陷创建',
  manual_defect_reviewed: '人工缺陷审核',
  task_record_completed: '完成任务病历',
  rectification_assigned: '派发整改',
  rectification_submitted: '提交整改',
  rectification_approved: '验收整改',
  rectification_rejected: '驳回整改',
  rectification_urged: '催办整改',
}
const STAGE_LABELS: Record<string, string> = { initial: '初审', recheck: '复审' }
const REVIEW_DECISION_LABELS: Record<string, string> = { approved: '通过', doubtful: '存疑' }
const DEFECT_DECISION_LABELS: Record<string, string> = { approved: '通过', rejected: '驳回' }
const CONTEXT_LABELS: Record<string, string> = { task: '任务', workspace: '病历列表' }
const RECTIFICATION_STATUS_LABELS: Record<string, string> = {
  pending: '待整改', submitted: '待验收', approved: '已验收', rejected: '已驳回',
}
const SCENE_LABELS: Record<string, string> = { running: '运行', final: '终末', outpatient_emergency: '门急诊' }

function typeLabel(item: CaseOperation) {
  return TYPE_LABELS[item.type] ?? '未知操作'
}

function actorLabel(item: CaseOperation) {
  const name = item.actor_name?.trim()
  if (name) return name
  const id = item.actor_id?.trim()
  return id || '操作人未知'
}

function text(value: unknown) {
  return typeof value === 'string' && value.trim() ? value.trim() : ''
}

function isCount(value: unknown): value is number {
  return typeof value === 'number' && Number.isInteger(value) && value >= 0
}

/** 已提供的枚举值按映射显示，映射外的值显示“未知”；字段缺失则不显示该项。 */
function enumPart(prefix: string, value: unknown, labels: Record<string, string>) {
  if (value === null || value === undefined || value === '') return ''
  return `${prefix} ${labels[String(value)] ?? '未知'}`
}

function summaryParts(item: CaseOperation): string[] {
  if (!isKnownCaseOperation(item) || typeof item.summary !== 'object' || item.summary === null) return []
  const parts: string[] = []
  const push = (value: string) => {
    if (value) parts.push(value)
  }
  switch (item.type) {
    case 'qc_run_completed': {
      const s = item.summary
      if (isCount(s.result_count)) push(`结果 ${s.result_count} 条`)
      if (text(s.task_id)) push(`任务 ${text(s.task_id)}`)
      if (isCount(s.task_run_number)) push(`第 ${s.task_run_number} 次运行`)
      if (text(s.rule_set_version)) push(`规则集 ${text(s.rule_set_version)}`)
      if (text(s.job_id)) push(`运行 ${text(s.job_id)}`)
      break
    }
    case 'record_review': {
      const s = item.summary
      push(enumPart('阶段', s.stage, STAGE_LABELS))
      push(enumPart('结论', s.decision, REVIEW_DECISION_LABELS))
      if (text(s.reason)) push(`原因 ${text(s.reason)}`)
      push(enumPart('来源', s.review_context, CONTEXT_LABELS))
      if (text(s.task_id)) push(`任务 ${text(s.task_id)}`)
      break
    }
    case 'manual_defect_created': {
      const s = item.summary
      push(text(s.rule_name) ? `规则 ${text(s.rule_name)}` : '')
      if (text(s.task_id)) push(`任务 ${text(s.task_id)}`)
      if (isCount(s.run_number)) push(`第 ${s.run_number} 次运行`)
      break
    }
    case 'manual_defect_reviewed': {
      const s = item.summary
      push(enumPart('结论', s.decision, DEFECT_DECISION_LABELS))
      if (text(s.reason)) push(`原因 ${text(s.reason)}`)
      break
    }
    case 'task_record_completed': {
      const s = item.summary
      if (text(s.task_id)) push(`任务 ${text(s.task_id)}`)
      if (isCount(s.completed_run_number)) push(`完成第 ${s.completed_run_number} 次运行`)
      break
    }
    case 'rectification_assigned':
    case 'rectification_submitted':
    case 'rectification_approved':
    case 'rectification_rejected':
    case 'rectification_urged': {
      const s = item.summary
      if (text(s.target_id)) push(`缺陷 ${text(s.target_id)}`)
      push(enumPart('场景', s.scene, SCENE_LABELS))
      push(enumPart('事件后状态', s.new_status, RECTIFICATION_STATUS_LABELS))
      if (text(s.comment)) push(`说明 ${text(s.comment)}`)
      if (text(s.root_job_id)) push(`运行 ${text(s.root_job_id)}`)
      if (text(s.envelope_id)) push(`结果 ${text(s.envelope_id)}`)
      if (text(s.rule_set_version)) push(`规则集 ${text(s.rule_set_version)}`)
      if (isCount(s.version)) push(`整改版本 ${s.version}`)
      break
    }
  }
  return parts
}

function formatTime(value: string | null | undefined) {
  if (!value) return '时间未知'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? '时间未知' : date.toLocaleString('zh-CN', { hour12: false })
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
.case-operations {
  margin-top: 12px;
  padding: 12px 14px;
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 10px;
  background: #fff;
}

.case-operations__header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 8px;
  color: #1d1d1f;
  font-size: 14px;
}

.case-operations__count {
  color: rgba(29, 29, 31, 0.58);
  font-size: 12px;
}

.case-operations__hint {
  margin: 4px 0;
  color: rgba(29, 29, 31, 0.58);
  font-size: 13px;
}

.case-operations__hint.is-warning {
  color: #ad6800;
}

.case-operations__error {
  display: flex;
  align-items: center;
  gap: 10px;
  color: #cf1322;
  font-size: 13px;
}

.case-operations__retry {
  padding: 2px 10px;
  border: 1px solid rgba(43, 108, 246, 0.3);
  border-radius: 6px;
  background: #f7fbff;
  color: #2b6cf6;
  cursor: pointer;
}

.case-operations__list {
  display: grid;
  gap: 6px;
  max-height: 320px;
  margin: 0;
  padding: 0 0 0 12px;
  overflow-y: auto;
  border-left: 2px solid #e6f0ff;
  list-style: none;
}

.case-operations__item {
  padding: 6px 10px;
  border: 1px solid rgba(0, 0, 0, 0.06);
  border-radius: 8px;
  background: #fafcff;
}

.case-operations__item-heading {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 4px 10px;
  font-size: 13px;
}

.case-operations__type {
  flex: none;
  padding: 0 8px;
  border-radius: 6px;
  background: #e6f4ff;
  color: #0958d9;
  font-size: 12px;
  line-height: 20px;
}

.case-operations__actor {
  color: #1d1d1f;
}

.case-operations__time {
  margin-left: auto;
  color: rgba(29, 29, 31, 0.5);
  font-size: 12px;
}

.case-operations__summary {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 14px;
  margin: 4px 0 0;
  color: rgba(29, 29, 31, 0.7);
  font-size: 12px;
}
</style>
