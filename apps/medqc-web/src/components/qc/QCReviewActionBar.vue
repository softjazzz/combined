<template>
  <div class="flex items-center gap-2">
    <!-- 确认问题 -->
    <a-tooltip title="确认此问题存在">
      <button 
        v-if="defect.status === 'pending'"
        class="action-btn confirm-btn"
        :disabled="actionLoading"
        @click.stop="handleConfirm"
      >
        <CheckCircleOutlined /> 确认
      </button>
    </a-tooltip>

    <!-- 标记误报 -->
    <a-tooltip title="标记为误报并忽略">
      <button 
        v-if="defect.status === 'pending' || defect.status === 'urged'"
        class="action-btn false-alarm-btn"
        :disabled="actionLoading"
        @click.stop="handleFalseAlarm"
      >
        <CloseCircleOutlined /> 误报
      </button>
    </a-tooltip>

    <!-- 派发整改 -->
    <a-tooltip title="派发给临床科室整改">
      <button 
        v-if="defect.status === 'urged'"
        class="action-btn remediation-btn"
        :disabled="actionLoading"
        @click.stop="showRemediationModal = true"
      >
        <SendOutlined /> 派发整改
      </button>
    </a-tooltip>

    <!-- 审核通过 -->
    <a-tooltip title="审核通过此问题">
      <button 
        v-if="defect.status === 'remediated'"
        class="action-btn approve-btn"
        :disabled="actionLoading"
        @click.stop="handleApprove"
      >
        <CheckOutlined /> 通过
      </button>
    </a-tooltip>

    <!-- 驳回 -->
    <a-tooltip title="驳回，需要重新整改">
      <button 
        v-if="defect.status === 'remediated'"
        class="action-btn reject-btn"
        :disabled="actionLoading"
        @click.stop="showRejectModal = true"
      >
        <RollbackOutlined /> 驳回
      </button>
    </a-tooltip>

    <!-- 催办 -->
    <a-tooltip title="发送催办提醒">
      <button 
        v-if="defect.status === 'pending' || defect.status === 'urged'"
        class="action-btn urge-btn"
        :disabled="actionLoading"
        @click.stop="handleUrge"
      >
        <BellOutlined /> 催办
      </button>
    </a-tooltip>

    <!-- 加载中指示 -->
    <a-spin v-if="actionLoading" size="small" class="ml-1" />

    <!-- 派发整改弹窗 -->
    <a-modal
      v-model:open="showRemediationModal"
      title="派发整改"
      @ok="handleRemediation"
      :confirm-loading="actionLoading"
      width="480px"
    >
      <div class="space-y-4 py-2">
        <div>
          <label class="block text-sm font-medium text-slate-700 mb-1">整改要求</label>
          <a-textarea 
            v-model:value="remediationForm.requirement" 
            placeholder="请描述整改要求..."
            :rows="3"
          />
        </div>
        <div>
          <label class="block text-sm font-medium text-slate-700 mb-1">整改期限</label>
          <a-date-picker 
            v-model:value="remediationForm.deadline" 
            class="w-full"
            placeholder="选择截止日期"
          />
        </div>
      </div>
    </a-modal>

    <!-- 驳回弹窗 -->
    <a-modal
      v-model:open="showRejectModal"
      title="驳回整改"
      @ok="handleReject"
      :confirm-loading="actionLoading"
      width="400px"
    >
      <div class="py-2">
        <label class="block text-sm font-medium text-slate-700 mb-1">驳回原因</label>
        <a-textarea 
          v-model:value="rejectReason" 
          placeholder="请输入驳回原因..."
          :rows="3"
        />
      </div>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { message } from 'ant-design-vue'
import {
  CheckCircleOutlined,
  CloseCircleOutlined,
  SendOutlined,
  CheckOutlined,
  RollbackOutlined,
  BellOutlined,
} from '@ant-design/icons-vue'
import {
  confirmDefect,
  markFalseAlarm,
  approveDefect,
  rejectDefect,
  urgeDefect,
  assignRemediation,
  type DefectItem,
} from '@/api/qcAdmin'

const props = defineProps<{
  defect: DefectItem
}>()

const emit = defineEmits<{
  (e: 'action-done'): void
}>()

const actionLoading = ref(false)
const showRemediationModal = ref(false)
const showRejectModal = ref(false)
const rejectReason = ref('')
const remediationForm = reactive({
  requirement: '',
  deadline: null as any,
})

/** 确认问题 */
const handleConfirm = async () => {
  actionLoading.value = true
  try {
    const res = await confirmDefect(props.defect.id)
    if (res.success) {
      message.success('已确认问题')
      emit('action-done')
    } else {
      message.error(res.message || '操作失败')
    }
  } finally {
    actionLoading.value = false
  }
}

/** 标记误报 */
const handleFalseAlarm = async () => {
  actionLoading.value = true
  try {
    const res = await markFalseAlarm(props.defect.id)
    if (res.success) {
      message.success('已标记为误报')
      emit('action-done')
    } else {
      message.error(res.message || '操作失败')
    }
  } finally {
    actionLoading.value = false
  }
}

/** 审核通过 */
const handleApprove = async () => {
  actionLoading.value = true
  try {
    const res = await approveDefect(props.defect.id)
    if (res.success) {
      message.success('审核通过')
      emit('action-done')
    } else {
      message.error(res.message || '操作失败')
    }
  } finally {
    actionLoading.value = false
  }
}

/** 派发整改 */
const handleRemediation = async () => {
  if (!remediationForm.requirement.trim()) {
    message.warning('请填写整改要求')
    return
  }
  actionLoading.value = true
  try {
    const res = await assignRemediation(props.defect.id, {
      assignee_id: '',  // TODO: 从病历关联医生获取
      assignee_name: '',
      remediation_requirement: remediationForm.requirement,
      deadline: remediationForm.deadline?.format?.('YYYY-MM-DD'),
    })
    if (res.success) {
      message.success('已派发整改')
      showRemediationModal.value = false
      remediationForm.requirement = ''
      remediationForm.deadline = null
      emit('action-done')
    } else {
      message.error(res.message || '操作失败')
    }
  } finally {
    actionLoading.value = false
  }
}

/** 驳回 */
const handleReject = async () => {
  if (!rejectReason.value.trim()) {
    message.warning('请填写驳回原因')
    return
  }
  actionLoading.value = true
  try {
    const res = await rejectDefect(props.defect.id, { reason: rejectReason.value })
    if (res.success) {
      message.success('已驳回')
      showRejectModal.value = false
      rejectReason.value = ''
      emit('action-done')
    } else {
      message.error(res.message || '操作失败')
    }
  } finally {
    actionLoading.value = false
  }
}

/** 催办 */
const handleUrge = async () => {
  actionLoading.value = true
  try {
    const res = await urgeDefect(props.defect.id, { message: '请尽快处理此质控问题' })
    if (res.success) {
      message.success('催办已发送')
      emit('action-done')
    } else {
      message.error(res.message || '操作失败')
    }
  } finally {
    actionLoading.value = false
  }
}
</script>

<style scoped>
.action-btn {
  @apply px-2.5 py-1.5 rounded-lg text-xs font-medium transition-all flex items-center gap-1.5 border;
}

.confirm-btn {
  @apply bg-blue-50 text-blue-600 border-blue-100 hover:bg-blue-100;
}

.false-alarm-btn {
  @apply bg-slate-50 text-slate-600 border-slate-200 hover:bg-slate-100;
}

.remediation-btn {
  @apply bg-amber-50 text-amber-600 border-amber-100 hover:bg-amber-100;
}

.approve-btn {
  @apply bg-emerald-50 text-emerald-600 border-emerald-100 hover:bg-emerald-100;
}

.reject-btn {
  @apply bg-rose-50 text-rose-600 border-rose-100 hover:bg-rose-100;
}

.urge-btn {
  @apply bg-orange-50 text-orange-600 border-orange-100 hover:bg-orange-100;
}

.action-btn:disabled {
  @apply opacity-50 cursor-not-allowed;
}
</style>
