<template>
  <div class="rule-configuration">
    <div class="space-y-6">
      <!-- 标题和操作 -->
      <div class="flex items-center justify-between">
        <div>
          <h3 class="text-lg font-semibold text-slate-100 flex items-center gap-2 mb-2">
            <SettingOutlined class="text-purple-400" />
            质控规则配置
          </h3>
          <p class="text-sm text-slate-400">管理和配置质控分析规则，自定义检查标准</p>
        </div>
        <div class="flex items-center gap-3">
          <a-button
            @click="importRules"
            class="bg-blue-500/20 border-blue-400/30 text-blue-100 hover:bg-blue-500/30 hover:text-white"
          >
            <ImportOutlined />
            导入规则
          </a-button>
          <a-button
            @click="exportRules"
            class="bg-emerald-500/20 border-emerald-400/30 text-emerald-100 hover:bg-emerald-500/30 hover:text-white"
          >
            <ExportOutlined />
            导出规则
          </a-button>
          <a-button 
            type="primary"
            @click="showCreateRuleModal"
            class="bg-gradient-to-r from-purple-500 to-indigo-600 hover:from-purple-400 hover:to-indigo-500 border-none"
          >
            <PlusOutlined />
            新增规则
          </a-button>
        </div>
      </div>

      <!-- 筛选和搜索 -->
      <div class="p-4 rounded-lg bg-slate-700/30 border border-slate-600/30">
        <div class="flex flex-col lg:flex-row gap-4">
          <div class="flex-1">
            <a-input-search
              v-model:value="searchKeyword"
              placeholder="搜索规则名称、描述或类别..."
              size="large"
              @search="searchRules"
              class="search-input"
            >
              <template #prefix>
                <SearchOutlined class="text-slate-400" />
              </template>
            </a-input-search>
          </div>
          <div class="flex gap-3">
            <a-select
              v-model:value="selectedCategory"
              placeholder="规则类别"
              size="large"
              style="width: 150px"
              allow-clear
              @change="filterRules"
              class="category-filter"
            >
              <a-select-option 
                v-for="category in categories" 
                :key="category" 
                :value="category"
              >
                {{ category }}
              </a-select-option>
            </a-select>
            
            <a-select
              v-model:value="selectedStatus"
              placeholder="状态"
              size="large"
              style="width: 100px"
              allow-clear
              @change="filterRules"
              class="status-filter"
            >
              <a-select-option value="active">
                <div class="flex items-center gap-2">
                  <div class="w-2 h-2 rounded-full bg-emerald-400"></div>
                  启用
                </div>
              </a-select-option>
              <a-select-option value="inactive">
                <div class="flex items-center gap-2">
                  <div class="w-2 h-2 rounded-full bg-red-400"></div>
                  禁用
                </div>
              </a-select-option>
            </a-select>
          </div>
        </div>
      </div>

      <!-- 规则列表 -->
      <div class="space-y-4">
        <div
          v-for="rule in filteredRules"
          :key="rule.id"
          class="rule-card p-5 rounded-xl border border-slate-600/30 bg-slate-700/20 hover:border-slate-500/50 hover:bg-slate-700/30 transition-all duration-300"
        >
          <div class="flex items-start gap-4">
            <!-- 规则状态指示器 -->
            <div class="flex flex-col items-center gap-2 pt-1">
              <div 
                class="w-4 h-4 rounded-full"
                :class="rule.is_active ? 'bg-emerald-400' : 'bg-red-400'"
              ></div>
              <a-switch 
                v-model:checked="rule.is_active"
                size="small"
                @change="toggleRuleStatus(rule)"
              />
            </div>

            <div class="flex-1 min-w-0">
              <!-- 规则标题和操作 -->
              <div class="flex items-center justify-between mb-3">
                <div class="flex items-center gap-3">
                  <h4 class="font-semibold text-slate-100 text-base">{{ rule.name }}</h4>
                  <a-tag 
                    :color="getCategoryColor(rule.category)" 
                    size="small"
                    class="category-tag"
                  >
                    {{ rule.category }}
                  </a-tag>
                  <a-tag 
                    :color="getSeverityColor(rule.severity)" 
                    size="small"
                    class="severity-tag"
                  >
                    {{ getSeverityLabel(rule.severity) }}
                  </a-tag>
                </div>
                <div class="flex items-center gap-2">
                  <a-tooltip title="编辑规则">
                    <a-button
                      size="small"
                      type="text"
                      @click="editRule(rule)"
                      class="text-blue-200 hover:text-blue-100 hover:bg-blue-500/20"
                    >
                      <EditOutlined />
                    </a-button>
                  </a-tooltip>
                  <a-tooltip title="复制规则">
                    <a-button
                      size="small"
                      type="text"
                      @click="duplicateRule(rule)"
                      class="text-emerald-200 hover:text-emerald-100 hover:bg-emerald-500/20"
                    >
                      <CopyOutlined />
                    </a-button>
                  </a-tooltip>
                  <a-tooltip title="删除规则">
                    <a-button
                      size="small"
                      type="text"
                      @click="deleteRule(rule)"
                      class="text-red-200 hover:text-red-100 hover:bg-red-500/20"
                    >
                      <DeleteOutlined />
                    </a-button>
                  </a-tooltip>
                </div>
              </div>

              <!-- 规则描述 -->
              <p class="text-sm text-slate-300 mb-4 leading-relaxed">{{ rule.description }}</p>

              <!-- 规则详情 -->
              <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-4">
                <div class="flex items-center gap-2">
                  <CodeOutlined class="text-slate-400 text-sm" />
                  <span class="text-xs text-slate-400">规则代码：</span>
                  <code class="text-xs text-cyan-300 bg-slate-800/50 px-2 py-1 rounded">{{ rule.rule_code }}</code>
                </div>
                <div class="flex items-center gap-2">
                  <ThunderboltOutlined class="text-slate-400 text-sm" />
                  <span class="text-xs text-slate-400">权重：</span>
                  <span class="text-xs text-slate-200 font-medium">{{ rule.weight }}</span>
                </div>
                <div class="flex items-center gap-2">
                  <ClockCircleOutlined class="text-slate-400 text-sm" />
                  <span class="text-xs text-slate-400">更新时间：</span>
                  <span class="text-xs text-slate-200">{{ formatDate(rule.updated_at) }}</span>
                </div>
                <div class="flex items-center gap-2">
                  <UserOutlined class="text-slate-400 text-sm" />
                  <span class="text-xs text-slate-400">创建者：</span>
                  <span class="text-xs text-slate-200">{{ rule.created_by || '系统' }}</span>
                </div>
              </div>

              <!-- 规则条件预览 -->
              <div class="p-3 rounded-lg bg-slate-800/50 border border-slate-600/30">
                <div class="flex items-center gap-2 mb-2">
                  <FilterOutlined class="text-purple-400 text-sm" />
                  <span class="text-sm font-medium text-slate-200">规则条件</span>
                </div>
                <div class="text-xs text-slate-300 font-mono bg-slate-900/50 p-2 rounded border border-slate-600/20">
                  {{ rule.conditions || '暂无条件配置' }}
                </div>
              </div>

              <!-- 统计信息 -->
              <div class="flex items-center justify-between mt-4 pt-4 border-t border-slate-600/30">
                <div class="flex items-center gap-4 text-xs text-slate-400">
                  <span class="flex items-center gap-1">
                    <BarChartOutlined />
                    执行次数: {{ rule.execution_count || 0 }}
                  </span>
                  <span class="flex items-center gap-1">
                    <CheckCircleOutlined />
                    通过率: {{ rule.pass_rate || 0 }}%
                  </span>
                  <span class="flex items-center gap-1">
                    <ExclamationCircleOutlined />
                    发现问题: {{ rule.issue_count || 0 }}
                  </span>
                </div>
                <div class="flex items-center gap-2">
                  <a-button
                    size="small"
                    @click="testRule(rule)"
                    class="bg-amber-500/20 border-amber-400/30 text-amber-100 hover:bg-amber-500/30 hover:text-white"
                  >
                    <ExperimentOutlined />
                    测试规则
                  </a-button>
                  <a-button
                    size="small"
                    @click="viewRuleHistory(rule)"
                    class="bg-slate-600/50 border-slate-500/50 text-slate-100 hover:bg-slate-600/70 hover:text-white"
                  >
                    <HistoryOutlined />
                    历史记录
                  </a-button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 空状态 -->
      <div v-if="filteredRules.length === 0" class="text-center py-12">
        <div class="w-20 h-20 rounded-full bg-slate-700/50 flex items-center justify-center mx-auto mb-4">
          <SettingOutlined class="text-slate-400 text-3xl" />
        </div>
        <div class="text-slate-400 mb-2">暂无匹配的质控规则</div>
        <div class="text-sm text-slate-500">尝试调整筛选条件或创建新的规则</div>
      </div>

      <!-- 分页 -->
      <div v-if="filteredRules.length > 0" class="flex justify-center">
        <a-pagination
          v-model:current="currentPage"
          v-model:page-size="pageSize"
          :total="totalRules"
          :show-size-changer="true"
          :show-quick-jumper="true"
          :show-total="(total, range) => `第 ${range[0]}-${range[1]} 条，共 ${total} 条规则`"
          class="rule-pagination"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { message, Modal } from 'ant-design-vue'
import {
  SettingOutlined,
  ImportOutlined,
  ExportOutlined,
  PlusOutlined,
  SearchOutlined,
  EditOutlined,
  CopyOutlined,
  DeleteOutlined,
  CodeOutlined,
  ThunderboltOutlined,
  ClockCircleOutlined,
  UserOutlined,
  FilterOutlined,
  BarChartOutlined,
  CheckCircleOutlined,
  ExclamationCircleOutlined,
  ExperimentOutlined,
  HistoryOutlined
} from '@ant-design/icons-vue'
import type { QCRule } from '@/types'

type RuleWithStats = QCRule & {
  updated_at?: string
  conditions?: string
  execution_count?: number
  pass_rate?: number
  issue_count?: number
}

// Props
interface Props {
  rules?: RuleWithStats[]
}

const props = withDefaults(defineProps<Props>(), {
  rules: () => []
})

// Emits
const emit = defineEmits<{
  'rule-updated': [rule: RuleWithStats]
  'rule-created': [rule: RuleWithStats]
  'rule-deleted': [ruleId: string]
}>()

// 状态
const searchKeyword = ref('')
const selectedCategory = ref<string>()
const selectedStatus = ref<string>()
const currentPage = ref(1)
const pageSize = ref(10)

// 模拟规则数据
const rules = ref<RuleWithStats[]>([
  {
    id: '1',
    rule_code: 'QC001',
    name: '主诉完整性检查',
    description: '检查病案中主诉部分是否完整，包含患者主要症状和持续时间',
    category: '基本信息',
    severity: 'major',
    weight: 10,
    is_active: true,
    conditions: 'content.includes("主诉") && content.match(/\\d+[天日月年]/)',
    created_at: '2024-01-15T10:00:00Z',
    updated_at: '2024-01-20T15:30:00Z',
    execution_count: 1250,
    pass_rate: 85,
    issue_count: 187
  },
  {
    id: '2',
    rule_code: 'QC002',
    name: '诊断依据充分性',
    description: '检查诊断是否有充分的依据支撑，包括症状、体征、检查结果等',
    category: '诊断质量',
    severity: 'critical',
    weight: 15,
    is_active: true,
    conditions: 'diagnosis.length > 0 && evidence.length >= 3',
    created_at: '2024-01-10T09:00:00Z',
    updated_at: '2024-01-25T11:45:00Z',
    execution_count: 980,
    pass_rate: 78,
    issue_count: 215
  },
  {
    id: '3',
    rule_code: 'QC003',
    name: '用药合理性检查',
    description: '检查用药是否合理，包括药物选择、剂量、用法等',
    category: '治疗方案',
    severity: 'major',
    weight: 12,
    is_active: false,
    conditions: 'medications.every(med => med.dosage && med.frequency)',
    created_at: '2024-01-08T14:20:00Z',
    updated_at: '2024-01-22T16:10:00Z',
    execution_count: 756,
    pass_rate: 92,
    issue_count: 60
  }
])

// 计算属性
const categories = computed(() => {
  const cats = [...new Set(rules.value.map(r => r.category))]
  return cats.sort()
})

const filteredRules = computed(() => {
  let filtered = rules.value

  // 搜索筛选
  if (searchKeyword.value) {
    const keyword = searchKeyword.value.toLowerCase()
    filtered = filtered.filter(rule => 
      rule.name.toLowerCase().includes(keyword) ||
      rule.description.toLowerCase().includes(keyword) ||
      rule.category.toLowerCase().includes(keyword) ||
      rule.rule_code.toLowerCase().includes(keyword)
    )
  }

  // 类别筛选
  if (selectedCategory.value) {
    filtered = filtered.filter(rule => rule.category === selectedCategory.value)
  }

  // 状态筛选
  if (selectedStatus.value) {
    const isActive = selectedStatus.value === 'active'
    filtered = filtered.filter(rule => rule.is_active === isActive)
  }

  return filtered
})

const totalRules = computed(() => filteredRules.value.length)

// 方法
const searchRules = () => {
  currentPage.value = 1
}

const filterRules = () => {
  currentPage.value = 1
}

const toggleRuleStatus = async (rule: RuleWithStats) => {
  try {
    // 模拟API调用
    await new Promise(resolve => setTimeout(resolve, 500))
    
    message.success(`规则"${rule.name}"已${rule.is_active ? '启用' : '禁用'}`)
    emit('rule-updated', rule)
  } catch (error) {
    // 回滚状态
    rule.is_active = !rule.is_active
    message.error('状态更新失败')
  }
}

const showCreateRuleModal = () => {
  message.info('创建规则功能开发中...')
}

const editRule = (rule: RuleWithStats) => {
  message.info(`编辑规则"${rule.name}"功能开发中...`)
}

const duplicateRule = (rule: RuleWithStats) => {
  const newRule = {
    ...rule,
    id: Date.now().toString(),
    name: `${rule.name}_副本`,
    rule_code: `${rule.rule_code}_COPY`,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString()
  }
  
  rules.value.unshift(newRule)
  message.success(`规则"${rule.name}"已复制`)
  emit('rule-created', newRule)
}

const deleteRule = (rule: RuleWithStats) => {
  Modal.confirm({
    title: '确认删除', content: `确定要删除规则"${rule.name}"吗？此操作不可撤销。`, okText: '确认删除', okType: 'danger', cancelText: '取消', onOk: () => {
      const index = rules.value.findIndex(r => r.id === rule.id)
      if (index > -1) {
        rules.value.splice(index, 1)
        message.success(`规则"${rule.name}"已删除`)
        emit('rule-deleted', rule.id)
      }
    }
  })
}

const testRule = (rule: RuleWithStats) => {
  message.loading(`正在测试规则"${rule.name}"...`, 2)
  setTimeout(() => {
    message.success('规则测试完成，运行正常')
  }, 2000)
}

const viewRuleHistory = (rule: RuleWithStats) => {
  message.info(`查看规则"${rule.name}"历史记录功能开发中...`)
}

const importRules = () => {
  message.info('导入规则功能开发中...')
}

const exportRules = () => {
  message.info('导出规则功能开发中...')
}

const getCategoryColor = (category: string) => {
  const colors = {
    '基本信息': 'blue',
    '诊断质量': 'red',
    '治疗方案': 'green',
    '检查检验': 'orange',
    '护理记录': 'purple'
  }
  return colors[category as keyof typeof colors] || 'default'
}

const getSeverityColor = (severity: string) => {
  const colors = {
    critical: 'red',
    major: 'orange',
    minor: 'yellow',
    low: 'blue'
  }
  return colors[severity as keyof typeof colors] || 'default'
}

const getSeverityLabel = (severity: string) => {
  const labels = {
    critical: '严重',
    major: '重要',
    minor: '轻微',
    low: '提示'
  }
  return labels[severity as keyof typeof labels] || severity
}

const formatDate = (dateString: string) => {
  try {
    return new Date(dateString).toLocaleDateString('zh-CN')
  } catch {
    return dateString
  }
}

// 生命周期
onMounted(() => {
  // 初始化数据
})
</script>

<style scoped>
.rule-card {
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.rule-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 25px rgba(0, 0, 0, 0.15);
}

.category-tag,
.severity-tag {
  border: none !important;
  border-radius: 0.5rem !important;
  font-weight: 600 !important;
  font-size: 10px !important;
}

/* 搜索输入框样式 */
:deep(.search-input .ant-input) {
  background: rgba(255, 255, 255, 0.05) !important;
  border: 1px solid rgba(255, 255, 255, 0.1) !important;
  color: rgb(241 245 249) !important;
}

:deep(.search-input .ant-input:focus) {
  border-color: #8b5cf6 !important;
  box-shadow: 0 0 0 2px rgba(139, 92, 246, 0.2) !important;
}

/* 筛选器样式 */
:deep(.category-filter .ant-select-selector),
:deep(.status-filter .ant-select-selector) {
  background: rgba(255, 255, 255, 0.05) !important;
  border: 1px solid rgba(255, 255, 255, 0.1) !important;
  color: rgb(241 245 249) !important;
}

/* 开关样式 */
:deep(.ant-switch-checked) {
  background-color: #10b981 !important;
}

/* 分页样式 */
:deep(.rule-pagination .ant-pagination-item) {
  background: rgba(255, 255, 255, 0.05) !important;
  border: 1px solid rgba(255, 255, 255, 0.1) !important;
}

:deep(.rule-pagination .ant-pagination-item a) {
  color: rgb(203 213 225) !important;
}

:deep(.rule-pagination .ant-pagination-item-active) {
  background: rgba(139, 92, 246, 0.2) !important;
  border-color: #8b5cf6 !important;
}

:deep(.rule-pagination .ant-pagination-item-active a) {
  color: #a78bfa !important;
}

/* 按钮动画 */
:deep(.ant-btn) {
  transition: all 0.2s ease-out;
}

:deep(.ant-btn:hover) {
  transform: translateY(-1px);
}

/* 响应式设计 */
@media (max-width: 1024px) {
  .grid-cols-1.md\\:grid-cols-2.lg\\:grid-cols-4 {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 768px) {
  .flex.flex-col.lg\\:flex-row {
    flex-direction: column;
  }
  
  .grid-cols-1.md\\:grid-cols-2.lg\\:grid-cols-4 {
    grid-template-columns: 1fr;
  }
  
  .rule-card {
    padding: 1rem;
  }
}
</style>
