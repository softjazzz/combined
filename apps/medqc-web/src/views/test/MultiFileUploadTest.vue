<template>
  <div class="multi-file-upload-test">
    <div class="page-header">
      <h1>多文件上传测试</h1>
      <p>测试多文件选择和显示功能</p>
    </div>

    <div class="upload-section">
      <a-card title="文件上传测试">
        <!-- 文件上传区域 -->
        <a-upload-dragger
          :file-list="[]"
          :before-upload="beforeUpload"
          accept=".pdf,.doc,.docx,.txt"
          :multiple="true"
          :show-upload-list="false"
          @change="handleUploadChange"
          class="upload-area"
        >
          <p class="ant-upload-drag-icon">
            <InboxOutlined />
          </p>
          <p class="ant-upload-text">点击或拖拽文件到此区域上传</p>
          <p class="ant-upload-hint">
            支持 PDF、Word、文本文件格式，可批量上传
          </p>
        </a-upload-dragger>

        <!-- 调试信息 -->
        <div class="debug-info mt-4">
          <h3>调试信息</h3>
          <p>已选择文件数量: {{ uploadedFiles.length }}</p>
          <div v-if="debugLog.length > 0" class="debug-log">
            <h4>调试日志:</h4>
            <div v-for="(log, index) in debugLog" :key="index" class="log-item">
              {{ log }}
            </div>
          </div>
        </div>

        <!-- 文件列表 -->
        <div v-if="uploadedFiles.length > 0" class="file-list mt-4">
          <h3>已上传文件 ({{ uploadedFiles.length }})</h3>
          <a-list :data-source="uploadedFiles" size="small">
            <template #renderItem="{ item, index }">
              <a-list-item>
                <template #actions>
                  <a-button size="small" @click="removeFile(index)" danger>
                    删除
                  </a-button>
                </template>
                <a-list-item-meta>
                  <template #title>
                    <div class="file-title">
                      <FileOutlined class="file-icon" />
                      <span>{{ item.name }}</span>
                    </div>
                  </template>
                  <template #description>
                    <div class="file-details">
                      <span>大小: {{ formatFileSize(item.size) }}</span>
                      <span>类型: {{ item.type }}</span>
                      <span>上传时间: {{ item.uploadTime }}</span>
                    </div>
                  </template>
                </a-list-item-meta>
              </a-list-item>
            </template>
          </a-list>
        </div>

        <!-- 操作按钮 -->
        <div v-if="uploadedFiles.length > 0" class="actions mt-4">
          <a-space>
            <a-button type="primary" @click="processFiles">
              处理所有文件
            </a-button>
            <a-button @click="clearAllFiles" danger>
              清空所有文件
            </a-button>
          </a-space>
        </div>
      </a-card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { message } from 'ant-design-vue'
import { InboxOutlined, FileOutlined } from '@ant-design/icons-vue'

// 文件接口
interface UploadedFile {
  name: string
  size: number
  type: string
  file: File
  uploadTime: string
}

// 响应式数据
const uploadedFiles = ref<UploadedFile[]>([])
const debugLog = ref<string[]>([])

// 添加调试日志
const addDebugLog = (message: string) => {
  const timestamp = new Date().toLocaleTimeString()
  debugLog.value.unshift(`[${timestamp}] ${message}`)
  
  // 限制日志数量
  if (debugLog.value.length > 20) {
    debugLog.value = debugLog.value.slice(0, 20)
  }
}

// 文件验证
const beforeUpload = (file: File) => {
  addDebugLog(`beforeUpload 被调用: ${file.name}`)
  
  // 检查文件数量限制
  if (uploadedFiles.value.length >= 10) {
    message.error('最多只能上传10个文件')
    addDebugLog('文件数量超过限制')
    return false
  }

  // 检查文件类型
  const validTypes = [
    'application/pdf',
    'application/msword',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'text/plain'
  ]
  
  const fileName = file.name.toLowerCase()
  const validExtensions = ['.pdf', '.doc', '.docx', '.txt']
  const hasValidExtension = validExtensions.some(ext => fileName.endsWith(ext))
  
  const isValidType = validTypes.includes(file.type) || hasValidExtension
  if (!isValidType) {
    message.error(`文件 ${file.name} 格式不支持`)
    addDebugLog(`文件格式不支持: ${file.name}`)
    return false
  }

  // 检查文件大小
  const isLt50M = file.size / 1024 / 1024 < 50
  if (!isLt50M) {
    message.error(`文件 ${file.name} 大小超过限制`)
    addDebugLog(`文件大小超过限制: ${file.name}`)
    return false
  }

  addDebugLog(`文件验证通过: ${file.name}`)
  return false // 返回false，阻止默认上传
}

// 处理文件上传变化
const handleUploadChange = (info: unknown) => {
  addDebugLog(`handleUploadChange 被调用，文件数量: ${info.fileList?.length || 0}`)
  
  const { fileList } = info
  
  if (!fileList || fileList.length === 0) {
    addDebugLog('没有文件列表')
    return
  }
  
  // 处理新添加的文件
  fileList.forEach((fileItem: unknown, index: number) => {
    const file = fileItem.originFileObj || fileItem
    
    if (!file) {
      addDebugLog(`文件项 ${index} 没有文件对象`)
      return
    }
    
    // 检查是否已经添加过这个文件
    const exists = uploadedFiles.value.some(existingFile => 
      existingFile.name === file.name && existingFile.size === file.size
    )
    
    if (!exists) {
      addDebugLog(`添加新文件: ${file.name}`)
      addFileToList(file)
    } else {
      addDebugLog(`文件已存在，跳过: ${file.name}`)
    }
  })
}

// 添加文件到列表
const addFileToList = (file: File) => {
  try {
    const fileObj: UploadedFile = {
      name: file.name,
      size: file.size,
      type: file.type,
      file: file,
      uploadTime: new Date().toLocaleString()
    }

    uploadedFiles.value.push(fileObj)
    addDebugLog(`文件已添加到列表: ${file.name}，当前总数: ${uploadedFiles.value.length}`)
    
    message.success(`文件 ${file.name} 上传成功`)

  } catch (error: unknown) {
    addDebugLog(`文件处理失败: ${file.name} - ${error.message}`)
    message.error(`文件处理失败: ${file.name}`)
  }
}

// 删除文件
const removeFile = (index: number) => {
  const file = uploadedFiles.value[index]
  uploadedFiles.value.splice(index, 1)
  addDebugLog(`删除文件: ${file.name}`)
  message.info(`已删除文件: ${file.name}`)
}

// 清空所有文件
const clearAllFiles = () => {
  const count = uploadedFiles.value.length
  uploadedFiles.value = []
  addDebugLog(`清空所有文件，共 ${count} 个`)
  message.info(`已清空 ${count} 个文件`)
}

// 处理文件
const processFiles = () => {
  addDebugLog(`开始处理 ${uploadedFiles.value.length} 个文件`)
  message.info(`开始处理 ${uploadedFiles.value.length} 个文件`)
}

// 格式化文件大小
const formatFileSize = (bytes: number) => {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}

// 初始化
addDebugLog('多文件上传测试页面已加载')
</script>

<style scoped>
.multi-file-upload-test {
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

.upload-section {
  max-width: 800px;
  margin: 0 auto;
}

.upload-area {
  background: linear-gradient(135deg, #f0f8ff 0%, #e6f3ff 100%);
  border: 2px dashed #91d5ff;
  border-radius: 12px;
}

.upload-area:hover {
  border-color: #40a9ff;
  background: linear-gradient(135deg, #e6f3ff 0%, #d6ebff 100%);
}

.debug-info {
  background: #fafafa;
  padding: 16px;
  border-radius: 8px;
  border: 1px solid #e8e8e8;
}

.debug-log {
  margin-top: 12px;
  max-height: 200px;
  overflow-y: auto;
}

.log-item {
  font-size: 12px;
  color: #666;
  padding: 2px 0;
  font-family: monospace;
}

.file-list {
  background: white;
  padding: 16px;
  border-radius: 8px;
  border: 1px solid #e8e8e8;
}

.file-title {
  display: flex;
  align-items: center;
  gap: 8px;
}

.file-icon {
  color: #1890ff;
  font-size: 16px;
}

.file-details {
  display: flex;
  gap: 16px;
  font-size: 12px;
  color: #8c8c8c;
}

.actions {
  text-align: center;
}

.mt-4 {
  margin-top: 16px;
}
</style>
