<template>
  <div class="batch-smart-import-view">
    <!-- 页面头部 -->
    <div class="page-header">
      <div class="header-content">
        <div class="title-section">
          <h1 class="page-title">批量智能导入</h1>
          <p class="page-subtitle">支持多文件批量上传和LLM智能解析</p>
        </div>
        <div class="header-actions">
          <a-space>
            <a-button @click="showLLMConfig = true" :icon="h(SettingOutlined)">
              LLM配置
            </a-button>
            <a-button @click="showHelp = true" :icon="h(QuestionCircleOutlined)">
              使用帮助
            </a-button>
          </a-space>
        </div>
      </div>
    </div>

    <!-- 主要内容区域 -->
    <div class="main-content">
      <a-row :gutter="24">
        <!-- 左侧：批量文件处理 -->
        <a-col :span="16">
          <a-card title="批量文件处理" class="batch-processor-card">
            <BatchFileProcessor
              :max-file-size="50"
              :max-file-count="20"
              :allowed-types="['.pdf', '.doc', '.docx', '.txt']"
              @files-processed="handleFilesProcessed"
              @single-file-processed="handleSingleFileProcessed"
              @batch-completed="handleBatchCompleted"
            />
          </a-card>
        </a-col>

        <!-- 右侧：操作日志和统计 -->
        <a-col :span="8">
          <!-- 处理统计 -->
          <a-card title="处理统计" class="stats-card mb-4">
            <div class="stats-grid">
              <div class="stat-item">
                <div class="stat-value">{{ totalProcessed }}</div>
                <div class="stat-label">已处理文件</div>
              </div>
              <div class="stat-item">
                <div class="stat-value">{{ successCount }}</div>
                <div class="stat-label">成功解析</div>
              </div>
              <div class="stat-item">
                <div class="stat-value">{{ failureCount }}</div>
                <div class="stat-label">解析失败</div>
              </div>
              <div class="stat-item">
                <div class="stat-value">{{ averageConfidence }}%</div>
                <div class="stat-label">平均置信度</div>
              </div>
            </div>
          </a-card>

          <!-- 操作日志 -->
          <a-card title="操作日志" class="log-card">
            <div class="log-container">
              <div 
                v-for="(log, index) in operationLogs" 
                :key="index"
                :class="['log-item', `log-${log.type}`]"
              >
                <div class="log-time">{{ formatTime(log.timestamp) }}</div>
                <div class="log-message">{{ log.message }}</div>
              </div>
            </div>
            <div class="log-actions">
              <a-button size="small" @click="clearLogs">清空日志</a-button>
              <a-button size="small" @click="exportLogs">导出日志</a-button>
            </div>
          </a-card>
        </a-col>
      </a-row>
    </div>

    <!-- 批量结果汇总 -->
    <div v-if="batchResults.length > 0" class="batch-summary">
      <a-card title="批量处理结果汇总">
        <div class="summary-actions mb-4">
          <a-space size="large">
            <a-button 
              type="primary" 
              size="large"
              @click="showBatchResultsModal = true"
              :icon="h(EyeOutlined)"
            >
              查看所有结果 ({{ batchResults.length }})
            </a-button>
            <a-button 
              @click="exportAllResults"
              :icon="h(DownloadOutlined)"
            >
              导出所有结果
            </a-button>
            <a-button 
              @click="saveAllToDatabase"
              :loading="savingAll"
              :icon="h(DatabaseOutlined)"
            >
              批量保存到数据库
            </a-button>
          </a-space>
        </div>

        <!-- 结果预览表格 -->
        <a-table
          :columns="resultColumns"
          :data-source="batchResults"
          :pagination="{ pageSize: 10 }"
          size="small"
        >
          <template #bodyCell="{ column, record, index }">
            <template v-if="column.key === 'fileName'">
              <div class="file-name-cell">
                <component :is="getFileIcon(record.fileName)" class="file-icon" />
                <span>{{ record.fileName }}</span>
              </div>
            </template>
            <template v-else-if="column.key === 'status'">
              <a-tag :color="record.success ? 'success' : 'error'">
                {{ record.success ? '成功' : '失败' }}
              </a-tag>
            </template>
            <template v-else-if="column.key === 'confidence'">
              <a-progress 
                :percent="Math.round(record.data?.confidence || 0)" 
                size="small"
                :status="record.data?.confidence > 80 ? 'success' : 'normal'"
              />
            </template>
            <template v-else-if="column.key === 'actions'">
              <a-space>
                <a-button size="small" @click="viewSingleResult(index)">
                  查看
                </a-button>
                <a-button size="small" @click="saveSingleResult(record)">
                  保存
                </a-button>
              </a-space>
            </template>
          </template>
        </a-table>
      </a-card>
    </div>

    <!-- LLM配置抽屉 -->
    <a-drawer
      v-model:open="showLLMConfig"
      title="LLM配置"
      width="720px"
      placement="right"
    >
      <LLMApiConfig
        @config-updated="handleLLMConfigUpdated"
        @close-drawer="handleCloseDrawer"
        @close-modal="handleCloseDrawer"
      />
    </a-drawer>

    <!-- 帮助Modal -->
    <a-modal
      v-model:open="showHelp"
      title="使用帮助"
      width="800px"
      :footer="null"
    >
      <div class="help-content">
        <h3>批量智能导入使用指南</h3>
        <a-steps direction="vertical" size="small">
          <a-step title="上传文件">
            <template #description>
              <p>支持拖拽或点击上传多个医疗文档文件</p>
              <ul>
                <li>支持格式：PDF、Word、TXT</li>
                <li>单文件最大：50MB</li>
                <li>最多文件数：20个</li>
              </ul>
            </template>
          </a-step>
          <a-step title="批量解析">
            <template #description>
              <p>点击"一键解析所有文件"开始批量LLM解析</p>
              <ul>
                <li>支持暂停/继续/取消操作</li>
                <li>实时显示处理进度</li>
                <li>自动错误处理和重试</li>
              </ul>
            </template>
          </a-step>
          <a-step title="查看结果">
            <template #description>
              <p>解析完成后可查看详细结果</p>
              <ul>
                <li>按文件分组查看解析结果</li>
                <li>支持单个文件结果预览</li>
                <li>显示置信度和错误信息</li>
              </ul>
            </template>
          </a-step>
          <a-step title="保存导出">
            <template #description>
              <p>将解析结果保存到数据库或导出</p>
              <ul>
                <li>批量保存到数据库</li>
                <li>导出JSON/Excel格式</li>
                <li>支持单个文件操作</li>
              </ul>
            </template>
          </a-step>
        </a-steps>
      </div>
    </a-modal>

    <!-- 批量结果详情Modal -->
    <a-modal
      v-model:open="showBatchResultsModal"
      title="批量解析结果详情"
      width="1400px"
      :footer="null"
      class="batch-results-detail-modal"
    >
      <a-tabs v-model:activeKey="activeResultTab" type="card">
        <a-tab-pane 
          v-for="(result, index) in batchResults" 
          :key="index" 
          :tab="result.fileName"
        >
          <LLMResultModal
            :visible="true"
            :data="result.data"
            :result="result"
            :original-text="result.originalText"
            @update:visible="() => {}"
            @save-and-redirect="() => handleResultSave(result)"
            @save-only="() => handleResultSave(result)"
            @export-result="() => handleResultExport(result)"
            @export-pdf="() => handleResultExportPDF(result)"
            @go-to-import="() => {}"
          />
        </a-tab-pane>
      </a-tabs>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, h, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import {
  SettingOutlined,
  QuestionCircleOutlined,
  EyeOutlined,
  DownloadOutlined,
  DatabaseOutlined,
  FileOutlined,
  FilePdfOutlined,
  FileWordOutlined,
  FileTextOutlined
} from '@ant-design/icons-vue'
import BatchFileProcessor from '@/components/BatchFileProcessor.vue'
import LLMApiConfig from '@/components/LLMApiConfig.vue'
import LLMResultModal from '@/components/LLMResultModal.vue'

interface BatchResultItem {
  success?: boolean
  fileName?: string
  message?: string
  data?: {
    confidence?: number
    patientName?: string
    department?: string
  }
  originalText?: string
}

interface OperationLog {
  timestamp: Date
  message: string
  type: 'info' | 'success' | 'error' | 'warning'
}

const getErrorMessage = (error: unknown): string => {
  if (error instanceof Error) return error.message
  if (typeof error === 'object' && error && 'message' in error) {
    return String((error as { message?: unknown }).message || '未知错误')
  }
  return '未知错误'
}

const router = useRouter()

// 响应式数据
const showLLMConfig = ref(false)

// 监听全局关闭事件
const handleGlobalClose = () => {
  console.log('🎯 收到全局关闭事件，关闭LLM配置')
  showLLMConfig.value = false
}

onMounted(() => {
  window.addEventListener('llm-config-close', handleGlobalClose)
})

onUnmounted(() => {
  window.removeEventListener('llm-config-close', handleGlobalClose)
})
const showHelp = ref(false)
const showBatchResultsModal = ref(false)
const activeResultTab = ref(0)
const savingAll = ref(false)

const batchResults = ref<BatchResultItem[]>([])
const operationLogs = ref<OperationLog[]>([])
const totalProcessed = ref(0)
const successCount = ref(0)
const failureCount = ref(0)

// 计算属性
const averageConfidence = computed(() => {
  if (batchResults.value.length === 0) return 0
  const total = batchResults.value.reduce((sum, result) => {
    return sum + (result.data?.confidence || 0)
  }, 0)
  return Math.round(total / batchResults.value.length)
})

// 表格列定义
const resultColumns = [
  {
    title: '文件名',
    dataIndex: 'fileName',
    key: 'fileName',
    width: 200
  },
  {
    title: '状态',
    key: 'status',
    width: 80
  },
  {
    title: '患者姓名',
    dataIndex: ['data', 'patientName'],
    key: 'patientName',
    width: 120
  },
  {
    title: '科室',
    dataIndex: ['data', 'department'],
    key: 'department',
    width: 100
  },
  {
    title: '置信度',
    key: 'confidence',
    width: 120
  },
  {
    title: '操作',
    key: 'actions',
    width: 120
  }
]

// 方法
const addLog = (message: string, type: 'info' | 'success' | 'error' | 'warning' = 'info') => {
  operationLogs.value.unshift({
    timestamp: new Date(),
    message,
    type
  })
  
  // 限制日志数量
  if (operationLogs.value.length > 100) {
    operationLogs.value = operationLogs.value.slice(0, 100)
  }
}

const formatTime = (timestamp: Date) => {
  return timestamp.toLocaleTimeString()
}

const clearLogs = () => {
  operationLogs.value = []
}

const exportLogs = () => {
  const logText = operationLogs.value
    .map(log => `[${formatTime(log.timestamp)}] ${log.type.toUpperCase()}: ${log.message}`)
    .join('\n')
  
  const blob = new Blob([logText], { type: 'text/plain' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `operation_logs_${Date.now()}.txt`
  a.click()
  URL.revokeObjectURL(url)
}

const getFileIcon = (fileName: string) => {
  const ext = fileName.split('.').pop()?.toLowerCase()
  if (ext === 'pdf') return FilePdfOutlined
  if (['doc', 'docx'].includes(ext || '')) return FileWordOutlined
  if (ext === 'txt') return FileTextOutlined
  return FileOutlined
}

// 事件处理
const handleFilesProcessed = (results: BatchResultItem[]) => {
  addLog(`处理了 ${results.length} 个文件`, 'info')
}

const handleSingleFileProcessed = (result: BatchResultItem) => {
  totalProcessed.value++
  if (result.success) {
    successCount.value++
    addLog(`文件解析成功: ${result.fileName || '未知文件'}`, 'success')
  } else {
    failureCount.value++
    addLog(`文件解析失败: ${result.fileName || '未知文件'}`, 'error')
  }
}

const handleBatchCompleted = (results: BatchResultItem[]) => {
  batchResults.value = results
  addLog(`批量处理完成，共处理 ${results.length} 个文件`, 'success')
  message.success('批量处理完成!')
}

const handleLLMConfigUpdated = (config: unknown) => {
  addLog('LLM配置已更新', 'info')
}

const handleCloseDrawer = () => {
  showLLMConfig.value = false
  addLog('LLM配置弹窗已关闭', 'info')
}

const viewSingleResult = (index: number) => {
  activeResultTab.value = index
  showBatchResultsModal.value = true
}

const saveSingleResult = async (result: BatchResultItem) => {
  try {
    // 这里实现单个结果保存逻辑
    await new Promise(resolve => setTimeout(resolve, 1000))
    message.success(`保存 ${result.fileName} 成功`)
    addLog(`保存文件结果: ${result.fileName}`, 'success')
  } catch (error: unknown) {
    const errMsg = getErrorMessage(error)
    message.error(`保存失败: ${errMsg}`)
    addLog(`保存失败: ${result.fileName || '未知文件'} - ${errMsg}`, 'error')
  }
}

const exportAllResults = () => {
  const dataStr = JSON.stringify(batchResults.value, null, 2)
  const blob = new Blob([dataStr], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `batch_results_${Date.now()}.json`
  a.click()
  URL.revokeObjectURL(url)
  
  addLog('导出所有结果完成', 'success')
}

const saveAllToDatabase = async () => {
  savingAll.value = true
  try {
    // 这里实现批量保存逻辑
    await new Promise(resolve => setTimeout(resolve, 3000))
    message.success('批量保存成功!')
    addLog(`批量保存 ${batchResults.value.length} 个文件到数据库`, 'success')
  } catch (error: unknown) {
    const errMsg = getErrorMessage(error)
    message.error(`批量保存失败: ${errMsg}`)
    addLog(`批量保存失败: ${errMsg}`, 'error')
  } finally {
    savingAll.value = false
  }
}

const handleResultSave = (result: BatchResultItem) => {
  saveSingleResult(result)
}

const handleResultExport = (result: BatchResultItem) => {
  const dataStr = JSON.stringify(result, null, 2)
  const blob = new Blob([dataStr], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${result.fileName}_result.json`
  a.click()
  URL.revokeObjectURL(url)
}

const handleResultExportPDF = (result: BatchResultItem) => {
  message.info('PDF导出功能开发中...')
}

// 初始化
addLog('批量智能导入系统已就绪', 'info')
</script>

<style scoped>
.batch-smart-import-view {
  padding: 24px;
  background: #f5f5f5;
  min-height: 100vh;
}

.page-header {
  background: white;
  border-radius: 12px;
  padding: 24px;
  margin-bottom: 24px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

.header-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.title-section {
  flex: 1;
}

.page-title {
  margin: 0;
  font-size: 28px;
  font-weight: 600;
  color: #262626;
  background: linear-gradient(135deg, #1890ff, #52c41a);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.page-subtitle {
  margin: 8px 0 0 0;
  color: #8c8c8c;
  font-size: 14px;
}

.main-content {
  margin-bottom: 24px;
}

.batch-processor-card {
  border-radius: 12px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
}

.stats-card {
  border-radius: 12px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
}

.stats-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.stat-item {
  text-align: center;
  padding: 12px;
  background: #f8f9fa;
  border-radius: 8px;
}

.stat-value {
  font-size: 24px;
  font-weight: 600;
  color: #1890ff;
  margin-bottom: 4px;
}

.stat-label {
  font-size: 12px;
  color: #8c8c8c;
}

.log-card {
  border-radius: 12px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
}

.log-container {
  max-height: 300px;
  overflow-y: auto;
  background: #fafafa;
  border-radius: 6px;
  padding: 8px;
}

.log-item {
  padding: 6px 8px;
  margin-bottom: 4px;
  border-radius: 4px;
  font-size: 12px;
  border-left: 3px solid transparent;
}

.log-info {
  background: #f0f8ff;
  border-left-color: #1890ff;
}

.log-success {
  background: #f6ffed;
  border-left-color: #52c41a;
}

.log-error {
  background: #fff2f0;
  border-left-color: #ff4d4f;
}

.log-warning {
  background: #fffbe6;
  border-left-color: #faad14;
}

.log-time {
  color: #8c8c8c;
  font-size: 10px;
}

.log-message {
  color: #262626;
  margin-top: 2px;
}

.log-actions {
  margin-top: 8px;
  text-align: right;
}

.batch-summary {
  background: white;
  border-radius: 12px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
}

.summary-actions {
  text-align: center;
}

.file-name-cell {
  display: flex;
  align-items: center;
  gap: 8px;
}

.file-icon {
  color: #1890ff;
  font-size: 16px;
}

.help-content h3 {
  color: #262626;
  margin-bottom: 16px;
}

.help-content ul {
  margin: 8px 0;
  padding-left: 20px;
}

.help-content li {
  margin-bottom: 4px;
  color: #595959;
}

.batch-results-detail-modal :deep(.ant-modal-body) {
  padding: 0;
}

.mb-4 {
  margin-bottom: 16px;
}

/* 响应式设计 */
@media (max-width: 1200px) {
  .batch-smart-import-view {
    padding: 16px;
  }

  .main-content :deep(.ant-col) {
    margin-bottom: 16px;
  }
}

@media (max-width: 768px) {
  .batch-smart-import-view {
    padding: 8px;
  }

  .page-header {
    padding: 16px;
  }

  .header-content {
    flex-direction: column;
    gap: 16px;
    align-items: flex-start;
  }

  .page-title {
    font-size: 24px;
  }

  .stats-grid {
    grid-template-columns: 1fr;
  }

  .summary-actions :deep(.ant-space) {
    flex-wrap: wrap;
  }
}

/* 动画效果 */
.batch-processor-card,
.stats-card,
.log-card,
.batch-summary {
  animation: fadeInUp 0.6s ease-out;
}

@keyframes fadeInUp {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* 卡片悬停效果 */
.batch-processor-card:hover,
.stats-card:hover,
.log-card:hover {
  box-shadow: 0 6px 16px rgba(0, 0, 0, 0.12);
  transform: translateY(-2px);
  transition: all 0.3s ease;
}
</style>
