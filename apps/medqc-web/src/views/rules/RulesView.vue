<template>
  <div class="page-container min-h-screen bg-gray-50 p-4 lg:p-6">
    <!-- 页面头部 -->
    <div class="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-6">
      <div class="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
        <div class="flex-1">
          <div class="flex items-center space-x-3 mb-2">
            <div class="p-2 bg-blue-100 rounded-lg">
              <SettingOutlined class="text-xl text-blue-600" />
            </div>
            <h1 class="text-2xl lg:text-3xl font-bold text-gray-900">
              质控规则管理
            </h1>
          </div>
          <p class="text-gray-600 text-sm lg:text-base">
            统一管理传统质控规则和语义质控规则，支持规则创建、编辑、测试和版本管理
          </p>
        </div>
        <div class="flex flex-wrap gap-2" v-if="activeTab === 'traditional'">
          <a-button
            @click="refreshRules"
            :loading="loading"
            class="flex items-center space-x-2"
          >
            <template #icon><ReloadOutlined /></template>
            <span>刷新</span>
          </a-button>
          <a-button
            @click="importRules"
            class="flex items-center space-x-2"
          >
            <template #icon><ImportOutlined /></template>
            <span>导入规则</span>
          </a-button>
          <a-button
            type="primary"
            @click="showCreateModal"
            class="flex items-center space-x-2 bg-blue-600 hover:bg-blue-700"
          >
            <template #icon><PlusOutlined /></template>
            <span>新增规则</span>
          </a-button>
        </div>
      </div>
    </div>

    <!-- 标签页导航 -->
    <a-tabs
      v-model:activeKey="activeTab"
      type="card"
      class="rules-tabs"
      @change="handleTabChange"
    >
      <a-tab-pane key="semantic" tab="语义质控规则">
        <template #tab>
          <span>
            <BranchesOutlined />
            语义质控规则
          </span>
        </template>
      </a-tab-pane>
      <a-tab-pane key="traditional" tab="传统质控规则">
        <template #tab>
          <span>
            <SettingOutlined />
            传统质控规则
          </span>
        </template>
      </a-tab-pane>
    </a-tabs>

    <!-- 标签页内容 -->
    <div class="tab-content">
      <!-- 传统质控规则标签页 -->
      <div v-if="activeTab === 'traditional'">
        <!-- 统计卡片 -->
        <div class="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-6">
          <div class="flex items-center justify-between mb-4">
            <h2 class="text-lg font-semibold text-gray-900">规则统计</h2>
            <a-tag color="blue" class="px-3 py-1">
              传统规则模式
            </a-tag>
          </div>
          <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <div class="bg-gradient-to-br from-blue-50 to-blue-100 rounded-lg p-4 border border-blue-200">
              <a-statistic
                title="总规则数"
                :value="statistics.total"
                :value-style="{ color: '#1890ff', fontSize: '18px', fontWeight: '600' }"
              >
                <template #prefix>
                  <div class="p-2 bg-blue-500 rounded-lg inline-block">
                    <FileTextOutlined class="text-white text-lg" />
                  </div>
                </template>
              </a-statistic>
            </div>
            <div class="bg-gradient-to-br from-green-50 to-green-100 rounded-lg p-4 border border-green-200">
              <a-statistic
                title="激活规则"
                :value="statistics.active"
                :value-style="{ color: '#16a34a', fontSize: '18px', fontWeight: '600' }"
              >
                <template #prefix>
                  <div class="p-2 bg-green-500 rounded-lg inline-block">
                    <CheckCircleOutlined class="text-white text-lg" />
                  </div>
                </template>
              </a-statistic>
            </div>
            <div class="bg-gradient-to-br from-red-50 to-red-100 rounded-lg p-4 border border-red-200">
              <a-statistic
                title="严重规则"
                :value="statistics.critical"
                :value-style="{ color: '#dc2626', fontSize: '18px', fontWeight: '600' }"
              >
                <template #prefix>
                  <div class="p-2 bg-red-500 rounded-lg inline-block">
                    <ExclamationCircleOutlined class="text-white text-lg" />
                  </div>
                </template>
              </a-statistic>
            </div>
            <div class="bg-gradient-to-br from-purple-50 to-purple-100 rounded-lg p-4 border border-purple-200">
              <a-statistic
                title="规则分类"
                :value="statistics.categories"
                :value-style="{ color: '#9333ea', fontSize: '18px', fontWeight: '600' }"
              >
                <template #prefix>
                  <div class="p-2 bg-purple-500 rounded-lg inline-block">
                    <TagsOutlined class="text-white text-lg" />
                  </div>
                </template>
              </a-statistic>
            </div>
          </div>
        </div>

        <!-- 筛选和搜索 -->
        <div class="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-6">
          <div class="flex items-center justify-between mb-4">
            <h2 class="text-lg font-semibold text-gray-900">筛选条件</h2>
            <a-button
              size="small"
              @click="resetFilters"
              class="text-gray-500 hover:text-gray-700"
            >
              <template #icon><ClearOutlined /></template>
              清空筛选
            </a-button>
          </div>

          <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4 mb-4">
            <div class="space-y-2">
              <label class="text-sm font-medium text-gray-700">搜索</label>
              <a-input-search
                v-model:value="searchText"
                placeholder="搜索规则名称或描述"
                @search="handleSearch"
                allow-clear
                class="w-full"
              />
            </div>

            <div class="space-y-2">
              <label class="text-sm font-medium text-gray-700">文书类别</label>
              <a-select
                v-model:value="filterDocumentCategory"
                placeholder="选择文书类别"
                allowClear
                @change="handleFilter"
                class="w-full"
              >
                <a-select-option
                  v-for="option in documentCategoryOptions"
                  :key="option.value"
                  :value="option.value"
                >
                  <div class="flex items-center space-x-2">
                    <a-tag :color="option.color" class="text-xs">
                      {{ option.label }}
                    </a-tag>
                  </div>
                </a-select-option>
              </a-select>
            </div>

            <div class="space-y-2">
              <label class="text-sm font-medium text-gray-700">规则分类</label>
              <a-select
                v-model:value="filterCategory"
                placeholder="选择分类"
                allowClear
                @change="handleFilter"
                class="w-full"
              >
                <a-select-option value="completeness">完整性</a-select-option>
                <a-select-option value="consistency">一致性</a-select-option>
                <a-select-option value="rationality">合理性</a-select-option>
                <a-select-option value="timeliness">及时性</a-select-option>
              </a-select>
            </div>

            <div class="space-y-2">
              <label class="text-sm font-medium text-gray-700">严重程度</label>
              <a-select
                v-model:value="filterSeverity"
                placeholder="严重程度"
                allowClear
                @change="handleFilter"
                class="w-full"
              >
                <a-select-option value="critical">严重</a-select-option>
                <a-select-option value="major">重要</a-select-option>
                <a-select-option value="minor">轻微</a-select-option>
              </a-select>
            </div>

            <div class="space-y-2">
              <label class="text-sm font-medium text-gray-700">规则类型</label>
              <a-select
                v-model:value="filterType"
                placeholder="选择类型"
                allowClear
                @change="handleFilter"
                class="w-full"
              >
                <a-select-option value="logical">逻辑规则</a-select-option>
                <a-select-option value="semantic">语义规则</a-select-option>
                <a-select-option value="hybrid">混合规则</a-select-option>
              </a-select>
            </div>

            <div class="space-y-2">
              <label class="text-sm font-medium text-gray-700">状态</label>
              <a-select
                v-model:value="filterStatus"
                placeholder="选择状态"
                allowClear
                @change="handleFilter"
                class="w-full"
              >
                <a-select-option value="active">激活</a-select-option>
                <a-select-option value="inactive">停用</a-select-option>
              </a-select>
            </div>
          </div>

          <!-- 快速筛选标签 -->
          <div class="space-y-3">
            <!-- 文书类别快速筛选 -->
            <div class="flex items-center gap-3 flex-wrap">
              <span class="text-sm font-semibold text-gray-800">文书类别：</span>
              <div
                :class="['filter-tag', { 'filter-tag-active': !filterDocumentCategory }]"
                @click="clearDocumentCategoryFilter"
              >
                <span class="filter-tag-text">全部文书</span>
                <span class="filter-tag-count">({{ statistics.total }})</span>
              </div>
              <div
                v-for="option in documentCategoryOptions"
                :key="option.value"
                :class="['filter-tag', { 'filter-tag-active': filterDocumentCategory === option.value }]"
                @click="quickFilterDocumentCategory(option.value)"
                :style="{ borderColor: option.color }"
              >
                <span class="filter-tag-text">{{ option.label }}</span>
                <span class="filter-tag-count">({{ documentCategoryStats[option.value] || 0 }})</span>
              </div>
            </div>

            <!-- 其他快速筛选 -->
            <div class="flex items-center gap-3 flex-wrap">
              <span class="text-sm font-semibold text-gray-800">其他筛选：</span>
              <div
                :class="['filter-tag', { 'filter-tag-active': !filterCategory && !filterSeverity && !filterType && !filterStatus && !filterDocumentCategory }]"
                @click="clearAllFilters"
              >
                <span class="filter-tag-text">全部规则</span>
                <span class="filter-tag-count">({{ statistics.total }})</span>
              </div>
              <div
                :class="['filter-tag', { 'filter-tag-active': filterCategory === 'completeness' }]"
                @click="quickFilterCategory('completeness')"
              >
                <span class="filter-tag-text">完整性</span>
              </div>
              <div
                :class="['filter-tag', { 'filter-tag-active': filterCategory === 'consistency' }]"
                @click="quickFilterCategory('consistency')"
              >
                <span class="filter-tag-text">一致性</span>
              </div>
              <div
                :class="['filter-tag', { 'filter-tag-active': filterCategory === 'rationality' }]"
                @click="quickFilterCategory('rationality')"
              >
                <span class="filter-tag-text">合理性</span>
              </div>
              <div
                :class="['filter-tag filter-tag-danger', { 'filter-tag-danger-active': filterSeverity === 'critical' }]"
                @click="quickFilterSeverity('critical')"
              >
                <span class="filter-tag-text">严重缺陷</span>
              </div>
              <div
                :class="['filter-tag filter-tag-success', { 'filter-tag-success-active': filterStatus === 'active' }]"
                @click="quickFilterStatus('active')"
              >
                <span class="filter-tag-text">已激活</span>
              </div>
            </div>
          </div>

            <!-- 操作按钮 -->
            <div class="ml-auto flex items-center gap-2 flex-shrink-0">
              <a-button type="primary" @click="handleFilter" class="bg-blue-600 hover:bg-blue-700">
                <template #icon><SearchOutlined /></template>
                查询
              </a-button>
              <a-button @click="resetFilters">
                <template #icon><ClearOutlined /></template>
                重置
              </a-button>
            </div>
        </div>

        <!-- 批量操作区域 -->
        <div class="batch-actions" v-if="selectedRowKeys.length > 0">
          <a-alert
            :message="`已选择 ${selectedRowKeys.length} 条规则`"
            type="info"
            show-icon
            class="selection-alert mb-4"
          >
            <template #action>
              <a-space>
                <a-button size="small" @click="batchActivate(true)">
                  <template #icon><CheckCircleOutlined /></template>
                  批量激活
                </a-button>
                <a-button size="small" @click="batchActivate(false)">
                  <template #icon><StopOutlined /></template>
                  批量停用
                </a-button>
                <a-button size="small" danger @click="batchDelete">
                  <template #icon><DeleteOutlined /></template>
                  批量删除
                </a-button>
                <a-button size="small" @click="selectedRowKeys = []">
                  取消选择
                </a-button>
              </a-space>
            </template>
          </a-alert>
        </div>

        <!-- 规则列表 -->
        <div class="rules-table-section">
          <a-card class="table-card">
            <template #title>
              <div class="table-header">
                <span class="table-title">
                  <FileTextOutlined class="table-icon" />
                  规则列表
                </span>
                <span class="table-count">共 {{ statistics.total }} 条规则</span>
              </div>
            </template>
            <template #extra>
              <a-space>
                <a-button size="small" @click="exportRules">
                  <template #icon><ExportOutlined /></template>
                  导出规则
                </a-button>
              </a-space>
            </template>

            <a-table
            :columns="columns"
            :data-source="filteredRules"
            :loading="loading"
            :pagination="pagination"
            :row-selection="rowSelection"
            row-key="id"
            @change="handleTableChange"
            size="middle"
          >
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'rule_code'">
                <a-tag color="blue">{{ record.rule_code }}</a-tag>
              </template>

              <template v-else-if="column.key === 'source'">
                <div class="rule-source">
                  {{ record.name }}
                </div>
              </template>

              <template v-else-if="column.key === 'name'">
                <div class="rule-name">
                  {{ record.description }}
                </div>
              </template>

              <template v-else-if="column.key === 'category'">
                <a-tag :color="getCategoryColor(record.category)">
                  {{ getCategoryLabel(record.category) }}
                </a-tag>
              </template>

              <template v-else-if="column.key === 'severity'">
                <a-tag :color="getSeverityColor(record.severity)">
                  {{ getSeverityLabel(record.severity) }}
                </a-tag>
              </template>

              <template v-else-if="column.key === 'rule_type'">
                <a-tag :color="getTypeColor(record.rule_type)">
                  {{ getTypeLabel(record.rule_type) }}
                </a-tag>
              </template>

              <template v-else-if="column.key === 'is_active'">
                <a-switch
                  v-model:checked="record.is_active"
                  @change="(checked) => toggleRuleStatus(record, checked)"
                  :loading="record.updating"
                />
              </template>

              <template v-else-if="column.key === 'max_score'">
                <a-tag v-if="record.max_score === 0" color="red">单否</a-tag>
                <span v-else>{{ record.max_score }}分</span>
              </template>

              <template v-else-if="column.key === 'actions'">
                <a-space>
                  <a-button type="link" size="small" @click="viewRule(record)">
                    查看
                  </a-button>
                  <a-button type="link" size="small" @click="editRule(record)">
                    编辑
                  </a-button>
                  <a-button type="link" size="small" @click="testRule(record)">
                    测试
                  </a-button>
                  <a-popconfirm
                    title="确定要删除这条规则吗？"
                    @confirm="deleteRule(record)"
                  >
                    <a-button type="link" size="small" danger>
                      删除
                    </a-button>
                  </a-popconfirm>
                </a-space>
              </template>
            </template>
            </a-table>
          </a-card>
        </div>
        </div>

      <!-- 语义质控规则标签页 -->
      <div v-else-if="activeTab === 'semantic'">
        <SemanticRulesView />
      </div>
    </div>

    <!-- 创建/编辑规则模态框 -->
    <a-modal
      v-model:open="modalVisible"
      :title="modalTitle"
      width="800px"
      @ok="handleModalOk"
      @cancel="handleModalCancel"
      :confirm-loading="modalLoading"
    >
      <a-form
        ref="formRef"
        :model="formData"
        :rules="formRules"
        layout="vertical"
      >
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item label="规则编码" name="rule_code">
              <a-input v-model:value="formData.rule_code" placeholder="如: 1.1.1" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="规则名称" name="name">
              <a-input v-model:value="formData.name" placeholder="输入规则名称" />
            </a-form-item>
          </a-col>
        </a-row>

        <a-form-item label="规则描述" name="description">
          <a-textarea
            v-model:value="formData.description"
            placeholder="详细描述规则内容和检查要点"
            :rows="3"
          />
        </a-form-item>

        <a-row :gutter="16">
          <a-col :span="8">
            <a-form-item label="分类" name="category">
              <a-select v-model:value="formData.category" placeholder="选择分类">
                <a-select-option value="completeness">完整性</a-select-option>
                <a-select-option value="consistency">一致性</a-select-option>
                <a-select-option value="rationality">合理性</a-select-option>
                <a-select-option value="timeliness">及时性</a-select-option>
              </a-select>
            </a-form-item>
          </a-col>
          <a-col :span="8">
            <a-form-item label="严重程度" name="severity">
              <a-select v-model:value="formData.severity" placeholder="选择严重程度">
                <a-select-option value="critical">严重</a-select-option>
                <a-select-option value="major">重要</a-select-option>
                <a-select-option value="minor">轻微</a-select-option>
              </a-select>
            </a-form-item>
          </a-col>
          <a-col :span="8">
            <a-form-item label="规则类型" name="rule_type">
              <a-select v-model:value="formData.rule_type" placeholder="选择规则类型">
                <a-select-option value="objective">客观规则</a-select-option>
                <a-select-option value="subjective">主观规则</a-select-option>
                <a-select-option value="hybrid">混合规则</a-select-option>
              </a-select>
            </a-form-item>
          </a-col>
        </a-row>

        <a-row :gutter="16">
          <a-col :span="8">
            <a-form-item label="最大扣分" name="max_score">
              <a-input-number
                v-model:value="formData.max_score"
                :min="0"
                :max="100"
                placeholder="0表示单否"
                style="width: 100%"
              />
            </a-form-item>
          </a-col>
          <a-col :span="8">
            <a-form-item label="权重" name="weight">
              <a-input-number
                v-model:value="formData.weight"
                :min="0.1"
                :max="5.0"
                :step="0.1"
                placeholder="1.0"
                style="width: 100%"
              />
            </a-form-item>
          </a-col>
          <a-col :span="8">
            <a-form-item label="状态" name="is_active">
              <a-switch
                v-model:checked="formData.is_active"
                checked-children="激活"
                un-checked-children="停用"
              />
            </a-form-item>
          </a-col>
        </a-row>

        <a-form-item label="检查逻辑配置" name="check_logic">
          <a-textarea
            v-model:value="checkLogicText"
            placeholder="JSON格式的检查逻辑配置"
            :rows="4"
          />
        </a-form-item>

        <a-form-item label="提示模板" name="prompt_template">
          <a-textarea
            v-model:value="formData.prompt_template"
            placeholder="AI分析时使用的提示模板"
            :rows="6"
          />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, h, watch } from 'vue'
import { message } from 'ant-design-vue'
import type { TableColumnsType, TableProps } from 'ant-design-vue'
import {
  PlusOutlined,
  ReloadOutlined,
  ImportOutlined,
  ExportOutlined,
  DownOutlined,
  ClearOutlined,
  FileTextOutlined,
  CheckCircleOutlined,
  ExclamationCircleOutlined,
  TagsOutlined,
  SettingOutlined,
  BranchesOutlined,
  SearchOutlined,
  StopOutlined,
  DeleteOutlined
} from '@ant-design/icons-vue'
import SemanticRulesView from './SemanticRulesView.vue'
import { DocumentCategoryService } from '@/services/document-category-service'
import { DocumentCategory } from '@/types/medical'
import type { EnhancedQCRule, QCRuleFilterParams } from '@/types/quality-control'
// import { RulesService } from '@/services/rules-service'
// import { RulesValidator } from '@/utils/rules-validator'
// import { RULES_CONFIG } from '@/config/rules-config'

// 模拟配置
const RULES_CONFIG = {
  categories: {
    completeness: { label: '完整性', color: 'blue' },
    consistency: { label: '一致性', color: 'green' },
    rationality: { label: '合理性', color: 'orange' },
    timeliness: { label: '及时性', color: 'purple' }
  },
  severities: {
    critical: { label: '严重', color: 'red' },
    major: { label: '重要', color: 'orange' },
    minor: { label: '轻微', color: 'blue' }
  },
  types: {
    objective: { label: '客观规则', color: 'cyan' },
    subjective: { label: '主观规则', color: 'magenta' },
    hybrid: { label: '混合规则', color: 'geekblue' }
  }
}

// 接口定义
interface QCRule {
  id: string
  rule_code: string
  name: string
  description: string
  category: 'completeness' | 'consistency' | 'rationality' | 'timeliness'
  rule_type: 'objective' | 'subjective' | 'hybrid'
  severity: 'critical' | 'major' | 'minor'
  max_score: number
  weight: number
  is_active: boolean
  check_logic: Record<string, any>
  prompt_template?: string
  version: string
  created_at: string
  updated_at: string
  updating?: boolean
}

// 响应式数据
const activeTab = ref('semantic') // 默认显示语义质控规则
const loading = ref(false)
const rules = ref<EnhancedQCRule[]>([])
const selectedRowKeys = ref<string[]>([])
const searchText = ref('')
const filterCategory = ref<string>()
const filterDocumentCategory = ref<DocumentCategory>()
const filterSeverity = ref<string>()
const filterType = ref<string>()
const filterStatus = ref<string>()

// 文书类别相关数据（仅来源于数据库，不再回退到内置配置）
const documentCategoryOptions = ref<Array<{ value: DocumentCategory; label: string; description?: string; color?: string; icon?: string }>>([])
const documentCategoryStats = ref<Record<string, number>>({})
const categoriesLoaded = ref(false)

// 仅从数据库加载文书类别，失败则抛出错误，由调用方处理
const loadDocumentCategoryOptions = async () => {
  const categories = await DocumentCategoryService.getDocumentCategories()
  if (!categories || categories.length === 0) {
    throw new Error('No document categories found')
  }
  documentCategoryOptions.value = categories
    .sort((a: any, b: any) => (a.sort_order ?? 0) - (b.sort_order ?? 0))
    .map((cfg: any) => {
      const disp = DocumentCategoryService.getDocumentCategoryDisplayConfig(cfg.category_code as DocumentCategory)
      return {
        value: cfg.category_code as DocumentCategory,
        label: cfg.category_name,
        description: cfg.category_description || cfg.description,
        color: disp.color,
        icon: disp.icon
      }
    })
  categoriesLoaded.value = true
  // 调试输出：实际用于下拉框的文书类别选项
  try {
    // 仅打印关键信息，避免刷屏
    console.log('📄 文书类别选项(用于筛选) count=', documentCategoryOptions.value.length,
      documentCategoryOptions.value.map(o => ({ value: o.value, label: o.label })))
  } catch {}
}

// 模态框相关
const modalVisible = ref(false)
const modalLoading = ref(false)
const modalTitle = ref('')
const formRef = ref()
const isEditing = ref(false)
const editingId = ref<string>()

// 表单数据
const formData = reactive({
  rule_code: '',
  name: '',
  description: '',
  category: 'completeness' as const,
  rule_type: 'objective' as const,
  severity: 'minor' as const,
  max_score: 0,
  weight: 1.0,
  is_active: true,
  check_logic: {},
  prompt_template: '',
  version: '1.0'
})

const checkLogicText = ref('')

// 表单验证规则
const formRules = {
  rule_code: [
    { required: true, message: '请输入规则编码' },
    { pattern: /^\d+(\.\d+)*$/, message: '规则编码格式不正确，如: 1.1.1' }
  ],
  name: [
    { required: true, message: '请输入规则名称' },
    { min: 2, max: 100, message: '规则名称长度在2-100个字符' }
  ],
  description: [
    { required: true, message: '请输入规则描述' },
    { min: 10, max: 500, message: '规则描述长度在10-500个字符' }
  ],
  category: [{ required: true, message: '请选择规则分类' }],
  rule_type: [{ required: true, message: '请选择规则类型' }],
  severity: [{ required: true, message: '请选择严重程度' }],
  max_score: [{ required: true, type: 'number', min: 0, max: 100, message: '最大扣分范围0-100' }],
  weight: [{ required: true, type: 'number', min: 0.1, max: 5.0, message: '权重范围0.1-5.0' }]
}

// 分页配置
const pagination = reactive({
  current: 1,
  pageSize: 10,
  total: 0,
  showSizeChanger: true,
  showQuickJumper: true,
  showTotal: (total: number, range: [number, number]) =>
    `第 ${range[0]}-${range[1]} 条，共 ${total} 条`
})

// 表格列配置
const columns: TableColumnsType = [
  {
    title: '规则编码',
    dataIndex: 'rule_code',
    key: 'rule_code',
    width: 90,
    sorter: true
  },
  {
    title: '质控点来源',
    dataIndex: 'name',
    key: 'source',
    width: 180
  },
  {
    title: '质控点名称',
    dataIndex: 'description',
    key: 'name',
    width: 220
  },
  {
    title: '文书类别',
    dataIndex: 'primary_document_category',
    key: 'primary_document_category',
    width: 120,
    filters: documentCategoryOptions.value.map(option => ({
      text: option.label,
      value: option.value
    })),
    customRender: ({ record }: { record: EnhancedQCRule }) => {
      return renderDocumentCategory(record.primary_document_category)
    }
  },
  {
    title: '分类',
    dataIndex: 'category',
    key: 'category',
    width: 80,
    filters: [
      { text: '完整性', value: 'completeness' },
      { text: '一致性', value: 'consistency' },
      { text: '合理性', value: 'rationality' },
      { text: '及时性', value: 'timeliness' }
    ]
  },
  {
    title: '严重程度',
    dataIndex: 'severity',
    key: 'severity',
    width: 90,
    filters: [
      { text: '严重', value: 'critical' },
      { text: '重要', value: 'major' },
      { text: '轻微', value: 'minor' }
    ]
  },
  {
    title: '类型',
    dataIndex: 'rule_type',
    key: 'rule_type',
    width: 80,
    filters: [
      { text: '客观规则', value: 'objective' },
      { text: '主观规则', value: 'subjective' },
      { text: '混合规则', value: 'hybrid' }
    ]
  },
  {
    title: '最大扣分',
    dataIndex: 'max_score',
    key: 'max_score',
    width: 85,
    sorter: true
  },
  {
    title: '权重',
    dataIndex: 'weight',
    key: 'weight',
    width: 60,
    sorter: true
  },
  {
    title: '状态',
    dataIndex: 'is_active',
    key: 'is_active',
    width: 60
  },
  {
    title: '操作',
    key: 'actions',
    width: 200,
    fixed: 'right'
  }
]

// 行选择配置
const rowSelection: TableProps['rowSelection'] = {
  selectedRowKeys: selectedRowKeys.value,
  onChange: (keys: string[]) => {
    selectedRowKeys.value = keys
  }
}
// 让表头“文书类别”筛选项跟随选项变化而更新
watch(documentCategoryOptions, (opts) => {
  const col = (columns as any[]).find(c => c.key === 'primary_document_category')
  if (col) {
    col.filters = (opts || []).map((o: any) => ({ text: o.label, value: o.value }))
  }
}, { immediate: true })


// 计算属性
const statistics = computed(() => {
  const total = rules.value.length
  const active = rules.value.filter(r => r.is_active).length
  const critical = rules.value.filter(r => r.severity === 'critical').length
  const categories = new Set(rules.value.map(r => r.category)).size

  return { total, active, critical, categories }
})

const filteredRules = computed(() => {
  let filtered = [...rules.value]

  // 搜索过滤
  if (searchText.value) {
    const search = searchText.value.toLowerCase()
    filtered = filtered.filter(rule =>
      rule.name.toLowerCase().includes(search) ||
      rule.description.toLowerCase().includes(search) ||
      rule.rule_code.toLowerCase().includes(search)
    )
  }

  // 文书类别过滤
  if (filterDocumentCategory.value) {
    filtered = filtered.filter(rule =>
      rule.primary_document_category === filterDocumentCategory.value ||
      (rule.document_categories && rule.document_categories.includes(filterDocumentCategory.value))
    )
  }

  // 分类过滤
  if (filterCategory.value) {
    filtered = filtered.filter(rule => rule.category === filterCategory.value)
  }

  // 严重程度过滤
  if (filterSeverity.value) {
    filtered = filtered.filter(rule => rule.severity === filterSeverity.value)
  }

  // 类型过滤
  if (filterType.value) {
    filtered = filtered.filter(rule => rule.rule_type === filterType.value)
  }

  // 状态过滤
  if (filterStatus.value) {
    const isActive = filterStatus.value === 'active'
    filtered = filtered.filter(rule => rule.is_active === isActive)
  }

  return filtered
})

// 工具函数
const getCategoryColor = (category: string) => {
  return RULES_CONFIG.categories[category as keyof typeof RULES_CONFIG.categories]?.color || 'default'
}

const getCategoryLabel = (category: string) => {
  return RULES_CONFIG.categories[category as keyof typeof RULES_CONFIG.categories]?.label || category
}

const getSeverityColor = (severity: string) => {
  return RULES_CONFIG.severities[severity as keyof typeof RULES_CONFIG.severities]?.color || 'default'
}

const getSeverityLabel = (severity: string) => {
  return RULES_CONFIG.severities[severity as keyof typeof RULES_CONFIG.severities]?.label || severity
}

const getTypeColor = (type: string) => {
  return RULES_CONFIG.types[type as keyof typeof RULES_CONFIG.types]?.color || 'default'
}

const getTypeLabel = (type: string) => {
  return RULES_CONFIG.types[type as keyof typeof RULES_CONFIG.types]?.label || type
}

// 文书类别相关工具函数
const getDocumentCategoryLabel = (category: DocumentCategory) => {
  const config = DocumentCategoryService.getDocumentCategoryDisplayConfig(category)
  return config.label
}

const getDocumentCategoryColor = (category: DocumentCategory) => {
  const config = DocumentCategoryService.getDocumentCategoryDisplayConfig(category)
  return config.color
}

const renderDocumentCategory = (category: DocumentCategory) => {
  if (!category) return '-'
  const config = DocumentCategoryService.getDocumentCategoryDisplayConfig(category)
  return h('a-tag', { color: config.color }, config.label)
}

// 模拟数据
const mockRules: QCRule[] = [
  {
    id: '1',
    rule_code: '1.1.1',
    name: '入院记录完整性检查',
    description: '检查入院记录是否包含必要的基本信息，包括患者基本信息、主诉、现病史、既往史等',
    category: 'completeness',
    rule_type: 'objective',
    severity: 'critical',
    max_score: 0,
    weight: 2.0,
    is_active: true,
    check_logic: {
      required_fields: ['patient_name', 'admission_date', 'chief_complaint', 'present_illness']
    },
    prompt_template: '请检查入院记录是否包含以下必要信息：患者姓名、入院日期、主诉、现病史',
    version: '1.0',
    created_at: '2024-01-15T10:00:00Z',
    updated_at: '2024-01-15T10:00:00Z'
  },
  {
    id: '2',
    rule_code: '1.2.1',
    name: '诊断一致性检查',
    description: '检查入院诊断与出院诊断的一致性，确保诊断变更有合理依据',
    category: 'consistency',
    rule_type: 'hybrid',
    severity: 'major',
    max_score: 5,
    weight: 1.5,
    is_active: true,
    check_logic: {
      compare_fields: ['admission_diagnosis', 'discharge_diagnosis'],
      tolerance: 0.8
    },
    prompt_template: '请分析入院诊断与出院诊断的一致性，如有变更请说明理由',
    version: '1.0',
    created_at: '2024-01-15T10:30:00Z',
    updated_at: '2024-01-15T10:30:00Z'
  },
  {
    id: '3',
    rule_code: '2.1.1',
    name: '用药合理性检查',
    description: '检查药物使用是否符合适应症，剂量是否合理，是否存在禁忌症',
    category: 'rationality',
    rule_type: 'subjective',
    severity: 'critical',
    max_score: 0,
    weight: 3.0,
    is_active: true,
    check_logic: {
      drug_interaction_check: true,
      dosage_check: true,
      contraindication_check: true
    },
    prompt_template: '请评估患者的用药方案是否合理，包括适应症、剂量、禁忌症等方面',
    version: '1.0',
    created_at: '2024-01-15T11:00:00Z',
    updated_at: '2024-01-15T11:00:00Z'
  },
  {
    id: '4',
    rule_code: '3.1.1',
    name: '手术记录及时性检查',
    description: '检查手术记录是否在规定时间内完成，确保医疗文书的及时性',
    category: 'timeliness',
    rule_type: 'objective',
    severity: 'major',
    max_score: 3,
    weight: 1.0,
    is_active: true,
    check_logic: {
      time_limit: 24,
      time_unit: 'hours'
    },
    prompt_template: '请检查手术记录是否在术后24小时内完成',
    version: '1.0',
    created_at: '2024-01-15T11:30:00Z',
    updated_at: '2024-01-15T11:30:00Z'
  },
  {
    id: '5',
    rule_code: '1.1.2',
    name: '病程记录完整性检查',
    description: '检查病程记录是否按规定频次记录，内容是否完整',
    category: 'completeness',
    rule_type: 'objective',
    severity: 'minor',
    max_score: 2,
    weight: 1.0,
    is_active: false,
    check_logic: {
      frequency_check: true,
      content_completeness: ['symptoms', 'treatment', 'response']
    },
    prompt_template: '请检查病程记录的频次和内容完整性',
    version: '1.0',
    created_at: '2024-01-15T12:00:00Z',
    updated_at: '2024-01-15T12:00:00Z'
  },
  {
    id: '6',
    rule_code: '2.2.1',
    name: '检查结果合理性分析',
    description: '分析检查结果是否与临床表现相符，是否需要进一步检查',
    category: 'rationality',
    rule_type: 'hybrid',
    severity: 'major',
    max_score: 4,
    weight: 1.8,
    is_active: true,
    check_logic: {
      clinical_correlation: true,
      reference_range_check: true
    },
    prompt_template: '请分析检查结果与临床表现的相关性，评估是否需要进一步检查',
    version: '1.0',
    created_at: '2024-01-15T12:30:00Z',
    updated_at: '2024-01-15T12:30:00Z'
  }
]

// 模拟服务
const mockRulesService = {
  getAllRules: async () => {
    await new Promise(resolve => setTimeout(resolve, 500)) // 模拟网络延迟
    return mockRules
  },
  createRule: async (ruleData: any) => {
    await new Promise(resolve => setTimeout(resolve, 300))
    const newRule = {
      ...ruleData,
      id: Date.now().toString(),
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString()
    }
    mockRules.push(newRule)
    return newRule
  },
  updateRule: async (id: string, ruleData: any) => {
    await new Promise(resolve => setTimeout(resolve, 300))
    const index = mockRules.findIndex(r => r.id === id)
    if (index !== -1) {
      mockRules[index] = { ...mockRules[index], ...ruleData, updated_at: new Date().toISOString() }
    }
    return mockRules[index]
  },
  deleteRule: async (id: string) => {
    await new Promise(resolve => setTimeout(resolve, 300))
    const index = mockRules.findIndex(r => r.id === id)
    if (index !== -1) {
      mockRules.splice(index, 1)
    }
  },
  toggleRuleStatus: async (id: string, isActive: boolean) => {
    await new Promise(resolve => setTimeout(resolve, 200))
    const rule = mockRules.find(r => r.id === id)
    if (rule) {
      rule.is_active = isActive
      rule.updated_at = new Date().toISOString()
    }
  },
  batchUpdateRuleStatus: async (ids: string[], isActive: boolean) => {
    await new Promise(resolve => setTimeout(resolve, 500))
    ids.forEach(id => {
      const rule = mockRules.find(r => r.id === id)
      if (rule) {
        rule.is_active = isActive
        rule.updated_at = new Date().toISOString()
      }
    })
  },
  deleteRules: async (ids: string[]) => {
    await new Promise(resolve => setTimeout(resolve, 500))
    ids.forEach(id => {
      const index = mockRules.findIndex(r => r.id === id)
      if (index !== -1) {
        mockRules.splice(index, 1)
      }
    })
  },
  exportRules: async (format: string) => {
    await new Promise(resolve => setTimeout(resolve, 300))
    return JSON.stringify(mockRules, null, 2)
  }
}

// 模拟验证器
const mockRulesValidator = {
  validateRule: (ruleData: any) => {
    const errors: string[] = []
    const warnings: string[] = []

    if (!ruleData.rule_code) errors.push('规则编码不能为空')
    if (!ruleData.name) errors.push('规则名称不能为空')
    if (!ruleData.description) errors.push('规则描述不能为空')

    if (ruleData.max_score < 0 || ruleData.max_score > 100) {
      errors.push('最大扣分必须在0-100之间')
    }

    if (ruleData.weight < 0.1 || ruleData.weight > 5.0) {
      warnings.push('权重建议在0.1-5.0之间')
    }

    return {
      isValid: errors.length === 0,
      errors,
      warnings
    }
  }
}

// 数据加载（严格依赖数据库的文书类别和规则数据，不再回退到本地/模拟数据）
const loadRules = async () => {
  loading.value = true
  try {
    if (!categoriesLoaded.value) {
      throw new Error('Document categories not loaded')
    }
    const filters: QCRuleFilterParams = {
      keyword: searchText.value,
      category: filterCategory.value,
      document_category: filterDocumentCategory.value,
      rule_type: filterType.value as any,
      severity: filterSeverity.value as any,
      is_active: filterStatus.value === 'active' ? true : filterStatus.value === 'inactive' ? false : undefined,
      page: pagination.current,
      pageSize: pagination.pageSize
    }
    const result = await DocumentCategoryService.getEnhancedQCRules(filters)
    rules.value = result.data
    pagination.total = result.total
  } finally {
    loading.value = false
  }
}

// 事件处理
const handleTabChange = (key: string) => {
  activeTab.value = key
  // 可以在这里添加标签页切换时的逻辑
  console.log('切换到标签页:', key)
}

const refreshRules = async () => {
  try {
    await loadDocumentCategoryOptions()
    await loadRules()
    await loadDocumentCategoryStats()
  } catch (e) {
    console.error('刷新失败:', e)
    message.error('无法加载文书类别或规则数据，请检查数据库连接')
  }
}

const handleSearch = () => {
  // 搜索逻辑已在计算属性中处理
}

const handleFilter = () => {
  // 过滤逻辑已在计算属性中处理
}

const resetFilters = () => {
  searchText.value = ''
  filterCategory.value = undefined
  filterDocumentCategory.value = undefined
  filterSeverity.value = undefined
  filterType.value = undefined
  filterStatus.value = undefined
}

const clearAllFilters = () => {
  resetFilters()
}

// 文书类别相关方法
const clearDocumentCategoryFilter = () => {
  filterDocumentCategory.value = undefined
}

const quickFilterDocumentCategory = (category: DocumentCategory) => {
  if (filterDocumentCategory.value === category) {
    filterDocumentCategory.value = undefined
  } else {
    filterDocumentCategory.value = category
  }
}

// 加载文书类别统计
const loadDocumentCategoryStats = async () => {
  try {
    const stats = await DocumentCategoryService.getDocumentCategoryStats()
    documentCategoryStats.value = stats
  } catch (error) {
    console.error('加载文书类别统计失败:', error)
  }
}

const quickFilterCategory = (category) => {
  if (filterCategory.value === category) {
    filterCategory.value = undefined
  } else {
    filterCategory.value = category
  }
  handleFilter()
}

const quickFilterSeverity = (severity) => {
  if (filterSeverity.value === severity) {
    filterSeverity.value = undefined
  } else {
    filterSeverity.value = severity
  }
  handleFilter()
}

const quickFilterStatus = (status) => {
  if (filterStatus.value === status) {
    filterStatus.value = undefined
  } else {
    filterStatus.value = status
  }
  handleFilter()
}

const batchActivate = async (isActive) => {
  if (selectedRowKeys.value.length === 0) {
    message.warning('请先选择要操作的规则')
    return
  }

  try {
    loading.value = true
    await mockRulesService.batchUpdateRuleStatus(selectedRowKeys.value, isActive)
    message.success(`批量${isActive ? '激活' : '停用'}成功`)
    selectedRowKeys.value = []
    loadRules()
  } catch (error) {
    console.error('批量操作失败:', error)
    message.error(error instanceof Error ? error.message : '批量操作失败')
  } finally {
    loading.value = false
  }
}

const batchDelete = async () => {
  if (selectedRowKeys.value.length === 0) {
    message.warning('请先选择要删除的规则')
    return
  }

  try {
    loading.value = true
    await mockRulesService.deleteRules(selectedRowKeys.value)
    message.success(`批量删除 ${selectedRowKeys.value.length} 条规则成功`)
    selectedRowKeys.value = []
    loadRules()
  } catch (error) {
    console.error('批量删除失败:', error)
    message.error(error instanceof Error ? error.message : '批量删除失败')
  } finally {
    loading.value = false
  }
}

const handleTableChange: TableProps['onChange'] = (pag: any,  filters: any, sorter: any) => {
  if (pag) {
    pagination.current = pag.current || 1
    pagination.pageSize = pag.pageSize || 10
  }
}

// 规则操作
const showCreateModal = () => {
  isEditing.value = false
  modalTitle.value = '新增规则'
  resetFormData()
  modalVisible.value = true
}

const editRule = (rule: QCRule) => {
  isEditing.value = true
  editingId.value = rule.id
  modalTitle.value = '编辑规则'

  // 填充表单数据
  Object.assign(formData, {
    rule_code: rule.rule_code,
    name: rule.name,
    description: rule.description,
    category: rule.category,
    rule_type: rule.rule_type,
    severity: rule.severity,
    max_score: rule.max_score,
    weight: rule.weight,
    is_active: rule.is_active,
    check_logic: rule.check_logic,
    prompt_template: rule.prompt_template || '',
    version: rule.version
  })

  checkLogicText.value = JSON.stringify(rule.check_logic, null, 2)
  modalVisible.value = true
}

const viewRule = (rule: QCRule) => {
  // 可以打开详情页面或模态框
  message.info('查看规则详情功能待实现')
}

const testRule = (rule: QCRule) => {
  // 可以打开测试页面
  message.info('规则测试功能待实现')
}

const deleteRule = async (rule: QCRule) => {
  try {
    await mockRulesService.deleteRule(rule.id)
    message.success('删除成功')
    loadRules()
  } catch (error) {
    console.error('删除规则失败:', error)
    message.error(error instanceof Error ? error.message : '删除规则失败')
  }
}

const toggleRuleStatus = async (rule: QCRule, checked: boolean) => {
  try {
    rule.updating = true
    await mockRulesService.toggleRuleStatus(rule.id, checked)
    rule.is_active = checked
    message.success(checked ? '规则已激活' : '规则已停用')
  } catch (error) {
    console.error('更新规则状态失败:', error)
    message.error(error instanceof Error ? error.message : '更新规则状态失败')
    rule.is_active = !checked // 回滚状态
  } finally {
    rule.updating = false
  }
}

// 批量操作
const handleBatchAction = async ({ key }: { key: string }) => {
  if (selectedRowKeys.value.length === 0) {
    message.warning('请先选择要操作的规则')
    return
  }

  try {
    loading.value = true

    switch (key) {
      case 'activate':
        await mockRulesService.batchUpdateRuleStatus(selectedRowKeys.value, true)
        message.success('批量激活成功')
        break
      case 'deactivate':
        await mockRulesService.batchUpdateRuleStatus(selectedRowKeys.value, false)
        message.success('批量停用成功')
        break
      case 'delete':
        await mockRulesService.deleteRules(selectedRowKeys.value)
        message.success('批量删除成功')
        break
    }

    selectedRowKeys.value = []
    loadRules()
  } catch (error) {
    console.error('批量操作失败:', error)
    message.error(error instanceof Error ? error.message : '批量操作失败')
  } finally {
    loading.value = false
  }
}

// 模态框操作
const handleModalOk = async () => {
  try {
    await formRef.value.validate()
    modalLoading.value = true

    // 解析检查逻辑JSON
    let checkLogic = {}
    if (checkLogicText.value.trim()) {
      try {
        checkLogic = JSON.parse(checkLogicText.value)
      } catch (e) {
        message.error('检查逻辑JSON格式不正确')
        return
      }
    }

    const ruleData = {
      ...formData,
      check_logic: checkLogic
    }

    // 验证规则数据
    const validation = mockRulesValidator.validateRule(ruleData)
    if (!validation.isValid) {
      message.error(`规则验证失败: ${validation.errors.join(', ')}`)
      return
    }

    if (validation.warnings.length > 0) {
      console.warn('规则验证警告:', validation.warnings)
    }

    if (isEditing.value && editingId.value) {
      // 更新规则
      await mockRulesService.updateRule(editingId.value, ruleData)
      message.success('更新规则成功')
    } else {
      // 创建规则
      await mockRulesService.createRule(ruleData)
      message.success('创建规则成功')
    }

    modalVisible.value = false
    loadRules()
  } catch (error) {
    console.error('保存规则失败:', error)
    message.error(error instanceof Error ? error.message : '保存规则失败')
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
    rule_code: '',
    name: '',
    description: '',
    category: 'completeness',
    rule_type: 'objective',
    severity: 'minor',
    max_score: 0,
    weight: 1.0,
    is_active: true,
    check_logic: {},
    prompt_template: '',
    version: '1.0'
  })
  checkLogicText.value = ''
  formRef.value?.resetFields()
}

// 导入导出
const importRules = () => {
  message.info('规则导入功能待实现')
}

const exportRules = async () => {
  try {
    const exportData = await mockRulesService.exportRules('json')
    const blob = new Blob([exportData], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `qc-rules-${new Date().toISOString().split('T')[0]}.json`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(url)
    message.success('规则导出成功')
  } catch (error) {
    console.error('导出规则失败:', error)
    message.error('导出规则失败')
  }
}

// 生命周期
onMounted(async () => {
  try {
    await loadDocumentCategoryOptions()
    await loadRules()
    await loadDocumentCategoryStats()
  } catch (e) {
    console.error('初始化数据失败:', e)
    message.error('无法加载文书类别或规则数据，请检查数据库连接')
  }
})
</script>

<style scoped>
/* 主容器样式 */
.page-container {
  padding: 0;
  background: transparent;
  min-height: auto;
}

/* 标签页样式 */
.rules-tabs {
  @apply mb-4;
}

:deep(.rules-tabs .ant-tabs-nav) {
  @apply mb-3;
}

:deep(.rules-tabs .ant-tabs-tab) {
  @apply px-4 py-2;
  font-size: 14px !important;
  font-weight: 500 !important;
}

:deep(.rules-tabs .ant-tabs-tab-active) {
  @apply font-semibold;
}

:deep(.rules-tabs .ant-tabs-tab .anticon) {
  @apply mr-2;
}

.tab-content {
  @apply min-h-96;
}

/* 统计卡片内部样式优化 */
:deep(.ant-statistic-title) {
  color: #64748b;
  font-size: 14px;
  font-weight: 500;
  margin-bottom: 8px;
}

:deep(.ant-statistic-content) {
  font-size: 20px;
  font-weight: 700;
  line-height: 1.2;
}

/* 表格相关样式 */
.rules-table-section {
  background: white;
  border-radius: 12px;
  margin: 0;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1), 0 1px 2px rgba(0, 0, 0, 0.06);
  border: 1px solid #e2e8f0;
}

.table-card {
  border-radius: 12px;
  border: 1px solid #e2e8f0;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

.table-header {
  display: flex;
  align-items: center;
  gap: 8px;
}

.table-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
  color: #1e293b;
}

.table-icon {
  color: #3b82f6;
}

.table-count {
  color: #64748b;
  font-size: 14px;
  font-weight: 500;
}

/* 批量操作样式 */
.batch-actions {
  margin-bottom: 16px;
}

.selection-alert {
  border-radius: 8px;
  border: 1px solid #bfdbfe;
  background: linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%);
}

/* 快速筛选标签样式 */
.filter-tag {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 8px 16px;
  border-radius: 12px;
  font-size: 13px;
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
}

:deep(.ant-btn-primary:hover) {
  background: linear-gradient(135deg, #2563eb 0%, #1e40af 100%);
  transform: translateY(-1px);
  box-shadow: 0 4px 16px rgba(59, 130, 246, 0.3);
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

.rule-source {
  @apply font-medium text-gray-900;
  font-size: 12px !important;  /* 从 11px 恢复到 12px，提升可读性 */
  line-height: 1.3 !important;  /* 从 1.1 增加到 1.3，提升可读性 */
  padding: 1px 0 !important;  /* 适当增加内边距 */
  margin: 0 !important;
}

.rule-name {
  @apply text-gray-700;
  font-size: 11px !important;  /* 从 10px 恢复到 11px，提升可读性 */
  line-height: 1.3 !important;  /* 从 1.1 增加到 1.3，提升可读性 */
  padding: 1px 0 !important;  /* 适当增加内边距 */
  margin: 0 !important;
  word-break: break-word !important;
}

/* 表格标题行 - 进一步压缩高度 */
:deep(.ant-table-thead > tr > th) {
  @apply bg-gray-50 font-semibold;
  font-size: 11px !important;
  padding: 4px 3px !important;  /* 从 6px 4px 进一步减少到 4px 3px */
  white-space: nowrap !important;
  font-weight: 600 !important;
  height: 28px !important;  /* 明确设置标题行高度 */
  line-height: 1.1 !important;  /* 紧凑的行高 */
}

/* 表格行优化 - 平衡紧凑性与可读性 */
:deep(.ant-table-tbody > tr > td) {
  font-size: 13px !important;
  padding: 4px 6px !important;  /* 从 2px 4px 适当增加到 4px 6px，提升可读性 */
  vertical-align: middle !important;
  line-height: 1.2 !important;  /* 从 1.1 增加到 1.2，提升文字可读性 */
}

/* 特殊调整质控点来源和名称列的单元格 */
:deep(.ant-table-tbody > tr > td:nth-child(2)),
:deep(.ant-table-tbody > tr > td:nth-child(3)) {
  padding: 3px 5px !important;  /* 从 1px 3px 适当增加到 3px 5px */
  font-size: 11px !important;
}

:deep(.ant-table-tbody > tr:hover > td) {
  @apply bg-blue-50;
}

/* 表格行高调整 - 平衡紧凑性与可读性 */
:deep(.ant-table-tbody > tr) {
  height: 30px !important;  /* 从 26px 适当增加到 30px，提升可读性 */
}

/* 表格内容垂直居中 - 平衡间距与可读性 */
:deep(.ant-table-tbody > tr > td .ant-space) {
  align-items: center !important;
  gap: 3px !important;  /* 从 1px 适当增加到 3px，提升视觉分离度 */
}

:deep(.ant-table-tbody > tr > td .ant-space-item) {
  display: flex !important;
  align-items: center !important;
}

/* 表格整体紧凑化 */
:deep(.ant-table) {
  font-size: 11px !important;  /* 从 12px 减少到 11px */
}

:deep(.ant-table-container) {
  border-radius: 4px !important;
}

/* 表格外层容器优化 */
:deep(.ant-table-wrapper) {
  margin: 0 !important;
}

/* 表格内标签优化 */
:deep(.ant-table-tbody .ant-tag) {
  font-size: 10px !important;
  height: 16px !important;  /* 从默认高度减少 */
  line-height: 14px !important;
  padding: 0 4px !important;
  margin: 0 1px !important;
}

/* 表格内开关优化 */
:deep(.ant-table-tbody .ant-switch) {
  height: 14px !important;  /* 从默认高度减少 */
  min-width: 24px !important;
  font-size: 9px !important;
}

/* 表格分页器优化 */
:deep(.ant-pagination) {
  margin-top: 8px !important;  /* 减少分页器上边距 */
  margin-bottom: 0 !important;
}

/* 表格滚动条优化 */
:deep(.ant-table-body) {
  scrollbar-width: thin;
}

/* 表格边框优化 */
:deep(.ant-table-thead > tr > th),
:deep(.ant-table-tbody > tr > td) {
  border-bottom: 1px solid #f0f0f0 !important;
}

/* 表格行间距最小化 */
:deep(.ant-table-tbody > tr > td) {
  border-spacing: 0 !important;
}

/* 确保表格内数字垂直居中 */
:deep(.ant-table-tbody > tr > td .ant-statistic-content-value) {
  font-size: 12px !important;
  line-height: 1.1 !important;
}

/* 统计卡片标题 - 优化间距提高紧凑性 */
:deep(.ant-statistic-title) {
  @apply text-gray-700 font-bold;
  font-size: 15px !important;
  font-weight: 700 !important;
  margin-bottom: 4px !important;  /* 从 8px 减少到 4px */
}

:deep(.ant-statistic-content) {
  @apply font-bold;
  font-size: 20px !important;
}

:deep(.ant-statistic-content-value) {
  font-size: 20px !important;
}

:deep(.ant-form-item-label > label) {
  @apply font-medium text-gray-700;
  font-size: 14px !important;
}

:deep(.ant-modal-header) {
  @apply border-b border-gray-200;
}

:deep(.ant-modal-footer) {
  @apply border-t border-gray-200;
}

/* 统一按钮尺寸和字体 - 调小筛选区域按钮 */
:deep(.ant-btn) {
  font-size: 12px !important;
  height: 28px !important;
  padding: 3px 12px !important;
  line-height: 1.4 !important;
}

/* 表格内小按钮 - 进一步压缩 */
:deep(.ant-btn-sm) {
  font-size: 11px !important;  /* 从 12px 减少到 11px */
  height: 20px !important;     /* 从 22px 减少到 20px */
  padding: 0px 5px !important; /* 从 0px 6px 减少到 0px 5px */
  line-height: 1.1 !important;
}

/* 头部操作按钮保持稍大尺寸 */
:deep(.header-actions .ant-btn) {
  font-size: 13px !important;
  height: 30px !important;
  padding: 4px 14px !important;
}

/* 统一输入框尺寸 - 调小筛选区域输入框 */
:deep(.ant-input) {
  font-size: 12px !important;
  height: 28px !important;
  padding: 3px 8px !important;
}

:deep(.ant-input-search .ant-input) {
  font-size: 12px !important;
  height: 28px !important;
}

:deep(.ant-input-search .ant-input-search-button) {
  font-size: 12px !important;
  height: 28px !important;
}

/* 统一下拉菜单尺寸 - 调小筛选区域下拉菜单 */
:deep(.ant-select) {
  font-size: 12px !important;
}

:deep(.ant-select-selector) {
  font-size: 12px !important;
  height: 28px !important;
  padding: 0 8px !important;
}

:deep(.ant-select-selection-item) {
  font-size: 12px !important;
  line-height: 26px !important;
}

:deep(.ant-select-selection-placeholder) {
  font-size: 12px !important;
  line-height: 26px !important;
}

/* 统一标签尺寸 - 调整为更小尺寸与表格内容一致 */
:deep(.ant-tag) {
  font-size: 11px !important;
  height: 18px !important;
  line-height: 16px !important;
  padding: 0 5px !important;
  margin: 0 2px 0 0 !important;
  border-radius: 2px !important;
}

/* 表格内标签特殊调整 */
:deep(.ant-table-tbody .ant-tag) {
  font-size: 11px !important;
  height: 18px !important;
  line-height: 16px !important;
  padding: 0 5px !important;
  margin: 0 2px 2px 0 !important;
  display: inline-block !important;
  vertical-align: middle !important;
}

/* 统一开关尺寸 - 调整为与标签一致的小尺寸 */
:deep(.ant-switch) {
  font-size: 10px !important;
  height: 16px !important;
  min-width: 28px !important;
  line-height: 14px !important;
}

:deep(.ant-switch-inner) {
  font-size: 10px !important;
  line-height: 14px !important;
}

:deep(.ant-switch-handle) {
  width: 12px !important;
  height: 12px !important;
  top: 2px !important;
}

:deep(.ant-switch-handle::before) {
  border-radius: 6px !important;
}

:deep(.ant-switch-checked .ant-switch-handle) {
  left: calc(100% - 12px - 2px) !important;
}

/* 统一表格操作按钮 - 调整为更小尺寸 */
:deep(.ant-btn-link) {
  font-size: 12px !important;
  height: auto !important;
  padding: 0 4px !important;
  line-height: 1.4 !important;
  min-height: 20px !important;
}

/* 表格内的按钮间距调整 */
:deep(.ant-table-tbody .ant-space-item) {
  margin-right: 4px !important;
}

:deep(.ant-table-tbody .ant-space) {
  gap: 4px !important;
}

/* 统一卡片标题 */
:deep(.ant-card-head-title) {
  font-size: 14px !important;
  font-weight: 600 !important;
}

/* 统一表单输入框 */
:deep(.ant-form-item-control-input .ant-input) {
  font-size: 14px !important;
  height: 32px !important;
}

:deep(.ant-form-item-control-input .ant-select-selector) {
  font-size: 14px !important;
  height: 32px !important;
}

:deep(.ant-form-item-control-input .ant-input-number) {
  font-size: 14px !important;
  height: 32px !important;
  width: 100% !important;
}

:deep(.ant-form-item-control-input .ant-input-number-input) {
  font-size: 14px !important;
  height: 30px !important;
}

/* 统一文本域 */
:deep(.ant-input) {
  font-size: 14px !important;
}

/* 统一分页器 */
:deep(.ant-pagination) {
  font-size: 14px !important;
}

:deep(.ant-pagination-item) {
  font-size: 14px !important;
}

:deep(.ant-pagination-item a) {
  font-size: 14px !important;
}

:deep(.ant-pagination-prev .ant-pagination-item-link),
:deep(.ant-pagination-next .ant-pagination-item-link) {
  font-size: 14px !important;
}

/* 统一下拉菜单项 */
:deep(.ant-dropdown-menu-item) {
  font-size: 14px !important;
}

.line-clamp-2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>