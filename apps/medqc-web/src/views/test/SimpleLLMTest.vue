<template>
  <div class="simple-llm-test">
    <a-card title="简化版LLM配置测试">
      <a-space
        direction="vertical"
        style="width: 100%"
      >
        <!-- 当前配置显示 -->
        <a-alert
          v-if="currentConfig"
          :message="`当前配置: ${currentConfig.config_name}`"
          :description="`${currentConfig.provider?.provider_name} - ${currentConfig.model?.model_name}`"
          type="info"
          show-icon
        />

        <!-- 操作按钮 -->
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
            @click="loadDefaultConfig"
          >
            加载默认配置
          </a-button>
          <a-button
            :loading="loading"
            @click="showConfigModal = true"
          >
            配置管理
          </a-button>
          <a-button
            :loading="loading"
            type="dashed"
            @click="testLLMService"
          >
            测试LLM服务
          </a-button>
          <a-button
            :loading="loading"
            @click="debugDatabase"
          >
            调试数据库
          </a-button>
          <a-button
            :loading="loading"
            type="default"
            @click="cleanupDuplicates"
          >
            清理重复配置
          </a-button>
        </a-space>

        <!-- 测试结果 -->
        <a-card
          size="small"
          title="操作结果"
        >
          <pre>{{ testResult }}</pre>
        </a-card>

        <!-- 文本输入测试 -->
        <a-card
          size="small"
          title="文本解析测试"
        >
          <a-textarea
            v-model:value="testText"
            :rows="4"
            placeholder="输入医疗文本进行测试解析..."
          />
          <div class="mt-2">
            <a-button
              :loading="parsing"
              type="primary"
              @click="parseText"
            >
              解析文本
            </a-button>
          </div>
        </a-card>

        <!-- 解析结果 -->
        <a-card
          v-if="parseResult"
          size="small"
          title="解析结果"
        >
          <pre>{{ parseResult }}</pre>
        </a-card>
      </a-space>
    </a-card>

    <!-- 配置管理弹窗 -->
    <a-modal
      v-model:open="showConfigModal"
      title="LLM配置管理"
      width="600px"
      @ok="showConfigModal = false"
    >
      <a-alert
        message="配置管理功能暂时禁用，请使用其他测试功能"
        type="info"
      />
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { message } from 'ant-design-vue'
// 分步导入，避免可能的循环依赖
import { llmConfigService, type UserLLMConfig } from '@/services/llmConfigService'
import { initLLMDatabase } from '@/utils/initLLMDatabase'

const loading = ref(false)
const parsing = ref(false)
const testResult = ref('')
const parseResult = ref('')
const showConfigModal = ref(false)
const currentConfig = ref<UserLLMConfig | null>(null)

const testText = ref(`患者张三，男，65岁，因头晕、头痛3天入院。
患者3天前无明显诱因出现头晕、头痛，伴恶心，无呕吐，无发热，无胸闷气短。
既往有高血压病史10年，平时服用降压药物治疗，血压控制尚可。
入院诊断：高血压病
主要手术：无`)

const initDatabase = async () => {
  loading.value = true
  try {
    await initLLMDatabase()
    testResult.value = '✅ 数据库初始化成功！\n已创建提供商、模型和默认配置。'
    message.success('数据库初始化成功')
  } catch (error) {
    testResult.value = `❌ 数据库初始化失败: ${error}`
    message.error('数据库初始化失败')
  } finally {
    loading.value = false
  }
}

const cleanupDuplicates = async () => {
  loading.value = true
  try {
    const { supabase } = await import('@/lib/backend-store')

    // 查询所有default配置
    const { data: configs } = await supabase
      .from('user_llm_configs')
      .select('*')
      .eq('config_name', 'default')
      .is('user_id', null)
      .order('created_at', { ascending: true })

    if (configs && configs.length > 1) {
      // 保留第一个，删除其他的
      const toDelete = configs.slice(1).map((c) => c.id)

      const { error } = await supabase.from('user_llm_configs').delete().in('id', toDelete)

      if (error) {
        throw error
      }

      testResult.value = `✅ 清理完成！删除了 ${toDelete.length} 个重复配置`
      message.success(`删除了 ${toDelete.length} 个重复配置`)
    } else {
      testResult.value = '✅ 没有发现重复配置'
      message.info('没有发现重复配置')
    }
  } catch (error) {
    testResult.value = `❌ 清理失败: ${error}`
    message.error('清理失败')
  } finally {
    loading.value = false
  }
}

const debugDatabase = async () => {
  loading.value = true
  try {
    // 直接查询数据库
    const { supabase } = await import('@/lib/backend-store')

    // 查询所有配置
    const { data: configs, error: configError } = await supabase
      .from('user_llm_configs')
      .select('*')

    // 查询所有提供商
    const { data: providers, error: providerError } = await supabase
      .from('llm_api_providers')
      .select('*')

    // 查询所有模型
    const { data: models, error: modelError } = await supabase.from('llm_models').select('*')

    testResult.value = `🔍 数据库调试信息:

配置数量: ${configs?.length || 0}
提供商数量: ${providers?.length || 0}
模型数量: ${models?.length || 0}

配置详情:
${JSON.stringify(configs, null, 2)}

错误信息:
配置错误: ${configError?.message || '无'}
提供商错误: ${providerError?.message || '无'}
模型错误: ${modelError?.message || '无'}`

    message.success('数据库调试完成')
  } catch (error) {
    testResult.value = `❌ 调试失败: ${error}`
    message.error('调试失败')
  } finally {
    loading.value = false
  }
}

const loadDefaultConfig = async () => {
  loading.value = true
  try {
    const { llmService } = await import('@/services/llmServiceNew')

    const success = await llmService.loadConfigFromDatabase('default')
    if (success) {
      currentConfig.value = llmService.getCurrentConfig()
      testResult.value = '✅ 默认配置加载成功！'
      message.success('默认配置加载成功')
    } else {
      testResult.value = '⚠️ 未找到默认配置，请先初始化数据库'
      message.warning('未找到默认配置')
    }
  } catch (error) {
    testResult.value = `❌ 加载配置失败: ${error}`
    message.error('加载配置失败')
  } finally {
    loading.value = false
  }
}

const testLLMService = async () => {
  loading.value = true
  try {
    // 动态导入llmService
    const { llmService } = await import('@/services/llmServiceNew')

    const config = llmService.getCurrentConfig()
    if (!config) {
      testResult.value = '⚠️ 请先加载配置'
      message.warning('请先加载配置')
      return
    }

    testResult.value = `✅ LLM服务配置信息:
配置名称: ${config.config_name}
提供商: ${config.provider?.provider_name}
模型: ${config.model?.model_name}
端点: ${config.provider?.base_endpoint}
是否有API密钥: ${config.api_key_encrypted ? '是' : '否'}`

    message.success('LLM服务测试成功')
  } catch (error) {
    testResult.value = `❌ LLM服务测试失败: ${error}`
    message.error('LLM服务测试失败')
  } finally {
    loading.value = false
  }
}

const parseText = async () => {
  if (!testText.value.trim()) {
    message.warning('请输入测试文本')
    return
  }

  parsing.value = true
  try {
    const { llmService } = await import('@/services/llmServiceNew')

    const result = await llmService.parseMedicalText(testText.value)
    parseResult.value = JSON.stringify(result, null, 2)

    if (result.success) {
      message.success('文本解析成功')
    } else {
      message.error(`文本解析失败: ${result.error}`)
    }
  } catch (error) {
    parseResult.value = `解析失败: ${error}`
    message.error('文本解析失败')
  } finally {
    parsing.value = false
  }
}

const handleConfigUpdated = async (config: UserLLMConfig) => {
  try {
    const { llmService } = await import('@/services/llmServiceNew')

    const success = await llmService.loadConfigFromDatabase(config.config_name)
    if (success) {
      currentConfig.value = llmService.getCurrentConfig()
      testResult.value = `✅ 配置已更新: ${config.config_name}`
      message.success(`配置已更新: ${config.config_name}`)
      showConfigModal.value = false
    }
  } catch (error) {
    testResult.value = `❌ 应用配置失败: ${error}`
    message.error('应用配置失败')
  }
}
</script>

<style scoped>
.simple-llm-test {
  padding: 20px;
}

pre {
  background: #f5f5f5;
  padding: 10px;
  border-radius: 4px;
  max-height: 300px;
  overflow-y: auto;
  white-space: pre-wrap;
  word-wrap: break-word;
}

.mt-2 {
  margin-top: 8px;
}
</style>
