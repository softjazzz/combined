<template>
  <div class="llm-config-test">
    <a-card title="LLM配置系统测试">
      <a-space
        direction="vertical"
        style="width: 100%"
      >
        <!-- 测试按钮 -->
        <a-space>
          <a-button
            :loading="loading"
            type="primary"
            @click="initDatabase"
          >
            初始化数据库
          </a-button>
          <a-button
            :loading="loading"
            @click="testLoadProviders"
          >
            测试加载提供商
          </a-button>
          <a-button
            :loading="loading"
            @click="testLoadConfigs"
          >
            测试加载配置
          </a-button>
          <a-button
            :loading="loading"
            @click="testCreateConfig"
          >
            测试创建配置
          </a-button>
        </a-space>

        <!-- 结果显示 -->
        <a-card
          size="small"
          title="测试结果"
        >
          <pre>{{ testResult }}</pre>
        </a-card>

        <!-- LLM配置组件 -->
        <a-divider>LLM配置组件测试</a-divider>
        <LLMApiConfigDatabase @config-updated="handleConfigUpdated" />
      </a-space>
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { message } from 'ant-design-vue'
import { llmConfigService, type UserLLMConfig } from '@/services/llmConfigService'
import { initLLMDatabase } from '@/utils/initLLMDatabase'
import LLMApiConfigDatabase from '@/components/LLMApiConfigDatabase.vue'

const loading = ref(false)
const testResult = ref('')

const initDatabase = async () => {
  loading.value = true
  try {
    await initLLMDatabase()
    testResult.value = '数据库初始化成功！\n已创建提供商、模型和默认配置。'
    message.success('数据库初始化成功')
  } catch (error) {
    testResult.value = `数据库初始化失败: ${error}`
    message.error('数据库初始化失败')
  } finally {
    loading.value = false
  }
}

const testLoadProviders = async () => {
  loading.value = true
  try {
    const providers = await llmConfigService.getProviders()
    testResult.value = JSON.stringify(providers, null, 2)
    message.success(`成功加载 ${providers.length} 个提供商`)
  } catch (error) {
    testResult.value = `错误: ${error}`
    message.error('加载提供商失败')
  } finally {
    loading.value = false
  }
}

const testLoadConfigs = async () => {
  loading.value = true
  try {
    const configs = await llmConfigService.getUserConfigs()
    testResult.value = JSON.stringify(configs, null, 2)
    message.success(`成功加载 ${configs.length} 个配置`)
  } catch (error) {
    testResult.value = `错误: ${error}`
    message.error('加载配置失败')
  } finally {
    loading.value = false
  }
}

const testCreateConfig = async () => {
  loading.value = true
  try {
    // 首先获取提供商和模型
    const providers = await llmConfigService.getProviders()
    if (providers.length === 0) {
      throw new Error('没有可用的提供商')
    }
    
    const models = await llmConfigService.getModelsByProvider(providers[0].id)
    if (models.length === 0) {
      throw new Error('没有可用的模型')
    }

    // 创建测试配置
    const config = await llmConfigService.saveConfig({
      config_name: 'test_config',
      provider_id: providers[0].id,
      model_id: models[0].id,
      api_key: 'test-api-key',
      custom_parameters: { temperature: 0.7 }
    })

    testResult.value = JSON.stringify(config, null, 2)
    message.success('成功创建测试配置')
  } catch (error) {
    testResult.value = `错误: ${error}`
    message.error('创建配置失败')
  } finally {
    loading.value = false
  }
}

const handleConfigUpdated = (config: UserLLMConfig) => {
  testResult.value = `配置已更新: ${JSON.stringify(config, null, 2)}`
  message.success(`配置已更新: ${config.config_name}`)
}
</script>

<style scoped>
.llm-config-test {
  padding: 20px;
}

pre {
  background: #f5f5f5;
  padding: 10px;
  border-radius: 4px;
  max-height: 400px;
  overflow-y: auto;
}
</style>
