<template>
  <div class="enhanced-record-detail">
    <!-- 页面头部 -->
    <div class="detail-header">
      <div class="header-content">
        <div class="header-left">
          <a-button type="text" @click="$emit('back')" class="back-btn">
            <ArrowLeftOutlined />
            返回
          </a-button>
          <div class="title-section">
            <h1 class="record-title">{{ record.record_name || '医疗记录详情' }}</h1>
            <div class="record-meta">
              <a-tag :color="getStatusColor(record.status)">{{ getStatusText(record.status) }}</a-tag>
              <span class="record-id">ID: {{ record.record_number }}</span>
              <span class="update-time">更新于 {{ formatDateTime(record.updated_at) }}</span>
            </div>
          </div>
        </div>
        <div class="header-actions">
          <a-button-group>
            <a-button @click="handleEdit">
              <EditOutlined />
              编辑
            </a-button>
            <a-button @click="handleExport">
              <ExportOutlined />
              导出
            </a-button>
            <a-button @click="handleDelete" danger>
              <DeleteOutlined />
              删除
            </a-button>
          </a-button-group>
        </div>
      </div>
    </div>

    <!-- 主要内容区域 -->
    <div class="detail-content">
      <div class="content-layout">
        <!-- 左侧：原始内容展示区域 -->
        <div class="content-main">
          <EnhancedContentViewer 
            :content="record.content || record.raw_text"
            :title="'病历原始内容'"
            @search="handleContentSearch"
            @highlight="handleContentHighlight"
          />
        </div>

        <!-- 右侧：文档分类和其他信息 -->
        <div class="content-sidebar">
          <!-- 患者基本信息 -->
          <div class="info-card patient-info">
            <div class="card-header">
              <UserOutlined class="header-icon" />
              <h3>患者信息</h3>
            </div>
            <div class="card-content">
              <div class="info-grid">
                <div class="info-item">
                  <label>姓名</label>
                  <span class="info-value">{{ record.patient_info?.name || '未知' }}</span>
                </div>
                <div class="info-item">
                  <label>年龄</label>
                  <span class="info-value">{{ record.patient_info?.age || '未知' }}岁</span>
                </div>
                <div class="info-item">
                  <label>性别</label>
                  <span class="info-value">{{ record.patient_info?.gender || '未知' }}</span>
                </div>
                <div class="info-item">
                  <label>科室</label>
                  <span class="info-value">{{ record.department || '未知' }}</span>
                </div>
              </div>
            </div>
          </div>

          <!-- 文档分类展示区域 -->
          <EnhancedDocumentClassification 
            :documents="record.documents || []"
            :classification-result="record.ai_extraction_result"
            @document-select="handleDocumentSelect"
            @classification-filter="handleClassificationFilter"
          />

          <!-- 诊断信息 -->
          <div class="info-card diagnosis-info">
            <div class="card-header">
              <MedicineBoxOutlined class="header-icon" />
              <h3>诊断信息</h3>
            </div>
            <div class="card-content">
              <div class="diagnosis-item">
                <label>主要诊断</label>
                <span class="diagnosis-value primary">{{ record.primary_diagnosis || '未填写' }}</span>
              </div>
              <div class="diagnosis-item" v-if="record.secondary_diagnosis && record.secondary_diagnosis.length > 0">
                <label>次要诊断</label>
                <div class="secondary-diagnoses">
                  <a-tag v-for="(diagnosis, index) in record.secondary_diagnosis" :key="index" color="blue">
                    {{ diagnosis }}
                  </a-tag>
                </div>
              </div>
              <div class="diagnosis-item" v-if="record.major_surgery">
                <label>主要手术</label>
                <span class="diagnosis-value">{{ record.major_surgery }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { 
  ArrowLeftOutlined, 
  EditOutlined, 
  ExportOutlined, 
  DeleteOutlined,
  UserOutlined,
  MedicineBoxOutlined
} from '@ant-design/icons-vue'
import EnhancedContentViewer from './EnhancedContentViewer.vue'
import EnhancedDocumentClassification from './EnhancedDocumentClassification.vue'

// Props
interface Props {
  record: any
}

const props = defineProps<Props>()

// Emits
const emit = defineEmits<{
  back: []
  edit: [record: any]
  export: [record: any]
  delete: [record: any]
}>()

// 状态管理
const searchKeyword = ref('')
const highlightTexts = ref<string[]>([])

// 处理函数
const handleEdit = () => {
  emit('edit', props.record)
}

const handleExport = () => {
  emit('export', props.record)
}

const handleDelete = () => {
  emit('delete', props.record)
}

const handleContentSearch = (keyword: string) => {
  searchKeyword.value = keyword
  // 实现搜索逻辑
}

const handleContentHighlight = (texts: string[]) => {
  highlightTexts.value = texts
}

const handleDocumentSelect = (document: unknown) => {
  // 处理文档选择
  console.log('Selected document:', document)
}

const handleClassificationFilter = (filter: unknown) => {
  // 处理分类筛选
  console.log('Classification filter:', filter)
}

// 工具函数
const getStatusColor = (status: string) => {
  const colors: Record<string, string> = {
    'pending': 'processing',
    'completed': 'success',
    'failed': 'error',
    'reviewing': 'warning'
  }
  return colors[status] || 'default'
}

const getStatusText = (status: string) => {
  const texts: Record<string, string> = {
    'pending': '待处理',
    'completed': '已完成',
    'failed': '失败',
    'reviewing': '审核中'
  }
  return texts[status] || status
}

const formatDateTime = (dateStr: string | undefined) => {
  if (!dateStr) return '未知'
  try {
    return new Date(dateStr).toLocaleString('zh-CN', {
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
.enhanced-record-detail {
  min-height: 100vh;
  background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
}

.detail-header {
  background: white;
  border-bottom: 1px solid #e5e7eb;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
  position: sticky;
  top: 0;
  z-index: 100;
}

.header-content {
  max-width: 1400px;
  margin: 0 auto;
  padding: 16px 24px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.back-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #6b7280;
  font-weight: 500;
}

.title-section {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.record-title {
  font-size: 24px;
  font-weight: 600;
  color: #111827;
  margin: 0;
}

.record-meta {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 14px;
  color: #6b7280;
}

.record-id {
  font-family: 'SF Mono', monospace;
  background: #f3f4f6;
  padding: 2px 8px;
  border-radius: 4px;
}

.detail-content {
  max-width: 1400px;
  margin: 0 auto;
  padding: 24px;
}

.content-layout {
  display: grid;
  grid-template-columns: 1fr 400px;
  gap: 24px;
  align-items: start;
}

.content-main {
  background: white;
  border-radius: 12px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
  overflow: hidden;
}

.content-sidebar {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.info-card {
  background: white;
  border-radius: 12px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
  overflow: hidden;
}

.card-header {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  padding: 16px 20px;
  display: flex;
  align-items: center;
  gap: 12px;
}

.header-icon {
  font-size: 18px;
}

.card-header h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
}

.card-content {
  padding: 20px;
}

.info-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.info-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.info-item label {
  font-size: 12px;
  font-weight: 500;
  color: #6b7280;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.info-value {
  font-size: 14px;
  font-weight: 600;
  color: #111827;
}

.diagnosis-item {
  margin-bottom: 16px;
}

.diagnosis-item:last-child {
  margin-bottom: 0;
}

.diagnosis-item label {
  display: block;
  font-size: 12px;
  font-weight: 500;
  color: #6b7280;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 8px;
}

.diagnosis-value {
  font-size: 14px;
  font-weight: 600;
  color: #111827;
}

.diagnosis-value.primary {
  color: #dc2626;
  font-size: 16px;
}

.secondary-diagnoses {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

/* 响应式设计 */
@media (max-width: 1200px) {
  .content-layout {
    grid-template-columns: 1fr;
    gap: 20px;
  }
  
  .content-sidebar {
    order: -1;
  }
}

@media (max-width: 768px) {
  .header-content {
    flex-direction: column;
    gap: 16px;
    align-items: stretch;
  }
  
  .header-left {
    flex-direction: column;
    align-items: flex-start;
    gap: 12px;
  }
  
  .info-grid {
    grid-template-columns: 1fr;
  }
  
  .detail-content {
    padding: 16px;
  }
}
</style>
