<template>
  <div class="space-y-6">
    <!-- 统计卡片区 -->
    <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
      <!-- 卡片1: 规则总览 -->
      <div class="bg-white p-6 rounded-2xl shadow-[0_4px_20px_-4px_rgba(0,0,0,0.05)] border border-slate-100 group hover:shadow-lg transition-shadow duration-300">
        <div class="flex justify-between items-start mb-4">
          <h3 class="text-slate-700 font-semibold text-sm">规则总览</h3>
          <div class="w-8 h-8 rounded-lg bg-slate-50 flex items-center justify-center text-slate-400 group-hover:text-blue-500 group-hover:bg-blue-50 transition-colors">
            <FileSearchOutlined />
          </div>
        </div>
        <div class="flex items-end gap-6">
          <div>
            <div class="text-3xl font-bold text-blue-600">{{ statistics.total }}</div>
            <div class="text-xs text-slate-400 mt-1 font-medium">规则总数</div>
          </div>
          <div>
            <div class="text-2xl font-bold text-slate-700">{{ statistics.categories }}</div>
            <div class="text-xs text-slate-400 mt-1 font-medium">规则分类</div>
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

      <!-- 卡片3: 分类分布 -->
      <div class="bg-white p-6 rounded-2xl shadow-[0_4px_20px_-4px_rgba(0,0,0,0.05)] border border-slate-100 group hover:shadow-lg transition-shadow duration-300">
        <div class="flex justify-between items-start mb-4">
          <h3 class="text-slate-700 font-semibold text-sm">分类分布</h3>
          <div class="w-8 h-8 rounded-lg bg-slate-50 flex items-center justify-center text-slate-400 group-hover:text-violet-500 group-hover:bg-violet-50 transition-colors">
            <AppstoreOutlined />
          </div>
        </div>
        <div class="grid grid-cols-2 gap-3 mt-2">
          <div class="text-center p-3 bg-slate-50 rounded-xl border border-slate-100 hover:border-red-200 hover:bg-red-50/50 transition-colors">
            <div class="text-2xl font-bold text-slate-800">{{ statistics.category_counts?.required || 0 }}</div>
            <div class="text-[11px] font-medium text-slate-400 mt-1">📋 必填校验</div>
          </div>
          <div class="text-center p-3 bg-slate-50 rounded-xl border border-slate-100 hover:border-blue-200 hover:bg-blue-50/50 transition-colors">
            <div class="text-2xl font-bold text-slate-800">{{ statistics.category_counts?.format || 0 }}</div>
            <div class="text-[11px] font-medium text-slate-400 mt-1">📐 格式校验</div>
          </div>
          <div class="text-center p-3 bg-slate-50 rounded-xl border border-slate-100 hover:border-green-200 hover:bg-green-50/50 transition-colors">
            <div class="text-2xl font-bold text-slate-800">{{ statistics.category_counts?.logic || 0 }}</div>
            <div class="text-[11px] font-medium text-slate-400 mt-1">🧩 逻辑校验</div>
          </div>
          <div class="text-center p-3 bg-slate-50 rounded-xl border border-slate-100 hover:border-violet-200 hover:bg-violet-50/50 transition-colors">
            <div class="text-2xl font-bold text-slate-800">{{ statistics.category_counts?.consistency || 0 }}</div>
            <div class="text-[11px] font-medium text-slate-400 mt-1">🔗 一致性</div>
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
          @change="applyFilter"
          style="width: 130px"
        >
          <a-select-option value="required">必填校验</a-select-option>
          <a-select-option value="format">格式校验</a-select-option>
          <a-select-option value="logic">逻辑校验</a-select-option>
          <a-select-option value="consistency">一致性</a-select-option>
        </a-select>
        <a-select
          v-model:value="filterSeverity"
          placeholder="严重程度"
          allowClear
          @change="applyFilter"
          style="width: 120px"
        >
          <a-select-option value="error">阻断</a-select-option>
          <a-select-option value="warning">警告</a-select-option>
          <a-select-option value="info">提示</a-select-option>
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
        :data-source="filteredRules"
        :loading="loading"
        :pagination="{ pageSize: 20, showTotal: (t: number) => `共 ${t} 条` }"
        row-key="rule_id"
        class="ant-table-striped"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'rule_id'">
            <span class="font-mono text-blue-600 bg-blue-50 px-2 py-1 rounded text-xs font-medium border border-blue-100">
              {{ record.rule_id }}
            </span>
          </template>

          <template v-else-if="column.key === 'rule_name'">
            <div>
              <div class="font-medium text-slate-800 text-sm">{{ record.rule_name }}</div>
              <div class="text-xs text-slate-400 mt-0.5 line-clamp-1">{{ record.description }}</div>
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

          <template v-else-if="column.key === 'field_name'">
            <span class="text-xs font-mono text-slate-500 bg-slate-50 px-2 py-0.5 rounded">
              {{ record.field_name }}
            </span>
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
  FileSearchOutlined,
  ExclamationCircleOutlined,
  AppstoreOutlined,
  SearchOutlined,
  ReloadOutlined,
} from '@ant-design/icons-vue'

interface FrontpageRule {
  rule_id: string
  field_name: string
  rule_name: string
  description: string
  severity: string
  category: string
}

const loading = ref(false)
const allRules = ref<FrontpageRule[]>([])
const searchText = ref('')
const filterCategory = ref<string>()
const filterSeverity = ref<string>()

const statistics = reactive({
  total: 0,
  categories: 0,
  severity_counts: {} as Record<string, number>,
  category_counts: {} as Record<string, number>,
})

// 过滤后的规则
const filteredRules = computed(() => {
  let result = allRules.value
  if (searchText.value) {
    const kw = searchText.value.toLowerCase()
    result = result.filter(r =>
      r.rule_id.toLowerCase().includes(kw) ||
      r.rule_name.toLowerCase().includes(kw) ||
      r.description.toLowerCase().includes(kw) ||
      r.field_name.toLowerCase().includes(kw)
    )
  }
  if (filterCategory.value) {
    result = result.filter(r => r.category === filterCategory.value)
  }
  if (filterSeverity.value) {
    result = result.filter(r => r.severity === filterSeverity.value)
  }
  return result
})

const columns = [
  { title: '编号', dataIndex: 'rule_id', key: 'rule_id', width: 100 },
  { title: '规则名称', dataIndex: 'rule_name', key: 'rule_name', ellipsis: true },
  { title: '校验字段', dataIndex: 'field_name', key: 'field_name', width: 140 },
  { title: '分类', dataIndex: 'category', key: 'category', width: 100 },
  { title: '严重度', dataIndex: 'severity', key: 'severity', width: 90 },
]

const getCategoryColor = (cat: string) => {
  return { required: 'red', format: 'blue', logic: 'green', consistency: 'purple' }[cat] || 'default'
}
const getCategoryLabel = (cat: string) => {
  return { required: '必填', format: '格式', logic: '逻辑', consistency: '一致性' }[cat] || cat
}
const getSeverityColor = (s: string) => {
  return { error: 'red', warning: 'orange', info: 'blue' }[s] || 'default'
}
const getSeverityLabel = (s: string) => {
  return { error: '阻断', warning: '警告', info: '提示' }[s] || s
}

const severityPercent = (s: string) => {
  const total = statistics.total || 1
  const count = statistics.severity_counts?.[s] || 0
  return `${Math.round((count / total) * 100)}%`
}

let searchTimer: ReturnType<typeof setTimeout> | null = null
const handleSearch = () => {
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {}, 300)
}
const applyFilter = () => {}

const fetchRules = async () => {
  loading.value = true
  try {
    const resp = await fetch('/api/v1/qc/formal-qc/rules')
    const data = await resp.json()
    if (data.success && data.data) {
      allRules.value = data.data
      // 计算统计
      const rules = data.data as FrontpageRule[]
      statistics.total = rules.length
      const catSet = new Set(rules.map(r => r.category))
      statistics.categories = catSet.size
      const sevCounts: Record<string, number> = {}
      const catCounts: Record<string, number> = {}
      for (const r of rules) {
        sevCounts[r.severity] = (sevCounts[r.severity] || 0) + 1
        catCounts[r.category] = (catCounts[r.category] || 0) + 1
      }
      statistics.severity_counts = sevCounts
      statistics.category_counts = catCounts
    }
  } catch (e) {
    console.error('加载首页质控规则失败:', e)
    message.error('加载首页质控规则失败')
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchRules()
})
</script>
