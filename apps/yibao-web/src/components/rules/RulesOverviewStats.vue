<template>
  <div class="mb-6">
    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4 lg:gap-6">
      <!-- 总规则数 -->
      <a-card class="border border-gray-200 bg-white rounded-xl shadow-sm hover:shadow-md transition-colors duration-200">
        <a-statistic
          title="规则总数"
          :value="counts.total"
          :value-style="{ color: '#111827', fontSize: '28px', fontWeight: '700' }"
        >
          <template #prefix>
            <FileTextOutlined class="text-xl text-gray-500 mr-2" />
          </template>
        </a-statistic>
        <div class="mt-3">
          <span class="inline-flex items-center text-sm text-gray-600 font-medium">
            <ArrowUpOutlined class="w-4 h-4 mr-1" />
            较上月 +{{ monthlyGrowth }}
          </span>
        </div>
      </a-card>

      <!-- 启用规则数 -->
      <a-card class="border border-gray-200 bg-white rounded-xl shadow-sm hover:shadow-md transition-colors duration-200">
        <a-statistic
          title="已启用规则"
          :value="counts.enabled"
          :value-style="{ color: '#111827', fontSize: '28px', fontWeight: '700' }"
        >
          <template #prefix>
            <CheckCircleOutlined class="text-xl text-gray-500 mr-2" />
          </template>
        </a-statistic>
        <div class="mt-3 space-y-2">
          <a-progress
            :percent="enabledPercentage"
            :show-info="false"
            stroke-color="#10b981"
            size="small"
            class="mb-1"
          />
          <span class="text-xs text-gray-600 font-medium">启用率 {{ enabledPercentage }}%</span>
        </div>
      </a-card>

      <!-- 严重级别分布 -->
      <a-card class="border border-gray-200 bg-white rounded-xl shadow-sm hover:shadow-md transition-colors duration-200">
        <div class="space-y-4">
          <div class="text-base font-semibold text-gray-800">严重级别分布</div>
          <div class="space-y-3">
            <div class="space-y-2">
              <div class="flex items-center justify-between">
                <div class="flex items-center gap-2 text-gray-700">
                  <span class="w-2 h-2 rounded-full bg-red-500"></span>
                  <span class="text-sm">阻断</span>
                </div>
                <span class="text-sm font-semibold text-gray-800">{{ counts.bySeverity.block }}</span>
              </div>
              <a-progress
                :percent="getSeverityPercentage('block')"
                :show-info="false"
                stroke-color="#ef4444"
                size="small"
              />
            </div>
            <div class="space-y-2">
              <div class="flex items-center justify-between">
                <div class="flex items-center gap-2 text-gray-700">
                  <span class="w-2 h-2 rounded-full bg-amber-500"></span>
                  <span class="text-sm">警告</span>
                </div>
                <span class="text-sm font-semibold text-gray-800">{{ counts.bySeverity.warn }}</span>
              </div>
              <a-progress
                :percent="getSeverityPercentage('warn')"
                :show-info="false"
                stroke-color="#f59e0b"
                size="small"
              />
            </div>
            <div class="space-y-2">
              <div class="flex items-center justify-between">
                <div class="flex items-center gap-2 text-gray-700">
                  <span class="w-2 h-2 rounded-full bg-blue-500"></span>
                  <span class="text-sm">信息</span>
                </div>
                <span class="text-sm font-semibold text-gray-800">{{ counts.bySeverity.info }}</span>
              </div>
              <a-progress
                :percent="getSeverityPercentage('info')"
                :show-info="false"
                stroke-color="#3b82f6"
                size="small"
              />
            </div>
          </div>
        </div>
      </a-card>

      <!-- 规则类型分布 -->
      <a-card class="border border-gray-200 bg-white rounded-xl shadow-sm hover:shadow-md transition-colors duration-200">
        <div class="space-y-4">
          <div class="text-base font-semibold text-gray-800">规则类型分布</div>
          <div class="space-y-3">
            <div class="flex items-end justify-between h-20 px-2">
              <div
                v-for="(count, type) in counts.byType"
                :key="type"
                class="flex flex-col items-center space-y-1 flex-1"
              >
                <div
                  class="w-6 rounded-t bg-sky-500/70 transition-all duration-300"
                  :style="{ height: `${getTypePercentage(type)}%` }"
                ></div>
                <div class="text-xs text-gray-600 text-center leading-tight">{{ getTypeLabel(type) }}</div>
                <div class="text-xs font-semibold text-gray-800">{{ count }}</div>
              </div>
            </div>
          </div>
        </div>
      </a-card>

      <!-- 最近活动 -->
      <a-card class="border border-gray-200 bg-white rounded-xl shadow-sm hover:shadow-md transition-colors duration-200">
        <div class="space-y-4">
          <div class="flex items-center space-x-2 text-base font-semibold text-gray-800">
            <ClockCircleOutlined class="text-gray-500" />
            <span>最近活动</span>
          </div>
          <div class="space-y-3">
            <div class="flex items-center space-x-3">
              <div class="w-2 h-2 bg-gray-400 rounded-full flex-shrink-0"></div>
              <div class="flex-1 min-w-0">
                <div class="text-sm text-gray-700">今日新增 {{ todayStats.created }} 条规则</div>
                <div class="text-xs text-gray-500">{{ formatTime(new Date()) }}</div>
              </div>
            </div>
            <div class="flex items-center space-x-3">
              <div class="w-2 h-2 bg-gray-400 rounded-full flex-shrink-0"></div>
              <div class="flex-1 min-w-0">
                <div class="text-sm text-gray-700">今日更新 {{ todayStats.updated }} 条规则</div>
                <div class="text-xs text-gray-500">{{ formatTime(new Date()) }}</div>
              </div>
            </div>
            <div class="flex items-center space-x-3">
              <div class="w-2 h-2 bg-gray-400 rounded-full flex-shrink-0"></div>
              <div class="flex-1 min-w-0">
                <div class="text-sm text-gray-700">今日触发 {{ todayStats.triggered }} 次</div>
                <div class="text-xs text-gray-500">{{ formatTime(new Date()) }}</div>
              </div>
            </div>
          </div>
        </div>
      </a-card>

      <!-- 质控效果 -->
      <a-card class="border border-gray-200 bg-white rounded-xl shadow-sm hover:shadow-md transition-colors duration-200">
        <div class="space-y-4">
          <div class="flex items-center space-x-2 text-base font-semibold text-gray-800">
            <AimOutlined class="text-gray-500" />
            <span>质控效果</span>
          </div>
          <div class="grid grid-cols-1 gap-3">
            <div class="text-center p-2 rounded-md border border-gray-200 bg-gray-50">
              <div class="text-xl font-bold text-gray-800">{{ effectStats.intercepted }}</div>
              <div class="text-xs text-gray-600">拦截次数</div>
            </div>
            <div class="text-center p-2 rounded-md border border-gray-200 bg-gray-50">
              <div class="text-xl font-bold text-gray-800">{{ effectStats.warned }}</div>
              <div class="text-xs text-gray-600">警告次数</div>
            </div>
            <div class="text-center p-2 rounded-md border border-gray-200 bg-gray-50">
              <div class="text-xl font-bold text-gray-800">{{ effectStats.savedAmount }}</div>
              <div class="text-xs text-gray-600">节约金额(万元)</div>
            </div>
          </div>
        </div>
      </a-card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref, computed } from 'vue'
import { fetchRulesOverview } from '@/services/supabaseSdk'
import {
  FileTextOutlined, CheckCircleOutlined, ExclamationCircleOutlined,
  WarningOutlined, InfoCircleOutlined, ClockCircleOutlined,
  AimOutlined, ArrowUpOutlined
} from '@ant-design/icons-vue'

// 响应式数据
const counts = ref({
  total: 0,
  enabled: 0,
  bySeverity: { info: 0, warn: 0, block: 0 },
  byType: {
    drug_age: 0,
    drug_gender: 0,
    visit_type: 0,
    hospital_level: 0,
    duration: 0,
    surgery_pricing: 0
  }
})

const monthlyGrowth = ref(12)
const todayStats = ref({
  created: 3,
  updated: 8,
  triggered: 156
})

const effectStats = ref({
  intercepted: 45,
  warned: 128,
  savedAmount: 23.5
})

// 计算属性
const enabledPercentage = computed(() => {
  if (counts.value.total === 0) return 0
  return Math.round((counts.value.enabled / counts.value.total) * 100)
})

// 工具方法
const getSeverityPercentage = (severity: string) => {
  if (counts.value.total === 0) return 0
  const count = counts.value.bySeverity[severity as keyof typeof counts.value.bySeverity] || 0
  return Math.round((count / counts.value.total) * 100)
}

const getTypePercentage = (type: string) => {
  if (counts.value.total === 0) return 0
  const count = counts.value.byType[type as keyof typeof counts.value.byType] || 0
  const maxCount = Math.max(...Object.values(counts.value.byType))
  if (maxCount === 0) return 0
  return Math.round((count / maxCount) * 100)
}

const getTypeLabel = (type: string) => {
  const labelMap: Record<string, string> = {
    drug_age: '年龄',
    drug_gender: '性别',
    visit_type: '就诊',
    hospital_level: '机构',
    duration: '疗程',
    surgery_pricing: '手术'
  }
  return labelMap[type] || type
}

const formatTime = (date: Date) => {
  return date.toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit'
  })
}

// 数据加载
async function load() {
  try {
    const overview = await fetchRulesOverview()
    counts.value = {
      ...overview,
      byType: {
        drug_age: 15,
        drug_gender: 12,
        visit_type: 8,
        hospital_level: 6,
        duration: 10,
        surgery_pricing: 4
      }
    }
  } catch (error) {
    console.error('加载统计数据失败:', error)
  }
}

onMounted(load)
</script>






