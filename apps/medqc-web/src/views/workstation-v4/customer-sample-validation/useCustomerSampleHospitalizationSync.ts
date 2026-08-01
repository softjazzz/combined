import { computed, ref, type Ref } from 'vue'
import { message } from 'ant-design-vue'
import type {
  HospitalizationScopeMode,
  HospitalizationScopePayload,
  HospitalizationScopePreview,
} from './types'
import {
  previewManualSamplePoolHospitalizationScope,
  syncManualSamplePoolRecordsByHospitalization,
} from '@/services/manual-case-sample-service'

export interface CustomerSampleHospitalizationSyncDependencies {
  selectedPoolId: Ref<string | undefined>
  openSyncJob: (jobId: string) => Promise<void>
}

export function useCustomerSampleHospitalizationSync(
  dependencies: CustomerSampleHospitalizationSyncDependencies,
) {
  const { selectedPoolId, openSyncJob } = dependencies

  const hospitalizationSyncModalOpen = ref(false)
  const hospitalizationSyncSubmitting = ref(false)
  const hospitalizationSyncPreviewLoading = ref(false)
  const hospitalizationSyncPreviewError = ref('')
  const hospitalizationSyncPreview = ref<HospitalizationScopePreview | null>(null)
  const hospitalizationSyncPreviewRequestSequence = ref(0)
  const hospitalizationSyncForm = ref({
    scopeMode: 'active_and_discharged' as HospitalizationScopeMode,
    asOfDate: '',
    dischargeStartDate: '',
    dischargeEndDate: '',
    departments: [] as string[],
  })

  const hospitalizationScopeOptions = [
    { label: '在院 + 期间出院', value: 'active_and_discharged' },
    { label: '当前在院', value: 'active' },
    { label: '期间出院', value: 'discharged' },
  ]
  const hospitalizationScopeNeedsDischargeRange = computed(() =>
    ['discharged', 'active_and_discharged'].includes(hospitalizationSyncForm.value.scopeMode),
  )
  const hospitalizationSyncDepartmentOptions = computed(() =>
    (hospitalizationSyncPreview.value?.departments || []).map((department) => ({
      label: `${department.name}（${department.total_count}）`,
      value: department.name,
    })),
  )
  const hospitalizationPreviewMetrics = computed(() => {
    const counts = hospitalizationSyncPreview.value?.counts
    return [
      { label: '当前在院', value: Number(counts?.active || 0) },
      { label: '期间出院', value: Number(counts?.discharged || 0) },
      { label: '去重后', value: Number(counts?.deduplicated || 0) },
      { label: '已在池中', value: Number(counts?.existing_in_pool || 0) },
      { label: '预计新增', value: Number(counts?.new_to_pool || 0) },
    ]
  })
  const hospitalizationSyncCanSubmit = computed(
    () =>
      !hospitalizationSyncPreviewLoading.value &&
      !hospitalizationSyncPreviewError.value &&
      Number(hospitalizationSyncPreview.value?.counts?.deduplicated || 0) > 0,
  )
  const hospitalizationSyncOkText = computed(() => {
    const count = Number(hospitalizationSyncPreview.value?.counts?.deduplicated || 0)
    return count > 0 ? `同步 ${count} 份病历` : '开始同步'
  })

  function currentLocalDate(): string {
    const now = new Date()
    const offset = now.getTimezoneOffset() * 60_000
    return new Date(now.getTime() - offset).toISOString().slice(0, 10)
  }

  function buildHospitalizationScopePayload(): HospitalizationScopePayload | null {
    const form = hospitalizationSyncForm.value
    if (!form.asOfDate) return null
    if (
      hospitalizationScopeNeedsDischargeRange.value &&
      (!form.dischargeStartDate || !form.dischargeEndDate)
    ) {
      return null
    }
    return {
      scope_mode: form.scopeMode,
      as_of_date: form.asOfDate,
      discharge_start_date: hospitalizationScopeNeedsDischargeRange.value
        ? form.dischargeStartDate
        : null,
      discharge_end_date: hospitalizationScopeNeedsDischargeRange.value
        ? form.dischargeEndDate
        : null,
      departments: form.departments.filter(Boolean),
    }
  }

  async function refreshHospitalizationScopePreview() {
    const poolId = selectedPoolId.value
    const payload = buildHospitalizationScopePayload()
    if (!poolId || !payload) return
    const requestSequence = ++hospitalizationSyncPreviewRequestSequence.value
    hospitalizationSyncPreviewLoading.value = true
    hospitalizationSyncPreviewError.value = ''
    const result = await previewManualSamplePoolHospitalizationScope(poolId, payload)
    if (requestSequence !== hospitalizationSyncPreviewRequestSequence.value) return
    hospitalizationSyncPreviewLoading.value = false
    if (!result.success || !result.data) {
      hospitalizationSyncPreview.value = null
      hospitalizationSyncPreviewError.value =
        result.message || '暂时无法读取住院范围，请检查源库连接后重试。'
      return
    }
    hospitalizationSyncPreview.value = result.data
  }

  async function openHospitalizationSyncModal() {
    if (!selectedPoolId.value) {
      message.warning('请先选择样本池')
      return
    }
    if (!hospitalizationSyncForm.value.asOfDate) {
      const today = currentLocalDate()
      hospitalizationSyncForm.value = {
        scopeMode: 'active_and_discharged',
        asOfDate: today,
        dischargeStartDate: today,
        dischargeEndDate: today,
        departments: [],
      }
    }
    hospitalizationSyncModalOpen.value = true
    await refreshHospitalizationScopePreview()
  }

  async function handleHospitalizationSync() {
    const poolId = selectedPoolId.value
    const payload = buildHospitalizationScopePayload()
    if (!poolId) {
      message.warning('请先选择样本池')
      return
    }
    if (!payload) {
      message.warning('请完整填写住院范围日期')
      return
    }
    if (!hospitalizationSyncCanSubmit.value) {
      message.warning(hospitalizationSyncPreviewError.value || '当前住院范围没有可同步病历')
      return
    }
    hospitalizationSyncSubmitting.value = true
    const result = await syncManualSamplePoolRecordsByHospitalization(poolId, payload)
    hospitalizationSyncSubmitting.value = false
    if (!result.success || !result.data) {
      message.error(result.message || '按住院范围同步病历失败')
      return
    }
    hospitalizationSyncModalOpen.value = false
    message.success('住院范围同步任务已创建')
    await openSyncJob(result.data.job_id)
  }

  return {
    hospitalizationSyncModalOpen,
    hospitalizationSyncSubmitting,
    hospitalizationSyncPreviewLoading,
    hospitalizationSyncPreviewError,
    hospitalizationSyncPreview,
    hospitalizationSyncForm,
    hospitalizationScopeOptions,
    hospitalizationScopeNeedsDischargeRange,
    hospitalizationSyncDepartmentOptions,
    hospitalizationPreviewMetrics,
    hospitalizationSyncCanSubmit,
    hospitalizationSyncOkText,
    refreshHospitalizationScopePreview,
    openHospitalizationSyncModal,
    handleHospitalizationSync,
  }
}
