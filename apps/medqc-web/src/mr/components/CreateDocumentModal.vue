<template>
  <a-modal
    :open="visible"
    title="新增医疗文档"
    width="800px"
    :confirm-loading="loading"
    @ok="handleSubmit"
    @cancel="handleCancel"
  >
    <a-form
      ref="formRef"
      :model="formData"
      :rules="rules"
      layout="vertical"
      class="create-document-form"
    >
      <!-- 文档类型选择 -->
      <a-form-item label="文档类型" name="documentType" required>
        <a-select
          v-model:value="formData.documentType"
          placeholder="请选择文档类型"
          show-search
          :filter-option="filterOption"
          @change="handleTypeChange"
        >
          <a-select-opt-group
            v-for="category in documentTypes"
            :key="category.category_id"
            :label="category.category_name"
          >
            <a-select-option
              v-for="type in category.types"
              :key="`${category.category_code}.${type.type_code}`"
              :value="`${category.category_code}.${type.type_code}`"
              :label="type.type_name"
            >
              {{ type.type_name }}
              <span class="type-description" v-if="type.description">
                - {{ type.description }}
              </span>
            </a-select-option>
          </a-select-opt-group>
        </a-select>
      </a-form-item>

      <!-- 文档标题 -->
      <a-form-item label="文档标题" name="title" required>
        <a-input
          v-model:value="formData.title"
          placeholder="请输入文档标题"
          :maxlength="200"
          show-count
        />
      </a-form-item>

      <!-- 文档内容 -->
      <a-form-item label="文档内容" name="content" required>
        <a-textarea
          v-model:value="formData.content"
          placeholder="请输入文档内容..."
          :auto-size="{ minRows: 8, maxRows: 20 }"
          :maxlength="10000"
          show-count
        />
      </a-form-item>

      <!-- 文档摘要（可选） -->
      <a-form-item label="文档摘要（可选）" name="summary">
        <a-textarea
          v-model:value="formData.summary"
          placeholder="请输入文档摘要，留空将自动生成..."
          :auto-size="{ minRows: 2, maxRows: 4 }"
          :maxlength="500"
          show-count
        />
      </a-form-item>
    </a-form>

    <template #footer>
      <a-space>
        <a-button @click="handleCancel">取消</a-button>
        <a-button type="primary" :loading="loading" @click="handleSubmit">
          创建文档
        </a-button>
      </a-space>
    </template>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, reactive, watch } from 'vue'
import { message } from 'ant-design-vue'
import type { FormInstance } from 'ant-design-vue'

interface DocumentType {
  id: string
  category_id: string
  category_code: string
  category_name: string
  type_code: string
  type_name: string
  description?: string
  sort_order: number
}

interface DocumentCategory {
  category_id: string
  category_code: string
  category_name: string
  description?: string
  types: DocumentType[]
}

interface CreateDocumentForm {
  documentType: string
  title: string
  content: string
  summary: string
}

interface Props {
  visible: boolean
  recordId: string
  documentTypes: DocumentCategory[]
}

const props = withDefaults(defineProps<Props>(), {
  visible: false,
  recordId: '',
  documentTypes: () => []
})

const emit = defineEmits<{
  'update:visible': [value: boolean]
  'success': [document: unknown]
}>()

// 响应式数据
const formRef = ref<FormInstance>()
const loading = ref(false)

const formData = reactive<CreateDocumentForm>({
  documentType: '',
  title: '',
  content: '',
  summary: ''
})

// 表单验证规则
const rules = {
  documentType: [
    { required: true, message: '请选择文档类型', trigger: 'change' }
  ],
  title: [
    { required: true, message: '请输入文档标题', trigger: 'blur' },
    { min: 2, max: 200, message: '标题长度应在2-200字符之间', trigger: 'blur' }
  ],
  content: [
    { required: true, message: '请输入文档内容', trigger: 'blur' },
    { min: 10, message: '内容至少需要10个字符', trigger: 'blur' }
  ]
}

// 监听visible变化，重置表单
watch(() => props.visible, (newVisible) => {
  if (newVisible) {
    resetForm()
  }
})

// 重置表单
const resetForm = () => {
  formData.documentType = ''
  formData.title = ''
  formData.content = ''
  formData.summary = ''
  formRef.value?.clearValidate()
}

// 文档类型选择过滤
const filterOption = (input: string, option: unknown) => {
  const normalized = (option || {}) as { label?: string; value?: string }
  const label = normalized.label || ''
  const value = normalized.value || ''
  return label.toLowerCase().includes(input.toLowerCase()) ||
         value.toLowerCase().includes(input.toLowerCase())
}

// 处理类型变化
const handleTypeChange = (value: string) => {
  // 根据选择的类型自动填充标题建议
  if (value && !formData.title) {
    const [categoryCode, typeCode] = value.split('.')
    const category = props.documentTypes.find(cat => cat.category_code === categoryCode)
    const type = category?.types.find(t => t.type_code === typeCode)
    if (type) {
      formData.title = type.type_name
    }
  }
}

// 提交表单
const handleSubmit = async () => {
  try {
    await formRef.value?.validate()
    loading.value = true

    const [categoryCode, typeCode] = formData.documentType.split('.')
    
    const requestData = {
      title: formData.title,
      content: formData.content,
      summary: formData.summary || undefined,
      document_type: formData.documentType,
      category_code: categoryCode,
      type_code: typeCode
    }

    const response = await fetch(`/api/medical-records/${props.recordId}/documents`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(requestData)
    })

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}))
      throw new Error(errorData.detail || `创建失败: ${response.status}`)
    }

    const result = await response.json()
    
    message.success('文档创建成功')
    emit('success', result.document)
    emit('update:visible', false)
    
  } catch (error: unknown) {
    console.error('创建文档失败:', error)
    message.error(error instanceof Error ? error.message : '创建文档失败')
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
.create-document-form {
  padding: 16px 0;
}

.type-description {
  color: #999;
  font-size: 12px;
}

:deep(.ant-select-selection-item) {
  display: flex;
  align-items: center;
}

:deep(.ant-form-item-label) {
  font-weight: 500;
}

:deep(.ant-input-show-count-suffix) {
  color: #999;
}

:deep(.ant-textarea-show-count::after) {
  color: #999;
}
</style>
