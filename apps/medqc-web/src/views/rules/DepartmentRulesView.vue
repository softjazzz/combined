<template>
  <div class="page-container min-h-screen bg-gray-50 p-2 lg:p-3">
    <!-- 页面头部 -->
    <div class="bg-white rounded-lg shadow-sm border border-gray-200 p-2 mb-2">
      <div class="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-2">
        <div class="flex-1">
          <div class="flex items-center space-x-2 mb-0.5">
            <div class="p-1 bg-blue-100 rounded-md">
              <ApartmentOutlined class="text-base text-blue-600" />
            </div>
            <h1 class="text-lg lg:text-xl font-bold text-gray-900">
              科室级质控规则管理
            </h1>
          </div>
          <p class="text-gray-600 text-xs">
            管理科室级质控规则，支持覆盖全局规则或创建科室特有规则
          </p>
        </div>
        <div class="flex flex-wrap gap-1.5">
          <a-button
            @click="refreshRules"
            :loading="loading"
            size="small"
            class="flex items-center space-x-1"
          >
            <template #icon><ReloadOutlined /></template>
            <span>刷新</span>
          </a-button>
          <a-button
            type="primary"
            @click="showCreateModal"
            size="small"
            class="flex items-center space-x-1 bg-blue-600 hover:bg-blue-700"
          >
            <template #icon><PlusOutlined /></template>
            <span>新增科室规则</span>
          </a-button>
        </div>
      </div>
    </div>

    <!-- 筛选区域 -->
    <div class="bg-white rounded-lg shadow-sm border border-gray-200 p-3 mb-2">
      <a-row :gutter="[16, 16]">
        <a-col :xs="24" :sm="12" :md="6">
          <a-select
            v-model:value="filters.department_id"
            placeholder="选择科室"
            allow-clear
            show-search
            :filter-option="filterDepartmentOption"
            @change="handleFilterChange"
            class="w-full"
            size="small"
          >
            <a-select-option
              v-for="dept in departments"
              :key="dept.id"
              :value="dept.id"
            >
              {{ dept.name }}
            </a-select-option>
          </a-select>
        </a-col>
        <a-col :xs="24" :sm="12" :md="6">
          <a-select
            v-model:value="filters.status_filter"
            placeholder="规则状态"
            allow-clear
            @change="handleFilterChange"
            class="w-full"
            size="small"
          >
            <a-select-option value="draft">草稿</a-select-option>
            <a-select-option value="published">已发布</a-select-option>
            <a-select-option value="archived">已归档</a-select-option>
          </a-select>
        </a-col>
        <a-col :xs="24" :sm="12" :md="6">
          <a-select
            v-model:value="filters.override_action"
            placeholder="覆盖行为"
            allow-clear
            @change="handleFilterChange"
            class="w-full"
            size="small"
          >
            <a-select-option value="override">覆盖配置</a-select-option>
            <a-select-option value="disable">禁用规则</a-select-option>
          </a-select>
        </a-col>
        <a-col :xs="24" :sm="12" :md="6">
          <a-input-search
            v-model:value="filters.keyword"
            placeholder="搜索规则编号、名称"
            @search="handleFilterChange"
            allow-clear
            size="small"
          />
        </a-col>
      </a-row>
    </div>

    <!-- 规则列表 -->
    <div class="bg-white rounded-lg shadow-sm border border-gray-200 p-3">
      <a-table
        :columns="columns"
        :data-source="rules"
        :loading="loading"
        :pagination="pagination"
        @change="handleTableChange"
        :scroll="{ x: 1200 }"
        size="small"
        row-key="id"
      >
        <!-- 规则编号 -->
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'rule_code'">
            <div class="flex items-center space-x-2">
              <a-tag color="blue" class="text-xs">{{ record.rule_code }}</a-tag>
              <a-tag v-if="record.parent_rule_id" color="orange" class="text-xs">
                覆盖
              </a-tag>
            </div>
          </template>

          <!-- 规则名称 -->
          <template v-else-if="column.key === 'name'">
            <div>
              <div class="font-medium text-gray-900">{{ record.name }}</div>
              <div v-if="record.description" class="text-xs text-gray-500 mt-0.5">
                {{ record.description }}
              </div>
            </div>
          </template>

          <!-- 科室 -->
          <template v-else-if="column.key === 'department'">
            <a-tag color="green" class="text-xs">
              {{ getDepartmentName(record.department_id) }}
            </a-tag>
          </template>

          <!-- 状态 -->
          <template v-else-if="column.key === 'status'">
            <a-tag :color="getStatusColor(record.status)" class="text-xs">
              {{ getStatusText(record.status) }}
            </a-tag>
          </template>

          <!-- 覆盖行为 -->
          <template v-else-if="column.key === 'override_action'">
            <a-tag
              :color="record.override_action === 'override' ? 'blue' : 'red'"
              class="text-xs"
            >
              {{ record.override_action === 'override' ? '覆盖配置' : '禁用规则' }}
            </a-tag>
          </template>

          <!-- 优先级 -->
          <template v-else-if="column.key === 'priority'">
            <a-badge
              :count="record.priority"
              :number-style="{ backgroundColor: '#52c41a' }"
            />
          </template>

          <!-- 操作 -->
          <template v-else-if="column.key === 'actions'">
            <a-space :size="4">
              <a-button
                type="link"
                size="small"
                @click="viewRule(record)"
                class="p-0"
              >
                查看
              </a-button>
              <a-button
                type="link"
                size="small"
                @click="editRule(record)"
                class="p-0"
              >
                编辑
              </a-button>
              <a-button
                v-if="record.status === 'draft'"
                type="link"
                size="small"
                @click="publishRule(record)"
                class="p-0 text-green-600"
              >
                发布
              </a-button>
              <a-button
                type="link"
                size="small"
                @click="viewHistory(record)"
                class="p-0"
              >
                历史
              </a-button>
              <a-popconfirm
                title="确定要删除这条规则吗？"
                ok-text="确定"
                cancel-text="取消"
                @confirm="deleteRule(record)"
              >
                <a-button
                  type="link"
                  danger
                  size="small"
                  class="p-0"
                >
                  删除
                </a-button>
              </a-popconfirm>
            </a-space>
          </template>
        </template>
      </a-table>
    </div>

    <!-- 创建/编辑规则对话框 -->
    <a-modal
      v-model:open="modalVisible"
      :title="modalTitle"
      width="800px"
      :confirm-loading="modalLoading"
      @ok="handleModalOk"
      @cancel="handleModalCancel"
    >
      <a-form
        ref="formRef"
        :model="formData"
        :rules="formRules"
        :label-col="{ span: 6 }"
        :wrapper-col="{ span: 18 }"
      >
        <!-- 创建模式选择 -->
        <a-form-item v-if="isCreateMode" label="创建模式">
          <a-radio-group v-model:value="createMode" @change="handleCreateModeChange">
            <a-radio value="override">基于全局规则创建</a-radio>
            <a-radio value="new">全新创建</a-radio>
          </a-radio-group>
        </a-form-item>

        <!-- 选择全局规则 -->
        <a-form-item
          v-if="isCreateMode && createMode === 'override'"
          label="选择全局规则"
          name="base_rule_id"
        >
          <a-select
            v-model:value="formData.base_rule_id"
            placeholder="选择要覆盖的全局规则"
            show-search
            :filter-option="filterRuleOption"
            @change="handleBaseRuleChange"
          >
            <a-select-option
              v-for="rule in globalRules"
              :key="rule.id"
              :value="rule.id"
            >
              {{ rule.rule_code }} - {{ rule.name }}
            </a-select-option>
          </a-select>
        </a-form-item>

        <!-- 科室选择 -->
        <a-form-item label="科室" name="department_id" required>
          <a-select
            v-model:value="formData.department_id"
            placeholder="选择科室"
            show-search
            :filter-option="filterDepartmentOption"
          >
            <a-select-option
              v-for="dept in departments"
              :key="dept.id"
              :value="dept.id"
            >
              {{ dept.name }}
            </a-select-option>
          </a-select>
        </a-form-item>

        <!-- 规则编号 -->
        <a-form-item label="规则编号" name="rule_code" required>
          <a-input
            v-model:value="formData.rule_code"
            placeholder="例如：COMP_001"
            :disabled="createMode === 'override' && !!formData.base_rule_id"
          />
        </a-form-item>

        <!-- 规则名称 -->
        <a-form-item label="规则名称" name="name" required>
          <a-input
            v-model:value="formData.name"
            placeholder="输入规则名称"
          />
        </a-form-item>

        <!-- 规则描述 -->
        <a-form-item label="规则描述" name="description">
          <a-textarea
            v-model:value="formData.description"
            placeholder="输入规则描述"
            :rows="3"
          />
        </a-form-item>

        <!-- 规则分类 -->
        <a-form-item label="规则分类" name="category" required>
          <a-select v-model:value="formData.category" placeholder="选择规则分类">
            <a-select-option value="completeness">完整性</a-select-option>
            <a-select-option value="accuracy">准确性</a-select-option>
            <a-select-option value="timeliness">及时性</a-select-option>
            <a-select-option value="consistency">一致性</a-select-option>
            <a-select-option value="rationality">合理性</a-select-option>
          </a-select>
        </a-form-item>

        <!-- 严重程度 -->
        <a-form-item label="严重程度" name="severity" required>
          <a-select v-model:value="formData.severity" placeholder="选择严重程度">
            <a-select-option value="critical">严重</a-select-option>
            <a-select-option value="major">重要</a-select-option>
            <a-select-option value="minor">一般</a-select-option>
          </a-select>
        </a-form-item>

        <!-- 覆盖行为 -->
        <a-form-item label="覆盖行为" name="override_action">
          <a-radio-group v-model:value="formData.override_action">
            <a-radio value="override">覆盖配置</a-radio>
            <a-radio value="disable">禁用规则</a-radio>
          </a-radio-group>
        </a-form-item>

        <!-- 优先级 -->
        <a-form-item label="优先级" name="priority">
          <a-input-number
            v-model:value="formData.priority"
            :min="0"
            :max="100"
            placeholder="0-100，数字越大优先级越高"
            class="w-full"
          />
        </a-form-item>

        <!-- 生效期 -->
        <a-form-item label="生效期">
          <a-range-picker
            v-model:value="effectiveDateRange"
            show-time
            format="YYYY-MM-DD HH:mm:ss"
            class="w-full"
          />
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- 变更历史对话框 -->
    <a-modal
      v-model:open="historyModalVisible"
      title="变更历史"
      width="900px"
      :footer="null"
    >
      <a-timeline mode="left">
        <a-timeline-item
          v-for="log in changeLogs"
          :key="log.id"
          :color="getActionColor(log.action)"
        >
          <template #dot>
            <ClockCircleOutlined style="font-size: 16px" />
          </template>
          <div class="mb-2">
            <div class="flex items-center justify-between">
              <span class="font-medium">{{ getActionText(log.action) }}</span>
              <span class="text-xs text-gray-500">
                {{ formatDateTime(log.created_at) }}
              </span>
            </div>
            <div class="text-sm text-gray-600 mt-1">
              操作人：{{ log.actor_name || log.actor_id }}
              <span v-if="log.actor_role" class="ml-2">
                ({{ log.actor_role }})
              </span>
            </div>
            <div v-if="log.reason" class="text-sm text-gray-500 mt-1">
              原因：{{ log.reason }}
            </div>
          </div>
        </a-timeline-item>
      </a-timeline>

      <a-pagination
        v-model:current="historyPagination.current"
        v-model:page-size="historyPagination.pageSize"
        :total="historyPagination.total"
        :show-total="(total) => `共 ${total} 条`"
        @change="loadChangeHistory"
        size="small"
        class="mt-4 text-center"
      />
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import type { TableColumnsType, TablePaginationConfig } from 'ant-design-vue'
import dayjs, { Dayjs } from 'dayjs'
import {
  ApartmentOutlined,
  ReloadOutlined,
  PlusOutlined,
  ClockCircleOutlined,
} from '@ant-design/icons-vue'
import {
  departmentQCRulesService,
  type DepartmentRule,
  type DepartmentRuleCreate,
  type DepartmentRuleUpdate,
  type RuleChangeLog,
  RuleStatus,
  OverrideAction,
} from '@/services/department-qc-rules-service'
import { RulesService } from '@/services/rules-service'

// ============================================================================
// 状态定义
// ============================================================================

const loading = ref(false)
const rules = ref<DepartmentRule[]>([])
const departments = ref<any[]>([])
const globalRules = ref<any[]>([])

// 筛选条件
const filters = reactive({
  department_id: undefined as string | undefined,
  status_filter: undefined as string | undefined,
  override_action: undefined as string | undefined,
  keyword: undefined as string | undefined,
})

// 分页
const pagination = reactive({
  current: 1,
  pageSize: 20,
  total: 0,
  showSizeChanger: true,
  showQuickJumper: true,
  showTotal: (total: number) => `共 ${total} 条`,
})

// 模态框
const modalVisible = ref(false)
const modalLoading = ref(false)
const modalTitle = ref('')
const isCreateMode = ref(true)
const createMode = ref<'override' | 'new'>('new')

// 表单
const formRef = ref()
const formData = reactive<any>({
  department_id: undefined,
  base_rule_id: undefined,
  rule_code: '',
  name: '',
  description: '',
  category: '',
  severity: '',
  override_action: OverrideAction.OVERRIDE,
  priority: 0,
  check_logic: {},
  scoring_config: {},
  applicable_documents: [],
})

const effectiveDateRange = ref<[Dayjs, Dayjs] | null>(null)

const formRules = {
  department_id: [{ required: true, message: '请选择科室' }],
  rule_code: [{ required: true, message: '请输入规则编号' }],
  name: [{ required: true, message: '请输入规则名称' }],
  category: [{ required: true, message: '请选择规则分类' }],
  severity: [{ required: true, message: '请选择严重程度' }],
}

// 变更历史
const historyModalVisible = ref(false)
const changeLogs = ref<RuleChangeLog[]>([])
const currentRuleId = ref<string>('')
const historyPagination = reactive({
  current: 1,
  pageSize: 10,
  total: 0,
})

// ============================================================================
// 表格列定义
// ============================================================================

const columns: TableColumnsType = [
  {
    title: '规则编号',
    key: 'rule_code',
    dataIndex: 'rule_code',
    width: 150,
  },
  {
    title: '规则名称',
    key: 'name',
    dataIndex: 'name',
    width: 250,
  },
  {
    title: '科室',
    key: 'department',
    dataIndex: 'department_id',
    width: 120,
  },
  {
    title: '状态',
    key: 'status',
    dataIndex: 'status',
    width: 100,
  },
  {
    title: '覆盖行为',
    key: 'override_action',
    dataIndex: 'override_action',
    width: 120,
  },
  {
    title: '优先级',
    key: 'priority',
    dataIndex: 'priority',
    width: 80,
    align: 'center',
  },
  {
    title: '操作',
    key: 'actions',
    width: 280,
    fixed: 'right',
  },
]

// ============================================================================
// 计算属性和辅助函数
// ============================================================================

const getDepartmentName = (departmentId?: string) => {
  if (!departmentId) return '-'
  const dept = departments.value.find((d) => d.id === departmentId)
  return dept?.name || departmentId
}

const getStatusColor = (status: string) => {
  const colorMap: Record<string, string> = {
    draft: 'orange',
    published: 'green',
    archived: 'gray',
  }
  return colorMap[status] || 'default'
}

const getStatusText = (status: string) => {
  const textMap: Record<string, string> = {
    draft: '草稿',
    published: '已发布',
    archived: '已归档',
  }
  return textMap[status] || status
}

const getActionColor = (action: string) => {
  const colorMap: Record<string, string> = {
    create: 'green',
    update: 'blue',
    delete: 'red',
    publish: 'purple',
    archive: 'gray',
  }
  return colorMap[action] || 'blue'
}

const getActionText = (action: string) => {
  const textMap: Record<string, string> = {
    create: '创建',
    update: '更新',
    delete: '删除',
    publish: '发布',
    archive: '归档',
    enable: '启用',
    disable: '禁用',
  }
  return textMap[action] || action
}

const formatDateTime = (dateStr: string) => {
  return dayjs(dateStr).format('YYYY-MM-DD HH:mm:ss')
}

const filterDepartmentOption = (input: string, option: any) => {
  return option.children[0].children.toLowerCase().includes(input.toLowerCase())
}

const filterRuleOption = (input: string, option: any) => {
  return option.children[0].children.toLowerCase().includes(input.toLowerCase())
}

// ============================================================================
// 数据加载
// ============================================================================

const loadDepartments = async () => {
  try {
    // 这里需要调用科室列表 API
    // 暂时使用模拟数据
    departments.value = [
      { id: '1', name: '心内科' },
      { id: '2', name: '外科' },
      { id: '3', name: '儿科' },
      { id: '4', name: '妇产科' },
    ]
  } catch (error) {
    console.error('加载科室列表失败:', error)
  }
}

const loadGlobalRules = async () => {
  try {
    const allRules = await RulesService.getAllRules()
    globalRules.value = allRules.filter((rule: any) => rule.scope === 'global')
  } catch (error) {
    console.error('加载全局规则失败:', error)
  }
}

const loadRules = async () => {
  loading.value = true
  try {
    const result = await departmentQCRulesService.listDepartmentRules({
      department_id: filters.department_id,
      status_filter: filters.status_filter,
      override_action: filters.override_action,
      keyword: filters.keyword,
      page: pagination.current,
      limit: pagination.pageSize,
    })

    rules.value = result.items
    pagination.total = result.total
  } catch (error) {
    console.error('加载规则列表失败:', error)
    message.error('加载规则列表失败')
  } finally {
    loading.value = false
  }
}

const refreshRules = () => {
  loadRules()
}

// ============================================================================
// 事件处理
// ============================================================================

const handleFilterChange = () => {
  pagination.current = 1
  loadRules()
}

const handleTableChange = (pag: TablePaginationConfig) => {
  pagination.current = pag.current || 1
  pagination.pageSize = pag.pageSize || 20
  loadRules()
}

// ============================================================================
// 模态框操作
// ============================================================================

const showCreateModal = () => {
  isCreateMode.value = true
  createMode.value = 'new'
  modalTitle.value = '新增科室规则'
  resetFormData()
  modalVisible.value = true
}

const viewRule = (record: DepartmentRule) => {
  // TODO: 实现查看规则详情
  message.info('查看规则详情功能开发中')
}

const editRule = (record: DepartmentRule) => {
  isCreateMode.value = false
  modalTitle.value = '编辑科室规则'

  // 填充表单数据
  Object.assign(formData, {
    id: record.id,
    department_id: record.department_id,
    rule_code: record.rule_code,
    name: record.name,
    description: record.description,
    category: record.category,
    severity: record.severity,
    override_action: record.override_action,
    priority: record.priority,
    check_logic: record.check_logic || {},
    scoring_config: record.scoring_config || {},
    applicable_documents: record.applicable_documents || [],
  })

  // 设置生效期
  if (record.effective_from && record.effective_to) {
    effectiveDateRange.value = [
      dayjs(record.effective_from),
      dayjs(record.effective_to),
    ]
  }

  modalVisible.value = true
}

const publishRule = async (record: DepartmentRule) => {
  try {
    await departmentQCRulesService.publishDepartmentRule(record.id, {
      approved_by: 'current_user', // TODO: 从用户上下文获取
      reason: '发布规则',
    })
    message.success('规则发布成功')
    loadRules()
  } catch (error) {
    console.error('发布规则失败:', error)
  }
}

const deleteRule = async (record: DepartmentRule) => {
  try {
    await departmentQCRulesService.deleteDepartmentRule(record.id)
    message.success('规则删除成功')
    loadRules()
  } catch (error) {
    console.error('删除规则失败:', error)
  }
}

const viewHistory = async (record: DepartmentRule) => {
  currentRuleId.value = record.id
  historyModalVisible.value = true
  historyPagination.current = 1
  await loadChangeHistory()
}

const loadChangeHistory = async () => {
  try {
    const result = await departmentQCRulesService.getRuleChangeHistory(
      currentRuleId.value,
      historyPagination.current,
      historyPagination.pageSize
    )
    changeLogs.value = result.items
    historyPagination.total = result.total
  } catch (error) {
    console.error('加载变更历史失败:', error)
    message.error('加载变更历史失败')
  }
}

const handleCreateModeChange = () => {
  if (createMode.value === 'new') {
    formData.base_rule_id = undefined
    formData.rule_code = ''
    formData.name = ''
    formData.description = ''
  }
}

const handleBaseRuleChange = (ruleId: string) => {
  const baseRule = globalRules.value.find((r) => r.id === ruleId)
  if (baseRule) {
    // 自动填充基础规则的信息
    formData.rule_code = baseRule.rule_code
    formData.name = `${baseRule.name} (科室定制)`
    formData.description = baseRule.description
    formData.category = baseRule.category
    formData.severity = baseRule.severity
    formData.check_logic = baseRule.check_logic || {}
    formData.scoring_config = baseRule.scoring_config || {}
    formData.applicable_documents = baseRule.applicable_documents || []
  }
}

const handleModalOk = async () => {
  try {
    await formRef.value.validate()
    modalLoading.value = true

    // 准备提交数据
    const submitData: any = {
      department_id: formData.department_id,
      rule_code: formData.rule_code,
      name: formData.name,
      description: formData.description,
      category: formData.category,
      severity: formData.severity,
      override_action: formData.override_action,
      priority: formData.priority,
      check_logic: formData.check_logic,
      scoring_config: formData.scoring_config,
      applicable_documents: formData.applicable_documents,
    }

    // 添加生效期
    if (effectiveDateRange.value) {
      submitData.effective_from = effectiveDateRange.value[0].toISOString()
      submitData.effective_to = effectiveDateRange.value[1].toISOString()
    }

    // 如果是覆盖模式，添加 base_rule_id
    if (isCreateMode.value && createMode.value === 'override' && formData.base_rule_id) {
      submitData.base_rule_id = formData.base_rule_id
    }

    if (isCreateMode.value) {
      await departmentQCRulesService.createDepartmentRule(submitData)
      message.success('规则创建成功')
    } else {
      await departmentQCRulesService.updateDepartmentRule(formData.id, submitData)
      message.success('规则更新成功')
    }

    modalVisible.value = false
    loadRules()
  } catch (error) {
    console.error('保存规则失败:', error)
  } finally {
    modalLoading.value = false
  }
}

const handleModalCancel = () => {
  modalVisible.value = false
  resetFormData()
}

const resetFormData = () => {
  Object.assign(formData, {
    id: undefined,
    department_id: undefined,
    base_rule_id: undefined,
    rule_code: '',
    name: '',
    description: '',
    category: '',
    severity: '',
    override_action: OverrideAction.OVERRIDE,
    priority: 0,
    check_logic: {},
    scoring_config: {},
    applicable_documents: [],
  })
  effectiveDateRange.value = null
  formRef.value?.resetFields()
}

// ============================================================================
// 组件挂载
// ============================================================================

onMounted(() => {
  loadDepartments()
  loadGlobalRules()
  loadRules()
})
</script>

<style scoped>
.page-container {
  max-width: 1400px;
  margin: 0 auto;
}
</style>

