<template>
  <div class="dataset-upload-panel">
    <!-- 数据模式指示器 -->
    <a-alert
      v-if="store.hasUploadedData"
      type="success"
      show-icon
      closable
      class="mode-alert"
    >
      <template #message>
        <span>📊 模板数据模式</span>
      </template>
      <template #description>
        <span>
          已加载 <strong>{{ store.meta?.name }}</strong> —
          {{ store.meta?.validCount }} 条有效病案，
          {{ store.meta?.departments.length }} 个科室，
          {{ store.meta?.drgGroupCount }} 个 DRG 组
        </span>
      </template>
    </a-alert>

    <a-alert
      v-else
      type="info"
      show-icon
      class="mode-alert"
    >
      <template #message>
        <span>🎭 演示数据模式</span>
      </template>
      <template #description>
        <span>当前展示内置演示数据。上传 Excel 模板可切换为自定义数据分析。</span>
      </template>
    </a-alert>

    <!-- 操作区 -->
    <div class="action-bar">
      <a-space :size="12">
        <a-button
          type="default"
          :loading="downloading"
          @click="handleDownloadTemplate"
        >
          <template #icon>
            <DownloadOutlined />
          </template>
          下载模板
        </a-button>

        <a-upload
          :before-upload="handleBeforeUpload"
          :show-upload-list="false"
          accept=".xlsx,.xls"
        >
          <a-button
            type="primary"
            :loading="store.importing"
          >
            <template #icon>
              <UploadOutlined />
            </template>
            上传数据
          </a-button>
        </a-upload>

        <a-popconfirm
          v-if="store.hasUploadedData"
          title="确认清除上传数据？将恢复为演示数据模式。"
          ok-text="确认"
          cancel-text="取消"
          @confirm="handleClear"
        >
          <a-button danger>
            <template #icon>
              <DeleteOutlined />
            </template>
            清除数据
          </a-button>
        </a-popconfirm>
      </a-space>
    </div>

    <!-- 校验结果 -->
    <div
      v-if="validationResult"
      class="validation-result"
    >
      <a-result
        v-if="validationResult.canImport && !validationResult.errors.length"
        status="success"
        :title="`成功导入 ${validationResult.validRows} 条病案`"
        :sub-title="validationResult.warnings.length
          ? `${validationResult.warnings.length} 条警告`
          : '所有数据校验通过'"
      />

      <a-result
        v-else-if="validationResult.canImport && validationResult.errors.length"
        status="warning"
        :title="`导入 ${validationResult.validRows} 条，跳过 ${validationResult.errors.length} 条`"
      >
        <template #extra>
          <a-collapse :bordered="false">
            <a-collapse-panel
              key="errors"
              header="查看跳过原因"
            >
              <div
                v-for="(err, idx) in validationResult.errors.slice(0, 20)"
                :key="idx"
                class="error-item"
              >
                第 {{ err.row }} 行 [{{ err.field }}]: {{ err.message }}
              </div>
              <div
                v-if="validationResult.errors.length > 20"
                class="error-item more"
              >
                ... 还有 {{ validationResult.errors.length - 20 }} 条错误
              </div>
            </a-collapse-panel>
          </a-collapse>
        </template>
      </a-result>

      <a-result
        v-else
        status="error"
        title="导入失败"
        sub-title="没有有效数据行，请检查模板格式"
      >
        <template #extra>
          <div
            v-for="(err, idx) in validationResult.errors.slice(0, 10)"
            :key="idx"
            class="error-item"
          >
            第 {{ err.row }} 行 [{{ err.field }}]: {{ err.message }}
          </div>
        </template>
      </a-result>

      <!-- 警告列表 -->
      <div
        v-if="validationResult.warnings.length"
        class="warnings"
      >
        <a-tag
          v-for="(w, idx) in validationResult.warnings.slice(0, 5)"
          :key="idx"
          color="warning"
        >
          {{ w }}
        </a-tag>
        <a-tag
          v-if="validationResult.warnings.length > 5"
          color="default"
        >
          ... 还有 {{ validationResult.warnings.length - 5 }} 条
        </a-tag>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { message } from 'ant-design-vue'
import { UploadOutlined, DownloadOutlined, DeleteOutlined } from '@ant-design/icons-vue'
import { useDrgDatasetStore } from '@/stores/drgDataset'
import type { ValidationResult } from '@/types/drg-dataset'

const store = useDrgDatasetStore()
const downloading = ref(false)
const validationResult = ref<ValidationResult | null>(null)

const emit = defineEmits<{
  /** 数据变更后通知父组件刷新 */
  (e: 'dataChanged'): void
}>()

/** 下载模板 */
const handleDownloadTemplate = async () => {
  downloading.value = true
  try {
    await store.downloadTemplate()
    message.success('模板下载成功，请填入数据后上传')
  } catch (error) {
    console.error('下载模板失败:', error)
    message.error('模板下载失败')
  } finally {
    downloading.value = false
  }
}

/** 上传前拦截：前端解析 */
const handleBeforeUpload = async (file: File) => {
  validationResult.value = null

  try {
    const result = await store.importFromExcel(file)
    validationResult.value = result.validation

    if (result.success) {
      message.success(`成功导入 ${result.validation.validRows} 条病案数据`)
      emit('dataChanged')
    } else {
      message.error('导入失败，请检查数据格式')
    }
  } catch (error: any) {
    console.error('导入失败:', error)
    message.error(error.message || '文件解析失败')
  }

  // 阻止默认上传行为（不向服务器发送）
  return false
}

/** 清除数据 */
const handleClear = () => {
  store.clearData()
  validationResult.value = null
  message.info('已清除上传数据，恢复为演示数据模式')
  emit('dataChanged')
}
</script>

<style scoped>
.dataset-upload-panel {
  margin-bottom: 16px;
}

.mode-alert {
  margin-bottom: 12px;
}

.action-bar {
  margin-bottom: 12px;
}

.validation-result {
  margin-top: 8px;
}

.validation-result :deep(.ant-result) {
  padding: 12px 16px;
}

.error-item {
  font-size: 12px;
  color: #666;
  padding: 2px 0;
  font-family: 'Consolas', 'Monaco', monospace;
}

.error-item.more {
  color: #999;
  font-style: italic;
}

.warnings {
  margin-top: 8px;
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}
</style>
