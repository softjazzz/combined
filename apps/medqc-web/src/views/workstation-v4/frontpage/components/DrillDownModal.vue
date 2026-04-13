<template>
  <a-modal
    :open="open"
    :title="title"
    width="1000px"
    :footer="null"
    @cancel="handleCancel"
  >
    <div class="p-4">
      <!-- Summary Info -->
      <div
        v-if="loading"
        class="flex justify-center py-10"
      >
        <a-spin tip="加载数据中..." />
      </div>

      <div v-else>
        <!-- Data Table -->
        <a-table
          :data-source="cases"
          :columns="columns"
          :pagination="{ pageSize: 10 }"
          row-key="record_id"
          size="middle"
        >
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'profit'">
              <span :class="record.profit_margin >= 0 ? 'text-green-600' : 'text-red-600'">
                {{ record.profit_margin.toFixed(2) }}
              </span>
            </template>
            <template v-else-if="column.key === 'status'">
              <a-tag :color="record.drg_code ? 'blue' : 'orange'">
                {{ record.drg_code ? '入组成功' : '未入组' }}
              </a-tag>
            </template>
          </template>
        </a-table>
      </div>
    </div>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import axios from 'axios'

const props = defineProps<{
  open: boolean
  dimension: string
  value: string
  sessionId?: string // 新增：session_id
  batchId?: string
  title: string
}>()

const emit = defineEmits(['update:open'])

interface DrillDownCase {
  record_id: string
  patient_gender: string
  patient_age: number
  dept_name: string
  primary_diagnosis: string
  drg_code?: string
  drg_name?: string
  total_cost?: number
  profit_margin: number
}

const loading = ref(false)
const cases = ref<DrillDownCase[]>([])

const columns = [
  { title: '病案号', dataIndex: 'record_id', key: 'record_id' },
  {
    title: '患者',
    dataIndex: 'patient_gender',
    key: 'patient_gender',
    customRender: ({ text, record }: { text: string; record: DrillDownCase }) =>
      `${text === '1' ? '男' : '女'} / ${record.patient_age}岁`,
  },
  { title: '科室', dataIndex: 'dept_name', key: 'dept_name' },
  { title: '主诊断', dataIndex: 'primary_diagnosis', key: 'primary_diagnosis' },
  { title: 'DRG编码', dataIndex: 'drg_code', key: 'drg_code' },
  { title: 'DRG名称', dataIndex: 'drg_name', key: 'drg_name', ellipsis: true },
  { title: '总费用', dataIndex: 'total_cost', key: 'total_cost' },
  {
    title: '盈亏',
    dataIndex: 'profit_margin',
    key: 'profit',
    sorter: (a: DrillDownCase, b: DrillDownCase) => a.profit_margin - b.profit_margin,
  },
  { title: '状态', key: 'status' },
]

const fetchData = async () => {
  if (!props.sessionId || !props.value) return

  loading.value = true
  try {
    const res = await axios.get('/api/v1/drg/drill-down', {
      params: {
        session_id: props.sessionId, // 传递 session_id
        batch_id: props.batchId,
        dimension: props.dimension,
        value: props.value,
      },
    })

    const payload = res.data?.data ?? res.data
    const records = payload?.records ?? payload
    cases.value = Array.isArray(records) ? records : []
  } catch (e) {
    console.error('Failed to fetch drill-down data', e)
    cases.value = []
  } finally {
    loading.value = false
  }
}

watch(
  () => props.open,
  (newVal) => {
    if (newVal) {
      fetchData()
    }
  },
)

const handleCancel = () => {
  emit('update:open', false)
}
</script>
