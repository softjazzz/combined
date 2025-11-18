<template>
  <div class="batch-operations">
    <!-- 批量操作工具栏 -->
    <div 
      v-if="selectedItems.length > 0" 
      class="batch-toolbar"
      :class="{ 'batch-toolbar-mobile': isMobile }"
    >
      <div class="batch-info">
        <a-checkbox
          :checked="isAllSelected"
          :indeterminate="isIndeterminate"
          @change="handleSelectAll"
        >
          已选择 {{ selectedItems.length }} 项
        </a-checkbox>
      </div>
      
      <div class="batch-actions">
        <a-space :size="isMobile ? 'small' : 'middle'">
          <a-button
            v-for="action in availableActions"
            :key="action.key"
            :type="action.type || 'default'"
            :danger="action.danger"
            :loading="loadingActions.includes(action.key)"
            :disabled="!canExecuteAction(action)"
            :size="isMobile ? 'small' : 'middle'"
            @click="handleAction(action)"
          >
            <template #icon v-if="action.icon">
              <component :is="action.icon" />
            </template>
            {{ isMobile ? action.shortLabel || action.label : action.label }}
          </a-button>
        </a-space>
      </div>
      
      <div class="batch-close">
        <a-button 
          type="text" 
          size="small" 
          @click="clearSelection"
        >
          <template #icon>
            <CloseOutlined />
          </template>
        </a-button>
      </div>
    </div>
    
    <!-- 进度指示器 -->
    <div 
      v-if="showProgress" 
      class="batch-progress"
    >
      <a-progress
        :percent="progressPercent"
        :status="progressStatus"
        :size="isMobile ? 'small' : 'default'"
      >
        <template #format="percent">
          {{ progressText || `${percent}%` }}
        </template>
      </a-progress>
      
      <div class="progress-details" v-if="progressDetails">
        <div class="progress-stats">
          <span class="stat-item">
            <span class="stat-label">成功:</span>
            <span class="stat-value success">{{ progressDetails.success }}</span>
          </span>
          <span class="stat-item">
            <span class="stat-label">失败:</span>
            <span class="stat-value error">{{ progressDetails.failed }}</span>
          </span>
          <span class="stat-item">
            <span class="stat-label">总计:</span>
            <span class="stat-value">{{ progressDetails.total }}</span>
          </span>
        </div>
      </div>
    </div>
    
    <!-- 结果摘要 -->
    <a-modal
      v-model:open="showResultModal"
      title="批量操作结果"
      :width="isMobile ? '90%' : 600"
      :footer="null"
    >
      <div class="batch-result">
        <div class="result-summary">
          <a-result
            :status="resultSummary.status"
            :title="resultSummary.title"
            :sub-title="resultSummary.subtitle"
          >
            <template #extra>
              <a-space>
                <a-button type="primary" @click="showResultModal = false">
                  确定
                </a-button>
                <a-button 
                  v-if="resultSummary.failed > 0"
                  @click="downloadErrorReport"
                >
                  下载错误报告
                </a-button>
              </a-space>
            </template>
          </a-result>
        </div>
        
        <div v-if="resultDetails.length > 0" class="result-details">
          <a-collapse>
            <a-collapse-panel key="details" header="详细结果">
              <div class="result-list">
                <div
                  v-for="(result, index) in resultDetails"
                  :key="index"
                  class="result-item"
                  :class="{ 'result-error': result.error }"
                >
                  <div class="result-item-content">
                    <div class="result-item-title">{{ result.title }}</div>
                    <div v-if="result.error" class="result-item-error">
                      {{ result.error }}
                    </div>
                  </div>
                  <div class="result-item-status">
                    <a-tag :color="result.error ? 'error' : 'success'">
                      {{ result.error ? '失败' : '成功' }}
                    </a-tag>
                  </div>
                </div>
              </div>
            </a-collapse-panel>
          </a-collapse>
        </div>
      </div>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import type { Component } from 'vue'
import { CloseOutlined } from '@ant-design/icons-vue'
import { message } from 'ant-design-vue'

// 批量操作定义
interface BatchAction {
  key: string
  label: string
  shortLabel?: string
  icon?: Component
  type?: 'primary' | 'default' | 'dashed' | 'link' | 'text'
  danger?: boolean
  requireConfirm?: boolean
  confirmTitle?: string
  confirmContent?: string
  minSelection?: number
  maxSelection?: number
  validator?: (items: unknown[]) => boolean | string
}

// 进度详情
interface ProgressDetails {
  success: number
  failed: number
  total: number
}

// 结果详情
interface ResultDetail {
  title: string
  error?: string
}

// Props 定义
interface Props {
  selectedItems: unknown[]
  totalItems?: number
  actions: BatchAction[]
  isMobile?: boolean
  maxConcurrency?: number
}

const props = withDefaults(defineProps<Props>(), {
  selectedItems: () => [] as unknown[],
  totalItems: 0,
  isMobile: false,
  maxConcurrency: 5
})

// Emits 定义
const emit = defineEmits<{
  'update:selectedItems': [unknown[]]
  'select-all': [selected: boolean]
  'execute-action': [action: BatchAction, unknown[]]
}>()

// 响应式数据
const loadingActions = ref<string[]>([])
const showProgress = ref(false)
const progressPercent = ref(0)
const progressStatus = ref<'normal' | 'active' | 'success' | 'exception'>('normal')
const progressText = ref('')
const progressDetails = ref<ProgressDetails | null>(null)
const showResultModal = ref(false)
const resultSummary = ref<{
  status: 'success' | 'error' | 'warning'
  title: string
  subtitle: string
  success: number
  failed: number
}>({
  status: 'success',
  title: '',
  subtitle: '',
  success: 0,
  failed: 0
})
const resultDetails = ref<ResultDetail[]>([])

// 计算属性
const isAllSelected = computed(() => 
  props.totalItems > 0 && props.selectedItems.length === props.totalItems
)

const isIndeterminate = computed(() => 
  props.selectedItems.length > 0 && props.selectedItems.length < props.totalItems
)

const availableActions = computed(() => 
  props.actions.filter(action => {
    if (action.minSelection && props.selectedItems.length < action.minSelection) {
      return false
    }
    if (action.maxSelection && props.selectedItems.length > action.maxSelection) {
      return false
    }
    return true
  })
)

// 方法
const handleSelectAll = (e) => {
  emit('select-all', e.target.checked)
}

const clearSelection = () => {
  emit('update:selectedItems', [] as unknown[])
}

const canExecuteAction = (action: BatchAction): boolean => {
  if (loadingActions.value.includes(action.key)) {
    return false
  }
  
  if (action.validator) {
    const result = action.validator(props.selectedItems)
    return result === true
  }
  
  return true
}

const handleAction = async (action: BatchAction) => {
  // 验证
  if (action.validator) {
    const result = action.validator(props.selectedItems)
    if (result !== true) {
      message.error(typeof result === 'string' ? result : '操作条件不满足')
      return
    }
  }
  
  // 确认对话框
  if (action.requireConfirm) {
    const confirmed = await showConfirm(action)
    if (!confirmed) return
  }
  
  // 开始执行
  loadingActions.value.push(action.key)
  showProgress.value = true
  progressPercent.value = 0
  progressStatus.value = 'active'
  progressText.value = '正在处理...'
  progressDetails.value = { success: 0, failed: 0, total: props.selectedItems.length }
  resultDetails.value = []
  
  try {
    // 触发执行事件
    emit('execute-action', action, props.selectedItems)
    
    // 这里可以添加实际的批量处理逻辑
    await executeBatchOperation(action, props.selectedItems)
    
  } catch (error) {
    console.error('批量操作失败:', error)
    message.error('批量操作失败')
  } finally {
    loadingActions.value = loadingActions.value.filter(key => key !== action.key)
    showProgress.value = false
  }
}

const executeBatchOperation = async (action: BatchAction, items: unknown[]) => {
  const results: ResultDetail[] = []
  let successCount = 0
  let failedCount = 0
  
  // 分批处理，避免并发过多
  const batches = []
  for (let i = 0; i < items.length; i += props.maxConcurrency) {
    batches.push(items.slice(i, i + props.maxConcurrency))
  }
  
  for (const batch of batches) {
    const batchPromises = batch.map(async (item, index) => {
      try {
        // 这里应该调用实际的处理函数
        await new Promise(resolve => setTimeout(resolve, 1000)) // 模拟处理时间
        
        successCount++
        results.push({
          title: `项目 ${item.id || index + 1}`,
        })
      } catch (error) {
        failedCount++
        results.push({
          title: `项目 ${item.id || index + 1}`,
          error: error instanceof Error ? error.message : '处理失败'
        })
      }
      
      // 更新进度
      const completed = successCount + failedCount
      progressPercent.value = Math.round((completed / items.length) * 100)
      progressDetails.value = {
        success: successCount,
        failed: failedCount,
        total: items.length
      }
    })
    
    await Promise.all(batchPromises)
  }
  
  // 显示结果
  showResults(successCount, failedCount, results)
}

const showResults = (successCount: number, failedCount: number, details: ResultDetail[]) => {
  resultDetails.value = details
  
  if (failedCount === 0) {
    resultSummary.value = {
      status: 'success',
      title: '批量操作完成',
      subtitle: `成功处理 ${successCount} 项`,
      success: successCount,
      failed: failedCount
    }
    progressStatus.value = 'success'
    progressText.value = '处理完成'
  } else if (successCount === 0) {
    resultSummary.value = {
      status: 'error',
      title: '批量操作失败',
      subtitle: `${failedCount} 项处理失败`,
      success: successCount,
      failed: failedCount
    }
    progressStatus.value = 'exception'
    progressText.value = '处理失败'
  } else {
    resultSummary.value = {
      status: 'warning',
      title: '批量操作部分成功',
      subtitle: `成功 ${successCount} 项，失败 ${failedCount} 项`,
      success: successCount,
      failed: failedCount
    }
    progressStatus.value = 'success'
    progressText.value = '处理完成'
  }
  
  showResultModal.value = true
  
  // 清空选择
  setTimeout(() => {
    clearSelection()
  }, 1000)
}

const showConfirm = (action: BatchAction): Promise<boolean> => {
  return new Promise((resolve: unknown) => {
    // 这里应该显示确认对话框
    // 简化实现，直接返回 true
    resolve(true)
  })
}

const downloadErrorReport = () => {
  const errorItems = resultDetails.value.filter(item => item.error)
  const csvContent = 'data:text/csv;charset=utf-8,' + 
    '项目,错误信息\n' +
    errorItems.map(item => `"${item.title}","${item.error}"`).join('\n')
  
  const encodedUri = encodeURI(csvContent)
  const link = document.createElement('a')
  link.setAttribute('href', encodedUri)
  link.setAttribute('download', `批量操作错误报告_${new Date().toISOString().slice(0, 10)}.csv`)
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
}

// 监听选择变化
watch(() => props.selectedItems.length, (newLength) => {
  if (newLength === 0) {
    showProgress.value = false
  }
})
</script>

<style scoped>
.batch-operations {
  position: relative;
}

.batch-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  background: #f0f2f5;
  border-radius: 6px;
  margin-bottom: 16px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

.batch-toolbar-mobile {
  padding: 8px 12px;
  flex-wrap: wrap;
  gap: 8px;
}

.batch-info {
  flex: 1;
  min-width: 0;
}

.batch-actions {
  flex: 2;
  display: flex;
  justify-content: center;
}

.batch-close {
  flex: 0 0 auto;
}

.batch-progress {
  margin-bottom: 16px;
  padding: 16px;
  background: white;
  border-radius: 6px;
  border: 1px solid #d9d9d9;
}

.progress-details {
  margin-top: 12px;
}

.progress-stats {
  display: flex;
  gap: 16px;
  font-size: 14px;
}

.stat-item {
  display: flex;
  align-items: center;
  gap: 4px;
}

.stat-label {
  color: #666;
}

.stat-value {
  font-weight: 500;
}

.stat-value.success {
  color: #52c41a;
}

.stat-value.error {
  color: #ff4d4f;
}

.batch-result {
  max-height: 60vh;
  overflow-y: auto;
}

.result-details {
  margin-top: 16px;
}

.result-list {
  max-height: 300px;
  overflow-y: auto;
}

.result-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 0;
  border-bottom: 1px solid #f0f0f0;
}

.result-item:last-child {
  border-bottom: none;
}

.result-item-content {
  flex: 1;
  min-width: 0;
}

.result-item-title {
  font-weight: 500;
  margin-bottom: 4px;
}

.result-item-error {
  color: #ff4d4f;
  font-size: 12px;
  word-break: break-all;
}

.result-item-status {
  flex: 0 0 auto;
  margin-left: 12px;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .batch-toolbar {
    flex-direction: column;
    align-items: stretch;
    gap: 8px;
  }
  
  .batch-info,
  .batch-actions,
  .batch-close {
    flex: none;
  }
  
  .batch-actions {
    justify-content: flex-start;
  }
  
  .progress-stats {
    flex-direction: column;
    gap: 8px;
  }
}
</style>
