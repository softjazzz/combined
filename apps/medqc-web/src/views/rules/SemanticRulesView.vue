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
    const rulesResponse = await fetch(`/api/v1/semantic-rules?page=1&page_size=200`)
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
/* 主容器样式 */
.semantic-rules-view {
  padding: 0;
  background: transparent;
  min-height: auto;
}


/* 规则管理容器 */
.rules-manager-container {
  background: white;
  border-radius: 12px;
  margin: 0;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1), 0 1px 2px rgba(0, 0, 0, 0.06);
  border: 1px solid #e2e8f0;
}

/* 系统概览模态框 */
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

/* 快速筛选标签样式 */
.filter-tag {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  padding: 6px 12px;
  border-radius: 8px;
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  user-select: none;
  border: 2px solid transparent;

  /* 未选中状态 */
  background: rgba(248, 250, 252, 0.8);
  color: #64748b;
  border-color: #e2e8f0;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
}

.filter-tag:hover {
  background: rgba(241, 245, 249, 1);
  color: #475569;
  border-color: #cbd5e1;
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

/* 选中状态 - 主要筛选 */
.filter-tag-active {
  background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%);
  color: white;
  border-color: #2563eb;
  box-shadow: 0 4px 16px rgba(59, 130, 246, 0.3);
}

.filter-tag-active:hover {
  background: linear-gradient(135deg, #2563eb 0%, #1e40af 100%);
  transform: translateY(-1px);
  box-shadow: 0 6px 20px rgba(59, 130, 246, 0.4);
}

/* 危险类型筛选 */
.filter-tag-danger {
  background: rgba(254, 242, 242, 0.8);
  color: #dc2626;
  border-color: #fecaca;
}

.filter-tag-danger:hover {
  background: rgba(254, 226, 226, 1);
  color: #b91c1c;
  border-color: #fca5a5;
}

.filter-tag-danger-active {
  background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
  color: white;
  border-color: #dc2626;
  box-shadow: 0 4px 16px rgba(239, 68, 68, 0.3);
}

.filter-tag-danger-active:hover {
  background: linear-gradient(135deg, #dc2626 0%, #b91c1c 100%);
  box-shadow: 0 6px 20px rgba(239, 68, 68, 0.4);
}

/* 成功类型筛选 */
.filter-tag-success {
  background: rgba(240, 253, 244, 0.8);
  color: #16a34a;
  border-color: #bbf7d0;
}

.filter-tag-success:hover {
  background: rgba(220, 252, 231, 1);
  color: #15803d;
  border-color: #86efac;
}

.filter-tag-success-active {
  background: linear-gradient(135deg, #22c55e 0%, #16a34a 100%);
  color: white;
  border-color: #16a34a;
  box-shadow: 0 4px 16px rgba(34, 197, 94, 0.3);
}

.filter-tag-success-active:hover {
  background: linear-gradient(135deg, #16a34a 0%, #15803d 100%);
  box-shadow: 0 6px 20px rgba(34, 197, 94, 0.4);
}

/* 筛选标签文本 */
.filter-tag-text {
  font-weight: 500;
  letter-spacing: 0.025em;
}

/* 筛选标签计数 */
.filter-tag-count {
  font-size: 11px;
  opacity: 0.8;
  font-weight: 600;
  margin-left: 2px;
}

.filter-tag-active .filter-tag-count {
  opacity: 0.9;
}

/* 按钮样式优化 */
:deep(.ant-btn) {
  border-radius: 8px;
  font-weight: 500;
  transition: all 0.2s ease;
}

:deep(.ant-btn-primary) {
  background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%);
  border: none;
  box-shadow: 0 2px 8px rgba(59, 130, 246, 0.2);
  color: #ffffff !important; /* 确保文字为白色 */
}

:deep(.ant-btn-primary:hover) {
  background: linear-gradient(135deg, #2563eb 0%, #1e40af 100%);
  transform: translateY(-1px);
  box-shadow: 0 4px 16px rgba(59, 130, 246, 0.3);
  color: #ffffff !important; /* 确保悬停时文字也为白色 */
}

:deep(.ant-btn-primary span) {
  color: #ffffff !important; /* 确保按钮内的span文字为白色 */
}

:deep(.ant-btn-primary:hover span) {
  color: #ffffff !important; /* 确保悬停时按钮内的span文字也为白色 */
}

/* 卡片样式优化 */
:deep(.ant-card) {
  border-radius: 12px;
  border: 1px solid #e2e8f0;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

:deep(.ant-card-head) {
  border-bottom: 1px solid #f1f5f9;
  background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
}

/* 标签样式优化 */
:deep(.ant-tag) {
  border-radius: 6px;
  font-weight: 500;
  padding: 4px 12px;
  font-size: 12px;
  border: none;
}

/* 焦点状态（键盘导航） */
.filter-tag:focus {
  outline: 2px solid #3b82f6;
  outline-offset: 2px;
}

/* 活跃状态增强 */
.filter-tag:active {
  transform: translateY(0);
  transition-duration: 0.1s;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .semantic-rules-view {
    padding: 12px;
  }
  
  .filter-tag {
    padding: 5px 10px;
    font-size: 11px;
  }

  .rules-manager-container {
    margin: 0;
    border-radius: 6px;
  }
}
</style>
