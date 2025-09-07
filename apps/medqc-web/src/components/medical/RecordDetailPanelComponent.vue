<template>
  <div class="record-detail-panel">
    <!-- 基本信息 -->
    <a-card title="基本信息" class="mb-6" :bordered="false">
      <a-descriptions :column="2" bordered>
        <a-descriptions-item label="患者姓名">
          {{ record.patient_name }}
        </a-descriptions-item>
        <a-descriptions-item label="年龄">
          {{ record.patient_age }}岁
        </a-descriptions-item>
        <a-descriptions-item label="性别">
          {{ record.patient_gender === 'M' ? '男' : record.patient_gender === 'F' ? '女' : '未知' }}
        </a-descriptions-item>
        <a-descriptions-item label="科室">
          {{ record.department }}
        </a-descriptions-item>
        <a-descriptions-item label="记录类型">
          {{ getRecordTypeText(record.record_type) }}
        </a-descriptions-item>
        <a-descriptions-item label="入院日期">
          {{ record.admission_date }}
        </a-descriptions-item>
        <a-descriptions-item label="状态">
          <a-tag :color="getStatusColor(record.status)">
            {{ getStatusText(record.status) }}
          </a-tag>
        </a-descriptions-item>
        <a-descriptions-item label="创建时间">
          {{ formatDateTime(record.created_at) }}
        </a-descriptions-item>
      </a-descriptions>
    </a-card>

    <!-- 质控评分 -->
    <a-card 
      v-if="record.qc_score !== null && record.qc_score !== undefined" 
      title="质控评分" 
      class="mb-6" 
      :bordered="false"
    >
      <div class="flex items-center justify-between mb-4">
        <div class="text-center">
          <div class="text-3xl font-bold mb-2" :style="{ color: getScoreColor(record.qc_score) }">
            {{ record.qc_score }}分
          </div>
          <a-tag :color="getGradeColor(record.qc_grade)" size="large">
            {{ record.qc_grade }}级
          </a-tag>
        </div>
        
        <div class="flex-1 ml-8">
          <a-progress 
            :percent="record.qc_score" 
            :stroke-color="getScoreColor(record.qc_score)"
            :stroke-width="8"
          />
        </div>
      </div>
      
      <div class="text-sm text-gray-600">
        <p v-if="record.qc_grade === 'A'" class="text-green-600">
          ✅ 优秀：病案记录完整、规范，符合质控标准
        </p>
        <p v-else-if="record.qc_grade === 'B'" class="text-orange-600">
          ⚠️ 良好：病案记录基本符合要求，有小部分需要改进
        </p>
        <p v-else-if="record.qc_grade === 'C'" class="text-red-600">
          ❌ 需改进：病案记录存在明显问题，需要重点关注和改进
        </p>
      </div>
    </a-card>

    <!-- 病案内容 -->
    <a-card title="病案内容" class="mb-6" :bordered="false">
      <template #extra>
        <a-space>
          <a-button 
            type="text" 
            :icon="h(CopyOutlined)"
            @click="copyContent"
          >
            复制
          </a-button>
          <a-button 
            type="text" 
            :icon="h(DownloadOutlined)"
            @click="downloadContent"
          >
            下载
          </a-button>
        </a-space>
      </template>
      
      <div class="bg-gray-50 rounded-lg p-4 max-h-96 overflow-y-auto">
        <pre class="whitespace-pre-wrap text-sm text-gray-800 font-mono">{{ record.content }}</pre>
      </div>
    </a-card>

    <!-- 文件信息 -->
    <a-card 
      v-if="record.file_name" 
      title="附件信息" 
      class="mb-6" 
      :bordered="false"
    >
      <div class="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
        <div class="flex items-center space-x-3">
          <div class="text-2xl">
            {{ getFileIcon(record.file_name) }}
          </div>
          <div>
            <div class="font-medium">{{ record.file_name }}</div>
            <div class="text-sm text-gray-500">
              {{ record.file_size ? formatFileSize(record.file_size) : '未知大小' }}
            </div>
          </div>
        </div>
        
        <a-button 
          v-if="record.file_url"
          type="primary"
          ghost
          @click="downloadFile"
        >
          <template #icon>
            <DownloadOutlined />
          </template>
          下载文件
        </a-button>
      </div>
    </a-card>

    <!-- 操作历史 -->
    <a-card title="操作历史" :bordered="false">
      <a-timeline>
        <a-timeline-item color="green">
          <template #dot>
            <ClockCircleOutlined />
          </template>
          <div>
            <div class="font-medium">记录创建</div>
            <div class="text-sm text-gray-500">{{ formatDateTime(record.created_at) }}</div>
          </div>
        </a-timeline-item>
        
        <a-timeline-item 
          v-if="record.status === 'analyzing'" 
          color="blue"
        >
          <template #dot>
            <LoadingOutlined />
          </template>
          <div>
            <div class="font-medium">正在分析</div>
            <div class="text-sm text-gray-500">AI质控分析进行中...</div>
          </div>
        </a-timeline-item>
        
        <a-timeline-item 
          v-if="record.status === 'completed'" 
          color="green"
        >
          <template #dot>
            <CheckCircleOutlined />
          </template>
          <div>
            <div class="font-medium">分析完成</div>
            <div class="text-sm text-gray-500">{{ formatDateTime(record.updated_at) }}</div>
          </div>
        </a-timeline-item>
        
        <a-timeline-item 
          v-if="record.status === 'failed'" 
          color="red"
        >
          <template #dot>
            <CloseCircleOutlined />
          </template>
          <div>
            <div class="font-medium">分析失败</div>
            <div class="text-sm text-gray-500">{{ formatDateTime(record.updated_at) }}</div>
          </div>
        </a-timeline-item>
      </a-timeline>
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { h } from 'vue'
import { message } from 'ant-design-vue'
import {
  CopyOutlined,
  DownloadOutlined,
  ClockCircleOutlined,
  LoadingOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined
} from '@ant-design/icons-vue'
import type { MedicalRecord, MedicalRecordStatus } from '../../types/medical-records'

// 组件属性
interface Props {
  record: MedicalRecord
}

const props = defineProps<Props>()

// 组件事件
interface Emits {
  (e: 'close'): void
}

const emit = defineEmits<Emits>()

// 方法
const getRecordTypeText = (type: string): string => {
  const typeMap = {
    'inpatient': '住院记录',
    'outpatient': '门诊记录',
    'emergency': '急诊记录'
  }
  return typeMap[type as keyof typeof typeMap] || type
}

const getStatusColor = (status: MedicalRecordStatus): string => {
  const colorMap = {
    'pending': 'orange',
    'analyzing': 'blue',
    'completed': 'green',
    'failed': 'red'
  }
  return colorMap[status] || 'default'
}

const getStatusText = (status: MedicalRecordStatus): string => {
  const textMap = {
    'pending': '待分析',
    'analyzing': '分析中',
    'completed': '已完成',
    'failed': '分析失败'
  }
  return textMap[status] || status
}

const getScoreColor = (score: number): string => {
  if (score >= 90) return '#52c41a'
  if (score >= 80) return '#faad14'
  if (score >= 70) return '#fa8c16'
  return '#f5222d'
}

const getGradeColor = (grade?: string): string => {
  const gradeColorMap = {
    'A': 'green',
    'B': 'orange',
    'C': 'red'
  }
  return gradeColorMap[grade as keyof typeof gradeColorMap] || 'default'
}

const formatDateTime = (dateTime: string): string => {
  return new Date(dateTime).toLocaleString()
}

const formatFileSize = (bytes: number): string => {
  if (bytes === 0) return '0 Bytes'
  
  const k = 1024
  const sizes = ['Bytes', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}

const getFileIcon = (fileName: string): string => {
  const ext = fileName.split('.').pop()?.toLowerCase()
  
  switch (ext) {
    case 'pdf':
      return '📄'
    case 'doc':
    case 'docx':
      return '📝'
    case 'txt':
      return '📋'
    case 'jpg':
    case 'jpeg':
    case 'png':
      return '🖼️'
    default:
      return '📁'
  }
}

const copyContent = async () => {
  try {
    await navigator.clipboard.writeText(props.record.content)
    message.success('内容已复制到剪贴板')
  } catch (error) {
    message.error('复制失败')
  }
}

const downloadContent = () => {
  const blob = new Blob([props.record.content], { type: 'text/plain;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `病案_${props.record.patient_name}_${props.record.admission_date}.txt`
  link.click()
  URL.revokeObjectURL(url)
  message.success('下载已开始')
}

const downloadFile = () => {
  if (props.record.file_url) {
    // TODO: 实现文件下载
    message.info('文件下载功能开发中...')
  }
}
</script>

<style scoped>
.record-detail-panel {
  @apply space-y-6;
}

:deep(.ant-descriptions-item-label) {
  @apply font-medium text-gray-700 bg-gray-50;
}

:deep(.ant-descriptions-item-content) {
  @apply text-gray-900;
}

:deep(.ant-timeline-item-content) {
  @apply ml-2;
}
</style> 