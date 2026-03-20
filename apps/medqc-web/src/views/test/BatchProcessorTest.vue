<template>
  <div class="batch-processor-test">
    <div class="page-header">
      <h1>批量文件处理测试</h1>
      <p>测试批量文件上传和LLM解析功能</p>
    </div>

    <div class="test-content">
      <a-card title="批量文件处理组件测试">
        <BatchFileProcessor
          :max-file-size="50"
          :max-file-count="10"
          :allowed-types="['.pdf', '.doc', '.docx', '.txt']"
          @files-processed="handleFilesProcessed"
          @single-file-processed="handleSingleFileProcessed"
          @batch-completed="handleBatchCompleted"
        />
      </a-card>

      <a-card title="处理日志" class="mt-4">
        <div class="log-container">
          <div 
            v-for="(log, index) in logs" 
            :key="index"
            :class="['log-item', `log-${log.type}`]"
          >
            <span class="log-time">{{ formatTime(log.timestamp) }}</span>
            <span class="log-message">{{ log.message }}</span>
          </div>
        </div>
        <div class="log-actions mt-2">
          <a-button size="small" @click="clearLogs">清空日志</a-button>
        </div>
      </a-card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { message } from 'ant-design-vue'
import BatchFileProcessor from '@/components/BatchFileProcessor.vue'

// 响应式数据
const logs = ref<any[]>([])

// 方法
const addLog = (message: string, type: 'info' | 'success' | 'error' | 'warning' = 'info') => {
  logs.value.unshift({
    timestamp: new Date(),
    message,
    type
  })
  
  // 限制日志数量
  if (logs.value.length > 50) {
    logs.value = logs.value.slice(0, 50)
  }
}

const formatTime = (timestamp: Date) => {
  return timestamp.toLocaleTimeString()
}

const clearLogs = () => {
  logs.value = []
}

// 事件处理
const handleFilesProcessed = (results: unknown[]) => {
  addLog(`处理了 ${results.length} 个文件`, 'info')
  message.info(`处理了 ${results.length} 个文件`)
}

const handleSingleFileProcessed = (result: { success?: boolean; fileName?: string }) => {
  if (result.success) {
    addLog(`文件解析成功: ${result.fileName || '未知文件'}`, 'success')
  } else {
    addLog(`文件解析失败: ${result.fileName || '未知文件'}`, 'error')
  }
}

const handleBatchCompleted = (results: Array<{ success?: boolean; fileName?: string }>) => {
  const successCount = results.filter(r => r.success).length
  const failCount = results.length - successCount
  
  addLog(`批量处理完成: 成功 ${successCount} 个，失败 ${failCount} 个`, 'success')
  message.success(`批量处理完成: 成功 ${successCount} 个，失败 ${failCount} 个`)
}

// 初始化
addLog('批量文件处理测试页面已加载', 'info')
</script>

<style scoped>
.batch-processor-test {
  padding: 24px;
  background: #f5f5f5;
  min-height: 100vh;
}

.page-header {
  text-align: center;
  margin-bottom: 24px;
}

.page-header h1 {
  font-size: 28px;
  color: #262626;
  margin-bottom: 8px;
}

.page-header p {
  color: #8c8c8c;
  font-size: 14px;
}

.test-content {
  max-width: 1200px;
  margin: 0 auto;
}

.log-container {
  max-height: 300px;
  overflow-y: auto;
  background: #fafafa;
  border-radius: 6px;
  padding: 8px;
}

.log-item {
  display: flex;
  gap: 12px;
  padding: 4px 8px;
  margin-bottom: 2px;
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
  min-width: 80px;
}

.log-message {
  color: #262626;
  flex: 1;
}

.log-actions {
  text-align: right;
}

.mt-4 {
  margin-top: 16px;
}

.mt-2 {
  margin-top: 8px;
}
</style>
