<template>
  <div class="llm-api-config-database">
    <a-card size="small">
      <div class="config-content">
        <!-- 配置管理头部 -->
        <div class="config-header mb-4">
          <a-row :gutter="16" align="middle">
            <a-col flex="auto">
              <h4 class="mb-0">大模型API配置管理</h4>
              <p class="text-sm text-gray-500 mb-0">配置将安全保存到数据库中</p>
            </a-col>
            <a-col>
              <a-space>
                <a-button @click="loadConfigs" :loading="loading">
                  <template #icon><ReloadOutlined /></template>
                  刷新
                </a-button>
                <a-button type="primary" @click="showCreateModal = true">
                  <template #icon><PlusOutlined /></template>
                  新建配置
                </a-button>
              </a-space>
            </a-col>
          </a-row>
        </div>

        <!-- 现有配置列表 -->
        <div class="config-list mb-4" v-if="userConfigs.length > 0">
          <h5>已保存的配置</h5>
          <a-list size="small" :data-source="userConfigs">
            <template #renderItem="{ item }">
              <a-list-item>
                <template #actions>
                  <a-button size="small" @click="loadConfig(item)">使用</a-button>
                  <a-button size="small" @click="editConfig(item)">编辑</a-button>
                  <a-popconfirm
                    title="确定要删除这个配置吗？"
                    @confirm="deleteConfig(item.id)"
                  >
                    <a-button size="small" danger>删除</a-button>
                  </a-popconfirm>
                </template>
                <a-list-item-meta>
                  <template #title>
                    <span>{{ item.config_name }}</span>
                    <a-tag v-if="item.config_name === 'default'" color="blue" size="small" class="ml-2">
                      默认
                    </a-tag>
                  </template>
                  <template #description>
                    <div class="text-xs">
                      <span>{{ item.provider?.provider_name }}</span>
                      <span class="mx-2">•</span>
                      <span>{{ item.model?.model_name }}</span>
                      <span class="mx-2">•</span>
                      <span class="text-gray-400">{{ formatDate(item.updated_at) }}</span>
                    </div>
                  </template>
                </a-list-item-meta>
              </a-list-item>
            </template>
          </a-list>
        </div>

        <!-- 当前配置显示 -->
        <div class="current-config" v-if="currentConfig">
          <a-alert
            :message="`当前使用配置: ${currentConfig.config_name}`"
            :description="`${currentConfig.provider?.provider_name} - ${currentConfig.model?.model_name}`"
            type="info"
            show-icon
            class="mb-4"
          />
        </div>

        <!-- 快速配置区域 -->
        <div class="quick-config">
          <a-divider>快速配置</a-divider>
          <a-row :gutter="16">
            <a-col :span="8">
              <a-card size="small" hoverable @click="quickConfig('alibaba')">
                <div class="text-center">
                  <div class="text-lg mb-2">🤖</div>
                  <div class="font-medium">阿里通义千问</div>
                  <div class="text-xs text-gray-500">企业级AI服务</div>
                </div>
              </a-card>
            </a-col>
            <a-col :span="8">
              <a-card size="small" hoverable @click="quickConfig('baidu')">
                <div class="text-center">
                  <div class="text-lg mb-2">🧠</div>
                  <div class="font-medium">百度文心一言</div>
                  <div class="text-xs text-gray-500">中文理解能力强</div>
                </div>
              </a-card>
            </a-col>
            <a-col :span="8">
              <a-card size="small" hoverable @click="quickConfig('local')">
                <div class="text-center">
                  <div class="text-lg mb-2">🏠</div>
                  <div class="font-medium">本地部署模型</div>
                  <div class="text-xs text-gray-500">数据完全私有</div>
                </div>
              </a-card>
            </a-col>
          </a-row>
        </div>
      </div>
    </a-card>

    <!-- 创建/编辑配置弹窗（增强版） -->
    <a-modal
      v-model:open="showCreateModal"
      :title="editingConfig ? '编辑配置' : '创建新配置'"
      width="900px"
      @ok="saveConfig"
      @cancel="cancelEdit"
      :confirm-loading="saving"
    >
      <a-form :model="configForm" layout="vertical">
        <!-- 基本信息 -->
        <a-card size="small" class="mb-3" :bordered="false">
          <template #title>
            <a-space><ApiOutlined /> 基本信息</a-space>
          </template>
          <a-row :gutter="16">
            <a-col :span="12">
              <a-form-item label="配置名称" required :rules="[{ required: true, message: '请输入配置名称' }]">
                <a-input v-model:value="configForm.config_name" placeholder="如: default, medical_analysis" />
              </a-form-item>
            </a-col>
            <a-col :span="12">
              <a-form-item label="API提供商" required :rules="[{ required: true, message: '请选择提供商' }]">
                <a-select v-model:value="configForm.provider_id" @change="onProviderChange" placeholder="请选择提供商">
                  <a-select-option v-for="provider in providers" :key="provider.id" :value="provider.id">
                    {{ provider.provider_name }}
                  </a-select-option>
                </a-select>
              </a-form-item>
            </a-col>
          </a-row>
          <a-row :gutter="16">
            <a-col :span="12">
              <a-form-item label="模型" required :rules="[{ required: true, message: '请选择模型' }]">
                <a-select v-model:value="configForm.model_id" :disabled="!availableModels.length" placeholder="请选择模型">
                  <a-select-option v-for="model in availableModels" :key="model.id" :value="model.id">
                    {{ model.display_name || model.model_name }}
                  </a-select-option>
                </a-select>
              </a-form-item>
            </a-col>
            <a-col :span="12">
              <a-form-item label="API密钥" :extra="'部分提供商必填，保存时将加密存储'">
                <a-input-password
                  v-model:value="configForm.api_key"
                  placeholder="输入API密钥"
                  :visibility-toggle="true"
                />
              </a-form-item>
            </a-col>
          </a-row>
        </a-card>

        <!-- 高级设置 -->
        <a-card size="small" class="mb-3" :bordered="false">
          <template #title>
            <a-space><CloudOutlined /> 高级设置</a-space>
          </template>
          <a-form-item label="自定义端点 (可选)">
            <a-input v-model:value="configForm.custom_endpoint" placeholder="如: https://api.example.com/v1/chat/completions" />
          </a-form-item>
          <a-form-item label="自定义参数 (JSON格式，可选)">
            <a-textarea
              v-model:value="customParametersText"
              :rows="4"
              placeholder='{"temperature": 0.7, "max_tokens": 2000}'
            />
          </a-form-item>
        </a-card>

        <!-- 工具栏：测试/导入导出 -->
        <a-space>
          <a-button @click="testConnection" :loading="testing">
            <template #icon><ApiOutlined /></template>
            测试连接
          </a-button>
          <a-upload :before-upload="handleImportConfig" :show-upload-list="false">
            <a-button>
              <template #icon><UploadOutlined /></template>
              导入配置
            </a-button>
          </a-upload>
          <a-button @click="exportConfig">
            <template #icon><DownloadOutlined /></template>
            导出配置
          </a-button>
        </a-space>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import {
  ReloadOutlined,
  PlusOutlined,
  CloudOutlined,
  UploadOutlined,
  DownloadOutlined,
  InfoCircleOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  ApiOutlined
} from '@ant-design/icons-vue'
import {
  llmConfigService,
  type LLMProvider,
  type LLMModel,
  type UserLLMConfig,
  type LLMConfigInput
} from '@/services/llmConfigService'
import { llmService } from '@/services/llmServiceNew'
import { useAuthStore } from '@/stores/auth'

// 新增状态
const testing = ref(false)

// 组件事件
const emit = defineEmits<{
  'config-updated': [config: UserLLMConfig]
  'close-modal': []
}>()

// 响应式数据
const loading = ref(false)
const saving = ref(false)
const showCreateModal = ref(false)
const editingConfig = ref<UserLLMConfig | null>(null)

const providers = ref<LLMProvider[]>([])
const availableModels = ref<LLMModel[]>([])
const userConfigs = ref<UserLLMConfig[]>([])
const currentConfig = ref<UserLLMConfig | null>(null)

// 表单数据
const configForm = reactive<LLMConfigInput>({
  config_name: '',
  provider_id: '',
  model_id: '',
  api_key: '',
  custom_endpoint: '',
  custom_parameters: {},
  is_active: true
})

const customParametersText = ref('')

// 计算属性
const formatDate = (dateStr: string) => {
  return new Date(dateStr).toLocaleString('zh-CN')
}

// 方法
const loadProviders = async () => {
  try {
    providers.value = await llmConfigService.getProviders()
  } catch (error) {
    message.error('加载API提供商失败')
    console.error(error)
  }
}

const loadConfigs = async () => {
  loading.value = true
  try {
    userConfigs.value = await llmConfigService.getUserConfigs()
    // 尝试加载默认配置
    const defaultConfig = userConfigs.value.find(c => c.config_name === 'default')
    if (defaultConfig) {
      currentConfig.value = defaultConfig
    }
  } catch (error) {
    message.error('加载配置失败')
    console.error(error)
  } finally {
    loading.value = false
  }
}

const onProviderChange = async (providerId: string) => {
  try {
    availableModels.value = await llmConfigService.getModelsByProvider(providerId)
    configForm.model_id = '' // 重置模型选择
  } catch (error) {
    message.error('加载模型失败')
    console.error(error)
  }
}

const loadConfig = (config: UserLLMConfig) => {
  currentConfig.value = config
  emit('config-updated', config)
  // 同步到运行时服务，便于立即使用
  llmService.updateConfig({
    apiEndpoint: config.custom_endpoint || (config.provider?.base_endpoint || ''),
    apiKey: (config as any).api_key_decrypted || '',
    model: config.model?.model_code || ''
  })
  message.success(`已切换到配置: ${config.config_name}`)
}

const editConfig = (config: UserLLMConfig) => {
  editingConfig.value = config
  Object.assign(configForm, {
    config_name: config.config_name,
    provider_id: config.provider_id,
    model_id: config.model_id,
    api_key: '', // 不显示已保存的密钥
    custom_endpoint: config.custom_endpoint || '',
    custom_parameters: config.custom_parameters || {},
    is_active: config.is_active
  })
  
  customParametersText.value = JSON.stringify(config.custom_parameters || {}, null, 2)
  
  // 加载对应的模型
  if (config.provider_id) {
    onProviderChange(config.provider_id)
  }
  
  showCreateModal.value = true
}

const deleteConfig = async (configId: string) => {
  try {
    await llmConfigService.deleteConfig(configId)
    message.success('配置已删除')
    await loadConfigs()
  } catch (error) {
    message.error('删除配置失败')
    console.error(error)
  }
}

const saveConfig = async () => {
  if (!configForm.config_name || !configForm.provider_id || !configForm.model_id) {
    message.error('请填写必填字段')
    return
  }

  saving.value = true
  try {
    // 解析自定义参数
    let customParams = {}
    if (customParametersText.value.trim()) {
      try {
        customParams = JSON.parse(customParametersText.value)
      } catch (e) {
        message.error('自定义参数格式错误，请检查JSON格式')
        saving.value = false
        return
      }
    }

    const configData: LLMConfigInput = {
      ...configForm,
      custom_parameters: customParams
    }

    const savedConfig = await llmConfigService.saveConfig(configData)
    message.success(editingConfig.value ? '配置已更新' : '配置已创建')

    showCreateModal.value = false
    await loadConfigs()

    // 如果是默认配置，自动加载
    if (savedConfig.config_name === 'default') {
      loadConfig(savedConfig)
    }

    // 延迟关闭外层Modal，让用户看到成功消息
    setTimeout(() => {
      console.log('🔄 准备自动关闭LLM配置Modal...')
      emit('close-modal')
      console.log('✅ 已发送关闭Modal事件')
    }, 1000) // 1秒后自动关闭
  } catch (error) {
    message.error('保存配置失败')
    console.error(error)
  } finally {
    saving.value = false
  }
}

const cancelEdit = () => {
  editingConfig.value = null
  Object.assign(configForm, {
    config_name: '',
    provider_id: '',
    model_id: '',
    api_key: '',
    custom_endpoint: '',
    custom_parameters: {},
    is_active: true
  })
  customParametersText.value = ''
  showCreateModal.value = false
}

const quickConfig = (type: string) => {
  // 快速配置逻辑
  const quickConfigs = {
    alibaba: {
      config_name: 'alibaba_quick',
      provider_code: 'alibaba'
    },
    baidu: {
      config_name: 'baidu_quick', 
      provider_code: 'baidu'
    },
    local: {
      config_name: 'local_quick',
      provider_code: 'local'
    }
  }
  
  const config = quickConfigs[type as keyof typeof quickConfigs]
  if (config) {
    const provider = providers.value.find(p => p.provider_code === config.provider_code)
    if (provider) {
      configForm.config_name = config.config_name
      configForm.provider_id = provider.id
      onProviderChange(provider.id)
      showCreateModal.value = true
    }
  }
}

// 工具函数：导入/导出/测试
const exportConfig = () => {
  const data = JSON.stringify(configForm, null, 2)
  const blob = new Blob([data], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${configForm.config_name || 'llm_config'}.json`
  a.click()
  URL.revokeObjectURL(url)
  message.success('配置已导出')
}

const handleImportConfig = async (file: File) => {
  try {
    const text = await file.text()
    const data = JSON.parse(text)
    Object.assign(configForm, {
      config_name: data.config_name || '',
      provider_id: data.provider_id || '',
      model_id: data.model_id || '',
      api_key: data.api_key || '',
      custom_endpoint: data.custom_endpoint || '',
      custom_parameters: data.custom_parameters || {},
      is_active: data.is_active !== false
    })
    customParametersText.value = JSON.stringify(configForm.custom_parameters || {}, null, 2)
    if (configForm.provider_id) await onProviderChange(configForm.provider_id)
    message.success('配置已导入')
  } catch (e) {
    message.error('导入失败：JSON格式不正确')
  }
  return false
}

const testConnection = async () => {
  try {
    testing.value = true
    // 将当前表单应用到 llmService，仅用于测试
    llmService.updateConfig({
      apiEndpoint: configForm.custom_endpoint || (currentConfig.value?.provider?.base_endpoint || ''),
      apiKey: configForm.api_key,
      model: availableModels.value.find(m => m.id === configForm.model_id)?.model_code || ''
    })

    // 调用一个轻量 probe（使用已有 parseMedicalText 的最小请求）
    const result = await llmService.parseMedicalText('ping', { maxTokens: 5, temperature: 0 })
    if (result.success) {
      message.success('连接正常')
    } else {
      message.error(result.error || '连接失败')
    }
  } catch (e: any) {
    message.error(`连接失败：${e.message || e}`)
  } finally {
    testing.value = false
  }
}

// 生命周期
onMounted(async () => {
  await loadProviders()
  await loadConfigs()
})
</script>

<style scoped>
.config-header h4 {
  @apply text-lg font-semibold;
}

.config-list {
  @apply border border-gray-200 rounded-lg p-4;
}

.quick-config .ant-card {
  @apply cursor-pointer transition-all duration-200;
}

.quick-config .ant-card:hover {
  @apply shadow-md border-blue-300;
}

.current-config {
  @apply mb-4;
}
</style>
