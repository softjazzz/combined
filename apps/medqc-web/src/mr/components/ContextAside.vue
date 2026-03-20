<template>
  <div class="context-aside">
    <!-- 患者信息卡片 -->
    <div class="aside-section">
      <div class="section-header">
        <UserOutlined />
        <span>患者信息</span>
      </div>
      <div class="patient-card" v-if="patient">
        <div class="patient-basic">
          <h4>{{ patient.patient_info?.name || patient.record_name || '未知患者' }}</h4>
          <div class="patient-details">
            <div class="detail-item">
              <span class="label">性别:</span>
              <span class="value">{{ patient.patient_info?.gender || '-' }}</span>
            </div>
            <div class="detail-item">
              <span class="label">年龄:</span>
              <span class="value">{{ patient.patient_info?.age || '-' }}岁</span>
            </div>
            <div class="detail-item">
              <span class="label">科室:</span>
              <span class="value">{{ patient.department || '-' }}</span>
            </div>
            <div class="detail-item">
              <span class="label">病历号:</span>
              <span class="value">{{ patient.record_number || patient.id || '-' }}</span>
            </div>
            <div class="detail-item">
              <span class="label">主要诊断:</span>
              <span class="value">{{ patient.primary_diagnosis || '-' }}</span>
            </div>
            <div class="detail-item">
              <span class="label">状态:</span>
              <span class="value">{{ patient.status || '-' }}</span>
            </div>
          </div>
        </div>
      </div>
      <a-empty v-else description="患者信息加载中..." :image="Empty.PRESENTED_IMAGE_SIMPLE" />
    </div>

    <!-- 文档统计 -->
    <div class="aside-section">
      <div class="section-header">
        <BarChartOutlined />
        <span>文档统计</span>
      </div>
      <div class="stats-grid">
        <div class="stat-item">
          <div class="stat-number">{{ docStats.total }}</div>
          <div class="stat-label">总文档数</div>
        </div>
        <div class="stat-item">
          <div class="stat-number">{{ docStats.categories }}</div>
          <div class="stat-label">分类数</div>
        </div>
        <div class="stat-item">
          <div class="stat-number">{{ docStats.aiClassified }}</div>
          <div class="stat-label">AI分类</div>
        </div>
        <div class="stat-item">
          <div class="stat-number">{{ docStats.avgConfidence }}%</div>
          <div class="stat-label">平均置信度</div>
        </div>
      </div>
    </div>

    <!-- 分类分布 -->
    <div class="aside-section" v-if="categoryStats.length > 0">
      <div class="section-header">
        <PieChartOutlined />
        <span>分类分布</span>
      </div>
      <div class="category-list">
        <div 
          v-for="category in categoryStats" 
          :key="category.name"
          class="category-item"
        >
          <div class="category-info">
            <span class="category-name">{{ category.name }}</span>
            <span class="category-count">{{ category.count }}</span>
          </div>
          <div class="category-bar">
            <div 
              class="category-progress"
              :style="{ width: category.percentage + '%' }"
            ></div>
          </div>
        </div>
      </div>
    </div>

    <!-- AI 建议 -->
    <div class="aside-section">
      <div class="section-header">
        <BulbOutlined />
        <span>AI 建议</span>
      </div>
      <div class="ai-suggestions">
        <a-alert
          message="智能分析"
          description="基于文档内容的AI分析建议功能正在开发中..."
          type="info"
          show-icon
          :closable="false"
        />
      </div>
    </div>

    <!-- 快速操作 -->
    <div class="aside-section">
      <div class="section-header">
        <ToolOutlined />
        <span>快速操作</span>
      </div>
      <div class="quick-actions">
        <a-button block @click="exportDocs" :loading="exporting">
          <DownloadOutlined />
          导出文档
        </a-button>
        <a-button block @click="generateReport" :loading="generating">
          <FileTextOutlined />
          生成报告
        </a-button>
        <a-button block @click="qualityCheck" :loading="checking">
          <CheckCircleOutlined />
          质量检查
        </a-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { message } from 'ant-design-vue'
import { Empty } from 'ant-design-vue'
import {
  UserOutlined,
  BarChartOutlined,
  PieChartOutlined,
  BulbOutlined,
  ToolOutlined,
  DownloadOutlined,
  FileTextOutlined,
  CheckCircleOutlined
} from '@ant-design/icons-vue'

interface Document {
  id: string
  title: string
  category?: string
  ai_classified?: boolean
  classification_confidence?: number
  created_at?: string
}

interface Props {
  patient?: PatientLike | null
  docs?: Document[]
}

interface PatientLike {
  id?: string
  record_name?: string
  record_number?: string
  department?: string
  primary_diagnosis?: string
  status?: string
  patient_info?: {
    name?: string
    gender?: string
    age?: number | string
  }
}

const props = withDefaults(defineProps<Props>(), {
  patient: null,
  docs: () => []
})

// 加载状态
const exporting = ref(false)
const generating = ref(false)
const checking = ref(false)

// 文档统计
const docStats = computed(() => {
  const docs = props.docs || []
  const total = docs.length
  const categories = new Set(docs.map(d => d.category).filter(Boolean)).size
  const aiClassified = docs.filter(d => d.ai_classified).length
  const avgConfidence = total > 0 
    ? Math.round(docs.reduce((sum, d) => sum + (d.classification_confidence || 0), 0) / total * 100)
    : 0

  return {
    total,
    categories,
    aiClassified,
    avgConfidence
  }
})

// 分类统计
const categoryStats = computed(() => {
  const docs = props.docs || []
  const categoryMap = new Map<string, number>()
  
  docs.forEach(doc => {
    const category = doc.category || '未分类'
    categoryMap.set(category, (categoryMap.get(category) || 0) + 1)
  })

  const total = docs.length
  const stats = Array.from(categoryMap.entries())
    .map(([name, count]) => ({
      name,
      count,
      percentage: total > 0 ? Math.round((count / total) * 100) : 0
    }))
    .sort((a, b) => b.count - a.count)
    .slice(0, 5) // 只显示前5个分类

  return stats
})

// 格式化日期
const formatDate = (dateStr: string) => {
  if (!dateStr) return ''
  try {
    return new Date(dateStr).toLocaleDateString('zh-CN')
  } catch {
    return dateStr
  }
}

// 导出文档
const exportDocs = async () => {
  exporting.value = true
  try {
    // 模拟导出操作
    await new Promise(resolve => setTimeout(resolve, 1000))
    message.success('文档导出功能开发中...')
  } catch (error) {
    message.error('导出失败')
  } finally {
    exporting.value = false
  }
}

// 生成报告
const generateReport = async () => {
  generating.value = true
  try {
    // 模拟生成报告
    await new Promise(resolve => setTimeout(resolve, 1500))
    message.success('报告生成功能开发中...')
  } catch (error) {
    message.error('生成报告失败')
  } finally {
    generating.value = false
  }
}

// 质量检查
const qualityCheck = async () => {
  checking.value = true
  try {
    // 模拟质量检查
    await new Promise(resolve => setTimeout(resolve, 2000))
    message.success('质量检查功能开发中...')
  } catch (error) {
    message.error('质量检查失败')
  } finally {
    checking.value = false
  }
}
</script>

<style scoped>
.context-aside {
  height: 100%;
  overflow-y: auto;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.aside-section {
  background: #fafafa;
  border-radius: 8px;
  padding: 16px;
}

.section-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 16px;
  font-weight: 600;
  color: #262626;
}

.patient-card {
  background: white;
  border-radius: 6px;
  padding: 16px;
  border: 1px solid #e8e8e8;
}

.patient-basic h4 {
  margin: 0 0 12px 0;
  font-size: 16px;
  color: #262626;
}

.patient-details {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.detail-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.detail-item .label {
  color: #666;
  font-size: 13px;
}

.detail-item .value {
  color: #262626;
  font-size: 13px;
  font-weight: 500;
}

.stats-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.stat-item {
  text-align: center;
  background: white;
  padding: 12px;
  border-radius: 6px;
  border: 1px solid #e8e8e8;
}

.stat-number {
  font-size: 20px;
  font-weight: bold;
  color: #1890ff;
  margin-bottom: 4px;
}

.stat-label {
  font-size: 12px;
  color: #666;
}

.category-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.category-item {
  background: white;
  padding: 12px;
  border-radius: 6px;
  border: 1px solid #e8e8e8;
}

.category-info {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.category-name {
  font-size: 13px;
  color: #262626;
}

.category-count {
  font-size: 13px;
  color: #1890ff;
  font-weight: 500;
}

.category-bar {
  height: 4px;
  background: #f0f0f0;
  border-radius: 2px;
  overflow: hidden;
}

.category-progress {
  height: 100%;
  background: linear-gradient(90deg, #1890ff, #40a9ff);
  transition: width 0.3s ease;
}

.ai-suggestions {
  background: white;
  border-radius: 6px;
  padding: 12px;
}

.quick-actions {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.quick-actions .ant-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  height: 36px;
}

/* 滚动条样式 */
.context-aside::-webkit-scrollbar {
  width: 6px;
}

.context-aside::-webkit-scrollbar-track {
  background: #f1f1f1;
  border-radius: 3px;
}

.context-aside::-webkit-scrollbar-thumb {
  background: #c1c1c1;
  border-radius: 3px;
}

.context-aside::-webkit-scrollbar-thumb:hover {
  background: #a8a8a8;
}
</style>
