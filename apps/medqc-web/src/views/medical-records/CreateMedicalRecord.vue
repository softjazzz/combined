<template>
  <div class="page-container">
    <!-- 面包屑导航 -->
    <a-breadcrumb class="breadcrumb">
      <a-breadcrumb-item>
        <router-link to="/dashboard/medical-records">测试病历管理</router-link>
      </a-breadcrumb-item>
      <a-breadcrumb-item>新建病历</a-breadcrumb-item>
    </a-breadcrumb>

    <!-- 页面标题 -->
    <div class="page-header">
      <h1 class="page-title">新建病历</h1>
    </div>

    <!-- 表单内容 -->
    <a-form
      ref="formRef"
      :model="formData"
      :rules="formRules"
      layout="vertical"
      @finish="handleSubmit"
    >
      <!-- 病历基本信息 -->
      <a-card title="病历基本信息" class="form-card">
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item label="病历编号" name="recordNumber">
              <a-input 
                v-model:value="formData.recordNumber" 
                placeholder="自动生成"
                disabled
              />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="病历名称" name="recordName">
              <a-input 
                v-model:value="formData.recordName" 
                placeholder="请输入病历名称"
              />
            </a-form-item>
          </a-col>
        </a-row>
        
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item label="出院科室" name="department">
              <a-select 
                v-model:value="formData.department" 
                placeholder="请选择出院科室"
              >
                <a-select-option value="内科">内科</a-select-option>
                <a-select-option value="外科">外科</a-select-option>
                <a-select-option value="妇产科">妇产科</a-select-option>
                <a-select-option value="儿科">儿科</a-select-option>
                <a-select-option value="急诊科">急诊科</a-select-option>
                <a-select-option value="骨科">骨科</a-select-option>
                <a-select-option value="神经科">神经科</a-select-option>
                <a-select-option value="心内科">心内科</a-select-option>
              </a-select>
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="主诊断" name="primaryDiagnosis">
              <a-input 
                v-model:value="formData.primaryDiagnosis" 
                placeholder="请输入主诊断"
              />
            </a-form-item>
          </a-col>
        </a-row>

        <a-row :gutter="16">
          <a-col :span="24">
            <a-form-item label="主要手术及操作" name="majorSurgery">
              <a-textarea 
                v-model:value="formData.majorSurgery" 
                placeholder="请输入主要手术及操作（可选）"
                :rows="3"
              />
            </a-form-item>
          </a-col>
        </a-row>
      </a-card>

      <!-- 文书信息 -->
      <a-card title="文书信息" class="form-card">
        <div v-if="formData.documents.length === 0" class="no-documents">
          <a-empty description="暂无文书，请添加文书信息" />
        </div>
        
        <div v-else class="documents-list">
          <div 
            v-for="(document, index) in formData.documents" 
            :key="document.id"
            class="document-item"
          >
            <div class="document-header">
              <h4>文书{{ index + 1 }}: {{ document.type }}</h4>
              <a-button 
                type="text" 
                danger 
                size="small"
                @click="removeDocument(index)"
              >
                删除文书
              </a-button>
            </div>
            
            <a-row :gutter="16">
              <a-col :span="8">
                <a-form-item :name="['documents', index, 'type']" label="文书类型">
                  <a-select 
                    v-model:value="document.type" 
                    placeholder="请选择文书类型"
                  >
                    <a-select-option value="入院记录">入院记录</a-select-option>
                    <a-select-option value="病程记录">病程记录</a-select-option>
                    <a-select-option value="出院记录">出院记录</a-select-option>
                    <a-select-option value="手术记录">手术记录</a-select-option>
                    <a-select-option value="会诊记录">会诊记录</a-select-option>
                    <a-select-option value="检查报告">检查报告</a-select-option>
                    <a-select-option value="化验报告">化验报告</a-select-option>
                  </a-select>
                </a-form-item>
              </a-col>
              <a-col :span="16">
                <a-form-item :name="['documents', index, 'title']" label="文书标题">
                  <a-input 
                    v-model:value="document.title" 
                    placeholder="请输入文书标题"
                  />
                </a-form-item>
              </a-col>
            </a-row>
            
            <a-form-item :name="['documents', index, 'content']" label="文书内容">
              <a-textarea 
                v-model:value="document.content" 
                placeholder="请输入文书内容"
                :rows="6"
              />
            </a-form-item>
          </div>
        </div>
      </a-card>

      <!-- 操作按钮 -->
      <div class="form-actions">
        <div class="left-actions">
          <a-button 
            type="dashed" 
            @click="addDocument"
          >
            <template #icon><PlusOutlined /></template>
            新建文书
          </a-button>
        </div>
        
        <div class="right-actions">
          <a-space>
            <a-button @click="handleCancel">取消</a-button>
            <a-button 
              type="primary" 
              html-type="submit"
              :loading="submitting"
            >
              新建
            </a-button>
          </a-space>
        </div>
      </div>
    </a-form>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { PlusOutlined } from '@ant-design/icons-vue'
import type { FormInstance } from 'ant-design-vue'

const router = useRouter()
const formRef = ref<FormInstance>()
const submitting = ref(false)

// 表单数据
const formData = reactive({
  recordNumber: '',
  recordName: '',
  department: '',
  primaryDiagnosis: '',
  majorSurgery: '',
  documents: [] as Array<{
    id: string
    type: string
    title: string
    content: string
  }>
})

// 表单验证规则
const formRules = {
  recordName: [
    { required: true, message: '请输入病历名称', trigger: 'blur' }
  ],
  department: [
    { required: true, message: '请选择出院科室', trigger: 'change' }
  ],
  primaryDiagnosis: [
    { required: true, message: '请输入主诊断', trigger: 'blur' }
  ]
}

// 生命周期
onMounted(() => {
  generateRecordNumber()
})

// 生成病历编号
const generateRecordNumber = () => {
  const now = new Date()
  const year = now.getFullYear()
  const month = String(now.getMonth() + 1).padStart(2, '0')
  const day = String(now.getDate()).padStart(2, '0')
  const random = Math.floor(Math.random() * 1000).toString().padStart(3, '0')
  formData.recordNumber = `MR${year}${month}${day}${random}`
}

// 添加文书
const addDocument = () => {
  const newDocument = {
    id: `doc_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
    type: '入院记录',
    title: '',
    content: ''
  }
  formData.documents.push(newDocument)
}

// 删除文书
const removeDocument = (index: number) => {
  formData.documents.splice(index, 1)
}

// 提交表单
const handleSubmit = async () => {
  try {
    submitting.value = true
    
    // 模拟API调用
    await new Promise(resolve => setTimeout(resolve, 1500))
    
    message.success('病历创建成功')
    router.push('/dashboard/medical-records')
  } catch (error) {
    message.error('创建失败，请重试')
  } finally {
    submitting.value = false
  }
}

// 取消操作
const handleCancel = () => {
  router.back()
}
</script>

<style scoped>
/* 整体布局 */
.page-container {
  @apply p-3;
}

.breadcrumb {
  @apply mb-3;
}

.page-header {
  @apply mb-3;
}

.page-title {
  @apply text-lg font-bold text-gray-900;
  font-size: 16px;
}

/* 表单卡片 */
.form-card {
  @apply mb-3 shadow-sm;
}

:deep(.form-card .ant-card-body) {
  padding: 16px !important;
}

:deep(.form-card .ant-card-head) {
  padding: 0 16px !important;
  min-height: 40px !important;
}

:deep(.form-card .ant-card-head-title) {
  font-size: 14px !important;
  font-weight: 600 !important;
  padding: 8px 0 !important;
}

/* 表单项优化 */
:deep(.ant-form-item-label > label) {
  font-size: 12px !important;
  font-weight: 500 !important;
}

:deep(.ant-input) {
  font-size: 12px !important;
  height: 28px !important;
  padding: 3px 8px !important;
}

:deep(.ant-input-disabled) {
  background-color: #f5f5f5 !important;
  color: #999 !important;
}

:deep(.ant-select) {
  font-size: 12px !important;
}

:deep(.ant-select-selector) {
  font-size: 12px !important;
  height: 28px !important;
  padding: 0 8px !important;
}

:deep(.ant-select-selection-item) {
  font-size: 12px !important;
  line-height: 26px !important;
}

:deep(.ant-select-selection-placeholder) {
  font-size: 12px !important;
  line-height: 26px !important;
}

:deep(.ant-input) {
  font-size: 12px !important;
}

/* 文书相关样式 */
.no-documents {
  @apply text-center py-8;
}

.documents-list {
  @apply space-y-4;
}

.document-item {
  @apply border border-gray-200 rounded-lg p-4 bg-gray-50;
}

.document-header {
  @apply flex items-center justify-between mb-3;
}

.document-header h4 {
  @apply text-sm font-semibold text-gray-900 m-0;
}

/* 操作按钮区域 */
.form-actions {
  @apply flex items-center justify-between mt-6 pt-4 border-t border-gray-200;
}

.left-actions {
  @apply flex items-center;
}

.right-actions {
  @apply flex items-center;
}

/* 按钮样式优化 */
:deep(.ant-btn) {
  font-size: 12px !important;
  height: 28px !important;
  padding: 3px 12px !important;
}

:deep(.ant-btn-dashed) {
  border-style: dashed !important;
}

/* 面包屑样式 */
:deep(.ant-breadcrumb) {
  font-size: 12px !important;
}

:deep(.ant-breadcrumb a) {
  color: #1890ff !important;
  text-decoration: none !important;
}

:deep(.ant-breadcrumb a:hover) {
  color: #40a9ff !important;
}

/* 空状态样式 */
:deep(.ant-empty-description) {
  font-size: 12px !important;
  color: #999 !important;
}

/* 文本域样式 */
:deep(.ant-input) {
  font-size: 12px !important;
  line-height: 1.4 !important;
}

/* 表单验证错误样式 */
:deep(.ant-form-item-explain-error) {
  font-size: 11px !important;
}
</style>
