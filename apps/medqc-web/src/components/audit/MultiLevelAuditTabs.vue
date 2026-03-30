<!-- 多级审核结果展示组件 -->
<template>
  <div class="multi-level-audit">
    <!-- 审核级别标签页 -->
    <a-tabs
      v-model:active-key="activeTab"
      class="audit-level-tabs"
      @change="handleTabChange"
    >
      <!-- 科室级审核 -->
      <a-tab-pane
        key="department"
        tab="科室级审核"
      >
        <template #tab>
          <span class="tab-title">
            <TeamOutlined />
            科室级审核
            <a-badge
              v-if="auditResults.department?.status === 'approved'"
              status="success"
              class="tab-badge"
            />
            <a-badge
              v-else-if="auditResults.department?.status === 'submitted'"
              status="processing"
              class="tab-badge"
            />
          </span>
        </template>

        <AuditResultPanel
          :audit-result="auditResults.department"
          :editable="canEditDepartmentLevel"
          :reviewer-info="departmentReviewer"
          audit-level="department"
          @update="handleDepartmentUpdate"
          @submit="(auditResultId) => handleSubmitResult('department', auditResultId)"
        />
      </a-tab-pane>

      <!-- 院级审核 -->
      <a-tab-pane
        key="hospital"
        tab="院级审核"
        :disabled="!auditResults.department?.is_final"
      >
        <template #tab>
          <span class="tab-title">
            <BankOutlined />
            院级审核
            <a-badge
              v-if="auditResults.hospital?.status === 'approved'"
              status="success"
              class="tab-badge"
            />
            <a-badge
              v-else-if="auditResults.hospital?.status === 'submitted'"
              status="processing"
              class="tab-badge"
            />
          </span>
        </template>

        <AuditResultPanel
          :audit-result="auditResults.hospital"
          :editable="canEditHospitalLevel"
          :reviewer-info="hospitalReviewer"
          :can-modify-lower-level="true"
          :lower-level-results="[auditResults.department]"
          audit-level="hospital"
          @update="handleHospitalUpdate"
          @submit="(auditResultId) => handleSubmitResult('hospital', auditResultId)"
          @modify-lower="handleModifyLowerLevel"
        />
      </a-tab-pane>

      <!-- 专家级审核 -->
      <a-tab-pane
        key="expert"
        tab="专家级审核"
        :disabled="!auditResults.hospital?.is_final"
      >
        <template #tab>
          <span class="tab-title">
            <CrownOutlined />
            专家级审核
            <a-badge
              v-if="auditResults.expert?.status === 'approved'"
              status="success"
              class="tab-badge"
            />
            <a-badge
              v-else-if="auditResults.expert?.status === 'submitted'"
              status="processing"
              class="tab-badge"
            />
          </span>
        </template>

        <AuditResultPanel
          :audit-result="auditResults.expert"
          :editable="canEditExpertLevel"
          :reviewer-info="expertReviewer"
          :can-modify-lower-level="true"
          :lower-level-results="[auditResults.department, auditResults.hospital]"
          :is-final-level="true"
          audit-level="expert"
          @update="handleExpertUpdate"
          @submit="(auditResultId) => handleSubmitResult('expert', auditResultId)"
          @modify-lower="handleModifyLowerLevel"
        />
      </a-tab-pane>
    </a-tabs>

    <!-- 审核历史时间线 -->
    <div class="audit-timeline-section">
      <a-divider>审核历史</a-divider>
      <AuditTimeline
        :audit-history="auditHistory"
        :current-level="activeTab"
        @view-detail="handleViewHistoryDetail"
      />
    </div>

    <!-- 修改下级结果对话框 -->
    <a-modal
      v-model:open="modifyModalVisible"
      title="修改下级审核结果"
      width="800px"
      @ok="handleConfirmModification"
    >
      <ModifyLowerLevelForm
        v-if="modifyModalVisible"
        ref="modifyFormRef"
        :original-result="modifyTarget"
        :current-level="activeTab"
        @change="handleModificationChange"
      />
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { message } from 'ant-design-vue'
import { TeamOutlined, BankOutlined, CrownOutlined } from '@ant-design/icons-vue'

import type { QCAuditResult, AuditLevel, QCAuditTaskItem } from '@/types/audit-module'

import { useAuthStore } from '@/stores/auth'
import { auditResultService } from '@/services/audit-result-service'
// import AuditResultPanel from './AuditResultPanel.vue'
// import AuditTimeline from './AuditTimeline.vue'
// import ModifyLowerLevelForm from './ModifyLowerLevelForm.vue'

// Props
interface Props {
  taskItemId: string
  taskItem?: QCAuditTaskItem
}

interface AuditHistoryItem {
  level: AuditLevel
  reviewer: string
  score: number
  status: QCAuditResult['status']
  submitted_at: string | null | undefined
  review_duration: QCAuditResult['review_duration']
}

interface ModifyFormRef {
  validateAndGetData: () => Promise<ModifyLowerLevelPayload | null | undefined>
}

type CreateAuditResultPayload = Parameters<typeof auditResultService.createAuditResult>[3]
type ModifyLowerLevelPayload = Parameters<typeof auditResultService.modifyLowerLevelResult>[2]

const props = defineProps<Props>()

// Emits
const emit = defineEmits<{
  'result-updated': [level: AuditLevel, result: QCAuditResult]
  'result-submitted': [level: AuditLevel, result: QCAuditResult]
}>()

// 状态管理
const authStore = useAuthStore()
const activeTab = ref<AuditLevel>('department')
const loading = ref(false)

// 审核结果数据
const auditResults = ref<Record<AuditLevel, QCAuditResult | null>>({
  department: null,
  hospital: null,
  expert: null,
})

const auditHistory = ref<AuditHistoryItem[]>([])

// 修改下级结果相关
const modifyModalVisible = ref(false)
const modifyTarget = ref<QCAuditResult | null>(null)
const modifyFormRef = ref<ModifyFormRef | null>(null)

// 审核员信息
const departmentReviewer = computed(() => auditResults.value.department?.reviewer_name)
const hospitalReviewer = computed(() => auditResults.value.hospital?.reviewer_name)
const expertReviewer = computed(() => auditResults.value.expert?.reviewer_name)

// 权限控制
const canEditDepartmentLevel = computed(
  () =>
    authStore.hasRole('qc_reviewer_dept') &&
    (!auditResults.value.department?.is_final || auditResults.value.department?.status === 'draft'),
)

const canEditHospitalLevel = computed(
  () =>
    authStore.hasRole('qc_reviewer_hospital') &&
    auditResults.value.department?.is_final &&
    (!auditResults.value.hospital?.is_final || auditResults.value.hospital?.status === 'draft'),
)

const canEditExpertLevel = computed(
  () =>
    authStore.hasRole('qc_reviewer_expert') &&
    auditResults.value.hospital?.is_final &&
    (!auditResults.value.expert?.is_final || auditResults.value.expert?.status === 'draft'),
)

const getErrorMessage = (error: unknown): string => {
  if (error instanceof Error) return error.message
  if (typeof error === 'object' && error && 'message' in error) {
    return String((error as { message?: unknown }).message || '未知错误')
  }
  return '未知错误'
}

const getCurrentReviewerId = (): string | null => {
  const reviewerId = authStore.user?.id
  if (!reviewerId) {
    message.error('未获取到当前用户，请重新登录后重试')
    return null
  }
  return reviewerId
}

// 方法
const loadAuditResults = async () => {
  try {
    loading.value = true

    const results = await auditResultService.getAuditResults(props.taskItemId, true)

    // 按级别分组
    auditResults.value = {
      department: results.find((r) => r.audit_level === 'department') || null,
      hospital: results.find((r) => r.audit_level === 'hospital') || null,
      expert: results.find((r) => r.audit_level === 'expert') || null,
    }

    // 构建审核历史
    auditHistory.value = results
      .map((result) => ({
        level: result.audit_level,
        reviewer: result.reviewer_name || '',
        score: result.audit_score,
        status: result.status,
        submitted_at: result.submitted_at,
        review_duration: result.review_duration,
      }))
      .sort(
        (a, b) =>
          new Date(a.submitted_at || '').getTime() - new Date(b.submitted_at || '').getTime(),
      )
  } catch (error: unknown) {
    message.error(`加载审核结果失败: ${getErrorMessage(error)}`)
  } finally {
    loading.value = false
  }
}

const handleTabChange = (key: string) => {
  activeTab.value = key as AuditLevel
}

const handleDepartmentUpdate = async (resultData: CreateAuditResultPayload) => {
  try {
    const reviewerId = getCurrentReviewerId()
    if (!reviewerId) return

    const result = await auditResultService.createAuditResult(
      props.taskItemId,
      'department',
      reviewerId,
      resultData,
    )

    auditResults.value.department = result
    emit('result-updated', 'department', result)
    message.success('科室级审核结果已保存')
  } catch (error: unknown) {
    message.error(`保存失败: ${getErrorMessage(error)}`)
  }
}

const handleHospitalUpdate = async (resultData: CreateAuditResultPayload) => {
  try {
    const reviewerId = getCurrentReviewerId()
    if (!reviewerId) return

    const result = await auditResultService.createAuditResult(
      props.taskItemId,
      'hospital',
      reviewerId,
      resultData,
    )

    auditResults.value.hospital = result
    emit('result-updated', 'hospital', result)
    message.success('院级审核结果已保存')
  } catch (error: unknown) {
    message.error(`保存失败: ${getErrorMessage(error)}`)
  }
}

const handleExpertUpdate = async (resultData: CreateAuditResultPayload) => {
  try {
    const reviewerId = getCurrentReviewerId()
    if (!reviewerId) return

    const result = await auditResultService.createAuditResult(
      props.taskItemId,
      'expert',
      reviewerId,
      resultData,
    )

    auditResults.value.expert = result
    emit('result-updated', 'expert', result)
    message.success('专家级审核结果已保存')
  } catch (error: unknown) {
    message.error(`保存失败: ${getErrorMessage(error)}`)
  }
}

const handleSubmitResult = async (level: AuditLevel, auditResultId: string) => {
  try {
    await auditResultService.submitAuditResult(auditResultId)

    // 刷新数据
    await loadAuditResults()

    emit('result-submitted', level, auditResults.value[level]!)
    message.success(`${level}级审核结果已提交`)
  } catch (error: unknown) {
    message.error(`提交失败: ${getErrorMessage(error)}`)
  }
}

const handleModifyLowerLevel = (targetResult: QCAuditResult) => {
  modifyTarget.value = targetResult
  modifyModalVisible.value = true
}

const handleConfirmModification = async () => {
  try {
    const formData = await modifyFormRef.value?.validateAndGetData()

    if (!formData || !modifyTarget.value) {
      return
    }

    const reviewerId = getCurrentReviewerId()
    if (!reviewerId) return

    await auditResultService.modifyLowerLevelResult(modifyTarget.value.id, reviewerId, formData)

    modifyModalVisible.value = false
    await loadAuditResults()

    message.success('下级审核结果修改成功')
  } catch (error: unknown) {
    message.error(`修改失败: ${getErrorMessage(error)}`)
  }
}

const handleModificationChange = (_data: ModifyLowerLevelPayload) => {
  // 处理修改表单数据变化
}

const handleViewHistoryDetail = (historyItem: AuditHistoryItem) => {
  // 查看历史详情
  console.log('查看历史详情:', historyItem)
}

// 监听任务项变化
watch(
  () => props.taskItemId,
  () => {
    if (props.taskItemId) {
      loadAuditResults()
    }
  },
  { immediate: true },
)

onMounted(() => {
  if (props.taskItemId) {
    loadAuditResults()
  }
})
</script>

<style scoped>
.multi-level-audit {
  background: white;
  border-radius: 8px;
  padding: 24px;
}

.audit-level-tabs {
  margin-bottom: 24px;
}

.audit-level-tabs :deep(.ant-tabs-nav) {
  margin-bottom: 24px;
}

.tab-title {
  display: flex;
  align-items: center;
  gap: 8px;
}

.tab-badge {
  margin-left: 4px;
}

.audit-level-tabs :deep(.ant-tabs-tab) {
  padding: 12px 24px;
  font-weight: 500;
}

.audit-level-tabs :deep(.ant-tabs-tab-active) {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border-radius: 6px 6px 0 0;
}

.audit-level-tabs :deep(.ant-tabs-tab-disabled) {
  opacity: 0.5;
  cursor: not-allowed;
}

.audit-timeline-section {
  margin-top: 32px;
  padding-top: 24px;
  border-top: 1px solid #f0f0f0;
}

.audit-timeline-section :deep(.ant-divider) {
  font-size: 16px;
  font-weight: 600;
  color: #262626;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .multi-level-audit {
    padding: 16px;
  }

  .audit-level-tabs :deep(.ant-tabs-tab) {
    padding: 8px 16px;
    font-size: 14px;
  }

  .tab-title {
    flex-direction: column;
    gap: 4px;
  }
}

/* 加载状态 */
.multi-level-audit.loading {
  position: relative;
  min-height: 400px;
}

.multi-level-audit.loading::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(255, 255, 255, 0.8);
  z-index: 10;
}

/* 动画效果 */
.audit-level-tabs :deep(.ant-tabs-content-holder) {
  transition: all 0.3s ease;
}

.audit-timeline-section {
  animation: fadeInUp 0.5s ease;
}

@keyframes fadeInUp {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
</style>
