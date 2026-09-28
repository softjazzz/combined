<template>
  <a-drawer
    :open="open"
    :width="'min(760px, 100vw)'"
    title="任务分析"
    placement="right"
    class="task-analysis-drawer"
    :body-style="{ padding: 0 }"
    @close="closeDrawer"
  >
    <div class="task-analysis-drawer__body">
      <div v-if="loading" class="task-analysis-drawer__state" data-testid="task-analysis-loading">
        <a-skeleton active :paragraph="{ rows: 7 }" />
      </div>

      <div v-else-if="error" class="task-analysis-drawer__error" role="alert">
        <div>
          <strong>任务分析暂不可用</strong>
          <span>{{ error }}</span>
        </div>
        <a-button data-testid="retry-task-analysis" @click="void loadAnalysis()">
          <RotateCw :size="15" aria-hidden="true" />
          重试
        </a-button>
      </div>

      <template v-else-if="analysis">
        <header class="task-analysis-drawer__header">
          <div>
            <span>单任务口径</span>
            <h3>{{ analysis.task.task_name }}</h3>
            <p>{{ analysis.task.task_number }} · {{ sceneLabel(analysis.task.scene) }}</p>
          </div>
          <a-button type="primary" ghost data-testid="open-task-detail" @click="openTaskDetail">
            <Eye :size="15" aria-hidden="true" />
            查看任务详情
          </a-button>
        </header>

        <section class="task-analysis-drawer__metrics" aria-label="任务汇总">
          <div>
            <span>任务病历</span>
            <strong>{{ analysis.summary.total_records }}</strong>
            <small>来自任务病历关联</small>
          </div>
          <div>
            <span>处理完成</span>
            <strong>{{ analysis.summary.completed_records }}</strong>
            <small>{{ formatRate(analysis.summary.completion_rate) }}</small>
          </div>
          <div>
            <span>任务评分均值</span>
            <strong>{{ nullableNumber(analysis.summary.average_score) }}</strong>
            <small>未知 {{ analysis.summary.score_unknown_count }} 份</small>
          </div>
          <div>
            <span>任务缺陷总数</span>
            <strong>{{ nullableNumber(analysis.summary.total_defect_count) }}</strong>
            <small>未知 {{ analysis.summary.defect_unknown_count }} 份</small>
          </div>
        </section>

        <section class="task-analysis-drawer__section" aria-labelledby="task-status-title">
          <div class="task-analysis-drawer__section-title">
            <div>
              <span>处理状态</span>
              <h4 id="task-status-title">任务病历分布</h4>
            </div>
          </div>
          <div class="task-analysis-drawer__status-list">
            <div v-for="item in statusItems" :key="item.key">
              <span>{{ item.label }}</span>
              <strong>{{ item.count }}</strong>
            </div>
          </div>
        </section>

        <section class="task-analysis-drawer__section" aria-labelledby="task-assignee-title">
          <div class="task-analysis-drawer__section-title">
            <div>
              <span>受领人统计</span>
              <h4 id="task-assignee-title">分配与完成</h4>
            </div>
            <small>完成仅认质控员显式提交</small>
          </div>
          <a-empty v-if="!analysis.assignees.length" description="任务暂无病历分配" />
          <div v-else class="task-analysis-drawer__assignees">
            <div v-for="row in analysis.assignees" :key="JSON.stringify(row.assignee_id)">
              <div>
                <strong>{{ row.assignee_name || (row.assignee_id ? '姓名未知' : '未分配') }}</strong>
                <span v-if="row.assignee_id">{{ row.assignee_id }}</span>
              </div>
              <p>{{ row.completed_records }} / {{ row.total_records }}</p>
              <span>{{ formatRate(row.completion_rate) }}</span>
            </div>
          </div>
        </section>
      </template>
    </div>
  </a-drawer>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { Eye, RotateCw } from 'lucide-vue-next'
import { getTaskAnalysis, type TaskAnalysis } from '@/api/taskAnalysis'
import { useAuthStore } from '@/stores/auth'

const props = defineProps<{
  open: boolean
  taskId?: string | null
}>()

const emit = defineEmits<{
  'update:open': [value: boolean]
  'view-detail': [taskId: string]
}>()

const analysis = ref<TaskAnalysis | null>(null)
const authStore = useAuthStore()
const loading = ref(false)
const error = ref('')
let requestSequence = 0

const statusItems = computed(() => {
  if (!analysis.value) return []
  const labels = {
    pending: '待处理',
    in_progress: '处理中',
    completed: '已完成',
    skipped: '已跳过',
    unknown: '未知状态',
  }
  return Object.entries(labels).map(([key, label]) => ({
    key,
    label,
    count: analysis.value?.status_counts[key as keyof typeof labels] ?? 0,
  }))
})

function sceneLabel(scene: string | null): string {
  return ({ running: '运行病历', final: '终末病历', outpatient: '门急诊病历' } as Record<string, string>)[scene || ''] || '场景未知'
}

function formatRate(value: number): string {
  return `${value.toFixed(2).replace(/\.00$/, '')}%`
}

function nullableNumber(value: number | null): string {
  return value === null ? '未知' : String(value)
}

async function loadAnalysis(): Promise<void> {
  const taskId = props.taskId?.trim()
  if (!props.open || !taskId) return
  const sequence = ++requestSequence
  loading.value = true
  error.value = ''
  analysis.value = null
  const result = await getTaskAnalysis(taskId)
  if (sequence !== requestSequence || !props.open || props.taskId?.trim() !== taskId) return
  loading.value = false
  if (!result.success || !result.data) {
    error.value = result.message || '任务分析暂不可用'
    return
  }
  analysis.value = result.data
}

function closeDrawer(): void {
  requestSequence += 1
  loading.value = false
  emit('update:open', false)
}

function openTaskDetail(): void {
  if (analysis.value) emit('view-detail', analysis.value.task.id)
}

watch(
  () => [props.open, props.taskId, authStore.user?.id] as const,
  ([open, taskId]) => {
    requestSequence += 1
    analysis.value = null
    error.value = ''
    loading.value = false
    if (open && taskId?.trim()) void loadAnalysis()
  },
  { immediate: true },
)

onBeforeUnmount(() => {
  requestSequence += 1
})
</script>

<style scoped>
.task-analysis-drawer__body {
  min-height: 100%;
  padding: 20px;
  color: #1d1d1f;
  background: #f5f5f7;
  font-family: 'Source Han Sans SC', 'Microsoft YaHei UI', 'PingFang SC', sans-serif;
}

.task-analysis-drawer__state,
.task-analysis-drawer__error {
  padding: 24px;
  border: 1px solid rgba(0, 0, 0, .08);
  border-radius: 12px;
  background: #fff;
}

.task-analysis-drawer__error {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.task-analysis-drawer__error div,
.task-analysis-drawer__header div,
.task-analysis-drawer__section-title div {
  display: grid;
  gap: 4px;
}

.task-analysis-drawer__error span,
.task-analysis-drawer__header span,
.task-analysis-drawer__header p,
.task-analysis-drawer__section-title span,
.task-analysis-drawer__section-title small,
.task-analysis-drawer__metrics small,
.task-analysis-drawer__assignees span {
  margin: 0;
  color: rgba(29, 29, 31, .6);
  font-size: 13px;
  line-height: 20px;
}

.task-analysis-drawer__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 20px;
  padding: 20px;
  border: 1px solid rgba(255, 255, 255, .85);
  border-radius: 12px;
  background: rgba(255, 255, 255, .72);
  box-shadow: 0 4px 18px rgba(38, 58, 86, .04);
}

.task-analysis-drawer__header h3,
.task-analysis-drawer__section-title h4 {
  margin: 0;
  font-size: 17px;
  line-height: 22px;
  font-weight: 600;
}

.task-analysis-drawer__metrics {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
  margin-top: 12px;
}

.task-analysis-drawer__metrics > div {
  display: grid;
  min-width: 0;
  gap: 5px;
  padding: 14px;
  border: 1px solid rgba(0, 0, 0, .08);
  border-radius: 8px;
  background: #fff;
}

.task-analysis-drawer__metrics > div > span {
  font-size: 14px;
  line-height: 22px;
}

.task-analysis-drawer__metrics strong {
  color: #007aff;
  font-size: 22px;
  line-height: 28px;
  font-weight: 600;
}

.task-analysis-drawer__section {
  margin-top: 12px;
  padding: 18px 20px;
  border: 1px solid rgba(0, 0, 0, .08);
  border-radius: 12px;
  background: #fff;
}

.task-analysis-drawer__section-title {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 14px;
}

.task-analysis-drawer__status-list {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 8px;
}

.task-analysis-drawer__status-list > div {
  display: grid;
  gap: 4px;
  padding: 10px;
  border-radius: 8px;
  background: #f5f5f7;
  text-align: center;
}

.task-analysis-drawer__status-list span {
  color: rgba(29, 29, 31, .6);
  font-size: 13px;
}

.task-analysis-drawer__status-list strong {
  font-size: 18px;
}

.task-analysis-drawer__assignees {
  display: grid;
}

.task-analysis-drawer__assignees > div {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 80px 64px;
  align-items: center;
  gap: 12px;
  min-height: 52px;
  border-top: 1px solid rgba(0, 0, 0, .06);
}

.task-analysis-drawer__assignees > div:first-child {
  border-top: 0;
}

.task-analysis-drawer__assignees div > div {
  display: grid;
}

.task-analysis-drawer__assignees p {
  margin: 0;
  text-align: right;
}

.task-analysis-drawer__assignees > div > span {
  text-align: right;
}

@media (max-width: 640px) {
  .task-analysis-drawer__metrics {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .task-analysis-drawer__status-list {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .task-analysis-drawer__header,
  .task-analysis-drawer__section-title {
    align-items: stretch;
    flex-direction: column;
  }
}
</style>
