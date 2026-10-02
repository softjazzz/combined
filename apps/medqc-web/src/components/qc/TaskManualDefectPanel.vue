<template>
  <section
    class="manual-defects"
    aria-label="人工缺陷"
    data-testid="task-manual-defects"
  >
    <div class="manual-defects__heading">
      <h4>人工缺陷</h4>
      <a-button
        size="small"
        :loading="loading"
        :disabled="submitting"
        data-testid="manual-defect-refresh"
        @click="void refresh()"
      >
        <RotateCw
          :size="14"
          aria-hidden="true"
        />刷新
      </a-button>
    </div>
    <p
      v-if="loading"
      class="manual-defects__muted"
    >
      正在读取人工缺陷…
    </p>
    <p
      v-else-if="listError"
      class="manual-defects__error"
      role="alert"
    >
      {{ listError }}
    </p>
    <template v-else>
      <div
        v-for="item in items"
        :key="item.id"
        class="manual-defects__item"
        data-testid="manual-defect-item"
      >
        <div class="manual-defects__item-heading">
          <strong>{{ item.rule_name }}</strong>
          <span class="manual-defects__tags">
            <a-tag :color="severityColor(item.severity)">
              {{ severityLabel(item.severity) }}
            </a-tag>
            <a-tag
              :color="reviewColor(item.manual_review_status)"
              data-testid="manual-defect-review-status"
            >
              {{ reviewLabel(item.manual_review_status) }}
            </a-tag>
          </span>
        </div>
        <p>{{ item.description }}</p>
        <p v-if="item.suggestion">
          <span>建议</span>{{ item.suggestion }}
        </p>
        <p v-if="item.evidence">
          <span>证据</span>{{ item.evidence }}
        </p>
        <small>第 {{ item.run_number }} 次运行</small>
      </div>
      <p
        v-if="!items.length"
        class="manual-defects__muted"
      >
        当前病历暂无人工缺陷
      </p>
      <div
        v-if="total > items.length"
        class="manual-defects__paging"
      >
        <span>已显示 {{ items.length }} / {{ total }} 条</span>
        <a-button
          size="small"
          :loading="loadingMore"
          @click="void loadMore()"
        >
          加载更多
        </a-button>
      </div>
    </template>

    <form
      v-if="eligible"
      class="manual-defects__form"
      @submit.prevent="void submit()"
    >
      <h5>新增人工缺陷</h5>
      <label for="manual-defect-rule">问题名称</label>
      <a-input
        id="manual-defect-rule"
        v-model:value="ruleName"
        :maxlength="200"
        :disabled="!!pendingPayload || submitting"
        placeholder="填写具体质控问题"
      />
      <label for="manual-defect-description">问题描述</label>
      <a-textarea
        id="manual-defect-description"
        v-model:value="description"
        :maxlength="4000"
        :rows="3"
        :disabled="!!pendingPayload || submitting"
        placeholder="说明发现的问题"
      />
      <label for="manual-defect-severity">严重程度</label>
      <a-select
        id="manual-defect-severity"
        v-model:value="severity"
        :disabled="!!pendingPayload || submitting"
        :options="severityOptions"
      />
      <label for="manual-defect-suggestion">整改建议</label>
      <a-textarea
        id="manual-defect-suggestion"
        v-model:value="suggestion"
        :maxlength="2000"
        :rows="2"
        :disabled="!!pendingPayload || submitting"
      />
      <label for="manual-defect-evidence">证据说明</label>
      <a-textarea
        id="manual-defect-evidence"
        v-model:value="evidence"
        :maxlength="2000"
        :rows="2"
        :disabled="!!pendingPayload || submitting"
      />
      <a-button size="small" :loading="documentsLoading" :disabled="!!pendingPayload || submitting" @click="void loadDocuments()">
        <RotateCw :size="14" />选择可信文书
      </a-button>
      <p v-if="documentsError" class="manual-defects__error" role="alert">{{ documentsError }}</p>
      <template v-if="documentOptions.length">
        <label for="manual-anchor-document">证据文书</label>
        <a-select id="manual-anchor-document" v-model:value="selectedDocument" allow-clear
          :disabled="!!pendingPayload || submitting" :options="documentOptions.map((item, index) => ({ value: String(index), label: item.label }))"
          @change="selectedField = ''; anchorQuote = ''" />
        <template v-if="anchorDocument">
          <label for="manual-anchor-field">原文字段</label>
          <a-select id="manual-anchor-field" v-model:value="selectedField"
            :disabled="!!pendingPayload || submitting" :options="anchorDocument.fields.map((item) => ({ value: item.source_field, label: item.label }))"
            @change="anchorQuote = ''" />
          <pre v-if="anchorField" class="manual-defects__source">{{ anchorField.text }}</pre>
          <label for="manual-anchor-quote">完整原文摘录</label>
          <a-textarea id="manual-anchor-quote" v-model:value="anchorQuote" :maxlength="2000" :rows="3" :disabled="!!pendingPayload || submitting" />
        </template>
      </template>
      <p
        v-if="formError"
        class="manual-defects__error"
        role="alert"
      >
        {{ formError }}
      </p>
      <p
        v-if="successMessage"
        class="manual-defects__success"
        role="status"
      >
        {{ successMessage }}
      </p>
      <div class="manual-defects__actions">
        <a-button
          v-if="pendingPayload"
          :loading="submitting"
          @click="void verifyPending()"
        >
          查询提交状态
        </a-button>
        <a-button
          type="primary"
          html-type="submit"
          :loading="submitting"
          data-testid="manual-defect-submit"
        >
          {{ pendingPayload ? '重试提交' : '提交缺陷' }}
        </a-button>
      </div>
    </form>
  </section>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { RotateCw } from 'lucide-vue-next'
import { createTaskManualDefect, getTaskManualDefects, getTaskManualDocumentOptions } from '@/api/tasks'
import type { TaskManualDefect, TaskManualDefectCreate, TaskManualDefectSeverity, TaskManualDocumentOption } from '@/api/tasks'

const props = defineProps<{
  taskId: string
  taskRecordId: string
  runNumber: number
  jobId: string
  userId: string
  eligible: boolean
}>()

const emit = defineEmits<{ 'defect-created': [] }>()
const ruleName = ref('')
const description = ref('')
const severity = ref<TaskManualDefectSeverity>('warning')
const suggestion = ref('')
const evidence = ref('')
const items = ref<TaskManualDefect[]>([])
const total = ref(0)
const loading = ref(false)
const loadingMore = ref(false)
const submitting = ref(false)
const listError = ref('')
const formError = ref('')
const successMessage = ref('')
const pendingPayload = ref<TaskManualDefectCreate | null>(null)
let sequence = 0
const documentOptions = ref<TaskManualDocumentOption[]>([])
const documentsLoading = ref(false)
const documentsError = ref('')
const selectedDocument = ref<string>()
const selectedField = ref('')
const anchorQuote = ref('')
const anchorDocument = computed(() => selectedDocument.value === undefined ? undefined : documentOptions.value[Number(selectedDocument.value)])
const anchorField = computed(() => anchorDocument.value?.fields.find((item) => item.source_field === selectedField.value))
let documentSequence = 0

async function loadDocuments() {
  const key = contextKey.value
  const token = ++documentSequence
  documentsLoading.value = true
  documentsError.value = ''
  documentOptions.value = []
  selectedDocument.value = undefined
  selectedField.value = ''
  anchorQuote.value = ''
  try {
    const response = await getTaskManualDocumentOptions(props.taskId, props.taskRecordId, props.runNumber)
    if (key !== contextKey.value || token !== documentSequence) return
    const data = response.data
    if (!response.success || !data || data.task_id !== props.taskId || data.task_record_id !== props.taskRecordId
      || data.run_number !== props.runNumber || data.job_id !== props.jobId || !Array.isArray(data.documents)) {
      throw new Error('可信文书未通过本次运行身份校验')
    }
    documentOptions.value = data.documents
    if (!data.documents.length) documentsError.value = '本次暂无完整且唯一的可信文书字段'
  } catch {
    if (key === contextKey.value && token === documentSequence) documentsError.value = '可信文书暂不可用'
  } finally {
    if (key === contextKey.value && token === documentSequence) documentsLoading.value = false
  }
}

const contextKey = computed(() => JSON.stringify([
  props.taskId, props.taskRecordId, props.runNumber, props.jobId, props.userId,
]))
const severityOptions = [
  { value: 'info', label: '提示' },
  { value: 'warning', label: '一般' },
  { value: 'error', label: '严重' },
  { value: 'critical', label: '危急' },
]

function isCurrent(key: string, token: number) {
  return key === contextKey.value && token === sequence
}

function isOwned(item: TaskManualDefect) {
  return item.task_id === props.taskId && item.task_record_id === props.taskRecordId
    && Number.isInteger(item.run_number) && item.run_number > 0
}

function severityLabel(value: string) {
  return severityOptions.find((option) => option.value === value)?.label || '未分类'
}

function severityColor(value: string) {
  if (value === 'critical' || value === 'error') return 'error'
  if (value === 'warning') return 'warning'
  return 'default'
}

function reviewLabel(value: string) {
  return ({ pending: '待审核', approved: '已通过', rejected: '已驳回' } as Record<string, string>)[value] || '未知'
}

function reviewColor(value: string) {
  if (value === 'approved') return 'success'
  if (value === 'rejected') return 'error'
  if (value === 'pending') return 'processing'
  return 'default'
}

async function readPage(key: string, token: number, offset: number) {
  const response = await getTaskManualDefects(props.taskId, props.taskRecordId, 50, offset)
  if (!isCurrent(key, token)) return null
  if (!response.success || !response.data || !Array.isArray(response.data.items)
    || !Number.isInteger(response.data.total) || response.data.total < 0
    || response.data.items.some((item) => !isOwned(item))) {
    throw new Error(response.message || '人工缺陷查询未通过身份校验')
  }
  return response.data
}

async function refresh() {
  if (submitting.value) return
  const key = contextKey.value
  const token = ++sequence
  loading.value = true
  loadingMore.value = false
  listError.value = ''
  try {
    const page = await readPage(key, token, 0)
    if (!page || !isCurrent(key, token)) return
    items.value = page.items
    total.value = page.total
  } catch (error) {
    if (isCurrent(key, token)) listError.value = error instanceof Error ? error.message : '读取人工缺陷失败'
  } finally {
    if (isCurrent(key, token)) loading.value = false
  }
}

async function loadMore() {
  if (submitting.value || loading.value || loadingMore.value || items.value.length >= total.value) return
  const key = contextKey.value
  const token = ++sequence
  loadingMore.value = true
  try {
    const page = await readPage(key, token, items.value.length)
    if (!page || !isCurrent(key, token)) return
    items.value = [...items.value, ...page.items]
    total.value = page.total
  } catch (error) {
    if (isCurrent(key, token)) listError.value = error instanceof Error ? error.message : '读取人工缺陷失败'
  } finally {
    if (isCurrent(key, token)) loadingMore.value = false
  }
}

async function verifyPending() {
  const payload = pendingPayload.value
  if (!payload || submitting.value) return
  const key = contextKey.value
  const token = ++sequence
  submitting.value = true
  loading.value = false
  loadingMore.value = false
  formError.value = ''
  try {
    const page = await readPage(key, token, 0)
    if (!page || !isCurrent(key, token)) return
    items.value = page.items
    total.value = page.total
    if (!page.items.some((item) => item.id === payload.defect_id && item.run_number === props.runNumber
      && item.rule_name === payload.rule_name && item.description === payload.description
      && item.severity === payload.severity && item.suggestion === (payload.suggestion || null)
      && item.evidence === (payload.evidence || null)
      && (!payload.document_anchor || (item.job_id === props.jobId
        && item.document_anchor?.source_ref === payload.document_anchor.source_ref
        && item.document_anchor?.source_type === payload.document_anchor.source_type
        && item.document_anchor?.field_path === payload.document_anchor.field_path
        && item.document_anchor?.quote === payload.document_anchor.quote)))) {
      formError.value = '未查到本次提交，保留原编号可安全重试'
      return
    }
    pendingPayload.value = null
    ruleName.value = ''
    description.value = ''
    suggestion.value = ''
    evidence.value = ''
    selectedDocument.value = undefined
    selectedField.value = ''
    anchorQuote.value = ''
    severity.value = 'warning'
    successMessage.value = '人工缺陷已保存并确认'
    emit('defect-created')
  } catch {
    if (isCurrent(key, token)) formError.value = '无法确认提交状态，请查询或使用原编号重试'
  } finally {
    if (isCurrent(key, token)) submitting.value = false
  }
}

async function submit() {
  if (!props.eligible || submitting.value) return
  if (!pendingPayload.value) {
    const name = ruleName.value.trim()
    const text = description.value.trim()
    if (!name || !text) {
      formError.value = '请填写问题名称和问题描述'
      return
    }
    if (anchorDocument.value && (!anchorField.value || !anchorQuote.value.trim())) {
      formError.value = '请选择原文字段并填写完整摘录'
      return
    }
    pendingPayload.value = {
      defect_id: crypto.randomUUID(),
      run_number: props.runNumber,
      rule_name: name,
      description: text,
      severity: severity.value,
      suggestion: suggestion.value.trim() || null,
      evidence: evidence.value.trim() || null,
      ...(anchorDocument.value ? { document_anchor: {
        source_ref: anchorDocument.value.source_ref, source_type: anchorDocument.value.source_type,
        field_path: selectedField.value, quote: anchorQuote.value,
      } } : {}),
    }
  }
  const key = contextKey.value
  const token = ++sequence
  const payload = pendingPayload.value
  submitting.value = true
  loading.value = false
  loadingMore.value = false
  formError.value = ''
  successMessage.value = ''
  try {
    const response = await createTaskManualDefect(props.taskId, props.taskRecordId, payload)
    if (!isCurrent(key, token)) return
    if (!response.success && response.status && response.status >= 400 && response.status < 500 && response.status !== 408) {
      pendingPayload.value = null
      formError.value = response.message || '提交被拒绝，请检查内容后重试'
      return
    }
  } catch {
    // 网络超时可能已落库，仍通过精确列表验证。
  } finally {
    if (isCurrent(key, token)) submitting.value = false
  }
  if (isCurrent(key, token)) await verifyPending()
}

watch(contextKey, () => {
  documentSequence += 1
  documentOptions.value = []
  selectedDocument.value = undefined
  selectedField.value = ''
  anchorQuote.value = ''
  documentsLoading.value = false
  documentsError.value = ''
  sequence += 1
  items.value = []
  total.value = 0
  loading.value = false
  loadingMore.value = false
  submitting.value = false
  pendingPayload.value = null
  ruleName.value = ''
  description.value = ''
  suggestion.value = ''
  evidence.value = ''
  severity.value = 'warning'
  formError.value = ''
  successMessage.value = ''
  void refresh()
}, { immediate: true })
</script>

<style scoped>
.manual-defects { margin-top: 18px; padding-top: 16px; border-top: 1px solid rgba(0, 0, 0, .08); }
.manual-defects__heading, .manual-defects__item-heading, .manual-defects__paging, .manual-defects__actions { display: flex; align-items: center; justify-content: space-between; gap: 10px; }
.manual-defects__heading h4, .manual-defects__form h5 { margin: 0; font-size: 14px; font-weight: 600; }
.manual-defects__heading button { display: inline-flex; align-items: center; gap: 5px; }
.manual-defects__item { padding: 12px 0; border-bottom: 1px solid rgba(0, 0, 0, .08); }
.manual-defects__item p { margin: 6px 0 0; line-height: 22px; overflow-wrap: anywhere; }
.manual-defects__item p span { margin-right: 9px; color: rgba(29, 29, 31, .6); }
.manual-defects__item small, .manual-defects__muted, .manual-defects__paging { color: rgba(29, 29, 31, .6); font-size: 13px; }
.manual-defects__tags { display: inline-flex; gap: 4px; }
.manual-defects__error { color: #b42318; }
.manual-defects__success { color: #067647; }
.manual-defects__form { display: grid; gap: 8px; margin-top: 16px; padding-top: 14px; border-top: 1px solid rgba(0, 0, 0, .08); }
.manual-defects__form label { margin-top: 4px; color: rgba(29, 29, 31, .7); font-size: 13px; }
.manual-defects__actions { justify-content: flex-end; margin-top: 4px; }
.manual-defects__source { max-height: 220px; overflow: auto; white-space: pre-wrap; overflow-wrap: anywhere; font: inherit; line-height: 1.6; margin: 0; padding: 8px; background: #f5f5f7; }
</style>
