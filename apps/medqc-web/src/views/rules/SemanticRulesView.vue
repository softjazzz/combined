<template>
  <div :class="['semantic-rules-view', showHeader ? 'min-h-screen bg-gray-50 p-3 lg:p-4' : '']">
    <!-- 页面头部 -->
    <div
      v-if="showHeader"
      class="bg-white rounded-lg shadow-sm border border-gray-200 p-4 mb-4"
    >
      <div class="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-3">
        <div class="flex-1">
          <div class="flex items-center space-x-2 mb-1">
            <div class="p-1.5 bg-blue-100 rounded-md">
              <BranchesOutlined class="text-lg text-blue-600" />
            </div>
            <h1 class="text-xl lg:text-2xl font-bold text-gray-900">
              质控规则管理
            </h1>
          </div>
          <p class="text-gray-600 text-xs lg:text-sm">
            统一管理传统质控规则和语义质控规则，支持规则创建、编辑、测试和版本管理
          </p>
        </div>
        <div class="flex flex-wrap gap-2">
          <a-button
            :loading="loading"
            class="flex items-center space-x-2"
            @click="refreshData"
          >
            <template #icon>
              <ReloadOutlined />
            </template>
            <span>刷新</span>
          </a-button>
          <a-button
            class="flex items-center space-x-2"
            @click="showSystemOverview = true"
          >
            <template #icon>
              <EyeOutlined />
            </template>
            <span>系统概览</span>
          </a-button>
          <a-button
            type="primary"
            class="flex items-center space-x-2 bg-blue-600 hover:bg-blue-700"
            @click="openImportRules"
          >
            <template #icon>
              <ImportOutlined />
            </template>
            <span>导入规则</span>
          </a-button>
        </div>
      </div>
    </div>

    <!-- 语义规则管理组件 -->
    <div class="rules-manager-container">
      <SemanticRulesManager />
    </div>

    <!-- 系统概览模态框 -->
    <a-modal
      v-model:open="showSystemOverview"
      title="语义质控系统概览"
      width="1000px"
      :footer="null"
      centered
    >
      <div class="system-overview">
        <a-descriptions
          title="系统信息"
          :column="2"
          bordered
        >
          <a-descriptions-item label="LLM提供商">
            {{ llmStatus.provider || 'Mock' }}
          </a-descriptions-item>
          <a-descriptions-item label="模型版本">
            {{ llmStatus.model || 'mock-gpt-4' }}
          </a-descriptions-item>
          <a-descriptions-item label="连接状态">
            <a-tag :color="llmStatus.real_llm_available ? 'green' : 'orange'">
              {{ llmStatus.real_llm_available ? '真实LLM' : 'Mock模式' }}
            </a-tag>
          </a-descriptions-item>
          <a-descriptions-item label="运行模式">
            <a-tag color="blue">
              语义分析模式
            </a-tag>
          </a-descriptions-item>
        </a-descriptions>

        <a-divider>执行统计</a-divider>
        <a-row :gutter="16">
          <a-col :span="8">
            <a-statistic
              title="总执行次数"
              :value="engineStats?.total_executions || 0"
              :value-style="{ color: '#2b6cf6' }"
            />
          </a-col>
          <a-col :span="8">
            <a-statistic
              title="成功执行次数"
              :value="engineStats?.successful_executions || 0"
              :value-style="{ color: '#52c41a' }"
            />
          </a-col>
          <a-col :span="8">
            <a-statistic
              title="失败执行次数"
              :value="engineStats?.failed_executions || 0"
              :value-style="{ color: '#ff4d4f' }"
            />
          </a-col>
        </a-row>

        <a-divider>Token使用情况</a-divider>
        <a-row :gutter="16">
          <a-col :span="12">
            <a-statistic
              title="总Token消耗"
              :value="engineStats?.total_tokens || 0"
              :value-style="{ color: '#722ed1' }"
            />
          </a-col>
          <a-col :span="12">
            <a-statistic
              title="总执行时间"
              :value="engineStats?.total_time || 0"
              :precision="2"
              suffix="s"
              :value-style="{ color: '#faad14' }"
            />
          </a-col>
        </a-row>

        <a-divider>系统特性</a-divider>
        <a-list
          :data-source="systemFeatures"
          size="small"
        >
          <template #renderItem="{ item }">
            <a-list-item>
              <a-list-item-meta>
                <template #avatar>
                  <a-avatar :style="{ backgroundColor: item.color }">
                    <component :is="item.icon" />
                  </a-avatar>
                </template>
                <template #title>
                  {{ item.title }}
                </template>
                <template #description>
                  {{ item.description }}
                </template>
              </a-list-item-meta>
            </a-list-item>
          </template>
        </a-list>
      </div>
    </a-modal>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed } from 'vue'
import { message } from 'ant-design-vue'
import {
  ReloadOutlined,
  EyeOutlined,
  FileTextOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
  BranchesOutlined,
  ExperimentOutlined,
  SafetyCertificateOutlined,
  ThunderboltOutlined,
  ImportOutlined,
  SearchOutlined,
  ClearOutlined
} from '@ant-design/icons-vue'

import SemanticRulesManager from '../../components/SemanticRulesManager.vue'
import { semanticRulesService } from '../../services/semantic-rules-service'
import { getAccessToken } from '../../utils/auth-token'

const props = defineProps({
  showHeader: {
    type: Boolean,
    default: true
  }
})

const showHeader = computed(() => props.showHeader)

// 响应式数据
const loading = ref(false)
const showSystemOverview = ref(false)
const engineStats = ref(null)
const llmStatus = ref({
  real_llm_available: false,
  mock_mode: true,
  provider: '',
  model: ''
})

const buildAuthHeaders = () => {
  const headers = { 'Content-Type': 'application/json' }
  const token = getAccessToken()
  if (token) {
    headers.Authorization = `Bearer ${token}`
  }
  return headers
}

// 系统特性列表
const systemFeatures = [
  {
    icon: 'BranchesOutlined',
    title: '语义理解',
    description: '基于大模型的深度语义分析，理解医疗文档的复杂含义',
    color: '#2b6cf6'
  },
  {
    icon: 'ExperimentOutlined',
    title: '智能推理',
    description: '利用LLM的推理能力，进行复杂的医疗逻辑判断',
    color: '#52c41a'
  },
  {
    icon: 'SafetyCertificateOutlined',
    title: '可解释性',
    description: '提供详细的推理过程和证据，确保质控结果的可信度',
    color: '#faad14'
  },
  {
    icon: 'ThunderboltOutlined',
    title: '自适应学习',
    description: '支持自定义规则创建，系统可根据自然语言描述生成质控规则',
    color: '#722ed1'
  }
]

// 计算属性
const totalRules = computed(() => {
  return engineStats.value?.total_rules || 0
})

// 方法
const openImportRules = () => {
  // 这里可以打开导入规则的模态框或跳转到导入页面
  message.info('导入规则功能开发中...')
}

const refreshData = async () => {
  loading.value = true
  try {
    // 获取统计信息
    const statsResponse = await semanticRulesService.getEngineStats()
    if (statsResponse.success && statsResponse.data) {
      engineStats.value = statsResponse.data
    }

    // 验证LLM连接
    const llmResponse = await semanticRulesService.validateLLMConnection()
    if (llmResponse.success && llmResponse.data) {
      llmStatus.value = llmResponse.data
    }

    // 获取规则总数（后端 page_size 最大为 200）
    // 使用相对路径以兼容 Vite 开发代理和生产环境反向代理
    const rulesResponse = await fetch(`/api/v1/semantic-rules?page=1&page_size=200`, {
      headers: buildAuthHeaders(),
    })
    if (rulesResponse.ok) {
      const data = await rulesResponse.json()
      if (data.success && engineStats.value) {
        // 使用后端返回的 count 字段作为总数
        engineStats.value.total_rules = data.count || 0
      }
    }

    message.success('数据刷新成功')
  } catch (error) {
    console.error('刷新数据失败:', error)
    message.error('刷新数据失败')
  } finally {
    loading.value = false
  }
}

// 生命周期
onMounted(() => {
  refreshData()
})
</script>

<style scoped>
.semantic-rules-view {
  padding: 0;
  background: transparent;
  min-height: auto;
}

.rules-manager-container {
  background: linear-gradient(180deg, #f8fbff 0%, #f2f7ff 100%);
  border-radius: 16px;
  margin: 0;
  box-shadow: inset 0 0 0 1px #d7e4f5;
  border: 1px solid #d7e4f5;
  padding: 10px;
}

.system-overview {
  max-height: 600px;
  overflow-y: auto;
}

:deep(.ant-descriptions-title) {
  font-size: 16px;
  font-weight: 600;
  margin-bottom: 16px;
  color: #1e293b;
}

:deep(.ant-btn) {
  border-radius: 10px;
  font-weight: 500;
  transition: all 0.2s ease;
}

:deep(.ant-btn-primary) {
  background: linear-gradient(135deg, #2f6fee 0%, #1f5de0 100%);
  border: none;
  box-shadow: 0 6px 14px rgba(47, 111, 238, 0.25);
  color: #ffffff !important;
}

:deep(.ant-btn-primary:hover) {
  background: linear-gradient(135deg, #1f5de0 0%, #184ab5 100%);
  transform: translateY(-1px);
  box-shadow: 0 9px 20px rgba(31, 93, 224, 0.32);
  color: #ffffff !important;
}

@media (max-width: 768px) {
  .rules-manager-container {
    border-radius: 10px;
    padding: 6px;
  }
}
</style>
