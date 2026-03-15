<template>
  <div class="space-y-6">
    <!-- 统计卡片区 -->
    <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
      <!-- 卡片1: 规则总览 -->
      <div class="bg-white p-6 rounded-2xl shadow-[0_4px_20px_-4px_rgba(0,0,0,0.05)] border border-slate-100 group hover:shadow-lg transition-shadow duration-300">
        <div class="flex justify-between items-start mb-4">
          <h3 class="text-slate-700 font-semibold text-sm">规则总览</h3>
          <div class="w-8 h-8 rounded-lg bg-slate-50 flex items-center justify-center text-slate-400 group-hover:text-blue-500 group-hover:bg-blue-50 transition-colors">
            <MedicineBoxOutlined />
          </div>
        </div>
        <div class="flex items-end gap-6">
          <div>
            <div class="text-3xl font-bold text-blue-600">{{ statistics.total_types }}</div>
            <div class="text-xs text-slate-400 mt-1 font-medium">规则类型</div>
          </div>
          <div>
            <div class="text-2xl font-bold text-slate-700">{{ formatNumber(statistics.total_rule_count) }}</div>
            <div class="text-xs text-slate-400 mt-1 font-medium">规则条目</div>
          </div>
        </div>
      </div>

      <!-- 卡片2: 严重度分布 -->
      <div class="bg-white p-6 rounded-2xl shadow-[0_4px_20px_-4px_rgba(0,0,0,0.05)] border border-slate-100 group hover:shadow-lg transition-shadow duration-300">
        <div class="flex justify-between items-start mb-4">
          <h3 class="text-slate-700 font-semibold text-sm">严重度分布</h3>
          <div class="w-8 h-8 rounded-lg bg-slate-50 flex items-center justify-center text-slate-400 group-hover:text-orange-500 group-hover:bg-orange-50 transition-colors">
            <ExclamationCircleOutlined />
          </div>
        </div>
        <div class="space-y-3">
          <div>
            <div class="flex justify-between text-xs mb-1">
              <span class="text-slate-500 font-medium">阻断 (error)</span>
              <span class="text-red-500 font-bold">{{ statistics.severity_counts?.error || 0 }}</span>
            </div>
            <div class="w-full bg-slate-100 rounded-full h-2 overflow-hidden">
              <div class="bg-red-500 h-2 rounded-full transition-all duration-1000" :style="{ width: severityPercent('error') }"></div>
            </div>
          </div>
          <div>
            <div class="flex justify-between text-xs mb-1">
              <span class="text-slate-500 font-medium">警告 (warning)</span>
              <span class="text-orange-400 font-bold">{{ statistics.severity_counts?.warning || 0 }}</span>
            </div>
            <div class="w-full bg-slate-100 rounded-full h-2 overflow-hidden">
              <div class="bg-orange-400 h-2 rounded-full transition-all duration-1000" :style="{ width: severityPercent('warning') }"></div>
            </div>
          </div>
          <div>
            <div class="flex justify-between text-xs mb-1">
              <span class="text-slate-500 font-medium">提示 (info)</span>
              <span class="text-blue-400 font-bold">{{ statistics.severity_counts?.info || 0 }}</span>
            </div>
            <div class="w-full bg-slate-100 rounded-full h-2 overflow-hidden">
              <div class="bg-blue-400 h-2 rounded-full transition-all duration-1000" :style="{ width: severityPercent('info') }"></div>
            </div>
          </div>
        </div>
      </div>

      <!-- 卡片3: 规则来源 -->
      <div class="bg-white p-6 rounded-2xl shadow-[0_4px_20px_-4px_rgba(0,0,0,0.05)] border border-slate-100 group hover:shadow-lg transition-shadow duration-300">
        <div class="flex justify-between items-start mb-4">
          <h3 class="text-slate-700 font-semibold text-sm">规则来源分布</h3>
          <div class="w-8 h-8 rounded-lg bg-slate-50 flex items-center justify-center text-slate-400 group-hover:text-violet-500 group-hover:bg-violet-50 transition-colors">
            <AppstoreOutlined />
          </div>
        </div>
        <div class="grid grid-cols-2 gap-3 mt-2">
          <div class="text-center p-3 bg-slate-50 rounded-xl border border-slate-100 hover:border-cyan-200 hover:bg-cyan-50/50 transition-colors">
            <div class="text-2xl font-bold text-slate-800">{{ statistics.source_counts?.rule_engine || 0 }}</div>
            <div class="text-[11px] font-medium text-slate-400 mt-1">🔧 规则引擎</div>
          </div>
          <div class="text-center p-3 bg-slate-50 rounded-xl border border-slate-100 hover:border-violet-200 hover:bg-violet-50/50 transition-colors">
            <div class="text-2xl font-bold text-slate-800">{{ statistics.source_counts?.ai_review || 0 }}</div>
            <div class="text-[11px] font-medium text-slate-400 mt-1">🤖 AI语义审查</div>
          </div>
        </div>
      </div>
    </div>

    <!-- 搜索/筛选栏 -->
    <div class="flex flex-col sm:flex-row justify-between items-center gap-4">
      <div class="relative w-full sm:w-96 group">
        <SearchOutlined class="absolute left-3 top-1/2 transform -translate-y-1/2 text-slate-400 text-base group-hover:text-blue-500 transition-colors" />
        <input
          v-model="searchText"
          @input="handleSearch"
          type="text"
          placeholder="搜索规则编号、名称、描述..."
          class="w-full pl-10 pr-4 py-2.5 bg-white border border-slate-200 rounded-xl text-sm focus:outline-none focus:border-blue-500 focus:ring-4 focus:ring-blue-500/10 transition-all shadow-sm placeholder-slate-400 hover:border-slate-300"
        />
      </div>
      <div class="flex gap-3 w-full sm:w-auto">
        <a-select
          v-model:value="filterCategory"
          placeholder="规则分类"
          allowClear
          @change="fetchRules"
          style="width: 140px"
        >
          <a-select-option v-for="cat in categoryOptions" :key="cat.value" :value="cat.value">
            {{ cat.label }}
          </a-select-option>
        </a-select>
        <a-select
          v-model:value="filterSeverity"
          placeholder="严重程度"
          allowClear
          @change="fetchRules"
          style="width: 120px"
        >
          <a-select-option value="error">阻断</a-select-option>
          <a-select-option value="warning">警告</a-select-option>
          <a-select-option value="info">提示</a-select-option>
        </a-select>
        <a-select
          v-model:value="filterSource"
          placeholder="规则来源"
          allowClear
          @change="fetchRules"
          style="width: 130px"
        >
          <a-select-option value="rule_engine">规则引擎</a-select-option>
          <a-select-option value="ai_review">AI语义审查</a-select-option>
        </a-select>
        <button
          @click="fetchRules"
          class="flex items-center justify-center px-4 py-2 text-slate-500 hover:text-slate-700 hover:bg-slate-100 rounded-lg text-sm transition-all"
        >
          <ReloadOutlined class="mr-1" /> 刷新
        </button>
      </div>
    </div>

    <!-- 规则表格 -->
    <div class="bg-white rounded-2xl shadow-[0_4px_20px_-4px_rgba(0,0,0,0.05)] border border-slate-100 overflow-hidden">
      <a-table
        :columns="columns"
        :data-source="rules"
        :loading="loading"
        :pagination="false"
        row-key="rule_id"
        class="ant-table-striped"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'rule_id'">
            <span class="font-mono text-blue-600 bg-blue-50 px-2 py-1 rounded text-xs font-medium border border-blue-100">
              {{ record.rule_id }}
            </span>
          </template>

          <template v-else-if="column.key === 'name'">
            <div>
              <div class="font-medium text-slate-800 text-sm">{{ record.name }}</div>
              <div class="text-xs text-slate-400 mt-0.5 line-clamp-1">{{ record.description }}</div>
            </div>
          </template>

          <template v-else-if="column.key === 'category_name'">
            <a-tag :color="getCategoryColor(record.category)">
              {{ record.category_name }}
            </a-tag>
          </template>

          <template v-else-if="column.key === 'severity'">
            <a-tag :color="getSeverityColor(record.severity)">
              {{ getSeverityLabel(record.severity) }}
            </a-tag>
          </template>

          <template v-else-if="column.key === 'source_name'">
            <span class="text-xs">
              <span v-if="record.source === 'rule_engine'" class="text-cyan-600">🔧 {{ record.source_name }}</span>
              <span v-else class="text-violet-600">🤖 {{ record.source_name }}</span>
            </span>
          </template>

          <template v-else-if="column.key === 'rule_count'">
            <span v-if="record.rule_count > 0" class="font-mono text-sm font-medium text-slate-700">
              {{ formatNumber(record.rule_count) }}
            </span>
            <span v-else class="text-xs text-slate-400">AI动态</span>
          </template>

          <template v-else-if="column.key === 'is_active'">
            <a-switch
              v-model:checked="record.is_active"
              size="small"
            />
          </template>

          <template v-else-if="column.key === 'example'">
            <a-tooltip :title="record.example" placement="topLeft">
              <span class="text-xs text-slate-400 cursor-help line-clamp-1">{{ record.example }}</span>
            </a-tooltip>
          </template>
        </template>
      </a-table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, computed } from 'vue'
import { message } from 'ant-design-vue'
import {
  MedicineBoxOutlined,
  ExclamationCircleOutlined,
  AppstoreOutlined,
  SearchOutlined,
  ReloadOutlined,
} from '@ant-design/icons-vue'

interface CodingRule {
  rule_id: string
  name: string
  category: string
  category_name: string
  description: string
  severity: string
  source: string
  source_name: string
  is_active: boolean
  example: string
  rule_count: number
  version: string
}

interface Statistics {
  total_types: number
  total_rule_count: number
  categories: number
  severity_counts: Record<string, number>
  source_counts: Record<string, number>
}

// 响应式数据
const loading = ref(false)
const rules = ref<CodingRule[]>([])
const statistics = reactive<Statistics>({
  total_types: 0,
  total_rule_count: 0,
  categories: 0,
  severity_counts: {},
  source_counts: {},
})
const searchText = ref('')
const filterCategory = ref<string>()
const filterSeverity = ref<string>()
const filterSource = ref<string>()

// 分类选项（从数据动态生成）
const categoryOptions = computed(() => {
  const cats = new Map<string, string>()
  rules.value.forEach(r => {
    if (!cats.has(r.category)) {
      cats.set(r.category, r.category_name)
    }
  })
  return Array.from(cats.entries()).map(([value, label]) => ({ value, label }))
})

// 表格列
const columns = [
  { title: '编号', dataIndex: 'rule_id', key: 'rule_id', width: 100 },
  { title: '规则名称', dataIndex: 'name', key: 'name', ellipsis: true },
  { title: '分类', dataIndex: 'category_name', key: 'category_name', width: 110 },
  { title: '严重度', dataIndex: 'severity', key: 'severity', width: 90 },
  { title: '来源', dataIndex: 'source_name', key: 'source_name', width: 110 },
  { title: '条目数', dataIndex: 'rule_count', key: 'rule_count', width: 90, align: 'right' as const },
  { title: '示例', dataIndex: 'example', key: 'example', ellipsis: true, width: 200 },
  { title: '状态', dataIndex: 'is_active', key: 'is_active', width: 70, align: 'center' as const },
]

// 工具函数
const formatNumber = (n: number) => {
  if (n >= 10000) return `${(n / 10000).toFixed(1)}万+`
  if (n >= 1000) return `${(n / 1000).toFixed(1)}K`
  return String(n)
}

const getCategoryColor = (cat: string) => {
  const map: Record<string, string> = {
    format: 'blue', existence: 'cyan', consistency: 'green',
    primary_diagnosis: 'orange', merge: 'purple', exclusion: 'red',
    specificity: 'geekblue', additional: 'magenta', primary_surgery: 'volcano',
    cost_logic: 'gold', ai_semantic: 'purple',
  }
  return map[cat] || 'default'
}

const getSeverityColor = (s: string) => {
  return { error: 'red', warning: 'orange', info: 'blue' }[s] || 'default'
}

const getSeverityLabel = (s: string) => {
  return { error: '阻断', warning: '警告', info: '提示' }[s] || s
}

const severityPercent = (s: string) => {
  const total = statistics.total_types || 1
  const count = statistics.severity_counts?.[s] || 0
  return `${Math.round((count / total) * 100)}%`
}

// 搜索防抖
let searchTimer: ReturnType<typeof setTimeout> | null = null
const handleSearch = () => {
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(() => fetchRules(), 300)
}

// 加载数据
const fetchRules = async () => {
  loading.value = true
  try {
    const params = new URLSearchParams()
    if (searchText.value) params.set('keyword', searchText.value)
    if (filterCategory.value) params.set('category', filterCategory.value)
    if (filterSeverity.value) params.set('severity', filterSeverity.value)
    if (filterSource.value) params.set('source', filterSource.value)

    const resp = await fetch(`/api/v1/qc/coding-rules?${params.toString()}`)
    const data = await resp.json()
    if (data.success && data.data) {
      rules.value = data.data.items || []
      if (data.data.statistics) {
        Object.assign(statistics, data.data.statistics)
      }
    }
  } catch (e) {
    console.error('加载编码规则失败:', e)
    message.error('加载编码规则失败')
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchRules()
})
</script>
