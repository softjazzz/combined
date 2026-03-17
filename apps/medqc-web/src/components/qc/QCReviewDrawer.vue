<template>
  <a-drawer
    :open="visible"
    title="病历联审详情"
    placement="right"
    :width="960"
    @close="handleClose"
    class="qc-review-drawer"
    :destroyOnClose="true"
  >
    <!-- 顶部：病历基本信息 -->
    <div class="bg-slate-50 rounded-xl p-4 mb-4 border border-slate-100">
      <div class="flex items-center justify-between mb-3">
        <div class="flex items-center gap-3">
          <div class="w-10 h-10 rounded-full bg-blue-100 flex items-center justify-center text-blue-600 font-bold text-sm">
            {{ (record?.patient_name || '').charAt(0) }}
          </div>
          <div>
            <div class="text-base font-bold text-slate-800">{{ record?.patient_name || '-' }}</div>
            <div class="text-xs text-slate-400">病案号：{{ record?.record_id || '-' }}</div>
          </div>
        </div>
        <span 
          class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium border"
          :class="statusClass"
        >
          <span class="w-1.5 h-1.5 rounded-full" :class="statusDotClass"></span>
          {{ statusText }}
        </span>
      </div>
      <div class="grid grid-cols-4 gap-4 text-sm">
        <div>
          <span class="text-slate-400">科室</span>
          <div class="font-medium text-slate-700 mt-0.5">{{ record?.department || '-' }}</div>
        </div>
        <div>
          <span class="text-slate-400">出院日期</span>
          <div class="font-medium text-slate-700 mt-0.5">{{ record?.discharge_date || '-' }}</div>
        </div>
        <div>
          <span class="text-slate-400">质控得分</span>
          <div class="font-medium font-mono mt-0.5" :style="{ color: getScoreColor(record?.score) }">
            {{ record?.score ?? '-' }}
          </div>
        </div>
        <div>
          <span class="text-slate-400">缺陷数</span>
          <div class="font-medium text-slate-700 mt-0.5">{{ record?.defect_count || 0 }}</div>
        </div>
      </div>
    </div>

    <!-- 缺陷列表 -->
    <div class="mb-4">
      <div class="flex items-center justify-between mb-3">
        <h3 class="text-sm font-bold text-slate-800">
          质控问题列表
          <span class="text-xs text-slate-400 font-normal ml-2">共 {{ defectList.length }} 项</span>
        </h3>
        <a-button size="small" type="text" class="text-slate-500" @click="loadDefects">
          <ReloadOutlined :spin="defectLoading" />
        </a-button>
      </div>

      <a-spin :spinning="defectLoading">
        <div v-if="defectList.length === 0" class="text-center py-8 text-slate-400 text-sm">
          暂无质控问题
        </div>
        <div v-else class="space-y-3 max-h-[calc(100vh-420px)] overflow-y-auto pr-1">
          <div 
            v-for="defect in defectList" 
            :key="defect.id"
            class="bg-white rounded-xl border border-slate-100 p-4 hover:shadow-md transition-all cursor-pointer group"
            :class="{ 'ring-2 ring-blue-200 border-blue-200': selectedDefectId === defect.id }"
            @click="selectedDefectId = defect.id"
          >
            <div class="flex items-start justify-between mb-2">
              <div class="flex items-center gap-2">
                <span 
                  class="w-2 h-2 rounded-full flex-shrink-0"
                  :class="{
                    'bg-rose-500': defect.severity === 'critical' || defect.severity === 'error',
                    'bg-amber-500': defect.severity === 'warning',
                    'bg-blue-500': defect.severity === 'info',
                  }"
                ></span>
                <span class="text-sm font-medium text-slate-800">{{ defect.rule_name }}</span>
              </div>
              <span 
                class="text-xs px-2 py-0.5 rounded-md font-medium"
                :class="{
                  'bg-amber-50 text-amber-600': defect.status === 'pending',
                  'bg-blue-50 text-blue-600': defect.status === 'urged',
                  'bg-emerald-50 text-emerald-600': defect.status === 'approved',
                  'bg-rose-50 text-rose-600': defect.status === 'rejected',
                  'bg-slate-100 text-slate-500': defect.status === 'remediated',
                }"
              >
                {{ getDefectStatusText(defect.status) }}
              </span>
            </div>
            <p class="text-xs text-slate-500 mb-2 line-clamp-2">{{ defect.description }}</p>
            <div class="flex items-center gap-4 text-xs text-slate-400">
              <span>分类：{{ defect.category }}</span>
              <span>位置：{{ defect.location }}</span>
            </div>

            <!-- 操作按钮（选中时显示） -->
            <QCReviewActionBar 
              v-if="selectedDefectId === defect.id"
              :defect="defect"
              class="mt-3 pt-3 border-t border-slate-100"
              @action-done="handleActionDone"
            />
          </div>
        </div>
      </a-spin>
    </div>
  </a-drawer>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { ReloadOutlined } from '@ant-design/icons-vue'
import { getDefectList, type DefectItem } from '@/api/qcAdmin'
import QCReviewActionBar from './QCReviewActionBar.vue'

interface RecordData {
  id: string
  record_id: string
  patient_name?: string
  department?: string
  discharge_date?: string
  score?: number
  defect_count?: number
  status?: string
}

const props = defineProps<{
  visible: boolean
  record: RecordData | null
}>()

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
  (e: 'close'): void
  (e: 'refresh'): void
}>()

const defectLoading = ref(false)
const defectList = ref<DefectItem[]>([])
const selectedDefectId = ref<string | null>(null)

// 状态样式计算
const statusClass = computed(() => {
  const s = props.record?.status
  if (s === 'completed' || s === 'passed' || s === 'approved') return 'bg-emerald-50 text-emerald-600 border-emerald-100'
  if (s === 'failed' || s === 'rejected') return 'bg-rose-50 text-rose-600 border-rose-100'
  return 'bg-amber-50 text-amber-600 border-amber-100'
})

const statusDotClass = computed(() => {
  const s = props.record?.status
  if (s === 'completed' || s === 'passed' || s === 'approved') return 'bg-emerald-500'
  if (s === 'failed' || s === 'rejected') return 'bg-rose-500'
  return 'bg-amber-500'
})

const statusText = computed(() => {
  const map: Record<string, string> = {
    pending: '待质控', urged: '已催办', remediated: '已整改',
    approved: '已通过', rejected: '已驳回',
    completed: '已通过', passed: '已通过', failed: '未通过',
  }
  return map[props.record?.status || ''] || props.record?.status || '-'
})

const getScoreColor = (score?: number) => {
  if (!score) return '#94a3b8'
  if (score >= 90) return '#10b981'
  if (score >= 80) return '#3b82f6'
  if (score >= 60) return '#f59e0b'
  return '#f43f5e'
}

const getDefectStatusText = (status: string) => {
  const map: Record<string, string> = {
    pending: '待处理', urged: '已催办',
    remediated: '已整改', approved: '已通过', rejected: '已驳回',
  }
  return map[status] || status
}

// 加载缺陷列表
const loadDefects = async () => {
  if (!props.record?.record_id) return
  defectLoading.value = true
  try {
    const res = await getDefectList({ record_id: props.record.record_id })
    if (res.success && res.data) {
      defectList.value = (res.data as any).items || (res.data as any) || []
    }
  } catch {
    defectList.value = []
  } finally {
    defectLoading.value = false
  }
}

// 操作完成后刷新
const handleActionDone = () => {
  loadDefects()
  emit('refresh')
}

const handleClose = () => {
  emit('update:visible', false)
  emit('close')
}

// 打开时自动加载
watch(() => props.visible, (val) => {
  if (val && props.record) {
    selectedDefectId.value = null
    loadDefects()
  }
})
</script>

<style scoped>
.qc-review-drawer :deep(.ant-drawer-body) {
  padding: 20px;
  background: #fafbfc;
}

.line-clamp-2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>
