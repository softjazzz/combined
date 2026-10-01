<template>
  <section
    v-if="canReview"
    class="appeal-todos workstation-surface-enter"
    aria-labelledby="appeal-todos-title"
  >
    <header class="appeal-todos__header">
      <h2 id="appeal-todos-title">缺陷审核待办</h2>
      <div class="appeal-todos__tools">
        <button
          type="button"
          data-testid="all-appeals"
          @click="void router.push('/dashboard/qc/appeals')"
        >
          查看全部申诉
        </button>
        <button
          type="button"
          :disabled="loading"
          aria-label="刷新临床申诉待办"
          @click="void fetchTodos()"
        >
          <RotateCw :size="16" aria-hidden="true" />刷新
        </button>
      </div>
    </header>
    <p v-if="error" class="appeal-todos__error" role="alert" data-testid="appeal-todos-error">
      {{ error }}
    </p>
    <div class="appeal-todos__list">
      <button
        v-for="item in sceneTodos"
        :key="item.scene"
        type="button"
        class="appeal-todos__item"
        :data-testid="`appeal-review-todo-${item.scene}`"
        :disabled="loading || counts[item.scene] === null"
        @click="openTodo(item.scene)"
      >
        <ClipboardCheck :size="19" aria-hidden="true" />
        <span>{{ item.label }}</span>
        <strong :data-testid="`appeal-review-count-${item.scene}`">{{
          loading ? '加载中' : (counts[item.scene] ?? '不可用')
        }}</strong>
        <ArrowRight :size="17" aria-hidden="true" />
      </button>
    </div>
    <p
      v-if="!loading && totalCount === 0"
      class="appeal-todos__empty"
      data-testid="appeal-todos-empty"
      role="status"
    >
      没有待处理事项
    </p>
  </section>
</template>

<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import { message } from 'ant-design-vue'
import { ArrowRight, ClipboardCheck, RotateCw } from 'lucide-vue-next'
import { useRouter } from 'vue-router'
import { getAppeals } from '@/api/appeal'
import { useAuthStore } from '@/stores/auth'
import type { AppealScene } from '@/types/appeal'

const router = useRouter()
const authStore = useAuthStore()
const canReview = computed(() =>
  authStore.userRoles.some((role) => role === 'admin' || role === 'qc_manager'),
)
const currentUserId = computed(() => authStore.user?.id?.trim() || '')
const sceneTodos: Array<{ scene: AppealScene; label: string }> = [
  { scene: 'running', label: '运行质控申诉待审核' },
  { scene: 'final', label: '终末质控申诉待审核' },
  { scene: 'outpatient_emergency', label: '门急诊质控申诉待审核' },
]
const counts = ref<Record<AppealScene, number | null>>({
  running: null,
  final: null,
  outpatient_emergency: null,
})
const totalCount = computed(() => {
  const values = Object.values(counts.value)
  return values.every((value) => value !== null)
    ? values.reduce<number>((sum, value) => sum + (value ?? 0), 0)
    : null
})
const loading = ref(true)
const error = ref('')
let requestId = 0

async function fetchTodos() {
  if (!canReview.value || !currentUserId.value) {
    requestId++
    counts.value = { running: null, final: null, outpatient_emergency: null }
    loading.value = false
    error.value = ''
    return
  }
  const currentRequestId = ++requestId
  counts.value = { running: null, final: null, outpatient_emergency: null }
  loading.value = true
  error.value = ''
  try {
    const pages = await Promise.all(
      sceneTodos.map(async ({ scene }) => {
        try {
          const page = await getAppeals({ status: 'reviewable', scene, page: 1, pageSize: 1 })
          return Number.isInteger(page.total) && page.total >= 0
            ? ([scene, page.total] as const)
            : ([scene, null] as const)
        } catch {
          return [scene, null] as const
        }
      }),
    )
    if (currentRequestId !== requestId) return
    counts.value = Object.fromEntries(pages) as Record<AppealScene, number | null>
    if (pages.some(([, value]) => value === null)) error.value = '部分申诉待办暂不可用，请重试'
  } catch {
    if (currentRequestId !== requestId) return
    counts.value = { running: null, final: null, outpatient_emergency: null }
    error.value = '申诉待办暂不可用，请重试'
  } finally {
    if (currentRequestId === requestId) loading.value = false
  }
}

function openTodo(scene: AppealScene) {
  const count = counts.value[scene]
  if (count === null) return
  if (count === 0) {
    message.info('没有待审核的临床申诉')
    return
  }
  void router.push({ path: '/dashboard/qc/appeals', query: { todo: 'review', scene } })
}

watch(
  [currentUserId, canReview],
  ([userId, allowed]) => {
    requestId++
    counts.value = { running: null, final: null, outpatient_emergency: null }
    error.value = ''
    if (userId && allowed) {
      void fetchTodos()
    } else {
      loading.value = false
    }
  },
  { immediate: true },
)

onUnmounted(() => {
  requestId++
})
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
.appeal-todos__tools {
  display: flex;
  align-items: center;
  gap: 12px;
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
.appeal-todos__list {
  display: grid;
  gap: 8px;
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
.appeal-todos__empty {
  margin: 12px 0 0;
  color: rgba(29, 29, 31, 0.6);
  font-size: 14px;
}
</style>
