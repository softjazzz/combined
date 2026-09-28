<template>
  <div class="manual-defect-review">
    <a-page-header
      title="人工缺陷审核"
      sub-title="审核质控员在受领任务中新增的人工缺陷"
      class="bg-white mb-4 shadow-sm"
    />

    <div class="px-6 pb-6">
      <a-card
        :bordered="false"
        class="shadow-sm"
      >
        <!-- 筛选 -->
        <div class="manual-defect-review__toolbar">
          <div class="manual-defect-review__filters">
            <div class="manual-defect-review__scene-filter">
              <label for="manual-defect-scene">质控场景</label>
              <a-select
                id="manual-defect-scene"
                :value="scene || undefined"
                class="manual-defect-review__scene-select"
                popup-class-name="manual-defect-review-scene-popup"
                placeholder="场景参数无效"
                data-testid="manual-defect-scene-filter"
                @change="(value: unknown) => void changeScene(value)"
              >
                <a-select-option
                  v-for="option in sceneOptions"
                  :key="option.value"
                  :value="option.value"
                >
                  {{ option.label }}
                </a-select-option>
              </a-select>
            </div>
            <a-radio-group
              :value="reviewStatus"
              button-style="solid"
              data-testid="manual-defect-status-filter"
              @change="(event: RadioChangeEvent) => void changeStatus(event.target.value)"
            >
              <a-radio-button
                v-for="option in statusOptions"
                :key="option.value"
                :value="option.value"
              >
                {{ option.label }}
              </a-radio-button>
            </a-radio-group>
          </div>
          <div class="manual-defect-review__summary">
            <span v-if="total !== null">共 {{ total }} 条</span>
            <a-button
              :loading="loading"
              data-testid="manual-defect-review-refresh"
              @click="void fetchList()"
            >
              刷新
            </a-button>
          </div>
        </div>

        <a-result
          v-if="forbidden"
          status="403"
          title="没有人工缺陷审核权限"
          sub-title="仅质控管理员可审核人工缺陷"
          data-testid="manual-defect-review-forbidden"
        />
        <a-alert
          v-else-if="listError"
          type="error"
          :message="listError"
          show-icon
          class="mb-4"
          data-testid="manual-defect-review-error"
        >
          <template #action>
            <a-button
              size="small"
              @click="void fetchList()"
            >
              重试
            </a-button>
          </template>
        </a-alert>

        <template v-else>
          <p
            v-if="loading && !items.length"
            class="manual-defect-review__muted"
          >
            正在读取人工缺陷…
          </p>
          <a-empty
            v-else-if="!items.length"
            :description="emptyText"
          />
          <!-- 明细：卡片展示，避免窄列导致中文逐字换行 -->
          <div
            v-else
            class="manual-defect-review__list"
          >
            <article
              v-for="item in items"
              :key="item.id"
              class="manual-defect-review__item"
              data-testid="manual-defect-review-item"
            >
              <header class="manual-defect-review__item-heading">
                <strong>{{ item.rule_name || item.rule_code || '未命名问题' }}</strong>
                <a-tag :color="severityColor(item.severity)">
                  {{ severityLabel(item.severity) }}
                </a-tag>
                <a-tag :color="statusColor(item.manual_review_status)">
                  {{ statusLabel(item.manual_review_status) }}
                </a-tag>
              </header>
              <dl class="manual-defect-review__meta">
                <div>
                  <dt>病例</dt>
                  <dd>机构 {{ known(item.institute_id) }} / 患者 {{ known(item.patient_id) }} / 就诊 {{ known(item.visit_id) }}</dd>
                </div>
                <div>
                  <dt>任务</dt>
                  <dd>{{ known(item.task_id) }} · 第 {{ item.run_number ?? '未知' }} 次运行</dd>
                </div>
                <div>
                  <dt>规则</dt>
                  <dd>{{ known(item.rule_code) }}</dd>
                </div>
                <div>
                  <dt>创建</dt>
                  <dd>{{ known(item.manual_created_by) }} · {{ formatTime(item.created_at) }}</dd>
                </div>
              </dl>
              <p><span>描述</span>{{ known(item.description) }}</p>
              <p v-if="item.location">
                <span>位置</span>{{ item.location }}
              </p>
              <p v-if="item.suggestion">
                <span>建议</span>{{ item.suggestion }}
              </p>
              <footer
                v-if="item.manual_review_status === 'pending'"
                class="manual-defect-review__actions"
              >
                <a-button
                  type="primary"
                  size="small"
                  :data-testid="`manual-defect-approve-${item.id}`"
                  :disabled="submitting"
                  @click="openReview(item, 'approved')"
                >
                  通过
                </a-button>
                <a-button
                  danger
                  size="small"
                  :data-testid="`manual-defect-reject-${item.id}`"
                  :disabled="submitting"
                  @click="openReview(item, 'rejected')"
                >
                  驳回
                </a-button>
              </footer>
            </article>
          </div>

          <div
            v-if="total !== null && total > pageSize"
            class="manual-defect-review__pagination"
          >
            <a-pagination
              :current="page"
              :page-size="pageSize"
              :total="total"
              :show-size-changer="false"
              @change="(value: number) => void changePage(value)"
            />
          </div>
        </template>
      </a-card>
    </div>

    <a-modal
      :open="reviewOpen"
      :title="decision === 'rejected' ? '驳回人工缺陷' : '通过人工缺陷'"
      :confirm-loading="submitting"
      ok-text="提交"
      cancel-text="取消"
      @ok="void submitReview()"
      @cancel="closeReview()"
    >
      <p class="manual-defect-review__muted">
        {{ reviewTarget?.rule_name || '该人工缺陷' }}：审核结论提交后不可修改。
      </p>
      <label for="manual-defect-review-reason">{{ decision === 'rejected' ? '驳回原因（必填）' : '备注（可选）' }}</label>
      <a-textarea
        id="manual-defect-review-reason"
        v-model:value="reason"
        :maxlength="2000"
        :rows="3"
        :disabled="submitting"
      />
      <p
        v-if="reviewError"
        class="manual-defect-review__error"
        role="alert"
      >
        {{ reviewError }}
      </p>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { message } from 'ant-design-vue'
import type { RadioChangeEvent } from 'ant-design-vue'
import { useRoute, useRouter } from 'vue-router'
import { getManualDefects, reviewManualDefect } from '@/api/manualDefectReviews'
import type {
  ManualDefectReviewDecision,
  ManualDefectReviewItem,
  ManualDefectReviewScene,
  ManualDefectReviewStatus,
} from '@/api/manualDefectReviews'

const route = useRoute()
const router = useRouter()

const statusOptions: Array<{ value: ManualDefectReviewStatus; label: string }> = [
  { value: 'pending', label: '待审核' },
  { value: 'approved', label: '已通过' },
  { value: 'rejected', label: '已驳回' },
]
const sceneOptions: Array<{ value: ManualDefectReviewScene; label: string }> = [
  { value: 'all', label: '全部场景' },
  { value: 'outpatient_emergency', label: '门急诊' },
  { value: 'running', label: '运行病历' },
  { value: 'final', label: '终末病历' },
]

const pageSize = 20
const items = ref<ManualDefectReviewItem[]>([])
const total = ref<number | null>(null)
const page = ref(1)
const loading = ref(false)
const listError = ref('')
const forbidden = ref(false)
const reviewOpen = ref(false)
const reviewTarget = ref<ManualDefectReviewItem | null>(null)
const decision = ref<ManualDefectReviewDecision>('approved')
const reason = ref('')
const reviewError = ref('')
const submitting = ref(false)
let listSequence = 0

const reviewStatus = computed<ManualDefectReviewStatus>(() => parseStatus(route.query.review_status))
const scene = computed<ManualDefectReviewScene | null>(() => parseScene(route.query.scene))
const emptyText = computed(() => `暂无${statusOptions.find((option) => option.value === reviewStatus.value)?.label || ''}的人工缺陷`)

function parseStatus(value: unknown): ManualDefectReviewStatus {
  return value === 'approved' || value === 'rejected' ? value : 'pending'
}

function parseScene(value: unknown): ManualDefectReviewScene | null {
  if (value === undefined || value === null || value === '') return 'all'
  if (value === 'all' || value === 'running' || value === 'final' || value === 'outpatient_emergency') {
    return value
  }
  return null
}

function known(value: string | null | undefined) {
  return value && String(value).trim() ? value : '未知'
}

function formatTime(value: string | null | undefined) {
  if (!value) return '时间未知'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? '时间未知' : date.toLocaleString('zh-CN', { hour12: false })
}

function severityLabel(value: string | null) {
  return ({ info: '提示', warning: '一般', error: '严重', critical: '危急' } as Record<string, string>)[value || ''] || '未知'
}

function severityColor(value: string | null) {
  if (value === 'critical' || value === 'error') return 'error'
  if (value === 'warning') return 'warning'
  return 'default'
}

function statusLabel(value: ManualDefectReviewStatus) {
  return statusOptions.find((option) => option.value === value)?.label || '未知'
}

function statusColor(value: ManualDefectReviewStatus) {
  if (value === 'approved') return 'success'
  if (value === 'rejected') return 'error'
  return 'processing'
}

async function fetchList() {
  const status = reviewStatus.value
  const requestedScene = scene.value
  if (!requestedScene) {
    ++listSequence
    loading.value = false
    forbidden.value = false
    items.value = []
    total.value = null
    listError.value = '质控场景参数无效，请重新选择场景'
    return
  }
  const currentPage = page.value
  const token = ++listSequence
  loading.value = true
  listError.value = ''
  try {
    const response = await getManualDefects(status, currentPage, pageSize, requestedScene)
    if (token !== listSequence) return
    if (response.status === 403) {
      forbidden.value = true
      items.value = []
      total.value = null
      return
    }
    forbidden.value = false
    const data = response.data
    if (!response.success || !data || !Array.isArray(data.items)
      || !Number.isInteger(data.total) || data.total < 0 || data.scene !== requestedScene) {
      items.value = []
      total.value = null
      listError.value = response.message || '读取人工缺陷失败'
      return
    }
    const lastPage = Math.max(1, Math.ceil(data.total / pageSize))
    if (!data.items.length && currentPage > lastPage) {
      // 审核后当前页已空：回到最后一页，按后端 total 重新读取。
      page.value = lastPage
      void fetchList()
      return
    }
    items.value = data.items
    total.value = data.total
  } catch {
    if (token !== listSequence) return
    items.value = []
    total.value = null
    listError.value = '网络异常或服务器不可用'
  } finally {
    if (token === listSequence) loading.value = false
  }
}

async function changeStatus(value: unknown) {
  const status = parseStatus(value)
  if (status === reviewStatus.value) return
  await router.replace({ query: { ...route.query, review_status: status } })
}

async function changeScene(value: unknown) {
  const nextScene = parseScene(value)
  if (!nextScene || nextScene === scene.value) return
  await router.replace({ query: { ...route.query, scene: nextScene } })
}

async function changePage(value: number) {
  page.value = value
  await fetchList()
}

function openReview(item: ManualDefectReviewItem, next: ManualDefectReviewDecision) {
  if (submitting.value || item.manual_review_status !== 'pending') return
  reviewTarget.value = item
  decision.value = next
  reason.value = ''
  reviewError.value = ''
  reviewOpen.value = true
}

function closeReview() {
  if (submitting.value) return
  reviewOpen.value = false
  reviewTarget.value = null
}

async function submitReview() {
  const target = reviewTarget.value
  if (!target || submitting.value) return
  const text = reason.value.trim()
  if (decision.value === 'rejected' && !text) {
    reviewError.value = '请填写驳回原因'
    return
  }
  submitting.value = true
  reviewError.value = ''
  try {
    const response = await reviewManualDefect(target.id, {
      decision: decision.value,
      reason: text || null,
      expected_status: 'pending',
    })
    if (response.success && response.data?.id === target.id) {
      message.success(decision.value === 'approved' ? '已通过该人工缺陷' : '已驳回该人工缺陷')
      reviewOpen.value = false
      reviewTarget.value = null
      void fetchList()
      return
    }
    if (response.status === 409) {
      message.warning(response.code === 'not_pending' ? '该缺陷已不是待审核状态，已刷新列表' : response.message || '审核状态已变化，已刷新列表')
      reviewOpen.value = false
      reviewTarget.value = null
      void fetchList()
      return
    }
    if (response.status === 403) {
      reviewError.value = response.message || '无权审核该缺陷（不能审核本人创建的缺陷）'
      return
    }
    reviewError.value = response.message || '提交失败，请重试'
  } catch {
    reviewError.value = '网络异常，请重试'
  } finally {
    submitting.value = false
  }
}

watch([reviewStatus, scene], () => {
  ++listSequence
  page.value = 1
  items.value = []
  total.value = null
  forbidden.value = false
  if (!submitting.value) closeReview()
  void fetchList()
}, { immediate: true })
</script>

<style scoped>
.manual-defect-review__toolbar { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 16px; }
.manual-defect-review__filters { display: flex; flex-wrap: wrap; align-items: flex-end; gap: 12px; }
.manual-defect-review__scene-filter { display: grid; gap: 4px; }
.manual-defect-review__scene-filter label { color: rgba(29, 29, 31, .6); font-size: 13px; line-height: 20px; }
.manual-defect-review__scene-select { width: 150px; }
.manual-defect-review__summary { display: flex; align-items: center; gap: 12px; color: rgba(29, 29, 31, .6); font-size: 13px; }
.manual-defect-review__list { display: grid; gap: 12px; }
.manual-defect-review__item { padding: 14px 16px; border: 1px solid #f0f0f0; border-radius: 10px; background: #fff; }
.manual-defect-review__item-heading { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; }
.manual-defect-review__meta { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 6px 16px; margin: 10px 0 0; }
.manual-defect-review__meta div { display: flex; gap: 8px; min-width: 0; }
.manual-defect-review__meta dt { flex: none; color: rgba(29, 29, 31, .6); }
.manual-defect-review__meta dd { margin: 0; overflow-wrap: anywhere; }
.manual-defect-review__item p { margin: 8px 0 0; line-height: 22px; overflow-wrap: anywhere; }
.manual-defect-review__item p span { margin-right: 9px; color: rgba(29, 29, 31, .6); }
.manual-defect-review__actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 10px; }
.manual-defect-review__pagination { display: flex; justify-content: flex-end; margin-top: 16px; }
.manual-defect-review__muted { color: rgba(29, 29, 31, .6); font-size: 13px; }
.manual-defect-review__error { margin: 8px 0 0; color: #b42318; }
</style>

<style>
.manual-defect-review-scene-popup {
  font-family: 'Source Han Sans SC', 'Microsoft YaHei UI', 'PingFang SC', sans-serif;
}
</style>
