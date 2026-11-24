<template>
  <main class="catalog-page">
    <div class="catalog-page-inner">
      <header class="catalog-page-header">
        <div class="catalog-title-block">
          <div class="catalog-eyebrow mq-page-eyebrow">
            规则 · 只读配置
          </div>
          <h1 class="mq-page-title">
            手术操作分级目录
          </h1>
          <p>查看质控引擎用于区分手术、操作及手术等级的当前口径。</p>
        </div>
        <div class="catalog-page-actions">
          <span
            class="catalog-version"
            :class="{ 'is-error': Boolean(loadError && !data?.version) }"
            data-testid="catalog-version"
          >{{ versionBadgeText }}</span>
          <a-button @click="goBack">
            <ArrowLeft :size="15" />返回样本验证
          </a-button>
        </div>
      </header>

      <section class="catalog-workbench">
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
            :class="{ active: isAllFilter }"
            data-testid="catalog-summary-all"
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
          <div
            v-if="loadError"
            class="catalog-error-banner"
            data-testid="catalog-load-error"
          >
            <span>{{ loadError }}</span>
            <a-button
              size="small"
              type="primary"
              data-testid="catalog-retry"
              @click="loadCatalog"
            >
              重新加载
            </a-button>
          </div>
          <div class="catalog-table-meta">
            <span>当前筛选 <strong>{{ data?.total ?? 0 }}</strong> 条</span>
            <span>有效等级是质控判定使用的等级</span>
          </div>
          <a-table
            :columns="columns"
            :data-source="data?.items || []"
            :loading="loading"
            :pagination="pagination"
            :row-key="(record: SurgeryProcedureCatalogItem) => record.code"
            :scroll="{ x: 1020 }"
            size="middle"
            table-layout="fixed"
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
              <a-empty :description="loadError ? '目录加载失败，请点击重试' : '没有符合当前条件的手术操作'">
                <a-button
                  v-if="loadError"
                  size="small"
                  type="primary"
                  @click="loadCatalog"
                >
                  重新加载
                </a-button>
              </a-empty>
            </template>
          </a-table>
        </div>
      </section>
    </div>
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import type { TableColumnsType, TablePaginationConfig } from 'ant-design-vue'
import { message } from 'ant-design-vue'
import { ArrowLeft, RefreshCw, Search, ShieldCheck } from 'lucide-vue-next'
import {
  fetchSurgeryProcedureCatalog,
  type SurgeryProcedureCatalogData,
  type SurgeryProcedureCatalogItem,
} from '@/views/workstation-v4/surgery-catalog/service'

const loading = ref(false)
const loadError = ref('')
const router = useRouter()
const data = ref<SurgeryProcedureCatalogData>()
let catalogRequestSeq = 0
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

const isAllFilter = computed(
  () =>
    !filters.category &&
    !filters.level &&
    !filters.source &&
    !String(filters.keyword || '').trim(),
)
const isLevelFourFilter = computed(() => filters.category === '手术' && filters.level === '四级')
const versionBadgeText = computed(() => {
  if (data.value?.version) return data.value.version
  if (loading.value) return '目录加载中'
  if (loadError.value) return '目录加载失败'
  return '暂无目录版本'
})

async function loadCatalog(): Promise<void> {
  const seq = ++catalogRequestSeq
  loading.value = true
  loadError.value = ''
  try {
    const result = await fetchSurgeryProcedureCatalog({
      keyword: filters.keyword,
      category: filters.category,
      effectiveLevel: filters.level,
      source: filters.source,
      page: filters.page,
      pageSize: filters.pageSize,
    })
    if (seq !== catalogRequestSeq) return
    data.value = result
  } catch (error) {
    if (seq !== catalogRequestSeq) return
    const errMsg = error instanceof Error ? error.message : '加载手术操作分级目录失败'
    loadError.value = errMsg
    message.error(errMsg)
  } finally {
    if (seq === catalogRequestSeq) {
      loading.value = false
    }
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
  filters.keyword = ''
  filters.category = undefined
  filters.level = undefined
  filters.source = undefined
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

function goBack(): void {
  void router.push({ name: 'WorkstationV4CustomerSampleValidation' })
}

onMounted(() => void loadCatalog())
</script>

<style scoped>
.catalog-page {
  background: #f5f5f7;
  box-sizing: border-box;
  color: #1d1d1f;
  min-height: 100%;
  overflow-x: hidden;
  padding: 22px 24px 34px;
  width: 100%;
}

.catalog-page-inner {
  margin: 0 auto;
  max-width: 1440px;
  min-width: 0;
  width: 100%;
}

.catalog-page-header {
  align-items: flex-start;
  display: flex;
  justify-content: space-between;
  margin-bottom: 18px;
}

.catalog-title-block h1 {
  color: #1d1d1f;
  font-size: 28px;
  font-weight: 700;
  letter-spacing: -0.02em;
  line-height: 31px;
  margin: 0;
}

.catalog-title-block p {
  color: rgba(29, 29, 31, 0.56);
  font-size: 13px;
  line-height: 20px;
  margin: 7px 0 0;
}

.catalog-page-actions {
  align-items: center;
  display: flex;
  gap: 10px;
}

.catalog-page-actions :deep(.ant-btn) {
  align-items: center;
  border-radius: 8px;
  display: inline-flex;
  font-size: 13px;
  gap: 6px;
}

.catalog-workbench {
  background: rgba(255, 255, 255, 0.88);
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 20px;
  box-shadow: 0 8px 30px rgba(0, 0, 0, 0.04);
  min-width: 0;
  overflow: hidden;
  width: 100%;
}

.catalog-eyebrow {
  align-items: center;
  color: #0066cc;
  display: flex;
  font-size: 12px;
  font-weight: 600;
  gap: 6px;
  margin-bottom: 6px;
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
  flex-wrap: wrap;
  gap: 10px;
  padding: 16px 26px;
}

.catalog-search {
  flex: 1 1 300px;
  max-width: 420px;
  min-width: 260px;
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
  min-width: 0;
  width: 100%;
}
.catalog-table-meta {
  box-sizing: border-box;
  color: rgba(29, 29, 31, 0.46);
  display: flex;
  font-size: 12px;
  justify-content: space-between;
  line-height: 20px;
  min-width: 0;
  padding: 12px 26px;
  white-space: nowrap;
  width: 100%;
}
.catalog-table-meta strong {
  color: #0066cc;
}
.catalog-table-wrap :deep(.ant-table-wrapper) {
  display: block;
  min-width: 0;
  width: 100%;
}
.catalog-table-wrap :deep(.ant-spin-nested-loading),
.catalog-table-wrap :deep(.ant-spin-container),
.catalog-table-wrap :deep(.ant-table),
.catalog-table-wrap :deep(.ant-table-container) {
  min-width: 0;
  width: 100%;
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
  .catalog-page {
    padding: 16px;
  }
  .catalog-page-header {
    align-items: stretch;
    flex-direction: column;
    gap: 14px;
  }
  .catalog-page-actions {
    justify-content: space-between;
  }
  .filter-bar {
    align-items: stretch;
    flex-wrap: wrap;
  }
  .catalog-search {
    max-width: none;
    width: 100%;
  }
  .catalog-table-meta {
    align-items: flex-start;
    flex-direction: column;
    white-space: normal;
  }
  .summary-strip {
    grid-template-columns: repeat(2, 1fr);
  }
  .summary-item:nth-child(2) {
    border-right: 0;
  }
}

/* ===== v7.1 液态玻璃覆盖（同选择器后写生效） ===== */
.catalog-page {
  padding: 8px 28px 32px 22px;
  background: transparent;
  color: var(--mq-text-primary);
  font-family: var(--mq-font-family);
}

.catalog-page-header {
  align-items: flex-end;
  margin-bottom: 20px;
  padding: 0 4px;
}

.catalog-title-block h1 {
  font-family: var(--mq-font-display);
  font-size: var(--mq-font-title);
  font-weight: 700;
  letter-spacing: -0.03em;
  line-height: 1.1;
}

.catalog-eyebrow {
  margin-bottom: 4px;
  color: var(--mq-text-tertiary);
  font-size: var(--mq-font-13);
}

.catalog-title-block p {
  margin-top: 4px;
  color: var(--mq-text-tertiary);
}

.catalog-page-actions :deep(.ant-btn),
.filter-bar :deep(.ant-btn) {
  height: 36px;
  border-radius: 999px;
}

.catalog-version {
  background: var(--mq-bg-muted);
  color: var(--mq-text-tertiary);
  font-family: var(--mq-font-mono);
}

.catalog-version.is-error {
  background: rgba(207, 19, 34, 0.08);
  color: #cf1322;
}

.catalog-error-banner {
  align-items: center;
  background: rgba(207, 19, 34, 0.06);
  border-bottom: 1px solid rgba(207, 19, 34, 0.14);
  color: #cf1322;
  display: flex;
  font-size: 13px;
  gap: 12px;
  justify-content: space-between;
  padding: 10px 26px;
}

.catalog-workbench {
  border: 1px solid var(--mq-glass-border);
  border-radius: var(--mq-radius-card);
  background: var(--mq-glass-bg);
  -webkit-backdrop-filter: var(--mq-glass-blur);
  backdrop-filter: var(--mq-glass-blur);
  box-shadow: var(--mq-glass-shadow);
}

.policy-strip {
  background: var(--mq-info-bg);
  color: var(--mq-text-secondary);
}

.policy-strip strong {
  color: var(--mq-info-text);
}

/* 统计项即分类筛选：选中为白色浮起胶囊 */
.summary-item {
  border-radius: 16px;
  color: var(--mq-text-secondary);
}

.summary-item.active {
  background: #ffffff;
  box-shadow: 0 2px 10px rgba(10, 55, 115, 0.1);
  color: var(--mq-brand-600);
}

.summary-item strong {
  font-family: var(--mq-font-display);
  letter-spacing: -0.02em;
}

.filter-bar :deep(.ant-input-affix-wrapper),
.filter-bar :deep(.ant-select-selector) {
  border-color: rgba(60, 60, 80, 0.1) !important;
  border-radius: var(--mq-radius-control) !important;
  background: rgba(255, 255, 255, 0.85) !important;
}

.catalog-table-wrap :deep(.ant-table-thead > tr > th) {
  border-bottom: 0;
  background: rgba(118, 128, 160, 0.06);
  color: var(--mq-text-tertiary);
  font-size: var(--mq-font-12);
  font-weight: 600;
}

.catalog-table-wrap :deep(.ant-table-thead > tr > th::before) {
  display: none;
}

.catalog-table-wrap :deep(.ant-table-tbody > tr > td) {
  border-bottom: 0.5px solid var(--mq-border);
  background: transparent;
}

.catalog-table-wrap :deep(.ant-table-tbody > tr:hover > td) {
  background: rgba(10, 108, 255, 0.04);
}

.catalog-identity code {
  border-radius: 8px;
  background: var(--mq-info-bg);
  color: var(--mq-brand-700);
  font-family: var(--mq-font-mono);
}

.level-label,
.category-label {
  border-radius: 999px;
}

.catalog-table-wrap :deep(.ant-pagination-item-active) {
  border-color: transparent;
  background: var(--mq-brand-gradient);
}

.catalog-table-wrap :deep(.ant-pagination-item-active a) {
  color: #ffffff;
}

/* 字重收敛：Windows 下中文走微软雅黑，600 及以上都会渲染成粗黑体。
   只保留统计数字和口径标题用 600，行内名称、分类、等级一律 500 */
.summary-strip {
  gap: 8px;
  padding: 16px 22px 4px;
}

.summary-item {
  flex-direction: column;
  align-items: flex-start;
  justify-content: flex-start;
  gap: 2px;
  padding: 10px 16px;
  border-right: 0;
  text-align: left;
}

.summary-item span {
  color: var(--mq-text-tertiary);
  font-size: var(--mq-font-12);
}

.summary-item strong {
  color: var(--mq-text-primary);
  font-size: 26px;
  font-weight: 600;
  line-height: 32px;
  font-variant-numeric: tabular-nums;
}

.summary-item:hover span,
.summary-item.active span {
  color: var(--mq-brand-600);
}

.summary-item.active strong {
  color: var(--mq-brand-600);
}

.catalog-identity strong {
  color: var(--mq-text-primary);
  font-weight: 500;
}

.category-label,
.category-label.surgery {
  color: var(--mq-text-secondary);
  font-weight: 400;
}

.level-label {
  background: var(--mq-neutral-bg);
  color: var(--mq-text-secondary);
  font-weight: 500;
}

.level-label.level-4 {
  background: var(--mq-info-bg);
  color: var(--mq-brand-600);
}

.basis-cell strong {
  color: var(--mq-text-secondary);
  font-weight: 500;
}

.catalog-table-wrap :deep(.ant-table-thead > tr > th) {
  font-weight: 500;
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
