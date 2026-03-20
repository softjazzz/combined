<template>
  <div class="records-view-optimized">
    <!-- 页面头部 -->
    <div class="page-header">
      <div class="header-content">
        <div class="header-title">
          <h1>病案管理</h1>
          <p>智能化病案质控分析平台</p>
        </div>
        <div class="header-stats">
          <div class="stat-card" v-for="stat in stats" :key="stat.key">
            <div class="stat-value">{{ stat.value }}</div>
            <div class="stat-label">{{ stat.label }}</div>
          </div>
        </div>
      </div>
    </div>

    <!-- 工具栏 -->
    <div class="toolbar">
      <div class="toolbar-left">
        <a-button 
          type="primary" 
          @click="showUploadModal = true"
          :loading="uploading"
        >
          <template #icon><PlusOutlined /></template>
          上传病案
        </a-button>
        
        <a-button 
          @click="handleBatchAnalysis"
          :disabled="selectedRecords.length === 0"
          :loading="batchAnalyzing"
        >
          <template #icon><ThunderboltOutlined /></template>
          批量分析
        </a-button>
      </div>
      
      <div class="toolbar-right">
        <a-input-search
          v-model:value="searchKeyword"
          placeholder="搜索患者姓名、科室..."
          style="width: 250px"
          @search="handleSearch"
          allow-clear
        />
        
        <a-select
          v-model:value="statusFilter"
          placeholder="状态筛选"
          style="width: 120px"
          allow-clear
        >
          <a-select-option value="">全部</a-select-option>
          <a-select-option value="pending">待分析</a-select-option>
          <a-select-option value="analyzing">分析中</a-select-option>
          <a-select-option value="completed">已完成</a-select-option>
          <a-select-option value="failed">失败</a-select-option>
        </a-select>
        
        <a-select
          v-model:value="departmentFilter"
          placeholder="科室筛选"
          style="width: 120px"
          allow-clear
        >
          <a-select-option value="">全部科室</a-select-option>
          <a-select-option v-for="dept in departments" :key="dept" :value="dept">
            {{ dept }}
          </a-select-option>
        </a-select>
      </div>
    </div>

    <!-- 批量操作 -->
    <BatchOperationsComponent
      v-model:selected-items="selectedRecords"
      :total-items="filteredRecords.length"
      :actions="batchActions"
      :is-mobile="isMobile"
      @select-all="handleSelectAll"
      @execute-action="handleBatchAction"
    />

    <!-- 病案列表 - 使用虚拟滚动 -->
    <div class="records-container">
      <VirtualListComponent
        :items="filteredRecords"
        :item-height="120"
        :container-height="600"
        :loading="loading"
        :has-more="hasMore"
        :load-more="loadMore"
        key-field="id"
      >
        <template #default="{ item: record, index }">
          <div class="record-item" :class="{ 'record-selected': isSelected(record) }">
            <div class="record-checkbox">
              <a-checkbox
                :checked="isSelected(record)"
                @change="(e) => handleRecordSelect(record, e.target.checked)"
              />
            </div>
            
            <div class="record-avatar">
              <LazyImageComponent
                :src="getPatientAvatar(record)"
                :width="60"
                :height="60"
                :alt="record.patient_name"
                fit="cover"
                :show-skeleton="true"
                :fallback="getDefaultAvatar(record.patient_gender)"
              />
            </div>
            
            <div class="record-content">
              <div class="record-header">
                <div class="record-title">
                  <h3>{{ record.patient_name }}</h3>
                  <a-tag :color="getGenderColor(record.patient_gender)">
                    {{ record.patient_gender }}
                  </a-tag>
                  <a-tag>{{ record.patient_age }}岁</a-tag>
                </div>
                <div class="record-status">
                  <a-tag :color="getStatusColor(record.status)">
                    {{ getStatusText(record.status) }}
                  </a-tag>
                </div>
              </div>
              
              <div class="record-info">
                <div class="info-item">
                  <span class="info-label">科室:</span>
                  <span class="info-value">{{ record.department }}</span>
                </div>
                <div class="info-item">
                  <span class="info-label">入院日期:</span>
                  <span class="info-value">{{ formatDate(record.admission_date) }}</span>
                </div>
                <div class="info-item">
                  <span class="info-label">病案类型:</span>
                  <span class="info-value">{{ record.record_type }}</span>
                </div>
              </div>
              
              <div class="record-footer">
                <div class="record-time">
                  创建于 {{ formatDateTime(record.created_at) }}
                </div>
                <div class="record-actions">
                  <a-space size="small">
                    <a-button 
                      size="small" 
                      @click="viewRecord(record)"
                    >
                      查看
                    </a-button>
                    <a-button 
                      size="small" 
                      type="primary"
                      @click="analyzeRecord(record)"
                      :loading="analyzingRecords.includes(record.id)"
                      :disabled="record.status === 'analyzing'"
                    >
                      {{ record.status === 'completed' ? '重新分析' : '分析' }}
                    </a-button>
                    <a-dropdown>
                      <a-button size="small">
                        更多
                        <DownOutlined />
                      </a-button>
                      <template #overlay>
                        <a-menu @click="({ key   }) => handleRecordAction(key, record)">
                          <a-menu-item key="edit">编辑</a-menu-item>
                          <a-menu-item key="download">下载</a-menu-item>
                          <a-menu-item key="history">分析历史</a-menu-item>
                          <a-menu-divider />
                          <a-menu-item key="delete" danger>删除</a-menu-item>
                        </a-menu>
                      </template>
                    </a-dropdown>
                  </a-space>
                </div>
              </div>
            </div>
          </div>
        </template>
      </VirtualListComponent>
    </div>

    <!-- 上传模态框 -->
    <a-modal
      v-model:open="showUploadModal"
      title="上传病案"
      :width="800"
      :footer="null"
      :destroy-on-close="true"
    >
      <RecordUploadFormComponent 
        @submit="handleRecordSubmit"
        @cancel="showUploadModal = false"
        :loading="uploading"
      />
    </a-modal>

    <!-- 分析结果模态框 -->
    <a-modal
      v-model:open="showAnalysisModal"
      title="质控分析结果"
      :width="1000"
      :footer="null"
      :destroy-on-close="true"
    >
      <QCResultDisplay 
        v-if="currentAnalysisResult"
        :result="currentAnalysisResult"
        :show-details="true"
      />
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import {
  PlusOutlined,
  ThunderboltOutlined,
  DownOutlined,
  DeleteOutlined,
  AnalysisOutlined,
  ExportOutlined
} from '@ant-design/icons-vue'

// 组件导入
import VirtualListComponent from '@/components/common/VirtualListComponent.vue'
import LazyImageComponent from '@/components/common/LazyImageComponent.vue'
import BatchOperationsComponent from '@/components/common/BatchOperationsComponent.vue'
import RecordUploadFormComponent from '@/components/forms/RecordUploadFormComponent.vue'
import QCResultDisplay from '@/components/qc/QCResultDisplay.vue'

// API导入
import { getMedicalRecords, createMedicalRecord, deleteMedicalRecord } from '@/api/medical-records'
import { analyzeRecord as analyzeRecordAPI, batchAnalyzeRecords } from '@/api/qc-analysis-optimized'

// 工具函数导入
import { formatDate, formatDateTime } from '@/utils/date'
import { useBreakpoints } from '@/composables/useBreakpoints'

interface RecordItem {
  id: string
  patient_name?: string
  patient_gender?: string
  patient_age?: number | string
  status?: 'pending' | 'analyzing' | 'completed' | 'failed' | string
  department?: string
  admission_date?: string
  record_type?: string
  created_at?: string
  content?: string
  [key: string]: unknown
}
interface BatchActionItem {
  key: string
}

// 响应式数据
const router = useRouter()
const { isMobile } = useBreakpoints()

const records = ref<RecordItem[]>([])
const selectedRecords = ref<RecordItem[]>([])
const loading = ref(false)
const uploading = ref(false)
const batchAnalyzing = ref(false)
const analyzingRecords = ref<string[]>([])
const hasMore = ref(true)
const currentPage = ref(1)
const pageSize = ref(20)

// 筛选和搜索
const searchKeyword = ref('')
const statusFilter = ref('')
const departmentFilter = ref('')

// 模态框状态
const showUploadModal = ref(false)
const showAnalysisModal = ref(false)
const currentAnalysisResult = ref(null)

// 统计数据
const stats = computed(() => [
  { key: 'total', label: '总病案数', value: records.value.length },
  { key: 'pending', label: '待分析', value: records.value.filter(r => r.status === 'pending').length },
  { key: 'completed', label: '已完成', value: records.value.filter(r => r.status === 'completed').length },
  { key: 'analyzing', label: '分析中', value: records.value.filter(r => r.status === 'analyzing').length }
])

// 科室列表
const departments = computed(() => {
  const depts = new Set(records.value.map(r => r.department).filter(Boolean))
  return Array.from(depts).sort()
})

// 过滤后的记录
const filteredRecords = computed(() => {
  let filtered = records.value

  // 搜索过滤
  if (searchKeyword.value) {
    const keyword = searchKeyword.value.toLowerCase()
    filtered = filtered.filter(record =>
      record.patient_name?.toLowerCase().includes(keyword) ||
      record.department?.toLowerCase().includes(keyword) ||
      record.record_type?.toLowerCase().includes(keyword)
    )
  }

  // 状态过滤
  if (statusFilter.value) {
    filtered = filtered.filter(record => record.status === statusFilter.value)
  }

  // 科室过滤
  if (departmentFilter.value) {
    filtered = filtered.filter(record => record.department === departmentFilter.value)
  }

  return filtered
})

// 批量操作配置
const batchActions = computed(() => [
  {
    key: 'analyze',
    label: '批量分析',
    shortLabel: '分析',
    icon: AnalysisOutlined,
    type: 'primary',
    minSelection: 1,
    maxSelection: 10,
    validator: (items: RecordItem[]) => {
      const analyzingCount = items.filter(item => item.status === 'analyzing').length
      if (analyzingCount > 0) {
        return '选中的病案中包含正在分析的记录'
      }
      return true
    }
  },
  {
    key: 'export',
    label: '批量导出',
    shortLabel: '导出',
    icon: ExportOutlined,
    minSelection: 1,
    maxSelection: 50
  },
  {
    key: 'delete',
    label: '批量删除',
    shortLabel: '删除',
    icon: DeleteOutlined,
    danger: true,
    requireConfirm: true,
    confirmTitle: '确认删除',
    confirmContent: '删除后无法恢复，确定要删除选中的病案吗？',
    minSelection: 1,
    validator: (items: RecordItem[]) => {
      const analyzingCount = items.filter(item => item.status === 'analyzing').length
      if (analyzingCount > 0) {
        return '无法删除正在分析的病案'
      }
      return true
    }
  }
])

// 方法
const loadRecords = async (page = 1, append = false) => {
  try {
    loading.value = true
    const response = await getMedicalRecords({
      page,
      pageSize: pageSize.value,
      status: statusFilter.value || undefined,
      department: departmentFilter.value || undefined,
      search: searchKeyword.value || undefined
    })

    if (response.success && response.data) {
      const payload = response.data as unknown
      const pagedData = Array.isArray(payload)
        ? { data: payload as RecordItem[], hasMore: false }
        : (payload as { data?: RecordItem[]; hasMore?: boolean })

      if (append) {
        records.value.push(...(pagedData.data || []))
      } else {
        records.value = pagedData.data || []
      }
      hasMore.value = !!pagedData.hasMore
      currentPage.value = page
    }
  } catch (error) {
    console.error('加载病案列表失败:', error)
    message.error('加载病案列表失败')
  } finally {
    loading.value = false
  }
}

const loadMore = async () => {
  if (hasMore.value && !loading.value) {
    await loadRecords(currentPage.value + 1, true)
  }
}

const handleSearch = () => {
  currentPage.value = 1
  loadRecords(1, false)
}

const handleRecordSubmit = async (formData: FormData) => {
  try {
    uploading.value = true
    const response = await createMedicalRecord(formData)

    if (response.success) {
      message.success('病案上传成功')
      showUploadModal.value = false
      await loadRecords(1, false) // 重新加载列表
    } else {
      message.error(response.error?.message || '上传失败')
    }
  } catch (error) {
    console.error('上传病案失败:', error)
    message.error('上传病案失败')
  } finally {
    uploading.value = false
  }
}

const analyzeRecord = async (record: RecordItem) => {
  try {
    analyzingRecords.value.push(record.id)

    const response = await analyzeRecordAPI({
      recordId: record.id,
      content: record.content,
      options: {
        analysisMode: 'comprehensive',
        enableCache: true,
        priority: 'normal'
      }
    })

    if (response.success && response.data) {
      message.success('分析完成')
      currentAnalysisResult.value = response.data
      showAnalysisModal.value = true

      // 更新记录状态
      const index = records.value.findIndex(r => r.id === record.id)
      if (index !== -1) {
        records.value[index].status = 'completed'
      }
    } else {
      message.error(response.error?.message || '分析失败')
    }
  } catch (error) {
    console.error('分析失败:', error)
    message.error('分析失败')
  } finally {
    analyzingRecords.value = analyzingRecords.value.filter(id => id !== record.id)
  }
}

const handleBatchAnalysis = async () => {
  if (selectedRecords.value.length === 0) {
    message.warning('请先选择要分析的病案')
    return
  }

  try {
    batchAnalyzing.value = true

    const response = await batchAnalyzeRecords({
      records: selectedRecords.value.map(record => ({
        recordId: record.id,
        content: record.content,
        priority: 'normal'
      })),
      options: {
        analysisMode: 'comprehensive',
        enableCache: true,
        maxConcurrency: 3
      }
    })

    if (response.success && response.data) {
      const { summary } = response.data
      message.success(`批量分析完成：成功 ${summary.successful} 项，失败 ${summary.failed} 项`)

      // 更新记录状态
      selectedRecords.value.forEach(record => {
        const index = records.value.findIndex(r => r.id === record.id)
        if (index !== -1) {
          records.value[index].status = 'completed'
        }
      })

      selectedRecords.value = []
    } else {
      message.error(response.error?.message || '批量分析失败')
    }
  } catch (error) {
    console.error('批量分析失败:', error)
    message.error('批量分析失败')
  } finally {
    batchAnalyzing.value = false
  }
}

const handleRecordSelect = (record: RecordItem, selected: boolean) => {
  if (selected) {
    if (!selectedRecords.value.find(r => r.id === record.id)) {
      selectedRecords.value.push(record)
    }
  } else {
    selectedRecords.value = selectedRecords.value.filter(r => r.id !== record.id)
  }
}

const handleSelectAll = (selected: boolean) => {
  if (selected) {
    selectedRecords.value = [...filteredRecords.value]
  } else {
    selectedRecords.value = []
  }
}

const handleBatchAction = async (action: BatchActionItem, items: RecordItem[]) => {
  switch (action.key) {
    case 'analyze':
      await handleBatchAnalysis()
      break
    case 'export':
      await handleBatchExport(items)
      break
    case 'delete': await handleBatchDelete(items)
      break
  }
}

const handleBatchExport = async (items: RecordItem[]) => {
  try {
    // 实现批量导出逻辑
    message.success(`导出 ${items.length} 条记录`)
  } catch (error) {
    message.error('导出失败')
  }
}

const handleBatchDelete = async (items: RecordItem[]) => {
  try {
    const deletePromises = items.map(item => deleteMedicalRecord(item.id))
    await Promise.all(deletePromises)

    message.success(`删除 ${items.length} 条记录`)
    await loadRecords(1, false)
    selectedRecords.value = []
  } catch (error) {
    message.error('删除失败')
  }
}

const viewRecord = (record: RecordItem) => {
  router.push(`/records/${record.id}`)
}

const handleRecordAction = async (action: string, record: RecordItem) => {
  switch (action) {
    case 'edit':
      // 实现编辑逻辑
      break
    case 'download':
      // 实现下载逻辑
      break
    case 'history':
      router.push(`/records/${record.id}/history`)
      break
    case 'delete':
      await handleDeleteRecord(record)
      break
  }
}

const handleDeleteRecord = async (record: RecordItem) => {
  try {
    const response = await deleteMedicalRecord(record.id)
    if (response.success) {
      message.success('删除成功')
      await loadRecords(1, false)
    } else {
      message.error(response.error?.message || '删除失败')
    }
  } catch (error) {
    message.error('删除失败')
  }
}

// 工具方法
const isSelected = (record: RecordItem) => {
  return selectedRecords.value.some(r => r.id === record.id)
}

const getPatientAvatar = (record: RecordItem) => {
  // 返回患者头像URL，这里使用占位符
  return `https://api.dicebear.com/7.x/avataaars/svg?seed=${record.patient_name}`
}

const getDefaultAvatar = (gender: string) => {
  return gender === '女'
    ? 'https://api.dicebear.com/7.x/avataaars/svg?seed=female'
    : 'https://api.dicebear.com/7.x/avataaars/svg?seed=male'
}

const getGenderColor = (gender: string) => {
  return gender === '女' ? 'pink' : 'blue'
}

const getStatusColor = (status: string) => {
  const colors = {
    pending: 'orange',
    analyzing: 'blue',
    completed: 'green',
    failed: 'red'
  }
  return colors[status as keyof typeof colors] || 'default'
}

const getStatusText = (status: string) => {
  const texts = {
    pending: '待分析',
    analyzing: '分析中',
    completed: '已完成',
    failed: '失败'
  }
  return texts[status as keyof typeof texts] || status
}

// 监听筛选条件变化
watch([statusFilter, departmentFilter], () => {
  currentPage.value = 1
  loadRecords(1, false)
})

// 生命周期
onMounted(() => {
  loadRecords()
})
</script>

<style scoped>
.records-view-optimized {
  min-height: 100vh;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  padding: 0;
}

.page-header {
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(10px);
  border-bottom: 1px solid rgba(255, 255, 255, 0.2);
  padding: 24px 0;
  margin-bottom: 24px;
}

.header-content {
  max-width: 1200px;
  margin: 0 auto;
  padding: 0 24px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-title h1 {
  font-size: 28px;
  font-weight: 600;
  color: #1a1a1a;
  margin: 0 0 8px 0;
}

.header-title p {
  color: #666;
  margin: 0;
  font-size: 14px;
}

.header-stats {
  display: flex;
  gap: 24px;
}

.stat-card {
  text-align: center;
  padding: 16px 20px;
  background: rgba(255, 255, 255, 0.8);
  border-radius: 12px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
  min-width: 80px;
}

.stat-value {
  font-size: 24px;
  font-weight: 600;
  color: #1890ff;
  margin-bottom: 4px;
}

.stat-label {
  font-size: 12px;
  color: #666;
}

.toolbar {
  max-width: 1200px;
  margin: 0 auto 24px auto;
  padding: 0 24px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
}

.toolbar-left,
.toolbar-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.records-container {
  max-width: 1200px;
  margin: 0 auto;
  padding: 0 24px;
  background: rgba(255, 255, 255, 0.95);
  border-radius: 12px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
  backdrop-filter: blur(10px);
}

.record-item {
  display: flex;
  align-items: center;
  padding: 16px;
  border-bottom: 1px solid #f0f0f0;
  transition: all 0.3s ease;
  cursor: pointer;
}

.record-item:hover {
  background: rgba(24, 144, 255, 0.05);
}

.record-item:last-child {
  border-bottom: none;
}

.record-selected {
  background: rgba(24, 144, 255, 0.1);
  border-left: 4px solid #1890ff;
}

.record-checkbox {
  margin-right: 16px;
}

.record-avatar {
  margin-right: 16px;
  border-radius: 8px;
  overflow: hidden;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.record-content {
  flex: 1;
  min-width: 0;
}

.record-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.record-title {
  display: flex;
  align-items: center;
  gap: 8px;
}

.record-title h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 500;
  color: #1a1a1a;
}

.record-info {
  display: flex;
  gap: 24px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}

.info-item {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 14px;
}

.info-label {
  color: #666;
  font-weight: 500;
}

.info-value {
  color: #1a1a1a;
}

.record-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.record-time {
  font-size: 12px;
  color: #999;
}

.record-actions {
  flex-shrink: 0;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .header-content {
    flex-direction: column;
    gap: 16px;
    text-align: center;
  }

  .header-stats {
    gap: 12px;
  }

  .stat-card {
    padding: 12px 16px;
    min-width: 60px;
  }

  .stat-value {
    font-size: 20px;
  }

  .toolbar {
    flex-direction: column;
    gap: 12px;
  }

  .toolbar-left,
  .toolbar-right {
    width: 100%;
    justify-content: center;
    flex-wrap: wrap;
  }

  .record-item {
    flex-direction: column;
    align-items: flex-start;
    gap: 12px;
  }

  .record-checkbox {
    align-self: flex-end;
    margin: 0;
  }

  .record-avatar {
    align-self: center;
    margin: 0;
  }

  .record-content {
    width: 100%;
  }

  .record-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 8px;
  }

  .record-info {
    flex-direction: column;
    gap: 8px;
  }

  .record-footer {
    flex-direction: column;
    align-items: flex-start;
    gap: 8px;
  }
}

@media (max-width: 480px) {
  .page-header {
    padding: 16px 0;
  }

  .header-content {
    padding: 0 16px;
  }

  .toolbar {
    padding: 0 16px;
  }

  .records-container {
    padding: 0 16px;
    margin: 0 16px;
  }

  .record-item {
    padding: 12px;
  }
}
</style>
