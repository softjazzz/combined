<template>
  <div class="h-full flex flex-col bg-white overflow-hidden">
    <div class="px-6 py-4 border-b border-slate-100 flex items-center justify-between gap-3 shrink-0">
      <div>
        <h2 class="text-[15px] font-bold text-slate-900 tracking-tight">
          字段清洗与映射规则（只读）
        </h2>
        <div class="text-[11px] text-slate-500 mt-1">
          来源：后端映射配置 `/api/v1/sync/mappings`
        </div>
      </div>
      <a-button
        size="small"
        :loading="loading"
        @click="loadMappings"
      >
        刷新
      </a-button>
    </div>

    <div class="flex-1 overflow-auto custom-scrollbar p-6 bg-[#F8F9FA]">
      <div
        v-if="loading"
        class="text-[12px] text-slate-500"
      >
        正在加载映射配置...
      </div>
      <div
        v-else-if="mappings.length === 0"
        class="text-[12px] text-slate-500"
      >
        暂无映射数据。
      </div>
      <table
        v-else
        class="w-full text-left border-collapse bg-white border border-slate-200 rounded overflow-hidden"
      >
        <thead class="bg-slate-50">
          <tr class="text-slate-500 text-[11px] uppercase tracking-wider">
            <th class="px-4 py-3 font-medium">
              源集合
            </th>
            <th class="px-4 py-3 font-medium">
              目标表
            </th>
            <th class="px-4 py-3 font-medium">
              主键字段
            </th>
            <th class="px-4 py-3 font-medium">
              Tier
            </th>
            <th class="px-4 py-3 font-medium">
              状态
            </th>
          </tr>
        </thead>
        <tbody class="text-[12px] text-slate-700 font-mono">
          <tr
            v-for="item in mappings"
            :key="`${item.source_collection}-${item.target_table}`"
            class="border-t border-slate-100 hover:bg-slate-50"
          >
            <td class="px-4 py-2.5">
              {{ item.source_collection }}
            </td>
            <td class="px-4 py-2.5">
              {{ item.target_table }}
            </td>
            <td class="px-4 py-2.5">
              {{ item.key_fields.join(', ') || '-' }}
            </td>
            <td class="px-4 py-2.5">
              {{ item.tier }}
            </td>
            <td class="px-4 py-2.5">
              <span :class="item.enabled ? 'text-emerald-600' : 'text-slate-400'">
                {{ item.enabled ? '启用' : '停用' }}
              </span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { syncApi, type SyncMappingItem } from '@/api/sync'

const loading = ref(false)
const mappings = ref<SyncMappingItem[]>([])

async function loadMappings() {
  loading.value = true
  try {
    const resp = await syncApi.getMappings()
    mappings.value = Array.isArray(resp.items) ? resp.items : []
  } catch (error) {
    console.error('加载映射配置失败:', error)
    mappings.value = []
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  void loadMappings()
})
</script>
