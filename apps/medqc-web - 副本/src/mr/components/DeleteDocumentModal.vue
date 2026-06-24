<template>
  <a-modal
    :open="visible"
    title="删除文档确认"
    width="500px"
    :confirm-loading="loading"
    @ok="handleConfirm"
    @cancel="handleCancel"
  >
    <div class="delete-confirmation">
      <div class="warning-icon">
        <ExclamationCircleOutlined style="color: #ff4d4f; font-size: 24px;" />
      </div>
      
      <div class="confirmation-content">
        <h4>确定要删除以下文档吗？</h4>
        <div class="document-info">
          <p><strong>文档标题：</strong>{{ documentTitle }}</p>
          <p><strong>文档类型：</strong>{{ documentType }}</p>
        </div>
        
        <div class="delete-options">
          <a-radio-group
            v-model:value="deleteType"
            class="delete-type-group"
          >
            <a-radio value="soft">
              <div class="radio-option">
                <div class="option-title">
                  软删除（推荐）
                </div>
                <div class="option-description">
                  标记为已删除，可以恢复，保留审计记录
                </div>
              </div>
            </a-radio>
            <a-radio value="hard">
              <div class="radio-option">
                <div class="option-title">
                  永久删除
                </div>
                <div class="option-description">
                  彻底删除文档，无法恢复，请谨慎操作
                </div>
              </div>
            </a-radio>
          </a-radio-group>
        </div>
        
        <a-alert
          v-if="deleteType === 'hard'"
          message="警告"
          description="永久删除操作无法撤销，请确认您真的要删除此文档。"
          type="warning"
          show-icon
          class="warning-alert"
        />
      </div>
    </div>

    <template #footer>
      <a-space>
        <a-button @click="handleCancel">
          取消
        </a-button>
        <a-button 
          type="primary" 
          danger 
          :loading="loading" 
          @click="handleConfirm"
        >
          {{ deleteType === 'hard' ? '永久删除' : '删除' }}
        </a-button>
      </a-space>
    </template>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { message } from 'ant-design-vue'
import { ExclamationCircleOutlined } from '@ant-design/icons-vue'

interface Props {
  visible: boolean
  documentId: string
  documentTitle: string
  documentType: string
}

const props = withDefaults(defineProps<Props>(), {
  visible: false,
  documentId: '',
  documentTitle: '',
  documentType: ''
})

const emit = defineEmits<{
  'update:visible': [value: boolean]
  'success': [result: unknown]
}>()

// 响应式数据
const loading = ref(false)
const deleteType = ref<'soft' | 'hard'>('soft')

// 监听visible变化，重置状态
watch(() => props.visible, (newVisible) => {
  if (newVisible) {
    deleteType.value = 'soft'
  }
})

// 确认删除
const handleConfirm = async () => {
  if (!props.documentId) {
    message.error('文档ID不能为空')
    return
  }

  try {
    loading.value = true

    const url = `/api/medical-documents/${props.documentId}${deleteType.value === 'hard' ? '?hard_delete=true' : ''}`
    
    const response = await fetch(url, {
      method: 'DELETE',
      headers: {
        'Content-Type': 'application/json'
      }
    })

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}))
      throw new Error(errorData.detail || `删除失败: ${response.status}`)
    }

    const result = await response.json()
    
    const operationType = deleteType.value === 'hard' ? '永久删除' : '删除'
    message.success(`文档${operationType}成功`)
    
    emit('success', {
      ...result,
      deleteType: deleteType.value
    })
    emit('update:visible', false)
    
  } catch (error: unknown) {
    console.error('删除文档失败:', error)
    message.error(error instanceof Error ? error.message : '删除文档失败')
  } finally {
    loading.value = false
  }
}

// 取消操作
const handleCancel = () => {
  emit('update:visible', false)
}
</script>

<style scoped>
.delete-confirmation {
  display: flex;
  gap: 16px;
  padding: 16px 0;
}

.warning-icon {
  flex-shrink: 0;
  margin-top: 4px;
}

.confirmation-content {
  flex: 1;
}

.confirmation-content h4 {
  margin: 0 0 16px 0;
  font-size: 16px;
  font-weight: 500;
  color: #262626;
}

.document-info {
  background: #fafafa;
  padding: 12px;
  border-radius: 6px;
  margin-bottom: 16px;
}

.document-info p {
  margin: 4px 0;
  color: #595959;
}

.delete-options {
  margin-bottom: 16px;
}

.delete-type-group {
  width: 100%;
}

.delete-type-group :deep(.ant-radio-wrapper) {
  display: block;
  margin-bottom: 12px;
  padding: 12px;
  border: 1px solid #d9d9d9;
  border-radius: 6px;
  transition: all 0.2s;
}

.delete-type-group :deep(.ant-radio-wrapper:hover) {
  border-color: #1890ff;
}

.delete-type-group :deep(.ant-radio-wrapper-checked) {
  border-color: #1890ff;
  background: #f6ffed;
}

.delete-type-group :deep(.ant-radio-wrapper-checked:last-child) {
  background: #fff2f0;
  border-color: #ff4d4f;
}

.radio-option {
  margin-left: 8px;
}

.option-title {
  font-weight: 500;
  color: #262626;
  margin-bottom: 4px;
}

.option-description {
  font-size: 12px;
  color: #8c8c8c;
  line-height: 1.4;
}

.warning-alert {
  margin-top: 8px;
}

:deep(.ant-alert-warning) {
  border: 1px solid #ffccc7;
  background: #fff2f0;
}
</style>
