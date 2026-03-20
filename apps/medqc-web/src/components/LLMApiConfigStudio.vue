<template>
  <div class="studio min-h-[60vh] p-4 md:p-6 bg-gradient-to-br from-slate-50 to-blue-50">
    <!-- Header -->
    <div class="flex items-center justify-between mb-3">
      <div class="flex items-center gap-3">
        <span class="w-9 h-9 flex items-center justify-center rounded-xl bg-blue-100 text-blue-600 text-lg"><ApiOutlined /></span>
        <div>
          <div class="text-lg md:text-xl font-bold text-slate-900">大模型 API 配置</div>
          <div class="text-xs md:text-sm text-slate-500">创建、管理并测试你的大模型服务接入</div>
        </div>
      </div>
      <a-space>
        <a-upload :before-upload="onImport" :show-upload-list="false">
          <a-button class="hover:shadow-sm">
            <template #icon><UploadOutlined /></template>
            导入
          </a-button>
        </a-upload>
        <a-button :disabled="!selectedConfig" @click="exportCurrent" class="hover:shadow-sm">
          <template #icon><DownloadOutlined /></template>
          导出
        </a-button>
        <a-button type="primary" @click="openCreate()" class="shadow-sm hover:shadow">
          <template #icon><PlusOutlined /></template>
          新建
        </a-button>
        <a-button @click="loadAll" :loading="loading" class="hover:shadow-sm">
          <template #icon><ReloadOutlined /></template>
          刷新
        </a-button>
      </a-space>
    </div>

    <!-- Main with loading state -->
    <a-spin :spinning="loading" tip="加载中...">
      <a-row :gutter="[16,16]" class="studio__main">
        <!-- Left: list -->
        <a-col :xs="24" :md="9">
          <a-card size="small" :bordered="true" :loading="loading" class="rounded-2xl shadow-sm">
            <a-input-search v-model:value="search" placeholder="搜索配置/提供商/模型" allow-clear />
            <a-list class="mt-2 max-h-[420px] overflow-auto" :data-source="filteredConfigs" item-layout="horizontal" :split="false" :locale="{ emptyText: '暂无配置' }">
              <template #renderItem="{ item }">
                <a-list-item :class="['rounded-xl transition-all', item.id===selectedConfig?.id ? 'bg-blue-50' : 'hover:bg-slate-50']" @click="select(item)">
                  <template #actions>
                    <a-space>
                      <a-tooltip title="设为默认"><a-button type="text" size="small" @click.stop="setDefault(item)">默认</a-button></a-tooltip>
                      <a-button type="link" size="small" @click.stop="openEdit(item)">编辑</a-button>
                      <a-popconfirm title="确认删除该配置？" @confirm="remove(item)"><a-button type="text" danger size="small">删除</a-button></a-popconfirm>
                    </a-space>
                  </template>
                  <a-list-item-meta>
                    <template #title>
                      <span class="font-semibold text-slate-900">{{ item.config_name }}</span>
                      <a-tag v-if="item.config_name==='default'" color="blue" size="small" class="ml-1">默认</a-tag>
                    </template>
                    <template #description>
                      <div class="text-xs text-slate-500">{{ item.provider?.provider_name || '未指定' }} · {{ item.model?.model_name || '未指定模型' }}</div>
                    </template>
                  </a-list-item-meta>
                </a-list-item>
              </template>
            </a-list>
          </a-card>

          <a-card size="small" :bordered="false" v-if="providers.length" class="mt-3 rounded-xl">
            <div class="text-xs text-slate-500 mb-1">快速预设</div>
            <a-space wrap>
              <a-tag v-for="p in quickPresets" :key="p.provider_code" class="cursor-pointer bg-slate-50 border-slate-200" @click="applyPreset(p)">🧩 {{ p.name }}</a-tag>
            </a-space>
          </a-card>
        </a-col>

        <!-- Right: details -->
        <a-col :xs="24" :md="15">
          <a-card v-if="selectedConfig" :bordered="false" class="rounded-2xl shadow-sm">
            <div class="flex items-center justify-between">
              <div class="flex items-center gap-2">
                <span class="text-base font-bold text-slate-900">{{ selectedConfig.config_name }}</span>
                <a-tag>{{ selectedConfig.provider?.provider_name || '未指定提供商' }}</a-tag>
                <a-tag color="geekblue">{{ selectedConfig.model?.model_name || '未指定模型' }}</a-tag>
              </div>
              <a-space>
                <a-button @click="test(selectedConfig)" :loading="testing">
                  <template #icon><ApiOutlined /></template>
                  测试连接
                </a-button>
                <a-button type="primary" @click="openEdit(selectedConfig)">编辑</a-button>
              </a-space>
            </div>

            <a-descriptions size="small" :column="1" bordered class="mt-2">
              <a-descriptions-item label="API 端点">
                {{ selectedConfig.custom_endpoint || selectedConfig.provider?.base_endpoint || '-' }}
              </a-descriptions-item>
              <a-descriptions-item label="模型代码">
                {{ selectedConfig.model?.model_code || '-' }}
              </a-descriptions-item>
              <a-descriptions-item label="状态">
                <a-badge :status="testStatus.status" :text="testStatus.text" />
              </a-descriptions-item>
              <a-descriptions-item label="更新时间">
                {{ formatDate(selectedConfig.updated_at) }}
              </a-descriptions-item>
            </a-descriptions>
          </a-card>
          <a-empty v-else description="请选择左侧配置或新建配置" />
        </a-col>
      </a-row>
    </a-spin>

    <!-- Drawer: create/edit -->
    <a-drawer v-model:open="drawerOpen" :title="drawerTitle" width="520" :destroyOnClose="true">
      <a-form ref="formRef" layout="vertical" :model="form" :rules="rules">
        <a-form-item label="配置名称" name="config_name">
          <a-input v-model:value="form.config_name" placeholder="如：default 或 qwen_prod" />
        </a-form-item>
        <a-form-item label="API 提供商" name="provider_id">
          <a-select v-model:value="form.provider_id" placeholder="选择提供商" @change="onProviderChanged">
            <a-select-option v-for="p in providers" :key="p.id" :value="p.id">{{ p.provider_name }}</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item label="模型" name="model_id">
          <a-select v-model:value="form.model_id" placeholder="选择模型" :disabled="!models.length">
            <a-select-option v-for="m in models" :key="m.id" :value="m.id">{{ m.model_name }}</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item label="API 密钥" name="api_key" extra="密钥仅用于保存时写入数据库，界面不回显历史值">
          <a-input-password v-model:value="form.api_key" placeholder="填写或留空保持不变" />
        </a-form-item>
        <a-form-item label="自定义端点">
          <a-input v-model:value="form.custom_endpoint" placeholder="如 https://api.example.com/v1" />
        </a-form-item>
        <a-form-item label="自定义参数 (JSON)">
          <a-textarea v-model:value="customParamsText" :rows="4" placeholder='{"temperature":0.7,"max_tokens":2000}' />
        </a-form-item>
        <a-form-item label="启用">
          <a-switch v-model:checked="form.is_active" />
        </a-form-item>
        <div class="flex justify-end mt-2">
          <a-space>
            <a-button @click="drawerOpen=false">取消</a-button>
            <a-button @click="testTemp" :loading="testing" class="hover:shadow-sm"><ApiOutlined /> 测试</a-button>
            <a-button type="primary" @click="submit" :loading="saving" class="shadow-sm hover:shadow">保存</a-button>
          </a-space>
        </div>
      </a-form>
    </a-drawer>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { 
  ReloadOutlined, PlusOutlined, UploadOutlined, DownloadOutlined, ApiOutlined
} from '@ant-design/icons-vue'
import {
  llmConfigService,
  type LLMProvider,
  type LLMModel,
  type UserLLMConfig,
  type LLMConfigInput
} from '@/services/llmConfigService'
import { llmService } from '@/services/llmServiceNew'

const emit = defineEmits<{ 'config-updated': [config: UserLLMConfig] }>()

// state
const loading = ref(false)
const saving = ref(false)
const testing = ref(false)
const providers = ref<LLMProvider[]>([])
const configs = ref<UserLLMConfig[]>([])
const selectedConfig = ref<UserLLMConfig | null>(null)
const search = ref('')

// drawer/form
const drawerOpen = ref(false)
const formRef = ref()
const form = reactive<LLMConfigInput>({
  config_name: '', provider_id: '', model_id: '', api_key: '', custom_endpoint: '', custom_parameters: {}, is_active: true
})
const models = ref<LLMModel[]>([])
const customParamsText = ref('')
const rules = {
  config_name: [{ required: true, message: '请输入配置名称' }],
  provider_id: [{ required: true, message: '请选择提供商' }],
  model_id: [{ required: true, message: '请选择模型' }]
}

// test status
const testStatus = reactive<{status: 'processing'|'success'|'error'|'default', text: string}>({ status: 'default', text: '未测试' })

// quick presets
const quickPresets = computed(() => [
  { provider_code: 'alibaba', name: '通义·阿里云' },
  { provider_code: 'baidu', name: '文心·百度' },
  { provider_code: 'local', name: '本地Ollama/推理服务' }
])

const filteredConfigs = computed(() => {
  if (!search.value) return configs.value
  const q = search.value.toLowerCase()
  return configs.value.filter(c =>
    c.config_name.toLowerCase().includes(q) ||
    (c.provider?.provider_name || '').toLowerCase().includes(q) ||
    (c.model?.model_name || '').toLowerCase().includes(q)
  )
})

const formatDate = (s: string) => new Date(s).toLocaleString('zh-CN')

// actions
const loadAll = async () => {
  loading.value = true
  try {
    providers.value = await llmConfigService.getProviders()
    configs.value = await llmConfigService.getUserConfigs()
    if (!selectedConfig.value) selectedConfig.value = configs.value[0] || null
  } catch (e) {
    message.error('加载配置失败')
  } finally {
    loading.value = false
  }
}

const select = (c: UserLLMConfig) => {
  selectedConfig.value = c
  emit('config-updated', c)
}

const setDefault = async (c: UserLLMConfig) => {
  try {
    await llmConfigService.setDefaultConfig(c.id)
    message.success('已设为默认配置')
    await loadAll()
  } catch (e) { message.error('设置默认失败') }
}

const remove = async (c: UserLLMConfig) => {
  try {
    await llmConfigService.deleteConfig(c.id)
    message.success('已删除')
    await loadAll()
  } catch (e) { message.error('删除失败') }
}

const openCreate = () => {
  drawerOpen.value = true
  Object.assign(form, { config_name: '', provider_id: '', model_id: '', api_key: '', custom_endpoint: '', custom_parameters: {}, is_active: true })
  customParamsText.value = ''
  models.value = []
}

const openEdit = (c: UserLLMConfig) => {
  drawerOpen.value = true
  Object.assign(form, {
    config_name: c.config_name,
    provider_id: c.provider_id,
    model_id: c.model_id,
    api_key: '',
    custom_endpoint: c.custom_endpoint || '',
    custom_parameters: c.custom_parameters || {},
    is_active: c.is_active
  })
  customParamsText.value = JSON.stringify(form.custom_parameters || {}, null, 2)
  if (form.provider_id) onProviderChanged(form.provider_id)
}

const onProviderChanged = async (providerId: string) => {
  models.value = await llmConfigService.getModelsByProvider(providerId)
  form.model_id = ''
}

const submit = async () => {
  await formRef.value?.validate().catch(() => { throw new Error('表单校验失败') })
  saving.value = true
  try {
    let custom = {}
    if (customParamsText.value.trim()) {
      try { custom = JSON.parse(customParamsText.value) } catch { message.error('自定义参数 JSON 格式错误'); saving.value=false; return }
    }
    const data: LLMConfigInput = { ...form, custom_parameters: custom }
    const saved = await llmConfigService.saveConfig(data)
    message.success('配置已保存')
    drawerOpen.value = false
    await loadAll()
    select(saved)
  } catch (e) {
    message.error('保存失败')
  } finally { saving.value = false }
}

const test = async (c: UserLLMConfig) => {
  testing.value = true
  testStatus.status = 'processing'; testStatus.text = '测试中...'
  try {
    llmService.updateConfig({
      apiEndpoint: c.custom_endpoint || (c.provider?.base_endpoint || ''),
      apiKey: (c as any).api_key_decrypted || '',
      model: c.model?.model_code || ''
    })
    const r = await llmService.parseMedicalText('ping', { maxTokens: 5, temperature: 0 })
    if (r.success) { testStatus.status='success'; testStatus.text='连接正常' } else { testStatus.status='error'; testStatus.text=r.error || '失败' }
  } catch (e: unknown) { testStatus.status='error'; testStatus.text=e instanceof Error ? e.message : '失败' } finally { testing.value=false }
}

const testTemp = async () => {
  testing.value = true
  try {
    llmService.updateConfig({
      apiEndpoint: form.custom_endpoint || (selectedConfig.value?.provider?.base_endpoint || ''),
      apiKey: form.api_key,
      model: models.value.find(m => m.id===form.model_id)?.model_code || ''
    })
    const r = await llmService.parseMedicalText('ping', { maxTokens: 5, temperature: 0 })
    message[r.success ? 'success' : 'error'](r.success ? '连接正常' : (r.error || '连接失败'))
  } finally { testing.value = false }
}

// import/export
const onImport = async (file: File) => {
  try {
    const data = JSON.parse(await file.text())
    Object.assign(form, {
      config_name: data.config_name || '',
      provider_id: data.provider_id || '',
      model_id: data.model_id || '',
      api_key: data.api_key || '',
      custom_endpoint: data.custom_endpoint || '',
      custom_parameters: data.custom_parameters || {},
      is_active: data.is_active !== false
    })
    customParamsText.value = JSON.stringify(form.custom_parameters || {}, null, 2)
    if (form.provider_id) await onProviderChanged(form.provider_id)
    drawerOpen.value = true
    message.success('配置已导入')
  } catch { message.error('导入失败：JSON 无效') }
  return false
}

const exportCurrent = () => {
  if (!selectedConfig.value) return
  const content = JSON.stringify({
    config_name: selectedConfig.value.config_name,
    provider_id: selectedConfig.value.provider_id,
    model_id: selectedConfig.value.model_id,
    custom_endpoint: selectedConfig.value.custom_endpoint,
    custom_parameters: selectedConfig.value.custom_parameters,
    is_active: selectedConfig.value.is_active
  }, null, 2)
  const blob = new Blob([content], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a'); a.href = url; a.download = `${selectedConfig.value.config_name}.json`; a.click(); URL.revokeObjectURL(url)
  message.success('已导出')
}

const applyPreset = (preset: {provider_code:string, name:string}) => {
  const p = providers.value.find(x => x.provider_code === preset.provider_code)
  if (!p) return message.warning('该预设不可用')
  openCreate()
  form.config_name = `${preset.provider_code}_preset`
  form.provider_id = p.id
  onProviderChanged(p.id)
}

const drawerTitle = computed(() => form.config_name ? `编辑配置：${form.config_name}` : '新建配置')

onMounted(loadAll)
</script>



