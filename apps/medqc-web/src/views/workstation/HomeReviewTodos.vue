<template>
  <section class="review-todos workstation-surface-enter" aria-labelledby="review-todos-title">
    <header class="review-todos__header">
      <div>
        <span>全部场景</span>
        <h2 id="review-todos-title">我的审核待办</h2>
      </div>
      <button
        type="button"
        :disabled="loading"
        aria-label="刷新审核待办"
        data-testid="refresh-home-review-todos"
        @click="void fetchTodos()"
      >
        <RotateCw :size="16" aria-hidden="true" />刷新
      </button>
    </header>

    <div v-if="error" class="review-todos__error" role="alert" data-testid="home-review-todos-error">
      <span>{{ error }}</span>
      <button type="button" data-testid="retry-home-review-todos" @click="void fetchTodos()">重试</button>
    </div>

    <div class="review-todos__grid" :aria-busy="loading">
      <button
        v-for="item in todoItems"
        :key="item.key"
        type="button"
        :disabled="loading || item.value === null"
        :data-testid="`review-todo-${item.key}`"
        @click="openTodo(item)"
      >
        <component :is="item.icon" :size="19" aria-hidden="true" />
        <span>
          <strong>{{ item.label }}</strong>
          <small>{{ item.scope }}</small>
        </span>
        <b :data-testid="`review-todo-${item.key}-count`">{{ formatValue(item.value) }}</b>
        <ArrowRight :size="17" aria-hidden="true" />
      </button>
    </div>

    <p v-if="manualDefectUnavailable" class="review-todos__note" data-testid="manual-defect-scope-note">
      人工缺陷尚无场景归属；当前账号无全场景审核权限时，计数显示为不可用。
    </p>
  </section>
</template>

<script setup lang="ts">
import { computed, onUnmounted, ref, watch, type Component } from 'vue'
import { message } from 'ant-design-vue'
import { ArrowRight, ClipboardCheck, FileCheck2, Files, RotateCw } from 'lucide-vue-next'
import { useRouter } from 'vue-router'
import { getReviewTodoCounts, type ReviewTodoCounts } from '@/api/dashboard'
import { useAuthStore } from '@/stores/auth'

interface ReviewTodoItem {
  key: 'record-review' | 'record-recheck' | 'manual-defect'
  label: string
  scope: string
  value: number | null
  icon: Component
  path: string
  query: Record<string, string>
}

const router = useRouter()
const authStore = useAuthStore()
const counts = ref<ReviewTodoCounts | null>(null)
const loading = ref(true)
const error = ref('')
let requestId = 0

const todoItems = computed<ReviewTodoItem[]>(() => [
  {
    key: 'record-review',
    label: '待初审病历',
    scope: '本人受领任务的已核实结果',
    value: counts.value?.pending_record_review ?? null,
    icon: FileCheck2,
    path: '/dashboard/qc/record-reviews',
    query: { stage: 'initial', scene: 'all' },
  },
  {
    key: 'record-recheck',
    label: '待复审病历',
    scope: '本人受领任务的待复审结果',
    value: counts.value?.pending_record_recheck ?? null,
    icon: Files,
    path: '/dashboard/qc/record-reviews',
    query: { stage: 'recheck', scene: 'all' },
  },
  {
    key: 'manual-defect',
    label: '待审核人工缺陷',
    scope: '全场景总计（暂不可按场景归属）',
    value: counts.value?.pending_manual_defect_review ?? null,
    icon: ClipboardCheck,
    path: '/dashboard/qc/manual-defects',
    query: { review_status: 'pending' },
  },
])

const manualDefectUnavailable = computed(
  () => !loading.value && !error.value && counts.value?.pending_manual_defect_review === null,
)
const currentUserId = computed(() => authStore.user?.id?.trim() || '')

function formatValue(value: number | null) {
  if (loading.value) return '加载中'
  return value === null ? '不可用' : String(value)
}

async function fetchTodos() {
  const currentRequestId = ++requestId
  loading.value = true
  error.value = ''
  counts.value = null
  try {
    const response = await getReviewTodoCounts()
    if (currentRequestId !== requestId) return
    if (!response.success || !response.data) {
      error.value = response.message || '读取审核待办失败'
      return
    }
    counts.value = response.data
  } catch {
    if (currentRequestId !== requestId) return
    error.value = '网络异常或服务器不可用'
  } finally {
    if (currentRequestId === requestId) loading.value = false
  }
}

function openTodo(item: ReviewTodoItem) {
  if (loading.value || item.value === null) return
  if (item.value === 0) {
    message.info(`没有${item.label}`)
    return
  }
  void router.push({ path: item.path, query: item.query })
}

watch(
  currentUserId,
  (userId) => {
    requestId++
    counts.value = null
    error.value = ''
    if (!userId) {
      loading.value = false
      return
    }
    void fetchTodos()
  },
  { immediate: true },
)

onUnmounted(() => {
  requestId++
})
</script>

<style scoped>
.review-todos {
  margin: 16px 0;
  padding: 18px 0;
  border-block: 1px solid rgba(0, 0, 0, 0.08);
  color: #1d1d1f;
}
.review-todos__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
}
.review-todos__header span {
  color: rgba(29, 29, 31, 0.55);
  font-size: 12px;
}
.review-todos h2 {
  margin: 2px 0 0;
  font-size: 17px;
  font-weight: 600;
  line-height: 22px;
}
.review-todos button {
  font: inherit;
}
.review-todos__header > button,
.review-todos__error button {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border: 0;
  background: transparent;
  color: #007aff;
  cursor: pointer;
}
.review-todos button:disabled {
  cursor: wait;
  opacity: 0.6;
}
.review-todos__grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 260px), 1fr));
  gap: 10px;
}
.review-todos__grid > button {
  display: grid;
  grid-template-columns: 22px minmax(0, 1fr) auto 18px;
  align-items: center;
  gap: 9px;
  min-height: 62px;
  padding: 10px 12px;
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 8px;
  background: #fff;
  color: rgba(29, 29, 31, 0.7);
  text-align: left;
  cursor: pointer;
}
.review-todos__grid > button:hover:not(:disabled) {
  border-color: rgba(0, 122, 255, 0.28);
  background: rgba(0, 122, 255, 0.035);
}
.review-todos__grid strong,
.review-todos__grid small {
  display: block;
}
.review-todos__grid strong {
  color: #1d1d1f;
  font-size: 14px;
  font-weight: 600;
  line-height: 22px;
}
.review-todos__grid small {
  margin-top: 2px;
  color: rgba(29, 29, 31, 0.52);
  font-size: 12px;
  line-height: 18px;
}
.review-todos__grid b {
  color: #1d1d1f;
  font-size: 22px;
  font-weight: 600;
}
.review-todos__error {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
  padding: 9px 12px;
  border-radius: 8px;
  background: #fff1f0;
  color: #b42318;
  font-size: 13px;
}
.review-todos__note {
  margin: 10px 0 0;
  color: rgba(29, 29, 31, 0.6);
  font-size: 13px;
  line-height: 20px;
}
</style>
