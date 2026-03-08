<template>
  <div class="staff-ranking-page p-6 bg-gray-50 min-h-screen">
    <!-- 页面标题 -->
    <div class="flex items-center justify-between mb-6">
      <div>
        <h1 class="text-2xl font-bold text-gray-800">质控员工作量排名</h1>
        <p class="text-gray-500 text-sm mt-1">按周期查看质控员的工作量统计和排名</p>
      </div>
      <a-segmented v-model:value="period" :options="periodOptions" @change="fetchData" />
    </div>

    <!-- 汇总统计 -->
    <div class="grid grid-cols-5 gap-4 mb-6">
      <div class="stat-card bg-white">
        <div class="stat-label">质控员总数</div>
        <div class="stat-value text-blue-600">{{ summary.staff_count }}</div>
      </div>
      <div class="stat-card bg-white">
        <div class="stat-label">质控病历总数</div>
        <div class="stat-value text-green-600">{{ summary.total_qc }}</div>
      </div>
      <div class="stat-card bg-white">
        <div class="stat-label">复审病历总数</div>
        <div class="stat-value text-cyan-600">{{ summary.total_recheck }}</div>
      </div>
      <div class="stat-card bg-white">
        <div class="stat-label">发现缺陷总数</div>
        <div class="stat-value text-orange-600">{{ summary.total_defects }}</div>
      </div>
      <div class="stat-card bg-white">
        <div class="stat-label">平均通过率</div>
        <div class="stat-value text-purple-600">{{ summary.avg_pass_rate }}%</div>
      </div>
    </div>

    <!-- 排名表格 -->
    <div class="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden">
      <div class="p-4 border-b flex items-center justify-between">
        <span class="font-bold text-gray-700">详细排名</span>
        <a-radio-group v-model:value="sortBy" size="small" @change="fetchData">
          <a-radio-button value="qc_count">按质控数</a-radio-button>
          <a-radio-button value="defect_found">按缺陷数</a-radio-button>
          <a-radio-button value="recheck_count">按复审数</a-radio-button>
          <a-radio-button value="pass_rate">按通过率</a-radio-button>
        </a-radio-group>
      </div>

      <div class="divide-y">
        <div
          v-for="(staff, index) in rankings"
          :key="staff.user_id"
          class="flex items-center px-6 py-4 hover:bg-gray-50 transition-colors"
        >
          <!-- 排名 -->
          <div class="w-12 flex-shrink-0">
            <span
              :class="[
                'inline-flex items-center justify-center w-8 h-8 rounded-lg text-sm font-bold',
                index === 0 ? 'bg-gradient-to-br from-yellow-400 to-amber-500 text-white shadow-sm' :
                index === 1 ? 'bg-gradient-to-br from-gray-300 to-gray-400 text-white' :
                index === 2 ? 'bg-gradient-to-br from-amber-600 to-amber-700 text-white' :
                'bg-gray-100 text-gray-500'
              ]"
            >
              {{ index + 1 }}
            </span>
          </div>

          <!-- 用户信息 -->
          <div class="flex-1 min-w-0">
            <div class="font-medium text-gray-800">{{ staff.name }}</div>
            <div class="text-xs text-gray-400">{{ staff.department }} · 日均 {{ staff.avg_daily }} 份</div>
          </div>

          <!-- 数据条 -->
          <div class="flex items-center gap-6 text-sm">
            <div class="text-center w-20">
              <div class="font-bold text-blue-600">{{ staff.qc_count }}</div>
              <div class="text-[10px] text-gray-400">质控病历</div>
            </div>
            <div class="text-center w-20">
              <div class="font-bold text-orange-500">{{ staff.defect_found }}</div>
              <div class="text-[10px] text-gray-400">发现缺陷</div>
            </div>
            <div class="text-center w-20">
              <div class="font-bold text-cyan-600">{{ staff.recheck_count }}</div>
              <div class="text-[10px] text-gray-400">复审病历</div>
            </div>
            <div class="w-24">
              <div class="flex items-center gap-2">
                <div class="flex-1 h-1.5 bg-gray-100 rounded-full overflow-hidden">
                  <div
                    class="h-full rounded-full transition-all"
                    :class="staff.pass_rate >= 90 ? 'bg-green-500' : staff.pass_rate >= 80 ? 'bg-yellow-500' : 'bg-red-500'"
                    :style="{ width: staff.pass_rate + '%' }"
                  ></div>
                </div>
                <span class="text-xs font-medium" :class="staff.pass_rate >= 90 ? 'text-green-600' : 'text-orange-500'">
                  {{ staff.pass_rate }}%
                </span>
              </div>
              <div class="text-[10px] text-gray-400 text-right">通过率</div>
            </div>
          </div>
        </div>
      </div>

      <div v-if="!rankings.length" class="p-12 text-center text-gray-400">
        暂无数据
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import axios from 'axios'

const period = ref('本月')
const periodOptions = ['本周', '本月', '本季度']
const sortBy = ref('qc_count')
const rankings = ref<any[]>([])
const summary = ref<any>({ staff_count: 0, total_qc: 0, total_recheck: 0, total_defects: 0, avg_pass_rate: 0 })

const periodMap: Record<string, string> = {
  '本周': 'this_week',
  '本月': 'this_month',
  '本季度': 'this_quarter',
}

const fetchData = async () => {
  try {
    const res = await axios.get('/api/v1/staff-ranking', {
      params: {
        period: periodMap[period.value] || 'this_month',
        sort_by: sortBy.value,
      },
    })
    const data = res.data?.data
    if (data) {
      rankings.value = data.rankings || []
      summary.value = data.summary || {}
    }
  } catch (err) {
    console.error('获取排名失败:', err)
  }
}

onMounted(fetchData)
</script>

<style scoped>
.stat-card {
  border-radius: 12px;
  padding: 16px 20px;
  border: 1px solid #f0f0f0;
  box-shadow: 0 1px 3px rgba(0,0,0,0.04);
}
.stat-label {
  font-size: 12px;
  color: #999;
  margin-bottom: 4px;
}
.stat-value {
  font-size: 28px;
  font-weight: 800;
  line-height: 1.2;
}
</style>
