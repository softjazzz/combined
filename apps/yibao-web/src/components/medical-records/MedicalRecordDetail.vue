<template>
  <a-modal
    v-model:open="visible"
    title="医保病历详情"
    width="1000px"
    :footer="null"
    @cancel="handleClose"
  >
    <div v-if="record" class="medical-record-detail">
      <!-- 基本信息 -->
      <div class="mb-6">
        <h3 class="text-lg font-semibold mb-4 text-gray-800">基本信息</h3>
        <div class="grid grid-cols-2 md:grid-cols-3 gap-4">
          <div class="info-item">
            <label class="info-label">患者姓名</label>
            <div class="info-value">{{ record.patient_name }}</div>
          </div>
          <div class="info-item">
            <label class="info-label">年龄/性别</label>
            <div class="info-value">{{ record.patient_age }}岁 / {{ record.patient_gender === 'M' ? '男' : '女' }}</div>
          </div>
          <div class="info-item">
            <label class="info-label">身份证号</label>
            <div class="info-value">{{ record.patient_id_card }}</div>
          </div>
          <div class="info-item">
            <label class="info-label">医保类型</label>
            <div class="info-value">
              <a-tag :color="getInsuranceTypeColor(record.insurance_type)">
                {{ getInsuranceTypeLabel(record.insurance_type) }}
              </a-tag>
            </div>
          </div>
          <div class="info-item">
            <label class="info-label">医保号</label>
            <div class="info-value">{{ record.insurance_number }}</div>
          </div>
          <div class="info-item">
            <label class="info-label">科室</label>
            <div class="info-value">{{ record.department }}</div>
          </div>
          <div class="info-item">
            <label class="info-label">主治医生</label>
            <div class="info-value">{{ record.doctor_name }}</div>
          </div>
          <div class="info-item">
            <label class="info-label">入院日期</label>
            <div class="info-value">{{ record.admission_date }}</div>
          </div>
          <div class="info-item">
            <label class="info-label">出院日期</label>
            <div class="info-value">{{ record.discharge_date || '未出院' }}</div>
          </div>
        </div>
      </div>

      <!-- 诊断信息 -->
      <div class="mb-6">
        <h3 class="text-lg font-semibold mb-4 text-gray-800">诊断信息</h3>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div class="info-item">
            <label class="info-label">主要诊断</label>
            <div class="info-value">{{ record.diagnosis_primary }}</div>
          </div>
          <div class="info-item">
            <label class="info-label">次要诊断</label>
            <div class="info-value">
              <div v-if="record.diagnosis_secondary && record.diagnosis_secondary.length > 0">
                <a-tag v-for="diagnosis in record.diagnosis_secondary" :key="diagnosis" class="mb-1">
                  {{ diagnosis }}
                </a-tag>
              </div>
              <span v-else class="text-gray-400">无</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 费用信息 -->
      <div class="mb-6">
        <h3 class="text-lg font-semibold mb-4 text-gray-800">费用信息</h3>
        <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div class="cost-card">
            <div class="cost-label">总费用</div>
            <div class="cost-value text-blue-600">¥{{ record.total_cost.toLocaleString() }}</div>
          </div>
          <div class="cost-card">
            <div class="cost-label">医保支付</div>
            <div class="cost-value text-green-600">¥{{ record.insurance_cost.toLocaleString() }}</div>
          </div>
          <div class="cost-card">
            <div class="cost-label">自费金额</div>
            <div class="cost-value text-orange-600">¥{{ record.self_pay_cost.toLocaleString() }}</div>
          </div>
        </div>
        <div class="mt-4">
          <div class="flex items-center justify-between text-sm text-gray-600">
            <span>医保报销比例</span>
            <span class="font-medium">{{ ((record.insurance_cost / record.total_cost) * 100).toFixed(1) }}%</span>
          </div>
          <div class="w-full bg-gray-200 rounded-full h-2 mt-2">
            <div 
              class="bg-green-500 h-2 rounded-full" 
              :style="{ width: `${(record.insurance_cost / record.total_cost) * 100}%` }"
            ></div>
          </div>
        </div>
      </div>

      <!-- 审核状态 -->
      <div class="mb-6">
        <h3 class="text-lg font-semibold mb-4 text-gray-800">审核状态</h3>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div class="info-item">
            <label class="info-label">当前状态</label>
            <div class="info-value">
              <a-tag :color="getStatusColor(record.status)" class="text-sm">
                {{ getStatusLabel(record.status) }}
              </a-tag>
            </div>
          </div>
          <div class="info-item">
            <label class="info-label">违规风险</label>
            <div class="info-value">
              <a-tag :color="getViolationRiskColor(record.violation_risk)" class="text-sm">
                {{ getViolationRiskLabel(record.violation_risk) }}
              </a-tag>
            </div>
          </div>
          <div v-if="record.violation_reasons && record.violation_reasons.length > 0" class="info-item md:col-span-2">
            <label class="info-label">违规原因</label>
            <div class="info-value">
              <a-tag v-for="reason in record.violation_reasons" :key="reason" color="red" class="mb-1">
                {{ reason }}
              </a-tag>
            </div>
          </div>
          <div v-if="record.reviewed_at" class="info-item">
            <label class="info-label">审核时间</label>
            <div class="info-value">{{ formatDateTime(record.reviewed_at) }}</div>
          </div>
          <div v-if="record.reviewer_notes" class="info-item md:col-span-2">
            <label class="info-label">审核备注</label>
            <div class="info-value">{{ record.reviewer_notes }}</div>
          </div>
        </div>
      </div>

      <!-- 质控信息 -->
      <div class="mb-6">
        <h3 class="text-lg font-semibold mb-4 text-gray-800">质控信息</h3>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div class="info-item">
            <label class="info-label">质控评分</label>
            <div class="info-value">
              <span class="text-lg font-semibold" :class="getScoreColor(record.qc_score)">
                {{ record.qc_score || 'N/A' }}
              </span>
              <span class="text-gray-500 ml-1">/ 100</span>
            </div>
          </div>
          <div class="info-item">
            <label class="info-label">质控等级</label>
            <div class="info-value">
              <a-tag :color="getGradeColor(record.qc_grade)" class="text-sm">
                {{ record.qc_grade || 'N/A' }}
              </a-tag>
            </div>
          </div>
        </div>
      </div>

      <!-- 病历内容 -->
      <div class="mb-6">
        <h3 class="text-lg font-semibold mb-4 text-gray-800">病历内容</h3>
        <div class="content-box">
          <pre class="whitespace-pre-wrap text-sm text-gray-700">{{ record.content }}</pre>
        </div>
      </div>

      <!-- 操作按钮 -->
      <div class="flex justify-end gap-3 pt-4 border-t border-gray-200">
        <a-button @click="handleClose">关闭</a-button>
        <a-button type="primary" @click="handleEdit">编辑</a-button>
        <a-button 
          v-if="record.status === 'pending' || record.status === 'reviewing'" 
          type="primary" 
          @click="handleApprove"
        >
          审核通过
        </a-button>
        <a-button 
          v-if="record.status === 'pending' || record.status === 'reviewing'" 
          danger 
          @click="handleReject"
        >
          审核拒绝
        </a-button>
      </div>
    </div>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { message } from 'ant-design-vue'
import type { MedicalRecord } from '@/types/medical-records'
import { 
  STATUS_OPTIONS, 
  INSURANCE_TYPES, 
  VIOLATION_RISK_OPTIONS 
} from '@/types/medical-records'
import { updateMedicalRecord } from '@/api/medical-records'

// Props
interface Props {
  record?: MedicalRecord | null
}

const props = defineProps<Props>()

// Emits
const emit = defineEmits<{
  close: []
  edit: [record: MedicalRecord]
  update: []
}>()

// 响应式数据
const visible = computed({
  get: () => !!props.record,
  set: () => emit('close')
})

// 工具函数
function getStatusColor(status: string) {
  const option = STATUS_OPTIONS.find(s => s.value === status)
  return option?.color || '#666'
}

function getStatusLabel(status: string) {
  const option = STATUS_OPTIONS.find(s => s.value === status)
  return option?.label || status
}

function getInsuranceTypeColor(type: string) {
  const colors = {
    basic: '#1890ff',
    commercial: '#52c41a',
    government: '#722ed1',
    self_pay: '#faad14'
  }
  return colors[type as keyof typeof colors] || '#666'
}

function getInsuranceTypeLabel(type: string) {
  const option = INSURANCE_TYPES.find(t => t.value === type)
  return option?.label || type
}

function getViolationRiskColor(risk: string) {
  const option = VIOLATION_RISK_OPTIONS.find(r => r.value === risk)
  return option?.color || '#666'
}

function getViolationRiskLabel(risk: string) {
  const option = VIOLATION_RISK_OPTIONS.find(r => r.value === risk)
  return option?.label || risk
}

function getScoreColor(score?: number) {
  if (!score) return 'text-gray-400'
  if (score >= 90) return 'text-green-600'
  if (score >= 80) return 'text-blue-600'
  if (score >= 70) return 'text-orange-600'
  return 'text-red-600'
}

function getGradeColor(grade?: string) {
  const colors = {
    A: '#52c41a',
    B: '#1890ff',
    C: '#faad14',
    D: '#f5222d'
  }
  return colors[grade as keyof typeof colors] || '#666'
}

function formatDateTime(dateTime: string) {
  return new Date(dateTime).toLocaleString('zh-CN')
}

// 事件处理
function handleClose() {
  emit('close')
}

function handleEdit() {
  if (props.record) {
    emit('edit', props.record)
  }
}

async function handleApprove() {
  if (!props.record) return
  
  try {
    await updateMedicalRecord(props.record.id, { 
      status: 'approved',
      reviewed_at: new Date().toISOString()
    })
    message.success('审核通过')
    emit('update')
    emit('close')
  } catch (error) {
    message.error('操作失败')
  }
}

async function handleReject() {
  if (!props.record) return
  
  try {
    await updateMedicalRecord(props.record.id, { 
      status: 'rejected',
      reviewed_at: new Date().toISOString()
    })
    message.success('审核拒绝')
    emit('update')
    emit('close')
  } catch (error) {
    message.error('操作失败')
  }
}
</script>

<style scoped>
.info-item {
  @apply bg-gray-50 p-3 rounded-lg;
}

.info-label {
  @apply block text-sm font-medium text-gray-600 mb-1;
}

.info-value {
  @apply text-sm text-gray-900;
}

.cost-card {
  @apply bg-gradient-to-r from-gray-50 to-gray-100 p-4 rounded-lg text-center;
}

.cost-label {
  @apply text-sm text-gray-600 mb-1;
}

.cost-value {
  @apply text-xl font-bold;
}

.content-box {
  @apply bg-gray-50 p-4 rounded-lg border border-gray-200 max-h-60 overflow-y-auto;
}
</style>
