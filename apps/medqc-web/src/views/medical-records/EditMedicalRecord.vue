<template>
  <div class="page-container">
    <!-- 面包屑导航 -->
    <a-breadcrumb class="breadcrumb">
      <a-breadcrumb-item>
        <router-link to="/dashboard/medical-records"> 测试病历管理 </router-link>
      </a-breadcrumb-item>
      <a-breadcrumb-item>编辑病历</a-breadcrumb-item>
    </a-breadcrumb>

    <!-- 页面标题 -->
    <div class="page-header">
      <h1 class="page-title">编辑病历</h1>
      <div class="record-info">
        <span class="record-number">{{ formData.recordNumber }}</span>
      </div>
    </div>

    <!-- 加载状态 -->
    <div v-if="loading" class="loading-container">
      <a-spin size="large" tip="加载病历数据中..." />
    </div>

    <!-- 表单内容 -->
    <a-form
      v-else
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
              <a-input v-model:value="formData.recordNumber" disabled />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="病历名称" name="recordName">
              <a-input v-model:value="formData.recordName" placeholder="请输入病历名称" />
            </a-form-item>
          </a-col>
        </a-row>
      </a-card>

      <!-- 患者信息 -->
      <a-card title="患者信息" class="form-card">
        <a-row :gutter="16">
          <a-col :span="8">
            <a-form-item label="患者姓名" name="patientName">
              <a-input v-model:value="formData.patientName" placeholder="请输入患者姓名" />
            </a-form-item>
          </a-col>
          <a-col :span="8">
            <a-form-item label="年龄" name="patientAge">
              <a-input-number
                v-model:value="formData.patientAge"
                placeholder="请输入年龄"
                :min="0"
                :max="150"
                style="width: 100%"
              />
            </a-form-item>
          </a-col>
          <a-col :span="8">
            <a-form-item label="性别" name="patientGender">
              <a-select v-model:value="formData.patientGender" placeholder="请选择性别">
                <a-select-option value="男"> 男 </a-select-option>
                <a-select-option value="女"> 女 </a-select-option>
                <a-select-option value="未知"> 未知 </a-select-option>
              </a-select>
            </a-form-item>
          </a-col>
        </a-row>
      </a-card>

      <!-- 诊断信息 -->
      <a-card title="诊断信息" class="form-card">
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item label="出院科室" name="department">
              <a-select v-model:value="formData.department" placeholder="请选择出院科室">
                <a-select-option value="内科"> 内科 </a-select-option>
                <a-select-option value="外科"> 外科 </a-select-option>
                <a-select-option value="外一科"> 外一科 </a-select-option>
                <a-select-option value="外二科"> 外二科 </a-select-option>
                <a-select-option value="妇产科"> 妇产科 </a-select-option>
                <a-select-option value="儿科"> 儿科 </a-select-option>
                <a-select-option value="急诊科"> 急诊科 </a-select-option>
                <a-select-option value="骨科"> 骨科 </a-select-option>
                <a-select-option value="神经科"> 神经科 </a-select-option>
                <a-select-option value="心内科"> 心内科 </a-select-option>
                <a-select-option value="内科"> 内科 </a-select-option>
              </a-select>
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="状态" name="status">
              <a-select v-model:value="formData.status" placeholder="请选择状态">
                <a-select-option value="draft"> 草稿 </a-select-option>
                <a-select-option value="active"> 活跃 </a-select-option>
                <a-select-option value="archived"> 已归档 </a-select-option>
              </a-select>
            </a-form-item>
          </a-col>
        </a-row>

        <a-row :gutter="16">
          <a-col :span="24">
            <a-form-item label="主诊断" name="primaryDiagnosis">
              <a-input v-model:value="formData.primaryDiagnosis" placeholder="请输入主诊断" />
            </a-form-item>
          </a-col>
        </a-row>

        <a-row :gutter="16">
          <a-col :span="24">
            <a-form-item label="次要诊断" name="secondaryDiagnosis">
              <a-select
                v-model:value="formData.secondaryDiagnosis"
                mode="tags"
                placeholder="请输入次要诊断（可多个）"
                style="width: 100%"
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
              <a-button type="text" danger size="small" @click="removeDocument(index)">
                删除文书
              </a-button>
            </div>

            <a-row :gutter="16">
              <a-col :span="8">
                <a-form-item :name="['documents', index, 'type']" label="文书类型">
                  <a-select v-model:value="document.type" placeholder="请选择文书类型">
                    <!-- 标准六大类文书分类 -->
                    <a-select-optgroup label="入院记录">
                      <a-select-option value="admission_record"> 入院记录 </a-select-option>
                      <a-select-option value="admission_record_24h_in">
                        24小时内入院记录
                      </a-select-option>
                      <a-select-option value="admission_diagnosis"> 入院诊断 </a-select-option>
                    </a-select-optgroup>
                    <a-select-optgroup label="病程记录">
                      <a-select-option value="first_progress_note"> 首次病程记录 </a-select-option>
                      <a-select-option value="daily_progress_note"> 日常病程记录 </a-select-option>
                      <a-select-option value="attending_progress">
                        上级医师查房记录
                      </a-select-option>
                      <a-select-option value="consultation_record">
                        疑难病例讨论记录
                      </a-select-option>
                      <a-select-option value="handover_record"> 交接班记录 </a-select-option>
                      <a-select-option value="transfer_record"> 转科记录 </a-select-option>
                      <a-select-option value="stage_summary"> 阶段小结 </a-select-option>
                    </a-select-optgroup>
                    <a-select-optgroup label="出院记录">
                      <a-select-option value="discharge_record"> 出院记录 </a-select-option>
                      <a-select-option value="admission_record_24h_out">
                        24小时内出院记录
                      </a-select-option>
                      <a-select-option value="death_record"> 死亡记录 </a-select-option>
                      <a-select-option value="death_case_discussion">
                        死亡病例讨论
                      </a-select-option>
                    </a-select-optgroup>
                    <a-select-optgroup label="手术相关记录">
                      <a-select-option value="preoperative_summary"> 术前小结 </a-select-option>
                      <a-select-option value="preoperative_discussion"> 术前讨论 </a-select-option>
                      <a-select-option value="operation_record"> 手术记录 </a-select-option>
                      <a-select-option value="postoperative_first_note">
                        术后首次病程记录
                      </a-select-option>
                      <a-select-option value="anesthesia_record"> 麻醉记录 </a-select-option>
                    </a-select-optgroup>
                    <a-select-optgroup label="辅助检查">
                      <a-select-option value="imaging_report"> 影像检查报告 </a-select-option>
                      <a-select-option value="lab_report"> 检验报告 </a-select-option>
                      <a-select-option value="pathology_report"> 病理报告 </a-select-option>
                      <a-select-option value="other_examination"> 其他检查 </a-select-option>
                    </a-select-optgroup>
                    <a-select-optgroup label="知情同意书">
                      <a-select-option value="surgery_consent"> 手术同意书 </a-select-option>
                      <a-select-option value="anesthesia_consent"> 麻醉同意书 </a-select-option>
                      <a-select-option value="blood_transfusion_consent">
                        输血同意书
                      </a-select-option>
                      <a-select-option value="special_examination_consent">
                        特殊检查同意书
                      </a-select-option>
                      <a-select-option value="critical_illness_notice">
                        病危(重)通知书
                      </a-select-option>
                    </a-select-optgroup>
                  </a-select>
                </a-form-item>
              </a-col>
              <a-col :span="16">
                <a-form-item :name="['documents', index, 'title']" label="文书标题">
                  <a-input v-model:value="document.title" placeholder="请输入文书标题" />
                </a-form-item>
              </a-col>
            </a-row>

            <a-form-item :name="['documents', index, 'content']" label="文书内容">
              <a-textarea v-model:value="document.content" placeholder="请输入文书内容" :rows="6" />
            </a-form-item>
          </div>
        </div>
      </a-card>

      <!-- 修改历史 -->
      <a-card title="修改历史" class="form-card">
        <div class="history-list">
          <div v-for="(history, index) in modificationHistory" :key="index" class="history-item">
            <div class="history-time">
              {{ formatDateTime(history.timestamp) }}
            </div>
            <div class="history-user">
              {{ history.user }}
            </div>
            <div class="history-action">
              {{ history.action }}
            </div>
          </div>
        </div>
      </a-card>

      <!-- 操作按钮 -->
      <div class="form-actions">
        <div class="left-actions">
          <a-button type="dashed" @click="addDocument">
            <template #icon>
              <PlusOutlined />
            </template>
            新建文书
          </a-button>
        </div>

        <div class="right-actions">
          <a-space>
            <a-button @click="handleCancel"> 取消 </a-button>
            <a-button type="primary" html-type="submit" :loading="submitting"> 保存 </a-button>
          </a-space>
        </div>
      </div>
    </a-form>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { message } from 'ant-design-vue'
import { PlusOutlined } from '@ant-design/icons-vue'
import type { FormInstance, FormProps } from 'ant-design-vue'
import dayjs from 'dayjs'
import { getAccessToken } from '@/utils/auth-token'
import { resolveApiBaseUrl } from '@/utils/api-helpers'

interface EditableDocument {
  id?: string
  type?: string
  title?: string
  name?: string
  content?: string
}
interface EditableFormData {
  recordNumber: string
  recordName: string
  patientName: string
  patientAge: number | null
  patientGender: string
  department: string
  primaryDiagnosis: string
  secondaryDiagnosis: string[]
  majorSurgery: string
  status: 'draft' | 'active' | 'archived'
  documents: Array<{
    id: string
    type: string
    title: string
    content: string
  }>
}

interface RecordPayload {
  id?: string
  record_number?: string
  patient_name?: string
  patient_age?: number | null
  patient_gender?: string
  department?: string
  diagnosis_primary?: string
  primary_diagnosis?: string
  diagnosis_secondary?: string[]
  secondary_diagnosis?: string[]
  major_surgery?: string
  status?: 'draft' | 'active' | 'archived' | string
  content?: string
  documents?: EditableDocument[]
  content_sections?: {
    documents?: EditableDocument[]
  }
  updated_at?: string
}

const API_BASE_URL = resolveApiBaseUrl()
console.log('🌐 编辑页面使用API地址:', API_BASE_URL)

const router = useRouter()
const route = useRoute()
const formRef = ref<FormInstance>()
const loading = ref(true)
const submitting = ref(false)
const originalData = ref<RecordPayload | null>(null) // 用于并发编辑检测

// 表单数据
const formData = reactive<EditableFormData>({
  recordNumber: '',
  recordName: '',
  patientName: '',
  patientAge: null as number | null,
  patientGender: '',
  department: '',
  primaryDiagnosis: '',
  secondaryDiagnosis: [] as string[],
  majorSurgery: '',
  status: 'active' as 'draft' | 'active' | 'archived',
  documents: [] as Array<{
    id: string
    type: string
    title: string
    content: string
  }>,
})

// 修改历史
const modificationHistory = ref([
  {
    timestamp: '2024-08-27T10:30:00Z',
    user: '张医生',
    action: '创建病历',
  },
  {
    timestamp: '2024-08-27T14:20:00Z',
    user: '李医生',
    action: '修改主诊断信息',
  },
  {
    timestamp: '2024-08-27T16:45:00Z',
    user: '王医生',
    action: '添加出院记录',
  },
])

// 表单验证规则
const formRules = {
  recordName: [{ required: true, message: '请输入病历名称', trigger: 'blur' }],
  patientName: [{ required: true, message: '请输入患者姓名', trigger: 'blur' }],
  patientAge: [
    { required: true, message: '请输入患者年龄', trigger: 'blur' },
    { type: 'number', min: 0, max: 150, message: '年龄必须在0-150之间', trigger: 'blur' },
  ],
  patientGender: [{ required: true, message: '请选择患者性别', trigger: 'change' }],
  department: [{ required: true, message: '请选择出院科室', trigger: 'change' }],
  primaryDiagnosis: [{ required: true, message: '请输入主诊断', trigger: 'blur' }],
  status: [{ required: true, message: '请选择状态', trigger: 'change' }],
} satisfies NonNullable<FormProps['rules']>

// 生命周期
onMounted(async () => {
  await loadRecordData()
})

// 加载病历数据
const loadRecordData = async () => {
  try {
    loading.value = true
    const recordId = route.params.id as string

    console.log('正在加载病历数据，ID:', recordId)

    // 获取认证token
    const token = getAccessToken()
    if (!token) {
      message.error('请先登录')
      router.push('/login')
      return
    }

    // 调用后端统一的医疗记录详情接口
    const apiUrl = `${API_BASE_URL}/api/medical-records/${recordId}`
    console.log('📡 API调用URL:', apiUrl)

    const response = await fetch(apiUrl, {
      method: 'GET',
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
    })

    console.log(`📊 API响应状态: ${response.status} ${response.statusText}`)

    if (!response.ok) {
      const errorText = await response.text()
      console.error('❌ API调用失败:', errorText)
      throw new Error(`HTTP ${response.status}: ${response.statusText} - ${errorText}`)
    }

    const record = (await response.json()) as RecordPayload
    console.log('加载的病历数据:', record)

    // 转换数据格式以适配表单 - 适配medical_records表结构
    const formattedData: EditableFormData = {
      recordNumber: record.record_number || record.id || '',
      recordName: `${record.patient_name}的病历记录`,
      patientName: record.patient_name || '',
      patientAge: record.patient_age || null,
      patientGender: record.patient_gender || '',
      department: record.department || '未知科室',
      primaryDiagnosis: record.diagnosis_primary || record.primary_diagnosis || '',
      secondaryDiagnosis: record.diagnosis_secondary || record.secondary_diagnosis || [],
      majorSurgery: record.major_surgery || '',
      status: record.status === 'draft' || record.status === 'archived' ? record.status : 'active',
      documents: [],
    }

    // 处理文档数据 - 从content_sections或documents字段中提取
    if (record.content_sections?.documents && Array.isArray(record.content_sections.documents)) {
      formattedData.documents = record.content_sections.documents.map(
        (doc: EditableDocument, index: number) => ({
          id: doc.id || `doc_${index}`,
          type: doc.type || '病程记录',
          title: doc.title || doc.name || `文档${index + 1}`,
          content: doc.content || '',
        }),
      )
    } else if (record.documents && Array.isArray(record.documents)) {
      formattedData.documents = record.documents.map((doc: EditableDocument, index: number) => ({
        id: doc.id || `doc_${index}`,
        type: doc.type || '病程记录',
        title: doc.title || doc.name || `文档${index + 1}`,
        content: doc.content || '',
      }))
    } else if (record.content) {
      // 如果只有content字段，创建一个默认文档
      formattedData.documents = [
        {
          id: 'main_content',
          type: '病历内容',
          title: '主要内容',
          content: record.content,
        },
      ]
    }

    console.log('转换后的表单数据:', formattedData)
    console.log('文书数量:', formattedData.documents.length)

    Object.assign(formData, formattedData)

    // 保存原始数据用于并发编辑检测
    originalData.value = JSON.parse(JSON.stringify(record))

    message.success(`成功加载病历数据，包含 ${formattedData.documents.length} 个文书`)
  } catch (error) {
    console.error('加载病历数据失败:', error)
    message.error('加载病历数据失败，请检查病历ID是否正确')

    // 如果加载失败，返回列表页面
    setTimeout(() => {
      router.push('/dashboard/medical-records')
    }, 2000)
  } finally {
    loading.value = false
  }
}

// 格式化时间
const formatDateTime = (dateString: string) => {
  return dayjs(dateString).format('YYYY-MM-DD HH:mm:ss')
}

// 添加文书
const addDocument = () => {
  const newDocument = {
    id: `doc_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
    type: '入院记录',
    title: '',
    content: '',
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
    // 表单验证
    await formRef.value?.validate()

    submitting.value = true
    const recordId = route.params.id as string

    console.log('正在保存病历数据:', formData)

    // 并发编辑检测 - 使用后端API
    if (originalData.value) {
      try {
        const token = getAccessToken()
        if (token) {
          const checkResponse = await fetch(`${API_BASE_URL}/api/medical-records/${recordId}`, {
            method: 'GET',
            headers: {
              Authorization: `Bearer ${token}`,
              'Content-Type': 'application/json',
            },
          })

          if (checkResponse.ok) {
            const currentRecord = (await checkResponse.json()) as RecordPayload
            if (currentRecord.updated_at !== originalData.value.updated_at) {
              const confirmed = window.confirm(
                '检测到此病历已被其他用户修改。\n\n' +
                  '继续保存将覆盖其他用户的修改。\n\n' +
                  '是否继续保存？',
              )
              if (!confirmed) {
                submitting.value = false
                return
              }
            }
          }
        }
      } catch (error) {
        console.warn('并发编辑检测失败:', error)
      }
    }

    // 准备文书数据
    const documents = formData.documents.map((doc, index) => ({
      id: doc.id,
      type: doc.type,
      title: doc.title,
      content: doc.content,
      ai_classified: false, // 手动编辑的文书
      ai_confidence: 0,
      sort_order: index,
    }))

    // 准备更新数据 - 适配medical_records表结构
    const updateData = {
      patient_name: formData.patientName,
      patient_age: formData.patientAge,
      patient_gender: formData.patientGender,
      department: formData.department,
      diagnosis_primary: formData.primaryDiagnosis,
      diagnosis_secondary: formData.secondaryDiagnosis,
      major_surgery: formData.majorSurgery,
      status: formData.status,
      content_sections: {
        documents: documents,
      },
    }

    // 获取认证token
    const token = getAccessToken()
    if (!token) {
      message.error('请先登录')
      router.push('/login')
      return
    }

    // 调用后端更新接口
    const updateResponse = await fetch(`${API_BASE_URL}/api/medical-records/${recordId}`, {
      method: 'PUT',
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(updateData),
    })

    console.log(`📊 更新API响应状态: ${updateResponse.status} ${updateResponse.statusText}`)

    if (!updateResponse.ok) {
      const errorText = await updateResponse.text()
      console.error('❌ 更新API调用失败:', errorText)
      throw new Error(`HTTP ${updateResponse.status}: ${updateResponse.statusText} - ${errorText}`)
    }

    const updatedRecord = await updateResponse.json()

    console.log('病历保存成功，包含', documents.length, '个文书')
    message.success(`病历保存成功，包含 ${documents.length} 个文书`)

    // 延迟跳转，让用户看到成功消息
    setTimeout(() => {
      router.push('/dashboard/medical-records')
    }, 1500)
  } catch (error: unknown) {
    console.error('保存失败:', error)
    const errorMessage = error instanceof Error ? error.message : ''

    // 根据错误类型显示不同的错误消息
    if (errorMessage.includes('validation')) {
      message.error('数据验证失败，请检查输入内容')
    } else if (errorMessage.includes('network')) {
      message.error('网络连接失败，请检查网络后重试')
    } else if (errorMessage.includes('permission')) {
      message.error('权限不足，无法保存病历')
    } else {
      message.error(errorMessage || '保存失败，请重试')
    }
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
/* 继承创建页面的样式，并添加编辑页面特有样式 */
.page-container {
  @apply p-3;
}

.breadcrumb {
  @apply mb-3;
}

.page-header {
  @apply flex items-center justify-between mb-3;
}

.page-title {
  @apply text-lg font-bold text-gray-900;
  font-size: 16px;
}

.record-info {
  @apply flex items-center;
}

.record-number {
  @apply text-sm text-gray-600 bg-gray-100 px-2 py-1 rounded font-mono;
}

/* 加载状态 */
.loading-container {
  @apply flex items-center justify-center py-20;
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

/* 修改历史样式 */
.history-list {
  @apply space-y-3;
}

.history-item {
  @apply flex items-center gap-4 p-3 bg-gray-50 rounded border-l-4 border-blue-400;
}

.history-time {
  @apply text-xs text-gray-500 font-mono;
}

.history-user {
  @apply text-sm font-medium text-gray-700;
}

.history-action {
  @apply text-sm text-gray-600;
}

/* 其他样式继承创建页面 */
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

.form-actions {
  @apply flex items-center justify-between mt-6 pt-4 border-t border-gray-200;
}

.left-actions {
  @apply flex items-center;
}

.right-actions {
  @apply flex items-center;
}

:deep(.ant-btn) {
  font-size: 12px !important;
  height: 28px !important;
  padding: 3px 12px !important;
}

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

:deep(.ant-empty-description) {
  font-size: 12px !important;
  color: #999 !important;
}

:deep(.ant-input) {
  font-size: 12px !important;
  line-height: 1.4 !important;
}

:deep(.ant-form-item-explain-error) {
  font-size: 11px !important;
}

:deep(.ant-spin-text) {
  font-size: 12px !important;
}
</style>
