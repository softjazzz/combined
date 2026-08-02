<template>
  <section class="catalog-workbench">
    <header class="catalog-header">
      <div>
        <div class="catalog-eyebrow">
          <BookOpen :size="15" /> 只读配置
        </div>
        <h2>手术操作分级目录</h2>
        <p>查看质控引擎用于区分手术、操作及手术等级的当前口径。</p>
      </div>
      <div class="catalog-version">
        {{ data?.version || '目录加载中' }}
      </div>
    </header>

    <div
      v-if="data"
      class="policy-strip"
    >
      <ShieldCheck :size="18" />
      <div>
        <strong>等级判定口径</strong>
        <span>{{ data.policy.level_priority }}；{{ data.policy.conditional_level_four }}。</span>
        <span>{{ data.policy.category_boundary }}。</span>
      </div>
    </div>

    <div class="summary-strip">
      <button
        class="summary-item"
        :class="{ active: !filters.category && !filters.level }"
        @click="showAll"
      >
        <span>目录总数</span><strong>{{ data?.summary.total ?? '—' }}</strong>
      </button>
      <button
        class="summary-item"
        :class="{ active: filters.category === '手术' && !filters.level }"
        @click="showSurgeries"
      >
        <span>手术</span><strong>{{ data?.summary.surgery ?? '—' }}</strong>
      </button>
      <button
        class="summary-item"
        :class="{ active: isLevelFourFilter }"
        @click="showLevelFour"
      >
        <span>四级手术</span><strong>{{ data?.summary.level_four_surgery ?? '—' }}</strong>
      </button>
      <button
        class="summary-item"
        :class="{ active: filters.category === 'operation' }"
        @click="showOperations"
      >
        <span>非手术操作</span><strong>{{ data?.summary.operation ?? '—' }}</strong>
      </button>
    </div>

    <div class="filter-bar">
      <a-input
        v-model:value="filters.keyword"
        allow-clear
        class="catalog-search"
        placeholder="搜索手术操作编码或名称"
        @press-enter="applyFilters"
      >
        <template #prefix>
          <Search :size="15" />
        </template>
      </a-input>
      <a-select
        v-model:value="filters.category"
        allow-clear
        class="catalog-select"
        placeholder="全部分类"
        popup-class-name="catalog-filter-popup"
        @change="applyFilters"
      >
        <a-select-option
          v-for="item in categoryOptions"
          :key="item.value"
          :value="item.value"
        >
          {{ item.label }}
        </a-select-option>
      </a-select>
      <a-select
        v-model:value="filters.level"
        allow-clear
        class="catalog-select level-select"
        placeholder="全部等级"
        popup-class-name="catalog-filter-popup"
        @change="applyFilters"
      >
        <a-select-option
          v-for="level in data?.filter_options.levels || []"
          :key="level"
          :value="level"
        >
          {{ level }}
        </a-select-option>
      </a-select>
      <a-select
        v-model:value="filters.source"
        allow-clear
        class="catalog-select source-select"
        placeholder="全部来源"
        popup-class-name="catalog-filter-popup"
        @change="applyFilters"
      >
        <a-select-option
          v-for="source in data?.filter_options.sources || []"
          :key="source.value"
          :value="source.value"
        >
          {{ source.label }}
        </a-select-option>
      </a-select>
      <a-button
        type="primary"
        @click="applyFilters"
      >
        <Search :size="15" />查询
      </a-button>
      <a-button @click="resetFilters">
        <RefreshCw :size="15" />重置
      </a-button>
    </div>

    <div class="catalog-table-wrap">
      <div class="table-caption">
        <span>当前筛选 <strong>{{ data?.total ?? 0 }}</strong> 条</span>
        <span>有效等级是质控判定使用的等级</span>
      </div>
      <a-table
        :columns="columns"
        :data-source="data?.items || []"
        :loading="loading"
        :pagination="pagination"
        :row-key="(record: SurgeryProcedureCatalogItem) => record.code"
        size="middle"
        @change="handleTableChange"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'identity'">
            <div class="catalog-identity">
              <code>{{ record.code }}</code>
              <strong>{{ record.name }}</strong>
            </div>
          </template>
          <template v-else-if="column.key === 'category'">
            <span
              class="category-label"
              :class="{ surgery: record.category === '手术' }"
            >
              {{ record.category }}
            </span>
          </template>
          <template v-else-if="column.key === 'effective_level'">
            <span
              v-if="record.effective_level"
              class="level-label"
              :class="levelClass(record.effective_level)"
            >
              {{ record.effective_level }}
            </span>
            <span
              v-else
              class="muted-value"
            >不适用</span>
          </template>
          <template v-else-if="column.key === 'basis'">
            <div class="basis-cell">
              <strong>{{ record.raw_level || '未分级' }}</strong>
              <span>{{ record.source_label }}</span>
            </div>
          </template>
        </template>
        <template #emptyText>
          <a-empty description="没有符合当前条件的手术操作" />
        </template>
      </a-table>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import type { TableColumnsType, TablePaginationConfig } from 'ant-design-vue'
import { message } from 'ant-design-vue'
import { BookOpen, RefreshCw, Search, ShieldCheck } from 'lucide-vue-next'
import {
  fetchSurgeryProcedureCatalog,
  type SurgeryProcedureCatalogData,
  type SurgeryProcedureCatalogItem,
} from '@/views/workstation-v4/surgery-catalog/service'

const loading = ref(false)
const data = ref<SurgeryProcedureCatalogData>()
const filters = reactive({
  keyword: '',
  category: undefined as string | undefined,
  level: undefined as string | undefined,
  source: undefined as string | undefined,
  page: 1,
  pageSize: 20,
})

const columns: TableColumnsType<SurgeryProcedureCatalogItem> = [
  { title: '编码与名称', key: 'identity', width: 500 },
  { title: '类型', key: 'category', width: 130 },
  { title: '有效等级', key: 'effective_level', width: 130 },
  { title: '原始等级与来源', key: 'basis', width: 260 },
]

const categoryOptions = computed(() => {
  const categories = data.value?.filter_options.categories || []
  return [
    ...categories.map((value) => ({ value, label: value })),
    { value: 'operation', label: '全部非手术操作' },
  ]
})

const pagination = computed<TablePaginationConfig>(() => ({
  current: data.value?.page || filters.page,
  pageSize: data.value?.page_size || filters.pageSize,
  total: data.value?.total || 0,
  showSizeChanger: true,
  pageSizeOptions: ['20', '50', '100'],
  showTotal: (total: number) => `共 ${total} 条`,
  size: 'small',
}))

const isLevelFourFilter = computed(() => filters.category === '手术' && filters.level === '四级')

async function loadCatalog(): Promise<void> {
  loading.value = true
  try {
    const result = await fetchSurgeryProcedureCatalog({
      keyword: filters.keyword,
      category: filters.category,
      effectiveLevel: filters.level,
      source: filters.source,
      page: filters.page,
      pageSize: filters.pageSize,
    })
    data.value = result
  } catch (error) {
    message.error(error instanceof Error ? error.message : '加载手术操作分级目录失败')
  } finally {
    loading.value = false
  }
}

function applyFilters(): void {
  filters.page = 1
  void loadCatalog()
}

function resetFilters(): void {
  filters.keyword = ''
  filters.category = undefined
  filters.level = undefined
  filters.source = undefined
  filters.page = 1
  void loadCatalog()
}

function showAll(): void {
  filters.category = undefined
  filters.level = undefined
  applyFilters()
}

function showSurgeries(): void {
  filters.category = '手术'
  filters.level = undefined
  applyFilters()
}

function showLevelFour(): void {
  filters.category = '手术'
  filters.level = '四级'
  applyFilters()
}

function showOperations(): void {
  filters.category = 'operation'
  filters.level = undefined
  applyFilters()
}

function handleTableChange(paginationValue: TablePaginationConfig): void {
  filters.page = paginationValue.current || 1
  filters.pageSize = paginationValue.pageSize || 20
  void loadCatalog()
}

function levelClass(level: string): string {
  return `level-${({ 一级: 1, 二级: 2, 三级: 3, 四级: 4 } as Record<string, number>)[level] || 0}`
}

onMounted(() => void loadCatalog())
</script>

<style scoped>
.catalog-workbench {
  background: rgba(255, 255, 255, 0.88);
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 20px;
  box-shadow: 0 8px 30px rgba(0, 0, 0, 0.04);
  overflow: hidden;
}

.catalog-header {
  align-items: flex-start;
  display: flex;
  justify-content: space-between;
  padding: 24px 26px 20px;
}

.catalog-eyebrow {
  align-items: center;
  color: #0066cc;
  display: flex;
  font-size: 12px;
  font-weight: 600;
  gap: 6px;
  margin-bottom: 7px;
}

.catalog-header h2 {
  color: #1d1d1f;
  font-size: 20px;
  font-weight: 700;
  line-height: 26px;
  margin: 0;
}

.catalog-header p {
  color: rgba(29, 29, 31, 0.58);
  font-size: 13px;
  margin: 5px 0 0;
}

.catalog-version {
  background: rgba(0, 0, 0, 0.04);
  border-radius: 999px;
  color: rgba(29, 29, 31, 0.5);
  font-size: 11px;
  padding: 6px 10px;
}

.policy-strip {
  align-items: flex-start;
  background: rgba(0, 102, 204, 0.055);
  border-bottom: 1px solid rgba(0, 102, 204, 0.1);
  border-top: 1px solid rgba(0, 102, 204, 0.1);
  color: #0066cc;
  display: flex;
  gap: 10px;
  padding: 13px 26px;
}

.policy-strip div {
  display: flex;
  flex-wrap: wrap;
  gap: 2px 12px;
}
.policy-strip strong {
  font-size: 13px;
}
.policy-strip span {
  color: rgba(29, 29, 31, 0.64);
  font-size: 12px;
}

.summary-strip {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  padding: 18px 26px 8px;
}

.summary-item {
  align-items: baseline;
  background: transparent;
  border: 0;
  border-right: 1px solid rgba(0, 0, 0, 0.08);
  color: rgba(29, 29, 31, 0.55);
  cursor: pointer;
  display: flex;
  gap: 10px;
  justify-content: center;
  padding: 5px 12px;
}

.summary-item:last-child {
  border-right: 0;
}
.summary-item:hover span,
.summary-item.active span {
  color: #0066cc;
}
.summary-item strong {
  color: #1d1d1f;
  font-size: 22px;
  line-height: 28px;
}
.summary-item.active strong {
  color: #0066cc;
}

.filter-bar {
  align-items: center;
  display: flex;
  gap: 10px;
  padding: 16px 26px;
}

.catalog-search {
  max-width: 330px;
}
.catalog-select {
  width: 150px;
}
.level-select {
  width: 125px;
}
.source-select {
  width: 190px;
}
.filter-bar :deep(.ant-input-affix-wrapper),
.filter-bar :deep(.ant-select-selector),
.filter-bar :deep(.ant-btn) {
  border-radius: 8px !important;
}
.filter-bar :deep(.ant-btn) {
  align-items: center;
  display: inline-flex;
  gap: 6px;
}

.catalog-table-wrap {
  border-top: 1px solid rgba(0, 0, 0, 0.08);
}
.table-caption {
  color: rgba(29, 29, 31, 0.46);
  display: flex;
  font-size: 12px;
  justify-content: space-between;
  padding: 12px 26px;
}
.table-caption strong {
  color: #0066cc;
}
.catalog-table-wrap :deep(.ant-table-thead > tr > th) {
  background: rgba(0, 0, 0, 0.025);
  color: rgba(29, 29, 31, 0.52);
  font-size: 12px;
  font-weight: 600;
}
.catalog-table-wrap :deep(.ant-table-tbody > tr > td) {
  border-bottom-color: rgba(0, 0, 0, 0.06);
}
.catalog-table-wrap :deep(.ant-table-tbody > tr:hover > td) {
  background: rgba(0, 102, 204, 0.025) !important;
}
.catalog-table-wrap :deep(.ant-pagination) {
  margin: 16px 24px;
}

.catalog-identity {
  align-items: baseline;
  display: flex;
  gap: 14px;
  min-width: 0;
}
.catalog-identity code {
  background: rgba(0, 0, 0, 0.04);
  border-radius: 6px;
  color: rgba(29, 29, 31, 0.58);
  flex: 0 0 auto;
  font-size: 12px;
  padding: 3px 7px;
}
.catalog-identity strong {
  color: #1d1d1f;
  font-size: 14px;
  font-weight: 600;
}
.category-label {
  color: rgba(29, 29, 31, 0.58);
  font-size: 13px;
}
.category-label.surgery {
  color: #0066cc;
  font-weight: 600;
}
.level-label {
  background: rgba(0, 0, 0, 0.045);
  border-radius: 999px;
  color: rgba(29, 29, 31, 0.68);
  display: inline-flex;
  font-size: 12px;
  font-weight: 600;
  padding: 3px 10px;
}
.level-label.level-4 {
  background: rgba(0, 102, 204, 0.1);
  color: #0066cc;
}
.basis-cell {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.basis-cell strong {
  color: rgba(29, 29, 31, 0.72);
  font-size: 13px;
}
.basis-cell span,
.muted-value {
  color: rgba(29, 29, 31, 0.42);
  font-size: 12px;
}

@media (max-width: 980px) {
  .filter-bar {
    align-items: stretch;
    flex-wrap: wrap;
  }
  .catalog-search {
    max-width: none;
    width: 100%;
  }
  .summary-strip {
    grid-template-columns: repeat(2, 1fr);
  }
  .summary-item:nth-child(2) {
    border-right: 0;
  }
}
</style>

<style>
.catalog-filter-popup {
  font-family:
    'Source Han Sans SC', 'San Francisco', 'SF Pro Text', Inter, 'PingFang SC',
    'Microsoft YaHei UI', sans-serif;
}
.catalog-filter-popup.ant-select-dropdown {
  background: rgba(255, 255, 255, 0.96);
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 10px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.12);
}
.catalog-filter-popup .ant-select-item {
  font-size: 13px;
  min-height: 34px;
}
.catalog-filter-popup .ant-select-item-option-selected {
  background: rgba(0, 102, 204, 0.08);
  color: #0066cc;
  font-weight: 600;
}
</style>
