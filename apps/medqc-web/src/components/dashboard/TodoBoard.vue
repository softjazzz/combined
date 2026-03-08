<template>
  <div class="todo-board">
    <div class="board-header">
      <h3 class="board-title">
        <ThunderboltOutlined class="title-icon" />
        我的待办
      </h3>
      <a-segmented v-model:value="activeScene" :options="sceneOptions" size="small" />
    </div>

    <div class="board-grid">
      <!-- 任务维度 -->
      <div class="dimension-card task-card">
        <div class="card-header">
          <ProjectOutlined class="dim-icon" />
          <span>任务</span>
        </div>
        <div class="card-body">
          <div class="stat-item clickable" @click="navigate('/dashboard/tasks/my', { status: 'in_progress' })">
            <span class="stat-number text-blue-600">{{ todoData.task_stats?.in_progress || 0 }}</span>
            <span class="stat-label">进行中</span>
          </div>
          <div class="stat-divider"></div>
          <div class="stat-item clickable" @click="navigate('/dashboard/tasks/my', { status: 'not_started' })">
            <span class="stat-number text-orange-500">{{ todoData.task_stats?.not_started || 0 }}</span>
            <span class="stat-label">未开始</span>
          </div>
          <div class="stat-divider"></div>
          <div class="stat-item clickable" @click="navigate('/dashboard/tasks/my', { countdown: true })">
            <span class="stat-number text-red-500">{{ todoData.task_stats?.countdown || 0 }}</span>
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
          <div class="stat-item clickable" @click="navigate('/dashboard/qc/appeals')">
            <span class="stat-number text-purple-600">{{ todoData.defect_stats?.clinical_appeals || 0 }}</span>
            <span class="stat-label">临床申诉</span>
          </div>
          <div class="stat-divider"></div>
          <div class="stat-item clickable" @click="navigate('/dashboard/records/final', { status: 'pending_review' })">
            <span class="stat-number text-orange-500">{{ todoData.defect_stats?.pending_review || 0 }}</span>
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
          <div class="stat-item clickable" @click="navigate('/dashboard/records/final', { status: 'pending' })">
            <span class="stat-number text-blue-600">{{ todoData.record_stats?.pending_review || 0 }}</span>
            <span class="stat-label">待审核</span>
          </div>
          <div class="stat-divider"></div>
          <div class="stat-item clickable" @click="navigate('/dashboard/records/final', { status: 'recheck' })">
            <span class="stat-number text-cyan-600">{{ todoData.record_stats?.pending_recheck || 0 }}</span>
            <span class="stat-label">待复审</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import {
  ThunderboltOutlined,
  ProjectOutlined,
  ExclamationCircleOutlined,
  FileTextOutlined,
} from '@ant-design/icons-vue'

const props = defineProps<{
  todoData: Record<string, any>
}>()

const router = useRouter()
const activeScene = ref('全部')
const sceneOptions = ['全部', '终末', '运行', '门急诊']

const navigate = (path: string, query?: Record<string, any>) => {
  router.push({ path, query: query as any })
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
.title-icon { color: #1677ff; }

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
