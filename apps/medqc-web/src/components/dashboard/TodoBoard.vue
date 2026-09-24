<template>
  <div class="todo-board">
    <div class="board-header">
      <h3 class="board-title">
        <ThunderboltOutlined class="title-icon" />
        我的待办
      </h3>
      <a-segmented
        v-model:value="activeScene"
        :options="sceneOptions"
        size="small"
      />
    </div>

    <p v-if="allEmpty" class="board-status" role="status" data-testid="todo-board-empty">
      没有待处理事项
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
            class="stat-item clickable"
            @click="openTodo(todoData.task_stats?.in_progress, '/dashboard/tasks/my', { status: 'in_progress' })"
          >
            <span class="stat-number text-blue-600">{{ formatCount(todoData.task_stats?.in_progress) }}</span>
            <span class="stat-label">进行中</span>
          </div>
          <div class="stat-divider" />
          <div
            class="stat-item clickable"
            @click="openTodo(todoData.task_stats?.not_started, '/dashboard/tasks/my', { status: 'not_started' })"
          >
            <span class="stat-number text-orange-500">{{ formatCount(todoData.task_stats?.not_started) }}</span>
            <span class="stat-label">未开始</span>
          </div>
          <div class="stat-divider" />
          <div
            class="stat-item clickable"
            @click="openTodo(todoData.task_stats?.countdown, '/dashboard/tasks/my', { countdown: 'true' })"
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
            class="stat-item clickable"
            @click="openTodo(todoData.defect_stats?.clinical_appeals, '/dashboard/qc/appeals')"
          >
            <span class="stat-number text-purple-600">{{ formatCount(todoData.defect_stats?.clinical_appeals) }}</span>
            <span class="stat-label">临床申诉</span>
          </div>
          <div class="stat-divider" />
          <div
            class="stat-item clickable"
            @click="openTodo(todoData.defect_stats?.pending_review, '/dashboard/records/final', { status: 'pending_review' })"
          >
            <span class="stat-number text-orange-500">{{ formatCount(todoData.defect_stats?.pending_review) }}</span>
            <span class="stat-label">待审核</span>
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
            class="stat-item clickable"
            @click="openTodo(todoData.record_stats?.pending_review, '/dashboard/records/final', { status: 'pending' })"
          >
            <span class="stat-number text-blue-600">{{ formatCount(todoData.record_stats?.pending_review) }}</span>
            <span class="stat-label">待审核</span>
          </div>
          <div class="stat-divider" />
          <div
            class="stat-item clickable"
            @click="openTodo(todoData.record_stats?.pending_recheck, '/dashboard/records/final', { status: 'recheck' })"
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
import { computed, ref } from 'vue'
import { message } from 'ant-design-vue'
import { useRouter } from 'vue-router'
import type { TodoStats } from '@/api/dashboard'
import {
  ThunderboltOutlined,
  ProjectOutlined,
  ExclamationCircleOutlined,
  FileTextOutlined,
} from '@ant-design/icons-vue'

const props = defineProps<{
  todoData: Partial<TodoStats>
}>()

const router = useRouter()
const activeScene = ref('全部')
const sceneOptions = ['全部', '终末', '运行', '门急诊']

const counts = computed(() => [
  props.todoData.task_stats?.in_progress,
  props.todoData.task_stats?.not_started,
  props.todoData.task_stats?.countdown,
  props.todoData.defect_stats?.clinical_appeals,
  props.todoData.defect_stats?.pending_review,
  props.todoData.record_stats?.pending_review,
  props.todoData.record_stats?.pending_recheck,
])
const noData = computed(() => counts.value.every((value) => !Number.isFinite(value)))
const allEmpty = computed(() => counts.value.every((value) => value === 0))

function formatCount(value: number | undefined) {
  return Number.isFinite(value) ? value : '不可用'
}

function openTodo(value: number | undefined, path: string, query?: Record<string, string>) {
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
