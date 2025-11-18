<template>
  <div>
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
      <div class="flex justify-between items-center mb-3">
        <h3 class="text-sm font-semibold text-gray-900">科室规则列表</h3>
        <a-space>
          <a-button
            @click="refreshRules"
            :loading="loading"
            size="small"
          >
            <template #icon><ReloadOutlined /></template>
            刷新
          </a-button>
          <a-button
            type="primary"
            @click="showCreateModal"
            size="small"
          >
            <template #icon><PlusOutlined /></template>
            新增科室规则
          </a-button>
        </a-space>
      </div>

      <a-table
        :columns="columns"
        :data-source="rules"
        :loading="loading"
        :pagination="pagination"
        @change="handleTableChange"
        :scroll="{ x: 1000 }"
        size="small"
        row-key="id"
        class="rules-table"
      >
        <template #bodyCell="{ column, record, index }">
          <!-- 编号 -->
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
            <div class="font-medium text-gray-900">
              <div class="rule-name">{{ record.name }}</div>
              <div class="text-xs text-gray-500 mt-0.5" v-if="record.description">
                {{ record.description }}
              </div>
              <div class="mt-1">
                <a-tag v-if="record.department_id" color="green" class="text-xs mr-1">
                  {{ getDepartmentName(record.department_id) }}
                </a-tag>
                <a-tag :color="getStatusColor(record.status)" class="text-xs">
                  {{ getStatusText(record.status) }}
                </a-tag>
              </div>
            </div>
          </template>

          <!-- 分类 -->
          <template v-else-if="column.key === 'category'">
            <a-tag color="geekblue" class="text-xs">
              {{ getCategoryText(record.category) }}
            </a-tag>
          </template>

          <!-- 缺陷级别（映射自 severity） -->
          <template v-else-if="column.key === 'severity'">
            <a-tag :color="getSeverityColor(record.severity)" class="text-xs">
              {{ getSeverityText(record.severity) }}
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
            <a-select-option value="consistency">一致性</a-select-option>
            <a-select-option value="rationality">合理性</a-select-option>
            <a-select-option value="timeliness">及时性</a-select-option>
          </a-select>
        </a-form-item>

        <!-- 严重程度 -->
        <a-form-item label="严重程度" name="severity" required>
          <a-select v-model:value="formData.severity" placeholder="选择严重程度">
            <a-select-option value="critical">严重</a-select-option>
            <a-select-option value="major">重要</a-select-option>
            <a-select-option value="minor">轻微</a-select-option>
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
            placeholder="0-100，数值越大优先级越高"
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
      title="规则变更历史"
      width="900px"
      :footer="null"
    >
      <a-table
        :columns="historyColumns"
        :data-source="changeLogs"
        :pagination="{
          current: historyPagination.current,
          pageSize: historyPagination.pageSize,
          total: historyPagination.total,
          onChange: handleHistoryPageChange,
        }"
        size="small"
        row-key="id"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'action'">
            <a-tag :color="getActionColor(record.action)" class="text-xs">
              {{ getActionText(record.action) }}
            </a-tag>
          </template>
          <template v-else-if="column.key === 'created_at'">
            {{ formatDateTime(record.created_at) }}
          </template>
        </template>
      </a-table>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { onMounted, type TableColumnsType } from 'vue'
import { ReloadOutlined, PlusOutlined } from '@ant-design/icons-vue'
import { useDepartmentRules } from '@/composables/useDepartmentRules'

// 使用 composable
const {
  loading,
  rules,
  departments,
  globalRules,
  filters,
  pagination,
  modalVisible,
  modalLoading,
  modalTitle,
  isCreateMode,
  createMode,
  formRef,
  formData,
  formRules,
  effectiveDateRange,
  historyModalVisible,
  changeLogs,
  historyPagination,
  getDepartmentName,
  getStatusColor,
  getStatusText,
  getActionColor,
  getActionText,
  formatDateTime,
  filterDepartmentOption,
  filterRuleOption,
  refreshRules,
  handleFilterChange,
  handleTableChange,
  showCreateModal,
  editRule,
  viewRule,
  publishRule,
  deleteRule,
  viewHistory,
  handleHistoryPageChange,
  handleCreateModeChange,
  handleBaseRuleChange,
  handleModalOk,
  handleModalCancel,
  initialize,
} = useDepartmentRules()

// 表格列定义（尽量对齐泸县33条质控规则的列表风格）
const columns: TableColumnsType = [
  {
    title: () => '序号',
    key: 'index',
    width: 60,
    fixed: 'left',
    customRender: ({ index }) => {
      const page = pagination.current || 1
      const pageSize = pagination.pageSize || 20
      return (page - 1) * pageSize + (index as number) + 1
    },
  },
  {
    title: () => '编号',
    key: 'rule_code',
    dataIndex: 'rule_code',
    width: 120,
    fixed: 'left',
  },
  {
    title: () => '规则名称',
    key: 'name',
    dataIndex: 'name',
    width: 320,
  },
  {
    title: () => '分类',
    key: 'category',
    dataIndex: 'category',
    width: 120,
  },
  {
    title: () => '缺陷级别',
    key: 'severity',
    dataIndex: 'severity',
    width: 120,
  },
  {
    title: () => '操作',
    key: 'actions',
    width: 280,
    fixed: 'right',
  },
]

const historyColumns: TableColumnsType = [
  {
    title: '操作',
    key: 'action',
    dataIndex: 'action',
    width: 100,
  },
  {
    title: '操作人',
    key: 'changed_by',
    dataIndex: 'changed_by',
    width: 120,
  },
  {
    title: '变更原因',
    key: 'reason',
    dataIndex: 'reason',
    width: 200,
  },
  {
    title: '变更时间',
    key: 'created_at',
    dataIndex: 'created_at',
    width: 180,
  },
]

// 分类中文显示
const getCategoryText = (category: string | undefined) => {
  const map: Record<string, string> = {
    completeness: '完整性',
    consistency: '一致性',
    rationality: '合理性',
    timeliness: '及时性',
  }
  if (!category) return '-'
  const key = String(category).toLowerCase()
  return map[key] || category
}

// 严重程度中文及颜色
const getSeverityText = (severity: string | undefined) => {
  const map: Record<string, string> = {
    critical: '严重',
    major: '重要',
    minor: '轻微',
  }
  if (!severity) return '-'
  const key = String(severity).toLowerCase()
  return map[key] || severity
}

const getSeverityColor = (severity: string | undefined) => {
  const map: Record<string, string> = {
    critical: 'red',
    major: 'orange',
    minor: 'green',
  }
  if (!severity) return 'default'
  const key = String(severity).toLowerCase()
  return map[key] || 'default'
}

// 初始化
onMounted(() => {
  initialize()
})
</script>
