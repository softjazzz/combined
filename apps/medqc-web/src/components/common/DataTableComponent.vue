<template>
  <div class="data-table-container">
    <!-- 表格工具栏 -->
    <div
      v-if="showToolbar"
      class="table-toolbar"
    >
      <div class="toolbar-left">
        <slot name="toolbar-left">
          <!-- 批量操作 -->
          <div
            v-if="selectedRowKeys.length > 0"
            class="batch-actions"
          >
            <span class="batch-info"> 已选择 {{ selectedRowKeys.length }} 项 </span>
            <a-space size="small">
              <a-button
                v-for="action in batchActions"
                :key="action.key"
                :type="action.type || 'default'"
                :danger="action.danger"
                :loading="action.loading"
                :disabled="action.disabled"
                @click="handleBatchAction(action)"
              >
                <component
                  :is="action.icon"
                  v-if="action.icon"
                />
                {{ action.text }}
              </a-button>
            </a-space>
          </div>

          <!-- 搜索框 -->
          <div
            v-if="showSearch"
            class="search-box"
          >
            <a-input-search
              v-model:value="searchValue"
              :placeholder="searchPlaceholder"
              :loading="searchLoading"
              style="width: 280px"
              @search="handleSearch"
              @change="handleSearchChange"
            />
          </div>
        </slot>
      </div>

      <div class="toolbar-right">
        <slot name="toolbar-right">
          <a-space size="small">
            <!-- 筛选器 -->
            <a-dropdown
              v-if="filters.length > 0"
              trigger="click"
            >
              <a-button>
                <FilterOutlined />
                筛选
                <span
                  v-if="activeFilters.length > 0"
                  class="filter-count"
                >
                  {{ activeFilters.length }}
                </span>
              </a-button>
              <template #overlay>
                <div class="filter-dropdown">
                  <div
                    v-for="filter in filters"
                    :key="filter.key"
                    class="filter-item"
                  >
                    <div class="filter-label">
                      {{ filter.label }}
                    </div>
                    <a-select
                      v-if="filter.type === 'select'"
                      :value="getSelectFilterValue(filter.key)"
                      :placeholder="filter.placeholder"
                      :options="filter.options"
                      style="width: 160px"
                      allow-clear
                      @update:value="(value) => setSelectFilterValue(filter.key, value)"
                    />
                    <a-date-picker
                      v-else-if="filter.type === 'date'"
                      :value="getDateFilterValue(filter.key)"
                      :placeholder="filter.placeholder"
                      style="width: 160px"
                      @update:value="(value) => setDateFilterValue(filter.key, value)"
                    />
                    <a-input
                      v-else
                      :value="getInputFilterValue(filter.key)"
                      :placeholder="filter.placeholder"
                      style="width: 160px"
                      @update:value="(value) => setInputFilterValue(filter.key, value)"
                    />
                  </div>
                </div>
              </template>
            </a-dropdown>

            <!-- 列设置 -->
            <a-dropdown
              v-if="showColumnSettings"
              trigger="click"
            >
              <a-button>
                <SettingOutlined />
                列设置
              </a-button>
              <template #overlay>
                <div class="column-settings">
                  <a-checkbox-group v-model:value="visibleColumns">
                    <div
                      v-for="column in configurableColumns"
                      :key="column.key"
                      class="column-item"
                    >
                      <a-checkbox :value="column.key">
                        {{ column.title }}
                      </a-checkbox>
                    </div>
                  </a-checkbox-group>
                </div>
              </template>
            </a-dropdown>

            <!-- 刷新 -->
            <a-button
              :loading="refreshing"
              @click="handleRefresh"
            >
              <ReloadOutlined />
              刷新
            </a-button>

            <!-- 导出 -->
            <a-button
              v-if="showExport"
              :loading="exporting"
              @click="handleExport"
            >
              <DownloadOutlined />
              导出
            </a-button>
          </a-space>
        </slot>
      </div>
    </div>

    <!-- 数据表格 -->
    <a-table
      v-bind="tableProps"
      :columns="visibleTableColumns"
      :data-source="processedDataSource"
      :loading="loading"
      :pagination="paginationConfig"
      :row-selection="rowSelection"
      :scroll="scroll"
      :size="size"
      :bordered="bordered"
      :class="tableClass"
      @change="handleTableChange"
    >
      <!-- 传递所有插槽 -->
      <template
        v-for="(_, name) in $slots"
        :key="name"
        #[name]="slotProps"
      >
        <slot
          :name="name"
          v-bind="slotProps"
        />
      </template>
    </a-table>

    <!-- 空状态 -->
    <div
      v-if="!loading && processedDataSource.length === 0"
      class="empty-state"
    >
      <slot name="empty">
        <EmptyStateComponent
          :type="emptyType"
          :title="emptyTitle"
          :description="emptyDescription"
          :actions="emptyActions"
          @action="handleEmptyAction"
        />
      </slot>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import type { Component } from 'vue'
import dayjs, { type Dayjs } from 'dayjs'
import {
  FilterOutlined,
  SettingOutlined,
  ReloadOutlined,
  DownloadOutlined,
} from '@ant-design/icons-vue'
import EmptyStateComponent from './EmptyStateComponent.vue'
import type { TableColumnsType, TableProps } from 'ant-design-vue'

interface FilterItem {
  key: string
  label: string
  type: 'select' | 'input' | 'date'
  placeholder?: string
  options?: { label: string; value: string | number }[]
}

interface BatchAction {
  key: string
  text: string
  type?: 'primary' | 'default' | 'dashed' | 'text' | 'link'
  icon?: Component
  danger?: boolean
  loading?: boolean
  disabled?: boolean
  onClick?: (selectedKeys: string[]) => void
}

interface EmptyAction {
  key: string
  text: string
  type?: 'primary' | 'default' | 'dashed' | 'text' | 'link'
  icon?: Component
  size?: 'small' | 'middle' | 'large'
  loading?: boolean
  disabled?: boolean
  onClick?: () => void
}

type TableRecord = Record<string, unknown>
type FilterValue = string | number | Dayjs | undefined
type TableColumn = NonNullable<TableColumnsType<TableRecord>[number]>

const getColumnKey = (column: TableColumn): string | undefined => {
  const key = column.key ?? ('dataIndex' in column ? column.dataIndex : undefined)

  if (key === undefined || key === null) {
    return undefined
  }

  return Array.isArray(key) ? key.map((part) => String(part)).join('.') : String(key)
}

interface Props {
  // 基础属性
  columns: TableColumnsType<TableRecord>
  dataSource: TableRecord[]
  loading?: boolean
  size?: 'small' | 'middle' | 'large'
  bordered?: boolean

  // 分页配置
  pagination?: Record<string, unknown> | false

  // 选择配置
  rowSelection?: Record<string, unknown>

  // 工具栏配置
  showToolbar?: boolean
  showSearch?: boolean
  searchPlaceholder?: string
  showColumnSettings?: boolean
  showExport?: boolean

  // 筛选配置
  filters?: FilterItem[]

  // 批量操作
  batchActions?: BatchAction[]

  // 空状态配置
  emptyType?: 'empty' | 'search' | 'error'
  emptyTitle?: string
  emptyDescription?: string
  emptyActions?: EmptyAction[]

  // 滚动配置
  scroll?: { x?: number; y?: number }

  // 其他表格属性
  tableProps?: Partial<TableProps>
}

interface Emits {
  (e: 'change', pagination: unknown, filters: unknown, sorter: unknown): void
  (e: 'search', value: string): void
  (e: 'filter-change', filters: Record<string, unknown>): void
  (e: 'batch-action', action: BatchAction, selectedKeys: string[]): void
  (e: 'refresh'): void
  (e: 'export'): void
  (e: 'empty-action', action: EmptyAction): void
}

const props = withDefaults(defineProps<Props>(), {
  dataSource: () => [] as TableRecord[],
  loading: false,
  size: 'middle',
  bordered: false,
  showToolbar: true,
  showSearch: true,
  searchPlaceholder: '请输入关键词搜索',
  showColumnSettings: true,
  showExport: false,
  filters: () => [] as FilterItem[],
  batchActions: () => [] as BatchAction[],
  emptyType: 'empty',
  emptyTitle: '暂无数据',
  emptyDescription: '当前没有可显示的内容',
  emptyActions: () => [] as EmptyAction[],
  tableProps: () => ({}) as Partial<TableProps>,
})

const emit = defineEmits<Emits>()

// 响应式数据
const searchValue = ref('')
const searchLoading = ref(false)
const refreshing = ref(false)
const exporting = ref(false)
const selectedRowKeys = ref<string[]>([])
const filterValues = ref<Record<string, FilterValue>>({})
const visibleColumns = ref<string[]>([])

// 初始化可见列
onMounted(() => {
  visibleColumns.value = props.columns
    .map((col: TableColumn) => getColumnKey(col))
    .filter((key): key is string => Boolean(key))
})

// 计算属性
const configurableColumns = computed(() => {
  return props.columns.filter((col: TableColumn) => col.key !== 'actions' && !col.fixed)
})

const visibleTableColumns = computed(() => {
  return props.columns.filter((col: TableColumn) => {
    if (col.key === 'actions' || col.fixed) return true

    const columnKey = getColumnKey(col)
    return columnKey ? visibleColumns.value.includes(columnKey) : false
  })
})

const activeFilters = computed(() => {
  return Object.entries(filterValues.value)
    .filter(([_, value]) => value !== undefined && value !== null && value !== '')
    .map(([key, _]) => key)
})

const processedDataSource = computed(() => {
  let data = [...props.dataSource]

  // 搜索过滤
  if (searchValue.value) {
    const searchLower = searchValue.value.toLowerCase()
    data = data.filter((item) => {
      return Object.values(item).some((value) => String(value).toLowerCase().includes(searchLower))
    })
  }

  // 筛选器过滤
  if (activeFilters.value.length > 0) {
    data = data.filter((item) => {
      return activeFilters.value.every((key) => {
        const filterValue = filterValues.value[key]
        const itemValue = item[key]

        if (filterValue === undefined || filterValue === null || filterValue === '') {
          return true
        }

        return String(itemValue).includes(String(filterValue))
      })
    })
  }

  return data
})

const paginationConfig = computed(() => {
  if (props.pagination === false) return false

  return {
    showSizeChanger: true,
    showQuickJumper: true,
    showTotal: (total: number, range: [number, number]) =>
      `显示 ${range[0]}-${range[1]} 条，共 ${total} 条`,
    ...props.pagination,
  }
})

const rowSelection = computed(() => {
  if (!props.rowSelection) return undefined

  return {
    selectedRowKeys: selectedRowKeys.value,
    onChange: (keys: string[]) => {
      selectedRowKeys.value = keys
    },
    ...props.rowSelection,
  }
})

const tableClass = computed(() => [
  'enhanced-table',
  {
    'table-small': props.size === 'small',
    'table-large': props.size === 'large',
    'table-bordered': props.bordered,
  },
])

// 事件处理
const handleSearch = (value: string) => {
  searchLoading.value = true
  emit('search', value)

  // 模拟搜索延迟
  setTimeout(() => {
    searchLoading.value = false
  }, 300)
}

const handleSearchChange = (e: Event) => {
  const target = e.target as HTMLInputElement | null
  searchValue.value = target?.value ?? ''
}

const handleFilterChange = () => {
  emit('filter-change', filterValues.value)
}

const getSelectFilterValue = (key: string): string | number | undefined => {
  const value = filterValues.value[key]
  return typeof value === 'string' || typeof value === 'number' ? value : undefined
}

const setSelectFilterValue = (key: string, value: unknown) => {
  if (typeof value === 'string' || typeof value === 'number') {
    filterValues.value[key] = value
  } else {
    filterValues.value[key] = undefined
  }
  handleFilterChange()
}

const getDateFilterValue = (key: string): Dayjs | undefined => {
  const value = filterValues.value[key]
  return value && dayjs.isDayjs(value) ? value : undefined
}

const setDateFilterValue = (key: string, value: Dayjs | string | null | undefined) => {
  if (!value) {
    filterValues.value[key] = undefined
  } else if (dayjs.isDayjs(value)) {
    filterValues.value[key] = value
  } else {
    filterValues.value[key] = dayjs(value)
  }
  handleFilterChange()
}

const getInputFilterValue = (key: string): string => {
  const value = filterValues.value[key]
  if (value === undefined || value === null) return ''
  return String(value)
}

const setInputFilterValue = (key: string, value: string) => {
  filterValues.value[key] = value
  handleFilterChange()
}

const handleBatchAction = (action: BatchAction) => {
  if (action.onClick) {
    action.onClick(selectedRowKeys.value)
  }
  emit('batch-action', action, selectedRowKeys.value)
}

const handleRefresh = () => {
  refreshing.value = true
  emit('refresh')

  // 模拟刷新延迟
  setTimeout(() => {
    refreshing.value = false
  }, 500)
}

const handleExport = () => {
  exporting.value = true
  emit('export')

  // 模拟导出延迟
  setTimeout(() => {
    exporting.value = false
  }, 1000)
}

const handleTableChange = (pagination: unknown, filters: unknown, sorter: unknown) => {
  emit('change', pagination, filters, sorter)
}

const handleEmptyAction = (action: EmptyAction) => {
  if (action.onClick) {
    action.onClick()
  }
  emit('empty-action', action)
}

// 清空选择
const clearSelection = () => {
  selectedRowKeys.value = []
}

// 重置筛选
const resetFilters = () => {
  filterValues.value = {}
  searchValue.value = ''
}

// 暴露方法
defineExpose({
  clearSelection,
  resetFilters,
  selectedRowKeys,
})
</script>

<style scoped>
.data-table-container {
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
  overflow: hidden;
}

/* 工具栏样式 */
.table-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 24px;
  background: #fafafa;
  border-bottom: 1px solid #e8e8e8;
  flex-wrap: wrap;
  gap: 16px;
}

.toolbar-left {
  display: flex;
  align-items: center;
  gap: 16px;
  flex: 1;
}

.toolbar-right {
  display: flex;
  align-items: center;
  flex-shrink: 0;
}

/* 批量操作样式 */
.batch-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 16px;
  background: #e6f7ff;
  border-radius: 6px;
  border: 1px solid #91d5ff;
}

.batch-info {
  font-size: 14px;
  color: #2b6cf6;
  font-weight: 500;
}

/* 搜索框样式 */
.search-box {
  flex: 1;
  max-width: 300px;
}

/* 筛选下拉框样式 */
.filter-dropdown {
  padding: 16px;
  min-width: 200px;
  max-width: 300px;
}

.filter-item {
  margin-bottom: 16px;
}

.filter-item:last-child {
  margin-bottom: 0;
}

.filter-label {
  font-size: 14px;
  color: #666;
  margin-bottom: 8px;
  font-weight: 500;
}

.filter-count {
  display: inline-block;
  background: #2b6cf6;
  color: white;
  border-radius: 50%;
  width: 18px;
  height: 18px;
  line-height: 18px;
  text-align: center;
  font-size: 12px;
  margin-left: 4px;
}

/* 列设置样式 */
.column-settings {
  padding: 16px;
  min-width: 200px;
  max-height: 300px;
  overflow-y: auto;
}

.column-item {
  padding: 8px 0;
  border-bottom: 1px solid #f0f0f0;
}

.column-item:last-child {
  border-bottom: none;
}

/* 表格样式增强 */
:deep(.enhanced-table) {
  .ant-table-thead > tr > th {
    background: #fafafa;
    font-weight: 600;
    color: #262626;
    border-bottom: 2px solid #e8e8e8;
  }

  .ant-table-tbody > tr:hover > td {
    background: #f5f5f5;
  }

  .ant-table-tbody > tr > td {
    transition: background-color 0.2s ease;
  }

  .ant-table-row-selected > td {
    background: #e6f7ff !important;
  }

  .ant-table-row-selected:hover > td {
    background: #bae7ff !important;
  }
}

/* 表格尺寸样式 */
:deep(.table-small) {
  .ant-table-thead > tr > th,
  .ant-table-tbody > tr > td {
    padding: 8px 12px;
    font-size: 12px;
  }
}

:deep(.table-large) {
  .ant-table-thead > tr > th,
  .ant-table-tbody > tr > td {
    padding: 16px 24px;
    font-size: 16px;
  }
}

/* 边框样式 */
:deep(.table-bordered) {
  .ant-table-thead > tr > th,
  .ant-table-tbody > tr > td {
    border-right: 1px solid #e8e8e8;
  }
}

/* 空状态样式 */
.empty-state {
  padding: 40px 20px;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .table-toolbar {
    flex-direction: column;
    align-items: stretch;
    gap: 12px;
  }

  .toolbar-left {
    flex-direction: column;
    align-items: stretch;
    gap: 12px;
  }

  .toolbar-right {
    justify-content: center;
  }

  .batch-actions {
    flex-direction: column;
    align-items: stretch;
    gap: 8px;
  }

  .search-box {
    max-width: none;
  }
}

/* 加载状态优化 */
:deep(.ant-table-placeholder) {
  padding: 60px 20px;
}

/* 滚动条样式 */
:deep(.ant-table-body) {
  scrollbar-width: thin;
  scrollbar-color: #d9d9d9 #f0f0f0;
}

:deep(.ant-table-body::-webkit-scrollbar) {
  width: 8px;
  height: 8px;
}

:deep(.ant-table-body::-webkit-scrollbar-track) {
  background: #f0f0f0;
  border-radius: 4px;
}

:deep(.ant-table-body::-webkit-scrollbar-thumb) {
  background: #d9d9d9;
  border-radius: 4px;
}

:deep(.ant-table-body::-webkit-scrollbar-thumb:hover) {
  background: #bfbfbf;
}

/* 动画效果 */
.data-table-container {
  animation: fadeIn 0.3s ease-out;
}

@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
</style>
