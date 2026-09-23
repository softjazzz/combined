<template>
  <section
    v-if="canReview"
    class="appeal-todos workstation-surface-enter"
    aria-labelledby="appeal-todos-title"
  >
    <header class="appeal-todos__header">
      <h2 id="appeal-todos-title">
        缺陷审核待办
      </h2>
      <button
        type="button"
        :disabled="loading"
        aria-label="刷新临床申诉待办"
        @click="void fetchTodos()"
      >
        <RotateCw
          :size="16"
          aria-hidden="true"
        />刷新
      </button>
    </header>
    <p
      v-if="error"
      class="appeal-todos__error"
      role="alert"
      data-testid="appeal-todos-error"
    >
      {{ error }}
    </p>
    <button
      type="button"
      class="appeal-todos__item"
      data-testid="appeal-review-todo"
      :disabled="loading || count === null"
      @click="openTodo"
    >
      <ClipboardCheck
        :size="19"
        aria-hidden="true"
      />
      <span>临床申诉待审核</span>
      <strong data-testid="appeal-review-count">{{ loading ? '加载中' : count ?? '不可用' }}</strong>
      <ArrowRight
        :size="17"
        aria-hidden="true"
      />
    </button>
  </section>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { message } from 'ant-design-vue'
import { ArrowRight, ClipboardCheck, RotateCw } from 'lucide-vue-next'
import { useRouter } from 'vue-router'
import { getAppeals } from '@/api/appeal'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const authStore = useAuthStore()
const canReview = computed(() => authStore.userRoles.some((role) => role === 'admin' || role === 'qc_manager'))
const count = ref<number | null>(null)
const loading = ref(true)
const error = ref('')
let requestId = 0

async function fetchTodos() {
  if (!canReview.value) return
  const currentRequestId = ++requestId
  count.value = null
  loading.value = true
  error.value = ''
  try {
    const page = await getAppeals({ status: 'reviewable', page: 1, pageSize: 1 })
    if (currentRequestId !== requestId) return
    if (!Number.isInteger(page.total) || page.total < 0) throw new Error('申诉待办数据暂不可用')
    count.value = page.total
  } catch {
    if (currentRequestId !== requestId) return
    count.value = null
    error.value = '申诉待办暂不可用，请重试'
  } finally {
    if (currentRequestId === requestId) loading.value = false
  }
}

function openTodo() {
  if (count.value === null) return
  if (count.value === 0) {
    message.info('没有待审核的临床申诉')
    return
  }
  void router.push({ path: '/dashboard/qc/appeals', query: { todo: 'review' } })
}

watch(
  canReview,
  (allowed) => {
    if (allowed) {
      void fetchTodos()
    } else {
      requestId++
      count.value = null
      loading.value = false
      error.value = ''
    }
  },
  { immediate: true },
)
</script>

<style scoped>
.appeal-todos {
  margin: 16px 0;
  padding: 18px 0;
  border-block: 1px solid rgba(0, 0, 0, 0.08);
  color: #1d1d1f;
}
.appeal-todos__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
}
.appeal-todos h2 {
  margin: 0;
  font-size: 17px;
  font-weight: 600;
  line-height: 22px;
}
.appeal-todos__header button {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border: 0;
  background: transparent;
  color: #007aff;
  cursor: pointer;
}
.appeal-todos__error {
  margin: 0 0 10px;
  color: #b42318;
  font-size: 13px;
}
.appeal-todos__item {
  display: grid;
  width: 100%;
  grid-template-columns: 22px 1fr auto 18px;
  align-items: center;
  gap: 9px;
  min-height: 54px;
  padding: 10px 12px;
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 8px;
  background: #fff;
  color: rgba(29, 29, 31, 0.7);
  text-align: left;
  cursor: pointer;
}
.appeal-todos__item strong {
  color: #1d1d1f;
  font-size: 17px;
}
.appeal-todos button:disabled {
  cursor: wait;
  opacity: 0.6;
}
</style>
