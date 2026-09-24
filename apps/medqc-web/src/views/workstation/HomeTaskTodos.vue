<template>
  <section
    class="task-todos workstation-surface-enter"
    aria-labelledby="task-todos-title"
  >
    <header>
      <div>
        <span>{{ activeSceneLabel }}</span>
        <h2 id="task-todos-title">
          我的任务待办
        </h2>
      </div>
      <div class="task-todos__tools">
        <button
          type="button"
          data-testid="all-my-tasks"
          @click="void router.push('/dashboard/tasks/my')"
        >
          查看全部任务
        </button>
        <label for="home-task-scene">场景</label>
        <select
          id="home-task-scene"
          v-model="activeSceneValue"
          data-testid="home-task-scene"
          :disabled="loading"
          @change="handleSceneChange"
        >
          <option
            v-for="option in sceneOptions"
            :key="option.value"
            :value="option.value"
          >
            {{ option.label }}
          </option>
        </select>
        <button
          data-testid="refresh-home-task-todos"
          type="button"
          :disabled="loading"
          aria-label="刷新我的任务待办"
          @click="void fetchTodos()"
        >
          <RotateCw :size="16" />刷新
        </button>
      </div>
    </header>

    <div
      v-if="error"
      data-testid="home-task-todos-error"
      class="task-todos__error"
      role="alert"
    >
      <span>任务待办暂不可用：{{ error }}</span>
      <button
        data-testid="retry-home-task-todos"
        type="button"
        @click="void fetchTodos()"
      >
        重试
      </button>
    </div>

    <div
      class="task-todos__grid"
      :aria-busy="loading"
    >
      <button
        v-for="item in todoItems"
        :key="item.key"
        :data-testid="`todo-${item.key}`"
        type="button"
        :disabled="loading"
        @click="openTodo(item.key, item.value)"
      >
        <component
          :is="item.icon"
          :size="19"
          aria-hidden="true"
        />
        <span>{{ item.label }}</span>
        <strong :data-testid="`todo-${item.key}-count`">{{ formatValue(item.value) }}</strong>
        <ArrowRight
          :size="17"
          aria-hidden="true"
        />
      </button>
    </div>
    <p
      v-if="!loading && !error && allEmpty"
      class="task-todos__empty"
      data-testid="home-task-todos-empty"
      role="status"
    >
      没有待处理事项
    </p>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { message } from 'ant-design-vue'
import { ArrowRight, CirclePlay, ClipboardList, Clock3, RotateCw } from 'lucide-vue-next'
import { useRouter } from 'vue-router'
import { getTaskTodoStats } from '@/api/tasks'
import type { TaskSceneFilter, TaskTodo, TaskTodoStats } from '@/api/tasks'

const router = useRouter()
const stats = ref<TaskTodoStats | null>(null)
const loading = ref(true)
const error = ref('')
const activeSceneValue = ref<TaskSceneFilter | ''>('')
let requestId = 0

const sceneOptions: Array<{ label: string; value: TaskSceneFilter | '' }> = [
  { label: '全部场景', value: '' },
  { label: '运行', value: 'running' },
  { label: '终末', value: 'final' },
  { label: '门急诊', value: 'outpatient' },
  { label: '未标注', value: 'unclassified' },
]

const activeSceneLabel = computed(
  () => sceneOptions.find((option) => option.value === activeSceneValue.value)?.label || '全部场景',
)
const allEmpty = computed(
  () => stats.value !== null
    && stats.value.due_soon === 0
    && stats.value.in_progress === 0
    && stats.value.assigned === 0,
)

const todoItems = computed(() => [
  {
    key: 'due_soon' as const,
    label: '24 小时内到期',
    value: stats.value?.due_soon ?? null,
    icon: Clock3,
  },
  {
    key: 'in_progress' as const,
    label: '进行中',
    value: stats.value?.in_progress ?? null,
    icon: CirclePlay,
  },
  {
    key: 'assigned' as const,
    label: '未开始',
    value: stats.value?.assigned ?? null,
    icon: ClipboardList,
  },
])

function formatValue(value: number | null) {
  if (loading.value) return '加载中'
  return value === null ? '不可用' : String(value)
}

async function fetchTodos() {
  const currentRequestId = ++requestId
  const scene = activeSceneValue.value || undefined
  loading.value = true
  error.value = ''
  stats.value = null
  try {
    const response = await getTaskTodoStats(scene ? { scene } : undefined)
    if (currentRequestId !== requestId) return
    if (response.success && response.data) {
      stats.value = response.data
    } else {
      stats.value = null
      error.value = response.message || '获取任务待办失败'
    }
  } catch {
    if (currentRequestId !== requestId) return
    stats.value = null
    error.value = '网络异常或服务器不可用'
  } finally {
    if (currentRequestId === requestId) loading.value = false
  }
}

function handleSceneChange() {
  void fetchTodos()
}

function openTodo(todo: TaskTodo, value: number | null) {
  if (loading.value || !stats.value || value === null) {
    message.warning('任务待办暂不可用，请稍后重试')
    return
  }
  if (value === 0) {
    message.info('没有待处理的事项')
    return
  }
  const query: Record<string, string> = { todo, as_of: stats.value.as_of }
  if (activeSceneValue.value) query.scene = activeSceneValue.value
  void router.push({ path: '/dashboard/tasks/my', query })
}

onMounted(() => void fetchTodos())
</script>

<style scoped>
.task-todos {
  margin: 16px 0;
  padding: 18px 0;
  border-block: 1px solid rgba(0, 0, 0, 0.08);
}
.task-todos header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 16px;
  margin-bottom: 14px;
}
.task-todos__tools {
  display: flex;
  align-items: center;
  gap: 8px;
}
.task-todos__tools label {
  color: rgba(29, 29, 31, 0.55);
  font-size: 12px;
}
.task-todos__tools select {
  height: 30px;
  padding: 0 28px 0 9px;
  border: 1px solid rgba(0, 0, 0, 0.12);
  border-radius: 6px;
  background: #fff;
  color: #1d1d1f;
  font: inherit;
}
.task-todos header span {
  color: rgba(29, 29, 31, 0.55);
  font-size: 12px;
}
.task-todos h2 {
  margin: 2px 0 0;
  color: #1d1d1f;
  font-size: 17px;
  line-height: 22px;
  font-weight: 600;
}
.task-todos button {
  font: inherit;
}
.task-todos header button,
.task-todos__error button {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border: 0;
  background: transparent;
  color: #007aff;
  cursor: pointer;
}
.task-todos button:disabled {
  cursor: wait;
  opacity: 0.6;
}
.task-todos__grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 240px), 1fr));
  gap: 10px;
}
.task-todos__grid > button {
  display: grid;
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
.task-todos__grid > button:hover {
  border-color: rgba(0, 122, 255, 0.28);
  background: rgba(0, 122, 255, 0.035);
}
.task-todos__grid strong {
  color: #1d1d1f;
  font-size: 22px;
  font-weight: 600;
}
.task-todos__error {
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
.task-todos__empty {
  margin: 12px 0 0;
  color: rgba(29, 29, 31, 0.6);
  font-size: 14px;
}
</style>
