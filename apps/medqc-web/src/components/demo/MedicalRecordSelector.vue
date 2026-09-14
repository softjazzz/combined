<!--
  病历选择器组件
  支持预置示例和自定义输入两种模式
-->
<template>
  <a-card
    title="病历选择"
    :bordered="false"
  >
    <!-- 模式选择 -->
    <a-radio-group
      v-model:value="selectedMode"
      button-style="solid"
      class="mb-4"
    >
      <a-radio-button value="preset">
        <template #icon>
          <FileTextOutlined />
        </template>
        预置示例
      </a-radio-button>
      <a-radio-button value="custom">
        <template #icon>
          <EditOutlined />
        </template>
        自定义输入
      </a-radio-button>
    </a-radio-group>

    <!-- 预置示例模式 -->
    <div
      v-if="selectedMode === 'preset'"
      class="preset-mode"
    >
      <a-alert
        message="预置示例：首次病程记录"
        description="李明，58岁男性，急性冠脉综合征（ACS），包含完整的病历结构和质控缺陷示例"
        type="info"
        show-icon
        class="mb-4"
      />
      
      <a-descriptions
        :column="2"
        bordered
        size="small"
        class="mb-4"
      >
        <a-descriptions-item label="文档类型">
          首次病程记录
        </a-descriptions-item>
        <a-descriptions-item label="患者姓名">
          李明
        </a-descriptions-item>
        <a-descriptions-item label="年龄/性别">
          58岁/男
        </a-descriptions-item>
        <a-descriptions-item label="科室">
          心内科
        </a-descriptions-item>
        <a-descriptions-item label="住院号">
          2025001234
        </a-descriptions-item>
        <a-descriptions-item label="床号">
          15床
        </a-descriptions-item>
        <a-descriptions-item label="入院时间">
          2025年10月11日 09:30
        </a-descriptions-item>
        <a-descriptions-item label="记录时间">
          2025年10月11日 15:00
        </a-descriptions-item>
        <a-descriptions-item
          label="初步诊断"
          :span="2"
        >
          急性冠脉综合征（ACS）、高血压病3级、2型糖尿病、血脂异常
        </a-descriptions-item>
      </a-descriptions>

      <a-button
        type="primary"
        block
        size="large"
        @click="handleLoadPreset"
      >
        <template #icon>
          <ThunderboltOutlined />
        </template>
        加载预置示例
      </a-button>
    </div>

    <!-- 自定义输入模式 -->
    <div
      v-else
      class="custom-mode"
    >
      <a-tabs v-model:active-key="customInputTab">
        <!-- 文本输入 -->
        <a-tab-pane
          key="text"
          tab="文本输入"
        >
          <a-form layout="vertical">
            <a-form-item label="文档类型">
              <a-select
                v-model:value="customDocumentType"
                placeholder="请选择文档类型"
              >
                <a-select-option value="首次病程记录">
                  首次病程记录
                </a-select-option>
                <a-select-option value="入院记录">
                  入院记录
                </a-select-option>
                <a-select-option value="出院记录">
                  出院记录
                </a-select-option>
                <a-select-option value="手术记录">
                  手术记录
                </a-select-option>
                <a-select-option value="病程记录">
                  病程记录
                </a-select-option>
              </a-select>
            </a-form-item>

            <a-form-item label="病历内容">
              <a-textarea
                v-model:value="customContent"
                placeholder="请输入病历内容..."
                :rows="12"
                show-count
                :maxlength="50000"
              />
            </a-form-item>

            <a-button
              type="primary"
              block
              size="large"
              :disabled="!customContent.trim()"
              @click="handleSetCustom"
            >
              <template #icon>
                <CheckOutlined />
              </template>
              使用此病历
            </a-button>
          </a-form>
        </a-tab-pane>

        <!-- 文件上传 -->
        <a-tab-pane
          key="upload"
          tab="文件上传"
        >
          <a-upload-dragger
            v-model:file-list="fileList"
            name="file"
            :multiple="false"
            :before-upload="beforeUpload"
            :custom-request="handleUpload"
            accept=".txt,.doc,.docx"
            :max-count="1"
          >
            <p class="ant-upload-drag-icon">
              <InboxOutlined />
            </p>
            <p class="ant-upload-text">
              点击或拖拽文件到此区域上传
            </p>
            <p class="ant-upload-hint">
              支持 .txt、.doc、.docx 格式，单个文件不超过 10MB
            </p>
          </a-upload-dragger>

          <a-alert
            v-if="uploadedContent"
            message="文件已上传"
            :description="`文件大小：${uploadedFileSize}，内容长度：${uploadedContent.length} 字符`"
            type="success"
            show-icon
            closable
            class="mt-4"
          />

          <a-button
            v-if="uploadedContent"
            type="primary"
            block
            size="large"
            class="mt-4"
            @click="handleUseUploadedContent"
          >
            <template #icon>
              <CheckOutlined />
            </template>
            使用上传的病历
          </a-button>
        </a-tab-pane>
      </a-tabs>
    </div>

    <!-- 病历内容预览（可折叠） -->
    <a-collapse
      v-if="previewContent"
      class="mt-4"
    >
      <a-collapse-panel
        key="preview"
        header="病历内容预览"
      >
        <div class="preview-content">
          {{ previewContent }}
        </div>
      </a-collapse-panel>
    </a-collapse>
  </a-card>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { message } from 'ant-design-vue'
import {
  FileTextOutlined,
  EditOutlined,
  ThunderboltOutlined,
  CheckOutlined,
  InboxOutlined
} from '@ant-design/icons-vue'
import type { UploadProps } from 'ant-design-vue'

// ========== Props & Emits ==========

const emit = defineEmits<{
  loadPreset: []
  setCustom: [content: string, type: string]
}>()

// ========== 状态 ==========

// 选择的模式：预置示例 or 自定义输入
const selectedMode = ref<'preset' | 'custom'>('preset')

// 自定义输入相关
const customInputTab = ref<'text' | 'upload'>('text')
const customDocumentType = ref<string>('首次病程记录')
const customContent = ref<string>('')

// 文件上传相关
const fileList = ref<any[]>([])
const uploadedContent = ref<string>('')
const uploadedFileSize = ref<string>('')

// 病历内容预览
const previewContent = ref<string>('')

// ========== 方法 ==========

/**
 * 加载预置示例
 */
const handleLoadPreset = () => {
  emit('loadPreset')
  previewContent.value = '预置示例已加载（首次病程记录 - 李明，58岁男性）'
  message.success('已加载预置示例病历')
}

/**
 * 使用自定义文本
 */
const handleSetCustom = () => {
  if (!customContent.value.trim()) {
    message.warning('请输入病历内容')
    return
  }

  emit('setCustom', customContent.value, customDocumentType.value)
  previewContent.value = customContent.value
  message.success('已设置自定义病历')
}

/**
 * 文件上传前的校验
 */
const beforeUpload: UploadProps['beforeUpload'] = (file) => {
  const isValidType = ['text/plain', 'application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'].includes(file.type)
  if (!isValidType) {
    message.error('只支持 .txt、.doc、.docx 格式的文件')
    return false
  }

  const isLt10M = file.size / 1024 / 1024 < 10
  if (!isLt10M) {
    message.error('文件大小不能超过 10MB')
    return false
  }

  return true
}

/**
 * 自定义文件上传处理
 */
const handleUpload: UploadProps['customRequest'] = async (options) => {
  const { file } = options

  try {
    // 读取文件内容
    const reader = new FileReader()
    
    reader.onload = (e) => {
      const content = e.target?.result as string
      uploadedContent.value = content
      uploadedFileSize.value = formatFileSize((file as File).size)
      
      message.success('文件上传成功')
    }

    reader.onerror = () => {
      message.error('文件读取失败')
    }

    // 读取为文本
    reader.readAsText(file as File, 'UTF-8')

  } catch (error) {
    console.error('文件上传失败:', error)
    message.error('文件上传失败')
  }
}

/**
 * 使用上传的病历内容
 */
const handleUseUploadedContent = () => {
  if (!uploadedContent.value) {
    message.warning('请先上传文件')
    return
  }

  emit('setCustom', uploadedContent.value, customDocumentType.value)
  previewContent.value = uploadedContent.value
  message.success('已使用上传的病历')
}

/**
 * 格式化文件大小
 */
const formatFileSize = (bytes: number): string => {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i]
}

// ========== 监听 ==========

// 切换模式时清空预览
watch(selectedMode, () => {
  previewContent.value = ''
})
</script>

<style scoped lang="less">
.preset-mode {
  .ant-descriptions {
    margin-bottom: 16px;
  }
}

.custom-mode {
  .ant-form-item {
    margin-bottom: 16px;
  }
}

.preview-content {
  max-height: 400px;
  overflow-y: auto;
  white-space: pre-wrap;
  word-wrap: break-word;
  font-family: 'Courier New', monospace;
  font-size: 12px;
  line-height: 1.6;
  padding: 12px;
  background-color: #f5f5f5;
  border-radius: 4px;
}

.ant-upload-drag-icon {
  font-size: 48px;
  color: #2b6cf6;
}
</style>

