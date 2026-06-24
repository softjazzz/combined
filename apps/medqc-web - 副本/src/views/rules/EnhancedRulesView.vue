<template>
  <div class="enhanced-rules-view">
    <div class="page-header">
      <h1>增强版规则配置</h1>
      <p>配置和管理医疗质控系统的增强版规则引擎</p>
    </div>

    <div class="content-wrapper">
      <!-- 规则引擎状态 -->
      <a-card
        title="规则引擎状态"
        class="status-card"
        :loading="loading"
      >
        <div class="status-grid">
          <div class="status-item">
            <div class="status-label">
              引擎状态
            </div>
            <div
              class="status-value"
              :class="engineStatus.status"
            >
              <a-badge :status="engineStatus.status === 'healthy' ? 'success' : 'error'" />
              {{ engineStatus.status === 'healthy' ? '运行正常' : '异常' }}
            </div>
          </div>
          <div class="status-item">
            <div class="status-label">
              活跃规则数
            </div>
            <div class="status-value">
              {{ engineStatus.activeRules }}
            </div>
          </div>
          <div class="status-item">
            <div class="status-label">
              今日执行次数
            </div>
            <div class="status-value">
              {{ engineStatus.executionCount }}
            </div>
          </div>
          <div class="status-item">
            <div class="status-label">
              平均响应时间
            </div>
            <div class="status-value">
              {{ engineStatus.avgResponseTime }}ms
            </div>
          </div>
        </div>
      </a-card>

      <!-- 规则管理 -->
      <a-card
        title="规则管理"
        class="rules-card"
      >
        <template #extra>
          <a-space>
            <a-button
              type="primary"
              @click="showCreateModal = true"
            >
              <template #icon>
                <PlusOutlined />
              </template>
              新建规则
            </a-button>
            <a-button @click="refreshRules">
              <template #icon>
                <ReloadOutlined />
              </template>
              刷新
            </a-button>
          </a-space>
        </template>

        <div class="rules-filters">
          <a-row :gutter="16">
            <a-col :span="6">
              <a-select
                v-model:value="filters.category"
                placeholder="规则类别"
                allow-clear
                @change="handleFilterChange"
              >
                <a-select-option value="completeness">
                  完整性检查
                </a-select-option>
                <a-select-option value="consistency">
                  一致性检查
                </a-select-option>
                <a-select-option value="timeliness">
                  及时性检查
                </a-select-option>
                <a-select-option value="accuracy">
                  准确性检查
                </a-select-option>
              </a-select>
            </a-col>
            <a-col :span="6">
              <a-select
                v-model:value="filters.status"
                placeholder="规则状态"
                allow-clear
                @change="handleFilterChange"
              >
                <a-select-option value="active">
                  启用
                </a-select-option>
                <a-select-option value="inactive">
                  禁用
                </a-select-option>
              </a-select>
            </a-col>
            <a-col :span="8">
              <a-input-search
                v-model:value="filters.keyword"
                placeholder="搜索规则名称或描述"
                @search="handleFilterChange"
              />
            </a-col>
          </a-row>
        </div>

        <a-table
          :columns="rulesColumns"
          :data-source="filteredRules"
          :loading="loading"
          :pagination="pagination"
          @change="handleTableChange"
        >
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'status'">
              <a-switch
                :checked="record.status === 'active'"
                @change="(checked: boolean) => toggleRuleStatus(record as RuleItem, checked)"
              />
            </template>
            <template v-else-if="column.key === 'category'">
              <a-tag :color="getCategoryColor(record.category)">
                {{ getCategoryName(record.category) }}
              </a-tag>
            </template>
            <template v-else-if="column.key === 'priority'">
              <a-tag :color="getPriorityColor(record.priority)">
                {{ record.priority }}
              </a-tag>
            </template>
            <template v-else-if="column.key === 'actions'">
              <a-space>
                <a-button
                  type="link"
                  size="small"
                  @click="editRule(record as RuleItem)"
                >
                  编辑
                </a-button>
                <a-button
                  type="link"
                  size="small"
                  @click="testRule(record as RuleItem)"
                >
                  测试
                </a-button>
                <a-popconfirm
                  title="确定要删除这个规则吗？"
                  @confirm="deleteRule(record as RuleItem)"
                >
                  <a-button
                    type="link"
                    size="small"
                    danger
                  >
                    删除
                  </a-button>
                </a-popconfirm>
              </a-space>
            </template>
          </template>
        </a-table>
      </a-card>
    </div>

    <!-- 创建/编辑规则模态框 -->
    <a-modal
      v-model:open="showCreateModal"
      :title="editingRule ? '编辑规则' : '创建规则'"
      width="800px"
      @ok="handleSaveRule"
      @cancel="handleCancelEdit"
    >
      <a-form
        ref="ruleFormRef"
        :model="ruleForm"
        :rules="ruleFormRules"
        layout="vertical"
      >
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item
              label="规则名称"
              name="name"
            >
              <a-input
                v-model:value="ruleForm.name"
                placeholder="请输入规则名称"
              />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item
              label="规则类别"
              name="category"
            >
              <a-select
                v-model:value="ruleForm.category"
                placeholder="请选择规则类别"
              >
                <a-select-option value="completeness">
                  完整性检查
                </a-select-option>
                <a-select-option value="consistency">
                  一致性检查
                </a-select-option>
                <a-select-option value="timeliness">
                  及时性检查
                </a-select-option>
                <a-select-option value="accuracy">
                  准确性检查
                </a-select-option>
              </a-select>
            </a-form-item>
          </a-col>
        </a-row>

        <a-form-item
          label="规则描述"
          name="description"
        >
          <a-textarea
            v-model:value="ruleForm.description"
            placeholder="请输入规则描述"
            :rows="3"
          />
        </a-form-item>

        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item
              label="优先级"
              name="priority"
            >
              <a-select
                v-model:value="ruleForm.priority"
                placeholder="请选择优先级"
              >
                <a-select-option value="high">
                  高
                </a-select-option>
                <a-select-option value="medium">
                  中
                </a-select-option>
                <a-select-option value="low">
                  低
                </a-select-option>
              </a-select>
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item
              label="规则状态"
              name="status"
            >
              <a-select
                v-model:value="ruleForm.status"
                placeholder="请选择状态"
              >
                <a-select-option value="active">
                  启用
                </a-select-option>
                <a-select-option value="inactive">
                  禁用
                </a-select-option>
              </a-select>
            </a-form-item>
          </a-col>
        </a-row>

        <a-form-item
          label="规则条件"
          name="conditions"
        >
          <a-textarea
            v-model:value="ruleForm.conditions"
            placeholder="请输入规则条件（JSON格式）"
            :rows="4"
          />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, computed, watch } from 'vue'
import { message } from 'ant-design-vue'
import type { FormProps, TableColumnsType, TablePaginationConfig } from 'ant-design-vue'
import { PlusOutlined, ReloadOutlined } from '@ant-design/icons-vue'

type RuleCategory = 'completeness' | 'consistency' | 'timeliness' | 'accuracy'
type RulePriority = 'high' | 'medium' | 'low'
type RuleStatus = 'active' | 'inactive'

interface RuleItem {
  id: string
  name: string
  category: RuleCategory
  description: string
  priority: RulePriority
  status: RuleStatus
  createdAt: string
  updatedAt: string
}

interface PaginationLike {
  current?: number
  pageSize?: number
}

// 响应式数据
const loading = ref(false)
const showCreateModal = ref(false)
const editingRule = ref<RuleItem | null>(null)

// 引擎状态
const engineStatus = reactive({
  status: 'healthy',
  activeRules: 156,
  executionCount: 2847,
  avgResponseTime: 125,
})

// 过滤器
const filters = reactive({
  category: undefined as RuleCategory | undefined,
  status: undefined as RuleStatus | undefined,
  keyword: '',
})

// 规则表单
const ruleForm = reactive({
  name: '',
  category: '' as RuleCategory | '',
  description: '',
  priority: 'medium' as RulePriority,
  status: 'active' as RuleStatus,
  conditions: '',
})

// 表单验证规则
const ruleFormRules = {
  name: [{ required: true, message: '请输入规则名称' }],
  category: [{ required: true, message: '请选择规则类别' }],
  description: [{ required: true, message: '请输入规则描述' }],
} satisfies NonNullable<FormProps['rules']>

// 模拟规则数据
const rules = ref<RuleItem[]>([
  {
    id: '1',
    name: '病历完整性检查',
    category: 'completeness',
    description: '检查病历必填字段是否完整',
    priority: 'high',
    status: 'active',
    createdAt: '2024-01-15',
    updatedAt: '2024-01-20',
  },
  {
    id: '2',
    name: '诊断一致性验证',
    category: 'consistency',
    description: '验证主诊断与辅助检查结果的一致性',
    priority: 'high',
    status: 'active',
    createdAt: '2024-01-16',
    updatedAt: '2024-01-21',
  },
  {
    id: '3',
    name: '用药合理性检查',
    category: 'accuracy',
    description: '检查用药剂量和配伍的合理性',
    priority: 'medium',
    status: 'active',
    createdAt: '2024-01-17',
    updatedAt: '2024-01-22',
  },
])

// 表格列配置
const rulesColumns: TableColumnsType<RuleItem> = [
  { title: '规则名称', dataIndex: 'name', key: 'name' },
  { title: '类别', dataIndex: 'category', key: 'category' },
  { title: '描述', dataIndex: 'description', key: 'description', ellipsis: true },
  { title: '优先级', dataIndex: 'priority', key: 'priority' },
  { title: '状态', dataIndex: 'status', key: 'status' },
  { title: '更新时间', dataIndex: 'updatedAt', key: 'updatedAt' },
  { title: '操作', key: 'actions', width: 200 },
]

// 分页配置
const pagination = reactive<TablePaginationConfig>({
  current: 1,
  pageSize: 10,
  total: 0,
  showSizeChanger: true,
  showQuickJumper: true,
})

// 计算属性
const filteredRules = computed(() => {
  let result = rules.value

  if (filters.category) {
    result = result.filter((rule) => rule.category === filters.category)
  }

  if (filters.status) {
    result = result.filter((rule) => rule.status === filters.status)
  }

  if (filters.keyword) {
    result = result.filter(
      (rule) => rule.name.includes(filters.keyword) || rule.description.includes(filters.keyword),
    )
  }

  return result
})

watch(
  filteredRules,
  (list) => {
    pagination.total = list.length
  },
  { immediate: true },
)

// 方法
const getCategoryColor = (category: string) => {
  const colors: Record<RuleCategory, string> = {
    completeness: 'blue',
    consistency: 'green',
    timeliness: 'orange',
    accuracy: 'red',
  }
  return category in colors ? colors[category as RuleCategory] : 'default'
}

const getCategoryName = (category: string) => {
  const names: Record<RuleCategory, string> = {
    completeness: '完整性',
    consistency: '一致性',
    timeliness: '及时性',
    accuracy: '准确性',
  }
  return category in names ? names[category as RuleCategory] : category
}

const getPriorityColor = (priority: string) => {
  const colors: Record<RulePriority, string> = {
    high: 'red',
    medium: 'orange',
    low: 'green',
  }
  return priority in colors ? colors[priority as RulePriority] : 'default'
}

const handleFilterChange = () => {
  pagination.current = 1
}

const handleTableChange = (pag: PaginationLike) => {
  pagination.current = pag.current ?? pagination.current
  pagination.pageSize = pag.pageSize ?? pagination.pageSize
}

const refreshRules = async () => {
  loading.value = true
  try {
    // 模拟API调用
    await new Promise((resolve) => setTimeout(resolve, 1000))
    message.success('规则列表已刷新')
  } catch (error) {
    message.error('刷新失败')
  } finally {
    loading.value = false
  }
}

const toggleRuleStatus = async (rule: RuleItem, checked: boolean) => {
  try {
    rule.status = checked ? 'active' : 'inactive'
    message.success(`规则已${checked ? '启用' : '禁用'}`)
  } catch (error) {
    message.error('状态更新失败')
  }
}

const editRule = (rule: RuleItem) => {
  editingRule.value = rule
  Object.assign(ruleForm, rule)
  showCreateModal.value = true
}

const testRule = (rule: RuleItem) => {
  message.info(`正在测试规则: ${rule.name}`)
}

const deleteRule = async (rule: RuleItem) => {
  try {
    const index = rules.value.findIndex((r) => r.id === rule.id)
    if (index > -1) {
      rules.value.splice(index, 1)
      message.success('规则已删除')
    }
  } catch (error) {
    message.error('删除失败')
  }
}

const handleSaveRule = async () => {
  try {
    if (editingRule.value) {
      // 编辑模式
      Object.assign(editingRule.value, ruleForm)
      message.success('规则已更新')
    } else {
      if (!ruleForm.category) {
        message.error('请选择规则类别')
        return
      }
      // 创建模式
      const newRule = {
        ...ruleForm,
        category: ruleForm.category as RuleCategory,
        id: Date.now().toString(),
        createdAt: new Date().toISOString().split('T')[0],
        updatedAt: new Date().toISOString().split('T')[0],
      }
      rules.value.unshift(newRule)
      message.success('规则已创建')
    }
    handleCancelEdit()
  } catch (error) {
    message.error('保存失败')
  }
}

const handleCancelEdit = () => {
  showCreateModal.value = false
  editingRule.value = null
  Object.assign(ruleForm, {
    name: '',
    category: '',
    description: '',
    priority: 'medium',
    status: 'active',
    conditions: '',
  })
}

// 生命周期
onMounted(() => {
  refreshRules()
})
</script>

<style scoped>
.enhanced-rules-view {
  padding: 24px;
}

.page-header {
  margin-bottom: 24px;
}

.page-header h1 {
  margin: 0 0 8px 0;
  font-size: 24px;
  font-weight: 600;
}

.page-header p {
  margin: 0;
  color: #666;
}

.content-wrapper {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.status-card {
  margin-bottom: 24px;
}

.status-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 24px;
}

.status-item {
  text-align: center;
}

.status-label {
  font-size: 14px;
  color: #666;
  margin-bottom: 8px;
}

.status-value {
  font-size: 20px;
  font-weight: 600;
}

.status-value.healthy {
  color: #52c41a;
}

.rules-filters {
  margin-bottom: 16px;
}

.rules-card {
  flex: 1;
}
</style>
