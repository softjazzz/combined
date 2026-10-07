import { useWorkstationConfirmation } from '@/components/layout/workstationConfirmation'
import { h, ref, type Ref } from 'vue'
import { message } from 'ant-design-vue'
import { useRoute, useRouter } from 'vue-router'
import type { ManualSamplePool, ManualSamplePoolRecord } from './types'
import {
  deleteManualSamplePool,
  listManualSamplePools,
} from '@/services/manual-case-sample-service'
import { CUSTOMER_TEST_POOL_ID } from './recordPresentation'

export interface CustomerSamplePoolManagementDependencies {
  selectedPoolId: Ref<string | undefined>
  selectedPool: Ref<ManualSamplePool | undefined>
  records: Ref<ManualSamplePoolRecord[]>
  pagination: Ref<{ page: number; pageSize: number; total: number }>
  selectedRowKeys: Ref<string[]>
  loadPools: () => Promise<void>
}

export function useCustomerSamplePoolManagement(
  dependencies: CustomerSamplePoolManagementDependencies,
) {
  const workstationConfirmation = useWorkstationConfirmation()
  const route = useRoute()
  const router = useRouter()
  const { selectedPoolId, selectedPool, records, pagination, selectedRowKeys, loadPools } =
    dependencies

  const poolManagementOpen = ref(false)
  const poolManagementLoading = ref(false)
  const poolManagementQuery = ref('')
  const managedPools = ref<ManualSamplePool[]>([])
  const deletingPoolIds = ref<string[]>([])
  const poolManagementPagination = ref({
    page: 1,
    pageSize: 10,
    total: 0,
  })

  async function loadManagedPools() {
    poolManagementLoading.value = true
    const result = await listManualSamplePools({
      q: poolManagementQuery.value.trim() || undefined,
      page: poolManagementPagination.value.page,
      page_size: poolManagementPagination.value.pageSize,
    })
    poolManagementLoading.value = false
    if (!result.success || !result.data) {
      managedPools.value = []
      message.error(result.message || '获取样本池失败')
      return
    }
    managedPools.value = result.data.items
    poolManagementPagination.value.total = result.data.total
  }

  async function openPoolManagement() {
    poolManagementOpen.value = true
    poolManagementQuery.value = ''
    poolManagementPagination.value.page = 1
    await loadManagedPools()
  }

  async function handlePoolManagementSearch() {
    poolManagementPagination.value.page = 1
    await loadManagedPools()
  }

  function poolJobStatusLabel(status: string) {
    const labels: Record<string, string> = {
      queued: '排队中',
      running: '执行中',
      cancel_requested: '停止中',
      completed: '已完成',
      failed: '失败',
      canceled: '已停止',
      cancelled: '已停止',
    }
    return labels[String(status || '').toLowerCase()] || status
  }

  function poolDeletionDisabled(pool: ManualSamplePool) {
    if (pool.id === CUSTOMER_TEST_POOL_ID) return true
    return ['queued', 'running', 'cancel_requested'].includes(
      String(pool.latest_job_status || '').toLowerCase(),
    )
  }

  function confirmDeletePool(pool: ManualSamplePool) {
    if (poolDeletionDisabled(pool)) return
    workstationConfirmation.confirm({
      title: `删除样本池“${pool.name || '未命名样本池'}”？`,
      content: h('div', { class: 'space-y-2 text-[13px] leading-6 text-slate-600' }, [
        h('p', `将删除该池及其中 ${pool.total_items || 0} 份样本，并清除该池的同步任务记录。`),
        h('p', '原始病历、Bundle 和已经完成的质控结果不会被删除。此操作无法撤销。'),
      ]),
      okText: '确认删除',
      cancelText: '取消',
      okType: 'danger',
      async onOk() {
        deletingPoolIds.value = [...deletingPoolIds.value, pool.id]
        const result = await deleteManualSamplePool(pool.id)
        deletingPoolIds.value = deletingPoolIds.value.filter((id) => id !== pool.id)
        if (!result.success || !result.data?.deleted) {
          message.error(result.message || '删除样本池失败')
          throw new Error(result.message || '删除样本池失败')
        }
        if (selectedPoolId.value === pool.id) {
          selectedPoolId.value = undefined
          selectedPool.value = undefined
          records.value = []
          pagination.value.total = 0
          selectedRowKeys.value = []
          const nextQuery = { ...route.query }
          delete nextQuery.poolId
          await router.replace({ query: nextQuery })
        }
        message.success(`已删除样本池“${result.data.pool_name || pool.name}”`)
        await Promise.all([loadManagedPools(), loadPools()])
      },
    })
  }

  return {
    poolManagementOpen,
    poolManagementLoading,
    poolManagementQuery,
    managedPools,
    deletingPoolIds,
    poolManagementPagination,
    loadManagedPools,
    openPoolManagement,
    handlePoolManagementSearch,
    poolJobStatusLabel,
    poolDeletionDisabled,
    confirmDeletePool,
  }
}
