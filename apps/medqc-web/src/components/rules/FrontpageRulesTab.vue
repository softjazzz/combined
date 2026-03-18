<template>
  <div class="space-y-6">

    <!-- 一体化数据看板 -->
    <div class="bg-white rounded-xl border border-slate-200 shadow-[0_4px_20px_rgba(0,0,0,0.03)] flex flex-col md:flex-row overflow-hidden min-h-[140px]">
      
      <!-- 首页规则总览 -->
      <div class="flex-1 p-6 md:p-8 border-b md:border-b-0 md:border-r border-slate-100 flex flex-col justify-between">
        <div class="flex items-center gap-1.5 text-[12px] font-bold text-slate-400 mb-6 uppercase tracking-wider">
          <svg class="w-4 h-4 text-slate-300" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path></svg>
          首页规则总览
        </div>
        <div class="flex items-end gap-10">
          <div class="flex flex-col">
            <span class="text-[36px] font-bold text-slate-800 leading-none tracking-tight mb-2">{{ statistics.total }}</span>
            <span class="text-[12px] font-medium text-slate-400">规则总数</span>
          </div>
          <div class="flex flex-col">
            <span class="text-[36px] font-bold text-slate-800 leading-none tracking-tight mb-2">{{ statistics.categories }}</span>
            <span class="text-[12px] font-medium text-slate-400">规则分类</span>
          </div>
        </div>
      </div>

      <!-- 拦截严重度 -->
      <div class="flex-1 p-6 md:p-8 border-b md:border-b-0 md:border-r border-slate-100 flex flex-col justify-between">
        <div class="text-[12px] font-bold text-slate-400 mb-6 uppercase tracking-wider">拦截严重度</div>
        <div class="space-y-4 w-full">
          <div>
            <div class="flex justify-between items-center mb-1.5">
              <span class="text-[12px] text-slate-500 font-medium">阻断 (Error)</span>
              <span class="text-[14px] font-bold text-slate-700">{{ statistics.severity_counts?.error || 0 }}</span>
            </div>
            <div class="h-1.5 w-full bg-slate-100 rounded-full overflow-hidden">
              <div class="h-full bg-rose-500 rounded-full transition-all duration-1000" :style="{ width: severityPercent('error') }"></div>
            </div>
          </div>
          <div>
            <div class="flex justify-between items-center mb-1.5">
              <span class="text-[12px] text-slate-500 font-medium">警告 (Warning)</span>
              <span class="text-[14px] font-bold text-slate-700">{{ statistics.severity_counts?.warning || 0 }}</span>
            </div>
            <div class="h-1.5 w-full bg-slate-100 rounded-full overflow-hidden">
              <div class="h-full bg-amber-400 rounded-full transition-all duration-1000" :style="{ width: severityPercent('warning') }"></div>
            </div>
          </div>
        </div>
      </div>

      <!-- 分类分布 -->
      <div class="flex-1 p-6 md:p-8 flex flex-col justify-between">
        <div class="text-[12px] font-bold text-slate-400 mb-6 uppercase tracking-wider">分类分布</div>
        <div class="grid grid-cols-2 gap-x-8 gap-y-4">
          <div class="flex flex-col">
            <span class="text-2xl font-bold text-slate-800 leading-none tracking-tight mb-1.5">{{ statistics.category_counts?.required || 0 }}</span>
            <div class="flex items-center gap-1.5 text-[12px] font-medium text-slate-400"><span class="w-1.5 h-1.5 rounded-full bg-slate-300"></span> 必填性</div>
          </div>
          <div class="flex flex-col">
            <span class="text-2xl font-bold text-slate-800 leading-none tracking-tight mb-1.5">{{ statistics.category_counts?.format || 0 }}</span>
            <div class="flex items-center gap-1.5 text-[12px] font-medium text-slate-400"><span class="w-1.5 h-1.5 rounded-full bg-blue-400"></span> 规范性</div>
          </div>
          <div class="flex flex-col">
            <span class="text-2xl font-bold text-slate-800 leading-none tracking-tight mb-1.5">{{ statistics.category_counts?.logic || 0 }}</span>
            <div class="flex items-center gap-1.5 text-[12px] font-medium text-slate-400"><span class="w-1.5 h-1.5 rounded-full bg-amber-400"></span> 逻辑质控</div>
          </div>
          <div class="flex flex-col">
            <span class="text-2xl font-bold text-slate-800 leading-none tracking-tight mb-1.5">{{ statistics.category_counts?.consistency || 0 }}</span>
            <div class="flex items-center gap-1.5 text-[12px] font-medium text-slate-400"><span class="w-1.5 h-1.5 rounded-full bg-emerald-400"></span> 合理性</div>
          </div>
        </div>
      </div>

    </div>

    <!-- 聚合列表容器 -->
    <div class="bg-white border border-slate-200 rounded-xl shadow-[0_2px_12px_rgba(0,0,0,0.03)] overflow-hidden">
      
      <!-- 头部操作栏 -->
      <div class="px-5 py-4 border-b border-slate-100 flex flex-wrap items-center justify-between gap-4 bg-white">
        <div class="relative w-full md:w-80">
          <svg class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"></path></svg>
          <input 
            v-model="searchText"
            @input="handleSearch"
            type="text" 
            placeholder="搜索规则编号、名称、描述、字段..." 
            class="w-full pl-9 pr-3 py-1.5 text-[13px] border border-slate-300 rounded-lg focus:ring-1 focus:ring-blue-500 focus:border-blue-500 outline-none transition-shadow placeholder:text-slate-400"
          >
        </div>
        <div class="flex items-center gap-3 w-full md:w-auto overflow-x-auto pb-1 md:pb-0">
          <select v-model="filterCategory" @change="applyFilter" class="py-1.5 pl-3 pr-8 text-[13px] border border-slate-300 rounded-lg focus:ring-1 focus:ring-blue-500 focus:border-blue-500 outline-none bg-white text-slate-600 appearance-none shadow-sm cursor-pointer min-w-[120px]">
            <option :value="undefined">规则分类</option>
            <option value="required">必填校验</option>
            <option value="format">格式校验</option>
            <option value="logic">逻辑校验</option>
            <option value="consistency">一致性</option>
          </select>
          <select v-model="filterSeverity" @change="applyFilter" class="py-1.5 pl-3 pr-8 text-[13px] border border-slate-300 rounded-lg focus:ring-1 focus:ring-blue-500 focus:border-blue-500 outline-none bg-white text-slate-600 appearance-none shadow-sm cursor-pointer min-w-[110px]">
            <option :value="undefined">严重程度</option>
            <option value="error">阻断</option>
            <option value="warning">警告</option>
            <option value="info">提示</option>
          </select>
          <div class="hidden md:block w-px h-4 bg-slate-200"></div>
          <button @click="fetchRules" class="flex items-center gap-1.5 px-3 py-1.5 text-slate-500 hover:text-slate-800 hover:bg-slate-50 text-[13px] font-medium rounded-lg transition-colors cursor-pointer shrink-0">
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path></svg> 刷新
          </button>
        </div>
      </div>

      <!-- 数据表格 -->
      <div class="overflow-x-auto relative min-h-[400px]">
        <div v-if="loading" class="absolute inset-0 bg-white/60 backdrop-blur-[1px] z-10 flex items-center justify-center">
          <a-spin />
        </div>
        <table class="w-full text-left border-collapse min-w-[1000px]">
          <thead class="bg-slate-50 border-b border-slate-200 text-[12px] font-semibold text-slate-500 uppercase tracking-wider">
            <tr>
              <th class="px-5 py-3 w-20">编号</th>
              <th class="px-5 py-3 w-[26%]">规则名称</th>
              <th class="px-5 py-3 w-40">校验字段</th>
              <th class="px-5 py-3">分类</th>
              <th class="px-5 py-3">严重度</th>
              <th class="px-5 py-3 text-right">状态</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-slate-100 text-[13px] text-slate-700">
            
            <tr v-for="record in filteredRules" :key="record.rule_id" @click="editRule(record)" class="hover:bg-slate-50/60 transition-colors cursor-pointer">
              <td class="px-5 py-4 align-top">
                <span class="font-mono text-[12px] text-slate-400 font-medium">{{ record.rule_id }}</span>
              </td>
              
              <td class="px-5 py-4 align-top">
                <div class="font-bold text-slate-900 mb-0.5">{{ record.rule_name }}</div>
                <div class="text-[12px] text-slate-400 leading-snug truncate max-w-xs" :title="record.description">{{ record.description }}</div>
              </td>
              
              <td class="px-5 py-4 align-top">
                <span class="text-[12px] font-mono text-slate-500 bg-slate-50 px-2 py-0.5 rounded border border-slate-200">
                  {{ record.field_name }}
                </span>
              </td>
              
              <td class="px-5 py-4 align-top">
                <span class="px-2 py-1 bg-slate-100 text-slate-600 rounded text-[11px] font-medium whitespace-nowrap">{{ getCategoryLabel(record.category) }}</span>
              </td>
              
              <td class="px-5 py-4 align-top">
                <span :class="getSeverityBgClass(record.severity)" class="px-2.5 py-1 rounded-md text-[11px] font-bold whitespace-nowrap">
                  {{ getSeverityLabel(record.severity) }}
                </span>
              </td>
              
              <td class="px-5 py-4 align-top text-right" @click.stop>
                <button 
                  class="bg-blue-500 border-transparent relative inline-flex h-4 w-7 shrink-0 cursor-pointer rounded-full border-2 transition-colors focus:outline-none"
                >
                  <span class="translate-x-3 inline-block h-3 w-3 transform rounded-full bg-white shadow-sm ring-0 transition"></span>
                </button>
              </td>
            </tr>

            <tr v-if="filteredRules.length === 0 && !loading">
              <td colspan="6" class="px-5 py-12 text-center text-slate-400 text-sm">暂无匹配数据</td>
            </tr>

          </tbody>
        </table>
      </div>
    </div>
    
    <!-- 规则编辑器抽屉 -->
    <RuleEditorDrawer
      v-model:open="drawerVisible"
      :record="currentRecord"
      @save="handleSaveRule"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, computed } from 'vue'
import { message } from 'ant-design-vue'
import RuleEditorDrawer from './RuleEditorDrawer.vue'

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

const drawerVisible = ref(false)
const currentRecord = ref({})

const editRule = (record: any) => {
  currentRecord.value = { ...record }
  drawerVisible.value = true
}

const handleSaveRule = (updatedRecord: any) => {
  message.success(`规则 [${updatedRecord.rule_id}] 配置已保存并发布！`)
  const idx = allRules.value.findIndex(r => r.rule_id === updatedRecord.rule_id)
  if (idx > -1) {
    allRules.value[idx] = { ...allRules.value[idx], ...updatedRecord }
  }
}

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
  return { required: '必填', format: '规范', logic: '逻辑', consistency: '合理' }[cat] || cat
}
const getSeverityBgClass = (s: string) => {
  return { 
    error: 'bg-rose-50 text-rose-600', 
    warning: 'bg-amber-50 text-amber-600', 
    info: 'bg-blue-50 text-blue-600' 
  }[s] || 'bg-slate-50 text-slate-600'
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
