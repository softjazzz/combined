<template>
  <div class="h-full flex flex-col bg-white">
    <div
      class="px-5 py-3 border-b border-[#E5E7EB] flex items-center justify-between shrink-0 relative z-10 h-[52px]"
    >
      <h2 class="text-[14px] font-semibold text-slate-800 tracking-tight leading-none">
        结构浏览器
      </h2>
      <div class="relative flex items-center">
        <svg
          class="w-3.5 h-3.5 absolute left-2.5 text-slate-400"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="2"
            d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
          />
        </svg>
        <input
          v-model="searchText"
          type="text"
          placeholder="搜索表或字段"
          class="w-[200px] pl-[32px] pr-3 py-1.5 text-[12px] bg-slate-100/60 border border-transparent rounded-[8px] focus:bg-white focus:border-[#2b6cf6] focus:ring-[3px] focus:ring-[#2b6cf6]/10 focus:shadow-sm outline-none transition-all duration-200 text-slate-700 placeholder:text-slate-400 leading-tight"
        >
      </div>
    </div>

    <div class="flex-1 flex overflow-hidden min-h-0">
      <div class="w-[230px] shrink-0 border-r border-[#E5E7EB]/60 bg-slate-50/40 flex flex-col">
        <div
          class="px-4 py-2.5 text-[11px] font-medium tracking-wide text-slate-400 border-b border-slate-100"
        >
          表数量：{{ filteredTables.length }}
        </div>
        <div class="flex-1 overflow-y-auto custom-scrollbar p-3">
          <div class="space-y-0.5">
            <button
              v-for="table in filteredTables"
              :key="table.name"
              class="w-full text-left px-3 py-1.5 rounded-lg text-[13px] font-mono transition-all duration-200 block truncate"
              :class="
                selectedTable?.name === table.name
                  ? 'bg-blue-50/80 text-blue-600 font-semibold shadow-sm'
                  : 'hover:bg-slate-100/80 text-slate-600 hover:text-slate-800'
              "
              @click="handleSelectTable(table.name)"
            >
              {{ table.name }}
            </button>
          </div>
        </div>
      </div>

      <div class="flex-1 flex flex-col min-w-0 bg-white">
        <div class="flex border-b border-slate-100/80 px-7 pt-2">
          <button
            class="px-2 py-3 border-b-[2px] text-[13px] mr-6 transition-all"
            :class="
              activeView === 'schema'
                ? 'border-[#2b6cf6] font-semibold text-[#2b6cf6]'
                : 'border-transparent text-slate-500 hover:text-slate-800'
            "
            @click="activeView = 'schema'"
          >
            表结构 (Schema)
          </button>
          <button
            class="px-2 py-3 border-b-[2px] text-[13px] transition-all"
            :class="
              activeView === 'sample'
                ? 'border-[#2b6cf6] font-semibold text-[#2b6cf6]'
                : 'border-transparent text-slate-500 hover:text-slate-800'
            "
            @click="activeView = 'sample'"
          >
            样本数据 (Limit 20)
          </button>
        </div>

        <div class="flex-1 overflow-auto custom-scrollbar bg-white">
          <div
            v-if="loading"
            class="p-6 text-[12px] text-slate-500"
          >
            正在加载结构...
          </div>
          <div
            v-else-if="!selectedTable"
            class="p-6 text-[12px] text-slate-500"
          >
            暂无可展示表结构。
          </div>
          <template v-else>
            <table
              v-if="activeView === 'schema'"
              class="w-full text-left border-collapse"
            >
              <thead class="bg-slate-50/50 sticky top-0 z-10 shadow-[0_1px_0_rgba(226,232,240,1)]">
                <tr class="text-slate-400 font-semibold text-[11px] uppercase tracking-wider">
                  <th class="px-5 py-3 font-medium whitespace-nowrap">
                    字段名
                  </th>
                  <th class="px-5 py-3 font-medium whitespace-nowrap">
                    系统类型
                  </th>
                  <th class="px-5 py-3 text-center font-medium whitespace-nowrap">
                    Null
                  </th>
                  <th class="px-5 py-3 font-medium whitespace-nowrap">
                    约束
                  </th>
                </tr>
              </thead>
              <tbody class="font-mono text-[13px] text-slate-700">
                <tr
                  v-for="col in selectedTable.columns"
                  :key="col.name"
                  class="hover:bg-blue-50/30 transition-colors border-b border-slate-100/60"
                >
                  <td class="px-5 py-3.5 font-semibold text-slate-900 whitespace-nowrap">
                    {{ col.name }}
                  </td>
                  <td class="px-5 py-3.5 text-slate-500 whitespace-nowrap">
                    {{ col.type }}
                  </td>
                  <td class="px-5 py-3.5 text-center text-slate-400 whitespace-nowrap">
                    {{ col.nullable ? 'Yes' : 'No' }}
                  </td>
                  <td class="px-5 py-3.5 text-slate-500 whitespace-nowrap">
                    <span
                      v-if="col.primary_key"
                      class="text-amber-500 font-bold bg-amber-50 px-1.5 py-0.5 rounded text-[11px] whitespace-nowrap"
                    >PK</span>
                    <span v-else>-</span>
                  </td>
                </tr>
              </tbody>
            </table>

            <div v-else>
              <div
                v-if="sampleLoading"
                class="p-6 text-[12px] text-slate-500"
              >
                正在加载样本数据...
              </div>
              <div
                v-else-if="sampleRows.length === 0"
                class="p-6 text-[12px] text-slate-500"
              >
                暂无样本数据。
              </div>
              <table
                v-else
                class="w-full text-left border-collapse"
              >
                <thead
                  class="bg-slate-50/50 sticky top-0 z-10 shadow-[0_1px_0_rgba(226,232,240,1)]"
                >
                  <tr class="text-slate-400 font-semibold text-[11px] uppercase tracking-wider">
                    <th
                      v-for="col in sampleColumns"
                      :key="col"
                      class="px-6 py-3 font-medium whitespace-nowrap"
                    >
                      {{ col }}
                    </th>
                  </tr>
                </thead>
                <tbody class="text-[13px] text-slate-700">
                  <tr
                    v-for="(row, idx) in sampleRows"
                    :key="idx"
                    class="hover:bg-blue-50/30 transition-colors border-b border-slate-100/60"
                  >
                    <td
                      v-for="col in sampleColumns"
                      :key="col"
                      class="px-6 py-3 whitespace-nowrap text-slate-600"
                    >
                      <span class="font-mono text-[12px]">{{ renderCell(row[col]) }}</span>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </template>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { http } from '@/utils/http'

interface SchemaColumn {
  name: string
  type: string
  nullable: boolean
  primary_key: boolean
}

interface SchemaTable {
  name: string
  label?: string
  columns: SchemaColumn[]
}

const loading = ref(false)
const sampleLoading = ref(false)
const searchText = ref('')
const activeView = ref<'schema' | 'sample'>('schema')
const tables = ref<SchemaTable[]>([])
const selectedTableName = ref('')
const sampleColumns = ref<string[]>([])
const sampleRows = ref<Record<string, any>[]>([])

const filteredTables = computed(() => {
  const keyword = searchText.value.trim().toLowerCase()
  if (!keyword) {
    return tables.value
  }
  return tables.value.filter((table) => {
    if (table.name.toLowerCase().includes(keyword)) {
      return true
    }
    return table.columns.some((col) => col.name.toLowerCase().includes(keyword))
  })
})

const selectedTable = computed(() => {
  return (
    filteredTables.value.find((table) => table.name === selectedTableName.value) ||
    filteredTables.value[0] ||
    null
  )
})

async function loadSchema() {
  loading.value = true
  try {
    const resp = await http.get('/api/medical-records/schema')
    tables.value = Array.isArray(resp.data?.tables) ? resp.data.tables : []
    if (!selectedTableName.value && tables.value.length > 0) {
      selectedTableName.value = tables.value[0].name
    }
  } catch (error) {
    console.error('加载 schema 失败:', error)
    tables.value = []
  } finally {
    loading.value = false
  }
}

function handleSelectTable(tableName: string) {
  selectedTableName.value = tableName
}

async function loadSampleData() {
  if (!selectedTable.value) {
    sampleColumns.value = []
    sampleRows.value = []
    return
  }
  sampleLoading.value = true
  try {
    const resp = await http.get(`/api/medical-records/table-data/${selectedTable.value.name}`, {
      params: { page: 1, page_size: 20 },
    })
    sampleColumns.value = Array.isArray(resp.data?.columns) ? resp.data.columns : []
    sampleRows.value = Array.isArray(resp.data?.items) ? resp.data.items : []
  } catch (error) {
    console.error('加载样本数据失败:', error)
    sampleColumns.value = []
    sampleRows.value = []
  } finally {
    sampleLoading.value = false
  }
}

function renderCell(value: unknown): string {
  if (value === null || value === undefined) {
    return '-'
  }
  if (typeof value === 'object') {
    try {
      return JSON.stringify(value)
    } catch {
      return '[Object]'
    }
  }
  return String(value)
}

watch(
  () => [activeView.value, selectedTableName.value],
  async ([view]) => {
    if (view === 'sample') {
      await loadSampleData()
    }
  },
)

watch(filteredTables, (list) => {
  if (list.length === 0) {
    selectedTableName.value = ''
    return
  }
  if (!list.some((item) => item.name === selectedTableName.value)) {
    selectedTableName.value = list[0].name
  }
})

onMounted(async () => {
  await loadSchema()
})
</script>
