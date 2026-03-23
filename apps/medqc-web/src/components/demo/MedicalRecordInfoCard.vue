<!--
  病历信息卡片组件
  用于 LLMQCDemoEnhanced 页面，展示已选病历的关键信息
-->
<template>
  <a-card
    title="病历信息"
    :bordered="false"
    class="medical-record-info-card"
  >
    <template #extra>
      <a-tag
        v-if="documentInfo"
        color="blue"
      >
        <FileTextOutlined />
        {{ documentInfo.type || documentInfo.title }}
      </a-tag>
      <a-tag
        v-else
        color="default"
      >
        未选择文书
      </a-tag>
    </template>

    <a-descriptions
      :column="2"
      bordered
      size="small"
    >
      <a-descriptions-item label="患者姓名">
        <span class="font-medium">{{ recordInfo.patientName || '-' }}</span>
      </a-descriptions-item>
      
      <a-descriptions-item label="年龄/性别">
        {{ recordInfo.age || '-' }}岁 / {{ recordInfo.gender || '-' }}
      </a-descriptions-item>
      
      <a-descriptions-item label="科室">
        {{ recordInfo.department || '-' }}
      </a-descriptions-item>
      
      <a-descriptions-item label="住院号">
        {{ recordInfo.admissionNumber || '-' }}
      </a-descriptions-item>
      
      <a-descriptions-item label="床号">
        {{ recordInfo.bedNumber || '-' }}
      </a-descriptions-item>
      
      <a-descriptions-item label="入院时间">
        {{ formatDate(recordInfo.admissionTime) }}
      </a-descriptions-item>
      
      <a-descriptions-item label="记录时间">
        {{ formatDate(recordInfo.recordTime) }}
      </a-descriptions-item>
      
      <a-descriptions-item
        label="初步诊断"
        :span="2"
      >
        <span class="text-gray-700">{{ recordInfo.diagnosis || '-' }}</span>
      </a-descriptions-item>
    </a-descriptions>
  </a-card>
</template>

<script setup lang="ts">
import { FileTextOutlined } from '@ant-design/icons-vue'

/**
 * 病历信息接口
 */
interface RecordInfo {
  patientName?: string
  age?: number
  gender?: string
  department?: string
  admissionNumber?: string
  bedNumber?: string
  admissionTime?: string
  recordTime?: string
  diagnosis?: string
}

/**
 * 文书信息接口
 */
interface DocumentInfo {
  type?: string
  title?: string
}

/**
 * 组件 Props
 */
interface Props {
  recordInfo: RecordInfo
  documentInfo?: DocumentInfo | null
}

const props = defineProps<Props>()

/**
 * 格式化日期
 */
const formatDate = (dateStr?: string) => {
  if (!dateStr) return '-'
  
  try {
    const date = new Date(dateStr)
    if (isNaN(date.getTime())) return dateStr
    
    return date.toLocaleString('zh-CN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit'
    })
  } catch {
    return dateStr
  }
}
</script>

<style scoped>
.medical-record-info-card {
  margin-bottom: 16px;
}

.medical-record-info-card :deep(.ant-descriptions-item-label) {
  font-weight: 500;
  background-color: #fafafa;
}

.medical-record-info-card :deep(.ant-descriptions-item-content) {
  color: #262626;
}
</style>

