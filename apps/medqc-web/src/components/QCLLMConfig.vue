<template>
  <div class="qc-llm-config">
    <a-card title="质控LLM配置" :bordered="false">
      <template #extra>
        <a-space>
          <a-button @click="refreshConfigs" :loading="loading">
            <template #icon><ReloadOutlined /></template>
            刷新
          </a-button>
        <a-button @click="showImportModal = true">
          <template #icon><ImportOutlined /></template>
          导入配置
        </a-button>
        <a-button @click="exportConfigs">
          <template #icon><ExportOutlined /></template>
          导出配置
        </a-button>
          <a-button type="primary" @click="showAddConfig">
            <template #icon><PlusOutlined /></template>
            添加配置
          </a-button>
        </a-space>
      </template>

      <!-- 配置列表 -->
      <a-table 
        :columns="columns" 
        :data-source="configs" 
        :loading="loading"
        row-key="config_id"
        :pagination="{ pageSize: 10 }"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'config_name'">
            <a-tag :color="getConfigTypeColor(record.config_name)">
              {{ getConfigTypeName(record.config_name) }}
            </a-tag>
          </template>
          
          <template v-if="column.key === 'provider'">
            <div>
              <div class="provider-name">{{ record.provider_name }}</div>
              <div class="model-name">{{ record.model_name }}</div>
            </div>
          </template>
          
          <template v-if="column.key === 'status'">
            <a-tag :color="record.is_active ? 'green' : 'red'">
              {{ record.is_active ? '启用' : '禁用' }}
            </a-tag>
          </template>
          
          <template v-if="column.key === 'actions'">
            <a-space>
              <a-button size="small" @click="testConfig(record)">
                测试
              </a-button>
              <a-button size="small" @click="editConfig(record)">
                编辑
              </a-button>
              <a-popconfirm
                title="确定要删除这个配置吗？"
                @confirm="deleteConfig(record)"
              >
                <a-button size="small" danger>
                  删除
                </a-button>
              </a-popconfirm>
            </a-space>
          </template>
        </template>
      </a-table>
    </a-card>

    <!-- 配置编辑弹窗 -->
    <a-modal
      v-model:open="configModalVisible"
      :title="editingConfig ? '编辑配置' : '添加配置'"
      width="600px"
      @ok="saveConfig"
      @cancel="cancelEdit"
    >
      <a-form
        ref="configForm"
        :model="configFormData"
        :rules="configFormRules"
        layout="vertical"
      >
        <a-form-item label="配置名称" name="config_name">
          <a-select v-model:value="configFormData.config_name" placeholder="选择配置类型">
            <a-select-option value="qc_analysis">质控分析</a-select-option>
            <a-select-option value="extraction">文档提取</a-select-option>
            <a-select-option value="default">默认配置</a-select-option>
          </a-select>
        </a-form-item>

        <a-form-item label="LLM提供商" name="provider_id">
          <a-select 
            v-model:value="configFormData.provider_id" 
            placeholder="选择LLM提供商"
            @change="onProviderChange"
          >
            <a-select-option 
              v-for="provider in providers" 
              :key="provider.id" 
              :value="provider.id"
            >
              {{ provider.provider_name }}
            </a-select-option>
          </a-select>
        </a-form-item>

        <a-form-item label="模型" name="model_id">
          <a-select v-model:value="configFormData.model_id" placeholder="选择模型">
            <a-select-option 
              v-for="model in availableModels" 
              :key="model.id" 
              :value="model.id"
            >
              <div>
                <div>{{ model.model_name }}</div>
                <div style="font-size: 12px; color: #666;">{{ model.description }}</div>
              </div>
            </a-select-option>
          </a-select>
        </a-form-item>

        <a-form-item label="API密钥" name="api_key">
          <a-input-password 
            v-model:value="configFormData.api_key" 
            placeholder="输入API密钥"
          />
        </a-form-item>

        <a-form-item label="自定义端点" name="custom_endpoint">
          <a-input 
            v-model:value="configFormData.custom_endpoint" 
            placeholder="可选：自定义API端点"
          />
        </a-form-item>

        <a-form-item label="自定义参数">
          <a-textarea 
            v-model:value="customParametersText"
            placeholder='可选：JSON格式的自定义参数，如 {"temperature": 0.1}'
            :rows="3"
          />
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- 测试结果弹窗 -->
    <a-modal
      v-model:open="testModalVisible"
      title="配置测试结果"
      width="500px"
      :footer="null"
    >
      <div v-if="testResult">
        <a-result
          :status="testResult.success ? 'success' : 'error'"
          :title="testResult.success ? '测试成功' : '测试失败'"
          :sub-title="testResult.message"
        >
          <template #extra v-if="testResult.details">
            <a-descriptions size="small" :column="1">
              <a-descriptions-item label="响应时间">
                {{ testResult.details.responseTime }}ms
              </a-descriptions-item>
              <a-descriptions-item label="模型">
                {{ testResult.details.model }}
              </a-descriptions-item>
              <a-descriptions-item label="Token使用" v-if="testResult.details.tokenUsage">
                {{ testResult.details.tokenUsage }}
              </a-descriptions-item>
            </a-descriptions>
          </template>
        </a-result>
      </div>
    </a-modal>

    <!-- 导入配置模态框 -->
    <a-modal
      v-model:open="showImportModal"
      title="导入LLM配置"
      width="600px"
      :footer="null"
      centered
    >
      <div class="import-config-container">
        <a-upload-dragger
          v-model:fileList="importFileList"
          :before-upload="handleImportFile"
          accept=".json"
          :multiple="false"
        >
          <p class="ant-upload-drag-icon">
            <InboxOutlined />
          </p>
          <p class="ant-upload-text">点击或拖拽文件到此区域上传</p>
          <p class="ant-upload-hint">
            支持JSON格式的配置文件
          </p>
        </a-upload-dragger>

        <div class="import-actions">
          <a-space>
            <a-button
              type="primary"
              @click="importConfigs"
              :loading="importing"
              :disabled="!importData"
            >
              <template #icon><ImportOutlined /></template>
              导入配置
            </a-button>
            <a-button @click="cancelImport">
              取消
            </a-button>
          </a-space>
        </div>

        <!-- 导入预览 -->
        <div v-if="importData" class="import-preview">
          <h4>配置预览</h4>
          <a-table
            :dataSource="importData"
            :columns="previewColumns"
            size="small"
            :pagination="false"
          />
        </div>
      </div>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import {
  ReloadOutlined,
  PlusOutlined,
  ImportOutlined,
  ExportOutlined,
  ExperimentOutlined,
  InboxOutlined
} from '@ant-design/icons-vue'

// 响应式数据
const loading = ref(false)
const configs = ref([])
const providers = ref([])
const models = ref([])
const configModalVisible = ref(false)
const testModalVisible = ref(false)
const editingConfig = ref(null)
const testResult = ref(null)

// 导入导出相关状态
const showImportModal = ref(false)
const importing = ref(false)
const importFileList = ref([])
const importData = ref(null)

// 测试相关状态
const showTestModal = ref(false)
const testing = ref(false)
const testPrompt = ref('请分析以下医疗文档的质量：\n\n主诉：患者因胸痛3小时来院就诊。\n现病史：患者3小时前无明显诱因出现胸痛，呈压榨性，伴有出汗。')

// 表格列定义
const columns = [
  {
    title: '配置类型',
    dataIndex: 'config_name',
    key: 'config_name',
    width: 120
  },
  {
    title: '提供商/模型',
    key: 'provider',
    width: 200
  },
  {
    title: '端点',
    dataIndex: 'base_endpoint',
    key: 'endpoint',
    ellipsis: true
  },
  {
    title: '状态',
    key: 'status',
    width: 80
  },
  {
    title: '操作',
    key: 'actions',
    width: 150
  }
]

// 导入预览表格列
const previewColumns = [
  {
    title: '配置类型',
    dataIndex: 'config_name',
    key: 'config_name'
  },
  {
    title: '提供商',
    dataIndex: 'provider_name',
    key: 'provider_name'
  },
  {
    title: '模型',
    dataIndex: 'model_name',
    key: 'model_name'
  },
  {
    title: '状态',
    dataIndex: 'is_active',
    key: 'is_active',
    customRender: ({ text }) => text ? '启用' : '禁用'
  }
]

// 表单数据
const configFormData = reactive({
  config_name: '',
  provider_id: '',
  model_id: '',
  api_key: '',
  custom_endpoint: '',
  custom_parameters: {}
})

const customParametersText = ref('')

// 表单验证规则
const configFormRules = {
  config_name: [{ required: true, message: '请选择配置类型' }],
  provider_id: [{ required: true, message: '请选择LLM提供商' }],
  model_id: [{ required: true, message: '请选择模型' }],
  api_key: [{ required: true, message: '请输入API密钥' }]
}

// 计算属性
const availableModels = computed(() => {
  if (!configFormData.provider_id) return []
  return models.value.filter(model => model.provider_id === configFormData.provider_id)
})

// 方法
const getConfigTypeColor = (configName) => {
  const colors = {
    'qc_analysis': 'blue',
    'extraction': 'green',
    'default': 'orange'
  }
  return colors[configName] || 'default'
}

const getConfigTypeName = (configName) => {
  const names = {
    'qc_analysis': '质控分析',
    'extraction': '文档提取',
    'default': '默认配置'
  }
  return names[configName] || configName
}

const refreshConfigs = async () => {
  loading.value = true
  try {
    const response = await fetch('/api/qc/llm-configs')
    const data = await response.json()
    configs.value = data.configs || []
  } catch (error) {
    message.error('获取配置失败: ' + error.message)
  } finally {
    loading.value = false
  }
}

const loadProviders = async () => {
  try {
    const response = await fetch('/api/v1/llm/providers')
    const data = await response.json()
    providers.value = data.providers || []
  } catch (error) {
    console.error('获取提供商失败:', error)
  }
}

const loadModels = async () => {
  try {
    const response = await fetch('/api/v1/llm/models')
    const data = await response.json()
    models.value = data.models || []
  } catch (error) {
    console.error('获取模型失败:', error)
  }
}

const showAddConfig = () => {
  editingConfig.value = null
  resetForm()
  configModalVisible.value = true
}

const editConfig = (config) => {
  editingConfig.value = config
  configFormData.config_name = config.config_name
  configFormData.provider_id = config.provider_id
  configFormData.model_id = config.model_id
  configFormData.api_key = '' // 不显示现有密钥
  configFormData.custom_endpoint = config.custom_endpoint || ''
  customParametersText.value = JSON.stringify(config.custom_parameters || {}, null, 2)
  configModalVisible.value = true
}

const resetForm = () => {
  Object.keys(configFormData).forEach(key => {
    configFormData[key] = ''
  })
  configFormData.custom_parameters = {}
  customParametersText.value = ''
}

const onProviderChange = () => {
  configFormData.model_id = ''
}

const saveConfig = async () => {
  try {
    // 解析自定义参数
    if (customParametersText.value.trim()) {
      try {
        configFormData.custom_parameters = JSON.parse(customParametersText.value)
      } catch (e) {
        message.error('自定义参数格式错误，请使用有效的JSON格式')
        return
      }
    }

    const url = editingConfig.value 
      ? `/api/qc/llm-configs/${editingConfig.value.config_id}`
      : '/api/qc/llm-configs'
    
    const method = editingConfig.value ? 'PUT' : 'POST'
    
    const response = await fetch(url, {
      method,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(configFormData)
    })

    if (response.ok) {
      message.success(editingConfig.value ? '配置更新成功' : '配置创建成功')
      configModalVisible.value = false
      refreshConfigs()
    } else {
      const error = await response.json()
      message.error(error.detail || '保存失败')
    }
  } catch (error) {
    message.error('保存失败: ' + error.message)
  }
}

const cancelEdit = () => {
  configModalVisible.value = false
  resetForm()
}

const testConfig = async (config) => {
  editingConfig.value = config
  showTestModal.value = true
}

const deleteConfig = async (config) => {
  try {
    const response = await fetch(`/api/qc/llm-configs/${config.config_id}`, {
      method: 'DELETE'
    })

    if (response.ok) {
      message.success('配置删除成功')
      refreshConfigs()
    } else {
      const error = await response.json()
      message.error(error.detail || '删除失败')
    }
  } catch (error) {
    message.error('删除失败: ' + error.message)
  }
}

// 导出配置
const exportConfigs = () => {
  try {
    const exportData = configs.value.map(config => ({
      config_name: config.config_name,
      provider_name: config.provider_name,
      model_name: config.model_name,
      custom_endpoint: config.custom_endpoint,
      custom_parameters: config.custom_parameters,
      is_active: config.is_active
    }))

    const blob = new Blob([JSON.stringify(exportData, null, 2)], {
      type: 'application/json'
    })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `llm-configs-${Date.now()}.json`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(url)

    message.success('配置导出成功')
  } catch (error) {
    console.error('导出失败:', error)
    message.error(`导出失败: ${error.message}`)
  }
}

// 处理导入文件
const handleImportFile = (file) => {
  const reader = new FileReader()
  reader.onload = (e) => {
    try {
      const data = JSON.parse(e.target.result)
      if (Array.isArray(data)) {
        importData.value = data
        message.success('文件解析成功')
      } else {
        throw new Error('文件格式不正确，应为配置数组')
      }
    } catch (error) {
      console.error('文件解析失败:', error)
      message.error(`文件解析失败: ${error.message}`)
    }
  }
  reader.readAsText(file)
  return false // 阻止自动上传
}

// 导入配置
const importConfigs = async () => {
  if (!importData.value) {
    message.error('请先选择要导入的文件')
    return
  }

  importing.value = true
  try {
    const baseURL = window.location.hostname === 'localhost'
      ? 'http://localhost:8001'
      : 'http://124.220.6.136:8001'

    for (const config of importData.value) {
      const response = await fetch(`${baseURL}/api/qc/llm-configs`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(config)
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(`导入配置 ${config.config_name} 失败: ${errorData.detail}`)
      }
    }

    message.success(`成功导入 ${importData.value.length} 个配置`)
    showImportModal.value = false
    cancelImport()
    refreshConfigs()

  } catch (error) {
    console.error('导入失败:', error)
    message.error(`导入失败: ${error.message}`)
  } finally {
    importing.value = false
  }
}

// 取消导入
const cancelImport = () => {
  showImportModal.value = false
  importFileList.value = []
  importData.value = null
}

// 增强的配置测试
const runConfigTest = async () => {
  if (!testPrompt.value.trim()) {
    message.error('请输入测试提示词')
    return
  }

  testing.value = true
  try {
    const baseURL = window.location.hostname === 'localhost'
      ? 'http://localhost:8001'
      : 'http://124.220.6.136:8001'

    const startTime = Date.now()
    const response = await fetch(`${baseURL}/api/qc/llm-configs/test`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        config_id: editingConfig.value.config_id,
        test_prompt: testPrompt.value
      })
    })

    const responseTime = Date.now() - startTime

    if (!response.ok) {
      const errorData = await response.json()
      throw new Error(errorData.detail || '测试失败')
    }

    const result = await response.json()

    testResult.value = {
      success: true,
      response_time: responseTime,
      response: result.response,
      details: result.details
    }

    message.success('配置测试成功')
    showTestModal.value = false
    testModalVisible.value = true

  } catch (error) {
    console.error('测试失败:', error)
    testResult.value = {
      success: false,
      response_time: 0,
      error: error.message
    }

    showTestModal.value = false
    testModalVisible.value = true
  } finally {
    testing.value = false
  }
}

// 生命周期
onMounted(() => {
  refreshConfigs()
  loadProviders()
  loadModels()
})
</script>

<style scoped>
.qc-llm-config {
  padding: 24px;
}

.provider-name {
  font-weight: 500;
}

.model-name {
  font-size: 12px;
  color: #666;
}

.test-config-container {
  padding: 16px 0;
}

.test-result {
  margin-top: 24px;
  padding: 16px;
  background: #f8f9fa;
  border-radius: 6px;
}

.test-result h4 {
  margin-bottom: 12px;
  color: #333;
}

.response-text {
  background: white;
  padding: 12px;
  border-radius: 4px;
  border: 1px solid #e8e8e8;
  max-height: 200px;
  overflow-y: auto;
}

.import-config-container {
  padding: 16px 0;
}

.import-actions {
  margin: 16px 0;
  text-align: center;
}

.import-preview {
  margin-top: 24px;
}

.import-preview h4 {
  margin-bottom: 12px;
  color: #333;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .qc-llm-config {
    padding: 12px;
  }

  .test-config-container,
  .import-config-container {
    padding: 8px 0;
  }
}
</style>
