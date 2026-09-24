<template>
  <div class="todo-board">
    <div class="board-header">
      <h3 class="board-title">
        <ThunderboltOutlined class="title-icon" />
        我的待办
      </h3>
      <span class="scene-label">全场景待办</span>
    </div>

    <p v-if="allEmpty" class="board-status" role="status" data-testid="todo-board-empty">
      已接入待办：没有待处理事项
    </p>
    <p v-else-if="noData" class="board-status" role="alert" data-testid="todo-board-unavailable">
      待办数据暂不可用
    </p>

    <div class="board-grid">
      <!-- 任务维度 -->
      <div class="dimension-card task-card">
        <div class="card-header">
          <ProjectOutlined class="dim-icon" />
          <span>任务</span>
        </div>
        <div class="card-body">
          <div
            class="stat-item"
            :class="{ clickable: canOpenTask(todoData.task_stats?.in_progress) }"
            @click="openTaskTodo(todoData.task_stats?.in_progress, 'in_progress')"
          >
            <span class="stat-number text-blue-600">{{ formatCount(todoData.task_stats?.in_progress) }}</span>
            <span class="stat-label">进行中</span>
          </div>
          <div class="stat-divider" />
          <div
            class="stat-item"
            :class="{ clickable: canOpenTask(todoData.task_stats?.not_started) }"
            @click="openTaskTodo(todoData.task_stats?.not_started, 'assigned')"
          >
            <span class="stat-number text-orange-500">{{ formatCount(todoData.task_stats?.not_started) }}</span>
            <span class="stat-label">未开始</span>
          </div>
          <div class="stat-divider" />
          <div
            class="stat-item"
            :class="{ clickable: canOpenTask(todoData.task_stats?.countdown) }"
            @click="openTaskTodo(todoData.task_stats?.countdown, 'due_soon')"
          >
            <span class="stat-number text-red-500">{{ formatCount(todoData.task_stats?.countdown) }}</span>
            <span class="stat-label">即将超时</span>
          </div>
        </div>
      </div>

      <!-- 缺陷维度 -->
      <div class="dimension-card defect-card">
        <div class="card-header">
          <ExclamationCircleOutlined class="dim-icon" />
          <span>缺陷</span>
        </div>
        <div class="card-body">
          <div
            class="stat-item"
            :class="{ clickable: canOpen(todoData.defect_stats?.clinical_appeals) }"
            @click="openTodo(todoData.defect_stats?.clinical_appeals, '/dashboard/qc/appeals', { todo: 'review' })"
          >
            <span class="stat-number text-purple-600">{{ formatCount(todoData.defect_stats?.clinical_appeals) }}</span>
            <span class="stat-label">临床申诉</span>
          </div>
          <div class="stat-divider" />
          <div
            class="stat-item"
            @click="openUnavailable(todoData.defect_stats?.pending_review)"
          >
            <span class="stat-number text-orange-500">{{ formatCount(todoData.defect_stats?.pending_review) }}</span>
            <span class="stat-label">人工缺陷待审核</span>
          </div>
        </div>
      </div>

      <!-- 病历维度 -->
      <div class="dimension-card record-card">
        <div class="card-header">
          <FileTextOutlined class="dim-icon" />
          <span>病历</span>
        </div>
        <div class="card-body">
          <div
            class="stat-item"
            @click="openUnavailable(todoData.record_stats?.pending_review)"
          >
            <span class="stat-number text-blue-600">{{ formatCount(todoData.record_stats?.pending_review) }}</span>
            <span class="stat-label">待审核</span>
          </div>
          <div class="stat-divider" />
          <div
            class="stat-item"
            @click="openUnavailable(todoData.record_stats?.pending_recheck)"
          >
            <span class="stat-number text-cyan-600">{{ formatCount(todoData.record_stats?.pending_recheck) }}</span>
            <span class="stat-label">待复审</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { message } from 'ant-design-vue'
import { useRouter } from 'vue-router'
import {
  ThunderboltOutlined,
  ProjectOutlined,
  ExclamationCircleOutlined,
  FileTextOutlined,
} from '@ant-design/icons-vue'

type Count = number | null | undefined
type TodoBoardData = {
  task_stats?: { in_progress?: Count; not_started?: Count; countdown?: Count; as_of?: string | null }
  defect_stats?: { clinical_appeals?: Count; pending_review?: Count }
  record_stats?: { pending_review?: Count; pending_recheck?: Count }
}

const props = defineProps<{ todoData: TodoBoardData }>()

const router = useRouter()
const deliveredCounts = computed(() => [
  props.todoData.task_stats?.in_progress,
  props.todoData.task_stats?.not_started,
  props.todoData.task_stats?.countdown,
  props.todoData.defect_stats?.clinical_appeals,
])
const noData = computed(() => deliveredCounts.value.every((value) => !Number.isFinite(value)))
const allEmpty = computed(() => deliveredCounts.value.every((value) => value === 0))

function formatCount(value: Count) {
  return Number.isFinite(value) ? value : '不可用'
}

function canOpen(value: Count) {
  return typeof value === 'number' && Number.isFinite(value) && value > 0
}

function canOpenTask(value: Count) {
  return canOpen(value) && Boolean(props.todoData.task_stats?.as_of)
}

function openTaskTodo(value: Count, todo: 'in_progress' | 'assigned' | 'due_soon') {
  if (value === 0) {
    message.info('没有待处理事项')
    return
  }
  const asOf = props.todoData.task_stats?.as_of
  if (!asOf) {
    message.warning('任务待办快照暂不可用，请稍后重试')
    return
  }
  openTodo(value, '/dashboard/tasks/my', { todo, as_of: asOf })
}

function openUnavailable(value: Count) {
  if (value === 0) {
    message.info('没有待处理事项')
    return
  }
  message.warning('待办数据暂不可用，请稍后重试')
}

function openTodo(value: Count, path: string, query?: Record<string, string>) {
  if (!Number.isFinite(value)) {
    message.warning('待办数据暂不可用，请稍后重试')
    return
  }
  if (value === 0) {
    message.info('没有待处理事项')
    return
  }
  void router.push({ path, query })
}
</script>

<style scoped>
.todo-board {
  background: white;
  border-radius: 16px;
  border: 1px solid #f0f0f0;
  padding: 20px 24px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.04);
}
.board-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}
.scene-label {
  color: rgba(29, 29, 31, 0.6);
  font-size: 13px;
}
.board-title {
  font-size: 16px;
  font-weight: 700;
  color: #1a1a1a;
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0;
}
.title-icon { color: #2b6cf6; }
.board-status {
  margin: 0 0 12px;
  color: rgba(29, 29, 31, 0.6);
  font-size: 14px;
}

.board-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
}

.dimension-card {
  border-radius: 12px;
  padding: 16px;
  border: 1px solid #f5f5f5;
  transition: all 0.2s;
}
.dimension-card:hover {
  box-shadow: 0 4px 12px rgba(0,0,0,0.06);
  border-color: #e6f0ff;
}
.task-card { background: linear-gradient(135deg, #f0f5ff 0%, #e6f7ff 100%); }
.defect-card { background: linear-gradient(135deg, #fff7e6 0%, #fff1f0 100%); }
.record-card { background: linear-gradient(135deg, #f6ffed 0%, #e6fffb 100%); }

.card-header {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 600;
  color: #666;
  margin-bottom: 12px;
}
.dim-icon { font-size: 14px; }

.card-body {
  display: flex;
  align-items: center;
  gap: 0;
}

.stat-item {
  flex: 1;
  text-align: center;
}
.stat-item.clickable {
  cursor: pointer;
  border-radius: 8px;
  padding: 4px;
  transition: background 0.2s;
}
.stat-item.clickable:hover {
  background: rgba(255,255,255,0.6);
}
.stat-number {
  display: block;
  font-size: 24px;
  font-weight: 800;
  line-height: 1.2;
}
.stat-label {
  display: block;
  font-size: 11px;
  color: #999;
  margin-top: 2px;
}
.stat-divider {
  width: 1px;
  height: 32px;
  background: rgba(0,0,0,0.06);
  flex-shrink: 0;
}
</style>
