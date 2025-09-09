<template>
  <BasicLayout>
    <div class="min-h-screen bg-gray-50 p-4 lg:p-6">
      <!-- 页面头部 -->
      <div class="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-6">
        <div class="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
          <div class="flex-1">
            <div class="flex items-center space-x-3 mb-2">
              <div class="p-2 bg-blue-100 rounded-lg">
                <SettingOutlined class="text-xl text-blue-600" />
              </div>
              <h1 class="text-2xl lg:text-3xl font-bold text-gray-900">
                智慧医保规则管理
              </h1>
            </div>
            <p class="text-gray-600 text-sm lg:text-base">
              管理医保临床实时质控规则，支持规则的创建、编辑、版本管理和生命周期控制
            </p>
          </div>
          <div class="flex flex-wrap gap-2">
            <a-button
              @click="load"
              :loading="loading"
              class="flex items-center space-x-2"
            >
              <template #icon><ReloadOutlined /></template>
              <span>刷新</span>
            </a-button>
            <a-button
              @click="openImport"
              class="flex items-center space-x-2"
            >
              <template #icon><ImportOutlined /></template>
              <span>导入规则</span>
            </a-button>
            <a-button
              @click="openExport"
              :disabled="!rows.length"
              class="flex items-center space-x-2"
            >
              <template #icon><ExportOutlined /></template>
              <span>导出规则</span>
            </a-button>
            <a-button
              type="primary"
              @click="openCreate"
              class="flex items-center space-x-2 bg-blue-600 hover:bg-blue-700"
            >
              <template #icon><PlusOutlined /></template>
              <span>新建规则</span>
            </a-button>
          </div>
        </div>
      </div>

      <!-- 筛选和搜索区域 -->
      <div class="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-6">
        <div class="flex items-center justify-between mb-4">
          <h2 class="text-lg font-semibold text-gray-900">筛选条件</h2>
          <a-button
            size="small"
            @click="clearFilters"
            class="text-gray-500 hover:text-gray-700"
          >
            <template #icon><ClearOutlined /></template>
            清空筛选
          </a-button>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-4">
          <div class="space-y-2">
            <label class="text-sm font-medium text-gray-700">搜索</label>
            <a-input-search
              v-model:value="keyword"
              placeholder="搜索规则名称、编码或描述..."
              @search="load"
              class="w-full"
            />
          </div>

          <div class="space-y-2">
            <label class="text-sm font-medium text-gray-700">规则分类</label>
            <a-select
              v-model:value="categoryFilter"
              placeholder="选择分类"
              allowClear
              @change="load"
              class="w-full"
            >
              <a-select-option value="batch_1">第一批（年龄性别）</a-select-option>
              <a-select-option value="batch_2">第二批（手术折价）</a-select-option>
              <a-select-option value="batch_3">第三批（保险类型）</a-select-option>
              <a-select-option value="batch_4">第四批（就诊方式）</a-select-option>
              <a-select-option value="batch_5">第五批（机构级别）</a-select-option>
            </a-select>
          </div>

          <div class="space-y-2">
            <label class="text-sm font-medium text-gray-700">启用状态</label>
            <a-select
              v-model:value="enabled"
              :options="enabledOptions"
              allowClear
              placeholder="启用状态"
              @change="load"
              class="w-full"
            />
          </div>

          <div class="space-y-2">
            <label class="text-sm font-medium text-gray-700">严重级别</label>
            <a-select
              v-model:value="severity"
              :options="severityOptions"
              allowClear
              placeholder="严重级别"
              @change="load"
              class="w-full"
            />
          </div>

          <div class="space-y-2">
            <label class="text-sm font-medium text-gray-700">规则类型</label>
            <a-select
              v-model:value="ruleTypeFilter"
              placeholder="选择类型"
              allowClear
              @change="load"
              class="w-full"
            >
              <a-select-option value="drug_gender">性别限制</a-select-option>
              <a-select-option value="drug_age">年龄限制</a-select-option>
              <a-select-option value="drug_children_only">儿童专用</a-select-option>
              <a-select-option value="drug_payment_course">支付疗程限制</a-select-option>
              <a-select-option value="drug_insurance_type">保险类型限制</a-select-option>
              <a-select-option value="drug_diagnosis">诊断限制</a-select-option>
              <a-select-option value="drug_dosage_form">剂型限制</a-select-option>
              <a-select-option value="drug_route">给药途径</a-select-option>
              <a-select-option value="drug_indication">适应症限制</a-select-option>
            </a-select>
          </div>
        </div>

      </div>

      <!-- 快速筛选标签 -->
      <div class="quick-filters mb-4">
        <div class="flex items-center gap-3 flex-wrap">
          <span class="text-sm font-semibold text-gray-800">快速筛选：</span>
          <div
            :class="['filter-tag', { 'filter-tag-active': !ruleTypeFilter }]"
            @click="quickFilter('all')"
          >
            <span class="filter-tag-text">全部类型</span>
            <span class="filter-tag-count">({{ total }})</span>
          </div>
          <div
            :class="['filter-tag', { 'filter-tag-active': ruleTypeFilter === 'drug_gender' }]"
            @click="quickFilter('drug_gender')"
          >
            <span class="filter-tag-text">性别限制</span>
          </div>
          <div
            :class="['filter-tag', { 'filter-tag-active': ruleTypeFilter === 'drug_age' }]"
            @click="quickFilter('drug_age')"
          >
            <span class="filter-tag-text">年龄限制</span>
          </div>
          <div
            :class="['filter-tag', { 'filter-tag-active': ruleTypeFilter === 'drug_children_only' }]"
            @click="quickFilter('drug_children_only')"
          >
            <span class="filter-tag-text">儿童专用</span>
          </div>
          <div
            :class="['filter-tag', { 'filter-tag-active': ruleTypeFilter === 'drug_insurance_type' }]"
            @click="quickFilter('drug_insurance_type')"
          >
            <span class="filter-tag-text">保险类型限制</span>
          </div>
          <div
            :class="['filter-tag filter-tag-danger', { 'filter-tag-danger-active': severity === 'block' }]"
            @click="quickFilterSeverity('block')"
          >
            <span class="filter-tag-text">拦截规则</span>
          </div>
          <div
            :class="['filter-tag filter-tag-success', { 'filter-tag-success-active': enabled === true }]"
            @click="quickFilterEnabled(true)"
          >
            <span class="filter-tag-text">已启用</span>
          </div>

          <!-- 操作按钮（移动到与快速筛选同一行，靠右） -->
          <div class="ml-auto flex items-center gap-2 flex-shrink-0">
            <a-button type="primary" @click="load" class="bg-blue-600 hover:bg-blue-700">
              <template #icon><SearchOutlined /></template>
              查询
            </a-button>
            <a-button @click="clearFilters">
              <template #icon><ClearOutlined /></template>
              重置
            </a-button>
          </div>
        </div>
      </div>

      <!-- 批量操作区域 -->
      <div class="batch-actions" v-if="selectedRowKeys.length > 0">
        <a-alert
          :message="`已选择 ${selectedRowKeys.length} 条规则`"
          type="info"
          show-icon
          class="selection-alert"
        >
          <template #action>
            <a-space>
              <a-button size="small" @click="batchEnable(true)">
                <template #icon><CheckCircleOutlined /></template>
                批量启用
              </a-button>
              <a-button size="small" @click="batchEnable(false)">
                <template #icon><StopOutlined /></template>
                批量禁用
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
              <span class="table-count">共 {{ total }} 条规则</span>
            </div>
          </template>

          <a-table
            :dataSource="rows"
            :columns="enhancedColumns"
            :pagination="paginationConfig"
            :loading="loading"
            :row-selection="rowSelection"
            :scroll="{ x: 1450 }"
            @change="onTableChange"
            row-key="id"
            class="rules-table"
            :locale="{
              emptyText: '暂无规则数据，请检查筛选条件或导入规则数据'
            }"
          >
            <!-- 自定义列渲染 -->
            <template #bodyCell="{ column, record }">
              <!-- 规则类型列 -->
              <template v-if="column.key === 'rule_type'">
                <a-tag :color="getRuleTypeColor(record.rule_type)" class="type-tag">
                  {{ getRuleTypeLabel(record.rule_type) }}
                </a-tag>
              </template>

              <!-- 分类列 -->
              <template v-else-if="column.key === 'category'">
                <a-tag :color="getCategoryColor(record.category_id)" class="category-tag">
                  {{ getCategoryLabel(record.category_id) }}
                </a-tag>
              </template>

              <!-- 严重级别列 -->
              <template v-else-if="column.key === 'severity'">
                <a-tag :color="getSeverityColor(record.severity)" class="severity-tag">
                  <template #icon>
                    <ExclamationCircleOutlined v-if="record.severity === 'block'" />
                    <WarningOutlined v-else-if="record.severity === 'warn'" />
                    <InfoCircleOutlined v-else />
                  </template>
                  {{ getSeverityLabel(record.severity) }}
                </a-tag>
              </template>

              <!-- 启用状态列 -->
              <template v-else-if="column.key === 'enabled'">
                <a-switch
                  :checked="!!record.enabled"
                  :loading="togglingId === record.id"
                  @change="(val) => toggle(record, val)"
                  :checkedChildren="'启用'"
                  :unCheckedChildren="'禁用'"
                />
              </template>

              <!-- 版本列 -->
              <template v-else-if="column.key === 'version'">
                <div class="version-info">
                  <a-tag color="purple">v{{ record.version || 1 }}</a-tag>
                  <a-button
                    type="link"
                    size="small"
                    @click="showVersionHistory(record)"
                    class="version-history-btn"
                  >
                    历史
                  </a-button>
                </div>
              </template>

              <!-- 更新时间列 -->
              <template v-else-if="column.key === 'updated_at'">
                <div class="time-info">
                  <div class="time-text">{{ formatTime(record.updated_at) }}</div>
                  <div class="time-relative">{{ getRelativeTime(record.updated_at) }}</div>
                </div>
              </template>

              <!-- 操作列 -->
              <template v-else-if="column.key === 'actions'">
                <a-space size="small">
                  <a-tooltip title="查看详情">
                    <a-button size="small" type="text" @click="view(record)">
                      <template #icon><EyeOutlined /></template>
                    </a-button>
                  </a-tooltip>
                  <a-tooltip title="编辑规则">
                    <a-button size="small" type="text" @click="edit(record)">
                      <template #icon><EditOutlined /></template>
                    </a-button>
                  </a-tooltip>
                  <a-tooltip title="测试规则">
                    <a-button size="small" type="text" @click="testRule(record)">
                      <template #icon><PlayCircleOutlined /></template>
                    </a-button>
                  </a-tooltip>
                  <a-dropdown>
                    <a-button size="small" type="text">
                      <template #icon><MoreOutlined /></template>
                    </a-button>
                    <template #overlay>
                      <a-menu>
                        <a-menu-item @click="duplicateRule(record)">
                          <CopyOutlined />
                          复制规则
                        </a-menu-item>
                        <a-menu-item @click="exportSingleRule(record)">
                          <ExportOutlined />
                          导出规则
                        </a-menu-item>
                        <a-menu-divider />
                        <a-menu-item @click="deleteRule(record)" danger>
                          <DeleteOutlined />
                          删除规则
                        </a-menu-item>
                      </a-menu>
                    </template>
                  </a-dropdown>
                </a-space>
              </template>
            </template>
          </a-table>
        </a-card>
      </div>

      <!-- 规则详情抽屉 -->
      <a-drawer
        v-model:open="showDetail"
        width="1000px"
        :maskClosable="true"
        class="rule-detail-drawer"
      >
        <template #title>
          <div class="drawer-title">
            <FileTextOutlined class="title-icon" />
            <span>规则详情</span>
            <a-tag v-if="selectedRule" :color="getSeverityColor(selectedRule.severity)" class="title-tag">
              {{ getSeverityLabel(selectedRule.severity) }}
            </a-tag>
          </div>
        </template>

        <div v-if="selectedRule" class="rule-detail-content">
          <!-- 基本信息 -->
          <a-card title="基本信息" size="small" class="detail-card">
            <a-descriptions :column="2" bordered size="small">
              <a-descriptions-item label="规则编码">
                <a-tag color="blue" class="code-tag">{{ selectedRule.code }}</a-tag>
              </a-descriptions-item>
              <a-descriptions-item label="规则名称">
                <span class="rule-name">{{ selectedRule.name }}</span>
              </a-descriptions-item>
              <a-descriptions-item label="规则类型">
                <a-tag :color="getRuleTypeColor(selectedRule.rule_type)">
                  {{ getRuleTypeLabel(selectedRule.rule_type) }}
                </a-tag>
              </a-descriptions-item>
              <a-descriptions-item label="规则分类">
                <a-tag :color="getCategoryColor(selectedRule.category_id)">
                  {{ getCategoryLabel(selectedRule.category_id) }}
                </a-tag>
              </a-descriptions-item>
              <a-descriptions-item label="严重级别">
                <a-tag :color="getSeverityColor(selectedRule.severity)">
                  <template #icon>
                    <ExclamationCircleOutlined v-if="selectedRule.severity === 'block'" />
                    <WarningOutlined v-else-if="selectedRule.severity === 'warn'" />
                    <InfoCircleOutlined v-else />
                  </template>
                  {{ getSeverityLabel(selectedRule.severity) }}
                </a-tag>
              </a-descriptions-item>
              <a-descriptions-item label="启用状态">
                <a-tag :color="selectedRule.enabled ? 'green' : 'red'">
                  <template #icon>
                    <CheckCircleOutlined v-if="selectedRule.enabled" />
                    <StopOutlined v-else />
                  </template>
                  {{ selectedRule.enabled ? '启用' : '禁用' }}
                </a-tag>
              </a-descriptions-item>
              <a-descriptions-item label="版本号">
                <a-tag color="purple">v{{ selectedRule.version || 1 }}</a-tag>
              </a-descriptions-item>
              <a-descriptions-item label="更新时间">
                <div class="time-info">
                  <div>{{ formatTime(selectedRule.updated_at) }}</div>
                  <div class="time-relative">{{ getRelativeTime(selectedRule.updated_at) }}</div>
                </div>
              </a-descriptions-item>
            </a-descriptions>
          </a-card>

          <!-- 统计摘要 -->
          <a-card title="配置统计" size="small" class="detail-card">
            <a-row :gutter="16">
              <a-col :span="6">
                <a-statistic
                  title="触发事件"
                  :value="agg.triggers"
                  :value-style="{ color: '#1890ff' }"
                >
                  <template #prefix><ThunderboltOutlined /></template>
                </a-statistic>
              </a-col>
              <a-col :span="6">
                <a-statistic
                  title="条件数量"
                  :value="agg.conditions"
                  :value-style="{ color: '#52c41a' }"
                >
                  <template #prefix><FilterOutlined /></template>
                </a-statistic>
              </a-col>
              <a-col :span="6">
                <a-statistic
                  title="动作数量"
                  :value="agg.actions"
                  :value-style="{ color: '#722ed1' }"
                >
                  <template #prefix><PlayCircleOutlined /></template>
                </a-statistic>
              </a-col>
              <a-col :span="6">
                <a-statistic
                  title="命中次数"
                  :value="selectedRule.hit_count || 0"
                  :value-style="{ color: '#fa8c16' }"
                >
                  <template #prefix><AimOutlined /></template>
                </a-statistic>
              </a-col>
            </a-row>
          </a-card>

          <!-- 触发事件 -->
          <a-card title="触发事件" size="small" class="detail-card">
            <template #extra>
              <a-button size="small" @click="copyTriggers">
                <template #icon><CopyOutlined /></template>
                复制
              </a-button>
            </template>
            <a-list :data-source="ruleTriggers" size="small">
              <template #renderItem="{ item, index }">
                <a-list-item>
                  <a-list-item-meta>
                    <template #title>
                      <a-tag color="geekblue">{{ item.event_type }}</a-tag>
                    </template>
                    <template #description>
                      优先级: {{ item.priority }}
                    </template>
                  </a-list-item-meta>
                </a-list-item>
              </template>
            </a-list>
          </a-card>

          <!-- 条件配置 -->
          <a-card title="条件配置" size="small" class="detail-card">
            <template #extra>
              <a-space>
                <a-button size="small" @click="copyConditions">
                  <template #icon><CopyOutlined /></template>
                  复制JSON
                </a-button>
                <a-button size="small" @click="exportConditions">
                  <template #icon><ExportOutlined /></template>
                  导出
                </a-button>
              </a-space>
            </template>
            <a-collapse v-if="ruleConditions.length > 0" size="small">
              <a-collapse-panel
                v-for="(condition, index) in ruleConditions"
                :key="index"
                :header="`条件 ${index + 1} (优先级: ${condition.priority})`"
              >
                <pre class="json-display">{{ formatJson(condition.expression_json) }}</pre>
              </a-collapse-panel>
            </a-collapse>
            <a-empty v-else description="暂无条件配置" />
          </a-card>

          <!-- 动作配置 -->
          <a-card title="动作配置" size="small" class="detail-card">
            <template #extra>
              <a-space>
                <a-button size="small" @click="copyActions">
                  <template #icon><CopyOutlined /></template>
                  复制JSON
                </a-button>
                <a-button size="small" @click="exportActions">
                  <template #icon><ExportOutlined /></template>
                  导出
                </a-button>
              </a-space>
            </template>
            <a-list :data-source="ruleActions" size="small">
              <template #renderItem="{ item, index }">
                <a-list-item>
                  <a-list-item-meta>
                    <template #title>
                      <a-tag :color="getActionTypeColor(item.action_type)">
                        {{ getActionTypeLabel(item.action_type) }}
                      </a-tag>
                    </template>
                    <template #description>
                      <div class="action-template">{{ item.message_template }}</div>
                    </template>
                  </a-list-item-meta>
                </a-list-item>
              </template>
            </a-list>
            <a-empty v-if="ruleActions.length === 0" description="暂无动作配置" />
          </a-card>
        </div>
      </a-drawer>
      <!-- 导出配置模态框 -->
      <a-modal
        v-model:open="exportOpen"
        title="导出规则配置"
        @ok="doExport"
        @cancel="exportOpen = false"
        width="600px"
      >
        <div class="export-config">
          <a-form layout="vertical">
            <a-form-item label="导出格式">
              <a-radio-group v-model:value="exportFormat">
                <a-radio value="json">JSON 格式</a-radio>
                <a-radio value="csv">CSV 格式</a-radio>
              </a-radio-group>
            </a-form-item>
            <a-form-item label="导出字段">
              <a-checkbox-group v-model:value="exportFields" class="export-fields">
                <a-checkbox
                  v-for="field in fieldOptions"
                  :key="field.value"
                  :value="field.value"
                  class="field-checkbox"
                >
                  {{ field.label }}
                </a-checkbox>
              </a-checkbox-group>
            </a-form-item>
          </a-form>
        </div>
      </a-modal>

      <!-- 版本历史模态框 -->
      <a-modal
        v-model:open="versionHistoryVisible"
        title="版本历史"
        width="800px"
        :footer="null"
      >
        <div v-if="selectedRule" class="version-history">
          <a-timeline>
            <a-timeline-item
              v-for="version in versionHistory"
              :key="version.version"
              :color="version.version === selectedRule.version ? 'green' : 'blue'"
            >
              <template #dot>
                <ClockCircleOutlined v-if="version.version === selectedRule.version" />
              </template>
              <div class="version-item">
                <div class="version-header">
                  <a-tag color="purple">v{{ version.version }}</a-tag>
                  <span class="version-time">{{ formatTime(version.created_at) }}</span>
                  <a-tag v-if="version.version === selectedRule.version" color="green">当前版本</a-tag>
                </div>
                <div class="version-description">{{ version.description || '无描述' }}</div>
                <div class="version-actions">
                  <a-button
                    size="small"
                    type="link"
                    @click="compareVersion(version)"
                    :disabled="version.version === selectedRule.version"
                  >
                    与当前版本比较
                  </a-button>
                  <a-button
                    size="small"
                    type="link"
                    @click="rollbackVersion(version)"
                    :disabled="version.version === selectedRule.version"
                  >
                    回滚到此版本
                  </a-button>
                </div>
              </div>
            </a-timeline-item>
          </a-timeline>
        </div>
      </a-modal>
    </div>
  </BasicLayout>
</template>

<script setup lang="ts">
import BasicLayout from '@/layouts/BasicLayout.vue'
import { ref, onMounted, computed, h } from 'vue'
import { supabase } from '@/lib/supabase'
import { message } from 'ant-design-vue'
import { toggleRuleEnabled } from '@/services/supabaseSdk'
import ApiService from '@/services/apiService'
import { useAuthStore } from '@/stores/auth'
import {
  SettingOutlined, ReloadOutlined, ImportOutlined, ExportOutlined, PlusOutlined,
  PlusCircleOutlined, ClockCircleOutlined, SearchOutlined, ClearOutlined,
  CheckCircleOutlined, StopOutlined, DeleteOutlined, FileTextOutlined,
  EyeOutlined, EditOutlined, PlayCircleOutlined, MoreOutlined, CopyOutlined,
  ExclamationCircleOutlined, WarningOutlined, InfoCircleOutlined,
  ThunderboltOutlined, FilterOutlined, AimOutlined
} from '@ant-design/icons-vue'

// 响应式数据
const loading = ref(false)
const rows = ref<any[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(15)

// 认证状态管理
const authStore = useAuthStore()

// 筛选条件
const keyword = ref('')
const enabled = ref<any>(undefined)
const severity = ref<string | undefined>(undefined)
const categoryFilter = ref<string | undefined>(undefined)
const ruleTypeFilter = ref<string | undefined>(undefined)
const updatedRange = ref<any[]>([])

// 界面状态
const togglingId = ref<number | null>(null)
const showDetail = ref(false)
const selectedRule = ref<any | null>(null)
const selectedRowKeys = ref<number[]>([])
const exportOpen = ref(false)
const versionHistoryVisible = ref(false)

// 统计数据
const monthlyStats = ref({
  newRules: 0,
  pendingReview: 0
})

// 规则详情数据
const agg = ref<{ triggers: number; conditions: number; actions: number }>({
  triggers: 0,
  conditions: 0,
  actions: 0
})
const ruleConditions = ref<any[]>([])
const ruleActions = ref<any[]>([])
const ruleTriggers = ref<any[]>([])
const versionHistory = ref<any[]>([])

// 导出配置
const exportFormat = ref<'json'|'csv'>('json')
const exportFields = ref<string[]>([
  'id', 'code', 'name', 'rule_type', 'severity', 'enabled', 'version', 'updated_at'
])

// 选项配置
const enabledOptions = [
  { label: '启用', value: true },
  { label: '停用', value: false }
]

const severityOptions = [
  { label: '信息', value: 'info' },
  { label: '警告', value: 'warn' },
  { label: '阻断', value: 'block' }
]

const fieldOptions = [
  { label: 'ID', value: 'id' },
  { label: '编码', value: 'code' },
  { label: '名称', value: 'name' },
  { label: '类型', value: 'rule_type' },
  { label: '分类', value: 'category_id' },
  { label: '严重级', value: 'severity' },
  { label: '启用状态', value: 'enabled' },
  { label: '版本', value: 'version' },
  { label: '更新时间', value: 'updated_at' }
]

// 表格列配置
const enhancedColumns = [
  {
    title: '规则编号',
    key: 'code',
    width: 200,
    fixed: 'left',
    customRender: ({ record }: any) => {
      return h('div', {
        class: 'flex justify-center'
      }, [
        h('div', {
          class: 'rule-code-badge font-mono text-xs'
        }, record.code)
      ])
    }
  },
  {
    title: '规则信息',
    key: 'name',
    width: 300,
    customRender: ({ record }: any) => {
      // 提取纯粹的规则名称，去掉类型描述部分
      const cleanName = record.name ? record.name.split(' - ')[0] : '未命名规则'
      return h('div', { class: 'space-y-1' }, [
        h('div', { class: 'text-sm text-gray-900 font-medium' }, cleanName),
        h('div', { class: 'text-xs text-gray-500 line-clamp-2' }, record.description || '暂无描述')
      ])
    }
  },
  {
    title: '规则类型',
    key: 'rule_type',
    width: 140,
    customRender: ({ record }: any) => {
      const typeName = getRuleTypeName(record.rule_type)
      const colorMap = {
        'drug_gender': 'pink',
        'drug_age': 'orange',
        'drug_children_only': 'green',
        'drug_payment_course': 'purple',
        'drug_insurance_type': 'blue',
        'drug_diagnosis': 'red',
        'drug_dosage_form': 'cyan',
        'drug_route': 'geekblue',
        'drug_indication': 'magenta'
      }
      const color = colorMap[record.rule_type] || 'default'
      return h('a-tag', { color }, typeName)
    },
    filters: [
      { text: '性别限制', value: 'drug_gender' },
      { text: '年龄限制', value: 'drug_age' },
      { text: '儿童专用', value: 'drug_children_only' },
      { text: '儿童限制', value: 'drug_children_limit' },
      { text: '支付疗程限制', value: 'drug_payment_course' },
      { text: '保险类型限制', value: 'drug_insurance_type' },
      { text: '诊断限制', value: 'drug_diagnosis' },
      { text: '剂型限制', value: 'drug_dosage_form' },
      { text: '给药途径', value: 'drug_route' },
      { text: '适应症限制', value: 'drug_indication' }
    ]
  },
  {
    title: '严重级别',
    key: 'severity',
    width: 100,
    customRender: ({ record }: any) => {
      const severityInfo = getSeverityInfo(record.severity)
      const iconMap = {
        'info': h(InfoCircleOutlined),
        'warn': h(WarningOutlined),
        'block': h(ExclamationCircleOutlined)
      }
      return h('a-tag', {
        color: severityInfo.color,
        class: 'flex items-center gap-1'
      }, [
        iconMap[record.severity] || null,
        severityInfo.label
      ])
    },
    filters: [
      { text: '信息', value: 'info' },
      { text: '警告', value: 'warn' },
      { text: '拦截', value: 'block' }
    ]
  },
  {
    title: '状态',
    key: 'enabled',
    width: 80,
    customRender: ({ record }: any) => {
      return h('a-switch', {
        checked: record.enabled,
        size: 'small',
        onChange: (checked: boolean) => toggleRuleEnabled(record.id, checked)
      })
    }
  },
  {
    title: '版本',
    key: 'version',
    width: 80,
    customRender: ({ record }: any) => {
      return h('a-tag', { color: 'purple' }, `v${record.version || '1'}`)
    }
  },
  {
    title: '更新时间',
    key: 'updated_at',
    width: 160,
    sorter: true,
    customRender: ({ record }: any) => {
      return h('div', { class: 'space-y-1' }, [
        h('div', { class: 'text-sm' }, formatTime(record.updated_at)),
        h('div', { class: 'text-xs text-gray-500' }, getRelativeTime(record.updated_at))
      ])
    }
  },
  {
    title: '操作',
    key: 'actions',
    width: 200,
    fixed: 'right'
  }
]

// 分页配置
const paginationConfig = computed(() => ({
  current: page.value,
  pageSize: pageSize.value,
  total: total.value,
  showSizeChanger: true,
  showQuickJumper: true,
  showTotal: (total: number, range: [number, number]) =>
    `第 ${range[0]}-${range[1]} 条，共 ${total} 条规则`,
  pageSizeOptions: ['10', '15', '20', '30', '50', '100'],
  size: 'default',
  position: ['bottomCenter']
}))

// 行选择配置
const rowSelection = {
  selectedRowKeys: selectedRowKeys.value,
  onChange: (keys: number[]) => {
    selectedRowKeys.value = keys
  },
  getCheckboxProps: (record: any) => ({
    disabled: false,
    name: record.code
  })
}

// 工具方法
const formatTime = (timeStr: string) => {
  if (!timeStr) return '-'
  return new Date(timeStr).toLocaleString('zh-CN')
}

const getRelativeTime = (timeStr: string) => {
  if (!timeStr) return ''
  const now = new Date()
  const time = new Date(timeStr)
  const diff = now.getTime() - time.getTime()
  const days = Math.floor(diff / (1000 * 60 * 60 * 24))
  if (days === 0) return '今天'
  if (days === 1) return '昨天'
  if (days < 7) return `${days}天前`
  if (days < 30) return `${Math.floor(days / 7)}周前`
  return `${Math.floor(days / 30)}个月前`
}

const getRuleTypeColor = (type: string) => {
  const colorMap: Record<string, string> = {
    // 药品相关
    'drug_gender': 'pink',
    'drug_age': 'orange',
    'drug_children_only': 'green',
    'drug_children_limit': 'green',
    'drug_payment_course': 'purple',
    'drug_insurance_type': 'blue',
    'drug_diagnosis': 'red',
    'drug_dosage_form': 'cyan',
    'drug_route': 'geekblue',
    'drug_indication': 'magenta',

    // 其他（保留原有）
    'visit_type': 'orange',
    'hospital_level': 'purple',
    'duration': 'cyan',
    'surgery_pricing': 'red'
  }
  return colorMap[type] || 'default'
}

const getRuleTypeLabel = (type: string) => {
  const labelMap: Record<string, string> = {
    // 药品相关
    'drug_gender': '性别限制',
    'drug_age': '年龄限制',
    'drug_children_only': '儿童专用',
    'drug_children_limit': '儿童限制',
    'drug_payment_course': '支付疗程限制',
    'drug_insurance_type': '保险类型限制',
    'drug_diagnosis': '诊断限制',
    'drug_dosage_form': '剂型限制',
    'drug_route': '给药途径',
    'drug_indication': '适应症限制',

    // 其他（保留原有）
    'visit_type': '就诊方式限制',
    'hospital_level': '机构级别限制',
    'duration': '疗程限制',
    'surgery_pricing': '手术折价'
  }
  return labelMap[type] || type || '未分类'
}

const getCategoryColor = (categoryId: any) => {
  const colorMap: Record<string, string> = {
    'batch_1': 'blue',
    'batch_2': 'green',
    'batch_3': 'orange',
    'batch_4': 'purple',
    'batch_5': 'cyan'
  }
  return colorMap[categoryId] || 'default'
}

const getCategoryLabel = (categoryId: any) => {
  const labelMap: Record<string, string> = {
    'batch_1': '第一批',
    'batch_2': '第二批',
    'batch_3': '第三批',
    'batch_4': '第四批',
    'batch_5': '第五批'
  }
  return labelMap[categoryId] || '未分类'
}

const getSeverityColor = (severity: string) => {
  const colorMap: Record<string, string> = {
    'info': 'blue',
    'warn': 'orange',
    'block': 'red'
  }
  return colorMap[severity] || 'default'
}

const getSeverityLabel = (severity: string) => {
  const labelMap: Record<string, string> = {
    'info': '信息',
    'warn': '警告',
    'block': '阻断'
  }
  return labelMap[severity] || severity
}

const getActionTypeColor = (actionType: string) => {
  const colorMap: Record<string, string> = {
    'intercept': 'red',
    'warn': 'orange',
    'notify': 'blue'
  }
  return colorMap[actionType] || 'default'
}

const getActionTypeLabel = (actionType: string) => {
  const labelMap: Record<string, string> = {
    'intercept': '拦截',
    'warn': '警告',
    'notify': '通知'
  }
  return labelMap[actionType] || actionType
}

// 规则类型映射
const ruleTypeMap = {
  'drug_gender': '性别限制',
  'drug_age': '年龄限制',
  'drug_children_only': '儿童专用',
  'drug_payment_course': '支付疗程限制',
  'drug_insurance_type': '保险类型限制',
  'drug_diagnosis': '诊断限制',
  'drug_dosage_form': '剂型限制',
  'drug_route': '给药途径',
  'drug_indication': '适应症限制'
}



// 严重级别映射
const severityMap = {
  'info': { label: '信息', color: 'blue' },
  'warn': { label: '警告', color: 'orange' },
  'block': { label: '拦截', color: 'red' }
}

// 获取规则类型中文名称
function getRuleTypeName(type: string) {
  return ruleTypeMap[type] || type
}

// 获取严重级别信息
function getSeverityInfo(severity: string) {
  return severityMap[severity] || { label: severity, color: 'default' }
}



// 数据加载方法
async function load() {
  try {
    loading.value = true
    const pageSizeVal = pageSize.value

    // 构建查询参数
    const params = new URLSearchParams({
      page: page.value.toString(),
      page_size: pageSizeVal.toString()
    })

    // 应用筛选条件
    if (keyword.value) {
      params.append('search', keyword.value)
    }
    if (enabled.value !== undefined) {
      params.append('enabled', enabled.value.toString())
    }
    if (severity.value) {
      params.append('severity', severity.value)
    }
    if (ruleTypeFilter.value) {
      params.append('rule_type', ruleTypeFilter.value)
    }

    // 使用ApiService调用API，自动处理认证和token刷新
    const data = await ApiService.get(`/api/rules/?${params.toString()}`)

    // 处理分页响应格式
    if (data.data && Array.isArray(data.data)) {
      rows.value = data.data
      total.value = data.total || 0
    } else if (Array.isArray(data)) {
      // 兼容旧格式
      rows.value = data
      total.value = data.length
    } else {
      rows.value = []
      total.value = 0
    }

    // 加载月度统计
    await loadMonthlyStats()
  } catch (error: any) {
    console.error('加载规则失败:', error)

    // 检查是否是认证/权限错误
    if (error.response?.status === 401) {
      message.error('登录已过期，请重新登录')
      authStore.signOut()
      window.location.href = '/login'
    } else if (error.response?.status === 403) {
      message.error('没有权限访问该资源，请使用有权限的账号或联系管理员')
    } else {
      message.error('加载规则失败，请检查网络连接')
    }

    // 如果API调用失败，尝试使用空数据
    rows.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

async function loadMonthlyStats() {
  try {
    const now = new Date()
    const startOfMonth = new Date(now.getFullYear(), now.getMonth(), 1).toISOString()

    const { count: newRules } = await supabase
      .from('yibao_rules')
      .select('id', { count: 'exact', head: true })
      .gte('created_at', startOfMonth)

    monthlyStats.value = {
      newRules: newRules || 0,
      pendingReview: 0 // 这里可以根据实际业务逻辑计算
    }
  } catch (error) {
    console.error('加载月度统计失败:', error)
  }
}

// 表格事件处理
function onTableChange(pagination: any, filters: any, sorter: any) {
  page.value = pagination.current
  pageSize.value = pagination.pageSize

  // 处理筛选
  if (filters.rule_type) {
    ruleTypeFilter.value = filters.rule_type[0]
  }
  if (filters.severity) {
    severity.value = filters.severity[0]
  }

  load()
}

function resetFilters() {
  keyword.value = ''
  enabled.value = undefined
  severity.value = undefined
  categoryFilter.value = undefined
  ruleTypeFilter.value = undefined
  updatedRange.value = []
  page.value = 1
  load()
}

function clearFilters() {
  resetFilters()
}

// 快速筛选函数
function quickFilter(type: string) {
  if (type === 'all') {
    ruleTypeFilter.value = undefined
  } else {
    ruleTypeFilter.value = type
  }
  page.value = 1
  load()
}

function quickFilterSeverity(severityLevel: string) {
  if (severity.value === severityLevel) {
    severity.value = undefined
  } else {
    severity.value = severityLevel
  }
  page.value = 1
  load()
}

function quickFilterEnabled(enabledState: boolean) {
  if (enabled.value === enabledState) {
    enabled.value = undefined
  } else {
    enabled.value = enabledState
  }
  page.value = 1
  load()
}

// 规则操作方法
async function toggle(row: any, val: boolean) {
  try {
    togglingId.value = row.id
    const updated = await toggleRuleEnabled(row.id, val)
    row.enabled = updated?.enabled ?? val
    message.success(`规则 ${row.code} 已${row.enabled ? '启用' : '停用'}`)
  } catch (e: any) {
    message.error(e?.message || '切换启停失败')
    row.enabled = !val
  } finally {
    togglingId.value = null
  }
}

function openCreate() {
  window.location.href = '/rules/edit'
}

function openImport() {
  window.location.href = '/rules/import'
}

function edit(row: any) {
  const query: any = row?.id ? { id: row.id } : {}
  window.location.href = `/rules/edit${Object.keys(query).length ? ('?' + new URLSearchParams(query).toString()) : ''}`
}

async function testRule(rule: any) {
  message.loading(`正在测试规则 ${rule.code}...`, 2)
  // 这里可以调用规则测试API
  setTimeout(() => {
    message.success('规则测试完成，运行正常')
  }, 2000)
}

async function duplicateRule(rule: any) {
  try {
    const newRule = {
      ...rule,
      id: undefined,
      code: `${rule.code}_COPY`,
      name: `${rule.name} (副本)`,
      enabled: false,
      version: 1
    }

    const { error } = await supabase.from('yibao_rules').insert(newRule)
    if (error) throw error

    message.success('规则复制成功')
    load()
  } catch (error) {
    console.error('复制规则失败:', error)
    message.error('复制规则失败')
  }
}

function exportSingleRule(rule: any) {
  const data = [rule]
  downloadJSON(`rule_${rule.code}_export.json`, data)
}

async function deleteRule(rule: any) {
  try {
    const { error } = await supabase
      .from('yibao_rules')
      .delete()
      .eq('id', rule.id)

    if (error) throw error

    message.success(`规则 ${rule.code} 删除成功`)
    load()
  } catch (error) {
    console.error('删除规则失败:', error)
    message.error('删除规则失败')
  }
}

// 批量操作方法
async function batchEnable(flag: boolean) {
  if (!selectedRowKeys.value.length) return

  try {
    await Promise.all(
      selectedRowKeys.value.map(id => toggleRuleEnabled(id as any, flag))
    )
    message.success(`批量${flag ? '启用' : '禁用'}完成`)
    selectedRowKeys.value = []
    load()
  } catch (e: any) {
    message.error(e?.message || '批量操作失败')
  }
}

async function batchDelete() {
  if (!selectedRowKeys.value.length) return

  try {
    const { error } = await supabase
      .from('yibao_rules')
      .delete()
      .in('id', selectedRowKeys.value)

    if (error) throw error

    message.success(`批量删除 ${selectedRowKeys.value.length} 条规则成功`)
    selectedRowKeys.value = []
    load()
  } catch (error) {
    console.error('批量删除失败:', error)
    message.error('批量删除失败')
  }
}

// 规则详情相关方法
async function view(row: any) {
  selectedRule.value = row
  showDetail.value = true
  await Promise.all([
    loadAggregates(row.id),
    loadDetailLists(row.id),
    loadVersionHistory(row.id)
  ])
}

function showVersionHistory(rule: any) {
  selectedRule.value = rule
  versionHistoryVisible.value = true
  loadVersionHistory(rule.id)
}

async function loadVersionHistory(ruleId: number) {
  try {
    // 模拟版本历史数据，实际应该从数据库加载
    versionHistory.value = [
      {
        version: 3,
        description: '优化规则条件，提高准确性',
        created_at: new Date().toISOString(),
        created_by: '管理员'
      },
      {
        version: 2,
        description: '修复规则逻辑错误',
        created_at: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString(),
        created_by: '管理员'
      },
      {
        version: 1,
        description: '初始版本',
        created_at: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString(),
        created_by: '管理员'
      }
    ]
  } catch (error) {
    console.error('加载版本历史失败:', error)
  }
}

function compareVersion(version: any) {
  message.info(`版本比较功能开发中...`)
}

async function rollbackVersion(version: any) {
  try {
    // 这里应该实现版本回滚逻辑
    message.success(`已回滚到版本 v${version.version}`)
    versionHistoryVisible.value = false
    load()
  } catch (error) {
    message.error('版本回滚失败')
  }
}

async function loadAggregates(ruleId: number) {
  try {
    const [{ count: triggers }, { count: conditions }, { count: actions }] = await Promise.all([
      supabase.from('yibao_rule_triggers').select('id', { count: 'exact', head: true }).eq('rule_id', ruleId),
      supabase.from('yibao_rule_conditions').select('id', { count: 'exact', head: true }).eq('rule_id', ruleId),
      supabase.from('yibao_rule_actions').select('id', { count: 'exact', head: true }).eq('rule_id', ruleId)
    ])
    agg.value = {
      triggers: Number(triggers || 0),
      conditions: Number(conditions || 0),
      actions: Number(actions || 0)
    }
  } catch (error) {
    console.error('加载统计数据失败:', error)
    agg.value = { triggers: 0, conditions: 0, actions: 0 }
  }
}

async function loadDetailLists(ruleId: number) {
  try {
    const [{ data: conds }, { data: acts }, { data: trigs }] = await Promise.all([
      supabase.from('yibao_rule_conditions').select('id, priority, expression_json').eq('rule_id', ruleId).order('priority', { ascending: true }),
      supabase.from('yibao_rule_actions').select('id, action_type, message_template').eq('rule_id', ruleId),
      supabase.from('yibao_rule_triggers').select('event_type, priority').eq('rule_id', ruleId).order('priority', { ascending: true })
    ])
    ruleConditions.value = Array.isArray(conds) ? conds : []
    ruleActions.value = Array.isArray(acts) ? acts : []
    ruleTriggers.value = Array.isArray(trigs) ? trigs : []
  } catch (error) {
    console.error('加载详情数据失败:', error)
    ruleConditions.value = []
    ruleActions.value = []
    ruleTriggers.value = []
  }
}

// 复制和导出方法
function copyToClipboard(text: string) {
  navigator.clipboard?.writeText(text)
    .then(() => message.success('已复制到剪贴板'))
    .catch(() => message.error('复制失败'))
}

function copyTriggers() {
  copyToClipboard(JSON.stringify(ruleTriggers.value, null, 2))
}

function copyConditions() {
  copyToClipboard(JSON.stringify(ruleConditions.value, null, 2))
}

function copyActions() {
  copyToClipboard(JSON.stringify(ruleActions.value, null, 2))
}

function downloadJSON(filename: string, content: any) {
  const blob = new Blob([JSON.stringify(content, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

function exportConditions() {
  downloadJSON(`rule_${selectedRule.value?.code || selectedRule.value?.id}_conditions.json`, ruleConditions.value)
}

function exportActions() {
  downloadJSON(`rule_${selectedRule.value?.code || selectedRule.value?.id}_actions.json`, ruleActions.value)
}

function formatJson(data: any) {
  try {
    return JSON.stringify(data, null, 2)
  } catch {
    return String(data)
  }
}



// 导入导出方法
async function beforeImport(file: File) {
  try {
    const text = await file.text()
    const json = JSON.parse(text)
    const list = Array.isArray(json) ? json : [json]
    let ok = 0
    let failed = 0

    for (const item of list) {
      try {
        // 检查必要字段
        if (!item.code || !item.name) {
          failed++
          continue
        }

        // 导入规则主表
        const { error } = await supabase.from('yibao_rules').insert({
          code: item.code,
          name: item.name,
          rule_type: item.rule_type || null,
          severity: item.severity || 'warn',
          enabled: item.enabled ?? true,
          version: item.version ?? 1,
          metadata: item.metadata || {},
          category_id: item.category_id || null
        })

        if (!error) {
          ok++
        } else {
          failed++
          console.error('导入规则失败:', item.code, error)
        }
      } catch (error) {
        failed++
        console.error('处理规则失败:', item.code, error)
      }
    }

    if (ok > 0) {
      message.success(`导入完成：成功 ${ok} 条，失败 ${failed} 条`)
      load()
    } else {
      message.error(`导入失败：${failed} 条规则导入失败`)
    }
  } catch (e: any) {
    message.error(e?.message || '文件解析失败')
  }
  return false
}

function openExport() {
  exportOpen.value = true
}

function toCSV(arr: any[], fields: string[]) {
  const lines: string[] = []
  lines.push(fields.join(','))

  for (const r of arr) {
    const row = fields.map(f => {
      const v = (r as any)[f]
      if (v == null) return ''
      const s = String(v).replace(/"/g, '""')
      return /[",\n]/.test(s) ? `"${s}"` : s
    })
    lines.push(row.join(','))
  }

  return lines.join('\n')
}

function doExport() {
  const data = rows.value.map(r => {
    const obj: any = {}
    exportFields.value.forEach(f => obj[f] = (r as any)[f])
    return obj
  })

  if (exportFormat.value === 'json') {
    downloadJSON(`rules_export_${Date.now()}.json`, data)
  } else {
    const csv = toCSV(data, exportFields.value)
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `rules_export_${Date.now()}.csv`
    a.click()
    URL.revokeObjectURL(url)
  }

  exportOpen.value = false
  message.success('导出完成')
}

// 生命周期
onMounted(() => {
  load()
})
</script>

<style scoped>
/* 表格优化样式 */
:deep(.ant-table) {
  border-radius: 8px;
  overflow: hidden;
  box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px 0 rgba(0, 0, 0, 0.06);
}

:deep(.ant-table-thead > tr > th) {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  font-weight: 600;
  border: none;
}

:deep(.ant-table-tbody > tr:hover > td) {
  background-color: #f8fafc !important;
}

:deep(.ant-table-tbody > tr > td) {
  border-bottom: 1px solid #f1f5f9;
  padding: 12px 16px;
}

/* 文本截断样式 */
.line-clamp-2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

/* 筛选区域样式 */
.filter-section {
  background: linear-gradient(135deg, #f8fafc 0%, #e2e8f0 100%);
  border-radius: 12px;
  border: 1px solid #e2e8f0;
}

/* 统计卡片样式 */
:deep(.ant-statistic-content) {
  color: #1e293b;
  font-weight: 600;
}

/* 分页样式优化 */
:deep(.ant-pagination) {
  margin-top: 24px;
  text-align: center;
}

:deep(.ant-pagination-item-active) {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border-color: #667eea;
}

:deep(.ant-pagination-item-active a) {
  color: white;
}

/* 标签样式优化 */
:deep(.ant-tag) {
  border-radius: 6px;
  font-weight: 500;
  padding: 2px 8px;
}

/* 开关样式 */
:deep(.ant-switch-checked) {
  background-color: #10b981;
}

/* 加载状态优化 */
:deep(.ant-spin-container) {
  min-height: 400px;
}

/* 规则编号样式 */
.rule-code-badge {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
  font-weight: bold;
  padding: 8px 12px;
  border-radius: 8px;
  font-size: 11px;
  letter-spacing: 0.3px;
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.15);
  transition: all 0.2s ease;
  display: inline-block;
  text-align: center;
  white-space: nowrap;
  max-width: 180px;
  overflow: hidden;
  text-overflow: ellipsis;
}

.rule-code-badge:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
}

/* 规则类型标签优化 */
:deep(.ant-tag) {
  font-weight: 500;
  border-radius: 8px;
  padding: 4px 12px;
  font-size: 12px;
}

/* 表格行优化 */
:deep(.ant-table-tbody > tr) {
  transition: all 0.2s ease;
}

:deep(.ant-table-tbody > tr:hover) {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
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

/* 危险类型筛选（拦截规则） */
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

/* 成功类型筛选（已启用） */
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

/* 快速筛选区域整体样式 */
.quick-filters {
  background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
  border-radius: 16px;
  padding: 16px 20px;
  border: 1px solid #e2e8f0;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
}

/* 响应式优化 */
@media (max-width: 768px) {
  .filter-tag {
    padding: 6px 12px;
    font-size: 12px;
  }

  .quick-filters {
    padding: 12px 16px;
  }
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

/* 禁用状态（如果需要） */
.filter-tag.disabled {
  opacity: 0.5;
  cursor: not-allowed;
  pointer-events: none;
}
</style>
