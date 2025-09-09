<template>
  <div class="rule-import-page p-6">
    <div class="max-w-6xl mx-auto">
      <!-- 页面标题 -->
      <div class="mb-6">
        <h1 class="text-2xl font-bold text-gray-900 mb-2">医保规则导入</h1>
        <p class="text-gray-600">批量导入医保质控规则，支持JSON格式文件</p>
      </div>

      <!-- 导入步骤 -->
      <a-steps :current="currentStep" class="mb-8">
        <a-step title="选择文件" description="上传规则文件" />
        <a-step title="验证规则" description="检查规则格式" />
        <a-step title="预览确认" description="确认导入内容" />
        <a-step title="导入完成" description="规则导入成功" />
      </a-steps>

      <!-- 步骤内容 -->
      <div class="bg-white rounded-lg shadow-sm border p-6">
        <!-- 步骤1: 文件上传 -->
        <div v-if="currentStep === 0" class="step-content">
          <h3 class="text-lg font-semibold mb-4">选择规则文件</h3>
          
          <a-upload-dragger
            v-model:fileList="fileList"
            :before-upload="beforeUpload"
            :remove="handleRemove"
            accept=".json"
            :multiple="false"
            class="mb-4"
          >
            <p class="ant-upload-drag-icon">
              <InboxOutlined />
            </p>
            <p class="ant-upload-text">点击或拖拽文件到此区域上传</p>
            <p class="ant-upload-hint">
              支持JSON格式的规则文件，单次上传一个文件
            </p>
          </a-upload-dragger>

          <div class="flex justify-between">
            <a-button @click="downloadTemplate">
              <DownloadOutlined />
              下载模板文件
            </a-button>
            <a-button 
              type="primary" 
              :disabled="!selectedFile"
              @click="nextStep"
            >
              下一步
            </a-button>
          </div>
        </div>

        <!-- 步骤2: 规则验证 -->
        <div v-if="currentStep === 1" class="step-content">
          <h3 class="text-lg font-semibold mb-4">规则验证</h3>
          
          <div v-if="validating" class="text-center py-8">
            <a-spin size="large" />
            <p class="mt-4 text-gray-600">正在验证规则格式...</p>
          </div>

          <div v-else-if="validationResult">
            <a-result
              :status="validationResult.valid ? 'success' : 'error'"
              :title="validationResult.valid ? '规则验证通过' : '规则验证失败'"
              :sub-title="`共检查 ${validationResult.rule_count} 条规则`"
            >
              <template #extra>
                <div class="text-left">
                  <!-- 错误信息 -->
                  <div v-if="validationResult.errors.length > 0" class="mb-4">
                    <h4 class="text-red-600 font-semibold mb-2">错误信息:</h4>
                    <a-alert
                      v-for="(error, index) in validationResult.errors"
                      :key="index"
                      :message="error"
                      type="error"
                      class="mb-2"
                    />
                  </div>

                  <!-- 警告信息 -->
                  <div v-if="validationResult.warnings.length > 0" class="mb-4">
                    <h4 class="text-orange-600 font-semibold mb-2">警告信息:</h4>
                    <a-alert
                      v-for="(warning, index) in validationResult.warnings"
                      :key="index"
                      :message="warning"
                      type="warning"
                      class="mb-2"
                    />
                  </div>
                </div>
              </template>
            </a-result>

            <div class="flex justify-between mt-6">
              <a-button @click="prevStep">上一步</a-button>
              <a-button 
                type="primary" 
                :disabled="!validationResult.valid"
                @click="nextStep"
              >
                下一步
              </a-button>
            </div>
          </div>
        </div>

        <!-- 步骤3: 预览确认 -->
        <div v-if="currentStep === 2" class="step-content">
          <h3 class="text-lg font-semibold mb-4">预览规则内容</h3>
          
          <div class="mb-4">
            <a-descriptions bordered size="small">
              <a-descriptions-item label="批次名称">
                <a-input v-model:value="importConfig.batch_name" placeholder="请输入批次名称" />
              </a-descriptions-item>
              <a-descriptions-item label="批次描述">
                <a-textarea v-model:value="importConfig.batch_description" placeholder="请输入批次描述" />
              </a-descriptions-item>
              <a-descriptions-item label="导入模式">
                <a-select v-model:value="importConfig.import_mode" style="width: 120px">
                  <a-select-option value="append">追加</a-select-option>
                  <a-select-option value="replace">替换</a-select-option>
                  <a-select-option value="update">更新</a-select-option>
                </a-select>
              </a-descriptions-item>
            </a-descriptions>
          </div>

          <!-- 规则预览表格 -->
          <a-table
            :dataSource="previewRules"
            :columns="previewColumns"
            :pagination="{ pageSize: 5 }"
            size="small"
            class="mb-4"
          >
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'rule_type'">
                <a-tag :color="getRuleTypeColor(record.rule_type)">
                  {{ getRuleTypeName(record.rule_type) }}
                </a-tag>
              </template>
              <template v-if="column.key === 'severity'">
                <a-tag :color="getSeverityColor(record.severity)">
                  {{ getSeverityName(record.severity) }}
                </a-tag>
              </template>
              <template v-if="column.key === 'enabled'">
                <a-tag :color="record.enabled ? 'green' : 'red'">
                  {{ record.enabled ? '启用' : '禁用' }}
                </a-tag>
              </template>
            </template>
          </a-table>

          <div class="flex justify-between">
            <a-button @click="prevStep">上一步</a-button>
            <a-button 
              type="primary" 
              :loading="importing"
              @click="importRules"
            >
              确认导入
            </a-button>
          </div>
        </div>

        <!-- 步骤4: 导入完成 -->
        <div v-if="currentStep === 3" class="step-content">
          <a-result
            :status="importResult?.success ? 'success' : 'error'"
            :title="importResult?.success ? '规则导入成功' : '规则导入失败'"
            :sub-title="getImportResultMessage()"
          >
            <template #extra>
              <div class="space-x-4">
                <a-button type="primary" @click="goToRulesList">
                  查看规则列表
                </a-button>
                <a-button @click="resetImport">
                  重新导入
                </a-button>
              </div>
            </template>
          </a-result>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { InboxOutlined, DownloadOutlined } from '@ant-design/icons-vue'
import type { UploadFile } from 'ant-design-vue'
import { apiService } from '@/services/apiService'

const router = useRouter()

// 响应式数据
const currentStep = ref(0)
const fileList = ref<UploadFile[]>([])
const selectedFile = ref<File | null>(null)
const validating = ref(false)
const validationResult = ref<any>(null)
const importing = ref(false)
const importResult = ref<any>(null)
const rulesData = ref<any[]>([])

// 导入配置
const importConfig = ref({
  batch_name: '规则导入批次',
  batch_description: '',
  import_mode: 'append'
})

// 预览规则数据
const previewRules = computed(() => {
  return rulesData.value.slice(0, 10) // 只显示前10条
})

// 预览表格列定义
const previewColumns = [
  { title: '规则编码', dataIndex: 'code', key: 'code', width: 150 },
  { title: '规则名称', dataIndex: 'name', key: 'name', width: 200 },
  { title: '规则类型', dataIndex: 'rule_type', key: 'rule_type', width: 120 },
  { title: '严重级别', dataIndex: 'severity', key: 'severity', width: 100 },
  { title: '状态', dataIndex: 'enabled', key: 'enabled', width: 80 },
  { title: '描述', dataIndex: 'description', key: 'description', ellipsis: true }
]

// 文件上传前处理
const beforeUpload = (file: File) => {
  selectedFile.value = file
  return false // 阻止自动上传
}

// 移除文件
const handleRemove = () => {
  selectedFile.value = null
  return true
}

// 下载模板文件
const downloadTemplate = () => {
  // 创建模板数据
  const template = [
    {
      code: "TEMPLATE_001",
      name: "模板规则",
      description: "这是一个规则模板",
      rule_type: "drug_gender",
      severity: "warn",
      conditions: [
        {
          fact: "patient.gender",
          operator: "!=",
          value: "男",
          description: "患者性别检查"
        }
      ],
      actions: [
        {
          action_type: "warn",
          message_template: "请注意患者性别限制",
          parameters: {}
        }
      ],
      triggers: ["prescription_create"],
      enabled: true
    }
  ]
  
  // 下载JSON文件
  const blob = new Blob([JSON.stringify(template, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = 'rule_template.json'
  a.click()
  URL.revokeObjectURL(url)
}

// 下一步
const nextStep = async () => {
  if (currentStep.value === 0) {
    // 读取文件内容
    if (selectedFile.value) {
      try {
        const text = await selectedFile.value.text()
        rulesData.value = JSON.parse(text)
        currentStep.value = 1
        await validateRules()
      } catch (error) {
        message.error('文件格式错误，请检查JSON格式')
      }
    }
  } else if (currentStep.value === 1) {
    currentStep.value = 2
  } else if (currentStep.value === 2) {
    await importRules()
  }
}

// 上一步
const prevStep = () => {
  if (currentStep.value > 0) {
    currentStep.value--
  }
}

// 验证规则
const validateRules = async () => {
  validating.value = true
  try {
    const result = await apiService.post('/api/rules/validate', rulesData.value)
    validationResult.value = result
  } catch (error) {
    message.error('规则验证失败')
    console.error(error)
  } finally {
    validating.value = false
  }
}

// 导入规则
const importRules = async () => {
  importing.value = true
  try {
    const result = await apiService.post('/api/rules/import', {
      ...importConfig.value,
      rules: rulesData.value
    })
    importResult.value = result
    currentStep.value = 3
    
    if (result.success) {
      message.success(`成功导入 ${result.imported_count} 条规则`)
    } else {
      message.error('规则导入失败')
    }
  } catch (error) {
    message.error('规则导入失败')
    console.error(error)
  } finally {
    importing.value = false
  }
}

// 重置导入
const resetImport = () => {
  currentStep.value = 0
  fileList.value = []
  selectedFile.value = null
  validationResult.value = null
  importResult.value = null
  rulesData.value = []
}

// 跳转到规则列表
const goToRulesList = () => {
  router.push('/rules')
}

// 获取导入结果消息
const getImportResultMessage = () => {
  if (!importResult.value) return ''
  
  if (importResult.value.success) {
    return `成功导入 ${importResult.value.imported_count} 条规则`
  } else {
    return `导入失败，失败 ${importResult.value.failed_count} 条规则`
  }
}

// 工具函数
const getRuleTypeColor = (type: string) => {
  const colors: Record<string, string> = {
    'drug_gender': 'blue',
    'drug_age': 'green',
    'drug_children_only': 'orange',
    'drug_payment_course': 'purple'
  }
  return colors[type] || 'default'
}

const getRuleTypeName = (type: string) => {
  const names: Record<string, string> = {
    'drug_gender': '性别限制',
    'drug_age': '年龄限制',
    'drug_children_only': '儿童专用',
    'drug_payment_course': '支付疗程'
  }
  return names[type] || type
}

const getSeverityColor = (severity: string) => {
  const colors: Record<string, string> = {
    'info': 'blue',
    'warn': 'orange',
    'block': 'red'
  }
  return colors[severity] || 'default'
}

const getSeverityName = (severity: string) => {
  const names: Record<string, string> = {
    'info': '信息',
    'warn': '警告',
    'block': '拦截'
  }
  return names[severity] || severity
}
</script>

<style scoped>
.rule-import-page {
  min-height: calc(100vh - 64px);
  background-color: #f5f5f5;
}

.step-content {
  min-height: 400px;
}

.ant-upload-drag {
  background-color: #fafafa;
}

.ant-upload-drag:hover {
  border-color: #1890ff;
}
</style>
