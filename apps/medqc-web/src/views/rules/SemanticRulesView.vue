<template>
  <div class="semantic-rules-view">
    <!-- 移除页面头部，因为现在是标签页内容 -->
    <div class="header-actions" style="margin-bottom: 16px;">
      <a-space>
        <a-button @click="refreshData" :loading="loading">
          <template #icon><ReloadOutlined /></template>
          刷新数据
        </a-button>
        <a-button type="primary" @click="showSystemOverview = true">
          <template #icon><EyeOutlined /></template>
          系统概览
        </a-button>
      </a-space>
    </div>

    <!-- 系统状态卡片 -->
    <a-row :gutter="16" class="status-cards">
      <a-col :span="6">
        <a-card size="small" :loading="loading">
          <a-statistic
            title="LLM连接状态"
            :value="llmStatus.real_llm_available ? '已连接' : 'Mock模式'"
            :value-style="{ 
              color: llmStatus.real_llm_available ? '#52c41a' : '#faad14' 
            }"
          >
            <template #prefix>
              <a-badge 
                :status="llmStatus.real_llm_available ? 'processing' : 'warning'" 
              />
            </template>
          </a-statistic>
        </a-card>
      </a-col>
      <a-col :span="6">
        <a-card size="small" :loading="loading">
          <a-statistic
            title="可用规则数"
            :value="totalRules"
            :value-style="{ color: '#1890ff' }"
          >
            <template #prefix><FileTextOutlined /></template>
          </a-statistic>
        </a-card>
      </a-col>
      <a-col :span="6">
        <a-card size="small" :loading="loading">
          <a-statistic
            title="执行成功率"
            :value="engineStats?.success_rate || 0"
            :precision="1"
            suffix="%"
            :value-style="{ color: '#52c41a' }"
          >
            <template #prefix><CheckCircleOutlined /></template>
          </a-statistic>
        </a-card>
      </a-col>
      <a-col :span="6">
        <a-card size="small" :loading="loading">
          <a-statistic
            title="平均响应时间"
            :value="engineStats?.avg_execution_time || 0"
            :precision="2"
            suffix="s"
            :value-style="{ color: '#722ed1' }"
          >
            <template #prefix><ClockCircleOutlined /></template>
          </a-statistic>
        </a-card>
      </a-col>
    </a-row>

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
        <a-descriptions title="系统信息" :column="2" bordered>
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
            <a-tag color="blue">语义分析模式</a-tag>
          </a-descriptions-item>
        </a-descriptions>

        <a-divider>执行统计</a-divider>
        <a-row :gutter="16">
          <a-col :span="8">
            <a-statistic
              title="总执行次数"
              :value="engineStats?.total_executions || 0"
              :value-style="{ color: '#1890ff' }"
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
                <template #title>{{ item.title }}</template>
                <template #description>{{ item.description }}</template>
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
  ThunderboltOutlined
} from '@ant-design/icons-vue'

import SemanticRulesManager from '../../components/SemanticRulesManager.vue'
import { semanticRulesService } from '../../services/semantic-rules-service'

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

// 系统特性列表
const systemFeatures = [
  {
    icon: 'BranchesOutlined',
    title: '语义理解',
    description: '基于大模型的深度语义分析，理解医疗文档的复杂含义',
    color: '#1890ff'
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

    // 获取规则数量（通过统计信息获取，不需要单独设置）
    const rulesResponse = await semanticRulesService.getAllSemanticRules()
    if (rulesResponse.success && rulesResponse.data) {
      // totalRules 现在是计算属性，会自动从 engineStats 中获取
      // 如果需要，可以将规则数量添加到 engineStats 中
      if (engineStats.value) {
        engineStats.value.total_rules = rulesResponse.data.length
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

.header-actions {
  display: flex;
  justify-content: flex-end;
  margin-bottom: 16px;
}

.status-cards {
  margin-bottom: 24px;
  padding: 0;
}

.rules-manager-container {
  background: white;
  border-radius: 8px;
  margin: 0;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.system-overview {
  max-height: 600px;
  overflow-y: auto;
}

.ant-statistic-content {
  font-size: 18px;
  font-weight: 600;
}

.ant-descriptions-title {
  font-size: 16px;
  font-weight: 600;
  margin-bottom: 16px;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .status-cards .ant-col {
    margin-bottom: 12px;
  }

  .rules-manager-container {
    margin: 0;
  }
}
</style>
