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
      size="small"
      @finish="handleSubmit"
    >
      <!-- 病历基本信息（字段与后端 POST /api/medical-records 一致） -->
      <a-card title="病历基本信息" class="form-card">
        <a-row :gutter="8">
          <a-col :span="12">
            <a-form-item label="病历编号" name="record_number">
              <a-input 
                v-model:value="formData.record_number" 
                placeholder="自动生成"
                disabled
              />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="患者姓名" name="patient_name">
              <a-input 
                v-model:value="formData.patient_name" 
                placeholder="请输入患者姓名"
              />
            </a-form-item>
          </a-col>
        </a-row>

        <a-row :gutter="8">
          <a-col :span="12">
            <a-form-item label="年龄" name="patient_age">
              <a-input 
                v-model:value="formData.patient_age" 
                placeholder="请输入年龄"
                type="number"
              />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="性别" name="patient_gender">
              <a-select v-model:value="formData.patient_gender" placeholder="请选择性别">
                <a-select-option value="男">男</a-select-option>
                <a-select-option value="女">女</a-select-option>
                <a-select-option value="未知">未知</a-select-option>
              </a-select>
            </a-form-item>
          </a-col>
        </a-row>

        <a-row :gutter="8">
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
            <a-form-item label="主诊断" name="primary_diagnosis">
              <a-input 
                v-model:value="formData.primary_diagnosis" 
                placeholder="请输入主诊断"
              />
            </a-form-item>
          </a-col>
        </a-row>

        <a-row :gutter="8">
          <a-col :span="24">
            <a-form-item label="主要手术及操作" name="major_surgery">
              <a-textarea 
                v-model:value="formData.major_surgery" 
                placeholder="请输入主要手术及操作（可选）"
                :rows="2"
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
              <h4>文书{{ index + 1 }}</h4>
              <a-button 
                type="text" 
                danger 
                size="small"
                @click="removeDocument(index)"
              >
                删除文书
              </a-button>
            </div>
            
            <a-form-item :name="['documents', index, 'type']" label="文书类型">
              <a-select 
                v-model:value="document.type"
                show-search
                :filter-option="filterDocType"
                placeholder="请选择文书类型"
              >
                <a-select-opt-group label="入出院">
                  <a-select-option value="admission_record">入院记录</a-select-option>
                  <a-select-option value="admission_record_24h_in">24小时内入院记录</a-select-option>
                  <a-select-option value="admission_record_24h_out">24小时内出院记录</a-select-option>
                  <a-select-option value="discharge_record">出院记录</a-select-option>
                  <a-select-option value="death_record">死亡记录</a-select-option>
                  <a-select-option value="death_case_discussion">死亡病例讨论</a-select-option>
                </a-select-opt-group>
                <a-select-opt-group label="病程">
                  <a-select-option value="first_progress_note">首次病程记录</a-select-option>
                  <a-select-option value="daily_progress_note">日常病程记录</a-select-option>
                  <a-select-option value="attending_first_progress">主治首次病程</a-select-option>
                  <a-select-option value="attending_progress">主治查房记录</a-select-option>
                  <a-select-option value="consultation_record">会诊记录</a-select-option>
                  <a-select-option value="handover_record">交接班记录</a-select-option>
                  <a-select-option value="stage_summary">阶段小结</a-select-option>
                </a-select-opt-group>
                <a-select-opt-group label="手术">
                  <a-select-option value="operation_record">手术记录</a-select-option>
                  <a-select-option value="preoperative_summary">术前小结</a-select-option>
                </a-select-opt-group>
                <a-select-opt-group label="检查化验">
                  <a-select-option value="imaging_report">影像检查报告</a-select-option>
                  <a-select-option value="lab_report">检验报告</a-select-option>
                  <a-select-option value="other_examination">其他检查</a-select-option>
                </a-select-opt-group>
                <a-select-opt-group label="同意书">
                  <a-select-option value="surgery_consent">手术同意书</a-select-option>
                  <a-select-option value="anesthesia_consent">麻醉同意书</a-select-option>
                  <a-select-option value="blood_transfusion_consent">输血同意书</a-select-option>
                  <a-select-option value="special_treatment_consent">特殊治疗同意书</a-select-option>
                  <a-select-option value="critical_illness_notice">病危(重)通知书</a-select-option>
                </a-select-opt-group>
              </a-select>
            </a-form-item>
            
            <a-form-item :name="['documents', index, 'content']" label="文书内容">
              <a-textarea 
                v-model:value="document.content" 
                placeholder="请输入文书内容"
                :rows="4"
                :auto-size="{ minRows: 4, maxRows: 20 }"
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
            @click="showDocumentSelector"
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
    
    <!-- 文书选择器弹窗 -->
    <a-modal
      v-model:visible="documentSelectorVisible"
      title="选择文书类型"
      width="600px"
      :footer="null"
      @cancel="documentSelectorVisible = false"
    >
      <div class="document-selector">
        <div class="selector-header">
          <a-input-search 
            v-model:value="searchKeyword"
            placeholder="搜索文书类型..."
            allow-clear
            @search="onSearch"
          />
        </div>
        
        <div class="selector-body">
          <a-tree
            v-model:expandedKeys="expandedKeys"
            v-model:selectedKeys="selectedKeys"
            :tree-data="filteredTreeData"
            :field-names="{ title: 'label', key: 'key', children: 'children' }"
            :selectable="true"
            @select="onSelectDocument"
          >
            <template #title="{ label, isLeaf, description }">
              <div class="tree-node-content">
                <span v-if="!isLeaf" class="folder-icon">
                  <FolderOutlined />
                </span>
                <span v-else class="file-icon">
                  <FileTextOutlined />
                </span>
                <span class="node-label">{{ label }}</span>
                <span v-if="description" class="node-description">{{ description }}</span>
              </div>
            </template>
          </a-tree>
        </div>
        
        <div class="selector-footer">
          <div class="selected-info" v-if="selectedDocument">
            已选择：<strong>{{ selectedDocument.label }}</strong>
          </div>
          <a-space>
            <a-button @click="documentSelectorVisible = false">取消</a-button>
            <a-button 
              type="primary" 
              :disabled="!selectedDocument"
              @click="confirmAddDocument"
            >
              添加文书
            </a-button>
          </a-space>
        </div>
      </div>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { PlusOutlined, FolderOutlined, FileTextOutlined } from '@ant-design/icons-vue'
import type { FormInstance } from 'ant-design-vue'

const router = useRouter()
const formRef = ref<FormInstance>()
const submitting = ref(false)

// 文书选择器状态
const documentSelectorVisible = ref(false)
const searchKeyword = ref('')
const expandedKeys = ref<string[]>(['admission', 'progress', 'surgery', 'examination', 'consent'])
const selectedKeys = ref<string[]>([])
const selectedDocument = ref<unknown>(null)

// 与后端保持一致的文书类型（完整枚举）
const DOCUMENT_TYPES = [
  { code: 'admission_record', label: '入院记录', group: '入出院' },
  { code: 'admission_record_24h_in', label: '24小时内入院记录', group: '入出院' },
  { code: 'admission_record_24h_out', label: '24小时内出院记录', group: '入出院' },
  { code: 'first_progress_note', label: '首次病程记录', group: '病程' },
  { code: 'daily_progress_note', label: '日常病程记录', group: '病程' },
  { code: 'attending_first_progress', label: '主治首次病程', group: '病程' },
  { code: 'attending_progress', label: '主治查房记录', group: '病程' },
  { code: 'consultation_record', label: '会诊记录', group: '病程' },
  { code: 'handover_record', label: '交接班记录', group: '病程' },
  { code: 'stage_summary', label: '阶段小结', group: '病程' },
  { code: 'operation_record', label: '手术记录', group: '手术' },
  { code: 'preoperative_summary', label: '术前小结', group: '手术' },
  { code: 'discharge_record', label: '出院记录', group: '入出院' },
  { code: 'death_record', label: '死亡记录', group: '入出院' },
  { code: 'death_case_discussion', label: '死亡病例讨论', group: '入出院' },
  { code: 'imaging_report', label: '影像检查报告', group: '检查化验' },
  { code: 'lab_report', label: '检验报告', group: '检查化验' },
  { code: 'other_examination', label: '其他检查', group: '检查化验' },
  { code: 'surgery_consent', label: '手术同意书', group: '同意书' },
  { code: 'anesthesia_consent', label: '麻醉同意书', group: '同意书' },
  { code: 'blood_transfusion_consent', label: '输血同意书', group: '同意书' },
  { code: 'special_treatment_consent', label: '特殊治疗同意书', group: '同意书' },
  { code: 'critical_illness_notice', label: '病危(重)通知书', group: '同意书' }
]

// 构建树形数据结构 - 按照标准六大类文书分类
const documentTreeData = [
  {
    key: 'admission_record',
    label: '入院记录',
    isLeaf: false,
    children: [
      { key: 'admission_record_basic', label: '入院记录', code: 'admission_record', isLeaf: true, description: '患者入院时的基本情况记录' },
      { key: 'admission_record_24h_in', label: '24小时内入院记录', code: 'admission_record_24h_in', isLeaf: true, description: '入院24小时内完成' },
      { key: 'admission_diagnosis', label: '入院诊断', code: 'admission_diagnosis', isLeaf: true, description: '入院时的初步诊断' }
    ]
  },
  {
    key: 'progress_note',
    label: '病程记录',
    isLeaf: false,
    children: [
      { key: 'first_progress_note', label: '首次病程记录', code: 'first_progress_note', isLeaf: true, description: '入院后第一次病程' },
      { key: 'daily_progress_note', label: '日常病程记录', code: 'daily_progress_note', isLeaf: true, description: '每日病情变化记录' },
      { key: 'attending_progress', label: '上级医师查房记录', code: 'attending_progress', isLeaf: true, description: '上级医师查房记录' },
      { key: 'consultation_record', label: '疑难病例讨论记录', code: 'consultation_record', isLeaf: true, description: '疑难病例讨论记录' },
      { key: 'handover_record', label: '交接班记录', code: 'handover_record', isLeaf: true, description: '医护人员交接班记录' },
      { key: 'transfer_record', label: '转科记录', code: 'transfer_record', isLeaf: true, description: '患者转科时的记录' },
      { key: 'stage_summary', label: '阶段小结', code: 'stage_summary', isLeaf: true, description: '治疗阶段性总结' }
    ]
  },
  {
    key: 'discharge_record',
    label: '出院记录',
    isLeaf: false,
    children: [
      { key: 'discharge_record_basic', label: '出院记录', code: 'discharge_record', isLeaf: true, description: '患者出院时的总结记录' },
      { key: 'admission_record_24h_out', label: '24小时内出院记录', code: 'admission_record_24h_out', isLeaf: true, description: '入院24小时内出院' },
      { key: 'death_record', label: '死亡记录', code: 'death_record', isLeaf: true, description: '患者死亡情况记录' },
      { key: 'death_case_discussion', label: '死亡病例讨论', code: 'death_case_discussion', isLeaf: true, description: '死亡病例的讨论记录' }
    ]
  },
  {
    key: 'operation_record',
    label: '手术相关记录',
    isLeaf: false,
    children: [
      { key: 'preoperative_summary', label: '术前小结', code: 'preoperative_summary', isLeaf: true, description: '手术前准备情况' },
      { key: 'preoperative_discussion', label: '术前讨论', code: 'preoperative_discussion', isLeaf: true, description: '术前讨论记录' },
      { key: 'operation_record_basic', label: '手术记录', code: 'operation_record', isLeaf: true, description: '手术过程详细记录' },
      { key: 'postoperative_first_note', label: '术后首次病程记录', code: 'postoperative_first_note', isLeaf: true, description: '术后首次病程记录' },
      { key: 'anesthesia_record', label: '麻醉记录', code: 'anesthesia_record', isLeaf: true, description: '麻醉过程记录' }
    ]
  },
  {
    key: 'examination_report',
    label: '辅助检查',
    isLeaf: false,
    children: [
      { key: 'imaging_report', label: '影像检查报告', code: 'imaging_report', isLeaf: true, description: 'CT、MRI、X光等影像报告' },
      { key: 'lab_report', label: '检验报告', code: 'lab_report', isLeaf: true, description: '血液、尿液等化验报告' },
      { key: 'pathology_report', label: '病理报告', code: 'pathology_report', isLeaf: true, description: '病理检查报告' },
      { key: 'other_examination', label: '其他检查', code: 'other_examination', isLeaf: true, description: '其他特殊检查报告' }
    ]
  },
  {
    key: 'consent_form',
    label: '知情同意书',
    isLeaf: false,
    children: [
      { key: 'surgery_consent', label: '手术同意书', code: 'surgery_consent', isLeaf: true, description: '手术知情同意' },
      { key: 'anesthesia_consent', label: '麻醉同意书', code: 'anesthesia_consent', isLeaf: true, description: '麻醉知情同意' },
      { key: 'blood_transfusion_consent', label: '输血同意书', code: 'blood_transfusion_consent', isLeaf: true, description: '输血治疗同意' },
      { key: 'special_examination_consent', label: '特殊检查同意书', code: 'special_examination_consent', isLeaf: true, description: '特殊检查同意' },
      { key: 'critical_illness_notice', label: '病危(重)通知书', code: 'critical_illness_notice', isLeaf: true, description: '病情危重告知' }
    ]
  }
]

const getTypeLabel = (code: string) => {
  const t = DOCUMENT_TYPES.find(t => t.code === code)
  return t ? t.label : code
}

const filterDocType = (input: string, option: unknown) => {
  const text = (option?.children as string) || ''
  return text.toLowerCase().includes((input || '').toLowerCase())
}

// 表单数据
const formData = reactive({
  record_number: '',
  patient_name: '',
  patient_age: undefined as unknown as number,
  patient_gender: '未知',
  department: '',
  primary_diagnosis: '',
  major_surgery: '',
  documents: [] as Array<{
    id: string
    type: string
    content: string
  }>
})

// 表单验证规则
const formRules = {
  patient_name: [
    { required: true, message: '请输入患者姓名', trigger: 'blur' }
  ],
  department: [
    { required: true, message: '请选择出院科室', trigger: 'change' }
  ],
  primary_diagnosis: [
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
  formData.record_number = `MR${year}${month}${day}${random}`
}

// 显示文书选择器
const showDocumentSelector = () => {
  documentSelectorVisible.value = true
  selectedKeys.value = []
  selectedDocument.value = null
  searchKeyword.value = ''
}

// 搜索过滤树形数据
const filteredTreeData = computed(() => {
  if (!searchKeyword.value) {
    return documentTreeData
  }
  
  const keyword = searchKeyword.value.toLowerCase()
  const filterTree = (nodes: unknown[]): unknown[] => {
    return nodes.reduce((acc, node) => {
      if (node.children) {
        const filteredChildren = filterTree(node.children)
        if (filteredChildren.length > 0) {
          acc.push({
            ...node,
            children: filteredChildren
          })
        }
      } else if (node.label.toLowerCase().includes(keyword) || 
                 (node.description && node.description.toLowerCase().includes(keyword))) {
        acc.push(node)
      }
      return acc
    }, [])
  }
  
  return filterTree(documentTreeData)
})

// 搜索处理
const onSearch = () => {
  // 搜索时自动展开所有节点
  if (searchKeyword.value) {
    expandedKeys.value = ['admission', 'progress', 'surgery', 'examination', 'consent']
  }
}

// 选择文书类型
const onSelectDocument = (keys: string[], info: unknown) => {
  if (info.node.isLeaf) {
    selectedKeys.value = keys
    selectedDocument.value = info.node
  }
}

// 确认添加文书
const confirmAddDocument = () => {
  if (!selectedDocument.value) {
    message.warning('请选择文书类型')
    return
  }
  
  const newDocument = {
    id: `doc_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
    type: selectedDocument.value.code,
    content: ''
  }
  formData.documents.push(newDocument)
  
  documentSelectorVisible.value = false
  message.success(`已添加文书：${selectedDocument.value.label}`)
}

// 添加文书（兼容旧方法）
const addDocument = () => {
  showDocumentSelector()
}

// 删除文书
const removeDocument = (index: number) => {
  formData.documents.splice(index, 1)
}

// 提交表单
const handleSubmit = async () => {
  try {
    submitting.value = true
    
    // 直接调用后端现有接口：POST /api/medical-records
    const response = await fetch('/api/medical-records', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        record_number: formData.record_number,
        patient_name: formData.patient_name,
        patient_age: Number(formData.patient_age || 0),
        patient_gender: formData.patient_gender || '未知',
        department: formData.department,
        primary_diagnosis: formData.primary_diagnosis,
        secondary_diagnosis: [],
        major_surgery: formData.major_surgery,
        content: '',
        documents: formData.documents.map(d => ({
          type: d.type,
          content: d.content
        })),
        confidence: 0,
        method: 'manual_entry'
      })
    })

    if (!response.ok) {
      const err = await response.text()
      throw new Error(err || '创建失败')
    }

    message.success('病历创建成功')
    router.push('/dashboard/medical-records')
  } catch (error) {
    message.error(error instanceof Error ? error.message : '创建失败，请重试')
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

::deep(.form-card .ant-card-body) {
  padding: 12px !important;
}

::deep(.form-card .ant-card-head) {
  padding: 0 16px !important;
  min-height: 36px !important;
}

::deep(.form-card .ant-card-head-title) {
  font-size: 14px !important;
  font-weight: 600 !important;
  padding: 4px 0 !important;
}

/* 表单项优化 */
::deep(.ant-form-item-label > label) {
  font-size: 12px !important;
  font-weight: 500 !important;
}

::deep(.ant-form-vertical .ant-form-item) {
  margin-bottom: 12px !important;
}

::deep(.ant-input) {
  font-size: 12px !important;
  height: 32px !important;
  padding: 3px 8px !important;
  border-radius: 6px !important;
}

::deep(.ant-input-disabled) {
  background-color: #f5f5f5 !important;
  color: #999 !important;
}

::deep(.ant-select) {
  font-size: 12px !important;
}

::deep(.ant-select-selector) {
  font-size: 12px !important;
  height: 32px !important;
  padding: 0 8px !important;
  border-radius: 6px !important;
}

::deep(.ant-select-selection-item) {
  font-size: 12px !important;
  line-height: 30px !important;
}

::deep(.ant-select-selection-placeholder) {
  font-size: 12px !important;
  line-height: 30px !important;
}

::deep(textarea.ant-input) {
  border-radius: 6px !important;
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
  padding: 10px !important;
}

.document-header {
  @apply flex items-center justify-between mb-3;
  margin-bottom: 8px !important;
}

.document-header h4 {
  @apply text-sm font-semibold text-gray-900 m-0;
}

/* 操作按钮区域 */
.form-actions {
  @apply flex items-center justify-between mt-6 pt-4 border-t border-gray-200;
  margin-top: 16px !important;
  padding-top: 8px !important;
}

.left-actions {
  @apply flex items-center;
}

.right-actions {
  @apply flex items-center;
}

/* 按钮样式优化 */
::deep(.ant-btn) {
  font-size: 12px !important;
  height: 28px !important;
  padding: 3px 12px !important;
}

::deep(.ant-btn-dashed) {
  border-style: dashed !important;
}

/* 面包屑样式 */
::deep(.ant-breadcrumb) {
  font-size: 12px !important;
}

::deep(.ant-breadcrumb a) {
  color: #1890ff !important;
  text-decoration: none !important;
}

::deep(.ant-breadcrumb a:hover) {
  color: #40a9ff !important;
}

/* 空状态样式 */
::deep(.ant-empty-description) {
  font-size: 12px !important;
  color: #999 !important;
}

/* 文本域样式 */
::deep(.ant-input) {
  font-size: 12px !important;
  line-height: 1.4 !important;
}

/* 表单验证错误样式 */
::deep(.ant-form-item-explain-error) {
  font-size: 11px !important;
}

/* 兼容写法：使用 :deep 保证作用域样式生效 */
:deep(.form-card .ant-card-body){ padding: 12px !important; }
:deep(.form-card .ant-card-head){ padding: 0 16px !important; min-height: 36px !important; }
:deep(.form-card .ant-card-head-title){ font-size: 14px !important; font-weight: 600 !important; padding: 4px 0 !important; }
:deep(.ant-form-vertical .ant-form-item){ margin-bottom: 12px !important; }
:deep(.ant-input){ font-size: 12px !important; height: 32px !important; padding: 3px 8px !important; border-radius: 6px !important; }
:deep(.ant-input-disabled){ background-color: #f5f5f5 !important; color: #999 !important; }
:deep(.ant-select-selector){ font-size: 12px !important; height: 32px !important; padding: 0 8px !important; border-radius: 6px !important; }
:deep(.ant-select-selection-item){ font-size: 12px !important; line-height: 30px !important; }
:deep(.ant-select-selection-placeholder){ font-size: 12px !important; line-height: 30px !important; }
:deep(textarea.ant-input){ border-radius: 6px !important; }

/* 统一输入类控件尺寸与圆角（更高优先级，覆盖 small 尺寸） */
:deep(.ant-input-affix-wrapper) {
  height: 32px !important;
  border-radius: 6px !important;
}
:deep(.ant-input-affix-wrapper .ant-input) {
  height: 30px !important;
  line-height: 30px !important;
}
:deep(input.ant-input[disabled]) {
  border-radius: 6px !important;
}
:deep(.ant-select-single .ant-select-selector) {
  height: 32px !important;
  border-radius: 6px !important;
}
:deep(.ant-select-single .ant-select-selector .ant-select-selection-item),
:deep(.ant-select-single .ant-select-selector .ant-select-selection-placeholder) {
  line-height: 30px !important;
}
:deep(.ant-select-single .ant-select-selector .ant-select-selection-search-input) {
  height: 30px !important;
}

/* 文书选择器样式 */
.document-selector {
  display: flex;
  flex-direction: column;
  height: 500px;
}

.selector-header {
  margin-bottom: 16px;
}

.selector-body {
  flex: 1;
  overflow-y: auto;
  border: 1px solid #f0f0f0;
  border-radius: 6px;
  padding: 8px;
  background: #fafafa;
}

.selector-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid #f0f0f0;
}

.selected-info {
  color: #52c41a;
  font-size: 14px;
}

.selected-info strong {
  color: #333;
  margin-left: 4px;
}

/* 树形节点样式 */
.tree-node-content {
  display: flex;
  align-items: center;
  padding: 2px 0;
}

.folder-icon,
.file-icon {
  margin-right: 6px;
  font-size: 14px;
}

.folder-icon {
  color: #faad14;
}

.file-icon {
  color: #1890ff;
}

.node-label {
  font-size: 14px;
  color: #333;
  margin-right: 8px;
}

.node-description {
  font-size: 12px;
  color: #999;
  margin-left: auto;
}

/* 树形组件样式调整 */
:deep(.ant-tree) {
  background: transparent;
  font-size: 14px;
}

:deep(.ant-tree-node-content-wrapper) {
  padding: 4px 8px !important;
  border-radius: 4px;
  transition: all 0.2s;
}

:deep(.ant-tree-node-content-wrapper:hover) {
  background-color: #f5f5f5;
}

:deep(.ant-tree-node-content-wrapper.ant-tree-node-selected) {
  background-color: #e6f7ff !important;
  border: 1px solid #1890ff;
}

:deep(.ant-tree-treenode) {
  padding: 2px 0;
}

:deep(.ant-tree-switcher) {
  color: #999;
}

/* 搜索框样式 */
:deep(.ant-input-search) {
  border-radius: 6px;
}

:deep(.ant-input-search .ant-input) {
  border-radius: 6px 0 0 6px;
}

:deep(.ant-input-search .ant-input-search-button) {
  border-radius: 0 6px 6px 0;
}

/* Modal 样式调整 */
:deep(.ant-modal-header) {
  border-bottom: 1px solid #f0f0f0;
}

:deep(.ant-modal-title) {
  font-size: 16px;
  font-weight: 600;
}

:deep(.ant-modal-body) {
  padding: 20px;
}
</style>
