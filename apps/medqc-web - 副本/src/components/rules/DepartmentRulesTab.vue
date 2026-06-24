<template>
  <div class="space-y-6">
    <!-- 筛选区域 -->
    <div
      class="bg-white rounded-2xl shadow-[0_4px_20px_-4px_rgba(0,0,0,0.05)] border border-slate-100 p-5"
    >
      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div class="relative group">
          <label
            class="block text-[11px] font-semibold text-slate-400 uppercase tracking-wider mb-1.5"
          >科室</label>
          <a-select
            v-model:value="filters.department_id"
            placeholder="选择科室"
            allow-clear
            show-search
            :filter-option="filterDepartmentOption"
            class="w-full dept-select"
            @change="handleFilterChange"
          >
            <a-select-option
              v-for="dept in departments"
              :key="dept.id"
              :value="dept.id"
            >
              {{ dept.name }}
            </a-select-option>
          </a-select>
        </div>
        <div>
          <label
            class="block text-[11px] font-semibold text-slate-400 uppercase tracking-wider mb-1.5"
          >规则状态</label>
          <a-select
            v-model:value="filters.status_filter"
            placeholder="全部状态"
            allow-clear
            class="w-full dept-select"
            @change="handleFilterChange"
          >
            <a-select-option value="draft">
              草稿
            </a-select-option>
            <a-select-option value="published">
              已发布
            </a-select-option>
            <a-select-option value="archived">
              已归档
            </a-select-option>
          </a-select>
        </div>
        <div>
          <label
            class="block text-[11px] font-semibold text-slate-400 uppercase tracking-wider mb-1.5"
          >覆盖行为</label>
          <a-select
            v-model:value="filters.override_action"
            placeholder="全部类型"
            allow-clear
            class="w-full dept-select"
            @change="handleFilterChange"
          >
            <a-select-option value="override">
              覆盖配置
            </a-select-option>
            <a-select-option value="disable">
              禁用规则
            </a-select-option>
          </a-select>
        </div>
        <div>
          <label
            class="block text-[11px] font-semibold text-slate-400 uppercase tracking-wider mb-1.5"
          >搜索</label>
          <div class="relative">
            <SearchOutlined
              class="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 text-sm pointer-events-none"
            />
            <input
              v-model="filters.keyword"
              type="text"
              placeholder="搜索规则编号、名称..."
              class="w-full pl-9 pr-3 py-[7px] bg-white border border-slate-200 rounded-lg text-sm text-slate-700 outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/10 transition-all"
              @keyup.enter="handleFilterChange"
            >
          </div>
        </div>
      </div>
    </div>

    <!-- 规则列表 -->
    <div
      class="bg-white rounded-2xl shadow-[0_4px_20px_-4px_rgba(0,0,0,0.05)] border border-slate-100 overflow-hidden"
    >
      <!-- 列表头部 -->
      <div class="flex justify-between items-center px-6 py-4 border-b border-slate-100">
        <div class="flex items-center gap-3">
          <h3 class="text-slate-700 font-semibold text-sm">
            科室规则列表
          </h3>
          <span
            v-if="rules.length"
            class="text-xs text-slate-400 bg-slate-50 px-2 py-0.5 rounded-full border border-slate-100"
          >
            {{ rules.length }} 条
          </span>
        </div>
        <div class="flex gap-3">
          <button
            class="inline-flex items-center px-3 py-2 rounded-lg text-sm font-medium text-slate-500 hover:text-blue-600 hover:bg-blue-50 transition-colors"
            @click="refreshRules"
          >
            <ReloadOutlined
              :class="{ 'animate-spin': loading }"
              class="mr-1.5"
            />
            刷新
          </button>
          <button
            class="inline-flex items-center px-4 py-2 rounded-lg text-sm font-semibold text-white bg-gradient-to-r from-indigo-500 to-blue-500 shadow-md shadow-blue-500/20 hover:shadow-lg hover:shadow-blue-500/30 hover:-translate-y-0.5 transition-all"
            @click="showCreateModal"
          >
            <PlusOutlined class="mr-1.5" />
            新增科室规则
          </button>
        </div>
      </div>

      <!-- 空状态 -->
      <div
        v-if="!loading && rules.length === 0"
        class="py-20 px-8"
      >
        <div class="max-w-md mx-auto text-center">
          <div
            class="w-20 h-20 mx-auto mb-6 rounded-2xl bg-gradient-to-br from-slate-50 to-blue-50 border border-slate-100 flex items-center justify-center"
          >
            <ApartmentOutlined class="text-3xl text-blue-300" />
          </div>
          <h4 class="text-lg font-bold text-slate-700 mb-2">
            {{ filters.department_id ? '该科室暂无自定义规则' : '请先选择一个科室' }}
          </h4>
          <p class="text-sm text-slate-400 leading-relaxed mb-6">
            {{
              filters.department_id
                ? '科室规则允许您针对特定科室覆盖全局规则参数，或禁用不适用的规则。点击下方按钮开始创建。'
                : '从上方筛选区域选择一个科室，查看或管理该科室的自定义质控规则。'
            }}
          </p>
          <button
            v-if="filters.department_id"
            class="inline-flex items-center px-5 py-2.5 rounded-xl text-sm font-semibold text-white bg-gradient-to-r from-indigo-500 to-blue-500 shadow-md shadow-blue-500/20 hover:shadow-lg transition-all"
            @click="showCreateModal"
          >
            <PlusOutlined class="mr-2" />
            创建第一条科室规则
          </button>
          <button
            v-else
            class="inline-flex items-center px-5 py-2.5 rounded-xl text-sm font-semibold text-blue-600 bg-blue-50 border border-blue-100 hover:bg-blue-100 transition-all"
            @click="focusDeptSelect"
          >
            <ApartmentOutlined class="mr-2" />
            选择科室
          </button>
        </div>
      </div>

      <!-- 数据表格 -->
      <a-table
        v-else
        :columns="columns"
        :data-source="rules"
        :loading="loading"
        :pagination="pagination"
        :scroll="{ x: 1000 }"
        row-key="id"
        class="modern-table"
        @change="handleTableChange"
      >
        <template #bodyCell="{ column, record }">
          <!-- 编号 -->
          <template v-if="column.key === 'rule_code'">
            <div class="flex items-center gap-2">
              <span
                class="font-mono text-slate-600 bg-slate-100 px-2 py-1 rounded text-xs font-semibold select-all border border-slate-200"
              >
                {{ record.rule_code }}
              </span>
              <span
                v-if="record.parent_rule_id"
                class="px-1.5 py-0.5 bg-amber-50 text-amber-600 border border-amber-100 rounded text-[10px] font-medium"
              >
                覆盖
              </span>
            </div>
          </template>

          <!-- 规则名称 -->
          <template v-else-if="column.key === 'name'">
            <div class="py-2">
              <div class="text-slate-800 font-semibold text-sm leading-snug mb-1">
                {{ record.name }}
              </div>
              <div class="flex items-center gap-2">
                <span
                  v-if="record.department_id"
                  class="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-emerald-50 text-emerald-600 border border-emerald-100"
                >
                  {{ getDepartmentName(record.department_id) }}
                </span>
                <span
                  class="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium"
                  :class="getStatusClass(record.status)"
                >
                  {{ getStatusText(record.status) }}
                </span>
                <span
                  v-if="record.description"
                  class="text-slate-400 text-xs truncate"
                  :title="record.description"
                >
                  {{ record.description }}
                </span>
              </div>
            </div>
          </template>

          <!-- 分类 -->
          <template v-else-if="column.key === 'category'">
            <span
              class="inline-flex items-center px-2.5 py-1 rounded-md text-xs font-semibold bg-indigo-50 text-indigo-600 border border-indigo-100"
            >
              {{ getCategoryText(record.category) }}
            </span>
          </template>

          <!-- 缺陷级别 -->
          <template v-else-if="column.key === 'severity'">
            <span
              class="inline-flex items-center px-2.5 py-1 rounded-md text-xs font-semibold"
              :class="getSeverityClass(record.severity)"
            >
              {{ getSeverityText(record.severity) }}
            </span>
          </template>

          <!-- 操作 -->
          <template v-else-if="column.key === 'actions'">
            <div class="flex items-center justify-end gap-2">
              <a-tooltip title="查看详情">
                <button
                  class="p-1.5 rounded-lg text-slate-400 bg-slate-50 hover:text-blue-600 hover:bg-blue-50 border border-transparent hover:border-blue-100 transition-all"
                  @click="viewRule(record as DepartmentRule)"
                >
                  <EyeOutlined />
                </button>
              </a-tooltip>
              <a-tooltip title="编辑">
                <button
                  class="p-1.5 rounded-lg text-slate-400 bg-slate-50 hover:text-indigo-600 hover:bg-indigo-50 border border-transparent hover:border-indigo-100 transition-all"
                  @click="editRule(record as DepartmentRule)"
                >
                  <EditOutlined />
                </button>
              </a-tooltip>
              <button
                v-if="record.status === 'draft'"
                class="px-2.5 py-1 rounded-lg text-xs font-semibold text-emerald-600 bg-emerald-50 border border-emerald-100 hover:bg-emerald-600 hover:text-white hover:border-emerald-600 transition-all"
                @click="publishRule(record as DepartmentRule)"
              >
                发布
              </button>
              <a-tooltip title="变更历史">
                <button
                  class="p-1.5 rounded-lg text-slate-400 bg-slate-50 hover:text-amber-600 hover:bg-amber-50 border border-transparent hover:border-amber-100 transition-all"
                  @click="viewHistory(record as DepartmentRule)"
                >
                  <HistoryOutlined />
                </button>
              </a-tooltip>
              <a-popconfirm
                title="确定要删除这条规则吗？"
                ok-text="确定"
                cancel-text="取消"
                @confirm="deleteRule(record as DepartmentRule)"
              >
                <a-tooltip title="删除">
                  <button
                    class="p-1.5 rounded-lg text-slate-400 bg-slate-50 hover:text-red-600 hover:bg-red-50 border border-transparent hover:border-red-100 transition-all"
                  >
                    <DeleteOutlined />
                  </button>
                </a-tooltip>
              </a-popconfirm>
            </div>
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
      centered
      class="modern-modal"
      @ok="handleModalOk"
      @cancel="handleModalCancel"
    >
      <a-form
        ref="formRef"
        :model="formData"
        :rules="typedFormRules"
        :label-col="{ span: 6 }"
        :wrapper-col="{ span: 18 }"
      >
        <!-- 创建模式选择 -->
        <a-form-item
          v-if="isCreateMode"
          label="创建模式"
        >
          <a-radio-group
            v-model:value="createMode"
            @change="handleCreateModeChange"
          >
            <a-radio value="override">
              基于全局规则创建
            </a-radio>
            <a-radio value="new">
              全新创建
            </a-radio>
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
        <a-form-item
          label="科室"
          name="department_id"
          required
        >
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

        <a-form-item
          label="规则编号"
          name="rule_code"
          required
        >
          <a-input
            v-model:value="formData.rule_code"
            placeholder="例如：COMP_001"
            :disabled="createMode === 'override' && !!formData.base_rule_id"
          />
        </a-form-item>

        <a-form-item
          label="规则名称"
          name="name"
          required
        >
          <a-input
            v-model:value="formData.name"
            placeholder="输入规则名称"
          />
        </a-form-item>

        <a-form-item
          label="规则描述"
          name="description"
        >
          <a-textarea
            v-model:value="formData.description"
            placeholder="输入规则描述"
            :rows="3"
          />
        </a-form-item>

        <a-form-item
          label="规则分类"
          name="category"
          required
        >
          <a-select
            v-model:value="formData.category"
            placeholder="选择规则分类"
          >
            <a-select-option value="completeness">
              完整性
            </a-select-option>
            <a-select-option value="consistency">
              一致性
            </a-select-option>
            <a-select-option value="rationality">
              合理性
            </a-select-option>
            <a-select-option value="timeliness">
              及时性
            </a-select-option>
          </a-select>
        </a-form-item>

        <a-form-item
          label="严重程度"
          name="severity"
          required
        >
          <a-select
            v-model:value="formData.severity"
            placeholder="选择严重程度"
          >
            <a-select-option value="critical">
              严重
            </a-select-option>
            <a-select-option value="major">
              重要
            </a-select-option>
            <a-select-option value="minor">
              轻微
            </a-select-option>
          </a-select>
        </a-form-item>

        <a-form-item
          label="覆盖行为"
          name="override_action"
        >
          <a-radio-group v-model:value="formData.override_action">
            <a-radio value="override">
              覆盖配置
            </a-radio>
            <a-radio value="disable">
              禁用规则
            </a-radio>
          </a-radio-group>
        </a-form-item>

        <a-form-item
          label="优先级"
          name="priority"
        >
          <a-input-number
            v-model:value="formData.priority"
            :min="0"
            :max="100"
            placeholder="0-100，数值越大优先级越高"
            class="w-full"
          />
        </a-form-item>

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
      centered
      class="modern-modal"
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
        class="modern-table"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'action'">
            <span
              class="inline-flex items-center px-2 py-0.5 rounded-md text-xs font-semibold"
              :class="getActionClass(record.action)"
            >
              {{ getActionText(record.action) }}
            </span>
          </template>
          <template v-else-if="column.key === 'created_at'">
            <span class="text-slate-500 text-xs">{{ formatDateTime(record.created_at) }}</span>
          </template>
        </template>
      </a-table>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import type { FormProps, TableColumnsType } from 'ant-design-vue'
import {
  ReloadOutlined,
  PlusOutlined,
  SearchOutlined,
  ApartmentOutlined,
  EyeOutlined,
  EditOutlined,
  DeleteOutlined,
  HistoryOutlined,
} from '@ant-design/icons-vue'
import { useDepartmentRules } from '@/composables/useDepartmentRules'
import type { DepartmentRule, RuleChangeLog } from '@/services/department-qc-rules-service'

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

const typedFormRules = formRules as FormProps['rules']

// 聚焦科室下拉框
const focusDeptSelect = () => {
  const selectEl = document.querySelector('.dept-select .ant-select-selector') as HTMLElement
  selectEl?.click()
}

// 表格列定义
const columns: TableColumnsType<DepartmentRule> = [
  {
    title: '序号',
    key: 'index',
    width: 60,
    fixed: 'left',
    align: 'center',
    customRender: ({ index }) => {
      const page = pagination.current || 1
      const pageSize = pagination.pageSize || 20
      return (page - 1) * pageSize + (index as number) + 1
    },
  },
  { title: '编号', key: 'rule_code', dataIndex: 'rule_code', width: 120, fixed: 'left' },
  { title: '规则名称', key: 'name', dataIndex: 'name', width: 360 },
  { title: '分类', key: 'category', dataIndex: 'category', width: 100 },
  { title: '缺陷级别', key: 'severity', dataIndex: 'severity', width: 100 },
  { title: '操作', key: 'actions', width: 220, fixed: 'right', align: 'right' },
]

const historyColumns: TableColumnsType<RuleChangeLog> = [
  { title: '操作', key: 'action', dataIndex: 'action', width: 100 },
  { title: '操作人', key: 'changed_by', dataIndex: 'changed_by', width: 120 },
  { title: '变更原因', key: 'reason', dataIndex: 'reason', width: 200 },
  { title: '变更时间', key: 'created_at', dataIndex: 'created_at', width: 180 },
]

// 样式映射
const getCategoryText = (category: string | undefined) => {
  const map: Record<string, string> = {
    completeness: '完整性',
    consistency: '一致性',
    rationality: '合理性',
    timeliness: '及时性',
  }
  return category ? map[category.toLowerCase()] || category : '-'
}

const getSeverityText = (severity: string | undefined) => {
  const map: Record<string, string> = { critical: '严重', major: '重要', minor: '轻微' }
  return severity ? map[severity.toLowerCase()] || severity : '-'
}

const getSeverityClass = (severity: string | undefined) => {
  const map: Record<string, string> = {
    critical: 'bg-rose-50 text-rose-700 border border-rose-100',
    major: 'bg-orange-50 text-orange-700 border border-orange-100',
    minor: 'bg-emerald-50 text-emerald-700 border border-emerald-100',
  }
  return severity
    ? map[severity.toLowerCase()] || 'bg-slate-50 text-slate-600 border border-slate-200'
    : 'bg-slate-50 text-slate-600 border border-slate-200'
}

const getStatusClass = (status: string | undefined) => {
  const map: Record<string, string> = {
    draft: 'bg-slate-100 text-slate-500 border border-slate-200',
    published: 'bg-emerald-50 text-emerald-600 border border-emerald-100',
    archived: 'bg-slate-100 text-slate-400 border border-slate-200',
  }
  return status
    ? map[status] || 'bg-slate-100 text-slate-500 border border-slate-200'
    : 'bg-slate-100 text-slate-500 border border-slate-200'
}

const getActionClass = (action: string | undefined) => {
  const map: Record<string, string> = {
    create: 'bg-blue-50 text-blue-600 border border-blue-100',
    update: 'bg-amber-50 text-amber-600 border border-amber-100',
    publish: 'bg-emerald-50 text-emerald-600 border border-emerald-100',
    delete: 'bg-red-50 text-red-600 border border-red-100',
  }
  return action
    ? map[action] || 'bg-slate-50 text-slate-600 border border-slate-200'
    : 'bg-slate-50 text-slate-600 border border-slate-200'
}

onMounted(() => {
  initialize()
})
</script>

<style scoped>
/* 统一表格样式 - 复用 SemanticRulesManager 的 modern-table 风格 */
.modern-table :deep(.ant-table-thead > tr > th) {
  background: #f8fafc;
  color: #475569;
  font-size: 0.8rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.025em;
  border-bottom: 1px solid #e2e8f0;
  padding: 1rem;
}

.modern-table :deep(.ant-table-tbody > tr > td) {
  padding: 1rem;
  border-bottom: 1px solid #f1f5f9;
  font-size: 0.875rem;
}

.modern-table :deep(.ant-table-tbody > tr:hover > td) {
  background: #f8fafc !important;
}

.modern-table :deep(.ant-table-tbody > tr:last-child > td) {
  border-bottom: none;
}

/* 选择器样式美化 */
.dept-select :deep(.ant-select-selector) {
  border-radius: 0.5rem !important;
  border-color: #e2e8f0 !important;
  transition: all 0.2s;
}

.dept-select :deep(.ant-select-selector:hover) {
  border-color: #94a3b8 !important;
}

.dept-select :deep(.ant-select-focused .ant-select-selector) {
  border-color: #3b82f6 !important;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1) !important;
}
</style>
